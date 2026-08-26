"""Редактор лифтовых групп и неоднородных кабин."""

from __future__ import annotations

from uuid import uuid4

import pandas as pd
import streamlit as st

from src.models.elevator import ControlType, DoorOpeningType, Elevator, ElevatorGroup
from src.services.elevator_service import clone_last_elevator
from src.ui import configure_page, ensure_session, update_project


def _elevators_from_editor(
    rows: list[dict[str, object]],
    original_elevators: list[Elevator],
) -> list[Elevator]:
    """Преобразует строки редактора в модели, сохраняя или создавая идентификаторы."""

    elevators: list[Elevator] = []
    for row_index, row in enumerate(rows):
        template = original_elevators[min(row_index, len(original_elevators) - 1)]
        elevator_id = (
            template.id if row_index < len(original_elevators) else str(uuid4())
        )
        elevators.append(
            Elevator(
                **{
                    **template.model_dump(),
                    "id": elevator_id,
                    "name": str(row["Наименование"]),
                    "capacity_kg": float(row["Г/п, кг"]),
                    "nominal_passengers": int(row["Номинал, пасс."]),
                    "load_factor": float(row["Заполнение, %"]) / 100.0,
                    "speed_mps": float(row["Скорость, м/с"]),
                    "acceleration_mps2": float(row["Ускорение, м/с²"]),
                    "deceleration_mps2": float(row["Замедление, м/с²"]),
                    "jerk_mps3": float(row["Рывок, м/с³"]),
                    "door_width_m": float(row["Дверь, м"]),
                    "door_opening_type": DoorOpeningType(str(row["Тип дверей"])),
                    "door_open_time_s": float(row["Открытие, с"]),
                    "door_close_time_s": float(row["Закрытие, с"]),
                    "pre_open_time_s": float(row["Предв. открытие, с"]),
                    "door_dwell_time_s": float(row["Задержка, с"]),
                    "start_brake_allowance_s": float(row["Задержка пуска, с"]),
                    "boarding_time_per_passenger_s": float(row["Посадка, с/пасс."]),
                    "alighting_time_per_passenger_s": float(row["Высадка, с/пасс."]),
                    "stops_count": int(row["Остановки"]),
                    "accessible": bool(row["МГН"]),
                }
            )
        )
    return elevators


configure_page("Лифтовые группы")
project = ensure_session()
st.title("3. Лифтовые группы")

if not project.elevator_groups:
    project.elevator_groups = [ElevatorGroup()]

group_names = [group.name for group in project.elevator_groups]
selected_name = st.selectbox(
    "Редактируемая группа",
    group_names,
    help="Выберите лифтовую группу, параметры и состав которой требуется изменить.",
)
selected_index = group_names.index(selected_name)
group = project.elevator_groups[selected_index]

actions = st.columns(3)
if actions[0].button(
    "Добавить группу",
    help="Создаёт новую группу, первоначально обслуживающую все этажи проекта.",
):
    candidate = project.model_copy(deep=True)
    floors = [floor.number for floor in candidate.floors]
    candidate.elevator_groups.append(
        ElevatorGroup(
            name=f"Группа {chr(65 + len(candidate.elevator_groups))}",
            main_floor=floors[0],
            served_floors=floors,
        )
    )
    update_project(candidate)
    st.rerun()
if actions[1].button(
    "Копировать группу",
    help="Создаёт независимую копию выбранной группы для разработки другого варианта.",
):
    candidate = project.model_copy(deep=True)
    copy = group.model_copy(deep=True)
    copy.id = f"{copy.id}-copy"
    copy.name = f"{copy.name} — копия"
    for index, elevator in enumerate(copy.elevators):
        elevator.id = f"{elevator.id}-copy-{index}"
    copy.control_type = ControlType.GROUP_COLLECTIVE
    candidate.elevator_groups.append(copy)
    update_project(candidate)
    st.rerun()
