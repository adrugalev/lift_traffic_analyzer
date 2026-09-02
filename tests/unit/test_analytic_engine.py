"""Unit-тесты прозрачных инженерных зависимостей."""

from __future__ import annotations

import pytest

from src.engines.analytic_engine import (
    AnalyticEngine,
    NormativeConfigurationError,
    adjacent_floor_nominal_time,
    calculated_capacity,
    expected_parking_depth,
    expected_parking_lower_reversal,
    expected_highest_reversal,
    group_handling_capacity,
    handling_capacity_percent,
    jerk_limited_peak_speed,
    jerk_limited_transition_distance,
    jerk_limited_travel_phases,
    jerk_limited_travel_time,
    mixed_group_handling_capacity,
    mixed_group_interval,
    nominal_passengers_from_capacity,
    normative_interval,
    normative_round_trip_time,
    normative_stop_time,
    passenger_transfer_time,
    probable_stops_uniform,
    probable_parking_stops,
    travel_time,
    travel_time_phases,
)
from src.models.floor import Floor
from src.services.configuration_service import ConfigurationService
from src.services.project_service import ProjectService


def test_calculated_capacity_never_exceeds_nominal() -> None:
    assert calculated_capacity(13, 0.8) == 10
    assert calculated_capacity(13, 0.5) == 7
    assert calculated_capacity(13, 1.0) == 13


@pytest.mark.parametrize("nominal,factor", [(0, 0.8), (13, 0.0), (13, 1.1)])
def test_calculated_capacity_rejects_invalid_inputs(nominal: int, factor: float) -> None:
    with pytest.raises(ValueError):
        calculated_capacity(nominal, factor)


def test_motion_time_trapezoidal_profile() -> None:
    assert travel_time(100.0, 2.0, 1.0, 1.0) == pytest.approx(52.0)


def test_motion_time_triangular_profile() -> None:
    assert travel_time(1.0, 2.0, 1.0, 1.0) == pytest.approx(2.0)


def test_motion_time_equals_sum_of_displayed_phases() -> None:
    phases = travel_time_phases(100.0, 2.0, 1.0, 1.0)

    assert phases == pytest.approx((2.0, 48.0, 2.0))
    assert travel_time(100.0, 2.0, 1.0, 1.0) == pytest.approx(sum(phases))


def test_jerk_limited_motion_time_matches_control_profile() -> None:
    assert jerk_limited_travel_time(3.2, 2.0, 0.8, 0.8, 1.0) == pytest.approx(
        4.879215610874,
        abs=1e-12,
    )


def test_jerk_limited_time_equals_sum_of_displayed_phases() -> None:
    phases = jerk_limited_travel_phases(3.2, 2.0, 0.8, 0.8, 1.0)

    assert phases[1] == pytest.approx(0.0)
    assert jerk_limited_travel_time(3.2, 2.0, 0.8, 0.8, 1.0) == pytest.approx(
        sum(phases)
    )


def test_jerk_limited_peak_speed_matches_closed_form_for_symmetric_profile() -> None:
    distance = 3.2
    acceleration = 0.8
    jerk = 1.0
    expected = (
        -(acceleration**2) / (2.0 * jerk)
        + (
            acceleration * distance
            + ((acceleration**2) / (2.0 * jerk)) ** 2
        )
        ** 0.5
    )

    peak_speed = jerk_limited_peak_speed(
        distance,
        2.0,
        acceleration,
        acceleration,
        jerk,
    )

    assert peak_speed == pytest.approx(expected, abs=1e-12)
    assert peak_speed < 2.0
    assert 2.0 * jerk_limited_transition_distance(
        peak_speed, acceleration, jerk
    ) == pytest.approx(distance, abs=1e-12)


def test_jerk_limited_peak_speed_returns_nominal_when_distance_is_sufficient() -> None:
    assert jerk_limited_peak_speed(20.0, 2.0, 0.8, 0.8, 1.0) == pytest.approx(2.0)


def test_jerk_limited_motion_rejects_invalid_parameters() -> None:
    with pytest.raises(ValueError):
        jerk_limited_travel_time(3.2, 2.0, 0.8, 0.8, 0.0)


def test_probable_stops_is_bounded() -> None:
    result = probable_stops_uniform(20, 10)
    assert 0 < result <= 20


def test_highest_reversal_is_bounded() -> None:
    result = expected_highest_reversal(20, 10)
    assert 1 <= result <= 20


def test_preview_contains_interval_capacity_and_formula_traces() -> None:
    project = ProjectService.create_default()
    result = AnalyticEngine().calculate_preview(project)
    assert result.metric("interval").value > 0
    assert result.metric("handling_capacity_5min").value > 0
    assert len(result.formulas) >= 7
    assert all(trace.clause is None for trace in result.formulas)
    assert all(metric.compliance.value == "Не оценено" for metric in result.metrics)


