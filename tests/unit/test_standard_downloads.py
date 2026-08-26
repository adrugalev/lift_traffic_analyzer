"""Проверки скачивания нормативного документа из разделов 8 и 9."""

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


def test_gost_downloads_are_available_in_sections_8_and_9(monkeypatch) -> None:
    monkeypatch.setattr(ui, "render_navigation", lambda: None)
    root = Path(__file__).resolve().parents[2]

    reference_page = AppTest.from_file(str(root / "pages" / "09_reference_data.py"))
    reference_page.run(timeout=20)
    about_page = AppTest.from_file(str(root / "pages" / "10_settings.py"))
    about_page.run(timeout=20)

    assert not reference_page.exception
    assert not about_page.exception
    assert "скачать ГОСТ" in [item.label for item in reference_page.get("download_button")]
    assert "ГОСТ 34758-2021" in [item.label for item in about_page.get("download_button")]
