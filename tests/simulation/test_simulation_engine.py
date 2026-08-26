"""Сценарные тесты дискретно-событийной модели."""

from __future__ import annotations

import numpy as np

from src.engines.simulation_engine import SimulationEngine
from src.models.floor import Floor
from src.models.simulation import SimulationSettings
from src.models.traffic import ArrivalDistribution
from src.services.project_service import ProjectService


def _imported_project(passengers: list[dict[str, float | int]]):
    project = ProjectService.create_default()
    scenario = project.traffic_scenarios[0]
    scenario.arrival_distribution = ArrivalDistribution.IMPORTED
    scenario.imported_passengers = passengers
    return project


def test_one_passenger_one_elevator() -> None:
    project = _imported_project(
        [{"arrival_time_s": 0.0, "origin_floor": 1, "destination_floor": 10}]
    )
    project.elevator_groups[0].elevators = project.elevator_groups[0].elevators[:1]
    result = SimulationEngine().run(
        project, SimulationSettings(repetitions=1, random_seed=7)
    )
    assert result.transported_passengers == 1
    assert result.unserved_passengers == 0
    assert result.waiting_time.mean >= 0
    assert result.time_to_destination.mean > result.waiting_time.mean


def test_same_route_passengers_are_batched() -> None:
    project = _imported_project(
        [
            {"arrival_time_s": 0.0, "origin_floor": 1, "destination_floor": 10},
            {"arrival_time_s": 0.1, "origin_floor": 1, "destination_floor": 10},
            {"arrival_time_s": 0.2, "origin_floor": 1, "destination_floor": 10},
        ]
    )
    project.elevator_groups[0].elevators = project.elevator_groups[0].elevators[:1]
    result = SimulationEngine().run(
        project, SimulationSettings(repetitions=1, random_seed=7)
    )
    assert result.transported_passengers == 3
    assert result.maximum_car_load >= 2


def test_capacity_overflow_requires_multiple_trips() -> None:
    project = _imported_project(
        [
            {"arrival_time_s": 0.0, "origin_floor": 1, "destination_floor": 10}
            for _ in range(6)
        ]
    )
    elevator = project.elevator_groups[0].elevators[0]
    elevator.nominal_passengers = 2
    elevator.load_factor = 1.0
    project.elevator_groups[0].elevators = [elevator]
    result = SimulationEngine().run(
        project, SimulationSettings(repetitions=1, random_seed=11)
    )
    assert result.transported_passengers == 6
    assert result.maximum_car_load <= 2
    assert result.stops_count >= 3


def test_multiple_elevators_are_used() -> None:
    project = _imported_project(
        [
            {"arrival_time_s": 0.0, "origin_floor": 1, "destination_floor": 10}
            for _ in range(20)
        ]
    )
    result = SimulationEngine().run(
        project, SimulationSettings(repetitions=1, random_seed=5)
    )
    used = {point.elevator_id for point in result.trajectories}
    assert len(used) == 2


def test_same_seed_is_exactly_reproducible() -> None:
    project = ProjectService.create_default()
    settings = SimulationSettings(repetitions=3, random_seed=123)
    first = SimulationEngine().run(project, settings)
    second = SimulationEngine().run(project, settings)
    assert first.model_dump() == second.model_dump()


def test_parking_share_generates_incoming_trips_from_parking() -> None:
    project = ProjectService.create_default()
    project.building.occupancy_percent = 50
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
    scenario = project.scenario()
    scenario.arrival_distribution = ArrivalDistribution.DETERMINISTIC
    scenario.five_minute_passengers = 9999
    scenario.population_percent_5min = 10.0
    scenario.incoming_share = 1.0
    scenario.outgoing_share = 0.0
    scenario.interfloor_share = 0.0
    scenario.parking_incoming_share = 1.0

    passengers = SimulationEngine().generate_passengers(
        project,
        scenario,
        np.random.default_rng(7),
        group,
    )

    assert passengers
    assert len(passengers) == 9
    assert {passenger.origin_floor for passenger in passengers} == {-1}
    assert all(passenger.destination_floor > 1 for passenger in passengers)
