"""Предварительный и нормативный аналитический расчёт."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.engines.analytic_engine import AnalyticEngine, NormativeConfigurationError
from src.engines.recommendation_engine import RecommendationEngine
from src.services.validation_service import ValidationService
from src.ui import (
    configure_page,
    ensure_session,
    invalidate_generated_reports,
    render_messages,
    update_project,
)
from src.utils.traffic_profiles import scenario_for_gost_calculation


configure_page("Аналитический расчёт")
project = ensure_session()
engine = AnalyticEngine()
st.title("5. Аналитический расчёт")
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

group = st.selectbox(
    "Лифтовая группа",
    project.elevator_groups,
    format_func=lambda item: item.name,
    help="Группа, для которой будет выполнен предварительный или нормативный расчёт.",
)
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
        st.success("Расчёт по ГОСТ выполнен.")
    except NormativeConfigurationError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(str(exc))

result = st.session_state.analytic_result
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
