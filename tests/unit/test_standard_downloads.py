"""Проверки скачивания нормативного документа из справочного раздела."""

from __future__ import annotations

from io import BytesIO
from pypdf import PdfReader

from src.standard_document import gost_document_bytes


def test_embedded_gost_is_readable_pdf() -> None:
    data = gost_document_bytes()
    reader = PdfReader(BytesIO(data))

    assert data.startswith(b"%PDF-")
    assert len(reader.pages) == 28
    assert not reader.is_encrypted
