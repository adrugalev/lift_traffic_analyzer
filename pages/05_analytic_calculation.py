"""Предварительный и нормативный аналитический расчёт."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.engines.analytic_engine import AnalyticEngine, NormativeConfigurationError
from src.engines.recommendation_engine import RecommendationEngine
from src.reports.gost_report import build_gost_docx_report, build_gost_pdf_report
from src.services.validation_service import ValidationService
from src.ui import (
    configure_page,
    ensure_session,
    invalidate_generated_reports,
    render_messages,
    update_project,
)
from src.utils.file_utils import safe_filename
from src.utils.traffic_profiles import scenario_for_gost_calculation


def _generate_gost_exports(project, result) -> list[str]:
    """Независимо формирует DOCX и PDF нормативного отчёта."""

    for key in ("gost_report_docx", "gost_report_pdf"):
        st.session_state.pop(key, None)
    errors: list[str] = []
    try:
        st.session_state.gost_report_docx = build_gost_docx_report(project, result)
    except Exception as exc:
        errors.append(f"DOCX: {exc}")
    try:
        st.session_state.gost_report_pdf = build_gost_pdf_report(project, result)
    except Exception as exc:
        errors.append(f"PDF: {exc}")
    return errors


configure_page("Расчёт и отчёт")
project = ensure_session()
engine = AnalyticEngine()
st.title("5. Расчёт и отчёт")
st.markdown(
    """
    <style>
    .st-key-analytic_metric_cards [data-testid="stMetricLabel"],
    .st-key-analytic_metric_cards [data-testid="stMetricLabel"] > div,
    .st-key-analytic_metric_cards [data-testid="stMetricLabel"] p {
        overflow: visible !important;
        text-overflow: clip !important;
        white-space: normal !important;
    }
    .st-key-analytic_metric_cards [data-testid="stMetricLabel"] {
        min-height: 2.4rem;
    }
    .st-key-analytic_metric_cards [data-testid="stMetricLabel"] p {
        font-size: 0.82rem !important;
        line-height: 1.25 !important;
    }
    .st-key-analytic_metric_cards [data-testid="stMetricValue"],
    .st-key-analytic_metric_cards [data-testid="stMetricValue"] > div {
        overflow: visible !important;
        text-overflow: clip !important;
        white-space: nowrap !important;
    }
    .st-key-analytic_metric_cards [data-testid="stMetricValue"] > div {
        font-size: clamp(1.45rem, 2.2vw, 2rem) !important;
        line-height: 1.15 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

messages = ValidationService.validate_project(project)
render_messages(messages)

if not project.elevator_groups:
    st.error("В разделе «3. Лифты» необходимо добавить хотя бы один лифт.")
    st.stop()
group = project.elevator_groups[0]
methods = st.columns(2)
with methods[0]:
    st.markdown("**Предварительный расчёт**")
    st.caption(
        "Использует сценарий, выбранный в разделе «4. Пассажиропоток». "
        "Предназначен для проверки произвольных направлений потока без оценки соответствия ГОСТ."
    )
    preview_clicked = st.button(
        "Выполнить предварительный расчёт",
        use_container_width=True,
        help=(
            "Выполняет инженерную оценку по текущему пользовательскому сценарию. "
            "Результат не является подтверждением соответствия ГОСТ."
        ),
    )
with methods[1]:
    st.markdown("**Расчёт по ГОСТ**")
    st.caption(
        "Автоматически применяет нормативный восходящий сценарий: "
        "100% входящего потока, 0% исходящего и 0% межэтажного."
    )
    normative_clicked = st.button(
        "Выполнить расчёт по ГОСТ",
        type="primary",
        use_container_width=True,
        help=(
            "Применяет нормативный восходящий пик и выполняет расчётный метод "
            "ГОСТ 34758-2021 с оценкой критериев."
        ),
    )

if preview_clicked:
    try:
        result = engine.calculate_preview(project, group.id)
        result.recommendations = RecommendationEngine.generate(result)
        invalidate_generated_reports()
        st.session_state.analytic_result = result
        st.success("Предварительный расчёт выполнен.")
    except Exception as exc:
        st.error(str(exc))
if normative_clicked:
    try:
        normative_project = project.model_copy(deep=True)
        current_scenario = normative_project.scenario()
        normative_scenario = scenario_for_gost_calculation(
            current_scenario,
            normative_project.building.building_type,
        )
        scenario_index = next(
            index
            for index, scenario in enumerate(normative_project.traffic_scenarios)
            if scenario.id == current_scenario.id
        )
        normative_project.traffic_scenarios[scenario_index] = normative_scenario
        result = engine.calculate_normative(normative_project, group.id)
        result.recommendations = RecommendationEngine.generate(result)
        update_project(normative_project)
        st.session_state.analytic_result = result
        with st.spinner("Подготавливается отчёт по ГОСТ…"):
            gost_export_errors = _generate_gost_exports(normative_project, result)
        st.success("Расчёт по ГОСТ выполнен.")
        if gost_export_errors:
            st.error(
                "Не удалось подготовить отдельные форматы отчёта: "
                + "; ".join(gost_export_errors)
            )
    except NormativeConfigurationError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(str(exc))

result = st.session_state.analytic_result
if result and result.calculation_basis == "GOST_34758_2021_CLAUSE_7":
    with methods[1]:
        st.caption("Отчёт по результатам нормативного расчёта")
        available_gost_reports = [
            ("DOCX", st.session_state.get("gost_report_docx")),
            ("PDF", st.session_state.get("gost_report_pdf")),
        ]
        available_gost_reports = [
            (kind, data) for kind, data in available_gost_reports if data is not None
        ]
        if not available_gost_reports:
            if st.button(
                "Подготовить отчёт по ГОСТ",
                key="prepare_gost_report",
                use_container_width=True,
                help="Формирует DOCX и PDF по результатам сохранённого расчёта.",
            ):
                with st.spinner("Подготавливается отчёт по ГОСТ…"):
                    gost_export_errors = _generate_gost_exports(project, result)
                if gost_export_errors:
                    st.error(
                        "Не удалось подготовить отдельные форматы отчёта: "
                        + "; ".join(gost_export_errors)
                    )
                st.rerun()
        else:
            base_name = safe_filename(st.session_state.project.metadata.name)
            download_columns = st.columns(len(available_gost_reports))
            for column, (kind, data) in zip(
                download_columns, available_gost_reports, strict=True
            ):
                if kind == "DOCX":
                    column.download_button(
                        "Скачать DOCX",
                        data,
                        f"{base_name}_GOST_34758-2021.docx",
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document",
                        use_container_width=True,
                        help="Скачивает редактируемый отчёт по ГОСТ.",
                    )
                else:
                    column.download_button(
                        "Скачать PDF",
                        data,
                        f"{base_name}_GOST_34758-2021.pdf",
                        "application/pdf",
                        use_container_width=True,
                        help="Скачивает отчёт по ГОСТ с фиксированной вёрсткой.",
                    )
if result:
    st.subheader("Основные показатели")
    keys = ["interval", "handling_capacity_5min", "average_wait_proxy", "reserve"]
    metric_help = {
        "interval": (
            "Расчётное время между последовательными отправлениями кабин "
            "с основного посадочного этажа."
        ),
        "handling_capacity_5min": (
            "Среднее число пассажиров, которое группа способна перевезти "
            "за расчётные пять минут."
        ),
        "average_wait_proxy": (
            "Ориентир I/2 при равномерных интервалах отправления. Фактическое "
            "ожидание определяется симуляцией и обычно бывает не меньше."
        ),
        "reserve": (
            "Превышение провозной способности над расчётным спросом, выраженное "
            "в процентах от спроса. Отрицательное значение означает дефицит."
        ),
    }
    with st.container(key="analytic_metric_cards"):
        columns = st.columns(4)
        for column, key in zip(columns, keys, strict=True):
            metric = result.metric(key)
            display_unit = "пасс." if key == "handling_capacity_5min" else metric.unit
            column.metric(
                metric.title_ru,
                f"{metric.value:.1f} {display_unit}",
                help=metric_help[key],
            )
    if result.calculation_basis == "GOST_34758_2021_CLAUSE_7":
        st.caption(
            "Статусы рассчитаны по критериям ГОСТ 34758-2021. "
            "Ориентировочное время ожидания нормативно не оценивается."
        )
    else:
        st.caption(
            "Предварительный результат для выбранного сценария. "
            "Соответствие ГОСТ не оценивается."
        )

    tabs = st.tabs(["Все показатели", "Формулы", "Сообщения", "Рекомендации", "Аудит"])
    with tabs[0]:
        st.dataframe(
            pd.DataFrame([metric.model_dump(mode="json") for metric in result.metrics]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "key": st.column_config.TextColumn(
                    "Код",
                    help="Внутренний неизменяемый идентификатор показателя.",
                ),
                "title_ru": st.column_config.TextColumn(
                    "Показатель",
                    help="Наименование расчётного или справочного показателя.",
                ),
                "value": st.column_config.NumberColumn(
                    "Значение",
                    help="Рассчитанное числовое значение до форматирования.",
                ),
                "unit": st.column_config.TextColumn(
                    "Единица",
                    help="Единица измерения рассчитанного значения.",
                ),
                "method": st.column_config.TextColumn(
                    "Метод",
                    help="Расчётный метод или источник показателя.",
                ),
                "compliance": st.column_config.TextColumn(
                    "Соответствие",
                    help="Результат сравнения с применимым нормативным критерием.",
                ),
                "target_value": st.column_config.NumberColumn(
                    "Целевое значение",
                    help="Числовая граница критерия, если она однозначно задана.",
                ),
                "target_description": st.column_config.TextColumn(
                    "Критерий",
                    help="Условие, с которым сравнивается расчётное значение.",
                ),
            },
        )
    with tabs[1]:
        for trace in result.formulas:
            with st.expander(f"{trace.title_ru}: {trace.result:.3f} {trace.unit}"):
                st.code(trace.expression, language=None)
                st.write("Подстановка:", trace.substituted_expression)
                st.json(trace.variables)
                st.caption(
                    f"Источник: {trace.standard}; пункт: {trace.clause or 'не подтверждён'}; "
                    f"статус: {trace.status}."
                )
    with tabs[2]:
        render_messages(result.messages)
    with tabs[3]:
        for recommendation in result.recommendations:
            st.info(
                f"{recommendation.problem}\n\n**Решение:** {recommendation.proposed_action}\n\n"
                f"**Ограничение:** {recommendation.limitations}"
            )
    with tabs[4]:
        st.json(result.audit.model_dump(mode="json"))
