"""Упрощённая коллективная стратегия MVP."""

from __future__ import annotations

from collections.abc import Iterable

from .nearest_car import ElevatorStateLike, choose_nearest_car


def choose_collective_car(elevators: Iterable[ElevatorStateLike], origin_floor: int) -> int:
    """Назначает ближайшую свободную кабину.

    Очередь вызовов обслуживается по времени появления. Полная логика движения
    в направлении и попутных вызовов запланирована для следующего этапа.
    """

    return choose_nearest_car(elevators, origin_floor)