def test_gost_normative_calculation_is_enabled() -> None:
    result = AnalyticEngine().calculate_normative(ProjectService.create_default())
    assert result.calculation_basis == "GOST_34758_2021_CLAUSE_7"
    assert result.metric("interval").value > 0
    assert result.metric("handling_capacity_5min").value > 0
    assert all(trace.clause for trace in result.formulas)
    assert result.metric("actual_car_passengers").value.is_integer()
    assert result.metric("adjacent_floor_profile_time").value > 0
    assert result.metric("adjacent_floor_peak_speed").value > 0
    assert result.metric("adjacent_floor_peak_speed").value < (
        ProjectService.create_default().elevator_groups[0].elevators[0].speed_mps
    )
    assert {
        "kinematic_acceleration_distance",
        "kinematic_maximum_speed",
    } <= {trace.formula_id for trace in result.formulas}


def test_strict_gost_kinematics_uses_formula_8_only() -> None:
    project = ProjectService.create_default()
    elevator = project.elevator_groups[0].elevators[0]
    result = AnalyticEngine().calculate_normative(
        project,
        include_extended_kinematics=False,
    )

    formula_ids = {trace.formula_id for trace in result.formulas}
    assert result.metric("adjacent_floor_peak_speed").value == pytest.approx(
        elevator.speed_mps
    )
    nominal_time = next(
        trace.result
        for trace in result.formulas
        if trace.formula_id == "gost_adjacent_floor_time"
    )
    assert result.metric("adjacent_floor_profile_time").value == pytest.approx(
        nominal_time
    )
    assert "gost_adjacent_floor_time" in formula_ids
    assert "gost_adjacent_floor_profile_time" not in formula_ids
    assert "kinematic_acceleration_distance" not in formula_ids
    assert "kinematic_maximum_speed" not in formula_ids
    assert not any(
        message.code == "NOMINAL_SPEED_NOT_REACHED_ADJACENT_FLOOR"
        for message in result.messages
    )


def test_formula_trace_symbols_exist_in_reference_tables() -> None:
    """Подстановки расчёта используют те же обозначения, что и справочник."""

    project = ProjectService.create_default()
    results = (
        AnalyticEngine().calculate_preview(project),
        AnalyticEngine().calculate_normative(project),
    )
    registry = ConfigurationService().formulas()["formulas"]

    for result in results:
        for trace in result.formulas:
            documented_symbols = set(registry[trace.formula_id]["variables"])
            assert set(trace.variables) <= documented_symbols


def test_full_height_time_below_recommended_range_complies() -> None:
    result = AnalyticEngine().calculate_normative(ProjectService.create_default())
    metric = result.metric("full_height_time")

    assert metric.value < 25.0
    assert metric.compliance.value == "Соответствует"
    assert metric.target_value == pytest.approx(45.0)
    assert metric.target_description == "≤ 45.0 с"


def test_legacy_express_flag_does_not_change_normative_calculation() -> None:
    project = ProjectService.create_default()
    project.elevator_groups[0].express_zone = True

    result = AnalyticEngine().calculate_normative(project)

    assert result.calculation_basis == "GOST_34758_2021_CLAUSE_7"


def test_occupancy_percent_changes_normative_population() -> None:
    project = ProjectService.create_default()
    project.building.occupancy_percent = 50

    result = AnalyticEngine().calculate_normative(project)

    assert result.metric("population").value == 90


def test_gost_calculation_over_18_floors_is_not_blocked() -> None:
    project = ProjectService.create_default(floors_count=20)

    result = AnalyticEngine().calculate_normative(project)

    assert result.metric("interval").value > 0
    assert any(
        message.code == "MODELING_RECOMMENDED_OVER_18_FLOORS"
        for message in result.messages
    )


def test_gost_calculation_with_parking_is_not_blocked() -> None:
    project = ProjectService.create_default()
    group = project.elevator_groups[0]
    project.floors.insert(
        0,
        Floor(
            number=-1,
            label="P1",
            elevation_m=-3.3,
            floor_height_m=3.3,
            purpose="Подземный паркинг",
            population=0,
            served_by_group_ids=[group.id],
            is_parking=True,
        ),
    )
    group.served_floors.insert(0, -1)
    project.scenario().parking_incoming_share = 0.15

    result = AnalyticEngine().calculate_normative(project)

    assert result.metric("interval").value > 0
    assert result.metric("parking_round_trip_addition").value > 0
    assert result.metric("parking_trip_probability").value == pytest.approx(100.0)
    assert result.metric("parking_lower_reversal").value == pytest.approx(1.0)
    assert result.metric("parking_probable_stops").value == pytest.approx(1.0)
    assert result.metric("parking_expected_depth").value == pytest.approx(3.3)
    assert (
        result.metric("cycle_time").value
        > result.metric("gost_cycle_time_without_parking").value
    )
    assert {
        "parking_lower_reversal",
        "parking_expected_depth",
        "parking_probable_stops",
        "parking_round_trip_extension",
    }.issubset({trace.formula_id for trace in result.formulas})
    assert any(
        message.code == "PARKING_ENGINEERING_EXTENSION_APPLIED"
        for message in result.messages
    )


