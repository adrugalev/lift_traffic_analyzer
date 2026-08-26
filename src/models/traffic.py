"""Модели пассажиропотока и OD-матрицы."""

from __future__ import annotations

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class TrafficScenarioType(StrEnum):
    """Тип расчётного пассажиропотока."""

    UP_PEAK = "Утренний восходящий пик"
    DOWN_PEAK = "Вечерний нисходящий пик"
    LUNCH = "Обеденный поток"
    MIXED = "Смешанный межэтажный поток"
    BIDIRECTIONAL = "Двунаправленный поток"
    HOTEL_MORNING = "Гостиничный утренний поток"
    HOTEL_EVENING = "Гостиничный вечерний поток"
    RESIDENTIAL_MORNING = "Жилой утренний поток"
    RESIDENTIAL_EVENING = "Жилой вечерний поток"
    CUSTOM = "Пользовательский сценарий"


class ArrivalDistribution(StrEnum):
    """Распределение моментов появления пассажиров."""

    POISSON = "Пуассоновский поток"
    NONSTATIONARY_POISSON = "Нестационарный пуассоновский поток"
    PROFILE = "Заданный временной профиль"
    DETERMINISTIC = "Детерминированный поток"
    IMPORTED = "Импортированный список"
    BATCH = "Пакетное прибытие"


class TrafficScenario(BaseModel):
    """Сценарий пассажиропотока для расчёта и симуляции."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "Восходящий пик"
    scenario_type: TrafficScenarioType = TrafficScenarioType.UP_PEAK
    duration_s: int = 300
    five_minute_passengers: int | None = None
    population_percent_5min: float = 5.0
    incoming_share: float = 1.0
    outgoing_share: float = 0.0
    interfloor_share: float = 0.0
    parking_incoming_share: float = 0.15
    arrival_distribution: ArrivalDistribution = ArrivalDistribution.POISSON
    intensity_profile: list[float] = Field(default_factory=list)
    random_bursts: bool = False
    od_floor_numbers: list[int] = Field(default_factory=list)
    od_matrix: list[list[float]] = Field(default_factory=list)
    imported_passengers: list[dict[str, float | int]] = Field(default_factory=list)

    @field_validator("duration_s")
    @classmethod
    def validate_duration(cls, value: int) -> int:
        """Проверяет положительную длительность сценария."""

        if value <= 0:
            raise ValueError("Продолжительность анализа должна быть больше нуля.")
        return value

    @field_validator("population_percent_5min")
    @classmethod
    def validate_percentage(cls, value: float) -> float:
        """Проверяет неотрицательный пятиминутный процент."""

        if value < 0:
            raise ValueError("Пятиминутный процент не может быть отрицательным.")
        return value

    @field_validator("parking_incoming_share")
    @classmethod
    def validate_parking_share(cls, value: float) -> float:
        """Проверяет долю входящих пассажиров, прибывающих с паркинга."""

        if not 0 <= value <= 1:
            raise ValueError("Доля входящего потока с паркинга должна находиться в диапазоне [0; 1].")
        return value

    @model_validator(mode="after")
    def validate_shares_and_od(self) -> "TrafficScenario":
        """Проверяет доли направлений и форму OD-матрицы."""

        shares = (self.incoming_share, self.outgoing_share, self.interfloor_share)
        if any(value < 0 or value > 1 for value in shares):
            raise ValueError("Доли направлений должны находиться в диапазоне [0; 1].")
        if abs(sum(shares) - 1.0) > 1e-6:
            raise ValueError("Сумма долей входящего, исходящего и межэтажного потока должна быть равна 1.")
        if self.od_matrix:
            size = len(self.od_floor_numbers)
            if size == 0 or len(self.od_matrix) != size or any(len(row) != size for row in self.od_matrix):
                raise ValueError("Размер OD-матрицы должен соответствовать списку этажей.")
            for index, row in enumerate(self.od_matrix):
                if abs(row[index]) > 1e-12:
                    raise ValueError("Диагональ OD-матрицы должна быть нулевой.")
                if any(value < 0 for value in row):
                    raise ValueError("OD-матрица не может содержать отрицательные вероятности.")
                row_sum = sum(row)
                if row_sum > 0 and abs(row_sum - 1.0) > 1e-6:
                    raise ValueError("Каждая ненулевая строка OD-матрицы должна иметь сумму 1.")
        return self
