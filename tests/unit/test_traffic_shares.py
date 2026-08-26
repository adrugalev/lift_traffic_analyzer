"""Тесты зависимых долей направлений пассажиропотока."""

import pytest

from src.utils.traffic_shares import shares_from_incoming, shares_from_interfloor


def test_incoming_change_resets_interfloor_and_calculates_outgoing() -> None:
    assert shares_from_incoming(80) == (80, 20, 0)


def test_interfloor_change_keeps_incoming_and_reduces_outgoing() -> None:
    assert shares_from_interfloor(80, 7) == (80, 13, 7)


@pytest.mark.parametrize("incoming", [-1, 101])
def test_incoming_rejects_out_of_range_value(incoming: int) -> None:
    with pytest.raises(ValueError):
        shares_from_incoming(incoming)


@pytest.mark.parametrize("interfloor", [-1, 21])
def test_interfloor_rejects_value_outside_available_remainder(interfloor: int) -> None:
    with pytest.raises(ValueError):
        shares_from_interfloor(80, interfloor)
