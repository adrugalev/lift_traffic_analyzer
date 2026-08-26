"""Регрессия упрощённой страницы лифтов."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from src import ui
from src.services.project_service import ProjectService


def test_page_saves_all_lifts_as_one_implicit_group(monkeypatch) -> None:
    monkeypatch.setattr(ui, "render_navigation", lambda: None)
    project = ProjectService.create_default()
    second_group = project.elevator_groups[0].model_copy(deep=True)
    second_group.id = "second-group"
    for index, elevator in enumerate(second_group.elevators):
        elevator.id = f"second-{index}"
        elevator.name = f"Лифт B{index + 1}"
    project.elevator_groups.append(second_group)

    page = Path(__file__).resolve().parents[2] / "pages" / "03_elevator_groups.py"
    app = AppTest.from_file(str(page))
    app.session_state["project"] = project
    app.session_state["analytic_result"] = None
    app.session_state["simulation_result"] = None
    app.session_state["variants"] = []

    app.run(timeout=20)

    assert not app.exception
    assert [item.value for item in app.title] == ["3. Лифты"]
    assert "Добавить группу" not in [item.label for item in app.button]
    assert "Редактируемая группа" not in [item.label for item in app.selectbox]
    markdown_values = [item.value for item in app.markdown]
    assert "**Основные характеристики и движение**" in markdown_values
    assert "**Двери и пассажирообмен**" in markdown_values

    next(item for item in app.button if item.label == "Сохранить лифты").click()
    app.run(timeout=20)

    saved = app.session_state["project"]
    assert not app.exception
    assert len(saved.elevator_groups) == 1
    assert len(saved.elevator_groups[0].elevators) == 4
    assert saved.elevator_groups[0].served_floors == list(range(1, 11))
    assert all(
        floor.served_by_group_ids == [saved.elevator_groups[0].id]
        for floor in saved.floors
    )
