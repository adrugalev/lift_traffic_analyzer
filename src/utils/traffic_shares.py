"""Зависимости между долями направлений пассажиропотока."""

from __future__ import annotations


def shares_from_incoming(incoming_percent: int) -> tuple[int, int, int]:
    """Сбрасывает межэтажный поток и отдаёт остаток исходящему."""

    if not 0 <= incoming_percent <= 100:
        raise ValueError("Входящий поток должен находиться в диапазоне от 0 до 100%.")
    return incoming_percent, 100 - incoming_percent, 0


def shares_from_interfloor(
    incoming_percent: int,
    interfloor_percent: int,
) -> tuple[int, int, int]:
    """Фиксирует входящий поток и вычитает межэтажный из исходящего."""

    if not 0 <= incoming_percent <= 100:
        raise ValueError("Входящий поток должен находиться в диапазоне от 0 до 100%.")
    maximum_interfloor = 100 - incoming_percent
    if not 0 <= interfloor_percent <= maximum_interfloor:
        raise ValueError(
            "Межэтажный поток не может превышать остаток после входящего потока."
        )
    return incoming_percent, maximum_interfloor - interfloor_percent, interfloor_percent
