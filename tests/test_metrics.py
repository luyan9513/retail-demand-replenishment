import pytest

from src.metrics import forecast_bias, mae, smape, wape


def test_error_metrics_with_zero_demand_are_finite():
    actual = [0, 10, 0]
    predicted = [1, 8, 0]
    assert mae(actual, predicted) == pytest.approx(1.0)
    assert wape(actual, predicted) == pytest.approx(0.3)
    assert smape(actual, predicted) >= 0
    assert forecast_bias(actual, predicted) == pytest.approx(-0.1)


def test_wape_returns_none_for_all_zero_actuals():
    assert wape([0, 0], [1, 0]) is None
