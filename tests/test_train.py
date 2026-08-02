import pandas as pd

from src.train import create_future_forecast, select_models


def test_croston_is_only_eligible_for_intermittent_skus():
    metrics = pd.DataFrame([
        {"stock_code": "stable", "model_name": "croston_sba", "demand_segment": "稳定型", "wape": 0.1, "mae": 1, "forecast_bias": 0, "observations": 21},
        {"stock_code": "stable", "model_name": "moving_average", "demand_segment": "稳定型", "wape": 0.2, "mae": 2, "forecast_bias": 0, "observations": 21},
        {"stock_code": "tail", "model_name": "croston_sba", "demand_segment": "间歇/长尾型", "wape": 0.1, "mae": 1, "forecast_bias": 0, "observations": 21},
        {"stock_code": "tail", "model_name": "moving_average", "demand_segment": "间歇/长尾型", "wape": 0.2, "mae": 2, "forecast_bias": 0, "observations": 21},
    ])
    selected = select_models(metrics)
    assert selected.set_index("stock_code").loc["stable", "selected_model"] == "moving_average"
    assert selected.set_index("stock_code").loc["tail", "selected_model"] == "croston_sba"


def test_future_hgb_is_generated_by_global_path(monkeypatch):
    dates = pd.date_range("2024-01-01", periods=30)
    daily = pd.concat([
        pd.DataFrame({"stock_code": sku, "demand_date": dates, "daily_qty": [float(index % 5) for index in range(30)], "demand_segment": "稳定型"})
        for sku in ("A", "B")
    ], ignore_index=True)
    selected = pd.DataFrame([{"stock_code": "A", "selected_model": "hist_gradient_boosting", "selected_wape": 0.1, "selected_mae": 1, "selected_bias": 0}])
    backtest = pd.DataFrame([{"stock_code": "A", "model_name": "hist_gradient_boosting", "residual": 1.0}])
    monkeypatch.setattr("src.train.global_machine_learning_forecasts", lambda histories, first_dates, horizon: {key: [7.0] * horizon for key in histories})
    future = create_future_forecast(daily, selected, backtest, horizon_days=2)
    assert future["predicted_qty"].tolist() == [7.0, 7.0]
