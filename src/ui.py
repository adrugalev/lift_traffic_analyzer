"""Общие функции тонкого слоя Streamlit."""

from __future__ import annotations

from datetime import datetime, timezone
from random import SystemRandom
from typing import Any

import streamlit as st

from src import APP_NAME, APP_SUBTITLE
from src.models.project import Project
from src.models.results import DiagnosticMessage, MessageSeverity
from src.services.project_service import ProjectService


NAVIGATION = (
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

DEMO_CLICK_THRESHOLD = 4


def invalidate_generated_reports() -> None:
    """Удаляет отчёты, которые могли устареть после изменения исходных данных."""

    for key in GENERATED_REPORT_KEYS:
        st.session_state.pop(key, None)


def handle_demo_project_trigger(clicked: bool) -> bool:
    """Загружает очередной демо-проект после четырёх кликов по заголовку меню."""

    if not clicked:
        return False
    click_count = int(st.session_state.get("sections_demo_click_count", 0)) + 1
    if click_count < DEMO_CLICK_THRESHOLD:
        st.session_state.sections_demo_click_count = click_count
        return False

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
            project_queue[0], project_queue[1] = project_queue[1], project_queue[0]

    project_key = project_queue.pop(0)
    test_project = ProjectService.create_test_project(project_key=project_key)
    elevator_count = test_project.elevator_groups[0].elevator_count
    update_project(test_project)
    st.session_state.test_project_queue = project_queue
    st.session_state.last_test_project_key = project_key
    st.session_state.sections_demo_click_count = 0
    st.session_state.demo_project_loaded_notice = (
        f"Загружен проект «{test_project.metadata.name}»: "
        f"{len(test_project.floors)} этажей, {test_project.population} человек, "
        f"{elevator_count} лифтов."
    )
    return True


def render_navigation() -> None:
    """Показывает единое русскоязычное меню приложения."""

    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-app-brand">
                <div class="sidebar-app-name">{APP_NAME}</div>
                <div class="sidebar-app-subtitle">{APP_SUBTITLE}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        demo_clicked = st.button(
            "РАЗДЕЛЫ",
            key="sections_demo_trigger",
            type="tertiary",
        )
        if handle_demo_project_trigger(demo_clicked):
            st.rerun()
        if notice := st.session_state.pop("demo_project_loaded_notice", None):
            st.success(notice)
        for page, label in NAVIGATION[:5]:
            st.page_link(page, label=label, use_container_width=True)
        show_additional = st.checkbox(
            "Показать дополнительные разделы (бета-версия)",
            key="show_additional_sections",
            help="Открывает разделы «Симуляция» и «Сравнение вариантов».",
        )
        if show_additional:
            for page, label in NAVIGATION:
                if page in ADDITIONAL_NAVIGATION:
                    st.page_link(page, label=label, use_container_width=True)
        for page, label in NAVIGATION[7:]:
            st.page_link(page, label=label, use_container_width=True)


def configure_page(title: str, icon: str = "↕️") -> None:
    """Настраивает страницу и единый визуальный стиль."""

    st.set_page_config(
        page_title=f"{title} — {APP_NAME}",
        page_icon=icon,
        layout="wide",
    )
    render_navigation()
    st.markdown(
        """
        <style>
        .block-container {max-width: 1420px; padding-top: 1.4rem;}
        .sidebar-app-brand {
            margin: 0.1rem 0 1.15rem;
        }
        .sidebar-app-name {
            color: #31333f;
            font-size: 1.08rem;
            font-weight: 650;
            line-height: 1.25;
        }
        .sidebar-app-subtitle {
            margin-top: 0.35rem;
            color: rgba(49, 51, 63, 0.58);
            font-size: 0.78rem;
            font-weight: 400;
            line-height: 1.35;
        }
        [data-testid="stMetric"] {
            background: #f4f7f9; border: 1px solid #d5e0e5;
            padding: 0.8rem; border-radius: 0.65rem;
        }
        .st-key-sections_demo_trigger button,
        .st-key-sections_demo_trigger button:hover,
        .st-key-sections_demo_trigger button:focus,
        .st-key-sections_demo_trigger button:active {
            min-height: auto !important; height: auto !important;
            padding: 0 !important; border: 0 !important;
            background: transparent !important; box-shadow: none !important;
            color: rgba(49, 51, 63, 0.55) !important;
            cursor: default !important; outline: none !important;
        }
        .st-key-sections_demo_trigger button p {
            color: inherit !important; font-size: 0.875rem !important;
            font-weight: 400 !important; letter-spacing: 0.02em !important;
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
