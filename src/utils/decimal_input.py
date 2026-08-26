"""Разбор дробных значений из русской и международной записи."""

from __future__ import annotations

from typing import Any


def parse_decimal(value: Any) -> float:
    """Принимает число с запятой или точкой в качестве дробного разделителя."""

    if isinstance(value, str):
        normalized = value.strip().replace("\u00a0", "").replace(" ", "")
        if not normalized:
            raise ValueError("Введите числовое значение.")
        if "," in normalized and "." in normalized:
            raise ValueError("Используйте только один дробный разделитель.")
        value = normalized.replace(",", ".")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"Значение «{value}» должно быть числом; допустимы запятая и точка."
        ) from exc


def format_decimal(value: Any, digits: int = 2) -> str:
    """Форматирует значение для универсального текстового ввода."""

    return f"{parse_decimal(value):.{digits}f}"
