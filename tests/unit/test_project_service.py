"""Тестовые проекты для быстрой проверки интерфейса."""

from src.models.elevator import DoorOpeningType, Elevator
from src.models.traffic import TrafficScenarioType
from src.services.project_service import ProjectService


def test_create_test_project_fills_all_calculation_sections() -> None:
    project = ProjectService.create_test_project(
        elevator_count=4,
        project_key="homecity",
    )

    assert project.metadata.name == "ЖК Homecity"
    assert project.metadata.address.endswith("22-й километр, д. 6В")
    assert project.metadata.customer == "ООО «Специализированный застройщик «Дельта Ком»"
    assert len(project.floors) == 9
    assert project.population > 0
    assert len(project.elevator_groups) == 1
    assert project.elevator_groups[0].elevator_count == 4
    assert all(
        floor.served_by_group_ids == [project.elevator_groups[0].id]
        for floor in project.floors
    )
    assert project.scenario().population_percent_5min == 6.0
    assert project.scenario().random_bursts is True
    assert (
        project.scenario().scenario_type
        is TrafficScenarioType.RESIDENTIAL_MORNING
    )
    elevator = project.elevator_groups[0].elevators[0]
    assert elevator.door_opening_type is DoorOpeningType.TELESCOPIC
    assert elevator.door_width_m == 0.9
    assert elevator.door_open_time_s == 2.5
    assert elevator.door_close_time_s == 4.5
    assert elevator.door_dwell_time_s == 1.0
    assert elevator.pre_open_time_s == 0.0
    assert elevator.start_brake_allowance_s == 0.5
    assert elevator.boarding_time_per_passenger_s == 1.1
    assert elevator.alighting_time_per_passenger_s == 1.1
    assert elevator.acceleration_mps2 == 0.8
    assert elevator.deceleration_mps2 == 0.8
    assert elevator.jerk_mps3 == 1.0


def test_new_elevator_uses_reference_door_defaults() -> None:
    elevator = Elevator()

    assert elevator.capacity_kg == 1000.0
    assert elevator.door_width_m == 0.9
    assert elevator.door_opening_type is DoorOpeningType.TELESCOPIC
    assert elevator.boarding_time_per_passenger_s == 1.1
    assert elevator.alighting_time_per_passenger_s == 1.1
    assert elevator.door_open_time_s == 2.5
    assert elevator.door_close_time_s == 4.5
    assert elevator.door_dwell_time_s == 1.0
    assert elevator.pre_open_time_s == 0.0
    assert elevator.start_brake_allowance_s == 0.5
    assert elevator.acceleration_mps2 == 0.8
    assert elevator.deceleration_mps2 == 0.8
    assert elevator.jerk_mps3 == 1.0


def test_create_test_project_rejects_out_of_range_elevator_count() -> None:
    try:
        ProjectService.create_test_project(elevator_count=1)
    except ValueError as exc:
        assert "от 2 до 6" in str(exc)
    else:
        raise AssertionError("Ожидалась проверка количества лифтов.")


def test_test_project_catalog_contains_five_distinct_projects() -> None:
    keys = ProjectService.test_project_keys()
    projects = [
        ProjectService.create_test_project(elevator_count=3, project_key=key)
        for key in keys
    ]

    assert len(keys) >= 5
    assert len({project.metadata.name for project in projects}) == len(keys)
    assert all(project.metadata.address for project in projects)
    assert all(project.metadata.customer for project in projects)


def test_occupancy_percent_is_persisted_and_changes_population() -> None:
    project = ProjectService.create_default()
    project.building.occupancy_percent = 61

    restored = ProjectService.loads(ProjectService.dump_bytes(project))

    assert project.base_population == 180
    assert project.population == 110
    assert restored.building.occupancy_percent == 61
    assert restored.population == 110
