"""Генератор PDF-версии инженерного отчёта."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from src import __version__
from src.models.project import Project
from src.models.results import CalculationResult, VariantResult
from src.models.simulation import SimulationResult
from src.reports.formula_rendering import (
    pdf_formula_legend_markup,
    pdf_formula_markup,
    pdf_substitution_markup,
)


def _register_fonts() -> tuple[str, str]:
    regular_candidates = [
        Path("C:/Windows/Fonts/arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    bold_candidates = [
        Path("C:/Windows/Fonts/arialbd.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    regular = next((path for path in regular_candidates if path.exists()), None)
    bold = next((path for path in bold_candidates if path.exists()), None)
    if regular is None or bold is None:
        raise RuntimeError("Не найден шрифт с поддержкой кириллицы для PDF.")
    pdfmetrics.registerFont(TTFont("LTA-Regular", str(regular)))
    pdfmetrics.registerFont(TTFont("LTA-Bold", str(bold)))
    return "LTA-Regular", "LTA-Bold"


def build_pdf_report(
    project: Project,
    analytic: CalculationResult | None = None,
    simulation: SimulationResult | None = None,
    variants: list[VariantResult] | None = None,
) -> bytes:
    """Формирует PDF-отчёт с ключевыми исходными данными и результатами."""

    regular, bold = _register_fonts()
    stream = BytesIO()
    document = SimpleDocTemplate(
        stream,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=16 * mm,
        title=f"Анализ пассажиропотока — {project.metadata.name}",
        author=project.metadata.calculation_author,
    )
    base = getSampleStyleSheet()
    styles = {
        "title": ParagraphStyle(
            "LTA Title",
            parent=base["Title"],
            fontName=bold,
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#176B87"),
            alignment=TA_LEFT,
            spaceAfter=12,
        ),
        "h1": ParagraphStyle(
            "LTA H1",
            parent=base["Heading1"],
            fontName=bold,
            fontSize=15,
            leading=18,
            textColor=colors.HexColor("#176B87"),
            spaceBefore=10,
            spaceAfter=7,
        ),
        "body": ParagraphStyle(
            "LTA Body",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=9.5,
            leading=13,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=6,
        ),
        "small": ParagraphStyle(
            "LTA Small",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=8,
            leading=10,
        ),
        "formula_label": ParagraphStyle(
            "LTA Formula Label",
            parent=base["BodyText"],
            fontName=bold,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#5B6770"),
            spaceAfter=2,
        ),
        "formula": ParagraphStyle(
            "LTA Formula",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=13,
            leading=19,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#111827"),
            spaceBefore=2,
            spaceAfter=7,
        ),
        "formula_legend": ParagraphStyle(
            "LTA Formula Legend",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#374151"),
            spaceBefore=0,
            spaceAfter=6,
        ),
        "formula_source": ParagraphStyle(
            "LTA Formula Source",
            parent=base["BodyText"],
            fontName=regular,
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#6B7280"),
            spaceAfter=10,
        ),
        "table_header": ParagraphStyle(
            "LTA Table Header",
            parent=base["BodyText"],
            fontName=bold,
            fontSize=8,
            leading=10,
            textColor=colors.white,
        ),
    }

    def paragraph(text: object, style: str = "body", markup: bool = False) -> Paragraph:
        content = str(text) if markup else escape(str(text))
        return Paragraph(content, styles[style])

    def table(headers: list[str], rows: list[list[object]], widths: list[float]) -> Table:
        data = [[paragraph(item, "table_header") for item in headers]]
        data.extend([[paragraph(item, "small") for item in row] for row in rows])
        result = Table(data, colWidths=[value * mm for value in widths], repeatRows=1, hAlign="LEFT")
        result.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#176B87")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), bold),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#A9BBC4")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F7F9")]),
                ]
            )
        )
        return result

    is_gost = bool(
        analytic and analytic.calculation_basis == "GOST_34758_2021_CLAUSE_7"
    )
    if is_gost:
        failed = any(
            metric.compliance.value == "Не соответствует"
            for metric in analytic.metrics
        )
        status_text = (
            "<b>Статус:</b> выполнен расчётный метод ГОСТ 34758-2021; "
            f"результат — {'имеются несоответствия' if failed else 'критерии выполнены'}."
        )
        calculation_heading = "Расчёт по ГОСТ 34758-2021"
    else:
        status_text = (
            "<b>Важно:</b> нормативное соответствие не оценено до выполнения "
            "расчёта по верифицированной нормативной конфигурации."
        )
        calculation_heading = "Предварительный аналитический расчёт"

    story: list[object] = [
        paragraph("Анализ пассажиропотока<br/>лифтовой группы", "title", markup=True),
        paragraph(project.metadata.name),
        Spacer(1, 8 * mm),
        table(
            ["Поле", "Значение"],
            [
                ["Адрес", project.metadata.address or "не указан"],
                ["Тип здания", project.building.building_type.value],
                ["Стандарт", project.metadata.selected_standard.value],
                ["Дата", project.metadata.calculation_date.isoformat()],
            ],
            [45, 120],
        ),
        Spacer(1, 8 * mm),
        paragraph(status_text, markup=True),
        PageBreak(),
        paragraph("Исходные данные", "h1"),
        paragraph(
            f"Население: {project.population} чел. "
            f"Коэффициент заселённости: {project.building.occupancy_percent}%. "
            f"Этажей: {len(project.floors)}. "
            f"Лифтовых групп: {len(project.elevator_groups)}."
        ),
        table(
            ["Группа", "Лифты", "Основной этаж", "Этажи"],
            [
                [
                    group.name,
                    group.elevator_count,
                    group.main_floor,
                    ", ".join(map(str, group.served_floors)),
                ]
                for group in project.elevator_groups
            ],
            [42, 20, 28, 80],
        ),
        paragraph("<b>Параметры движения лифтов</b>", markup=True),
        table(
            ["Группа / лифт", "Ускорение, м/с²", "Замедление, м/с²", "Рывок, м/с³"],
            [
                [
                    f"{group.name} / {elevator.name}",
                    f"{elevator.acceleration_mps2:.2f}",
                    f"{elevator.deceleration_mps2:.2f}",
                    f"{elevator.jerk_mps3:.2f}",
                ]
                for group in project.elevator_groups
                for elevator in group.elevators
            ],
            [62, 36, 36, 30],
        ),
        paragraph(calculation_heading, "h1"),
    ]
    if analytic:
        story.append(
            table(
                ["Показатель", "Значение", "Единица", "Статус"],
                [
                    [metric.title_ru, f"{metric.value:.3f}", metric.unit, metric.compliance.value]
                    for metric in analytic.metrics
                ],
                [75, 28, 35, 30],
            )
        )
        story.append(paragraph("Формулы и трассировка", "h1"))
        for trace in analytic.formulas:
            source = trace.standard
            if trace.clause:
                source = f"{source}, {trace.clause}"
            story.append(
                KeepTogether(
                    [
                        paragraph(f"<b>{escape(trace.title_ru)}</b>", markup=True),
                        paragraph("Расчётная зависимость", "formula_label"),
                        paragraph(pdf_formula_markup(trace), "formula", markup=True),
                        paragraph(
                            pdf_formula_legend_markup(trace),
                            "formula_legend",
                            markup=True,
                        ),
                        paragraph("Подстановка значений", "formula_label"),
                        paragraph(
                            pdf_substitution_markup(trace),
                            "formula",
                            markup=True,
                        ),
                        paragraph(
                            f"<b>Результат:</b> {trace.result:.2f} "
                            f"{escape(trace.unit)}<br/>Источник: {escape(source)}.",
                            "formula_source",
                            markup=True,
                        ),
                    ]
                )
            )
    else:
        story.append(paragraph("Расчёт не приложен."))

    story.append(paragraph("Симуляция", "h1"))
    if simulation:
        story.append(
            table(
                ["Показатель", "Значение"],
                [
                    ["Среднее время ожидания пассажира (AWT)", f"{simulation.waiting_time.mean:.2f} с"],
                    [
                        "Ожидание 95% пассажиров, не более (P95)",
                        f"{simulation.waiting_time.percentile_95:.2f} с",
                    ],
                    [
                        "Среднее полное время до этажа назначения (TTD)",
                        f"{simulation.time_to_destination.mean:.2f} с",
                    ],
                    [
                        "Средняя / максимальная очередь, пассажиров",
                        f"{simulation.average_queue_length:.2f} / {simulation.maximum_queue_length}",
                    ],
                    [
                        "Перевезено / не обслужено пассажиров (в среднем за повтор)",
                        f"{simulation.transported_passengers} / {simulation.unserved_passengers}",
                    ],
                ],
                [100, 68],
            )
        )
    else:
        story.append(paragraph("Симуляция не выполнялась."))

    story.append(paragraph("Сравнение вариантов", "h1"))
    if variants:
        story.append(
            table(
                ["Вариант", "Лифты", "Г/п", "v", "I", "HC5", "Оценка"],
                [
                    [
                        item.variant_name,
                        item.elevator_count,
                        f"{item.capacity_kg:.0f}",
                        f"{item.speed_mps:.1f}",
                        f"{item.interval_s:.1f}",
                        f"{item.handling_capacity_5min:.1f}",
                        f"{item.score:.1f}",
                    ]
                    for item in variants
                ],
                [35, 17, 22, 17, 22, 25, 25],
            )
        )
    else:
        story.append(paragraph("Варианты не сохранены."))
    limitation_text = (
        "Расчётный метод ГОСТ применим к восходящему пику, одному нижнему входу, "
        "равномерному заселению и однородной группе. Формулы сверены с открытой "
        "публикацией; договорный отчёт требует контроля по экземпляру стандарта заказчика. "
        "Ориентировочное время ожидания не является нормативным критерием. "
        "Симуляция использует упрощённую диспетчеризацию; энергопотребление не рассчитывается."
        if analytic and analytic.calculation_basis == "GOST_34758_2021_CLAUSE_7"
        else (
            "Предварительный цикл не является нормативным RTT; симуляция использует "
            "упрощённую диспетчеризацию; энергопотребление не рассчитывается."
        )
    )
    story.extend(
        [
            paragraph("Ограничения", "h1"),
            paragraph(limitation_text),
            paragraph("Аудит", "h1"),
            paragraph(
                f"Версия приложения: {__version__}. "
                + (f"Хэш проекта: {analytic.audit.project_hash}." if analytic else "")
                + (
                    f" Seed: {simulation.seed}; повторов: {simulation.repetitions}."
                    if simulation
                    else ""
                )
            ),
        ]
    )

    def footer(canvas: object, doc: object) -> None:
        canvas.saveState()
        canvas.setFont(regular, 8)
        canvas.setFillColor(colors.HexColor("#5B6770"))
        canvas.drawString(18 * mm, 9 * mm, f"Lift Traffic Analyzer {__version__}")
        canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Стр. {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()
