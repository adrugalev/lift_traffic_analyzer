"""Проверки таблицы лифтов на странице симуляции."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from src import ui
from src.services.project_service import ProjectService


def test_simulation_page_shows_elevators_instead_of_group_selector(monkeypatch) -> None:
    monkeypatch.setattr(ui, "render_navigation", lambda: None)
    project = ProjectService.create_default()
    page = Path(__file__).resolve().parents[2] / "pages" / "06_simulation.py"
    app = AppTest.from_file(str(page))
    app.session_state["project"] = project

    app.run(timeout=20)

    assert not app.exception
    assert "Лифтовая группа" not in [item.label for item in app.selectbox]
    assert app.dataframe[0].value["Наименование"].tolist() == [
        elevator.name for elevator in project.elevator_groups[0].elevators
    ]
