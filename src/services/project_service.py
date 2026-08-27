"""Создание, миграция и сериализация проектов."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from random import SystemRandom
from typing import Any

from src.models.building import Building, BuildingType, ProjectMetadata
from src.models.elevator import DoorOpeningType, Elevator, ElevatorGroup
from src.models.floor import Floor
from src.models.project import Project
from src.models.traffic import ArrivalDistribution, TrafficScenario, TrafficScenarioType
from src.utils.traffic_profiles import scenario_for_building


class ProjectService:
    """Управляет сохраняемым форматом проекта версии 1.0."""

    CURRENT_SCHEMA_VERSION = "1.0"
    TEST_PROJECT_TEMPLATES: dict[str, dict[str, Any]] = {
        "homecity": {
            "name": "ЖК Homecity",
            "address": (
                "г. Москва, поселение Московский, Киевское шоссе, "
                "22-й километр, д. 6В"
            ),
            "customer": "ООО «Специализированный застройщик «Дельта Ком»",
            "designer": "Архитектурная мастерская «Сергей Киселев и партнеры» / MLA+",
            "floors_count": 9,
            "floor_height_m": 3.2,
            "population_per_floor": 50,
            "area_m2": 780.0,
            "speed_mps": 2.0,
        },
        "simvol": {
            "name": "ЖК «Символ»",
            "address": "г. Москва, ул. Золоторожский Вал, д. 11",
            "customer": "АО «Дон-Строй Инвест»",
            "designer": "LDA Design / UHA London / архитектурное бюро ATRIUM",
            "floors_count": 24,
            "parking_levels": 2,
            "floor_height_m": 3.15,
            "population_per_floor": 44,
            "area_m2": 720.0,
            "speed_mps": 2.5,
        },
        "zilart": {
            "name": "ЖК «ЗИЛАРТ»",
            "address": "г. Москва, ул. Архитектора Щусева, д. 1",
            "customer": "ПАО «Группа ЛСР»",
            "designer": "Архитектурные бюро жилого комплекса «ЗИЛАРТ»",
            "floors_count": 18,
            "parking_levels": 1,
            "floor_height_m": 3.3,
            "population_per_floor": 56,
            "area_m2": 840.0,
            "speed_mps": 2.5,
        },
        "heart_of_capital": {
            "name": "ЖК «Сердце Столицы»",
            "address": "г. Москва, Шелепихинская наб., д. 34",
            "customer": "АО «Дон-Строй Инвест»",
            "designer": "Архитектурные бюро жилого квартала «Сердце Столицы»",
            "floors_count": 28,
            "parking_levels": 2,
            "floor_height_m": 3.25,
            "population_per_floor": 48,
            "area_m2": 760.0,
            "speed_mps": 3.0,
        },
        "level_prichalny": {
            "name": "ЖК Level Причальный",
            "address": "г. Москва, Причальный пр., д. 8, корп. 1",
            "customer": "Level Group",
            "designer": "Архитектурное бюро SPEECH",
            "floors_count": 33,
            "parking_levels": 2,
            "floor_height_m": 3.15,
            "population_per_floor": 42,
            "area_m2": 700.0,
            "speed_mps": 3.0,
        },
    }

    @classmethod
    def create_default(cls, floors_count: int = 10) -> Project:
        """Создаёт редактируемый стартовый проект."""

        group = ElevatorGroup(
            name="Группа A",
            main_floor=1,
            served_floors=list(range(1, floors_count + 1)),
            elevators=[
                Elevator(name="Лифт A1", stops_count=floors_count, travel_height_m=max(0, floors_count - 1) * 3.0),
                Elevator(name="Лифт A2", stops_count=floors_count, travel_height_m=max(0, floors_count - 1) * 3.0),
            ],
        )
        floors = [
            Floor(
                number=number,
                label=str(number),
                elevation_m=(number - 1) * 3.0,
                population=0 if number == 1 else 20,
                served_by_group_ids=[group.id],
                is_main_entrance=number == 1,
                is_entrance=number == 1,
            )
            for number in range(1, floors_count + 1)
        ]
        scenario = TrafficScenario()
        return Project(
            metadata=ProjectMetadata(),
            building=Building(),
            floors=floors,
            elevator_groups=[group],
            traffic_scenarios=[scenario],
            active_scenario_id=scenario.id,
        )

    @classmethod
    def create_application_default(cls, floors_count: int = 10) -> Project:
        """Создаёт стартовый проект с нормативным сценарием «По ГОСТ»."""

        project = cls.create_default(floors_count=floors_count)
        project.traffic_scenarios[0] = scenario_for_building(
            project.scenario(),
            project.building.building_type,
        )
        return project

    @classmethod
    def test_project_keys(cls) -> tuple[str, ...]:
        """Возвращает ключи доступных демонстрационных проектов."""

        return tuple(cls.TEST_PROJECT_TEMPLATES)

    @classmethod
    def create_test_project(
        cls,
        elevator_count: int | None = None,
        *,
        project_key: str | None = None,
    ) -> Project:
        """Создаёт один из полностью заполненных жилых проектов."""

        if project_key is None:
            project_key = SystemRandom().choice(cls.test_project_keys())
        if project_key not in cls.TEST_PROJECT_TEMPLATES:
            raise ValueError(f"Неизвестный тестовый проект: {project_key}.")
        template = cls.TEST_PROJECT_TEMPLATES[project_key]
        floors_count = int(template["floors_count"])
        parking_levels = int(template.get("parking_levels", 0))
        if elevator_count is None:
            elevator_count = SystemRandom().randint(2, 6)
        if not 2 <= elevator_count <= 6:
            raise ValueError("В тестовом проекте должно быть от 2 до 6 лифтов.")

        floor_height_m = float(template["floor_height_m"])
        parking_height_m = 3.3
        served_floors = [
            *range(-parking_levels, 0),
            *range(1, floors_count + 1),
        ]
        travel_height_m = (
            (floors_count - 1) * floor_height_m
            + parking_levels * parking_height_m
        )
        group = ElevatorGroup(
            name=f"Группа A — {template['name']}",
            service_zone_name="Все этажи",
            main_floor=1,
            served_floors=served_floors,
            building_type=BuildingType.RESIDENTIAL.value,
            elevators=[
                Elevator(
                    name=f"Лифт A{index}",
                    capacity_kg=1000.0,
                    nominal_passengers=13,
                    load_factor=0.8,
                    speed_mps=float(template["speed_mps"]),
                    acceleration_mps2=0.8,
                    deceleration_mps2=0.8,
                    jerk_mps3=1.0,
                    door_width_m=0.9,
                    door_opening_type=DoorOpeningType.TELESCOPIC,
                    door_open_time_s=2.5,
                    door_close_time_s=4.5,
                    pre_open_time_s=0.0,
                    door_dwell_time_s=1.0,
                    boarding_time_per_passenger_s=1.1,
                    alighting_time_per_passenger_s=1.1,
                    start_brake_allowance_s=0.5,
                    travel_height_m=travel_height_m,
                    stops_count=len(served_floors),
                    accessible=index == 1,
                    fire_service=index == elevator_count,
                )
                for index in range(1, elevator_count + 1)
            ],
        )
        floors = [
            Floor(
                number=number,
                label=f"P{abs(number)}",
                elevation_m=number * parking_height_m,
                floor_height_m=parking_height_m,
                purpose="Подземный паркинг",
                population=0,
                served_by_group_ids=[group.id],
                is_parking=True,
            )
            for number in range(-parking_levels, 0)
        ]
        for number in range(1, floors_count + 1):
            population = (
                0
                if number == 1
                else int(template["population_per_floor"])
            )
            floors.append(
                Floor(
                    number=number,
                    label="Вход" if number == 1 else str(number),
                    elevation_m=(number - 1) * floor_height_m,
                    floor_height_m=floor_height_m,
                    purpose="Входная группа" if number == 1 else "Жилой этаж",
                    area_m2=(
                        float(template["area_m2"]) * 0.7
                        if number == 1
                        else float(template["area_m2"]) + (number % 3) * 40.0
                    ),
                    population=population,
                    incoming_passengers=round(population * 0.06),
                    outgoing_passengers=0,
                    interfloor_passengers=0,
                    served_by_group_ids=[group.id],
                    is_main_entrance=number == 1,
                    is_entrance=number == 1,
                )
            )

        scenario = scenario_for_building(TrafficScenario(
            name="Утренний восходящий пик",
            scenario_type=TrafficScenarioType.UP_PEAK,
            duration_s=300,
            population_percent_5min=6.0,
            incoming_share=1.0,
            outgoing_share=0.0,
            interfloor_share=0.0,
            parking_incoming_share=0.15,
            arrival_distribution=ArrivalDistribution.POISSON,
            random_bursts=True,
        ), BuildingType.RESIDENTIAL)
        return Project(
            metadata=ProjectMetadata(
                name=str(template["name"]),
                address=str(template["address"]),
                customer=str(template["customer"]),
                designer=str(template["designer"]),
                calculation_author="Другалев Александр Александрович",
                design_stage="Концепция",
                comment="",
            ),
            building=Building(building_type=BuildingType.RESIDENTIAL),
            floors=floors,
            elevator_groups=[group],
            traffic_scenarios=[scenario],
            active_scenario_id=scenario.id,
        )

    @classmethod
    def dumps(cls, project: Project, indent: int = 2) -> str:
        """Сериализует проект в UTF-8 JSON."""

        project.modified_at = datetime.now(timezone.utc)
        return project.model_dump_json(indent=indent)

    @classmethod
    def dump_bytes(cls, project: Project) -> bytes:
        """Возвращает JSON проекта как байты UTF-8."""

        return cls.dumps(project).encode("utf-8")

    @classmethod
    def loads(cls, content: str | bytes) -> Project:
        """Загружает и при необходимости мигрирует проект."""

        text = content.decode("utf-8-sig") if isinstance(content, bytes) else content
        payload = json.loads(text)
        migrated = cls.migrate(payload)
        return Project.model_validate(migrated)

    @classmethod
    def load_file(cls, path: Path) -> Project:
        """Загружает проект с диска."""

        return cls.loads(path.read_bytes())

    @classmethod
    def save_file(cls, project: Project, path: Path) -> None:
        """Сохраняет проект атомарной заменой временного файла."""

        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_bytes(cls.dump_bytes(project))
        temporary.replace(path)

    @classmethod
    def migrate(cls, payload: dict[str, Any]) -> dict[str, Any]:
        """Мигрирует известные ранние варианты схемы к версии 1.0."""

        version = str(payload.get("schema_version", "0.9"))
        migrated = dict(payload)
        if version == "0.9":
            migrated["schema_version"] = cls.CURRENT_SCHEMA_VERSION
            if "project_info" in migrated and "metadata" not in migrated:
                migrated["metadata"] = migrated.pop("project_info")
        if migrated.get("schema_version") != cls.CURRENT_SCHEMA_VERSION:
            raise ValueError(
                f"Версия схемы {migrated.get('schema_version')!r} не поддерживается; "
                f"ожидается {cls.CURRENT_SCHEMA_VERSION}."
            )
        return migrated
