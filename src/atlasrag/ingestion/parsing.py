import io
import re
from dataclasses import dataclass

from bs4 import BeautifulSoup
from pypdf import PdfReader

from atlasrag.core.errors import CapacityExceeded, InvalidInput


@dataclass(frozen=True)
class Section:
    title: str
    text: str
    page: int | None = None


def clean(text: str) -> str:
    text = text.replace("\x00", "").replace("\r\n", "\n")
    text = re.sub(r"[^\S\n]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def markdown_sections(text: str, page: int | None = None) -> list[Section]:
    sections: list[Section] = []
    heading = "Overview"
    lines: list[str] = []
    for line in clean(text).splitlines():
        match = re.match(r"^#{1,6}\s+(.+)$", line)
        if match:
            if "\n".join(lines).strip():
                sections.append(Section(heading[:500], "\n".join(lines).strip(), page))
            heading, lines = match.group(1), []
        else:
            lines.append(line)
    if "\n".join(lines).strip():
        sections.append(Section(heading[:500], "\n".join(lines).strip(), page))
    return sections


def parse(raw: bytes, format: str) -> list[Section]:
    if format == "pdf":
        if not raw.startswith(b"%PDF-"):
            raise InvalidInput("PDF signature missing")
        try:
            reader = PdfReader(io.BytesIO(raw))
            if reader.is_encrypted:
                raise InvalidInput("encrypted PDFs are unsupported")
            if len(reader.pages) > 300:
                raise CapacityExceeded("maximum 300 PDF pages")
            sections = []
            total = 0
            for number, page in enumerate(reader.pages, start=1):
                text = clean(page.extract_text() or "")
                total += len(text.encode())
                if total > 5_000_000:
                    raise CapacityExceeded("extracted text limit")
                if text:
                    sections.append(Section(f"Page {number}", text, number))
        except (InvalidInput, CapacityExceeded):
            raise
        except Exception as exc:
            raise InvalidInput("unreadable PDF") from exc
    elif format in {"txt", "md", "html"}:
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InvalidInput("text must use UTF-8") from exc
        if "\x00" in text:
            raise InvalidInput("binary content is not text")
        if format == "html":
            soup = BeautifulSoup(text, "html.parser")
            for tag in soup(["script", "style", "iframe", "noscript", "svg"]):
                tag.decompose()
            for tag in soup.find_all(re.compile(r"^h[1-6]$")):
                tag.replace_with(f"\n# {tag.get_text(' ', strip=True)}\n")
            text = soup.get_text("\n")
        sections = markdown_sections(text)
    else:
        raise InvalidInput("unsupported format")
    if not sections:
        raise InvalidInput("document contains no extractable text; OCR is not included")
    return sections
