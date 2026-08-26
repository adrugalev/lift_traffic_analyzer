"""Формирование и скачивание DOCX, PDF и XLSX."""

from __future__ import annotations

import streamlit as st

from src.reports.docx_report import build_docx_report
from src.reports.excel_report import build_excel_report
from src.reports.gost_report import build_gost_docx_report, build_gost_pdf_report
from src.reports.pdf_report import build_pdf_report
from src.ui import configure_page, ensure_session
from src.utils.file_utils import safe_filename


configure_page("Отчёт")
project = ensure_session()
st.title("8. Отчёт")
analytic = st.session_state.analytic_result
simulation = st.session_state.simulation_result
variants = st.session_state.variants

st.write(
    f"В отчёт включаются: аналитический расчёт — {'да' if analytic else 'нет'}, "
    f"симуляция — {'да' if simulation else 'нет'}, вариантов — {len(variants)}."
)
is_gost_result = bool(
    analytic and analytic.calculation_basis == "GOST_34758_2021_CLAUSE_7"
)
if is_gost_result:
    st.success(
        "Доступна отдельная форма «По ГОСТ»: состав сведений соответствует разделу 9 "
        "ГОСТ 34758-2021."
    )
else:
    st.info(
        "Общий отчёт маркирует предварительные формулы. Для формы «По ГОСТ» сначала "
        "выполните нормативный расчёт на странице 5."
    )

base_name = safe_filename(project.metadata.name)
if st.button(
    "Сформировать пакет отчётов",
    type="primary",
    help=(
        "Создаёт общий DOCX, PDF и XLSX из сохранённых данных проекта и доступных "
        "результатов расчёта, симуляции и сравнения."
    ),
):
    try:
        with st.spinner("Формируются DOCX, PDF и XLSX…"):
            st.session_state.report_docx = build_docx_report(project, analytic, simulation, variants)
            st.session_state.report_pdf = build_pdf_report(project, analytic, simulation, variants)
            st.session_state.report_xlsx = build_excel_report(project, analytic, simulation, variants)
        st.success("Пакет отчётов сформирован в памяти текущей сессии.")
    except Exception as exc:
        st.error(f"Не удалось сформировать отчёт: {exc}")

if "report_docx" in st.session_state:
    columns = st.columns(3)
    columns[0].download_button(
        "Скачать DOCX",
        st.session_state.report_docx,
        f"{base_name}_report.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
        help="Скачивает редактируемый общий отчёт Microsoft Word.",
    )
    columns[1].download_button(
        "Скачать PDF",
        st.session_state.report_pdf,
        f"{base_name}_report.pdf",
        "application/pdf",
        use_container_width=True,
        help="Скачивает общий отчёт с фиксированной вёрсткой в формате PDF.",
    )
    columns[2].download_button(
        "Скачать XLSX",
        st.session_state.report_xlsx,
        f"{base_name}_data.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        help="Скачивает исходные данные и результаты в табличном формате Excel.",
    )

st.subheader("Форма отчёта «По ГОСТ»")
st.caption(
    "Включает общие сведения, данные здания и этажей, критерии, параметры лифтовой "
    "установки, расчётные показатели, оценку соответствия, формулы и аудит."
)
if st.button(
    "Сформировать отчёт «По ГОСТ»",
    type="primary",
    disabled=not is_gost_result,
    help=(
        "Формирует специальный отчёт по составу раздела 9 ГОСТ 34758-2021. "
        "Кнопка доступна после выполнения расчёта по ГОСТ в разделе 5."
    ),
):
    try:
        with st.spinner("Формируются DOCX и PDF по разделу 9 ГОСТ…"):
            st.session_state.gost_report_docx = build_gost_docx_report(project, analytic)
            st.session_state.gost_report_pdf = build_gost_pdf_report(project, analytic)
        st.success("Отчёт «По ГОСТ» сформирован.")
    except Exception as exc:
        st.error(f"Не удалось сформировать отчёт «По ГОСТ»: {exc}")

if "gost_report_docx" in st.session_state:
    gost_columns = st.columns(2)
    gost_columns[0].download_button(
        "Скачать DOCX «По ГОСТ»",
        st.session_state.gost_report_docx,
        f"{base_name}_GOST_34758-2021.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True,
        help="Скачивает редактируемую форму отчёта по ГОСТ в формате Word.",
    )
    gost_columns[1].download_button(
        "Скачать PDF «По ГОСТ»",
        st.session_state.gost_report_pdf,
        f"{base_name}_GOST_34758-2021.pdf",
        "application/pdf",
        use_container_width=True,
        help="Скачивает форму отчёта по ГОСТ с фиксированной вёрсткой в формате PDF.",
    )
