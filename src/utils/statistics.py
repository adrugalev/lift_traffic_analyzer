"""Статистические функции для результатов симуляции."""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

from src.models.simulation import SimulationStatistics


def describe(values: Sequence[float]) -> SimulationStatistics:
    """Рассчитывает описательную статистику и 95%-й интервал среднего."""

    data = np.asarray(values, dtype=float)
    if data.size == 0:
        data = np.asarray([0.0], dtype=float)
    mean = float(np.mean(data))
    std = float(np.std(data, ddof=1)) if data.size > 1 else 0.0
    half_width = 1.96 * std / math.sqrt(data.size) if data.size > 1 else 0.0
    return SimulationStatistics(
        mean=mean,
        median=float(np.median(data)),
        std=std,
        percentile_80=float(np.percentile(data, 80)),
        percentile_90=float(np.percentile(data, 90)),
        percentile_95=float(np.percentile(data, 95)),
        percentile_99=float(np.percentile(data, 99)),
        confidence_interval_95_low=mean - half_width,
        confidence_interval_95_high=mean + half_width,
        minimum=float(np.min(data)),
        maximum=float(np.max(data)),
    )

