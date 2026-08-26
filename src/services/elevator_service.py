"""Операции над составом лифтовой группы."""

from __future__ import annotations

import re
from uuid import uuid4

from src.models.elevator import Elevator


def _next_elevator_name(last_name: str, existing_names: set[str]) -> str:
    """Формирует следующее уникальное имя на основе имени последнего лифта."""

    match = re.match(r"^(.*?)(\d+)$", last_name.strip())
    if match:
        prefix, number = match.groups()
        next_number = int(number) + 1
        candidate = f"{prefix}{next_number}"
        while candidate in existing_names:
            next_number += 1
            candidate = f"{prefix}{next_number}"
        return candidate

    candidate = f"{last_name} — копия"
    copy_number = 2
    while candidate in existing_names:
        candidate = f"{last_name} — копия {copy_number}"
        copy_number += 1
    return candidate


def clone_last_elevator(elevators: list[Elevator]) -> Elevator:
    """Клонирует последний лифт, заменяя только идентификатор и имя."""

    if not elevators:
        raise ValueError("Невозможно добавить лифт в пустую группу.")

    clone = elevators[-1].model_copy(deep=True)
    clone.id = str(uuid4())
    clone.name = _next_elevator_name(
        clone.name,
        {elevator.name for elevator in elevators},
    )
    return clone
