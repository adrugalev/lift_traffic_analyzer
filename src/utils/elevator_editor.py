"""Нормализация строк табличного редактора лифтов."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from src.models.elevator import Elevator
from src.utils.decimal_input import parse_decimal


ELEVATOR_EDITOR_COLUMNS = (
    "Наименование",
    "Г/п, кг",
    "Номинал, пасс.",
    "Заполнение, %",
    "Скорость, м/с",
    "Ускорение, м/с²",
    "Замедление, м/с²",
    "Рывок, м/с³",
    "Дверь, м",
    "Тип дверей",
    "Открытие, с",
    "Закрытие, с",
    "Предв. открытие, с",
    "Задержка, с",
    "Задержка пуска, с",
    "Посадка, с/пасс.",
    "Высадка, с/пасс.",
    "Остановки",
    "МГН",
)

ELEVATOR_DECIMAL_COLUMNS = (
    "Г/п, кг",
    "Скорость, м/с",
    "Ускорение, м/с²",
    "Замедление, м/с²",
    "Рывок, м/с³",
    "Дверь, м",
    "Открытие, с",
    "Закрытие, с",
    "Предв. открытие, с",
    "Задержка, с",
    "Задержка пуска, с",
    "Посадка, с/пасс.",
    "Высадка, с/пасс.",
)


def elevator_to_editor_row(elevator: Elevator) -> dict[str, object]:
    """Преобразует модель лифта в строку редактора."""

    return {
        "Наименование": elevator.name,
        "Г/п, кг": elevator.capacity_kg,
        "Номинал, пасс.": elevator.nominal_passengers,
        "Заполнение, %": round(elevator.load_factor * 100),
        "Скорость, м/с": elevator.speed_mps,
        "Ускорение, м/с²": elevator.acceleration_mps2,
        "Замедление, м/с²": elevator.deceleration_mps2,
        "Рывок, м/с³": elevator.jerk_mps3,
        "Дверь, м": elevator.door_width_m,
        "Тип дверей": elevator.door_opening_type.value,
        "Открытие, с": elevator.door_open_time_s,
        "Закрытие, с": elevator.door_close_time_s,
        "Предв. открытие, с": elevator.pre_open_time_s,
        "Задержка, с": elevator.door_dwell_time_s,
        "Задержка пуска, с": elevator.start_brake_allowance_s,
        "Посадка, с/пасс.": elevator.boarding_time_per_passenger_s,
        "Высадка, с/пасс.": elevator.alighting_time_per_passenger_s,
        "Остановки": elevator.stops_count,
        "МГН": elevator.accessible,
    }


def _missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _next_name(last_name: str, existing_names: set[str]) -> str:
    match = re.match(r"^(.*?)(\d+)$", last_name.strip())
    if match:
        prefix, number = match.groups()
        candidate_number = int(number) + 1
        candidate = f"{prefix}{candidate_number}"
        while candidate in existing_names:
            candidate_number += 1
            candidate = f"{prefix}{candidate_number}"
        return candidate
    candidate_number = len(existing_names) + 1
    candidate = f"Лифт {candidate_number}"
    while candidate in existing_names:
        candidate_number += 1
        candidate = f"Лифт {candidate_number}"
    return candidate


def normalize_elevator_editor_frame(
    frame: pd.DataFrame,
    existing_elevators: list[Elevator],
    stops_count: int,
) -> pd.DataFrame:
    """Заполняет новые строки по предыдущему лифту и синхронизирует остановки."""

    working = frame.copy()
    for column in ELEVATOR_EDITOR_COLUMNS:
        if column not in working:
            working[column] = None
    working = working[list(ELEVATOR_EDITOR_COLUMNS)]

    default_row = elevator_to_editor_row(
        existing_elevators[-1] if existing_elevators else Elevator()
    )
    existing_names = {
        str(value).strip()
        for value in working["Наименование"]
        if not _missing(value) and str(value).strip()
    }
    records: list[dict[str, object]] = []
    for row_index, raw in enumerate(working.to_dict("records")):
        is_new = row_index >= len(existing_elevators)
        template = records[-1] if records else default_row
        record = dict(raw)
        if is_new:
            for column in ELEVATOR_EDITOR_COLUMNS:
                if _missing(record.get(column)):
                    record[column] = template[column]
            if _missing(raw.get("Наименование")):
                record["Наименование"] = _next_name(
                    str(template["Наименование"]), existing_names
                )
        for column in ELEVATOR_DECIMAL_COLUMNS:
            record[column] = parse_decimal(record[column])
        record["Остановки"] = stops_count
        name = str(record.get("Наименование") or "").strip()
        if name:
            existing_names.add(name)
        records.append(record)
    return pd.DataFrame(records, columns=ELEVATOR_EDITOR_COLUMNS)


def elevator_editor_frames_equal(left: pd.DataFrame, right: pd.DataFrame) -> bool:
    """Сравнивает редакторские таблицы без влияния типов pandas."""

    if left.shape != right.shape or list(left.columns) != list(right.columns):
        return False
    return left.fillna("").astype(str).equals(right.fillna("").astype(str))
