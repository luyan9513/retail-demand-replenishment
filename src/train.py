"""运行回测、选择每个 SKU 的最优策略并生成未来 7 天预测。"""
from __future__ import annotations

import argparse
from datetime import timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from src.backtest import BacktestConfig, croston_sba, global_machine_learning_forecasts, metric_summary, moving_average, run_backtest, seasonal_naive


def _future_prediction(model_name: str, history: list[float], first_date: pd.Timestamp, horizon_days: int) -> list[float]:
    if model_name == "seasonal_naive":
        return seasonal_naive(history, horizon_days)
    if model_name == "moving_average":
        return moving_average(history, horizon_days)
    if model_name == "croston_sba":
        return croston_sba(history, horizon_days)
    if model_name == "hist_gradient_boosting":
        raise ValueError("未来 HGB 预测必须由共享全局 HGB 路径生成")
    raise ValueError(f"未知模型：{model_name}")


def select_models(metrics: pd.DataFrame, min_observations: int = 21) -> pd.DataFrame:
    """仅在完成全部 3×7 天回测的 SKU 中按低 WAPE 选模型。"""
    if metrics.empty:
        return pd.DataFrame(columns=["stock_code", "selected_model", "selected_wape", "selected_mae", "selected_bias"])
    ranking = metrics[metrics["observations"] >= min_observations].copy()
    ranking = ranking[(ranking["demand_segment"] == "间歇/长尾型") | (ranking["model_name"] != "croston_sba")]
    if ranking.empty:
        return pd.DataFrame(columns=["stock_code", "selected_model", "selected_wape", "selected_mae", "selected_bias"])
    ranking["wape_sort"] = ranking["wape"].fillna(np.inf)
    ranking["bias_sort"] = ranking["forecast_bias"].abs().fillna(np.inf)
    ranking = ranking.sort_values(["stock_code", "wape_sort", "mae", "bias_sort", "model_name"])
    selected = ranking.groupby("stock_code", as_index=False).first()
    return selected.rename(columns={"model_name": "selected_model", "wape": "selected_wape", "mae": "selected_mae", "forecast_bias": "selected_bias"})[
        ["stock_code", "selected_model", "selected_wape", "selected_mae", "selected_bias"]
    ]


def create_future_forecast(daily: pd.DataFrame, selected: pd.DataFrame, backtest_predictions: pd.DataFrame, horizon_days: int = 7) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    selected_map = selected.set_index("stock_code").to_dict("index") if not selected.empty else {}
    grouped_daily = {str(stock_code): group.sort_values("demand_date") for stock_code, group in daily.groupby("stock_code")}
    hgb_selected = {stock_code for stock_code, item in selected_map.items() if item["selected_model"] == "hist_gradient_boosting"}
    global_hgb_predictions: dict[str, list[float]] = {}
    if hgb_selected:
        histories = {stock_code: group["daily_qty"].astype(float).tolist() for stock_code, group in grouped_daily.items()}
        first_dates = {stock_code: pd.Timestamp(group["demand_date"].iloc[0]) for stock_code, group in grouped_daily.items()}
        global_hgb_predictions = global_machine_learning_forecasts(histories, first_dates, horizon_days)
    for stock_code, group in grouped_daily.items():
        if stock_code not in selected_map:
            continue
        group = group.sort_values("demand_date")
        history = group["daily_qty"].astype(float).tolist()
        first_date = pd.Timestamp(group["demand_date"].iloc[0])
        last_date = pd.Timestamp(group["demand_date"].iloc[-1])
        model_name = str(selected_map[stock_code]["selected_model"])
        values = global_hgb_predictions[stock_code] if model_name == "hist_gradient_boosting" else _future_prediction(model_name, history, first_date, horizon_days)
        residuals = backtest_predictions.loc[
            (backtest_predictions["stock_code"] == stock_code) & (backtest_predictions["model_name"] == model_name), "residual"
        ]
        residual_sigma = float(residuals.std(ddof=0)) if len(residuals) >= 2 else float(group["daily_qty"].std(ddof=0))
        for step, predicted in enumerate(values, start=1):
            rows.append({"stock_code": stock_code, "forecast_origin": last_date, "forecast_date": last_date + timedelta(days=int(step)),
                         "horizon_day": step, "model_name": model_name, "predicted_qty": max(0.0, float(predicted)),
                         "residual_sigma": max(0.0, residual_sigma), "demand_segment": group["demand_segment"].iloc[0]})
    return pd.DataFrame(rows)


def run_training(database_path: Path, output_dir: Path, top_skus: int = 30) -> dict[str, int]:
    output_dir.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(database_path), read_only=True) as connection:
        daily = connection.execute(
            "SELECT * FROM mart_sku_daily_demand ORDER BY stock_code, demand_date"
        ).fetchdf()
    if daily.empty:
        raise ValueError("mart_sku_daily_demand 为空；请先完成数据导入和 dbt run")
    value_rank = daily.groupby("stock_code", as_index=False)["daily_revenue"].sum().sort_values("daily_revenue", ascending=False)
    selected_codes = value_rank.head(top_skus)["stock_code"].tolist()
    daily = daily[daily["stock_code"].isin(selected_codes)].copy()
    predictions = run_backtest(daily, BacktestConfig())
    sku_metrics = metric_summary(predictions, ["stock_code", "model_name", "demand_segment"])
    model_metrics = metric_summary(predictions, ["model_name"])
    segment_metrics = metric_summary(predictions, ["demand_segment", "model_name"])
    window_metrics = metric_summary(predictions, ["window_number", "model_name"])
    selected = select_models(sku_metrics, min_observations=BacktestConfig().horizon_days * BacktestConfig().n_windows)
    future = create_future_forecast(daily, selected, predictions)
    for name, frame in {"daily_demand": daily, "backtest_predictions": predictions, "sku_model_metrics": sku_metrics,
                        "model_metrics": model_metrics, "segment_model_metrics": segment_metrics,
                        "window_model_metrics": window_metrics, "selected_models": selected,
                        "future_forecast": future}.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False)
    with duckdb.connect(str(database_path)) as connection:
        connection.register("forecast_frame", future)
        connection.execute("CREATE OR REPLACE TABLE mart_sku_forecast AS SELECT * FROM forecast_frame")
    return {"candidate_skus": len(selected_codes), "eligible_skus": len(selected), "backtest_rows": len(predictions), "future_rows": len(future)}


def main() -> None:
    parser = argparse.ArgumentParser(description="执行滚动回测并生成 SKU 未来 7 天预测")
    parser.add_argument("--database", type=Path, default=Path("data/retail.duckdb"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--top-skus", type=int, default=30, choices=range(20, 51))
    args = parser.parse_args()
    result = run_training(args.database, args.output_dir, args.top_skus)
    print("训练完成：" + ", ".join(f"{key}={value}" for key, value in result.items()))


if __name__ == "__main__":
    main()
