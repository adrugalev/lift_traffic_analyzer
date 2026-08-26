"""Регрессия скачивания нормативного отчёта на странице расчёта."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from src import ui
from src.engines.analytic_engine import AnalyticEngine
from src.services.project_service import ProjectService


def test_gost_download_is_rendered_on_calculation_page(monkeypatch) -> None:
    """Нормативный DOCX доступен рядом с расчётом даже при отсутствии PDF."""

    monkeypatch.setattr(ui, "render_navigation", lambda: None)
    project = ProjectService.create_default()
    result = AnalyticEngine().calculate_normative(project)
    calculation_page = (
        Path(__file__).resolve().parents[2] / "pages" / "05_analytic_calculation.py"
    )
    app = AppTest.from_file(str(calculation_page))
    app.session_state["project"] = project
    app.session_state["analytic_result"] = result
    app.session_state["simulation_result"] = None
    app.session_state["variants"] = []
    app.session_state["gost_report_docx"] = b"docx-only"

    app.run(timeout=20)

    assert not app.exception
    assert [button.label for button in app.get("download_button")] == ["Скачать DOCX"]
