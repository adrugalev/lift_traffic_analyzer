"""Проверка формата отображаемой версии приложения."""

from __future__ import annotations

import re
from pathlib import Path

from src import VERSION_DATE, VERSION_NUMBER, __version__
from src.services.configuration_service import ConfigurationService


def test_application_version_contains_release_number_and_date() -> None:
    assert __version__ == f"{VERSION_NUMBER}_{VERSION_DATE}"
    assert re.fullmatch(r"\d+_\d{2}\.\d{2}\.\d{4}", __version__)


def test_version_history_starts_with_current_release_and_stays_brief() -> None:
    history = ConfigurationService().version_history()
    versions = history["versions"]

    assert versions[0]["version"] == VERSION_NUMBER
    assert versions[0]["date"] == VERSION_DATE
    assert len({item["version"] for item in versions}) == len(versions)
    assert [int(item["version"]) for item in versions] == sorted(
        (int(item["version"]) for item in versions),
        reverse=True,
    )
    assert all(
        re.fullmatch(r"\d{2}\.\d{2}\.\d{4}", item["date"])
        for item in versions
    )
    assert all(1 <= len(item["changes_ru"]) <= 80 for item in versions)


def test_sidebar_opens_version_history_from_version_number() -> None:
    project_root = Path(__file__).resolve().parents[2]
    ui_text = (project_root / "src" / "ui.py").read_text(
        encoding="utf-8"
    )

    assert '@st.dialog("История версий", width="large")' in ui_text
    assert 'key="show_version_history_sidebar"' in ui_text
    assert "show_version_history()" in ui_text
