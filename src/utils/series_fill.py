"""Excel-подобное продолжение рядов поверх массового заполнения Streamlit."""

from __future__ import annotations

from numbers import Real
import re
from typing import Callable

import pandas as pd


SeriesValue = int | float | str
SeriesBuilder = Callable[[int], SeriesValue]


def _values_equal(left: object, right: object) -> bool:
    if pd.isna(left) and pd.isna(right):
        return True
    return bool(left == right)


def _series_builder(first: object, second: object) -> SeriesBuilder | None:
    """Возвращает продолжатель числового ряда или текста с числовым окончанием."""

    if (
        isinstance(first, Real)
        and not isinstance(first, bool)
        and isinstance(second, Real)
        and not isinstance(second, bool)
    ):
        step = float(second) - float(first)
        if abs(step) < 1e-12:
            return None
        integer_series = float(first).is_integer() and float(second).is_integer()

        def build_numeric(position: int) -> int | float:
            value = float(second) + position * step
            return int(round(value)) if integer_series else value

        return build_numeric

    if not isinstance(first, str) or not isinstance(second, str):
        return None
    first_match = re.fullmatch(r"(.*?)(-?\d+)(\D*)", first.strip())
    second_match = re.fullmatch(r"(.*?)(-?\d+)(\D*)", second.strip())
    if not first_match or not second_match:
        return None
    first_prefix, first_number, first_suffix = first_match.groups()
    second_prefix, second_number, second_suffix = second_match.groups()
    if first_prefix != second_prefix or first_suffix != second_suffix:
        return None
    step = int(second_number) - int(first_number)
    if step == 0:
        return None
    width = max(len(first_number.lstrip("-")), len(second_number.lstrip("-")))

    def build_text(position: int) -> str:
        value = int(second_number) + position * step
        sign = "-" if value < 0 else ""
        digits = str(abs(value)).zfill(width)
        return f"{second_prefix}{sign}{digits}{second_suffix}"

    return build_text


def continue_copied_series(
    previous: pd.DataFrame,
    edited: pd.DataFrame,
) -> tuple[pd.DataFrame, bool]:
    """Заменяет скопированный двухэлементный шаблон продолжением ряда вниз.

    Одиночное массовое заполнение и произвольные ручные изменения не затрагиваются.
    """

    if previous.shape != edited.shape or list(previous.columns) != list(edited.columns):
        return edited, False

    result = edited.copy(deep=True)
    series_continued = False
    for column in edited.columns:
        changed_rows = [
            row
            for row in range(len(edited))
            if not _values_equal(previous.iloc[row][column], edited.iloc[row][column])
        ]
        if len(changed_rows) < 2 or changed_rows[0] < 2:
            continue
        if changed_rows != list(range(changed_rows[0], changed_rows[-1] + 1)):
            continue

        start = changed_rows[0]
        first = edited.iloc[start - 2][column]
        second = edited.iloc[start - 1][column]
        builder = _series_builder(first, second)
        if builder is None:
            continue

        copied_pattern = (first, second)
        current_values = [edited.iloc[row][column] for row in changed_rows]
        if not all(
            _values_equal(value, copied_pattern[offset % 2])
            for offset, value in enumerate(current_values)
        ):
            continue

        generated = [builder(offset + 1) for offset in range(len(changed_rows))]
        if all(
            _values_equal(current, replacement)
            for current, replacement in zip(current_values, generated, strict=True)
        ):
            continue
        for row, value in zip(changed_rows, generated, strict=True):
            result.at[result.index[row], column] = value
        series_continued = True

    return result, series_continued
