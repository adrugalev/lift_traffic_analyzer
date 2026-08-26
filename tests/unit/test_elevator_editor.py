"""Проверки табличного редактора лифтов."""

from __future__ import annotations

import pandas as pd

from src.models.elevator import Elevator
from src.utils.elevator_editor import (
    elevator_to_editor_row,
    normalize_elevator_editor_frame,
)


def test_new_row_continues_name_and_copies_previous_elevator() -> None:
    first = Elevator(name="Лифт A1", speed_mps=1.6)
    second = Elevator(
        name="Лифт A2",
        capacity_kg=1000,
        speed_mps=2.5,
        acceleration_mps2=0.8,
        jerk_mps3=1.0,
    )
    frame = pd.DataFrame(
        [elevator_to_editor_row(first), elevator_to_editor_row(second), {}]
    )

    normalized = normalize_elevator_editor_frame(frame, [first, second], 18)

    assert normalized.iloc[2]["Наименование"] == "Лифт A3"
    assert normalized.iloc[2]["Г/п, кг"] == 1000
    assert normalized.iloc[2]["Скорость, м/с"] == 2.5
    assert normalized.iloc[2]["Ускорение, м/с²"] == 0.8
    assert normalized.iloc[2]["Рывок, м/с³"] == 1.0
    assert normalized["Остановки"].tolist() == [18, 18, 18]


def test_multiple_new_rows_receive_consecutive_names() -> None:
    elevator = Elevator(name="Лифт 4")
    frame = pd.DataFrame([elevator_to_editor_row(elevator), {}, {}])

    normalized = normalize_elevator_editor_frame(frame, [elevator], 10)

    assert normalized["Наименование"].tolist() == ["Лифт 4", "Лифт 5", "Лифт 6"]


def test_existing_values_are_preserved_except_automatic_stops() -> None:
    elevator = Elevator(name="Лифт A1", speed_mps=2.0, stops_count=8)
    row = elevator_to_editor_row(elevator)
    row["Скорость, м/с"] = 3.0

    normalized = normalize_elevator_editor_frame(
        pd.DataFrame([row]), [elevator], 12
    )

    assert normalized.iloc[0]["Скорость, м/с"] == 3.0
    assert normalized.iloc[0]["Остановки"] == 12


def test_decimal_parameters_accept_comma_or_dot() -> None:
    elevator = Elevator(name="Лифт A1")
    row = elevator_to_editor_row(elevator)
    row["Скорость, м/с"] = "2,50"
    row["Ускорение, м/с²"] = "0.80"

    normalized = normalize_elevator_editor_frame(
        pd.DataFrame([row]), [elevator], 12
    )

    assert normalized.iloc[0]["Скорость, м/с"] == 2.5
    assert normalized.iloc[0]["Ускорение, м/с²"] == 0.8
