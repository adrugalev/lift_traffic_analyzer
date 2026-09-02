"""Проверки порядка строк на странице этажей."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from src import ui
from src.services.project_service import ProjectService


def test_floor_table_displays_upper_floors_first(monkeypatch) -> None:
    monkeypatch.setattr(ui, "render_navigation", lambda: None)
    page = Path(__file__).resolve().parents[2] / "pages" / "02_floors.py"
    app = AppTest.from_file(str(page))
    app.session_state["project"] = ProjectService.create_default(floors_count=5)

    app.run(timeout=20)

    assert not app.exception
    assert app.dataframe[0].value["Этаж"].tolist() == [5, 4, 3, 2, 1]


def test_page_deletes_multiple_floors(monkeypatch) -> None:
    monkeypatch.setattr(ui, "render_navigation", lambda: None)
    page = Path(__file__).resolve().parents[2] / "pages" / "02_floors.py"
    app = AppTest.from_file(str(page))
    app.session_state["project"] = ProjectService.create_default(floors_count=5)
    app.session_state["analytic_result"] = object()
    app.session_state["simulation_result"] = object()
    app.session_state["variants"] = [object()]

    app.run(timeout=20)
    selector = next(
        item for item in app.multiselect if item.label == "Этажи для удаления"
    )
    selector.set_value([3, 5]).run(timeout=20)
    next(item for item in app.button if item.label == "Удалить").click()
    app.run(timeout=20)

    assert not app.exception
    assert [floor.number for floor in app.session_state["project"].floors] == [
        1,
        2,
        3,
    ]
    assert app.session_state["analytic_result"] is None
    assert app.session_state["simulation_result"] is None
    assert app.session_state["variants"] == []
    selector_after_deletion = next(
        item for item in app.multiselect if item.label == "Этажи для удаления"
    )
    assert selector_after_deletion.value == []
