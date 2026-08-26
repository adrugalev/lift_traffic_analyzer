"""Unit-тесты статистических показателей."""

from __future__ import annotations

import pytest

from src.utils.statistics import describe


def test_describe_known_values() -> None:
    result = describe([1.0, 2.0, 3.0, 4.0, 5.0])
    assert result.mean == pytest.approx(3.0)
    assert result.median == pytest.approx(3.0)
    assert result.percentile_95 == pytest.approx(4.8)
    assert result.minimum == 1.0
    assert result.maximum == 5.0


def test_describe_empty_sequence_is_safe() -> None:
    result = describe([])
    assert result.mean == 0.0
    assert result.std == 0.0

