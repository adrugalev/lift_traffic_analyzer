"""Автоматический перебор и сравнение вариантов."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.engines.optimization_engine import OptimizationEngine
from src.reports.charts import variants_chart
from src.ui import configure_page, ensure_session, invalidate_generated_reports


configure_page("Сравнение вариантов")
project = ensure_session()
st.title("7. Сравнение вариантов")

with st.form("optimizer"):
    basic, weights_tab = st.tabs(["Диапазоны", "Весовые коэффициенты"])
    with basic:
        c1, c2, c3 = st.columns(3)
        minimum_count = c1.number_input(
            "Лифтов от",
            1,
            12,
            2,
            help="Минимальное количество лифтов в перебираемых конфигурациях.",
        )
        maximum_count = c2.number_input(
            "Лифтов до",
            1,
            12,
            4,
            help="Максимальное количество лифтов в перебираемых конфигурациях.",
        )
        maximum_shafts = c3.number_input(
            "Максимум шахт",
            1,
            20,
            6,
            help=(
                "Ограничение на количество лифтовых шахт. Варианты с большим "
                "числом лифтов исключаются из перебора."
            ),
        )
        capacities = st.multiselect(
            "Грузоподъёмности, кг",
            [630, 800, 1000, 1275, 1600],
            default=[1000, 1600],
            help="Номинальные грузоподъёмности, которые будут сочетаться с каждым числом лифтов и скоростью.",
        )
        speeds = st.multiselect(
            "Скорости, м/с",
            [1.0, 1.6, 2.0, 2.5, 3.0, 4.0],
            default=[1.6, 2.5],
            help="Номинальные скорости, которые будут проверены в перебираемых конфигурациях.",
        )
    with weights_tab:
        c1, c2, c3, c4 = st.columns(4)
        weight_capacity = c1.number_input(
            "Провозная способность",
            0.0,
            10.0,
            4.5,
            0.5,
            help=(
                "Относительная важность покрытия расчётного спроса. Чем больше "
                "вес, тем сильнее этот критерий влияет на итоговую оценку."
            ),
        )
        weight_wait = c2.number_input(
            "Комфорт",
            0.0,
            10.0,
            3.5,
            0.5,
            help=(
                "Относительная важность меньшего ориентировочного ожидания I/2 "
                "в предварительном расчёте."
            ),
        )
        weight_shafts = c3.number_input(
            "Количество шахт",
            0.0,
            10.0,
            1.0,
            0.5,
            help="Относительная важность варианта с меньшим количеством лифтов и шахт.",
        )
        weight_reserve = c4.number_input(
            "Резерв",
            0.0,
            10.0,
            1.0,
            0.5,
            help="Относительная важность запаса провозной способности сверх расчётного спроса.",
        )
        st.caption("Стоимость и энергоэффективность не оцениваются без введённых цен и подтверждённой энергетической модели.")
    calculate = st.form_submit_button(
        "Перебрать варианты",
        type="primary",
        help=(
            "Формирует все сочетания выбранных количества, грузоподъёмности "
            "и скорости, затем ранжирует их по заданным весам."
        ),
    )

if calculate:
    if minimum_count > maximum_count:
        st.error("Нижняя граница количества лифтов выше верхней.")
    elif not capacities or not speeds:
        st.error("Выберите хотя бы одну грузоподъёмность и скорость.")
    else:
        nominal = {630: 8, 800: 10, 1000: 13, 1275: 17, 1600: 21}
        try:
            with st.spinner("Выполняется перебор допустимых комбинаций…"):
                variants = OptimizationEngine().enumerate_variants(
                    project,
                    elevator_counts=list(range(int(minimum_count), int(maximum_count) + 1)),
                    capacities_kg=[float(value) for value in capacities],
                    nominal_passengers={float(key): value for key, value in nominal.items()},
                    speeds_mps=[float(value) for value in speeds],
                    maximum_shafts=int(maximum_shafts),
                    weights={
                        "capacity": weight_capacity,
                        "wait": weight_wait,
                        "shafts": weight_shafts,
                        "reserve": weight_reserve,
                    },
                )
            invalidate_generated_reports()
            st.session_state.variants = variants
            st.success(f"Рассмотрено вариантов: {len(variants)}.")
        except Exception as exc:
            st.error(f"Перебор не выполнен: {exc}")

variants = st.session_state.variants
if variants:
    frame = pd.DataFrame(
        [
            {
                "Вариант": item.variant_name,
                "Лифты": item.elevator_count,
                "Г/п, кг": item.capacity_kg,
                "Скорость, м/с": item.speed_mps,
                "Интервал, с": item.interval_s,
                "Провозная способность": item.handling_capacity_5min,
                "Ориентировочное время ожидания, не менее, с": item.average_wait_s,
                "Резерв, %": item.reserve_percent,
                "Соответствие": item.compliance.value,
                "Оценка": item.score,
                "Категория": item.category,
            }
            for item in variants
        ]
    )
    st.dataframe(
        frame,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Вариант": st.column_config.TextColumn(help="Условное наименование перебранной конфигурации."),
            "Лифты": st.column_config.NumberColumn(help="Количество лифтов и шахт в конфигурации."),
            "Г/п, кг": st.column_config.NumberColumn(help="Номинальная грузоподъёмность каждого лифта."),
            "Скорость, м/с": st.column_config.NumberColumn(help="Номинальная скорость каждого лифта."),
            "Интервал, с": st.column_config.NumberColumn(
                help="Предварительный интервал между отправлениями кабин."
            ),
            "Провозная способность": st.column_config.NumberColumn(
                help="Предварительная провозная способность группы за пять минут."
            ),
            "Ориентировочное время ожидания, не менее, с": st.column_config.NumberColumn(
                help="Вспомогательная оценка I/2; фактическое ожидание проверяется симуляцией."
            ),
            "Резерв, %": st.column_config.NumberColumn(
                help="Превышение провозной способности над расчётным спросом."
            ),
            "Соответствие": st.column_config.TextColumn(
                help="В сравнении нормативное соответствие не оценивается."
            ),
            "Оценка": st.column_config.NumberColumn(
                help="Итоговая оценка 0–100 по относительным весам выбранных критериев."
            ),
            "Категория": st.column_config.TextColumn(
                help="Особая роль варианта среди рассмотренных конфигураций."
            ),
        },
    )
    st.plotly_chart(variants_chart(variants), use_container_width=True)
