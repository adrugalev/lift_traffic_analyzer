"""Табличный редактор лифтов."""

from __future__ import annotations

from uuid import uuid4

import pandas as pd
import streamlit as st

from src.models.elevator import DoorOpeningType, Elevator, ElevatorGroup
from src.ui import configure_page, ensure_session, update_project
from src.utils.decimal_input import format_decimal
from src.utils.elevator_editor import (
    ELEVATOR_DECIMAL_COLUMNS,
    elevator_editor_frames_equal,
    elevator_to_editor_row,
    normalize_elevator_editor_frame,
)
from src.utils.series_fill import continue_copied_series


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


configure_page("Лифты")
project = ensure_session()
st.title("3. Лифты")

if not project.elevator_groups:
    project.elevator_groups = [ElevatorGroup()]

existing_elevators = [
    elevator
    for existing_group in project.elevator_groups
    for elevator in existing_group.elevators
]
project_elevator_rows = [
    elevator_to_editor_row(elevator) for elevator in existing_elevators
]
stops_count = len(project.floors)
editor_revision = int(st.session_state.get("elevators_editor_revision", 0))
if st.session_state.get("elevators_editor_project_id") != project.id:
    st.session_state.pop("elevators_editor_pending", None)
    st.session_state.elevators_editor_revision = editor_revision + 1
    st.session_state.elevators_editor_project_id = project.id
    editor_revision += 1
    editor_frame = pd.DataFrame(project_elevator_rows)
elif "elevators_editor_pending" in st.session_state:
    editor_frame = st.session_state.pop("elevators_editor_pending")
else:
    editor_frame = st.session_state.get(
        "elevators_editor_frame", pd.DataFrame(project_elevator_rows)
    )

if st.button(
    "Добавить лифт",
    help=(
        "Добавляет новую строку, продолжает нумерацию наименования и копирует "
        "параметры предыдущего лифта."
    ),
):
    expanded = pd.concat([editor_frame, pd.DataFrame([{}])], ignore_index=True)
    try:
        expanded = normalize_elevator_editor_frame(
            expanded, existing_elevators, stops_count
        )
    except Exception as exc:
        st.error(f"Не удалось добавить лифт: {exc}")
    else:
        st.session_state.elevators_editor_pending = expanded.copy()
        st.session_state.elevators_editor_frame = expanded.copy()
        st.session_state.elevators_editor_revision = editor_revision + 1
        st.rerun()

display_frame = editor_frame.copy()
for decimal_column in ELEVATOR_DECIMAL_COLUMNS:
    display_frame[decimal_column] = display_frame[decimal_column].map(format_decimal)

