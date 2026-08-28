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
    page_text = page.read_text(encoding="utf-8")
    assert "elevators_main_editor" not in page_text
    assert "elevators_doors_editor" not in page_text
    assert 'key=f"elevators_editor_{editor_revision}"' in page_text

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


def test_page_deletes_multiple_lifts_and_keeps_one_minimum(monkeypatch) -> None:
    monkeypatch.setattr(ui, "render_navigation", lambda: None)
    project = ProjectService.create_default()
    group = project.elevator_groups[0]
    for index in range(3, 5):
        elevator = group.elevators[-1].model_copy(deep=True)
        elevator.id = f"lift-{index}"
        elevator.name = f"Лифт A{index}"
        group.elevators.append(elevator)
    page = Path(__file__).resolve().parents[2] / "pages" / "03_elevator_groups.py"
    app = AppTest.from_file(str(page))
    app.session_state["project"] = project
    app.session_state["analytic_result"] = object()
    app.session_state["simulation_result"] = object()
    app.session_state["variants"] = [object()]

    app.run(timeout=20)
    assert not app.exception
    assert len(app.session_state["project"].elevator_groups[0].elevators) == 4

    selector = next(
        item for item in app.multiselect if item.label == "Лифты для удаления"
    )
    selector.set_value([1, 2]).run(timeout=20)
    next(item for item in app.button if item.label == "Удалить").click()
    app.run(timeout=20)

    saved = app.session_state["project"]
    assert not app.exception
    assert [item.name for item in saved.elevator_groups[0].elevators] == [
        "Лифт A1",
        "Лифт A4",
    ]
    assert app.session_state["analytic_result"] is None
    assert app.session_state["simulation_result"] is None
    assert app.session_state["variants"] == []

    selector = next(
        item for item in app.multiselect if item.label == "Лифты для удаления"
    )
    selector.set_value([0, 1]).run(timeout=20)
    assert next(
        item for item in app.button if item.label == "Удалить"
    ).disabled
