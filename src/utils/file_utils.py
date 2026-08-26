"""Безопасная работа с именами экспортируемых файлов."""

from __future__ import annotations

import re


def safe_filename(value: str, fallback: str = "lift_traffic_project") -> str:
    """Удаляет недопустимые для имени файла символы."""

    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", value).strip(" ._")
    return cleaned or fallback

