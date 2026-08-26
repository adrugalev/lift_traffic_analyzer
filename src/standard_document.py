"""Доступ к нормативному документу, поставляемому вместе с приложением."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path


GOST_DOCUMENT_LABEL = "ГОСТ 34758-2021"
GOST_DOCUMENT_FILENAME = "ГОСТ_34758-2021.pdf"
GOST_DOCUMENT_PATH = (
    Path(__file__).resolve().parents[1] / "data" / "gost34758-2021.pdf"
)


@lru_cache(maxsize=1)
def gost_document_bytes() -> bytes:
    """Возвращает проверенный PDF стандарта для скачивания в браузере."""

    data = GOST_DOCUMENT_PATH.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise ValueError("Файл ГОСТ повреждён или не является PDF.")
    return data
