"""Пользовательский справочник по формулам и пассажиропотокам."""

from __future__ import annotations

from html import escape

import pandas as pd
import streamlit as st

from src.reference_guide import (
    ARRIVAL_DISTRIBUTION_GUIDE,
    BUILDING_PROFILE_GUIDE,
    FORMULA_GROUPS,
    FORMULA_LATEX,
    FORMULA_USAGE,
    FORMULA_VARIABLES_IN_ORDER,
    PROFILE_EXAMPLES,
    formula_symbol_html,
)
from src.services.configuration_service import ConfigurationService
from src.ui import configure_page, ensure_session


PROFILE_CARD_HEIGHT = 280
ARRIVAL_MODEL_CARD_HEIGHT = 210


FORMULA_TABLE_STYLES = """
<style>
.formula-symbol-table-wrap {
    width: 100%;
    overflow: hidden;
    border: 1px solid #dfe3e8;
    border-radius: 0.65rem;
    margin: 0.75rem 0 0.55rem;
}
.formula-symbol-table {
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    color: var(--text-color);
    font-size: 0.95rem;
}
.formula-symbol-table th {
    background: var(--secondary-background-color);
    color: #7a828d;
    font-weight: 400;
    text-align: left;
}
.formula-symbol-table th,
.formula-symbol-table td {
    padding: 0.58rem 0.72rem;
    vertical-align: middle;
}
.formula-symbol-table th:not(:last-child),
.formula-symbol-table td:not(:last-child) {
    border-right: 1px solid #e1e5e9;
}
.formula-symbol-table tr:not(:last-child) td {
    border-bottom: 1px solid #e1e5e9;
}
.formula-symbol-table th:nth-child(1),
.formula-symbol-table td:nth-child(1) { width: 20%; }
.formula-symbol-table th:nth-child(2),
.formula-symbol-table td:nth-child(2) { width: 60%; }
.formula-symbol-table th:nth-child(3),
.formula-symbol-table td:nth-child(3) { width: 20%; }
.formula-symbol {
    white-space: nowrap;
    font-family: "Cambria Math", "STIX Two Math", serif;
    font-size: 1.06em;
}
.formula-symbol sub {
    font-size: 0.72em;
    line-height: 0;
    vertical-align: -0.35em;
}
.st-key-gost_source_links {
    align-items: center;
    gap: 0.35rem;
}
.st-key-gost_source_links [data-testid="stMarkdown"] {
    width: auto;
}
.st-key-gost_source_links [data-testid="stDownloadButton"] button,
.st-key-gost_source_links [data-testid="stDownloadButton"] button:hover,
.st-key-gost_source_links [data-testid="stDownloadButton"] button:focus,
.st-key-gost_source_links [data-testid="stDownloadButton"] button:active {
    min-height: auto;
    height: auto;
    padding: 0;
    border: 0;
    background: transparent;
    box-shadow: none;
    color: #0068c9;
    text-decoration: underline;
}
.st-key-gost_source_links [data-testid="stDownloadButton"] button p {
    color: inherit;
    font-size: 1rem;
    font-weight: 400;
}
</style>
"""


def _percent(value: float) -> str:
    """Форматирует долю как целый процент."""

    return f"{round(value * 100):.0f}%"


def _formula_card(formula_id: str, formula: dict[str, object]) -> None:
    """Показывает одну формулу без внутренних технических полей."""

    title = str(formula["title_ru"])
    with st.expander(title):
        st.latex(FORMULA_LATEX[formula_id])
        st.write(FORMULA_USAGE[formula_id])

        variables = formula.get("variables", {})
        if isinstance(variables, dict) and variables:
            rows_html = "".join(
                "<tr>"
                f"<td>{formula_symbol_html(symbol)}</td>"
                f"<td>{escape(str(details['title_ru']))}</td>"
                f"<td>{escape(str(details.get('unit') or '—'))}</td>"
                "</tr>"
                for symbol in FORMULA_VARIABLES_IN_ORDER[formula_id]
                for details in (variables[symbol],)
            )
            st.markdown(
                '<div class="formula-symbol-table-wrap">'
                '<table class="formula-symbol-table" '
                'aria-label="Обозначения формулы">'
                "<thead><tr>"
                "<th>Обозначение</th><th>Параметр</th><th>Единица</th>"
                "</tr></thead>"
                f"<tbody>{rows_html}</tbody>"
                "</table></div>",
                unsafe_allow_html=True,
            )

        clause = formula.get("clause")
        result_unit = formula.get("unit") or "безразмерная величина"
        if clause:
            st.caption(
                f"Результат: {result_unit}. Источник: "
                f"{formula['standard']}, {clause}."
            )
        else:
            st.caption(
                f"Результат: {result_unit}. Инженерная зависимость для "
                "предварительной оценки или симуляции; нормативным критерием не является."
            )


