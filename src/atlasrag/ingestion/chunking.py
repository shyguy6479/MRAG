import re
from dataclasses import dataclass

from atlasrag.ingestion.parsing import Section


@dataclass(frozen=True)
class Chunk:
    text: str
    section: str
    page: int | None
    ordinal: int


def windows(text: str, size: int, overlap: int) -> list[str]:
    # Preserve original substrings for auditable source excerpts.
    spans = list(re.finditer(r"\S+", text))
    result = []
    for start in range(0, len(spans), size - overlap):
        end = min(start + size, len(spans))
        result.append(text[spans[start].start() : spans[end - 1].end()])
        if end == len(spans):
            break
    return result


def chunk_sections(sections: list[Section], strategy: str, size: int, overlap: int) -> list[Chunk]:
    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("require 0 <= overlap < size")
    if strategy not in {"fixed", "recursive", "semantic"}:
        raise ValueError("unknown chunking strategy")
    chunks: list[Chunk] = []
    for section in sections:
        # Never cross page/section provenance boundaries, including fixed windows.
        if strategy == "fixed":
            pieces = windows(section.text, size, overlap)
        else:
            separator = r"\n\s*\n" if strategy == "semantic" else r"(?<=[.!?])\s+|\n\s*\n"
            units = [u.strip() for u in re.split(separator, section.text) if u.strip()]
            pieces, pending = [], ""
            for unit in units:
                if pending and len((pending + " " + unit).split()) > size:
                    pieces.extend(windows(pending, size, overlap))
                    pending = ""
                if len(unit.split()) > size:
                    if pending:
                        pieces.extend(windows(pending, size, overlap))
                        pending = ""
                    pieces.extend(windows(unit, size, overlap))
                else:
                    pending = f"{pending}\n\n{unit}".strip()
            if pending:
                pieces.extend(windows(pending, size, overlap))
        for piece in pieces:
            chunks.append(Chunk(piece, section.title, section.page, len(chunks)))
    return chunks
