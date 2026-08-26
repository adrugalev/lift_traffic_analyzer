"""Проверка добавления лифта по образцу последнего."""

from __future__ import annotations

import pytest

from src.models.elevator import Elevator
from src.services.elevator_service import clone_last_elevator


def test_clone_last_elevator_copies_parameters_and_increments_name() -> None:
    first = Elevator(name="Лифт A1", speed_mps=1.6)
    last = Elevator(
        name="Лифт A4",
        speed_mps=2.5,
        acceleration_mps2=0.8,
        deceleration_mps2=0.9,
        jerk_mps3=1.1,
        door_open_time_s=2.7,
    )

    clone = clone_last_elevator([first, last])

    assert clone.name == "Лифт A5"
    assert clone.id != last.id
    assert clone.model_dump(exclude={"id", "name"}) == last.model_dump(
        exclude={"id", "name"}
    )


def test_clone_last_elevator_requires_existing_template() -> None:
    with pytest.raises(ValueError):
        clone_last_elevator([])
