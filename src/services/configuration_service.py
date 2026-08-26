"""Загрузка версионированной конфигурации без выполнения выражений."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


class ConfigurationError(RuntimeError):
    """Ошибка чтения конфигурационного файла."""


class ConfigurationService:
    """Читает JSON-совместимые YAML-файлы из каталога config."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self.config_dir = config_dir or Path(__file__).resolve().parents[2] / "config"

    @lru_cache(maxsize=16)
    def load(self, filename: str) -> dict[str, Any]:
        """Загружает конфигурацию и возвращает словарь."""

        path = (self.config_dir / filename).resolve()
        if path.parent != self.config_dir.resolve():
            raise ConfigurationError("Недопустимый путь конфигурации.")
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ConfigurationError(f"Не удалось прочитать {filename}: {exc}") from exc
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            try:
                import yaml

                data = yaml.safe_load(text)
                if not isinstance(data, dict):
                    raise ConfigurationError(f"Корень {filename} должен быть объектом.")
                return data
            except ImportError as exc:
                raise ConfigurationError(
                    f"{filename} не является JSON-совместимым YAML, а PyYAML не установлен."
                ) from exc

    def formulas(self) -> dict[str, Any]:
        """Возвращает реестр формул."""

        return self.load("formulas.yaml")

    def normative_values(self) -> dict[str, Any]:
        """Возвращает нормативные критерии."""

        return self.load("normative_values.yaml")

    def version_history(self) -> dict[str, Any]:
        """Возвращает краткую историю версий приложения."""

        return self.load("version_history.yaml")

    @property
    def normative_ready(self) -> bool:
        """Показывает, доступен ли хотя бы один нормативный режим."""

        standards = self.normative_values().get("standards", {})
        return any(
            item.get("verified", False) and item.get("assessment_enabled", False)
            for item in standards.values()
        )

    def standard_ready(self, standard_key: str) -> bool:
        """Проверяет готовность конкретной нормативной базы."""

        item = self.normative_values().get("standards", {}).get(standard_key, {})
        return bool(item.get("verified", False) and item.get("assessment_enabled", False))

    def standard(self, standard_key: str) -> dict[str, Any]:
        """Возвращает конфигурацию конкретного стандарта."""

        standards = self.normative_values().get("standards", {})
        if standard_key not in standards:
            raise ConfigurationError(f"Стандарт {standard_key!r} отсутствует в конфигурации.")
        return dict(standards[standard_key])

    @property
    def configuration_version(self) -> str:
        """Возвращает версию нормативной конфигурации."""

        return str(self.normative_values().get("configuration_version", "unknown"))
