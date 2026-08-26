"""Синхронизация назначения основного посадочного этажа."""

from __future__ import annotations

from src.models.project import Project


def synchronize_main_floor(project: Project) -> Project:
    """Назначает отмеченный основной этаж всем лифтовым группам."""

    candidate = project.model_copy(deep=True)
    main_floors = [
        floor for floor in candidate.floors if floor.is_main_entrance
    ]
    if len(main_floors) != 1:
        raise ValueError(
            "В таблице должен быть выбран ровно один основной посадочный этаж."
        )
    main_floor = main_floors[0]
    if main_floor.is_parking:
        raise ValueError(
            "Парковочный этаж не может быть основным посадочным этажом."
        )
    main_floor.is_entrance = True

    floor_numbers = {floor.number for floor in candidate.floors}
    for group in candidate.elevator_groups:
        group.main_floor = main_floor.number
        group.served_floors = sorted(
            {
                floor_number
                for floor_number in group.served_floors
                if floor_number in floor_numbers
            }
            | {main_floor.number}
        )
        for elevator in group.elevators:
            elevator.stops_count = len(group.served_floors)

    for floor in candidate.floors:
        floor.served_by_group_ids = [
            group.id
            for group in candidate.elevator_groups
            if floor.number in group.served_floors
        ]
    return Project.model_validate(candidate.model_dump())
