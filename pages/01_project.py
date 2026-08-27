"""Страница общих сведений о проекте."""

from __future__ import annotations

import streamlit as st

from src.models.building import BuildingType
from src.services.configuration_service import ConfigurationService
from src.ui import configure_page, ensure_session, enum_index, update_project
from src.utils.traffic_profiles import scenario_for_building


configure_page("Проект")
project = ensure_session()
st.title("1. Проект")

report_authors = [
    str(author)
    for author in ConfigurationService().load("report_authors.yaml").get("report_authors", [])
]
author_options = ["Не выбран", *report_authors]
current_author = (
    project.metadata.calculation_author
    if project.metadata.calculation_author in report_authors
    else "Не выбран"
)

st.subheader("Общие сведения")
with st.form("project_form"):
    left, right = st.columns(2)
    with left:
        name = st.text_input(
            "Название проекта *",
            project.metadata.name,
            help=(
                "Название объекта в интерфейсе и отчётах. Оно также используется "
                "при формировании имён скачиваемых файлов."
            ),
        )
        address = st.text_input(
            "Адрес",
            project.metadata.address,
            help="Адрес проектируемого здания для титульных и общих сведений отчёта.",
        )
        customer = st.text_input(
            "Заказчик",
            project.metadata.customer,
            help="Организация-заказчик, указываемая в общих сведениях отчёта.",
        )
    with right:
        building_options = list(BuildingType)
        building_type = st.selectbox(
            "Тип здания *",
            building_options,
            index=enum_index(building_options, project.building.building_type),
            format_func=lambda value: value.value,
            help=(
                "Определяет нормативные критерии ГОСТ и типовой сценарий "
                "пассажиропотока, предлагаемый приложением."
            ),
        )
        st.text_input(
            "Нормативная база",
            value="ГОСТ 34758-2021",
            disabled=True,
            help=(
                "Стандарт, по формулам и критериям которого выполняется "
                "нормативный аналитический расчёт."
            ),
        )
        calculation_author = st.selectbox(
            "Разработчик отчёта",
            author_options,
            index=author_options.index(current_author),
            help="Специалист, который будет указан разработчиком расчёта в отчёте.",
        )
    submitted = st.form_submit_button(
        "Сохранить сведения",
        type="primary",
        help=(
            "Сохраняет общие сведения. При изменении типа здания автоматически "
            "устанавливается нормативный сценарий «По ГОСТ»."
        ),
    )

if submitted:
    candidate = project.model_copy(deep=True)
    building_type_changed = (
        building_type != project.building.building_type
    )
    candidate.metadata.name = name.strip() or "Новый проект"
    candidate.metadata.address = address
    candidate.metadata.customer = customer
    candidate.metadata.calculation_author = "" if calculation_author == "Не выбран" else calculation_author
    candidate.building.building_type = building_type
    if building_type_changed:
        scenario_index = next(
            index
            for index, item in enumerate(candidate.traffic_scenarios)
            if item.id == candidate.scenario().id
        )
        candidate.traffic_scenarios[scenario_index] = scenario_for_building(
            candidate.scenario(),
            building_type,
        )
    update_project(candidate)
    if building_type_changed:
        st.success(
            "Сведения сохранены. Для выбранного типа здания установлен сценарий "
            f"«{candidate.scenario().name}»."
        )
    else:
        st.success("Сведения сохранены.")

if project.building.building_type == BuildingType.MIXED_USE:
    st.info(
        "Многофункциональные зоны хранятся в модели проекта. Отдельный визуальный "
        "редактор зон пока не реализован."
    )
