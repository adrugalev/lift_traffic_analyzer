"""Проверки пользовательской формы сценария пассажиропотока."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from src import ui
from src.models.traffic import ArrivalDistribution, TrafficScenarioType
from src.services.project_service import ProjectService


def test_gost_scenario_fills_and_locks_normative_parameters(monkeypatch) -> None:
    """Выбор «По ГОСТ» фиксирует нормативные параметры до смены сценария."""

    monkeypatch.setattr(ui, "render_navigation", lambda: None)
    page = Path(__file__).resolve().parents[2] / "pages" / "04_traffic.py"
    app = AppTest.from_file(str(page))
    app.session_state["project"] = ProjectService.create_default()

    app.run(timeout=20)
    scenario_select = next(
        item for item in app.selectbox if item.label == "Тип сценария"
    )
    scenario_select.select("По ГОСТ").run(timeout=20)

    distribution_select = next(
        item
        for item in app.selectbox
        if item.label == "Распределение поступления"
    )
    population_input = next(
        item
        for item in app.number_input
        if item.label == "Процент населения за 5 минут"
    )
    bursts_checkbox = next(
        item for item in app.checkbox if item.label == "Учитывать всплески"
    )
    sliders = {item.label: item for item in app.slider}

    assert not app.exception
    assert distribution_select.value is ArrivalDistribution.POISSON
    assert distribution_select.disabled
    assert population_input.value == 6.0
    assert population_input.disabled
    assert bursts_checkbox.value is False
    assert bursts_checkbox.disabled
    assert sliders["Входящий поток, %"].value == 100
    assert sliders["Входящий поток, %"].disabled
    assert sliders["Исходящий поток, % (автоматически)"].value == 0
    assert sliders["Межэтажный поток, %"].value == 0
    assert sliders["Межэтажный поток, %"].disabled

    next(
        button for button in app.button if button.label == "Сохранить сценарий"
    ).click().run(timeout=20)
    saved_scenario = app.session_state["project"].scenario()
    assert saved_scenario.name == "По ГОСТ"
    assert saved_scenario.scenario_type is TrafficScenarioType.UP_PEAK
