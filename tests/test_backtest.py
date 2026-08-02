import pandas as pd

from src.backtest import BacktestConfig, rolling_origins


def test_rolling_origins_are_time_ordered_and_leave_full_horizons():
    dates = pd.date_range("2024-01-01", periods=60)
    config = BacktestConfig(horizon_days=7, n_windows=3, min_train_days=28)
    origins = rolling_origins(dates, config)
    assert len(origins) == 3
    assert origins == sorted(origins)
    assert (dates[-1] - origins[-1]).days == 7


def test_rolling_origins_reject_insufficient_history():
    assert rolling_origins(pd.date_range("2024-01-01", periods=30), BacktestConfig()) == []
