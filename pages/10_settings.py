"""Диагностика конфигурации и настройки приложения."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src import __version__
from src.services.configuration_service import ConfigurationService
from src.ui import configure_page, ensure_session


@st.dialog("История версий", width="large")
def show_version_history(
    versions: list[dict[str, str]],
    history_starts_with: str,
) -> None:
    """Показывает компактную историю изменений."""

    rows = [
        {
            "Версия": item["version"],
            "Дата": item["date"],
            "Изменения": item["changes_ru"],
        }
        for item in versions
    ]
    st.dataframe(
        pd.DataFrame(rows),
        hide_index=True,
        width="stretch",
        height="auto",
        column_config={
            "Версия": st.column_config.TextColumn(width="small"),
            "Дата": st.column_config.TextColumn(width="small"),
            "Изменения": st.column_config.TextColumn(width="large"),
        },
    )
    st.caption(f"История ведётся с версии {history_starts_with}.")


configure_page("О программе")
ensure_session()
st.title("9. О программе")
st.markdown(
    """
    <style>
    .st-key-version_metric_card {
        height: 103.2px;
        min-height: 103.2px;
        padding: 0.8rem;
        background: #f4f7f9;
        border: 1px solid #d5e0e5;
        border-radius: 0.65rem;
    }
    .version-metric-label {
        height: 24px;
        color: #31333f;
        font-size: 14px;
        line-height: 24px;
    }
    .st-key-version_metric_card
    [data-testid="stMarkdownContainer"]:has(.version-metric-label) {
        margin-bottom: 0;
    }
    .st-key-version_metric_card [data-testid="stBaseButton-tertiary"] {
        height: 52px;
        justify-content: flex-start;
        padding: 0 0 4px;
    }
    .st-key-version_metric_card [data-testid="stBaseButton-tertiary"] > div,
    .st-key-version_metric_card [data-testid="stBaseButton-tertiary"] span {
        justify-content: flex-start;
    }
    .st-key-version_metric_card [data-testid="stBaseButton-tertiary"] p {
        font-size: 36px;
        font-weight: 400;
        line-height: 48px;
        text-align: left;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

version_history = ConfigurationService().version_history()
versions = version_history["versions"]

columns = st.columns(2)
with columns[0].container(key="version_metric_card", gap=None):
    st.markdown(
        '<div class="version-metric-label">Версия приложения</div>',
        unsafe_allow_html=True,
    )
    if st.button(
        __version__,
        key="show_version_history",
        type="tertiary",
        width="stretch",
        help="Нажмите, чтобы открыть краткую историю версий.",
    ):
        show_version_history(
            versions,
            str(version_history["history_starts_with"]),
        )
columns[1].metric(
    "Нормативный документ",
    "ГОСТ 34758-2021",
    help=(
        "Нормативный документ, методика и критерии которого используются "
        "при выполнении расчёта по ГОСТ."
    ),
)

st.subheader("Локальность и приватность")
st.write(
    "Расчёты выполняются локально. Проектные данные не отправляются во внешние сервисы. "
    "Отчёты формируются в памяти сессии и передаются браузеру только по кнопке скачивания."
)

st.subheader("Нормативное наполнение")
st.code(
    "config/formulas.yaml\nconfig/normative_values.yaml\nconfig/version_history.yaml",
    language=None,
)
st.caption(
    "ГОСТ: таблицы 1, 3, 4, формулы (1), (4)–(11), пример приложения Д."
)
