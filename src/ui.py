"""Общие функции тонкого слоя Streamlit."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import streamlit as st

from src.models.project import Project
from src.models.results import DiagnosticMessage, MessageSeverity
from src.services.project_service import ProjectService


NAVIGATION = (
    ("app.py", "Главная"),
    ("pages/01_project.py", "1. Проект"),
    ("pages/02_floors.py", "2. Этажи"),
    ("pages/03_elevator_groups.py", "3. Лифты"),
    ("pages/04_traffic.py", "4. Пассажиропоток"),
    ("pages/05_analytic_calculation.py", "5. Расчёт и отчёт"),
    ("pages/06_simulation.py", "6. Симуляция"),
    ("pages/07_comparison.py", "7. Сравнение вариантов"),
    ("pages/09_reference_data.py", "8. Справочники и формулы"),
    ("pages/10_settings.py", "9. О программе"),
)

ADDITIONAL_NAVIGATION = {
    "pages/06_simulation.py",
    "pages/07_comparison.py",
}

GENERATED_REPORT_KEYS = (
    "report_docx",
    "report_pdf",
    "report_xlsx",
    "gost_report_docx",
    "gost_report_pdf",
)


def invalidate_generated_reports() -> None:
    """Удаляет отчёты, которые могли устареть после изменения исходных данных."""

    for key in GENERATED_REPORT_KEYS:
        st.session_state.pop(key, None)


def render_navigation() -> None:
    """Показывает единое русскоязычное меню приложения."""

    with st.sidebar:
        st.caption("РАЗДЕЛЫ")
        for page, label in NAVIGATION[:6]:
            st.page_link(page, label=label, use_container_width=True)
        show_additional = st.checkbox(
            "Показать дополнительные разделы",
            key="show_additional_sections",
            help="Открывает разделы «Симуляция» и «Сравнение вариантов».",
        )
        if show_additional:
            for page, label in NAVIGATION:
                if page in ADDITIONAL_NAVIGATION:
                    st.page_link(page, label=label, use_container_width=True)
        for page, label in NAVIGATION[8:]:
            st.page_link(page, label=label, use_container_width=True)


def configure_page(title: str, icon: str = "↕️") -> None:
    """Настраивает страницу и единый визуальный стиль."""

    st.set_page_config(page_title=title, page_icon=icon, layout="wide")
    render_navigation()
    st.markdown(
        """
        <style>
        .block-container {max-width: 1420px; padding-top: 1.4rem;}
        [data-testid="stMetric"] {
            background: #f4f7f9; border: 1px solid #d5e0e5;
            padding: 0.8rem; border-radius: 0.65rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def ensure_session() -> Project:
    """Инициализирует изолированный проект в пользовательской сессии."""

    if "project" not in st.session_state:
        st.session_state.project = ProjectService.create_application_default()
    st.session_state.setdefault("analytic_result", None)
    st.session_state.setdefault("simulation_result", None)
    st.session_state.setdefault("variants", [])
    return st.session_state.project


def update_project(project: Project) -> None:
    """Сохраняет обновлённую модель и очищает устаревшие результаты."""

    project.modified_at = datetime.now(timezone.utc)
    st.session_state.project = project
    st.session_state.analytic_result = None
    st.session_state.simulation_result = None
    st.session_state.variants = []
    invalidate_generated_reports()


def render_messages(messages: list[DiagnosticMessage]) -> None:
    """Отображает типизированные сообщения подходящим компонентом."""

    for message in messages:
        text = f"{message.code}: {message.text}"
        if message.severity == MessageSeverity.ERROR:
            st.error(text)
        elif message.severity == MessageSeverity.WARNING:
            st.warning(text)
        else:
            st.info(text)


def enum_index(options: list[Any], current: Any) -> int:
    """Безопасно возвращает индекс текущего значения в списке enum."""

    try:
        return options.index(current)
    except ValueError:
        return 0
