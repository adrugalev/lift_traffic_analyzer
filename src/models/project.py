"""Корневая модель сохраняемого проекта."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from .building import Building, ProjectMetadata
from .elevator import ElevatorGroup
from .floor import Floor
from .traffic import TrafficScenario


class Project(BaseModel):
    """Полная сериализуемая схема проекта."""

    schema_version: str = "1.0"
    id: str = Field(default_factory=lambda: str(uuid4()))
    metadata: ProjectMetadata = Field(default_factory=ProjectMetadata)
    building: Building = Field(default_factory=Building)
    floors: list[Floor] = Field(default_factory=list)
    elevator_groups: list[ElevatorGroup] = Field(default_factory=list)
    traffic_scenarios: list[TrafficScenario] = Field(default_factory=list)
    active_scenario_id: str | None = None
    calculation_settings: dict[str, Any] = Field(default_factory=dict)
    stored_results: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    modified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_references(self) -> "Project":
        """Проверяет уникальность этажей и ссылку на активный сценарий."""

        floor_numbers = [floor.number for floor in self.floors]
        if len(floor_numbers) != len(set(floor_numbers)):
            raise ValueError("Номера этажей должны быть уникальными.")
        if self.active_scenario_id is not None and self.active_scenario_id not in {
            scenario.id for scenario in self.traffic_scenarios
        }:
            raise ValueError("Активный сценарий отсутствует в проекте.")
        return self

    @property
    def base_population(self) -> int:
        """Возвращает население при стопроцентной заселённости."""

        return sum(floor.population for floor in self.floors)

    @property
    def occupancy_factor(self) -> float:
        """Возвращает сохранённый коэффициент заселённости как долю."""

        return self.building.occupancy_percent / 100.0

    def effective_floor_population(self, floor: Floor) -> float:
        """Возвращает расчётное население этажа с учётом заселённости."""

        return floor.population * self.occupancy_factor

    @property
    def population(self) -> int:
        """Возвращает расчётное население всего проекта."""

        return round(self.base_population * self.occupancy_factor)

    def scenario(self) -> TrafficScenario:
        """Возвращает активный сценарий."""

        if not self.traffic_scenarios:
            raise ValueError("В проекте не задан сценарий пассажиропотока.")
        if self.active_scenario_id is None:
            return self.traffic_scenarios[0]
        for scenario in self.traffic_scenarios:
            if scenario.id == self.active_scenario_id:
                return scenario
        raise ValueError("Активный сценарий не найден.")

    def group(self, group_id: str | None = None) -> ElevatorGroup:
        """Возвращает выбранную или первую лифтовую группу."""

        if not self.elevator_groups:
            raise ValueError("В проекте не задана лифтовая группа.")
        if group_id is None:
            return self.elevator_groups[0]
        for group in self.elevator_groups:
            if group.id == group_id:
                return group
        raise ValueError("Лифтовая группа не найдена.")