if actions[2].button(
    "Удалить группу",
    disabled=len(project.elevator_groups) == 1,
    help=(
        "Удаляет выбранную группу. Единственную оставшуюся группу удалить нельзя."
    ),
):
    candidate = project.model_copy(deep=True)
    del candidate.elevator_groups[selected_index]
    update_project(candidate)
    st.rerun()

st.subheader("Параметры группы")
left, right = st.columns(2)
with left:
    group_name = st.text_input(
        "Название группы",
        group.name,
        help="Наименование группы в расчётах, сравнении вариантов и отчётах.",
    )
with right:
    served_floors = st.multiselect(
        "Обслуживаемые этажи",
        [floor.number for floor in project.floors],
        default=[floor for floor in group.served_floors if floor in {item.number for item in project.floors}],
        help=(
            "Этажи, между которыми перемещаются лифты группы. Основной посадочный "
            "этаж проекта добавляется автоматически."
        ),
    )

st.subheader("Лифты группы")
elevator_rows = [
    {
        "Наименование": elevator.name,
        "Г/п, кг": elevator.capacity_kg,
        "Номинал, пасс.": elevator.nominal_passengers,
        "Заполнение, %": round(elevator.load_factor * 100),
        "Скорость, м/с": elevator.speed_mps,
        "Ускорение, м/с²": elevator.acceleration_mps2,
        "Замедление, м/с²": elevator.deceleration_mps2,
        "Рывок, м/с³": elevator.jerk_mps3,
        "Дверь, м": elevator.door_width_m,
        "Тип дверей": elevator.door_opening_type.value,
        "Открытие, с": elevator.door_open_time_s,
        "Закрытие, с": elevator.door_close_time_s,
        "Предв. открытие, с": elevator.pre_open_time_s,
        "Задержка, с": elevator.door_dwell_time_s,
        "Задержка пуска, с": elevator.start_brake_allowance_s,
        "Посадка, с/пасс.": elevator.boarding_time_per_passenger_s,
        "Высадка, с/пасс.": elevator.alighting_time_per_passenger_s,
        "Остановки": elevator.stops_count,
        "МГН": elevator.accessible,
    }
    for elevator in group.elevators
]
edited = st.data_editor(
    pd.DataFrame(elevator_rows),
    num_rows="dynamic",
    use_container_width=True,
    height=max(150, min(420, 32 * (len(elevator_rows) + 2))),
    row_height=30,
    hide_index=True,
    column_config={
        "Наименование": st.column_config.TextColumn(
            "Лифт",
            width=95,
            help="Наименование лифта",
        ),
        "Г/п, кг": st.column_config.NumberColumn(
            "Г/п, кг",
            width=72,
            min_value=1.0,
            help=(
                "Номинальная грузоподъёмность. В расчёте по ГОСТ номинальная "
                "вместимость проверяется как грузоподъёмность, делённая на 75 кг."
            ),
        ),
        "Номинал, пасс.": st.column_config.NumberColumn(
            "Пасс.",
            width=62,
            help="Номинальная вместимость, пассажиров",
            min_value=1,
            step=1,
        ),
        "Заполнение, %": st.column_config.NumberColumn(
            "Зап., %",
            width=72,
            help="Расчётное заполнение кабины",
            min_value=1,
            max_value=100,
            step=1,
            format="%d%%",
        ),
        "Скорость, м/с": st.column_config.NumberColumn(
            "v, м/с",
            width=70,
            help="Номинальная скорость",
            min_value=0.01,
            format="%.2f",
        ),
        "Ускорение, м/с²": st.column_config.NumberColumn(
            "a, м/с²",
            width=70,
            help="Ускорение",
            min_value=0.01,
        ),
        "Замедление, м/с²": st.column_config.NumberColumn(
            "b, м/с²",
            width=70,
            help="Замедление",
            min_value=0.01,
        ),
        "Рывок, м/с³": st.column_config.NumberColumn(
            "j, м/с³",
            width=70,
            help=(
                "Ограничение темпа изменения ускорения, характеризующее плавность "
                "хода. Учитывается в S-образном профиле межэтажного движения."
            ),
            min_value=0.0,
        ),
        "Дверь, м": st.column_config.NumberColumn(
            "Дверь, м",
            width=74,
            help="Ширина дверного проёма",
            min_value=0.01,
        ),
        "Тип дверей": st.column_config.SelectboxColumn(
            "Тип дверей",
            width=115,
            options=[item.value for item in DoorOpeningType],
            help="Конструктивный тип открывания дверей кабины.",
        ),
        "Открытие, с": st.column_config.NumberColumn(
            "Откр., с",
            width=72,
            help="Время открывания дверей",
            min_value=0.0,
        ),
        "Закрытие, с": st.column_config.NumberColumn(
            "Закр., с",
            width=72,
            help="Время закрывания дверей",
            min_value=0.0,
        ),
        "Предв. открытие, с": st.column_config.NumberColumn(
            "Пред. откр., с",
            width=88,
            help="Время предварительного открывания дверей",
            min_value=0.0,
            format="%.2f",
        ),
        "Задержка, с": st.column_config.NumberColumn(
            "Стоянка, с",
            width=80,
            help="Время стоянки с открытыми дверями",
            min_value=0.0,
        ),
        "Задержка пуска, с": st.column_config.NumberColumn(
            "Пуск, с",
            width=70,
            help="Поправка на пуск и торможение",
            min_value=0.0,
            format="%.2f",
        ),
        "Посадка, с/пасс.": st.column_config.NumberColumn(
            "Посадка, с",
            width=84,
            help="Время посадки одного пассажира",
            min_value=0.0,
        ),
        "Высадка, с/пасс.": st.column_config.NumberColumn(
            "Высадка, с",
            width=84,
            help="Время высадки одного пассажира",
            min_value=0.0,
        ),
        "Остановки": st.column_config.NumberColumn(
            "Ост.",
            width=55,
            help=(
                "Число обслуживаемых остановок лифта. Должно совпадать с количеством "
                "этажей, выбранных для группы."
            ),
            min_value=1,
            step=1,
        ),
        "МГН": st.column_config.CheckboxColumn(
            "МГН",
            width=55,
            help=(
                "Признак доступности для маломобильных групп населения. Отражается "
                "в модели и отчёте, но не изменяет текущие формулы пассажиропотока."
            ),
        ),
    },
)

