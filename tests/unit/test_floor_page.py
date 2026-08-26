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