edited = st.data_editor(
    display_frame,
    key=f"elevators_editor_{editor_revision}",
    num_rows="fixed",
    width="stretch",
    height="auto",
    row_height=26,
    hide_index=True,
    disabled=["Остановки"],
    column_config={
        "Наименование": st.column_config.TextColumn(
            "Лифт",
            width=95,
            help="Наименование лифта",
        ),
        "Г/п, кг": st.column_config.TextColumn(
            "Г/п, кг",
            width=72,
            help=(
                "Номинальная грузоподъёмность. В расчёте по ГОСТ номинальная "
                "вместимость проверяется как грузоподъёмность, делённая на 75 кг. "
                "Допустимы запятая и точка."
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
        "Скорость, м/с": st.column_config.TextColumn(
            "v, м/с",
            width=70,
            help="Номинальная скорость. Допустимы запятая и точка.",
        ),
        "Ускорение, м/с²": st.column_config.TextColumn(
            "a, м/с²",
            width=70,
            help="Ускорение. Допустимы запятая и точка.",
        ),
        "Замедление, м/с²": st.column_config.TextColumn(
            "b, м/с²",
            width=70,
            help="Замедление. Допустимы запятая и точка.",
        ),
        "Рывок, м/с³": st.column_config.TextColumn(
            "j, м/с³",
            width=70,
            help=(
                "Ограничение темпа изменения ускорения, характеризующее плавность "
                "хода. Учитывается в S-образном профиле межэтажного движения. "
                "Допустимы запятая и точка."
            ),
        ),
        "Дверь, м": st.column_config.TextColumn(
            "Дверь, м",
            width=74,
            help="Ширина дверного проёма. Допустимы запятая и точка.",
        ),
        "Тип дверей": st.column_config.SelectboxColumn(
            "Тип дверей",
            width=115,
            options=[item.value for item in DoorOpeningType],
            help="Конструктивный тип открывания дверей кабины.",
        ),
        "Открытие, с": st.column_config.TextColumn(
            "Откр., с",
            width=72,
            help="Время открывания дверей. Допустимы запятая и точка.",
        ),
        "Закрытие, с": st.column_config.TextColumn(
            "Закр., с",
            width=72,
            help="Время закрывания дверей. Допустимы запятая и точка.",
        ),
        "Предв. открытие, с": st.column_config.TextColumn(
            "Пред. откр., с",
            width=88,
            help="Время предварительного открывания дверей. Допустимы запятая и точка.",
        ),
        "Задержка, с": st.column_config.TextColumn(
            "Стоянка, с",
            width=80,
            help="Время стоянки с открытыми дверями. Допустимы запятая и точка.",
        ),
        "Задержка пуска, с": st.column_config.TextColumn(
            "Пуск, с",
            width=70,
            help="Поправка на пуск и торможение. Допустимы запятая и точка.",
        ),
        "Посадка, с/пасс.": st.column_config.TextColumn(
            "Посадка, с",
            width=84,
            help="Время посадки одного пассажира. Допустимы запятая и точка.",
        ),
        "Высадка, с/пасс.": st.column_config.TextColumn(
            "Высадка, с",
            width=84,
            help="Время высадки одного пассажира. Допустимы запятая и точка.",
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
try:
    normalized_edited = normalize_elevator_editor_frame(
        edited, existing_elevators, stops_count
    )
except Exception as exc:
    normalized_edited = edited.copy()
    st.error(f"Проверьте таблицу лифтов: {exc}")
else:
    previous_editor_frame = st.session_state.get(
        "elevators_editor_previous", editor_frame
    )
    normalized_edited, series_continued = continue_copied_series(
        previous_editor_frame, normalized_edited
    )
    if series_continued:
        st.session_state.elevators_editor_pending = normalized_edited.copy()
        st.session_state.elevators_editor_frame = normalized_edited.copy()
        st.session_state.elevators_editor_previous = normalized_edited.copy()
        st.session_state.elevators_editor_revision = editor_revision + 1
        st.rerun()
    if not elevator_editor_frames_equal(normalized_edited, editor_frame):
        st.session_state.elevators_editor_pending = normalized_edited.copy()
        st.session_state.elevators_editor_frame = normalized_edited.copy()
        st.session_state.elevators_editor_revision = editor_revision + 1
        st.rerun()
edited = normalized_edited
st.session_state.elevators_editor_frame = edited.copy()
st.session_state.elevators_editor_previous = edited.copy()

st.caption(
    "Новая строка продолжает нумерацию и получает параметры предыдущего лифта. "
    "Количество остановок синхронизируется с таблицей этажей автоматически."
)

if st.session_state.pop("elevators_saved_notice", False):
    st.success("Лифты сохранены.")

with st.expander("Массовое заполнение параметров лифтов"):
    template_name = st.selectbox(
        "Лифт-образец",
        edited["Наименование"].astype(str).tolist(),
        help="Параметры выбранного лифта будут перенесены во все строки.",
    )
    if st.button(
        "Применить параметры ко всем лифтам",
        help="Копирует все параметры, кроме наименований, во все строки таблицы.",
    ):
        template_row = edited.loc[
            edited["Наименование"].astype(str) == template_name
        ].iloc[0]
        for column in edited.columns:
            if column not in {"Наименование", "Остановки"}:
                edited[column] = template_row[column]
        st.session_state.elevators_editor_pending = edited.copy()
        st.session_state.elevators_editor_frame = edited.copy()
        st.session_state.elevators_editor_revision = editor_revision + 1
        st.rerun()

if st.button(
    "Сохранить лифты",
    type="primary",
    help=(
        "Сохраняет таблицу. Все лифты автоматически назначаются на все этажи "
        "проекта."
    ),
):
    try:
        if edited.empty:
            raise ValueError("Добавьте хотя бы один лифт.")
        candidate = project.model_copy(deep=True)
        original = candidate.elevator_groups[0]
        elevators = _elevators_from_editor(
            edited.to_dict("records"),
            existing_elevators,
        )
        floor_numbers = sorted(floor.number for floor in candidate.floors)
        main_floor = next(
            (
                floor.number
                for floor in candidate.floors
                if floor.is_main_entrance
            ),
            floor_numbers[0],
        )
        travel_height = (
            max(floor.elevation_m for floor in candidate.floors)
            - min(floor.elevation_m for floor in candidate.floors)
        )
        for elevator in elevators:
            elevator.stops_count = len(floor_numbers)
            elevator.travel_height_m = travel_height
        unified_group = ElevatorGroup(
            **{
                **original.model_dump(),
                "name": "Лифты",
                "service_zone_name": "Все этажи",
                "main_floor": main_floor,
                "served_floors": floor_numbers,
                "express_zone": False,
                "elevators": elevators,
            }
        )
        candidate.elevator_groups = [unified_group]
        for floor in candidate.floors:
            floor.served_by_group_ids = [unified_group.id]
        update_project(candidate)
        st.session_state.elevators_editor_pending = pd.DataFrame(
            [elevator_to_editor_row(elevator) for elevator in elevators]
        )
        st.session_state.elevators_editor_frame = (
            st.session_state.elevators_editor_pending.copy()
        )
        st.session_state.elevators_editor_revision = editor_revision + 1
        st.session_state.elevators_saved_notice = True
        st.rerun()
    except Exception as exc:
        st.error(f"Не удалось сохранить лифты: {exc}")