def test_preview_uses_actual_parking_share() -> None:
    project = ProjectService.create_default()
    group = project.elevator_groups[0]
    project.floors.insert(
        0,
        Floor(
            number=-1,
            label="P1",
            elevation_m=-3.3,
            floor_height_m=3.3,
            purpose="Подземный паркинг",
            population=0,
            served_by_group_ids=[group.id],
            is_parking=True,
        ),
    )
    group.served_floors.insert(0, -1)
    project.scenario().parking_incoming_share = 0.15

    result = AnalyticEngine().calculate_preview(project)
    capacity = result.metric("actual_car_passengers").value
    expected_probability = 1.0 - (1.0 - 0.15) ** capacity

    assert result.metric("parking_share").value == pytest.approx(15.0)
    assert result.metric("parking_trip_probability").value == pytest.approx(
        expected_probability * 100.0
    )
    assert result.metric("parking_lower_reversal").value == pytest.approx(
        expected_probability
    )
    assert result.metric("parking_round_trip_addition").value > 0
    assert any(
        message.code == "PARKING_EXACT_SHARE_APPLIED"
        for message in result.messages
    )


def test_parking_engineering_extension_uses_partial_parking_share() -> None:
    levels = expected_parking_lower_reversal(3, 10, 0.15)

    assert levels == pytest.approx(
        sum(1.0 - (1.0 - 0.15 * remaining / 3) ** 10 for remaining in (3, 2, 1))
    )
    assert probable_parking_stops(3, 10, 0.15) == pytest.approx(
        3 * (1 - (1 - 0.15 / 3) ** 10)
    )
    assert expected_parking_depth([3.3, 6.6, 9.9], 10, 0.15) == pytest.approx(
        3.3 * levels
    )


def test_gost_capacity_and_door_table() -> None:
    assert nominal_passengers_from_capacity(1000.0) == 13
    assert nominal_passengers_from_capacity(1275.0) == 17
    assert passenger_transfer_time(0.8) == pytest.approx(1.2)
    assert passenger_transfer_time(1.2) == pytest.approx(0.9)
    with pytest.raises(ValueError):
        passenger_transfer_time(0.95)


def test_gost_stop_interval_and_capacity_formulas() -> None:
    floor_nominal = adjacent_floor_nominal_time(4.0, 2.5)
    stop = normative_stop_time(2.4, 0.6, 5.1, 0.0, 2.0, 2.0, floor_nominal)
    assert floor_nominal == pytest.approx(1.6)
    assert stop == pytest.approx(10.5)
    rtt = normative_round_trip_time(12.5, 1.6, 8.4, stop, 13.1, 1.0)
    assert rtt == pytest.approx(164.9)
    interval = normative_interval(rtt, 6)
    capacity = group_handling_capacity(13.1, 6, rtt)
    assert interval == pytest.approx(27.4833, rel=1e-4)
    assert capacity == pytest.approx(142.996, rel=1e-4)
    assert handling_capacity_percent(capacity, 1092) == pytest.approx(13.095, rel=1e-3)


def test_mixed_group_aggregation_formulas() -> None:
    individual_intervals = [120.0, 180.0]
    car_passengers = [8.0, 12.0]

    assert mixed_group_interval(individual_intervals) == pytest.approx(75.0)
    assert mixed_group_handling_capacity(
        car_passengers,
        individual_intervals,
    ) == pytest.approx(40.0)


def test_mixed_capacity_mode_calculates_each_car_separately() -> None:
    project = ProjectService.create_default()
    group = project.elevator_groups[0]
    group.elevators[1].capacity_kg = 1275.0
    group.elevators[1].nominal_passengers = 17

    with pytest.raises(NormativeConfigurationError, match="неоднородна"):
        AnalyticEngine().calculate_normative(
            project,
            include_extended_kinematics=False,
        )

    individual_results = []
    for elevator in group.elevators:
        individual_project = project.model_copy(deep=True)
        individual_project.elevator_groups[0].elevators = [
            elevator.model_copy(deep=True)
        ]
        individual_results.append(
            AnalyticEngine().calculate_normative(
                individual_project,
                include_extended_kinematics=False,
            )
        )

    mixed_result = AnalyticEngine().calculate_normative(
        project,
        include_extended_kinematics=False,
        include_mixed_capacity=True,
    )
    expected_interval = sum(
        result.metric("interval").value for result in individual_results
    ) / len(individual_results) ** 2
    expected_capacity = sum(
        result.metric("handling_capacity_5min").value
        for result in individual_results
    )

    assert mixed_result.metric("interval").value == pytest.approx(expected_interval)
    assert mixed_result.metric("handling_capacity_5min").value == pytest.approx(
        expected_capacity
    )
    assert mixed_result.calculation_basis == "GOST_34758_2021_CLAUSE_7"
    assert mixed_result.method == (
        "Расчётный метод ГОСТ 34758-2021 "
        "(с учётом лифтов разной грузоподъёмности)"
    )
    assert {
        "mixed_group_interval",
        "mixed_group_handling_capacity",
    } <= {trace.formula_id for trace in mixed_result.formulas}
    assert any(
        message.code == "MIXED_CAPACITY_ENGINEERING_METHOD_APPLIED"
        for message in mixed_result.messages
    )
