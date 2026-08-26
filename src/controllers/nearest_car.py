"""Базовый контроллер ближайшей свободной кабины."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class ElevatorStateLike(Protocol):
    """Минимальный интерфейс состояния кабины для диспетчеризации."""

    index: int
    current_floor: int
    idle: bool


def choose_nearest_car(elevators: Iterable[ElevatorStateLike], origin_floor: int) -> int:
    """Возвращает индекс ближайшей свободной кабины с устойчивым tie-break."""

    candidates = [elevator for elevator in elevators if elevator.idle]
    if not candidates:
        raise ValueError("Нет свободной кабины.")
    chosen = min(candidates, key=lambda item: (abs(item.current_floor - origin_floor), item.index))
    return chosen.index

