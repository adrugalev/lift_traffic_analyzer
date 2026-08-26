"""Доступ к метаданным формул без eval()."""

from __future__ import annotations

from typing import Any

from .configuration_service import ConfigurationService


class FormulaService:
    """Предоставляет проверяемый реестр формул."""

    def __init__(self, configuration: ConfigurationService | None = None) -> None:
        self.configuration = configuration or ConfigurationService()

    def get(self, formula_id: str) -> dict[str, Any]:
        """Возвращает описание формулы по идентификатору."""

        formulas = self.configuration.formulas().get("formulas", {})
        if formula_id not in formulas:
            raise KeyError(f"Формула {formula_id!r} отсутствует в реестре.")
        return dict(formulas[formula_id])

    def matrix_rows(self) -> list[dict[str, Any]]:
        """Преобразует реестр в строки матрицы соответствия."""

        rows: list[dict[str, Any]] = []
        for formula_id, item in self.configuration.formulas().get("formulas", {}).items():
            variables = ", ".join(
                f"{symbol} — {details.get('title_ru', '')} [{details.get('unit', '')}]"
                for symbol, details in item.get("variables", {}).items()
            )
            rows.append(
                {
                    "Расчётный показатель": item.get("title_ru", formula_id),
                    "Формула": item.get("expression", ""),
                    "Обозначения": variables,
                    "Единицы": item.get("unit", ""),
                    "Пункт стандарта": item.get("clause") or "не подтверждён",
                    "Реализация в коде": item.get("implementation", ""),
                    "Статус": item.get("status", ""),
                }
            )
        return rows

