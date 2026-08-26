"""Перебор и многокритериальное ранжирование вариантов лифтовой группы."""

from __future__ import annotations

from itertools import product

from src.models.elevator import Elevator
from src.models.project import Project
from src.models.results import VariantResult

from .analytic_engine import AnalyticEngine


class OptimizationEngine:
    """Перебирает допустимые варианты без скрытых нормативных допущений."""

    def __init__(self, analytic_engine: AnalyticEngine | None = None) -> None:
        self.analytic_engine = analytic_engine or AnalyticEngine()

    def enumerate_variants(
        self,
        project: Project,
        elevator_counts: list[int],
        capacities_kg: list[float],
        nominal_passengers: dict[float, int],
        speeds_mps: list[float],
        maximum_shafts: int | None = None,
        weights: dict[str, float] | None = None,
    ) -> list[VariantResult]:
        """Возвращает ранжированный набор вариантов."""

        weights = weights or {"capacity": 0.45, "wait": 0.35, "shafts": 0.10, "reserve": 0.10}
        rows: list[VariantResult] = []
        for index, (count, capacity, speed) in enumerate(
            product(elevator_counts, capacities_kg, speeds_mps), start=1
        ):
            if count <= 0 or speed <= 0 or capacity <= 0:
                continue
            if maximum_shafts is not None and count > maximum_shafts:
                continue
            candidate = project.model_copy(deep=True)
            group = candidate.elevator_groups[0]
            template = group.elevators[0]
            group.elevators = [
                Elevator(
                    **{
                        **template.model_dump(),
                        "id": f"variant-{index}-elevator-{elevator_index + 1}",
                        "name": f"Вариант {index} — лифт {elevator_index + 1}",
                        "capacity_kg": capacity,
                        "nominal_passengers": nominal_passengers[capacity],
                        "speed_mps": speed,
                    }
                )
                for elevator_index in range(count)
            ]
            calculation = self.analytic_engine.calculate_preview(candidate, group.id)
            interval = calculation.metric("interval").value
            handling = calculation.metric("handling_capacity_5min").value
            wait = calculation.metric("average_wait_proxy").value
            reserve = calculation.metric("reserve").value
            capacity_score = min(1.0, max(0.0, handling / max(1.0, calculation.metric("demand_5min").value)))
            wait_score = 1.0 / (1.0 + wait / 30.0)
            shaft_score = 1.0 / count
            reserve_score = max(0.0, min(1.0, (reserve + 20.0) / 100.0))
            score = 100.0 * (
                weights.get("capacity", 0.0) * capacity_score
                + weights.get("wait", 0.0) * wait_score
                + weights.get("shafts", 0.0) * shaft_score
                + weights.get("reserve", 0.0) * reserve_score
            ) / max(1e-9, sum(weights.values()))
            rows.append(
                VariantResult(
                    variant_name=f"Вариант {index}",
                    elevator_count=count,
                    capacity_kg=capacity,
                    speed_mps=speed,
                    interval_s=interval,
                    handling_capacity_5min=handling,
                    average_wait_s=wait,
                    reserve_percent=reserve,
                    compliance=calculation.metric("interval").compliance,
                    score=score,
                )
            )
        rows.sort(key=lambda item: item.score, reverse=True)
        if rows:
            rows[0].category = "Рекомендуемый по заданным весам"
            minimum = min(rows, key=lambda item: (item.elevator_count, -item.score))
            minimum.category = "Минимум шахт среди рассмотренных"
            comfort = min(rows, key=lambda item: item.average_wait_s)
            comfort.category = "Повышенный комфорт среди рассмотренных"
            reserve = max(rows, key=lambda item: item.reserve_percent)
            reserve.category = "Максимальный резерв среди рассмотренных"
        return rows

