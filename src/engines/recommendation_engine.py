"""Правиловая генерация некатегоричных инженерных рекомендаций."""

from __future__ import annotations

from src.models.results import (
    CalculationResult,
    ComplianceStatus,
    MessageSeverity,
    Recommendation,
)


class RecommendationEngine:
    """Формирует рекомендации только из наблюдаемых показателей и целей пользователя."""

    @staticmethod
    def generate(result: CalculationResult, targets: dict[str, float] | None = None) -> list[Recommendation]:
        """Возвращает прозрачный список рекомендаций."""

        targets = targets or {}
        recommendations: list[Recommendation] = []
        is_gost = result.calculation_basis == "GOST_34758_2021_CLAUSE_7"
        reserve = result.metric("reserve").value
        if reserve < 0:
            recommendations.append(
                Recommendation(
                    problem="Заданный пятиминутный поток выше предварительной провозной способности.",
                    metric="Резерв провозной способности",
                    target="Неотрицательный резерв относительно пользовательского потока",
                    actual=f"{reserve:.1f} %",
                    proposed_action=(
                        "Проверить увеличение количества лифтов, вместимости или зонирование; "
                        "подтвердить решение симуляцией."
                    ),
                    expected_effect="Снижение расчётной загрузки и очереди.",
                    limitations=(
                        "Вывод основан на расчётном методе ГОСТ и требует повторной проверки "
                        "после изменения конфигурации."
                        if is_gost
                        else "Вывод основан на предварительной, а не нормативной формуле."
                    ),
                    severity=MessageSeverity.WARNING,
                )
            )
        target_wait = targets.get("target_wait_s")
        wait = result.metric("average_wait_proxy").value
        if target_wait is not None and wait > target_wait:
            recommendations.append(
                Recommendation(
                    problem="Ориентировочное время ожидания выше цели пользователя.",
                    metric="Ориентировочное время ожидания, не менее",
                    target=f"≤ {target_wait:.1f} с",
                    actual=f"{wait:.1f} с",
                    proposed_action="Сравнить варианты с меньшим интервалом и выполнить симуляцию.",
                    expected_effect="Снижение среднего и хвостового времени ожидания.",
                    limitations="Показатель является ориентировочным и не заменяет нормативную оценку или AWT по симуляции.",
                    severity=MessageSeverity.WARNING,
                )
            )
        if is_gost:
            interval = result.metric("interval")
            if interval.compliance is ComplianceStatus.DOES_NOT_COMPLY:
                recommendations.append(
                    Recommendation(
                        problem="Интервал движения превышает критерий ГОСТ.",
                        metric=interval.title_ru,
                        target=interval.target_description or "",
                        actual=f"{interval.value:.1f} с",
                        proposed_action=(
                            "Проверить увеличение числа лифтов, уменьшение времени остановки "
                            "или зонирование; затем пересчитать вариант."
                        ),
                        expected_effect="Сокращение интервала отправления кабин.",
                        limitations="Изменение параметров должно быть подтверждено новым расчётом и симуляцией.",
                        severity=MessageSeverity.WARNING,
                    )
                )
            full_height = result.metric("full_height_time")
            if full_height.compliance is ComplianceStatus.DOES_NOT_COMPLY:
                recommendations.append(
                    Recommendation(
                        problem="Время движения на всю высоту превышает рекомендуемую верхнюю границу ГОСТ.",
                        metric=full_height.title_ru,
                        target=full_height.target_description or "",
                        actual=f"{full_height.value:.1f} с",
                        proposed_action="Подобрать номинальную скорость по формуле (1) и стандартному ряду скоростей.",
                        expected_effect="Сокращение времени движения до рекомендуемой верхней границы.",
                        limitations="Окончательная скорость выбирается с учётом оборудования и комфорта движения.",
                        severity=MessageSeverity.WARNING,
                    )
                )
        if not recommendations and is_gost:
            recommendations.append(
                Recommendation(
                    problem="Расчётные критерии ГОСТ для выбранной конфигурации выполнены.",
                    metric="Интервал, провозная способность и время движения",
                    target="Критерии таблиц 1 и 4",
                    actual="Соответствует",
                    proposed_action="Подтвердить решение моделированием и предметной проверкой отчёта.",
                    expected_effect="Проверка устойчивости решения при случайном пассажиропотоке.",
                    limitations=(
                        "Вывод действует только в области применимости расчётного метода: "
                        "восходящий пик, один нижний вход, равномерное заселение и однородная группа."
                    ),
                    severity=MessageSeverity.INFO,
                )
            )
        elif not recommendations:
            recommendations.append(
                Recommendation(
                    problem="Нормативные критерии не загружены.",
                    metric="Статус соответствия",
                    target="Верифицированная конфигурация ГОСТ",
                    actual="Не оценено",
                    proposed_action=(
                        "Проверить нормативную конфигурацию ГОСТ и выполнить "
                        "симуляцию пикового сценария."
                    ),
                    expected_effect="Появится доказуемая нормативная оценка и проверка устойчивости решения.",
                    limitations="До нормативного наполнения категоричный вывод о достаточности невозможен.",
                    severity=MessageSeverity.INFO,
                )
            )
        return recommendations
