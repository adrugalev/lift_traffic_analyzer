"""Unit-тесты валидации проекта."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.services.project_service import ProjectService
from src.services.validation_service import ValidationService


def test_negative_population_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProjectService.create_default().floors[1].model_copy(update={"population": -1}).model_validate(
            {"number": 2, "floor_height_m": 3.0, "population": -1}
        )


def test_main_floor_must_be_served() -> None:
    project = ProjectService.create_default()
    group = project.elevator_groups[0]
    with pytest.raises(ValidationError):
        group.__class__(**{**group.model_dump(), "served_floors": [2, 3]})


def test_cross_model_stops_mismatch_is_warning() -> None:
    project = ProjectService.create_default()
    project.elevator_groups[0].elevators[0].stops_count = 3
    messages = ValidationService.validate_project(project)
    assert any(message.code == "STOPS_MISMATCH" for message in messages)
