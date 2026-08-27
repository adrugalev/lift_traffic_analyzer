"""Стартовые параметры типовых сценариев пассажиропотока."""

from __future__ import annotations

from dataclasses import dataclass

from src.models.building import BuildingType
from src.models.traffic import (
    ArrivalDistribution,
    TrafficScenario,
    TrafficScenarioType,
)
from src.services.configuration_service import ConfigurationService


@dataclass(frozen=True)
class TrafficProfilePreset:
    """Автоматически подставляемые, но редактируемые параметры сценария."""

    incoming_percent: int
    outgoing_percent: int
    interfloor_percent: int
    population_percent_5min: float


DEFAULT_SCENARIO_BY_BUILDING_TYPE = {
    BuildingType.RESIDENTIAL: TrafficScenarioType.RESIDENTIAL_MORNING,
    BuildingType.OFFICE: TrafficScenarioType.UP_PEAK,
    BuildingType.HOTEL: TrafficScenarioType.HOTEL_MORNING,
    BuildingType.MIXED_USE: TrafficScenarioType.MIXED,
    BuildingType.CUSTOM: TrafficScenarioType.CUSTOM,
}


def default_scenario_type(building_type: BuildingType) -> TrafficScenarioType:
    """Возвращает наиболее характерный стартовый сценарий для типа здания."""

    return DEFAULT_SCENARIO_BY_BUILDING_TYPE[building_type]


def traffic_profile_description(scenario_type: TrafficScenarioType) -> str:
    """Возвращает краткое пользовательское пояснение типового сценария."""

    profiles = ConfigurationService().load("traffic_profiles.yaml").get(
        "profiles", {}
    )
    profile = profiles.get(scenario_type.name.lower(), {})
    return str(profile.get("description_ru", ""))


def traffic_profile_preset(
    scenario_type: TrafficScenarioType,
    building_type: BuildingType,
    current_population_percent: float,
) -> TrafficProfilePreset | None:
    """Возвращает стартовый профиль или ``None`` для пользовательского сценария."""

    if scenario_type is TrafficScenarioType.CUSTOM:
        return None

    configuration = ConfigurationService()
    profiles = configuration.load("traffic_profiles.yaml").get("profiles", {})
    profile = profiles.get(scenario_type.name.lower())
    if not isinstance(profile, dict):
        return None

    shares = (
        float(profile["incoming_share"]),
        float(profile["outgoing_share"]),
        float(profile["interfloor_share"]),
    )
    if abs(sum(shares) - 1.0) > 1e-9:
        raise ValueError("Сумма долей типового профиля должна быть равна 1.")

    standard = configuration.standard("GOST_34758_2021")
    criteria = standard.get("criteria", {})
    if building_type.value in criteria:
        population_percent = float(
            criteria[building_type.value]["traffic_percent_5min_min"]
        )
    elif building_type is BuildingType.MIXED_USE and criteria:
        population_percent = max(
            float(item["traffic_percent_5min_min"])
            for item in criteria.values()
        )
    else:
        population_percent = float(current_population_percent)

    percentages = tuple(round(share * 100) for share in shares)
    return TrafficProfilePreset(
        incoming_percent=percentages[0],
        outgoing_percent=percentages[1],
        interfloor_percent=percentages[2],
        population_percent_5min=population_percent,
    )


def scenario_for_building(
    scenario: TrafficScenario,
    building_type: BuildingType,
) -> TrafficScenario:
    """Устанавливает стартовый нормативный сценарий для выбранного здания."""

    scenario_type = TrafficScenarioType.UP_PEAK
    preset = traffic_profile_preset(
        scenario_type,
        building_type,
        scenario.population_percent_5min,
    )
    updates: dict[str, object] = {
        "name": "По ГОСТ",
        "scenario_type": scenario_type,
        "five_minute_passengers": None,
        "arrival_distribution": ArrivalDistribution.POISSON,
        "random_bursts": False,
    }
    if preset is not None:
        updates.update(
            {
                "population_percent_5min": preset.population_percent_5min,
                "incoming_share": preset.incoming_percent / 100.0,
                "outgoing_share": preset.outgoing_percent / 100.0,
                "interfloor_share": preset.interfloor_percent / 100.0,
            }
        )
    return TrafficScenario.model_validate(
        {**scenario.model_dump(), **updates}
    )


def scenario_for_gost_calculation(
    scenario: TrafficScenario,
    building_type: BuildingType,
) -> TrafficScenario:
    """Возвращает нормативный восходящий сценарий для расчёта по ГОСТ."""

    preset = traffic_profile_preset(
        TrafficScenarioType.UP_PEAK,
        building_type,
        scenario.population_percent_5min,
    )
    if preset is None:
        raise ValueError("Не удалось сформировать нормативный сценарий ГОСТ.")

    return TrafficScenario.model_validate(
        {
            **scenario.model_dump(),
            "name": TrafficScenarioType.UP_PEAK.value,
            "scenario_type": TrafficScenarioType.UP_PEAK,
            "five_minute_passengers": None,
            "population_percent_5min": preset.population_percent_5min,
            "incoming_share": preset.incoming_percent / 100.0,
            "outgoing_share": preset.outgoing_percent / 100.0,
            "interfloor_share": preset.interfloor_percent / 100.0,
        }
    )