button_columns = st.columns([1, 1, 4])
add_elevator_clicked = button_columns[0].button(
    "Добавить лифт",
    help=(
        "Добавляет в группу новый лифт, полностью копируя параметры последнего "
        "лифта в таблице."
    ),
)
save_group_clicked = button_columns[1].button(
    "Сохранить группу",
    type="primary",
    help=(
        "Сохраняет название, обслуживаемые этажи и параметры всех лифтов "
        "выбранной группы."
    ),
)

if add_elevator_clicked or save_group_clicked:
    try:
        if not served_floors:
            raise ValueError("Выберите хотя бы один обслуживаемый этаж.")
        if edited.empty:
            raise ValueError("Добавьте хотя бы один лифт.")
        candidate = project.model_copy(deep=True)
        original = candidate.elevator_groups[selected_index]
        elevators = _elevators_from_editor(
            edited.to_dict("records"),
            original.elevators,
        )
        if add_elevator_clicked:
            elevators.append(clone_last_elevator(elevators))
        candidate.elevator_groups[selected_index] = ElevatorGroup(
            **{
                **original.model_dump(),
                "name": group_name,
                "control_type": ControlType.GROUP_COLLECTIVE,
                "served_floors": sorted(
                    {int(value) for value in served_floors}
                    | {original.main_floor}
                ),
                "express_zone": False,
                "elevators": elevators,
            }
        )
        update_project(candidate)
        if add_elevator_clicked:
            st.rerun()
        st.success("Лифтовая группа сохранена.")
    except Exception as exc:
        st.error(f"Не удалось сохранить группу: {exc}")
