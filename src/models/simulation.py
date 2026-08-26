"""Модели настроек и результатов дискретно-событийной симуляции."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class SimulationSettings(BaseModel):
    """Управляемые параметры запуска симуляции."""

    duration_s: int = 300
    warmup_s: int = 0
    repetitions: int = 5
    random_seed: int = 2026
    intensity_step_s: int = 60
    parallel_runs: int = 1
    maximum_queue_length: int = 1000
    maximum_wait_s: float = 300.0
    abandon_probability: float = 0.0
    slow_boarding_share: float = 0.0
    accessible_passenger_share: float = 0.0
    luggage_share: float = 0.0
    group_passenger_share: float = 0.0

    @field_validator("duration_s", "repetitions", "intensity_step_s", "parallel_runs", "maximum_queue_length")
    @classmethod
    def validate_positive_integer(cls, value: int) -> int:
        """Проверяет положительные настройки симуляции."""

        if value <= 0:
            raise ValueError("Параметр симуляции должен быть больше нуля.")
        return value

    @field_validator(
        "abandon_probability",
        "slow_boarding_share",
        "accessible_passenger_share",
        "luggage_share",
        "group_passenger_share",
    )
    @classmethod
    def validate_share(cls, value: float) -> float:
        """Проверяет долю в диапазоне [0; 1]."""

        if not 0 <= value <= 1:
            raise ValueError("Доля должна находиться в диапазоне [0; 1].")
        return value


class Passenger(BaseModel):
    """Состояние отдельного пассажира."""

    id: int
    arrival_time_s: float
    origin_floor: int
    destination_floor: int
    wait_start_time_s: float
    board_time_s: float | None = None
    exit_time_s: float | None = None
    waiting_time_s: float | None = None
    journey_time_s: float | None = None
    time_to_destination_s: float | None = None
    status: str = "waiting"
    elevator_id: str | None = None


class ElevatorTrajectoryPoint(BaseModel):
    """Точка траектории кабины на диаграмме этаж-время."""

    elevator_id: str
    time_s: float
    floor: int
    event: str


class SimulationStatistics(BaseModel):
    """Сводные статистические показатели по нескольким повторам."""

    mean: float
    median: float
    std: float
    percentile_80: float
    percentile_90: float
    percentile_95: float
    percentile_99: float
    confidence_interval_95_low: float
    confidence_interval_95_high: float
    minimum: float
    maximum: float


class SimulationResult(BaseModel):
    """Итог воспроизводимого симуляционного расчёта."""

    method: str = "Дискретно-событийная симуляция"
    group_id: str
    seed: int
    repetitions: int
    waiting_time: SimulationStatistics
    time_to_destination: SimulationStatistics
    average_journey_time_s: float
    maximum_waiting_time_s: float
    average_queue_length: float
    maximum_queue_length: int
    transported_passengers: int
    unserved_passengers: int
    average_car_load: float
    maximum_car_load: int
    stops_count: int
    idle_runs: int
    car_distance_floors: dict[str, float] = Field(default_factory=dict)
    utilization: dict[str, float] = Field(default_factory=dict)
    passengers: list[Passenger] = Field(default_factory=list)
    queue_time_series: list[dict[str, float]] = Field(default_factory=list)
    trajectories: list[ElevatorTrajectoryPoint] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    project_hash: str

