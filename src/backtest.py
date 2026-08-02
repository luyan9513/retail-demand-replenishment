"""按时间滚动回测 SKU 级需求模型；不允许随机拆分。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from src.features import feature_row
from src.metrics import forecast_bias, mae, smape, wape

FEATURE_COLUMNS = ["lag_1", "lag_7", "lag_14", "rolling_mean_7", "rolling_mean_14", "rolling_std_7", "day_of_week", "month"]


@dataclass(frozen=True)
class BacktestConfig:
    horizon_days: int = 7
    n_windows: int = 3
    min_train_days: int = 28
    moving_average_days: int = 7


def rolling_origins(dates: Iterable[pd.Timestamp], config: BacktestConfig | None = None) -> list[pd.Timestamp]:
    config = config or BacktestConfig()
    index = pd.DatetimeIndex(pd.to_datetime(list(dates)).unique()).sort_values()
    required = config.min_train_days + config.horizon_days * config.n_windows
    if len(index) < required:
        return []
    first_origin_index = len(index) - config.horizon_days * config.n_windows - 1
    return [pd.Timestamp(index[first_origin_index + config.horizon_days * step]) for step in range(config.n_windows)]


def seasonal_naive(history: list[float], horizon_days: int) -> list[float]:
    if not history:
        raise ValueError("seasonal naive 至少需要一天历史")
    output = []
    for step in range(horizon_days):
        position = len(history) - 7 + step
        output.append(max(0.0, history[position] if position >= 0 else history[-1]))
    return output


def moving_average(history: list[float], horizon_days: int, window: int = 7) -> list[float]:
    if not history:
        raise ValueError("移动平均至少需要一天历史")
    return [max(0.0, float(np.mean(history[-window:]))) for _ in range(horizon_days)]


def _training_matrix(history: list[float], first_date: pd.Timestamp) -> tuple[pd.DataFrame, np.ndarray]:
    rows, targets = [], []
    for index in range(14, len(history)):
        rows.append(feature_row(history[:index], first_date + pd.Timedelta(days=index)))
        targets.append(history[index])
    return pd.DataFrame(rows, columns=FEATURE_COLUMNS), np.asarray(targets, dtype=float)


def _make_hgb() -> HistGradientBoostingRegressor:
    """受限复杂度的候选模型：回测优先保证可复现和可在本地完成。"""
    return HistGradientBoostingRegressor(
        max_iter=40,
        learning_rate=0.12,
        max_leaf_nodes=7,
        max_bins=64,
        min_samples_leaf=20,
        l2_regularization=1.0,
        early_stopping=False,
        random_state=42,
    )


def machine_learning_forecast(history: list[float], first_date: pd.Timestamp, horizon_days: int) -> list[float]:
    x_train, y_train = _training_matrix(history, first_date)
    if len(x_train) < 14:
        return moving_average(history, horizon_days)
    model = _make_hgb()
    model.fit(x_train, y_train)
    recursive_history = history.copy()
    forecast: list[float] = []
    for step in range(horizon_days):
        date = first_date + pd.Timedelta(days=len(history) + step)
        predicted = float(model.predict(pd.DataFrame([feature_row(recursive_history, date)], columns=FEATURE_COLUMNS))[0])
        predicted = max(0.0, predicted)
        forecast.append(predicted)
        recursive_history.append(predicted)
    return forecast


def global_machine_learning_forecasts(
    histories: dict[str, list[float]], first_dates: dict[str, pd.Timestamp], horizon_days: int,
) -> dict[str, list[float]]:
    """每个滚动窗口只拟合一次共享 HGB，并通过 SKU one-hot 特征区分商品。"""
    feature_frames: list[pd.DataFrame] = []
    targets: list[np.ndarray] = []
    for stock_code, history in histories.items():
        x_train, y_train = _training_matrix(history, first_dates[stock_code])
        if len(x_train) < 14:
            continue
        x_train["sku_id"] = stock_code
        feature_frames.append(x_train)
        targets.append(y_train)
    if not feature_frames:
        return {stock_code: moving_average(history, horizon_days) for stock_code, history in histories.items()}
    training = pd.concat(feature_frames, ignore_index=True)
    encoded_training = pd.get_dummies(training, columns=["sku_id"], dtype=float)
    model = _make_hgb()
    model.fit(encoded_training, np.concatenate(targets))
    forecasts: dict[str, list[float]] = {}
    for stock_code, history in histories.items():
        recursive_history = history.copy()
        values: list[float] = []
        for step in range(horizon_days):
            date = first_dates[stock_code] + pd.Timedelta(days=len(history) + step)
            row = pd.DataFrame([feature_row(recursive_history, date)])
            row["sku_id"] = stock_code
            encoded_row = pd.get_dummies(row, columns=["sku_id"], dtype=float).reindex(columns=encoded_training.columns, fill_value=0.0)
            predicted = max(0.0, float(model.predict(encoded_row)[0]))
            values.append(predicted)
            recursive_history.append(predicted)
        forecasts[stock_code] = values
    return forecasts


def _predict(model_name: str, history: list[float], first_date: pd.Timestamp, config: BacktestConfig) -> list[float]:
    if model_name == "seasonal_naive":
        return seasonal_naive(history, config.horizon_days)
    if model_name == "moving_average":
        return moving_average(history, config.horizon_days, config.moving_average_days)
    if model_name == "hist_gradient_boosting":
        return machine_learning_forecast(history, first_date, config.horizon_days)
    raise ValueError(f"未知模型：{model_name}")


def run_backtest(daily: pd.DataFrame, config: BacktestConfig | None = None, models: tuple[str, ...] = ("seasonal_naive", "moving_average", "hist_gradient_boosting")) -> pd.DataFrame:
    config = config or BacktestConfig()
    required = {"stock_code", "demand_date", "daily_qty"}
    missing = required - set(daily.columns)
    if missing:
        raise ValueError(f"回测缺少字段：{sorted(missing)}")
    rows: list[dict[str, object]] = []
    prepared_groups = {str(stock_code): group.sort_values("demand_date").reset_index(drop=True)
                       for stock_code, group in daily.groupby("stock_code")}
    all_dates = pd.to_datetime(daily["demand_date"])
    origins = rolling_origins(all_dates, config)
    for window_number, origin in enumerate(origins, start=1):
        eligible: list[tuple[str, pd.DataFrame, pd.DataFrame, pd.Timestamp, str]] = []
        histories: dict[str, list[float]] = {}
        first_dates: dict[str, pd.Timestamp] = {}
        for stock_code, group in prepared_groups.items():
            dates = pd.to_datetime(group["demand_date"])
            train = group.loc[dates <= origin]
            test = group.loc[(dates > origin) & (dates <= origin + pd.Timedelta(days=config.horizon_days))]
            if len(train) < config.min_train_days or len(test) != config.horizon_days:
                continue
            first_date = pd.Timestamp(dates.iloc[0])
            segment = group["demand_segment"].iloc[0] if "demand_segment" in group else "未分层"
            eligible.append((stock_code, train, test, first_date, segment))
            histories[stock_code] = train["daily_qty"].astype(float).tolist()
            first_dates[stock_code] = first_date
        ml_predictions = global_machine_learning_forecasts(histories, first_dates, config.horizon_days) if "hist_gradient_boosting" in models else {}
        for stock_code, train, test, first_date, segment in eligible:
            history = histories[stock_code]
            predictions_by_model = {
                model_name: (ml_predictions[stock_code] if model_name == "hist_gradient_boosting"
                             else _predict(model_name, history, first_date, config))
                for model_name in models
            }
            for model_name, predictions in predictions_by_model.items():
                for date, actual, predicted in zip(pd.to_datetime(test["demand_date"]), test["daily_qty"], predictions):
                    rows.append({"stock_code": stock_code, "forecast_origin": origin, "forecast_date": date,
                                 "window_number": window_number, "model_name": model_name, "actual_qty": float(actual),
                                 "predicted_qty": float(predicted), "residual": float(actual) - float(predicted),
                                 "demand_segment": segment})
    return pd.DataFrame(rows)


def metric_summary(predictions: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if predictions.empty:
        return pd.DataFrame(columns=[*group_columns, "mae", "wape", "smape", "forecast_bias", "observations"])
    rows = []
    for keys, group in predictions.groupby(group_columns, dropna=False):
        keys = (keys,) if not isinstance(keys, tuple) else keys
        actual, predicted = group["actual_qty"], group["predicted_qty"]
        rows.append(dict(zip(group_columns, keys), mae=mae(actual, predicted), wape=wape(actual, predicted),
                         smape=smape(actual, predicted), forecast_bias=forecast_bias(actual, predicted), observations=len(group)))
    return pd.DataFrame(rows)
