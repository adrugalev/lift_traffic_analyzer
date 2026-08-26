"""Комплексная валидация исходных данных инженерным языком."""

from __future__ import annotations

from src.models.project import Project
from src.models.results import DiagnosticMessage, MessageSeverity


class ValidationService:
    """Выполняет межмодельные проверки, не покрываемые Pydantic."""

    @staticmethod
    def validate_project(project: Project) -> list[DiagnosticMessage]:
        """Возвращает ошибки, предупреждения и информационные сообщения."""

        messages: list[DiagnosticMessage] = []
        if not project.floors:
            messages.append(
                DiagnosticMessage(
                    severity=MessageSeverity.ERROR,
                    code="NO_FLOORS",
                    text="Добавьте хотя бы один этаж.",
                    field_path="floors",
                )
            )
        if project.population <= 0:
            messages.append(
                DiagnosticMessage(
                    severity=MessageSeverity.ERROR,
                    code="ZERO_POPULATION",
                    text="Суммарное население обслуживаемых этажей должно быть больше нуля.",
                    field_path="floors.population",
                )
            )
        main_floors = [
            floor for floor in project.floors if floor.is_main_entrance
        ]
        if len(main_floors) != 1:
            messages.append(
                DiagnosticMessage(
                    severity=MessageSeverity.ERROR,
                    code="MAIN_FLOOR_COUNT",
                    text=(
                        "В разделе «Этажи» должен быть выбран ровно один "
                        "основной посадочный этаж."
                    ),
                    field_path="floors.is_main_entrance",
                )
            )
        if not project.elevator_groups:
            messages.append(
                DiagnosticMessage(
                    severity=MessageSeverity.ERROR,
                    code="NO_GROUPS",
                    text="Создайте хотя бы одну лифтовую группу.",
                    field_path="elevator_groups",
                )
            )
        floor_numbers = {floor.number for floor in project.floors}
        for group_index, group in enumerate(project.elevator_groups):
            if (
                len(main_floors) == 1
                and group.main_floor != main_floors[0].number
            ):
                messages.append(
                    DiagnosticMessage(
                        severity=MessageSeverity.ERROR,
                        code="MAIN_FLOOR_MISMATCH",
                        text=(
                            f"У группы «{group.name}» основной этаж не совпадает "
                            "с отметкой в разделе «Этажи»."
                        ),
                        field_path=(
                            f"elevator_groups.{group_index}.main_floor"
                        ),
                    )
                )
            missing = set(group.served_floors) - floor_numbers
            if missing:
                messages.append(
                    DiagnosticMessage(
                        severity=MessageSeverity.ERROR,
                        code="UNKNOWN_SERVED_FLOORS",
                        text=f"Группа «{group.name}» ссылается на отсутствующие этажи: {sorted(missing)}.",
                        field_path=f"elevator_groups.{group_index}.served_floors",
                    )
                )
            for elevator_index, elevator in enumerate(group.elevators):
                if elevator.stops_count != len(group.served_floors):
                    messages.append(
                        DiagnosticMessage(
                            severity=MessageSeverity.WARNING,
                            code="STOPS_MISMATCH",
                            text=(
                                f"У лифта «{elevator.name}» указано остановок: {elevator.stops_count}; "
                                f"в зоне группы: {len(group.served_floors)}."
                            ),
                            field_path=f"elevator_groups.{group_index}.elevators.{elevator_index}.stops_count",
                        )
                    )
        if not project.traffic_scenarios:
            messages.append(
                DiagnosticMessage(
                    severity=MessageSeverity.ERROR,
                    code="NO_TRAFFIC_SCENARIO",
                    text="Создайте сценарий пассажиропотока.",
                    field_path="traffic_scenarios",
                )
            )
        return messages

    @staticmethod
    def errors(messages: list[DiagnosticMessage]) -> list[DiagnosticMessage]:
        """Фильтрует блокирующие ошибки."""

        return [message for message in messages if message.severity == MessageSeverity.ERROR]
