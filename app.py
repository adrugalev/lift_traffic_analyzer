"""Стартовая страница Lift Traffic Analyzer."""

from __future__ import annotations

from random import SystemRandom

import streamlit as st

from src.services.project_service import ProjectService
from src.ui import configure_page, ensure_session, update_project


configure_page("Lift Traffic Analyzer")
project = ensure_session()

st.markdown(
    """
    <style>
    .st-key-local_test_data_trigger button,
    .st-key-local_test_data_trigger button:hover,
    .st-key-local_test_data_trigger button:focus,
    .st-key-local_test_data_trigger button:active {
        min-height: auto !important;
        height: auto !important;
        padding: 0 !important;
        border: 0 !important;
        border-radius: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
        color: rgba(49, 51, 63, 0.6) !important;
        cursor: default !important;
        outline: none !important;
        margin-right: 0.25rem !important;
    }
    .st-key-local_test_data_trigger button p {
        color: inherit !important;
        font-size: 0.875rem !important;
        font-weight: 400 !important;
        line-height: 1.6 !important;
        white-space: nowrap !important;
    }
    .st-key-local_subtitle {
        margin-top: -0.75rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("Lift Traffic Analyzer")
with st.container(
    key="local_subtitle",
    horizontal=True,
    vertical_alignment="center",
    gap=None,
):
    local_clicked = st.button(
        "Локальный",
        key="local_test_data_trigger",
        type="tertiary",
    )
    st.caption("расчёт и симуляция пассажиропотока лифтовых групп")

if local_clicked:
    click_count = st.session_state.get("local_test_data_click_count", 0) + 1
    if click_count >= 4:
        project_queue = list(st.session_state.get("test_project_queue", []))
        if not project_queue:
            project_queue = list(ProjectService.test_project_keys())
            SystemRandom().shuffle(project_queue)
            previous_key = st.session_state.get("last_test_project_key")
            if (
                previous_key is not None
                and len(project_queue) > 1
                and project_queue[0] == previous_key
            ):
                project_queue[0], project_queue[1] = (
                    project_queue[1],
                    project_queue[0],
                )
        project_key = project_queue.pop(0)
        test_project = ProjectService.create_test_project(project_key=project_key)
        elevator_count = test_project.elevator_groups[0].elevator_count
        update_project(test_project)
        st.session_state.test_project_queue = project_queue
        st.session_state.last_test_project_key = project_key
        st.session_state.local_test_data_click_count = 0
        st.session_state.test_data_loaded_notice = (
            f"Загружен проект «{test_project.metadata.name}»: "
            f"{len(test_project.floors)} этажей, "
            f"{test_project.population} человек, {elevator_count} лифтов."
        )
        st.rerun()
    st.session_state.local_test_data_click_count = click_count

if notice := st.session_state.pop("test_data_loaded_notice", None):
    st.success(notice)

columns = st.columns(4)
columns[0].metric(
    "Проект",
    project.metadata.name,
    help="Название текущего проекта, данные которого используются во всех разделах.",
)
columns[1].metric(
    "Этажи",
    len(project.floors),
    help="Общее количество надземных и подземных этажей в таблице проекта.",
)
columns[2].metric(
    "Население",
    project.population,
    help="Суммарное население с учётом сохранённого коэффициента заселённости.",
)
columns[3].metric(
    "Лифтовые группы",
    len(project.elevator_groups),
    help="Количество сохранённых лифтовых групп в текущем проекте.",
)
