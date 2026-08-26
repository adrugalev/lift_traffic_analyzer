import pytest

from src.services.project_service import ProjectService
from src.utils.floor_roles import synchronize_main_floor


def test_main_floor_from_floors_is_applied_to_all_groups() -> None:
    project = ProjectService.create_default()
    project.floors[0].is_main_entrance = False
    project.floors[0].is_entrance = False
    project.floors[1].is_main_entrance = True

    synchronized = synchronize_main_floor(project)

    assert synchronized.floors[1].is_entrance is True
    assert all(
        group.main_floor == synchronized.floors[1].number
        for group in synchronized.elevator_groups
    )


def test_exactly_one_main_floor_is_required() -> None:
    project = ProjectService.create_default()
    project.floors[1].is_main_entrance = True

    with pytest.raises(ValueError, match="ровно один"):
        synchronize_main_floor(project)