def _profile_card(profile: dict[str, object], example: str) -> None:
    """Показывает профиль потока с назначением и практическим примером."""

    with st.container(border=True, height=PROFILE_CARD_HEIGHT):
        st.subheader(str(profile["title_ru"]))
        st.write(str(profile["description_ru"]))
        st.markdown(
            "**Доли направлений:** "
            f"входящий — {_percent(float(profile['incoming_share']))}; "
            f"исходящий — {_percent(float(profile['outgoing_share']))}; "
            f"межэтажный — {_percent(float(profile['interfloor_share']))}."
        )
        st.caption(f"Пример: {example}")


configure_page("Справочники и формулы")
ensure_session()
st.title("Справочники и формулы")
st.markdown(FORMULA_TABLE_STYLES, unsafe_allow_html=True)

configuration = ConfigurationService()
formula_registry = configuration.formulas()["formulas"]
profile_registry = configuration.load("traffic_profiles.yaml")["profiles"]
normative = configuration.normative_values()["standards"]["GOST_34758_2021"]

formula_tab, profiles_tab, buildings_tab, criteria_tab = st.tabs(
    [
        "Формулы",
        "Профили пассажиропотока",
        "Типы зданий",
        "Критерии ГОСТ",
    ]
)

with formula_tab:
    st.write(
        "Здесь собраны все зависимости, которые приложение фактически использует "
        "в расчёте по ГОСТ, предварительной оценке и симуляции. Откройте нужный "
        "параметр, чтобы увидеть формулу, расшифровку обозначений и источник."
    )
    for group_title, formula_ids in FORMULA_GROUPS:
        st.header(group_title)
        if group_title.startswith("Предварительный"):
            st.caption(
                "Эти зависимости помогают анализировать произвольные сценарии и "
                "работу симуляции, но сами по себе не подтверждают соответствие ГОСТ."
            )
        for formula_id in formula_ids:
            _formula_card(formula_id, formula_registry[formula_id])

with profiles_tab:
    st.write(
        "Профиль описывает, откуда и куда едут пассажиры в выбранный период. "
        "Входящий поток направлен от основного посадочного этажа вверх, исходящий — "
        "с обслуживаемых этажей к выходу, межэтажный — между обслуживаемыми этажами."
    )
    st.caption(
        "Доли ниже являются рекомендуемыми начальными значениями для моделирования. "
        "Их можно изменить в разделе «4. Пассажиропоток» по данным конкретного объекта."
    )

    profile_items = list(profile_registry.items())
    for row_start in range(0, len(profile_items), 2):
        columns = st.columns(2)
        for column, (profile_id, profile) in zip(
            columns, profile_items[row_start : row_start + 2], strict=False
        ):
            with column:
                _profile_card(profile, PROFILE_EXAMPLES[profile_id])

    st.header("Модели поступления пассажиров")
    st.write(
        "Модель поступления задаёт не направление поездки, а моменты появления "
        "пассажиров во времени."
    )
    distribution_items = list(ARRIVAL_DISTRIBUTION_GUIDE.items())
    for row_start in range(0, len(distribution_items), 2):
        columns = st.columns(2)
        for column, (distribution_name, guide) in zip(
            columns, distribution_items[row_start : row_start + 2], strict=False
        ):
            with column:
                with st.container(border=True, height=ARRIVAL_MODEL_CARD_HEIGHT):
                    st.subheader(distribution_name)
                    st.write(guide["description"])
                    st.caption(f"Пример: {guide['example']}")

