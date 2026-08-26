"""Проверка инвалидирования сформированных отчётов."""

from __future__ import annotations

from types import SimpleNamespace

from src import ui
from src.services.project_service import ProjectService


class _SessionState(dict):
    """Минимальный словарь с атрибутным интерфейсом Streamlit."""

    def __getattr__(self, key: str):
        return self[key]

    def __setattr__(self, key: str, value) -> None:
        self[key] = value


def test_invalidate_generated_reports_removes_every_export(monkeypatch) -> None:
    state = _SessionState(
        report_docx=b"old",
        report_pdf=b"old",
        report_xlsx=b"old",
        gost_report_docx=b"old",
        gost_report_pdf=b"old",
        unrelated="keep",
    )
    monkeypatch.setattr(ui, "st", SimpleNamespace(session_state=state))

    ui.invalidate_generated_reports()

    assert not (set(ui.GENERATED_REPORT_KEYS) & set(state))
    assert state["unrelated"] == "keep"


def test_update_project_invalidates_results_and_reports(monkeypatch) -> None:
    state = _SessionState(
        analytic_result=object(),
        simulation_result=object(),
        variants=[object()],
        gost_report_docx=b"old",
        report_pdf=b"old",
    )
    monkeypatch.setattr(ui, "st", SimpleNamespace(session_state=state))
    project = ProjectService.create_default()

    ui.update_project(project)

    assert state.project is project
    assert state.analytic_result is None
    assert state.simulation_result is None
    assert state.variants == []
    assert "gost_report_docx" not in state
    assert "report_pdf" not in state
