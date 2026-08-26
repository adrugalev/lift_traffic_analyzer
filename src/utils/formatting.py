"""Единообразное форматирование чисел для интерфейса и отчётов."""

from __future__ import annotations


def format_number(value: float, digits: int = 1) -> str:
    """Форматирует число с неразрывным разделителем тысяч."""

    return f"{value:,.{digits}f}".replace(",", "\u00a0")


def format_metric(value: float, unit: str, digits: int = 1) -> str:
    """Форматирует значение вместе с единицей измерения."""

    return f"{format_number(value, digits)} {unit}".strip()

