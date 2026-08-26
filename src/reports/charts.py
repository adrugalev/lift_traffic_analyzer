"""Plotly-графики аналитики и симуляции."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.models.results import CalculationResult, VariantResult
from src.models.simulation import SimulationResult


def waiting_histogram(result: SimulationResult) -> go.Figure:
    """Строит распределение времени ожидания."""

    values = [
        passenger.waiting_time_s
        for passenger in result.passengers
        if passenger.status == "served" and passenger.waiting_time_s is not None
    ]
    figure = px.histogram(
        x=values,
        nbins=25,
        labels={"x": "Время ожидания, с", "y": "Пассажиры"},
        title="Распределение времени ожидания",
    )
    figure.update_layout(showlegend=False)
    return figure


def waiting_ecdf(result: SimulationResult) -> go.Figure:
    """Строит эмпирическую функцию распределения ожидания."""

    values = sorted(
        float(passenger.waiting_time_s)
        for passenger in result.passengers
        if passenger.status == "served" and passenger.waiting_time_s is not None
    )
    frame = pd.DataFrame(
        {"Время ожидания, с": values, "Доля пассажиров": [(index + 1) / len(values) for index in range(len(values))]}
    )
    return px.line(
        frame,
        x="Время ожидания, с",
        y="Доля пассажиров",
        title="ECDF времени ожидания",
    )


def queue_chart(result: SimulationResult) -> go.Figure:
    """Строит изменение длины очереди."""

    frame = pd.DataFrame(result.queue_time_series)
    return px.line(
        frame,
        x="time_s",
        y="queue_length",
        labels={"time_s": "Время, с", "queue_length": "Пассажиров в очереди"},
        title="Длина очереди во времени",
    )


def trajectory_chart(result: SimulationResult) -> go.Figure:
    """Строит траектории кабин этаж-время."""

    frame = pd.DataFrame([point.model_dump() for point in result.trajectories])
    if frame.empty:
        return go.Figure().update_layout(title="Траектории кабин")
    return px.line(
        frame,
        x="time_s",
        y="floor",
        color="elevator_id",
        markers=True,
        labels={"time_s": "Время, с", "floor": "Этаж", "elevator_id": "Кабина"},
        title="Траектории кабин «этаж — время»",
    )


def variants_chart(variants: list[VariantResult]) -> go.Figure:
    """Сравнивает интервал и провозную способность вариантов."""

    frame = pd.DataFrame([item.model_dump(mode="json") for item in variants])
    return px.scatter(
        frame,
        x="interval_s",
        y="handling_capacity_5min",
        size="elevator_count",
        color="score",
        hover_name="variant_name",
        labels={
            "interval_s": "Интервал, с",
            "handling_capacity_5min": "Провозная способность, пасс./5 мин",
            "score": "Интегральная оценка",
            "elevator_count": "Лифты",
        },
        title="Сравнение рассмотренных вариантов",
    )


def analytic_vs_simulation(
    analytic: CalculationResult,
    simulation: SimulationResult,
) -> go.Figure:
    """Сопоставляет предварительную оценку ожидания и симуляцию."""

    labels = [
        "Ориентировочное время ожидания, не менее",
        "Симуляция: среднее ожидание (AWT)",
        "Симуляция: ожидание 95% пассажиров, не более (P95)",
    ]
    values = [
        analytic.metric("average_wait_proxy").value,
        simulation.waiting_time.mean,
        simulation.waiting_time.percentile_95,
    ]
    return px.bar(
        x=labels,
        y=values,
        labels={"x": "Метод/показатель", "y": "Время, с"},
        title="Предварительный расчёт и симуляция",
    )
