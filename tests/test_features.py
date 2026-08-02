import pandas as pd

from src.features import add_lag_features, feature_row


def test_lag_features_do_not_read_current_day_demand():
    frame = pd.DataFrame({"stock_code": ["A"] * 15, "demand_date": pd.date_range("2024-01-01", periods=15), "daily_qty": range(15)})
    result = add_lag_features(frame)
    assert result.loc[14, "lag_1"] == 13
    assert result.loc[14, "lag_14"] == 0
    assert result.loc[14, "rolling_mean_7"] == sum(range(7, 14)) / 7


def test_recursive_feature_row_uses_only_history():
    result = feature_row(list(range(14)), pd.Timestamp("2024-02-01"))
    assert result["lag_1"] == 13
    assert result["lag_14"] == 0
