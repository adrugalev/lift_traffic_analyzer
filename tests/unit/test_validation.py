"""Unit-тесты валидации проекта и OD-матрицы."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models.traffic import TrafficScenario
from src.services.project_service import ProjectService
from src.services.validation_service import ValidationService


def test_negative_population_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProjectService.create_default().floors[1].model_copy(update={"population": -1}).model_validate(
            {"number": 2, "floor_height_m": 3.0, "population": -1}
        )


def test_od_matrix_diagonal_must_be_zero() -> None:
    with pytest.raises(ValidationError):
        TrafficScenario(
            incoming_share=1.0,
            outgoing_share=0.0,
            interfloor_share=0.0,
            od_floor_numbers=[1, 2],
            od_matrix=[[1.0, 0.0], [1.0, 0.0]],
        )


def test_od_matrix_rows_must_sum_to_one() -> None:
    with pytest.raises(ValidationError):
        TrafficScenario(
            incoming_share=1.0,
            outgoing_share=0.0,
            interfloor_share=0.0,
            od_floor_numbers=[1, 2],
            od_matrix=[[0.0, 0.5], [1.0, 0.0]],
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

