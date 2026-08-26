"""Модели лифта и лифтовой группы."""

from __future__ import annotations

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator


class ControlType(StrEnum):
    """Поддерживаемые стратегии группового управления."""

    SINGLE = "Одиночное"
    GROUP_COLLECTIVE = "Групповое коллективное"
    FULL_COLLECTIVE = "Полное собирательное"
    DESTINATION_CONTROL = "Destination Control (базовая эвристика)"
    CUSTOM = "Пользовательский алгоритм"


class DoorOpeningType(StrEnum):
    """Тип открывания дверей."""

    CENTER = "Центральное"
    SIDE = "Боковое"
    TELESCOPIC = "Телескопическое"


class Elevator(BaseModel):
    """Технические параметры отдельного лифта."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "Лифт 1"
    capacity_kg: float = 1000.0
    nominal_passengers: int = 13
    load_factor: float = 0.8
    speed_mps: float = 1.6
    acceleration_mps2: float = 0.8
    deceleration_mps2: float = 0.8
    jerk_mps3: float = 1.0
    door_width_m: float = 0.9
    door_opening_type: DoorOpeningType = DoorOpeningType.TELESCOPIC
    door_open_time_s: float = 2.5
    door_close_time_s: float = 4.5
    pre_open_time_s: float = 0.0
    door_dwell_time_s: float = 1.0
    control_transfer_time_s: float = 0.4
    boarding_time_per_passenger_s: float = 1.1
    alighting_time_per_passenger_s: float = 1.1
    leveling_time_s: float = 0.5
    start_brake_allowance_s: float = 0.5
    travel_height_m: float = 30.0
    stops_count: int = 10
    door_count: int = 1
    through_car: bool = False
    accessible: bool = True
    fire_service: bool = False
    priority_floors: list[int] = Field(default_factory=list)

    @field_validator(
        "capacity_kg",
        "speed_mps",
        "acceleration_mps2",
        "deceleration_mps2",
        "jerk_mps3",
        "door_width_m",
    )
    @classmethod
    def validate_positive(cls, value: float) -> float:
        """Проверяет физически положительные параметры."""

        if value <= 0:
            raise ValueError("Технический параметр должен быть больше нуля.")
        return value

    @field_validator(
        "door_open_time_s",
        "door_close_time_s",
        "pre_open_time_s",
        "door_dwell_time_s",
        "control_transfer_time_s",
        "boarding_time_per_passenger_s",
        "alighting_time_per_passenger_s",
        "leveling_time_s",
        "start_brake_allowance_s",
    )
    @classmethod
    def validate_non_negative_time(cls, value: float) -> float:
        """Проверяет неотрицательные временные параметры."""

        if value < 0:
            raise ValueError("Временной параметр не может быть отрицательным.")
        return value

    @field_validator("nominal_passengers", "stops_count", "door_count")
    @classmethod
    def validate_positive_integer(cls, value: int) -> int:
        """Проверяет положительные целочисленные параметры."""

        if value <= 0:
            raise ValueError("Значение должно быть целым числом больше нуля.")
        return value

    @field_validator("load_factor")
    @classmethod
    def validate_load_factor(cls, value: float) -> float:
        """Ограничивает коэффициент заполнения диапазоном (0; 1]."""

        if not 0 < value <= 1:
            raise ValueError("Коэффициент заполнения должен быть в диапазоне (0; 1].")
        return value


class ElevatorGroup(BaseModel):
    """Конфигурация лифтовой группы."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = "Группа A"
    control_type: ControlType = ControlType.GROUP_COLLECTIVE
    service_zone_name: str = "Все этажи"
    main_floor: int = 1
    served_floors: list[int] = Field(default_factory=lambda: list(range(1, 11)))
    express_zone: bool = False
    entrance_floor_count: int = 1
    operating_mode: str = "Нормальный"
    building_type: str = "Жилое здание"
    elevators: list[Elevator] = Field(default_factory=lambda: [Elevator(name="Лифт 1"), Elevator(name="Лифт 2")])

    @model_validator(mode="after")
    def validate_group(self) -> "ElevatorGroup":
        """Проверяет состав и основную посадочную остановку группы."""

        if not self.elevators:
            raise ValueError("Лифтовая группа должна содержать хотя бы один лифт.")
        if self.main_floor not in self.served_floors:
            raise ValueError("Основной посадочный этаж должен обслуживаться группой.")
        if len(set(self.served_floors)) != len(self.served_floors):
            raise ValueError("Список обслуживаемых этажей содержит дубликаты.")
        return self

    @property
    def elevator_count(self) -> int:
        """Возвращает количество лифтов в группе."""

        return len(self.elevators)
