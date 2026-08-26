"""Запуск и визуализация дискретно-событийной симуляции."""

from __future__ import annotations

from math import ceil

import streamlit as st

from src.engines.simulation_engine import SimulationEngine
from src.models.simulation import SimulationSettings
from src.reports.charts import queue_chart, trajectory_chart, waiting_ecdf, waiting_histogram
from src.ui import configure_page, ensure_session, invalidate_generated_reports
from src.utils.hashing import project_hash


configure_page("Симуляция")
project = ensure_session()
st.title("6. Симуляция")
st.caption("Модель отделена от аналитического расчёта; её показатели помечаются как симуляционные.")
st.markdown(
    """
    <style>
    .st-key-simulation_metric_cards [data-testid="stMetricLabel"],
    .st-key-simulation_metric_cards [data-testid="stMetricLabel"] > div,
    .st-key-simulation_metric_cards [data-testid="stMetricLabel"] p {
        overflow: visible !important;
        text-overflow: clip !important;
        white-space: normal !important;
    }
    .st-key-simulation_metric_cards [data-testid="stMetricLabel"] {
        min-height: 3.2rem;
        align-items: flex-start !important;
    }
    .st-key-simulation_metric_cards [data-testid="stMetricLabel"] p {
        font-size: 0.84rem !important;
        line-height: 1.25 !important;
    }
    .st-key-simulation_metric_cards [data-testid="stMetricValue"],
    .st-key-simulation_metric_cards [data-testid="stMetricValue"] > div {
        overflow: visible !important;
        text-overflow: clip !important;
        white-space: nowrap !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

group = st.selectbox(
    "Лифтовая группа",
    project.elevator_groups,
    format_func=lambda item: item.name,
    help="Группа лифтов, работа которой будет воспроизведена в симуляции.",
)
scenario = project.scenario()
duration_recommended = 300
passengers_5min = project.population * scenario.population_percent_5min / 100
expected_passengers = passengers_5min * duration_recommended / 300
repetitions_recommended = 10 if expected_passengers <= 500 else 5
maximum_queue_recommended = max(50, ceil(expected_passengers * 2))
maximum_wait_recommended = float(max(180, min(600, duration_recommended)))
settings_key = f"{project_hash(project)[:12]}_{group.id}"

st.caption(
    "Рекомендуемые параметры уже установлены по текущему сценарию и расчётному потоку. "
    "Можно сразу запускать симуляцию."
)

with st.form("simulation_settings"):
    basic, advanced = st.tabs(["Основные", "Дополнительные"])
    with basic:
        c1, c2 = st.columns(2)
        duration = c1.number_input(
            "Длительность, с",
            min_value=1,
            value=duration_recommended,
            step=60,
            key=f"simulation_duration_{settings_key}",
            help=(
                "Продолжительность периода поступления пассажиров. Например, "
                "300 секунд соответствуют расчётному пятиминутному потоку."
            ),
        )
        repetitions = c2.number_input(
            "Повторы",
            min_value=1,
            value=repetitions_recommended,
            step=1,
            key=f"simulation_repetitions_{settings_key}",
            help=(
                "Число независимых запусков с разными случайными последовательностями. "
                "Большее число повторов делает итоговые средние показатели устойчивее."
            ),
        )
    with advanced:
        c1, c2 = st.columns(2)
        seed = c1.number_input(
            "Начальное число генератора",
            min_value=0,
            value=2026,
            step=1,
            key=f"simulation_seed_{settings_key}",
            help=(
                "Фиксирует последовательность случайных событий. При одинаковых "
                "данных, настройках и числе результат можно воспроизвести."
            ),
        )
        warmup = c2.number_input(
            "Разогрев, с",
            min_value=0,
            value=0,
            step=30,
            key=f"simulation_warmup_{settings_key}",
            help=(
                "Начальный период выхода системы на установившийся режим. "
                "Пассажиры этого периода влияют на работу лифтов, но не включаются "
                "в итоговую статистику."
            ),
        )
        c3, c4 = st.columns(2)
        maximum_queue = c3.number_input(
            "Максимальная очередь, пасс.",
            min_value=1,
            value=maximum_queue_recommended,
            step=10,
            key=f"simulation_queue_{settings_key}",
            help=(
                "Предельное число одновременно ожидающих пассажиров. Новые пассажиры "
                "сверх этого значения считаются необслуженными."
            ),
        )
        maximum_wait = c4.number_input(
            "Максимальное ожидание, с",
            min_value=1.0,
            value=maximum_wait_recommended,
            key=f"simulation_wait_{settings_key}",
            help=(
                "После превышения этого времени пассажир может отказаться от поездки "
                "с заданной ниже вероятностью. При вероятности отказа 0% ограничение "
                "не удаляет пассажира из очереди."
            ),
        )
        c5, c6 = st.columns(2)
        abandon = c5.slider(
            "Вероятность отказа после максимального ожидания, %",
            0,
            100,
            0,
            5,
            format="%d%%",
            key=f"simulation_abandon_{settings_key}",
            help=(
                "Вероятность того, что пассажир покинет очередь, если к моменту "
                "прибытия кабины его ожидание превысило заданный предел."
            ),
        )
        slow_share = c6.slider(
            "Пассажиры с увеличенным временем посадки, %",
            0,
            100,
            5,
            5,
            format="%d%%",
            key=f"simulation_slow_{settings_key}",
            help=(
                "Упрощённо увеличивает совокупное среднее время посадки "
                "на указанную долю, имитируя более медленную посадку."
            ),
        )
    run_clicked = st.form_submit_button(
        "Запустить симуляцию",
        type="primary",
        help=(
            "Создаёт пассажиров по сохранённому сценарию и воспроизводит работу "
            "выбранной лифтовой группы во всех заданных повторах."
        ),
    )

if run_clicked:
    try:
        settings = SimulationSettings(
            duration_s=int(duration),
            warmup_s=int(warmup),
            repetitions=int(repetitions),
            random_seed=int(seed),
            maximum_queue_length=int(maximum_queue),
            maximum_wait_s=float(maximum_wait),
            abandon_probability=float(abandon) / 100,
            slow_boarding_share=float(slow_share) / 100,
        )
        with st.spinner("Выполняются независимые повторы симуляции…"):
            result = SimulationEngine().run(project, settings, group.id)
        invalidate_generated_reports()
        st.session_state.simulation_result = result
        st.success("Симуляция завершена.")
    except Exception as exc:
        st.error(f"Симуляция не выполнена: {exc}")

result = st.session_state.simulation_result
if result:
    st.subheader("Ключевые показатели")
    with st.container(key="simulation_metric_cards"):
        primary_columns = st.columns(3)
        primary_columns[0].metric(
            "Среднее время ожидания пассажира (AWT)",
            f"{result.waiting_time.mean:.1f} с",
            help=(
                "Average Waiting Time — среднее время от появления обслуженного "
                "пассажира в очереди до его посадки в кабину."
            ),
        )
        primary_columns[1].metric(
            "Ожидание 95% пассажиров, не более (P95)",
            f"{result.waiting_time.percentile_95:.1f} с",
            help=(
                "95% обслуженных пассажиров ожидали кабину не дольше указанного "
                "времени; оставшиеся 5% ожидали дольше."
            ),
        )
        primary_columns[2].metric(
            "Среднее полное время до этажа назначения (TTD)",
            f"{result.time_to_destination.mean:.1f} с",
            help=(
                "Time to Destination — среднее время от появления обслуженного "
                "пассажира до выхода на этаже назначения: ожидание и поездка."
            ),
        )
        secondary_columns = st.columns(2)
        secondary_columns[0].metric(
            "Максимальная очередь, пассажиров",
            f"{result.maximum_queue_length} пасс.",
            help=(
                "Наибольшее число одновременно ожидавших пассажиров, "
                "зафиксированное хотя бы в одном повторе симуляции."
            ),
        )
        secondary_columns[1].metric(
            "Не обслужено пассажиров, в среднем за повтор",
            f"{result.unserved_passengers} пасс.",
            help=(
                "Среднее за один повтор число пассажиров, которые не завершили "
                "поездку в пределах расчётного периода."
            ),
        )

    tabs = st.tabs(["Распределение", "ECDF", "Очередь", "Траектории", "Воспроизводимость"])
    with tabs[0]:
        st.plotly_chart(waiting_histogram(result), use_container_width=True)
    with tabs[1]:
        st.plotly_chart(waiting_ecdf(result), use_container_width=True)
    with tabs[2]:
        st.plotly_chart(queue_chart(result), use_container_width=True)
    with tabs[3]:
        st.plotly_chart(trajectory_chart(result), use_container_width=True)
    with tabs[4]:
        st.json(
            {
                "seed": result.seed,
                "repetitions": result.repetitions,
                "project_hash": result.project_hash,
                "warnings": result.warnings,
            }
        )
