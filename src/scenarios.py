"""把未来预测转换为可复现的默认补货情景表；所有库存参数均为显式假设。"""
from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import pandas as pd

from src.replenishment import simulate_replenishment


def build_scenarios(forecast: pd.DataFrame, lead_time_days: int, service_level: float, available_inventory: float,
                    holding_cost_per_unit: float, stockout_cost_per_unit: float) -> pd.DataFrame:
    required = {"stock_code", "forecast_date", "predicted_qty", "residual_sigma", "model_name", "demand_segment"}
    missing = required - set(forecast.columns)
    if missing:
        raise ValueError(f"未来预测文件缺少字段：{sorted(missing)}")
    rows = []
    for stock_code, group in forecast.sort_values("forecast_date").groupby("stock_code"):
        result = simulate_replenishment(group["predicted_qty"], float(group["residual_sigma"].iloc[0]), lead_time_days,
                                        service_level, available_inventory, holding_cost_per_unit, stockout_cost_per_unit)
        rows.append({"scenario_name": "默认参数化情景", "stock_code": stock_code, "model_name": group["model_name"].iloc[0],
                     "demand_segment": group["demand_segment"].iloc[0], "lead_time_days": lead_time_days,
                     "service_level": service_level, "residual_sigma_source": "所选模型滚动回测残差；不足时历史日销量标准差",
                     "inventory_assumption": "统一假设可用库存，非真实库存", **result})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="生成参数化补货情景（不是实际库存优化）")
    parser.add_argument("--forecast", type=Path, default=Path("data/processed/future_forecast.csv"))
    parser.add_argument("--database", type=Path, default=Path("data/retail.duckdb"))
    parser.add_argument("--output", type=Path, default=Path("data/processed/replenishment_scenarios.csv"))
    parser.add_argument("--lead-time-days", type=int, default=7)
    parser.add_argument("--service-level", type=float, default=0.95)
    parser.add_argument("--available-inventory", type=float, default=0.0, help="假设值；不是原始数据中的真实库存")
    parser.add_argument("--holding-cost-per-unit", type=float, default=0.0)
    parser.add_argument("--stockout-cost-per-unit", type=float, default=0.0)
    args = parser.parse_args()
    forecast = pd.read_csv(args.forecast, parse_dates=["forecast_date"])
    scenarios = build_scenarios(forecast, args.lead_time_days, args.service_level, args.available_inventory,
                                args.holding_cost_per_unit, args.stockout_cost_per_unit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    scenarios.to_csv(args.output, index=False)
    with duckdb.connect(str(args.database)) as connection:
        connection.register("scenario_frame", scenarios)
        connection.execute("CREATE OR REPLACE TABLE mart_replenishment_scenario AS SELECT * FROM scenario_frame")
    print(f"已生成 {len(scenarios)} 个 SKU 的参数化情景：{args.output}")


if __name__ == "__main__":
    main()
