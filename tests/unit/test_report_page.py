"""Регрессия скачивания нормативного отчёта на странице расчёта."""

from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

from src import ui
from src.engines.analytic_engine import AnalyticEngine
from src.models.floor import Floor
from src.reports import gost_report
from src.services.project_service import ProjectService


def test_gost_download_is_rendered_on_calculation_page(monkeypatch) -> None:
    """Нормативный DOCX доступен рядом с расчётом даже при отсутствии PDF."""

    monkeypatch.setattr(ui, "render_navigation", lambda: None)
    project = ProjectService.create_default()
    result = AnalyticEngine().calculate_normative(project)
    calculation_page = (
        Path(__file__).resolve().parents[2] / "pages" / "05_analytic_calculation.py"
    )
    app = AppTest.from_file(str(calculation_page))
    app.session_state["project"] = project
    app.session_state["analytic_result"] = result
    app.session_state["simulation_result"] = None
    app.session_state["variants"] = []
    app.session_state["gost_report_docx"] = b"docx-only"
    app.session_state["gost_report_include_parking"] = False
    app.session_state["gost_report_include_extended_kinematics"] = False

    app.run(timeout=20)

    assert not app.exception
    assert "Лифтовая группа" not in [item.label for item in app.selectbox]
    assert [button.label for button in app.get("download_button")] == ["Скачать DOCX"]
    expander_labels = [item.label for item in app.expander]
    assert "Номинальная вместимость по грузоподъёмности: 13 пасс." in expander_labels
    assert "Расчётная вместимость кабины: 10 пасс." in expander_labels


def test_gost_calculation_separates_parking_reference(monkeypatch) -> None:
    """Основной результат не содержит паркинг, но справочный вариант сохраняется."""

    monkeypatch.setattr(ui, "render_navigation", lambda: None)

    def report_marker(_project, result) -> bytes:
        keys = {metric.key for metric in result.metrics}
        return (
            b"parking-report"
            if "parking_round_trip_addition" in keys
            else b"strict-gost-report"
        )

    monkeypatch.setattr(gost_report, "build_gost_docx_report", report_marker)
    monkeypatch.setattr(gost_report, "build_gost_pdf_report", report_marker)
    project = ProjectService.create_default()
    group = project.elevator_groups[0]
    project.floors.insert(
        0,
        Floor(
            number=-1,
            label="P1",
            elevation_m=-3.3,
            floor_height_m=3.3,
            purpose="Подземный паркинг",
            population=0,
            served_by_group_ids=[group.id],
            is_parking=True,
        ),
    )
    group.served_floors.insert(0, -1)
    project.scenario().parking_incoming_share = 0.15
    calculation_page = (
        Path(__file__).resolve().parents[2] / "pages" / "05_analytic_calculation.py"
    )
    app = AppTest.from_file(str(calculation_page))
    app.session_state["project"] = project
    app.session_state["analytic_result"] = None
    app.session_state["simulation_result"] = None
    app.session_state["variants"] = []

    app.run(timeout=20)
    next(
        button
        for button in app.button
        if button.label == "Выполнить расчёт по ГОСТ"
    ).click().run(timeout=20)

    assert not app.exception
    strict_result = app.session_state["analytic_result"]
    parking_result = app.session_state["parking_reference_result"]
    strict_metric_keys = {metric.key for metric in strict_result.metrics}
    assert "parking_round_trip_addition" not in strict_metric_keys
    assert parking_result.metric("parking_round_trip_addition").value > 0
    assert strict_result.metric("cycle_time").value == parking_result.metric(
        "gost_cycle_time_without_parking"
    ).value
    parking_checkbox = next(
        item
        for item in app.checkbox
        if item.label == "Включать в расчёт паркинг"
    )
    parking_checkbox.check().run(timeout=20)
    automatically_updated = app.session_state["analytic_result"]
    assert automatically_updated.metric("parking_round_trip_addition").value > 0
    assert app.session_state["gost_result_include_parking"] is True
    next(
        button
        for button in app.button
        if button.label == "Сформировать отчёт по ГОСТ (уточнённый)"
    ).click().run(timeout=20)
    assert app.session_state["gost_report_include_parking"] is True
    assert app.session_state["gost_report_docx"] == b"parking-report"

    next(
        item
        for item in app.checkbox
        if item.label == "Включать в расчёт паркинг"
    ).uncheck().run(timeout=20)
    automatically_updated = app.session_state["analytic_result"]
    assert "parking_round_trip_addition" not in {
        metric.key for metric in automatically_updated.metrics
    }
    assert app.session_state["gost_result_include_parking"] is False
    next(
        button
        for button in app.button
        if button.label == "Сформировать отчёт по ГОСТ"
    ).click().run(timeout=20)
    assert app.session_state["gost_report_include_parking"] is False
    assert app.session_state["gost_report_docx"] == b"strict-gost-report"

    kinematics_checkbox = next(
        item
        for item in app.checkbox
        if item.label == "Учитывать дополнительную кинематику"
    )
    kinematics_checkbox.check().run(timeout=20)
    automatically_updated = app.session_state["analytic_result"]
    assert "kinematic_maximum_speed" in {
        trace.formula_id for trace in automatically_updated.formulas
    }
    assert app.session_state["gost_result_include_extended_kinematics"] is True
    next(
        button
        for button in app.button
        if button.label == "Сформировать отчёт по ГОСТ (уточнённый)"
    ).click().run(timeout=20)
    assert app.session_state["gost_report_include_extended_kinematics"] is True
