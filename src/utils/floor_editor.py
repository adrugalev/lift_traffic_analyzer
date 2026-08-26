"""Нормализация строк редактора этажей."""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.models.floor import Floor
from src.utils.decimal_input import parse_decimal


FLOOR_EDITOR_COLUMNS = (
    "Этаж",
    "Метка",
    "Отметка, м",
    "Высота, м",
    "Назначение",
    "Население",
    "Основной посадочный этаж",
    "Входной этаж",
    "Паркинг",
)


def _missing(value: Any) -> bool:
    """Проверяет пустое значение редактора, включая pandas NA."""

    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _text(value: Any, default: str = "") -> str:
    if _missing(value):
        return default
    text = str(value).strip()
    return text or default


def _number(value: Any, default: float) -> float:
    if _missing(value):
        return float(default)
    return parse_decimal(value)


def _integer(value: Any, default: int) -> int:
    if _missing(value):
        return int(default)
    return int(round(float(value)))


def _flag(value: Any) -> bool:
    return False if _missing(value) else bool(value)


def _next_floor_number(used: set[int]) -> int:
    """Продолжает надземную нумерацию, не создавая условный этаж 0."""

    positive = [number for number in used if number > 0]
    candidate = max(positive, default=0) + 1
    while candidate in used or candidate == 0:
        candidate += 1
    return candidate


def _defaults_from_existing(floors: list[Floor]) -> tuple[float, int, str]:
    typical = [
        floor
        for floor in floors
        if floor.number > 0
        and not floor.is_main_entrance
        and not floor.is_parking
    ]
    source = typical[-1] if typical else (floors[-1] if floors else None)
    if source is None:
        return 3.0, 0, "Типовой этаж"
    return source.floor_height_m, source.population, source.purpose


def normalize_floor_editor_frame(
    frame: pd.DataFrame,
    existing_floors: list[Floor],
) -> pd.DataFrame:
    """Заполняет новые строки и пересчитывает отметки относительно главного этажа.

    Поле ``Высота, м`` трактуется как расстояние от данного этажа до следующего
    над ним. Для главного и надземных этажей это даёт последовательное накопление
    отметок, а для подземных — отрицательные отметки.
    """

    working = frame.copy()
    for column in FLOOR_EDITOR_COLUMNS:
        if column not in working:
            working[column] = None
    working = working[list(FLOOR_EDITOR_COLUMNS)]

    default_height, default_population, default_purpose = _defaults_from_existing(
        existing_floors
    )
    used = {
        _integer(value, 0)
        for value in working["Этаж"]
        if not _missing(value)
    }
    records: list[dict[str, object]] = []
    for raw in working.to_dict("records"):
        is_new = _missing(raw.get("Этаж"))
        number = _next_floor_number(used) if is_new else _integer(raw["Этаж"], 0)
        if number == 0:
            raise ValueError("Номер этажа 0 не используется: примените −1 или 1.")
        if is_new:
            used.add(number)

        parking = _flag(raw.get("Паркинг")) or number < 0
        main = _flag(raw.get("Основной посадочный этаж"))
        entrance = _flag(raw.get("Входной этаж")) or main
        if parking:
            purpose_default = "Подземный паркинг"
            label_default = f"P{abs(number)}"
            population_default = 0
        elif main:
            purpose_default = "Входная группа"
            label_default = "Вход"
            population_default = 0
        else:
            purpose_default = default_purpose
            label_default = str(number)
            population_default = default_population

        records.append(
            {
                "Этаж": number,
                "Метка": _text(raw.get("Метка"), label_default),
                "Отметка, м": _number(raw.get("Отметка, м"), 0.0),
                "Высота, м": _number(raw.get("Высота, м"), default_height),
                "Назначение": _text(raw.get("Назначение"), purpose_default),
                "Население": (
                    0
                    if parking or main
                    else _integer(raw.get("Население"), population_default)
                ),
                "Основной посадочный этаж": main,
                "Входной этаж": entrance,
                "Паркинг": parking,
            }
        )

    if not records:
        return pd.DataFrame(columns=FLOOR_EDITOR_COLUMNS)
    numbers = [int(record["Этаж"]) for record in records]
    if len(numbers) != len(set(numbers)):
        raise ValueError("Номера этажей не должны повторяться.")
    records.sort(key=lambda record: int(record["Этаж"]))

    main_indices = [
        index
        for index, record in enumerate(records)
        if bool(record["Основной посадочный этаж"])
    ]
    if len(main_indices) == 1:
        main_index = main_indices[0]
        records[main_index]["Отметка, м"] = 0.0
        for index in range(main_index + 1, len(records)):
            records[index]["Отметка, м"] = round(
                float(records[index - 1]["Отметка, м"])
                + float(records[index - 1]["Высота, м"]),
                6,
            )
        for index in range(main_index - 1, -1, -1):
            records[index]["Отметка, м"] = round(
                float(records[index + 1]["Отметка, м"])
                - float(records[index]["Высота, м"]),
                6,
            )

    return pd.DataFrame(records, columns=FLOOR_EDITOR_COLUMNS)


def apply_floor_bulk_fill(
    frame: pd.DataFrame,
    existing_floors: list[Floor],
    start_floor: int,
    end_floor: int,
    height_m: float,
    population: int,
) -> tuple[pd.DataFrame, int]:
    """Добавляет отсутствующие этажи диапазона и применяет типовые значения."""

    start = int(start_floor)
    end = int(end_floor)
    if start > end:
        raise ValueError("Начальный этаж не должен быть выше конечного.")
    requested_numbers = [number for number in range(start, end + 1) if number != 0]
    if not requested_numbers:
        raise ValueError("Диапазон должен содержать хотя бы один этаж, кроме 0.")

    present_numbers = {
        _integer(value, 0)
        for value in frame.get("Этаж", pd.Series(dtype=float))
        if not _missing(value)
    }
    missing_numbers = [
        number for number in requested_numbers if number not in present_numbers
    ]
    expanded = frame.copy()
    if missing_numbers:
        expanded = pd.concat(
            [expanded, pd.DataFrame({"Этаж": missing_numbers})],
            ignore_index=True,
        )

    normalized = normalize_floor_editor_frame(expanded, existing_floors)
    mask = normalized["Этаж"].isin(requested_numbers)
    normalized.loc[mask, "Высота, м"] = float(height_m)
    normalized.loc[mask, "Население"] = int(population)
    normalized = normalize_floor_editor_frame(normalized, existing_floors)
    return normalized, len(missing_numbers)


def floor_editor_frames_equal(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    """Сравнивает кадры без ложных различий из-за pandas dtype."""

    try:
        pd.testing.assert_frame_equal(
            left.reset_index(drop=True),
            right.reset_index(drop=True),
            check_dtype=False,
            check_exact=False,
            atol=1e-9,
            rtol=1e-9,
        )
    except AssertionError:
        return False
    return True
