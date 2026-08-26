"""Модель этажа."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Floor(BaseModel):
    """Геометрия, население и признаки обслуживания этажа."""

    number: int
    label: str = ""
    elevation_m: float = 0.0
    floor_height_m: float = 3.0
    purpose: str = "Типовой этаж"
    area_m2: float = 0.0
    population: int = 0
    incoming_passengers: int = 0
    outgoing_passengers: int = 0
    interfloor_passengers: int = 0
    served_by_group_ids: list[str] = Field(default_factory=list)
    is_main_entrance: bool = False
    is_entrance: bool = False
    is_parking: bool = False
    is_express: bool = False

    @field_validator("floor_height_m")
    @classmethod
    def validate_height(cls, value: float) -> float:
        """Запрещает нулевую или отрицательную высоту этажа."""

        if value <= 0:
            raise ValueError("Высота этажа должна быть больше нуля.")
        return value

    @field_validator("population", "incoming_passengers", "outgoing_passengers", "interfloor_passengers")
    @classmethod
    def validate_non_negative_counts(cls, value: int) -> int:
        """Запрещает отрицательные значения пассажиров."""

        if value < 0:
            raise ValueError("Количество пассажиров не может быть отрицательным.")
        return value

