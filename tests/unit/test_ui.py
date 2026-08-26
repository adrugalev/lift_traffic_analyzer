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


class _Sidebar:
    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None


class _NavigationStreamlit:
    def __init__(self, show_additional: bool) -> None:
        self.sidebar = _Sidebar()
        self.show_additional = show_additional
        self.links: list[str] = []
        self.session_state = _SessionState()
        self.markdown_values: list[str] = []

    def markdown(self, value: str, **_kwargs) -> None:
        self.markdown_values.append(value)

    def button(self, _label: str, **_kwargs) -> bool:
        return False

    def success(self, _text: str) -> None:
        return None

    def rerun(self) -> None:
        raise AssertionError("Неожиданный перезапуск в тесте навигации.")

    def checkbox(self, _label: str, **_kwargs) -> bool:
        return self.show_additional

    def page_link(self, page: str, **_kwargs) -> None:
        self.links.append(page)


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


def test_additional_navigation_is_hidden_by_default(monkeypatch) -> None:
    streamlit = _NavigationStreamlit(show_additional=False)
    monkeypatch.setattr(ui, "st", streamlit)

    ui.render_navigation()

    assert not (ui.ADDITIONAL_NAVIGATION & set(streamlit.links))
    assert "pages/05_analytic_calculation.py" in streamlit.links
    assert "pages/09_reference_data.py" in streamlit.links
    assert "app.py" not in streamlit.links
    assert ui.NAVIGATION[0] == ("pages/01_project.py", "1. Проект")
    branding = "\n".join(streamlit.markdown_values)
    assert "Расчёт пассажиропотока EPSS" in branding
    assert "Расчёт по ГОСТ и симуляция пассажиропотока" in branding


def test_additional_navigation_is_shown_by_checkbox(monkeypatch) -> None:
    streamlit = _NavigationStreamlit(show_additional=True)
    monkeypatch.setattr(ui, "st", streamlit)

    ui.render_navigation()

    assert ui.ADDITIONAL_NAVIGATION <= set(streamlit.links)


def test_four_section_heading_clicks_load_demo_project(monkeypatch) -> None:
    state = _SessionState(
        project=ProjectService.create_application_default(),
        analytic_result=None,
        simulation_result=None,
        variants=[],
    )
    monkeypatch.setattr(ui, "st", SimpleNamespace(session_state=state))

    assert ui.handle_demo_project_trigger(True) is False
    assert ui.handle_demo_project_trigger(True) is False
    assert ui.handle_demo_project_trigger(True) is False
    assert ui.handle_demo_project_trigger(True) is True

    assert state.sections_demo_click_count == 0
    assert state.project.metadata.name != "Новый проект"
    assert state.demo_project_loaded_notice.startswith("Загружен проект")
