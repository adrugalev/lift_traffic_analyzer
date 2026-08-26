"""Прозрачная базовая эвристика Destination Control."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class DestinationElevatorLike(Protocol):
    """Интерфейс кабины для оценки destination-control."""

    index: int
    current_floor: int
    idle: bool
    planned_destinations: list[int]


def choose_destination_car(
    elevators: Iterable[DestinationElevatorLike],
    origin_floor: int,
    destination_floor: int,
) -> int:
    """Минимизирует подачу и штраф за дополнительную остановку."""

    candidates = [elevator for elevator in elevators if elevator.idle]
    if not candidates:
        raise ValueError("Нет свободной кабины.")
    chosen = min(
        candidates,
        key=lambda item: (
            abs(item.current_floor - origin_floor)
            + (0 if destination_floor in item.planned_destinations else 1),
            item.index,
        ),
    )
    return chosen.index

