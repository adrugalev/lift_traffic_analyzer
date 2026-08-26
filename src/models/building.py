"""Модели общих сведений и здания."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field


class UnitSystem(StrEnum):
    """Поддерживаемые системы единиц."""

    SI = "SI"


class StandardSelection(StrEnum):
    """Выбранная нормативная база."""

    GOST_34758_2021 = "ГОСТ 34758-2021"


class BuildingType(StrEnum):
    """Тип функционального назначения здания."""

    RESIDENTIAL = "Жилое здание"
    OFFICE = "Офис"
    HOTEL = "Гостиница"
    MIXED_USE = "Многофункциональный комплекс"
    CUSTOM = "Пользовательский тип"


class ProjectMetadata(BaseModel):
    """Идентификационные сведения проекта."""

    name: str = "Новый проект"
    address: str = ""
    customer: str = ""
    designer: str = ""
    calculation_author: str = ""
    calculation_date: date = Field(default_factory=date.today)
    design_stage: str = "Концепция"
    comment: str = ""
    units: UnitSystem = UnitSystem.SI
    selected_standard: StandardSelection = StandardSelection.GOST_34758_2021


class Zone(BaseModel):
    """Функциональная зона многофункционального здания."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    building_type: BuildingType = BuildingType.CUSTOM
    floor_numbers: list[int] = Field(default_factory=list)
    traffic_profile_id: str = "custom"


class Building(BaseModel):
    """Описание здания и его функциональных зон."""

    building_type: BuildingType = BuildingType.RESIDENTIAL
    occupancy_percent: int = Field(default=100, ge=0, le=100)
    zones: list[Zone] = Field(default_factory=list)
