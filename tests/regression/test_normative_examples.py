"""Регрессия по примеру расчётного метода из приложения Д ГОСТ 34758-2021."""

from __future__ import annotations

import pytest

from src.engines.analytic_engine import (
    AnalyticEngine,
    expected_highest_reversal,
    group_handling_capacity,
    handling_capacity_percent,
    normative_interval,
    normative_round_trip_time,
    probable_stops_uniform,
)
from src.models.elevator import Elevator
from src.services.project_service import ProjectService

@pytest.mark.regression
def test_gost_appendix_d_lower_zone() -> None:
    passengers = 13.1
    stops = probable_stops_uniform(13, passengers)
    reversal = expected_highest_reversal(13, passengers)
    # В опубликованном примере S и Nр сначала показаны с точностью до 0,1,
    # затем именно эти значения подставлены в формулу (7).
    rtt = normative_round_trip_time(
        round(reversal, 1), 1.6, round(stops, 1), 10.5, passengers, 1.0
    )
    interval = normative_interval(rtt, 6)
    capacity = group_handling_capacity(passengers, 6, rtt)

    assert stops == pytest.approx(8.4, abs=0.05)
    assert reversal == pytest.approx(12.5, abs=0.05)
    assert rtt == pytest.approx(164.9, abs=0.2)
    assert interval == pytest.approx(27.5, abs=0.1)
    assert capacity == pytest.approx(142.9, abs=0.2)
    assert handling_capacity_percent(capacity, 1092) == pytest.approx(13.1, abs=0.1)


@pytest.mark.regression
def test_gost_appendix_d_upper_zone() -> None:
    passengers = 13.1
    stops = probable_stops_uniform(13, passengers)
    local_reversal = expected_highest_reversal(13, passengers)
    building_reversal = round(local_reversal, 1) + 13.0
    rtt = normative_round_trip_time(
        building_reversal, 0.8, round(stops, 1), 11.3, passengers, 1.0
    )
    interval = normative_interval(rtt, 6)
    capacity = group_handling_capacity(passengers, 6, rtt)

    assert building_reversal == pytest.approx(25.5, abs=0.05)
    assert rtt == pytest.approx(173.2, abs=0.2)
    assert interval == pytest.approx(28.9, abs=0.1)
    assert capacity == pytest.approx(136.0, abs=0.2)
    assert handling_capacity_percent(capacity, 1092) == pytest.approx(12.5, abs=0.1)


@pytest.mark.regression
def test_control_project_matches_reference_intermediate_values() -> None:
    """Одинаковые входные данные дают значения контрольного отчёта до 0,01."""

    project = ProjectService.create_default(floors_count=9)
    group = project.elevator_groups[0]
    group.elevators = [
        Elevator(
            name=f"Лифт A{index}",
            capacity_kg=1000.0,
            nominal_passengers=13,
            load_factor=0.8,
            speed_mps=2.0,
            acceleration_mps2=0.8,
            deceleration_mps2=0.8,
            jerk_mps3=1.0,
            door_width_m=0.9,
            door_open_time_s=2.5,
            door_close_time_s=4.5,
            pre_open_time_s=0.0,
            door_dwell_time_s=1.0,
            start_brake_allowance_s=0.5,
            travel_height_m=25.6,
            stops_count=9,
        )
        for index in range(1, 7)
    ]
    for floor in project.floors:
        floor.elevation_m = (floor.number - 1) * 3.2
        floor.floor_height_m = 3.2
        floor.population = 0 if floor.number == 1 else 100

    result = AnalyticEngine().calculate_normative(project)

    assert result.metric("actual_car_passengers").value == 10
    assert result.metric("adjacent_floor_profile_time").value == pytest.approx(
        4.88, abs=0.005
    )
    assert result.metric("probable_stops").value == pytest.approx(5.90, abs=0.005)
    assert result.metric("highest_reversal").value == pytest.approx(7.67, abs=0.005)
    assert result.metric("stop_time").value == pytest.approx(11.78, abs=0.005)
    assert result.metric("cycle_time").value == pytest.approx(127.77, abs=0.005)
    assert result.metric("interval").value == pytest.approx(21.29, abs=0.005)
    assert result.metric("handling_capacity_5min").value == pytest.approx(
        140.88, abs=0.005
    )
