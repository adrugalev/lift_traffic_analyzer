"""Проверки полноты пользовательского справочника."""

from __future__ import annotations

from pathlib import Path

from src.models.building import BuildingType
from src.models.traffic import ArrivalDistribution
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
from src.reports.formula_rendering import FORMULA_SPECS, PDF_FORMULAS
from src.services.configuration_service import ConfigurationService


def test_reference_guide_covers_every_configured_formula_and_profile() -> None:
    """У каждой используемой формулы и каждого профиля есть пояснение."""

    configuration = ConfigurationService()
    formula_ids = set(configuration.formulas()["formulas"])
    grouped_formula_ids = {
        formula_id
        for _group_title, group_formula_ids in FORMULA_GROUPS
        for formula_id in group_formula_ids
    }
    profile_ids = set(configuration.load("traffic_profiles.yaml")["profiles"])

    assert grouped_formula_ids == formula_ids
    assert set(FORMULA_LATEX) == formula_ids
    assert set(FORMULA_USAGE) == formula_ids
    assert set(FORMULA_VARIABLES_IN_ORDER) == formula_ids
    assert set(PROFILE_EXAMPLES) == profile_ids
    assert all("round" not in expression for expression in FORMULA_LATEX.values())
    assert sum("operatorname{окр}" in expression for expression in FORMULA_LATEX.values()) == 3

    formula_registry = configuration.formulas()["formulas"]
    for formula_id, expected_symbols in FORMULA_VARIABLES_IN_ORDER.items():
        assert tuple(formula_registry[formula_id]["variables"]) == expected_symbols


def test_user_formulas_do_not_expose_implementation_names() -> None:
    """В справочнике остаются инженерные обозначения, а не имена из кода."""

    configuration = ConfigurationService()
    configured_expressions = [
        item["expression"]
        for item in configuration.formulas()["formulas"].values()
    ]
    display_text = "\n".join(
        [
            *configured_expressions,
            *FORMULA_LATEX.values(),
            *PDF_FORMULAS.values(),
            repr(FORMULA_SPECS),
        ]
    )

    for technical_name in (
        "lookup",
        "S_curve",
        "T_cycle",
        "t_motion",
        "t_board",
        "t_alight",
        "AWT_proxy",
        "C_nom",
        "k_fill",
    ):
        assert technical_name not in display_text


def test_formula_symbols_use_required_subscripts() -> None:
    """Составные математические обозначения оформляются подстрочно."""

    assert formula_symbol_html("T") == (
        '<span class="formula-symbol"><i>T</i></span>'
    )
    assert formula_symbol_html("Nр") == (
        '<span class="formula-symbol"><i>N</i><sub>р</sub></span>'
    )
    assert formula_symbol_html("tэт.н") == (
        '<span class="formula-symbol"><i>t</i><sub>эт.н</sub></span>'
    )
    assert formula_symbol_html("HC5") == (
        '<span class="formula-symbol"><i>HC</i><sub>5</sub></span>'
    )
    assert formula_symbol_html("%P5") == (
        '<span class="formula-symbol">%<i>P</i><sub>5</sub></span>'
    )


def test_reference_guide_covers_building_and_arrival_types() -> None:
    """Справочник не пропускает поддерживаемые типы зданий и модели прихода."""

    assert set(BUILDING_PROFILE_GUIDE) == {
        building_type.value for building_type in BuildingType
    }
    assert set(ARRIVAL_DISTRIBUTION_GUIDE) == {
        distribution.value for distribution in ArrivalDistribution
    }


def test_reference_page_hides_internal_configurations() -> None:
    """Страница не возвращает пользователю прежние JSON и внутренние поля."""

    project_root = Path(__file__).resolve().parents[2]
    page_text = (project_root / "pages" / "09_reference_data.py").read_text(
        encoding="utf-8"
    )

    assert "st.json" not in page_text
    assert "Каталог лифтов" not in page_text
    assert "Реализация в коде" not in page_text
    assert 'st.title("Справочники и формулы")' in page_text
    assert "height=PROFILE_CARD_HEIGHT" in page_text
    assert "height=ARRIVAL_MODEL_CARD_HEIGHT" in page_text
    assert 'class="formula-symbol-table"' in page_text
    assert "formula_symbol_html(symbol)" in page_text
    assert '"Скачать ГОСТ"' not in page_text
    assert "download_button" not in page_text
    assert "Официальная карточка ГОСТ 34758-2021 в Росстандарте" in page_text
