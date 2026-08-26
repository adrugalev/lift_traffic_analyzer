"""Проверки Excel-подобного продолжения рядов."""

from __future__ import annotations

import pandas as pd

from src.utils.series_fill import continue_copied_series


def test_continues_numeric_series_from_two_cells() -> None:
    previous = pd.DataFrame({"value": [1000, 1100, 0, 0]})
    copied = pd.DataFrame({"value": [1000, 1100, 1000, 1100]})

    result, continued = continue_copied_series(previous, copied)

    assert continued is True
    assert result["value"].tolist() == [1000, 1100, 1200, 1300]


def test_continues_text_series_with_numeric_suffix() -> None:
    previous = pd.DataFrame(
        {"name": ["Лифт A01", "Лифт A02", "старое", "старое"]}
    )
    copied = pd.DataFrame(
        {"name": ["Лифт A01", "Лифт A02", "Лифт A01", "Лифт A02"]}
    )

    result, continued = continue_copied_series(previous, copied)

    assert continued is True
    assert result["name"].tolist() == [
        "Лифт A01",
        "Лифт A02",
        "Лифт A03",
        "Лифт A04",
    ]


def test_single_cell_fill_remains_a_copy() -> None:
    previous = pd.DataFrame({"value": [10, 20, 0, 0]})
    copied = pd.DataFrame({"value": [10, 20, 10, 0]})

    result, continued = continue_copied_series(previous, copied)

    assert continued is False
    assert result.equals(copied)


def test_manual_bulk_edit_is_not_rewritten() -> None:
    previous = pd.DataFrame({"value": [10, 20, 0, 0]})
    edited = pd.DataFrame({"value": [10, 20, 35, 45]})

    result, continued = continue_copied_series(previous, edited)

    assert continued is False
    assert result.equals(edited)
