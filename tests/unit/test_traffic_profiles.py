from src.models.building import BuildingType
from src.models.traffic import TrafficScenario, TrafficScenarioType
from src.utils.traffic_profiles import (
    default_scenario_type,
    scenario_for_building,
    scenario_for_gost_calculation,
    traffic_profile_description,
    traffic_profile_preset,
)


def test_lunch_profile_updates_directions_and_gost_percentage() -> None:
    preset = traffic_profile_preset(
        TrafficScenarioType.LUNCH,
        BuildingType.RESIDENTIAL,
        current_population_percent=3.0,
    )

    assert preset is not None
    assert (
        preset.incoming_percent,
        preset.outgoing_percent,
        preset.interfloor_percent,
    ) == (35, 35, 30)
    assert preset.population_percent_5min == 6.0


def test_custom_profile_preserves_user_parameters() -> None:
    assert (
        traffic_profile_preset(
            TrafficScenarioType.CUSTOM,
            BuildingType.OFFICE,
            current_population_percent=8.0,
        )
        is None
    )


def test_gost_profile_uses_locked_normative_directions_and_percentage() -> None:
    preset = traffic_profile_preset(
        TrafficScenarioType.UP_PEAK,
        BuildingType.RESIDENTIAL,
        current_population_percent=9.0,
    )

    assert preset is not None
    assert (
        preset.incoming_percent,
        preset.outgoing_percent,
        preset.interfloor_percent,
    ) == (100, 0, 0)
    assert preset.population_percent_5min == 6.0


def test_residential_building_gets_residential_morning_scenario() -> None:
    scenario = scenario_for_building(
        TrafficScenario(),
        BuildingType.RESIDENTIAL,
    )

    assert (
        default_scenario_type(BuildingType.RESIDENTIAL)
        is TrafficScenarioType.RESIDENTIAL_MORNING
    )
    assert scenario.scenario_type is TrafficScenarioType.RESIDENTIAL_MORNING
    assert (
        scenario.incoming_share,
        scenario.outgoing_share,
        scenario.interfloor_share,
    ) == (0.10, 0.80, 0.10)
    assert scenario.population_percent_5min == 6.0


def test_gost_calculation_uses_normative_up_peak_scenario() -> None:
    source = TrafficScenario(
        scenario_type=TrafficScenarioType.RESIDENTIAL_MORNING,
        population_percent_5min=9.0,
        incoming_share=0.10,
        outgoing_share=0.80,
        interfloor_share=0.10,
    )

    scenario = scenario_for_gost_calculation(
        source,
        BuildingType.RESIDENTIAL,
    )

    assert scenario.id == source.id
    assert scenario.scenario_type is TrafficScenarioType.UP_PEAK
    assert (
        scenario.incoming_share,
        scenario.outgoing_share,
        scenario.interfloor_share,
    ) == (1.0, 0.0, 0.0)
    assert scenario.population_percent_5min == 6.0


def test_every_scenario_has_a_short_description() -> None:
    assert all(
        traffic_profile_description(scenario_type)
        for scenario_type in TrafficScenarioType
    )
