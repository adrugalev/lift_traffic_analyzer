"""Проверки автозаполнения редактора этажей."""

from __future__ import annotations

import pandas as pd
import pytest

from src.services.project_service import ProjectService
from src.utils.floor_editor import (
    apply_floor_bulk_fill,
    delete_floor_rows,
    normalize_floor_editor_frame,
)


def _frame(project) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Этаж": floor.number,
                "Метка": floor.label,
                "Отметка, м": floor.elevation_m,
                "Высота, м": floor.floor_height_m,
                "Назначение": floor.purpose,
                "Население": floor.population,
                "Основной посадочный этаж": floor.is_main_entrance,
                "Входной этаж": floor.is_entrance,
                "Паркинг": floor.is_parking,
            }
            for floor in project.floors
        ]
    )


def test_new_row_continues_numbering_and_typical_values() -> None:
    project = ProjectService.create_default(floors_count=3)
    frame = pd.concat(
        [_frame(project), pd.DataFrame([{}])],
        ignore_index=True,
    )

    normalized = normalize_floor_editor_frame(frame, project.floors)
    new_row = normalized.iloc[-1]

    assert new_row["Этаж"] == 4
    assert new_row["Метка"] == "4"
    assert new_row["Назначение"] == "Типовой этаж"
    assert new_row["Высота, м"] == pytest.approx(3.0)
    assert new_row["Население"] == 20
    assert new_row["Отметка, м"] == pytest.approx(9.0)


def test_height_edit_recalculates_following_elevations() -> None:
    project = ProjectService.create_default(floors_count=4)
    frame = _frame(project)
    frame.loc[frame["Этаж"] == 2, "Высота, м"] = 4.2

    normalized = normalize_floor_editor_frame(frame, project.floors)
    elevations = normalized.set_index("Этаж")["Отметка, м"].to_dict()

    assert elevations[1] == pytest.approx(0.0)
    assert elevations[2] == pytest.approx(3.0)
    assert elevations[3] == pytest.approx(7.2)
    assert elevations[4] == pytest.approx(10.2)


def test_new_negative_floor_becomes_parking() -> None:
    project = ProjectService.create_default(floors_count=2)
    frame = pd.concat(
        [
            _frame(project),
            pd.DataFrame([{"Этаж": -1, "Высота, м": 3.3}]),
        ],
        ignore_index=True,
    )

    normalized = normalize_floor_editor_frame(frame, project.floors)
    parking = normalized.loc[normalized["Этаж"] == -1].iloc[0]

    assert parking["Метка"] == "P1"
    assert parking["Назначение"] == "Подземный паркинг"
    assert parking["Население"] == 0
    assert bool(parking["Паркинг"])
    assert parking["Отметка, м"] == pytest.approx(-3.3)


def test_duplicate_floor_numbers_are_rejected() -> None:
    project = ProjectService.create_default(floors_count=2)
    frame = _frame(project)
    frame.loc[1, "Этаж"] = 1

    with pytest.raises(ValueError, match="не должны повторяться"):
        normalize_floor_editor_frame(frame, project.floors)


def test_bulk_fill_extends_table_to_requested_upper_floor() -> None:
    project = ProjectService.create_default(floors_count=10)

    result, added_count = apply_floor_bulk_fill(
        _frame(project), project.floors, 1, 20, 3.0, 24
    )

    assert added_count == 10
    assert result["Этаж"].tolist() == list(range(1, 21))
    assert result.loc[result["Этаж"] == 20, "Население"].iloc[0] == 24
    assert result.loc[result["Этаж"] == 20, "Отметка, м"].iloc[0] == pytest.approx(
        57.0
    )
    assert result.loc[result["Этаж"] == 1, "Население"].iloc[0] == 0


def test_bulk_fill_can_add_underground_parking_floors() -> None:
    project = ProjectService.create_default(floors_count=2)

    result, added_count = apply_floor_bulk_fill(
        _frame(project), project.floors, -2, 2, 3.3, 30
    )

    assert added_count == 2
    assert result["Этаж"].tolist() == [-2, -1, 1, 2]
    parking = result[result["Этаж"] < 0]
    assert parking["Население"].tolist() == [0, 0]
    assert parking["Паркинг"].tolist() == [True, True]
    assert parking["Метка"].tolist() == ["P2", "P1"]


def test_bulk_fill_rejects_reversed_range() -> None:
    project = ProjectService.create_default(floors_count=3)

    with pytest.raises(ValueError, match="Начальный этаж"):
        apply_floor_bulk_fill(_frame(project), project.floors, 10, 1, 3.0, 20)


def test_height_accepts_comma_or_dot_as_decimal_separator() -> None:
    project = ProjectService.create_default(floors_count=3)
    frame = _frame(project)
    frame["Высота, м"] = frame["Высота, м"].astype(object)
    frame.loc[frame["Этаж"] == 1, "Высота, м"] = "3,25"
    frame.loc[frame["Этаж"] == 2, "Высота, м"] = "3.50"

    normalized = normalize_floor_editor_frame(frame, project.floors)

    heights = normalized.set_index("Этаж")["Высота, м"].to_dict()
    assert heights[1] == pytest.approx(3.25)
    assert heights[2] == pytest.approx(3.5)


def test_delete_multiple_floors_recalculates_elevations() -> None:
    project = ProjectService.create_default(floors_count=5)

    result, assigned_main = delete_floor_rows(
        _frame(project), project.floors, [3, 5]
    )

    assert result["Этаж"].tolist() == [1, 2, 4]
    assert result.set_index("Этаж")["Отметка, м"].to_dict() == {
        1: pytest.approx(0.0),
        2: pytest.approx(3.0),
        4: pytest.approx(6.0),
    }
    assert assigned_main is None


def test_delete_main_floor_assigns_lowest_remaining_non_parking_floor() -> None:
    project = ProjectService.create_default(floors_count=3)

    result, assigned_main = delete_floor_rows(
        _frame(project), project.floors, [1]
    )

    assert assigned_main == 2
    assert result.loc[
        result["Основной посадочный этаж"], "Этаж"
    ].tolist() == [2]
    assert result.set_index("Этаж").loc[2, "Отметка, м"] == pytest.approx(0.0)


def test_delete_all_floors_is_rejected() -> None:
    project = ProjectService.create_default(floors_count=2)

    with pytest.raises(ValueError, match="хотя бы один этаж"):
        delete_floor_rows(_frame(project), project.floors, [1, 2])
