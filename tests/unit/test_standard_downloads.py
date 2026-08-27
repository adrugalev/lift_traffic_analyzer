"""Проверки скачивания нормативного документа из справочного раздела."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from src import ui
from src.standard_document import gost_document_bytes


def test_embedded_gost_is_readable_pdf() -> None:
    data = gost_document_bytes()
    reader = PdfReader(BytesIO(data))

    assert data.startswith(b"%PDF-")
    assert len(reader.pages) == 28
    assert not reader.is_encrypted


def test_gost_download_is_available_in_criteria_section(monkeypatch) -> None:
    monkeypatch.setattr(ui, "render_navigation", lambda: None)
    root = Path(__file__).resolve().parents[2]
    page = AppTest.from_file(str(root / "pages" / "09_reference_data.py"))

    page.run(timeout=20)

    assert not page.exception
    assert [item.label for item in page.get("download_button")] == [
        "Скачать ГОСТ 34758-2021 (PDF)"
    ]
