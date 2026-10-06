import io

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from atlasrag.core.errors import InvalidInput
from atlasrag.ingestion.parsing import parse


def pdf_fixture(encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=300, height=300)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 20 200 Td (Quantization reduces weight memory.) Tj ET")
    page[NameObject("/Contents")] = stream
    if encrypted:
        writer.encrypt("test-fixture-password")
    data = io.BytesIO()
    writer.write(data)
    return data.getvalue()


def test_pdf_text_and_page_provenance() -> None:
    sections = parse(pdf_fixture(), "pdf")
    assert sections[0].page == 1
    assert "Quantization reduces weight memory." in sections[0].text


def test_encrypted_pdf_rejected_explicitly() -> None:
    with pytest.raises(InvalidInput):
        parse(pdf_fixture(encrypted=True), "pdf")
