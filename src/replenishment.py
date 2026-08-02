"""参数化补货情景模拟，不包含真实库存优化声明。"""
from __future__ import annotations

from statistics import NormalDist
from typing import Iterable

import numpy as np


def service_level_z(service_level: float) -> float:
    if not 0.5 <= service_level < 1:
        raise ValueError("服务水平必须在 50%（含）到 100%（不含）之间")
    return float(NormalDist().inv_cdf(service_level))


def lead_time_demand(forecast: Iterable[float], lead_time_days: int) -> float:
    values = np.maximum(np.asarray(list(forecast), dtype=float), 0)
    if lead_time_days < 1:
        raise ValueError("提前期必须至少为 1 天")
    if values.size == 0:
        raise ValueError("至少需要一个预测值")
    if lead_time_days <= values.size:
        return float(values[:lead_time_days].sum())
    return float(values.mean() * lead_time_days)


def safety_stock(demand_sigma: float, lead_time_days: int, service_level: float) -> float:
    if demand_sigma < 0:
        raise ValueError("需求标准差不能为负")
    return max(0.0, service_level_z(service_level) * demand_sigma * np.sqrt(lead_time_days))


def simulate_replenishment(
    forecast: Iterable[float],
    residual_sigma: float,
    lead_time_days: int,
    service_level: float,
    available_inventory: float,
    holding_cost_per_unit: float = 0.0,
    stockout_cost_per_unit: float = 0.0,
) -> dict[str, float]:
    if available_inventory < 0:
        raise ValueError("假设可用库存不能为负")
    lead_demand = lead_time_demand(forecast, lead_time_days)
    stock = safety_stock(residual_sigma, lead_time_days, service_level)
    reorder_point = lead_demand + stock
    order_qty = float(np.ceil(max(0.0, reorder_point - available_inventory)))
    return {
        "lead_time_demand": lead_demand,
        "safety_stock": stock,
        "reorder_point": reorder_point,
        "available_inventory": float(available_inventory),
        "recommended_order_qty": order_qty,
        "holding_cost_proxy": stock * max(0.0, holding_cost_per_unit),
        "stockout_cost_proxy": max(0.0, reorder_point - available_inventory) * max(0.0, stockout_cost_per_unit),
    }


def sensitivity_analysis(
    forecast: Iterable[float], residual_sigma: float, available_inventory: float,
    lead_times: Iterable[int], service_levels: Iterable[float],
    holding_costs: Iterable[float], stockout_costs: Iterable[float],
) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for lead_time in lead_times:
        for service_level in service_levels:
            for holding_cost in holding_costs:
                for stockout_cost in stockout_costs:
                    row = simulate_replenishment(
                        forecast, residual_sigma, lead_time, service_level, available_inventory,
                        holding_cost, stockout_cost,
                    )
                    rows.append({"lead_time_days": lead_time, "service_level": service_level,
                                 "holding_cost_per_unit": holding_cost, "stockout_cost_per_unit": stockout_cost, **row})
    return rows


def portfolio_sensitivity(
    forecasts_by_sku: dict[str, tuple[Iterable[float], float]], available_inventory: float,
    lead_times: Iterable[int], service_levels: Iterable[float],
    holding_cost_per_unit: float, stockout_cost_per_unit: float,
) -> list[dict[str, float]]:
    """聚合全 SKU 的参数情景，用理论补货缺口数量作为复核风险覆盖代理。"""
    rows: list[dict[str, float]] = []
    for lead_time in lead_times:
        for service_level in service_levels:
            scenarios = [
                simulate_replenishment(
                    forecast, residual_sigma, lead_time, service_level, available_inventory,
                    holding_cost_per_unit, stockout_cost_per_unit,
                )
                for forecast, residual_sigma in forecasts_by_sku.values()
            ]
            rows.append({
                "lead_time_days": lead_time,
                "service_level": service_level,
                "total_recommended_order_qty": float(sum(item["recommended_order_qty"] for item in scenarios)),
                "high_risk_sku_count": float(sum(item["recommended_order_qty"] > 0 for item in scenarios)),
                "total_holding_cost_proxy": float(sum(item["holding_cost_proxy"] for item in scenarios)),
                "total_stockout_cost_proxy": float(sum(item["stockout_cost_proxy"] for item in scenarios)),
            })
    return rows
