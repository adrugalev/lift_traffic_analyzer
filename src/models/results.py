"""Модели аналитических результатов, сравнений и рекомендаций."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MessageSeverity(StrEnum):
    """Уровень диагностического сообщения."""

    ERROR = "Ошибка"
    WARNING = "Предупреждение"
    INFO = "Информация"


class ComplianceStatus(StrEnum):
    """Статус нормативной оценки."""

    COMPLIES = "Соответствует"
    DOES_NOT_COMPLY = "Не соответствует"
    NOT_ASSESSED = "Не оценено"


class DiagnosticMessage(BaseModel):
    """Инженерное сообщение о качестве исходных данных или результата."""

    severity: MessageSeverity
    code: str
    text: str
    field_path: str | None = None


class FormulaTrace(BaseModel):
    """Трассировка формулы с исходными и промежуточными значениями."""

    formula_id: str
    title_ru: str
    expression: str
    substituted_expression: str
    variables: dict[str, Any] = Field(default_factory=dict)
    intermediate_values: dict[str, Any] = Field(default_factory=dict)
    result: float
    unit: str
    standard: str
    clause: str | None = None
    status: str = "engineering_preview"
    warnings: list[str] = Field(default_factory=list)


class MetricResult(BaseModel):
    """Единичный расчётный показатель."""

    key: str
    title_ru: str
    value: float
    unit: str
    method: str
    compliance: ComplianceStatus = ComplianceStatus.NOT_ASSESSED
    target_value: float | None = None
    target_description: str | None = None


class Recommendation(BaseModel):
    """Прозрачная инженерная рекомендация."""

    problem: str
    metric: str
    target: str
    actual: str
    proposed_action: str
    expected_effect: str
    limitations: str
    severity: MessageSeverity = MessageSeverity.INFO


class AuditRecord(BaseModel):
    """Реквизиты воспроизводимости расчёта."""

    application_version: str
    configuration_version: str
    project_hash: str
    calculated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    random_seed: int | None = None
    repetitions: int | None = None


class CalculationResult(BaseModel):
    """Результат предварительного или нормативного аналитического расчёта."""

    method: str
    calculation_basis: str
    group_id: str
    standard: str
    metrics: list[MetricResult]
    formulas: list[FormulaTrace]
    messages: list[DiagnosticMessage] = Field(default_factory=list)
    recommendations: list[Recommendation] = Field(default_factory=list)
    audit: AuditRecord

    def metric(self, key: str) -> MetricResult:
        """Возвращает показатель по машинному ключу."""

        for metric in self.metrics:
            if metric.key == key:
                return metric
        raise KeyError(key)


class VariantResult(BaseModel):
    """Показатели одного варианта лифтовой группы."""

    variant_name: str
    elevator_count: int
    capacity_kg: float
    speed_mps: float
    interval_s: float
    handling_capacity_5min: float
    average_wait_s: float
    reserve_percent: float
    compliance: ComplianceStatus
    score: float
    category: str = "Допустимый вариант"

