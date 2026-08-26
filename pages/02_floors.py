"""Редактор этажей и населения."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.models.floor import Floor
from src.ui import configure_page, ensure_session, update_project
from src.utils.decimal_input import format_decimal
from src.utils.floor_editor import (
    apply_floor_bulk_fill,
    floor_editor_frames_equal,
    normalize_floor_editor_frame,
)
from src.utils.floor_roles import synchronize_main_floor


configure_page("Этажи и население")
project = ensure_session()
st.title("2. Этажи и население")
st.caption(
    "Подземные уровни указывайте отрицательными номерами (например, −1, −2), "
    "отмечайте как «Паркинг» и оставляйте население равным 0. Доля пассажиров "
    "с паркинга задаётся в разделе «4. Пассажиропоток». Выберите ровно один "
    "основной посадочный этаж — он будет автоматически назначен всем лифтовым группам."
)


def floors_to_rows(floors: list[Floor]) -> list[dict[str, object]]:
    """Преобразует сохранённые этажи в строки редактора."""

    return [
        {
            "Этаж": floor.number,
            "Метка": floor.label,
            "Отметка, м": floor.elevation_m,
            "Высота, м": floor.floor_height_m,
            "Назначение": floor.purpose,
            "Население": floor.population,
            "Основной посадочный этаж": floor.is_main_entrance,
            "Входной этаж": floor.is_entrance,
            "Паркинг": floor.is_parking,
        }
        for floor in floors
    ]


rows = floors_to_rows(project.floors)
st.session_state.pop("imported_floors", None)

editor_revision = st.session_state.get("floors_editor_revision", 0)
if st.session_state.get("floors_editor_project_id") != project.id:
    st.session_state.pop("floors_editor_pending", None)
    st.session_state.floors_occupancy_percent = (
        project.building.occupancy_percent
    )
    editor_revision += 1
    st.session_state.floors_editor_revision = editor_revision
    st.session_state.floors_editor_project_id = project.id
    editor_frame = pd.DataFrame(rows)
elif "floors_editor_pending" in st.session_state:
    editor_frame = st.session_state.pop("floors_editor_pending")
else:
    editor_frame = st.session_state.get("floors_editor_frame", pd.DataFrame(rows))
st.session_state.setdefault(
    "floors_occupancy_percent",
    project.building.occupancy_percent,
)

if st.button(
    "Добавить этаж",
    help=(
        "Добавляет следующий надземный этаж и автоматически заполняет номер, "
        "метку, высоту, назначение и население по последнему типовому этажу."
    ),
):
    expanded = pd.concat(
        [editor_frame, pd.DataFrame([{}])],
        ignore_index=True,
    )
    try:
        expanded = normalize_floor_editor_frame(expanded, project.floors)
    except Exception as exc:
        st.error(f"Не удалось добавить этаж: {exc}")
    else:
        st.session_state.floors_editor_pending = expanded.copy()
        st.session_state.floors_editor_frame = expanded.copy()
        st.session_state.floors_editor_revision = editor_revision + 1
        st.rerun()

display_frame = editor_frame.copy()
display_frame["Высота, м"] = display_frame["Высота, м"].map(format_decimal)

edited = st.data_editor(
    display_frame,
    num_rows="fixed",
    width="stretch",
    height="auto",
    row_height=26,
    hide_index=True,
    disabled=["Отметка, м"],
    column_config={
        "Этаж": st.column_config.NumberColumn(
            required=True,
            step=1,
            width=65,
            help=(
                "Номер уровня. Для подземных этажей используйте отрицательные "
                "значения: −1, −2 и далее."
            ),
        ),
        "Метка": st.column_config.TextColumn(
            width=75,
            help="Краткое обозначение этажа для интерфейса и отчёта, например «Вход» или «P1».",
        ),
        "Отметка, м": st.column_config.NumberColumn(
            format="%.2f",
            width=90,
            help=(
                "Рассчитывается автоматически от основного посадочного этажа "
                "по введённым высотам этажей."
            ),
        ),
        "Высота, м": st.column_config.TextColumn(
            required=True,
            width=85,
            help=(
                "Высота этажа. Используется как резервное значение расстояния "
                "между уровнями и при предварительных оценках движения. "
                "Дробную часть можно отделять запятой или точкой."
            ),
        ),
        "Назначение": st.column_config.TextColumn(
            width=120,
            help=(
                "Функциональное назначение уровня для исходных данных и отчёта, "
                "например жилой этаж, входная группа или паркинг."
            ),
        ),
        "Население": st.column_config.NumberColumn(
            required=True,
            min_value=0,
            step=1,
            width=90,
            help=(
                "Полное расчётное население этажа до применения общего "
                "коэффициента заселённости."
            ),
        ),
        "Основной посадочный этаж": st.column_config.CheckboxColumn(
            help=(
                "Этаж основного входа, от которого рассчитываются входящие "
                "и исходящие поездки. Выберите ровно один этаж."
            ),
            width=135,
        ),
        "Входной этаж": st.column_config.CheckboxColumn(
            width=100,
            help=(
                "Уровень, через который пассажиры могут входить в здание. "
                "Основной посадочный этаж автоматически также считается входным."
            ),
        ),
        "Паркинг": st.column_config.CheckboxColumn(
            "Паркинг",
            help="Подземный парковочный этаж без постоянного населения.",
            width=90,
        ),
    },
    key=f"floors_editor_{editor_revision}",
)
try:
    normalized_edited = normalize_floor_editor_frame(edited, project.floors)
except Exception as exc:
    normalized_edited = edited.copy()
    st.error(f"Проверьте таблицу этажей: {exc}")
else:
    if not floor_editor_frames_equal(normalized_edited, editor_frame):
        st.session_state.floors_editor_pending = normalized_edited.copy()
        st.session_state.floors_editor_frame = normalized_edited.copy()
        st.session_state.floors_editor_revision = editor_revision + 1
        st.rerun()
edited = normalized_edited
st.session_state.floors_editor_frame = edited.copy()

st.caption(
    "Отметки пересчитываются автоматически по высотам этажей. Новая строка "
    "получает следующий номер, метку, назначение, высоту и население типового этажа."
)

occupancy_percent = st.slider(
    "Коэффициент заселённости, %",
    min_value=0,
    max_value=100,
    step=1,
    format="%d%%",
    key="floors_occupancy_percent",
    help=(
        "Доля фактически заселённого населения относительно полных значений "
        "в таблице. Суммарное население и расчётный поток пересчитываются сразу."
    ),
)
st.caption(
    "Итоговое население рассчитывается как сумма значений «Население» "
    "в таблице × коэффициент заселённости. При 100% используются полные значения."
)

bulk_fill_notice = st.session_state.pop("floors_bulk_fill_applied", None)
if bulk_fill_notice is not None:
    added_count = (
        int(bulk_fill_notice.get("added_count", 0))
        if isinstance(bulk_fill_notice, dict)
        else 0
    )
    added_text = f" Добавлено новых этажей: {added_count}." if added_count else ""
    st.success(
        "Массовое заполнение применено."
        + added_text
        + " Проверьте таблицу и сохраните этажи."
    )
if st.session_state.pop("floors_saved_notice", False):
    st.success("Этажи сохранены.")

with st.expander("Массовое заполнение и расчёт населения"):
    c1, c2, c3, c4 = st.columns(4)
    start_floor = c1.number_input(
        "С этажа",
        value=min(f.number for f in project.floors),
        step=1,
        help="Первый этаж диапазона, к которому применяется массовое заполнение.",
    )
    end_floor = c2.number_input(
        "По этаж",
        value=max(f.number for f in project.floors),
        step=1,
        help="Последний этаж диапазона, к которому применяется массовое заполнение.",
    )
    typical_height = c3.number_input(
        "Высота, м",
        min_value=0.01,
        value=3.0,
        step=0.1,
        help="Высота, которая будет записана во все этажи выбранного диапазона.",
    )
    typical_population = c4.number_input(
        "Население",
        min_value=0,
        value=20,
        step=1,
        help="Население, которое будет записано в каждый этаж выбранного диапазона.",
    )
    if st.button(
        "Применить массовое заполнение",
        help=(
            "Переносит заданные высоту и население в таблицу. Изменения необходимо "
            "проверить и затем сохранить отдельной кнопкой."
        ),
    ):
        try:
            bulk_filled, added_count = apply_floor_bulk_fill(
                edited,
                project.floors,
                int(start_floor),
                int(end_floor),
                float(typical_height),
                int(typical_population),
            )
        except Exception as exc:
            st.error(f"Не удалось применить массовое заполнение: {exc}")
        else:
            st.session_state.floors_editor_pending = bulk_filled.copy()
            st.session_state.floors_editor_frame = bulk_filled.copy()
            st.session_state.floors_editor_revision = editor_revision + 1
            st.session_state.floors_bulk_fill_applied = {
                "added_count": added_count
            }
            st.rerun()

if st.button(
    "Сохранить этажи",
    type="primary",
    help=(
        "Сохраняет таблицу и коэффициент заселённости, синхронизирует основной "
        "посадочный этаж и перечень остановок лифтовых групп."
    ),
):
    try:
        candidate = project.model_copy(deep=True)
        group_ids = [group.id for group in candidate.elevator_groups]
        candidate.floors = [
            Floor(
                number=int(row["Этаж"]),
                label=str(row.get("Метка") or row["Этаж"]),
                elevation_m=float(row.get("Отметка, м") or 0.0),
                floor_height_m=float(row.get("Высота, м") or 0.0),
                purpose=str(row.get("Назначение") or "Типовой этаж"),
                population=int(row.get("Население") or 0),
                served_by_group_ids=group_ids,
                is_main_entrance=bool(
                    row.get("Основной посадочный этаж")
                ),
                is_entrance=bool(row.get("Входной этаж")),
                is_parking=bool(row.get("Паркинг")),
                is_express=False,
            )
            for row in edited.to_dict("records")
        ]
        floor_numbers = sorted(floor.number for floor in candidate.floors)
        for group in candidate.elevator_groups:
            group.served_floors = floor_numbers.copy()
            for elevator in group.elevators:
                elevator.stops_count = len(floor_numbers)
                elevator.travel_height_m = (
                    max(floor.elevation_m for floor in candidate.floors)
                    - min(floor.elevation_m for floor in candidate.floors)
                )
        candidate.building.occupancy_percent = int(occupancy_percent)
        candidate = synchronize_main_floor(candidate)
        update_project(candidate)
        st.session_state.floors_editor_pending = pd.DataFrame(
            floors_to_rows(candidate.floors)
        )
        st.session_state.floors_editor_frame = st.session_state.floors_editor_pending.copy()
        st.session_state.floors_editor_revision = editor_revision + 1
        st.session_state.floors_saved_notice = True
        st.rerun()
    except Exception as exc:
        st.error(f"Не удалось сохранить этажи: {exc}")

table_population = (
    int(pd.to_numeric(edited["Население"], errors="coerce").fillna(0).sum())
    if "Население" in edited
    else 0
)
live_population = round(table_population * occupancy_percent / 100)
st.metric(
    "Суммарное население",
    live_population,
    help=(
        "Сумма населения всех этажей, умноженная на текущий коэффициент "
        "заселённости. Это значение используется при расчёте пассажиропотока."
    ),
)
st.caption(
    "Пересчитывается автоматически по текущим данным таблицы и выбранному "
    "коэффициенту заселённости."
)
