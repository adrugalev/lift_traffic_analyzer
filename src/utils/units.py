"""Явные преобразования единиц измерения."""

from __future__ import annotations


SECONDS_PER_FIVE_MINUTES = 300.0


def seconds_to_minutes(seconds: float) -> float:
    """Преобразует секунды в минуты."""

    return seconds / 60.0


def percent_to_fraction(percent: float) -> float:
    """Преобразует проценты в долю единицы."""

    return percent / 100.0