with buildings_tab:
    st.write(
        "Тип здания нужен для выбора разумного стартового профиля. Он не заменяет "
        "проверку фактического режима работы объекта."
    )
    for building_name, guide in BUILDING_PROFILE_GUIDE.items():
        with st.container(border=True):
            st.subheader(building_name)
            left, right = st.columns([1, 2])
            with left:
                st.markdown(f"**Профиль по умолчанию:** {guide['default']}")
                st.markdown(f"**Какие профили проверять:** {guide['profiles']}")
            with right:
                st.write(guide["description"])
                st.caption(f"Пример: {guide['example']}")

    st.info(
        "Расчёт по ГОСТ выполняется для нормативного восходящего пика: 100% "
        "пассажиров входят на основном посадочном этаже и едут вверх. Типовые "
        "профили здания используются для предварительного расчёта и симуляции "
        "реальных периодов работы."
    )

with criteria_tab:
    st.write(
        "Приложение использует ГОСТ 34758-2021 «Лифты. Методика расчёта "
        "пассажиропотоков в жилых зданиях, гостиницах и офисных зданиях». "
        "Ниже приведены применяемые в расчёте критерии и точные ссылки на стандарт."
    )
    st.markdown(
        "[Официальная карточка ГОСТ 34758-2021 в Росстандарте]"
        f"({normative['source']['official_card']})"
    )
    st.header("Критерии для оценки лифтовой группы")
    criteria_rows = []
    for building_name, criterion in normative["criteria"].items():
        criteria_rows.append(
            {
                "Тип здания": building_name,
                "Пассажиропоток за 5 минут": (
                    f"не менее {criterion['traffic_percent_5min_min']:.0f}% населения"
                ),
                "Интервал": f"не более {criterion['interval_s_max']:.0f} с",
                "Время движения на всю высоту": (
                    f"{criterion['full_height_time_s_min']:.0f}–"
                    f"{criterion['full_height_time_s_max']:.0f} с"
                ),
                "Привязка к ГОСТ": criterion["clause"],
            }
        )
    st.dataframe(
        pd.DataFrame(criteria_rows),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Тип здания": st.column_config.TextColumn(width="medium"),
            "Пассажиропоток за 5 минут": st.column_config.TextColumn(width="large"),
            "Интервал": st.column_config.TextColumn(width="medium"),
            "Время движения на всю высоту": st.column_config.TextColumn(width="large"),
            "Привязка к ГОСТ": st.column_config.TextColumn(width="large"),
        },
    )

    st.caption(
        "Пассажиропоток за пять минут приведён в таблице 1 (п. 5.4.1), "
        "рекомендуемые интервал и время движения — в таблице 4 (п. 6.5.2). "
        "Для времени движения приложение считает нарушением превышение верхней "
        "границы; более короткое время само по себе не является несоответствием."
    )

    st.header("Время входа и выхода одного пассажира")
    transfer_rows = [
        {
            "Ширина дверного проёма, мм": width,
            "Время на одного пассажира, с": seconds,
        }
        for width, seconds in normative["passenger_transfer_time_s"].items()
        if width != "clause"
    ]
    st.dataframe(
        pd.DataFrame(transfer_rows),
        hide_index=True,
        use_container_width=True,
        column_config={
            "Ширина дверного проёма, мм": st.column_config.NumberColumn(
                format="%d", width="medium"
            ),
            "Время на одного пассажира, с": st.column_config.NumberColumn(
                format="%.1f", width="medium"
            ),
        },
    )
    st.caption(
        f"Источник: ГОСТ 34758-2021, "
        f"{normative['passenger_transfer_time_s']['clause']}."
    )

    st.header("Дополнительные положения расчёта")
    load_factor = normative["default_load_factor"]
    st.markdown(
        f"""
- Номинальное число пассажиров определяется из грузоподъёмности кабины из расчёта
  **75 кг на человека** — ГОСТ 34758-2021, п. 6.5.3.
- Расчётное заполнение кабины по умолчанию — **{load_factor['value'] * 100:.0f}%**.
  Источник: ГОСТ 34758-2021, {load_factor['clause']}.
- Расчётное число пассажиров округляется до целого по зафиксированному в приложении
  правилу: значение с дробной частью **0,5 округляется вверх**.
- Нормативная схема предполагает **один основной нижний посадочный этаж**,
  восходящий поток, равномерное распределение пассажиров по этажам назначения и
  однородную лифтовую группу.
- Для многофункционального здания функциональные зоны следует рассчитывать отдельно;
  совместную работу общей группы дополнительно проверяют симуляцией.
"""
    )
