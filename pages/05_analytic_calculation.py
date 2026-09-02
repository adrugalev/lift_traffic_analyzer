"""Предварительный и нормативный аналитический расчёт."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.engines.analytic_engine import AnalyticEngine, NormativeConfigurationError
from src.engines.recommendation_engine import RecommendationEngine
from src.reports.gost_report import build_gost_docx_report, build_gost_pdf_report
from src.services.validation_service import ValidationService
from src.ui import (
    configure_page,
    ensure_session,
    invalidate_generated_reports,
    render_messages,
    update_project,
)
from src.utils.file_utils import safe_filename
from src.utils.traffic_profiles import scenario_for_gost_calculation


INTEGER_FORMULA_RESULTS = {
    "gost_nominal_capacity",
    "gost_calculated_car_capacity",
}


def _formatted_formula_result(trace) -> str:
    """Форматирует дискретные вместимости без незначащих дробных знаков."""

    if trace.formula_id in INTEGER_FORMULA_RESULTS:
        return f"{trace.result:.0f}"
    return f"{trace.result:.3f}"


def _generate_gost_exports(
    project,
    result,
    *,
    include_parking: bool,
    include_extended_kinematics: bool,
    include_mixed_capacity: bool,
) -> list[str]:
    """Независимо формирует DOCX и PDF нормативного отчёта."""

    for key in (
        "gost_report_docx",
        "gost_report_pdf",
        "gost_report_include_parking",
        "gost_report_include_extended_kinematics",
        "gost_report_include_mixed_capacity",
    ):
        st.session_state.pop(key, None)
    errors: list[str] = []
    try:
        st.session_state.gost_report_docx = build_gost_docx_report(project, result)
    except Exception as exc:
        errors.append(f"DOCX: {exc}")
    try:
        st.session_state.gost_report_pdf = build_gost_pdf_report(project, result)
    except Exception as exc:
        errors.append(f"PDF: {exc}")
    st.session_state.gost_report_include_parking = include_parking
    st.session_state.gost_report_include_extended_kinematics = (
        include_extended_kinematics
    )
    st.session_state.gost_report_include_mixed_capacity = include_mixed_capacity
    return errors


def _project_for_gost(project, *, include_parking: bool):
    """Готовит копию проекта для нормативного сценария, не меняя исходник."""

    normative_project = project.model_copy(deep=True)
    current_scenario = normative_project.scenario()
    normative_scenario = scenario_for_gost_calculation(
        current_scenario,
        normative_project.building.building_type,
    )
    if current_scenario.name == "По ГОСТ":
        normative_scenario = normative_scenario.model_copy(
            update={"name": "По ГОСТ"}
        )
    if not include_parking:
        normative_scenario = normative_scenario.model_copy(
            update={"parking_incoming_share": 0.0}
        )
    scenario_index = next(
        index
        for index, scenario in enumerate(normative_project.traffic_scenarios)
        if scenario.id == current_scenario.id
    )
    normative_project.traffic_scenarios[scenario_index] = normative_scenario
    return normative_project


def _parking_is_configured(project, group_id: str | None = None) -> bool:
    """Проверяет наличие уровней и заданного пассажиропотока с паркинга."""

    return bool(
        any(
            floor.is_parking
            and (group_id is None or group_id in floor.served_by_group_ids)
            for floor in project.floors
        )
        and project.scenario().parking_incoming_share > 0
    )


def _group_has_mixed_capacities(group) -> bool:
    """Проверяет различие номинальных грузоподъёмностей кабин группы."""

    capacities = {
        round(float(elevator.capacity_kg), 9) for elevator in group.elevators
    }
    return len(capacities) > 1


def _project_for_capacity_mode(
    project,
    group_id: str,
    *,
    include_mixed_capacity: bool,
):
    """Исключает различия кабин из расчётной копии, когда режим снят."""

    group = project.group(group_id)
    if include_mixed_capacity or not _group_has_mixed_capacities(group):
        return project
    candidate = project.model_copy(deep=True)
    candidate_group = candidate.group(group_id)
    reference = candidate_group.elevators[0]
    candidate_group.elevators = [
        reference.model_copy(
            deep=True,
            update={"id": elevator.id, "name": elevator.name},
        )
        for elevator in candidate_group.elevators
    ]
    return candidate


configure_page("Расчёт и отчёт")
project = ensure_session()
engine = AnalyticEngine()
st.title("5. Расчёт и отчёт")
st.markdown(
    """
    <style>
    .st-key-analytic_metric_cards [data-testid="stMetricLabel"],
    .st-key-analytic_metric_cards [data-testid="stMetricLabel"] > div,
    .st-key-analytic_metric_cards [data-testid="stMetricLabel"] p {
        overflow: visible !important;
        text-overflow: clip !important;
        white-space: normal !important;
    }
    .st-key-analytic_metric_cards [data-testid="stMetricLabel"] {
        min-height: 2.4rem;
    }
    .st-key-analytic_metric_cards [data-testid="stMetricLabel"] p {
        font-size: 0.82rem !important;
        line-height: 1.25 !important;
    }
    .st-key-analytic_metric_cards [data-testid="stMetricValue"],
    .st-key-analytic_metric_cards [data-testid="stMetricValue"] > div {
        overflow: visible !important;
        text-overflow: clip !important;
        white-space: nowrap !important;
    }
    .st-key-analytic_metric_cards [data-testid="stMetricValue"] > div {
        font-size: clamp(1.45rem, 2.2vw, 2rem) !important;
        line-height: 1.15 !important;
    }
    .st-key-all_metrics_table [data-testid="stDataFrame"] {
        font-size: 0.78rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

messages = ValidationService.validate_project(project)
render_messages(messages)

if not project.elevator_groups:
    st.error("В разделе «3. Лифты» необходимо добавить хотя бы один лифт.")
    st.stop()
group = project.elevator_groups[0]
methods = st.columns(2)
with methods[0]:
    st.markdown("**Предварительный расчёт**")
    st.caption(
        "Использует сценарий, выбранный в разделе «4. Пассажиропоток». "
        "Предназначен для проверки произвольных направлений потока без оценки соответствия ГОСТ."
    )
    preview_clicked = st.button(
        "Выполнить предварительный расчёт",
        use_container_width=True,
        help=(
            "Выполняет инженерную оценку по текущему пользовательскому сценарию. "
            "Результат не является подтверждением соответствия ГОСТ."
        ),
    )
with methods[1]:
    st.markdown("**Расчёт по ГОСТ**")
    st.caption(
        "Автоматически применяет нормативный восходящий сценарий: "
        "100% входящего потока, 0% исходящего и 0% межэтажного."
    )
    normative_clicked = st.button(
        "Выполнить расчёт по ГОСТ",
        type="primary",
        use_container_width=True,
        help=(
            "Применяет нормативный восходящий пик и выполняет расчётный метод "
            "ГОСТ 34758-2021 с оценкой критериев."
        ),
    )

mixed_capacity_detected = _group_has_mixed_capacities(group)
if not mixed_capacity_detected:
    st.session_state.pop("pending_mixed_capacity_confirmation", None)

confirmation_notice = st.session_state.pop("mixed_capacity_confirmation_notice", None)
if confirmation_notice:
    st.success(confirmation_notice)

execute_normative = False
mixed_capacity_mode = False
if normative_clicked:
    if mixed_capacity_detected:
        st.session_state.pending_mixed_capacity_confirmation = True
    else:
        execute_normative = True

if st.session_state.get("pending_mixed_capacity_confirmation", False):
    st.warning(
        "В группе обнаружены лифты разной грузоподъёмности. Строгая формула "
        "ГОСТ рассчитана для однородной группы. Применить инженерную формулу "
        "усреднения интервалов и продолжить расчёт по ГОСТ?"
    )
    confirmation_columns = st.columns(2)
    apply_mixed_formula = confirmation_columns[0].button(
        "Считать с учётом разных грузоподъёмностей",
        type="primary",
        use_container_width=True,
    )
    cancel_mixed_formula = confirmation_columns[1].button(
        "Не считать",
        use_container_width=True,
    )
    if apply_mixed_formula:
        st.session_state.pending_mixed_capacity_confirmation = False
        st.session_state.include_mixed_capacity_in_gost_report = True
        execute_normative = True
        mixed_capacity_mode = True
    elif cancel_mixed_formula:
        st.session_state.pending_mixed_capacity_confirmation = False
        st.session_state.mixed_capacity_confirmation_notice = (
            "Расчёт отменён. Параметры проекта не изменены."
        )
        st.rerun()

if preview_clicked:
    try:
        result = engine.calculate_preview(project, group.id)
        result.recommendations = RecommendationEngine.generate(result)
        invalidate_generated_reports()
        st.session_state.analytic_result = result
        st.success("Предварительный расчёт выполнен.")
    except Exception as exc:
        st.error(str(exc))
if execute_normative:
    try:
        normative_project = _project_for_gost(project, include_parking=True)
        strict_gost_project = _project_for_gost(project, include_parking=False)
        result = engine.calculate_normative(
            strict_gost_project,
            group.id,
            include_extended_kinematics=False,
            include_mixed_capacity=mixed_capacity_mode,
        )
        result.recommendations = RecommendationEngine.generate(result)
        parking_reference_result = None
        if _parking_is_configured(normative_project, group.id):
            parking_reference_result = engine.calculate_normative(
                normative_project,
                group.id,
                include_extended_kinematics=False,
                include_mixed_capacity=mixed_capacity_mode,
            )
            parking_reference_result.recommendations = RecommendationEngine.generate(
                parking_reference_result
            )
        update_project(normative_project)
        st.session_state.analytic_result = result
        st.session_state.gost_project_without_parking = strict_gost_project
        st.session_state.gost_project_with_parking = normative_project
        st.session_state.parking_reference_result = parking_reference_result
        st.session_state.gost_result_include_parking = False
        st.session_state.gost_result_include_extended_kinematics = False
        st.session_state.gost_result_include_mixed_capacity = mixed_capacity_mode
        if mixed_capacity_mode:
            st.success(
                "Расчёт с учётом разных грузоподъёмностей выполнен. "
                "Настройте условия ниже и отдельно сформируйте отчёт."
            )
        else:
            st.success("Расчёт по ГОСТ выполнен без учёта паркинга.")
    except NormativeConfigurationError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.error(str(exc))

result = st.session_state.analytic_result
if result and result.calculation_basis == "GOST_34758_2021_CLAUSE_7":
    st.subheader("Отчёт по результатам расчёта")
    parking_configured = _parking_is_configured(project, group.id)
    mixed_capacity_mode = bool(
        st.session_state.get("gost_result_include_mixed_capacity", False)
    )
    if not parking_configured:
        st.session_state.include_parking_in_gost_report = False
    if not mixed_capacity_detected:
        st.session_state.include_mixed_capacity_in_gost_report = False
    elif "include_mixed_capacity_in_gost_report" not in st.session_state:
        st.session_state.include_mixed_capacity_in_gost_report = mixed_capacity_mode
    report_controls = st.columns([1, 1, 1.25, 1.35])
    with report_controls[0]:
        include_parking_in_report = st.checkbox(
            "Включать в расчёт паркинг",
            value=False,
            key="include_parking_in_gost_report",
            disabled=not parking_configured,
            help=(
                "По умолчанию отчёт формируется строго по ГОСТ без паркинга. "
                "При включении применяется справочная инженерная поправка: "
                "каждый круговой рейс считается с заходом на паркинг."
            ),
        )
    with report_controls[1]:
        include_extended_kinematics_in_report = st.checkbox(
            "Учитывать дополнительную кинематику",
            value=False,
            key="include_extended_kinematics_in_gost_report",
            help=(
                "Если галочка снята, межэтажное время определяется строго по "
                "формуле (8) ГОСТ: hэт / vн, а максимальная скорость принимается "
                "равной номинальной. Если галочка установлена, применяется "
                "дополнительная инженерная модель S-образного профиля с учётом "
                "ускорения, замедления и рывка; эта модель не является формулой ГОСТ."
            ),
        )
    with report_controls[2]:
        include_mixed_capacity_in_report = st.checkbox(
            "Расчёт лифтов разной грузоподъёмности",
            key="include_mixed_capacity_in_gost_report",
            disabled=not mixed_capacity_detected,
            help=(
                "Для неоднородной группы рассчитывает отдельный интервал и "
                "провозную способность каждой кабины, затем объединяет их "
                "по инженерной формуле усреднения."
            ),
        )
    mixed_capacity_mode = include_mixed_capacity_in_report
    no_calculation_options_selected = not any(
        (
            include_parking_in_report,
            include_extended_kinematics_in_report,
            include_mixed_capacity_in_report,
        )
    )
    if mixed_capacity_detected and no_calculation_options_selected:
        invalidate_generated_reports()
        st.session_state.analytic_result = None
        st.session_state.parking_reference_result = None
        st.session_state.pop("gost_result_include_parking", None)
        st.session_state.pop("gost_result_include_extended_kinematics", None)
        st.session_state.pop("gost_result_include_mixed_capacity", None)
        st.rerun()
    previous_parking_mode = bool(
        st.session_state.get("gost_result_include_parking", False)
    )
    previous_kinematics_mode = bool(
        st.session_state.get(
            "gost_result_include_extended_kinematics",
            False,
        )
    )
    previous_mixed_capacity_mode = bool(
        st.session_state.get("gost_result_include_mixed_capacity", False)
    )
    result_mode_changed = (
        previous_parking_mode != include_parking_in_report
        or previous_kinematics_mode != include_extended_kinematics_in_report
        or previous_mixed_capacity_mode != mixed_capacity_mode
    )
    if result_mode_changed:
        try:
            selected_project = st.session_state.get(
                "gost_project_with_parking"
                if include_parking_in_report
                else "gost_project_without_parking"
            )
            if selected_project is None:
                selected_project = _project_for_gost(
                    project,
                    include_parking=include_parking_in_report,
                )
            selected_project = _project_for_capacity_mode(
                selected_project,
                group.id,
                include_mixed_capacity=mixed_capacity_mode,
            )
            recalculated_result = engine.calculate_normative(
                selected_project,
                group.id,
                include_extended_kinematics=(
                    include_extended_kinematics_in_report
                ),
                include_mixed_capacity=mixed_capacity_mode,
            )
            recalculated_result.recommendations = RecommendationEngine.generate(
                recalculated_result
            )
            parking_reference_result = None
            parking_project = st.session_state.get("gost_project_with_parking")
            if (
                not include_parking_in_report
                and parking_project is not None
                and _parking_is_configured(parking_project, group.id)
            ):
                parking_reference_result = engine.calculate_normative(
                    _project_for_capacity_mode(
                        parking_project,
                        group.id,
                        include_mixed_capacity=mixed_capacity_mode,
                    ),
                    group.id,
                    include_extended_kinematics=(
                        include_extended_kinematics_in_report
                    ),
                    include_mixed_capacity=mixed_capacity_mode,
                )
                parking_reference_result.recommendations = (
                    RecommendationEngine.generate(parking_reference_result)
                )
            invalidate_generated_reports()
            st.session_state.analytic_result = recalculated_result
            st.session_state.parking_reference_result = parking_reference_result
            st.session_state.gost_result_include_parking = (
                include_parking_in_report
            )
            st.session_state.gost_result_include_extended_kinematics = (
                include_extended_kinematics_in_report
            )
            st.session_state.gost_result_include_mixed_capacity = (
                mixed_capacity_mode
            )
            result = recalculated_result
        except NormativeConfigurationError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.error(f"Не удалось обновить расчёт: {exc}")
    stored_parking_mode = st.session_state.get("gost_report_include_parking")
    stored_kinematics_mode = st.session_state.get(
        "gost_report_include_extended_kinematics"
    )
    stored_mixed_capacity_mode = st.session_state.get(
        "gost_report_include_mixed_capacity",
        False,
    )
    report_mode_matches = (
        stored_parking_mode is not None
        and stored_kinematics_mode is not None
        and stored_parking_mode == include_parking_in_report
        and stored_kinematics_mode == include_extended_kinematics_in_report
        and stored_mixed_capacity_mode == mixed_capacity_mode
    )
    with report_controls[3]:
        available_gost_reports = [
            ("DOCX", st.session_state.get("gost_report_docx")),
            ("PDF", st.session_state.get("gost_report_pdf")),
        ]
        available_gost_reports = [
            (kind, data) for kind, data in available_gost_reports if data is not None
        ]
        if not report_mode_matches:
            available_gost_reports = []
        if not available_gost_reports:
            report_button_label = (
                "Сформировать отчёт по ГОСТ (уточнённый)"
                if (
                    include_parking_in_report
                    or include_extended_kinematics_in_report
                    or mixed_capacity_mode
                )
                else "Сформировать отчёт по ГОСТ"
            )
            if st.button(
                report_button_label,
                key="prepare_gost_report",
                use_container_width=True,
                help=(
                    "Формирует DOCX и PDF после окончательного выбора всех "
                    "условий расчёта."
                ),
            ):
                report_project = st.session_state.get(
                    "gost_project_with_parking"
                    if include_parking_in_report
                    else "gost_project_without_parking"
                )
                if report_project is None:
                    report_project = _project_for_gost(
                        project,
                        include_parking=include_parking_in_report,
                    )
                report_project = _project_for_capacity_mode(
                    report_project,
                    group.id,
                    include_mixed_capacity=mixed_capacity_mode,
                )
                report_result = engine.calculate_normative(
                    report_project,
                    group.id,
                    include_extended_kinematics=(
                        include_extended_kinematics_in_report
                    ),
                    include_mixed_capacity=mixed_capacity_mode,
                )
                report_result.recommendations = RecommendationEngine.generate(
                    report_result
                )
                with st.spinner("Подготавливается отчёт по ГОСТ…"):
                    gost_export_errors = _generate_gost_exports(
                        report_project,
                        report_result,
                        include_parking=include_parking_in_report,
                        include_extended_kinematics=(
                            include_extended_kinematics_in_report
                        ),
                        include_mixed_capacity=mixed_capacity_mode,
                    )
                if gost_export_errors:
                    st.error(
                        "Не удалось подготовить отдельные форматы отчёта: "
                        + "; ".join(gost_export_errors)
                    )
                st.rerun()
        else:
            base_name = safe_filename(st.session_state.project.metadata.name)
            download_columns = st.columns(len(available_gost_reports))
            for column, (kind, data) in zip(
                download_columns, available_gost_reports, strict=True
            ):
                if kind == "DOCX":
                    column.download_button(
                        "Скачать DOCX",
                        data,
                        f"{base_name}_GOST_34758-2021.docx",
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document",
                        use_container_width=True,
                        help="Скачивает редактируемый отчёт по ГОСТ.",
                    )
                else:
                    column.download_button(
                        "Скачать PDF",
                        data,
                        f"{base_name}_GOST_34758-2021.pdf",
                        "application/pdf",
                        use_container_width=True,
                        help="Скачивает отчёт по ГОСТ с фиксированной вёрсткой.",
                    )
if result:
    st.subheader("Основные показатели")
    keys = ["interval", "handling_capacity_5min", "average_wait_proxy", "reserve"]
    metric_help = {
        "interval": (
            "Расчётное время между последовательными отправлениями кабин "
            "с основного посадочного этажа."
        ),
        "handling_capacity_5min": (
            "Среднее число пассажиров, которое группа способна перевезти "
            "за расчётные пять минут."
        ),
        "average_wait_proxy": (
            "Ориентир I/2 при равномерных интервалах отправления. Фактическое "
            "ожидание определяется симуляцией и обычно бывает не меньше."
        ),
        "reserve": (
            "Превышение провозной способности над расчётным спросом, выраженное "
            "в процентах от спроса. Отрицательное значение означает дефицит."
        ),
    }
    with st.container(key="analytic_metric_cards"):
        columns = st.columns(4)
        for column, key in zip(columns, keys, strict=True):
            metric = result.metric(key)
            display_unit = "пасс." if key == "handling_capacity_5min" else metric.unit
            column.metric(
                metric.title_ru,
                f"{metric.value:.1f} {display_unit}",
                help=metric_help[key],
            )
    if result.calculation_basis == "GOST_34758_2021_CLAUSE_7":
        selected_mode_notes = []
        if include_parking_in_report:
            selected_mode_notes.append("с учётом справочной поправки на паркинг")
        else:
            selected_mode_notes.append("без учёта паркинга")
        if include_extended_kinematics_in_report:
            selected_mode_notes.append("с дополнительной инженерной кинематикой")
        else:
            selected_mode_notes.append("со строгой формулой межэтажного времени ГОСТ")
        if mixed_capacity_mode:
            selected_mode_notes.append(
                "с инженерным расчётом лифтов разной грузоподъёмности"
            )
        elif mixed_capacity_detected:
            selected_mode_notes.append(
                "без учёта различий грузоподъёмности, по параметрам первого лифта"
            )
        st.caption(
            "Показатели автоматически пересчитаны "
            + ", ".join(selected_mode_notes)
            + ". Ориентировочное время ожидания нормативно не оценивается."
        )
        parking_reference_result = st.session_state.get(
            "parking_reference_result"
        )
        if parking_reference_result is not None and not include_parking_in_report:
            st.markdown("**Справочная оценка влияния паркинга**")
            st.caption(
                "Не является расчётом по ГОСТ и не влияет на показанные выше "
                "нормативные статусы. Применено консервативное допущение: каждый "
                "круговой рейс включает заход на паркинг."
            )
            reference_columns = st.columns(3)
            reference_columns[0].metric(
                "Добавка к круговому рейсу",
                f"{parking_reference_result.metric('parking_round_trip_addition').value:.1f} с",
            )
            reference_columns[1].metric(
                "Интервал с паркингом",
                f"{parking_reference_result.metric('interval').value:.1f} с",
            )
            reference_columns[2].metric(
                "Провозная способность с паркингом",
                f"{parking_reference_result.metric('handling_capacity_5min').value:.1f} пасс.",
            )
    else:
        st.caption(
            "Предварительный результат для выбранного сценария. "
            "Соответствие ГОСТ не оценивается."
        )

    tabs = st.tabs(["Все показатели", "Формулы", "Сообщения", "Рекомендации", "Аудит"])
    with tabs[0]:
        metrics_frame = pd.DataFrame(
            [metric.model_dump(mode="json") for metric in result.metrics]
        )
        with st.container(key="all_metrics_table"):
            st.dataframe(
                metrics_frame,
                width="stretch",
                height=min(600, 36 + len(metrics_frame) * 29),
                row_height=28,
                hide_index=True,
                column_order=(
                    "key",
                    "title_ru",
                    "value",
                    "unit",
                    "method",
                    "compliance",
                    "target_value",
                    "target_description",
                ),
                column_config={
                    "key": st.column_config.TextColumn(
                        "Код",
                        width=135,
                        help="Внутренний неизменяемый идентификатор показателя.",
                    ),
                    "title_ru": st.column_config.TextColumn(
                        "Показатель",
                        width=300,
                        help="Наименование расчётного или справочного показателя.",
                    ),
                    "value": st.column_config.NumberColumn(
                        "Значение",
                        width=75,
                        help="Рассчитанное числовое значение до форматирования.",
                    ),
                    "unit": st.column_config.TextColumn(
                        "Единица",
                        width=80,
                        help="Единица измерения рассчитанного значения.",
                    ),
                    "method": st.column_config.TextColumn(
                        "Метод",
                        width=120,
                        help="Расчётный метод или источник показателя.",
                    ),
                    "compliance": st.column_config.TextColumn(
                        "Соответствие",
                        width=110,
                        help="Результат сравнения с применимым нормативным критерием.",
                    ),
                    "target_value": st.column_config.NumberColumn(
                        "Целевое значение",
                        width=105,
                        help="Числовая граница критерия, если она однозначно задана.",
                    ),
                    "target_description": st.column_config.TextColumn(
                        "Критерий",
                        width=220,
                        help="Условие, с которым сравнивается расчётное значение.",
                    ),
                },
            )
    with tabs[1]:
        for trace in result.formulas:
            with st.expander(
                f"{trace.title_ru}: {_formatted_formula_result(trace)} {trace.unit}"
            ):
                st.code(trace.expression, language=None)
                st.write("Подстановка:", trace.substituted_expression)
                st.json(trace.variables)
                st.caption(
                    f"Источник: {trace.standard}; пункт: {trace.clause or 'не подтверждён'}; "
                    f"статус: {trace.status}."
                )
    with tabs[2]:
        render_messages(result.messages)
    with tabs[3]:
        for recommendation in result.recommendations:
            st.info(
                f"{recommendation.problem}\n\n**Решение:** {recommendation.proposed_action}\n\n"
                f"**Ограничение:** {recommendation.limitations}"
            )
    with tabs[4]:
        st.json(result.audit.model_dump(mode="json"))
