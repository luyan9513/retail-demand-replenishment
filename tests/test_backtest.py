import pandas as pd
import pytest

from src.backtest import BacktestConfig, croston_sba, global_machine_learning_forecasts, rolling_origins


def test_rolling_origins_are_time_ordered_and_leave_full_horizons():
    dates = pd.date_range("2024-01-01", periods=60)
    config = BacktestConfig(horizon_days=7, n_windows=3, min_train_days=28)
    origins = rolling_origins(dates, config)
    assert len(origins) == 3
    assert origins == sorted(origins)
    assert (dates[-1] - origins[-1]).days == 7


def test_rolling_origins_reject_insufficient_history():
    assert rolling_origins(pd.date_range("2024-01-01", periods=30), BacktestConfig()) == []


def test_croston_sba_returns_nonnegative_constant_rate_for_intermittent_history():
    forecast = croston_sba([0, 0, 4, 0, 0, 0, 2, 0, 0, 3], horizon_days=3, alpha=0.1)
    assert len(forecast) == 3
    assert forecast[0] == pytest.approx(forecast[1])
    assert forecast[0] > 0


def test_global_hgb_falls_back_for_sku_with_less_than_14_days():
    histories = {
        "long": [float(day % 5 + 1) for day in range(35)],
        "short": [2.0, 4.0, 6.0],
    }
    first_dates = {"long": pd.Timestamp("2024-01-01"), "short": pd.Timestamp("2024-02-01")}
    forecasts = global_machine_learning_forecasts(histories, first_dates, horizon_days=3)
    assert forecasts["short"] == [4.0, 4.0, 4.0]
    assert len(forecasts["long"]) == 3
