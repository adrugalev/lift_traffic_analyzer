"""Каноническое хэширование проектов."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def canonical_json(value: BaseModel | dict[str, Any]) -> str:
    """Сериализует модель в стабильную JSON-строку."""

    payload = value.model_dump(mode="json") if isinstance(value, BaseModel) else value
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def project_hash(value: BaseModel | dict[str, Any]) -> str:
    """Вычисляет SHA-256 канонического представления проекта."""

    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()

