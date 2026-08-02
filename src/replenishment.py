"""参数化补货情景模拟：库存位置、供应约束和成本均为显式输入，不代表真实优化。"""
from __future__ import annotations

from statistics import NormalDist
from typing import Iterable

import numpy as np


def _nonnegative(name: str, value: float) -> float:
    numeric = float(value)
    if numeric < 0:
        raise ValueError(f"{name}不能为负")
    return numeric


def service_level_z(service_level: float) -> float:
    if not 0.5 <= service_level < 1:
        raise ValueError("服务水平必须在 50%（含）到 100%（不含）之间")
    return float(NormalDist().inv_cdf(service_level))


def inventory_position(
    on_hand_inventory: float,
    inbound_inventory: float = 0.0,
    reserved_inventory: float = 0.0,
    backorder_qty: float = 0.0,
) -> float:
    """库存位置 = 现货 + 在途 − 已预留 − 已欠交；允许为负，表示已被需求占用。"""
    return (
        _nonnegative("现货库存", on_hand_inventory)
        + _nonnegative("在途库存", inbound_inventory)
        - _nonnegative("已预留库存", reserved_inventory)
        - _nonnegative("已欠交数量", backorder_qty)
    )


def lead_time_demand(forecast: Iterable[float], lead_time_days: int) -> float:
    values = np.maximum(np.asarray(list(forecast), dtype=float), 0)
    if lead_time_days < 1:
        raise ValueError("提前期必须至少为 1 天")
    if values.size == 0:
        raise ValueError("至少需要一个预测值")
    if lead_time_days <= values.size:
        return float(values[:lead_time_days].sum())
    return float(values.mean() * lead_time_days)


def safety_stock(
    demand_sigma: float,
    lead_time_days: int,
    service_level: float,
    mean_daily_demand: float = 0.0,
    lead_time_std_days: float = 0.0,
) -> float:
    """同时考虑需求误差和提前期波动的正态近似安全库存。"""
    sigma = _nonnegative("需求标准差", demand_sigma)
    mean_demand = _nonnegative("日均预测需求", mean_daily_demand)
    lead_time_std = _nonnegative("提前期标准差", lead_time_std_days)
    if lead_time_days < 1:
        raise ValueError("提前期必须至少为 1 天")
    variance = lead_time_days * sigma**2 + mean_demand**2 * lead_time_std**2
    return max(0.0, service_level_z(service_level) * np.sqrt(variance))


def constrained_order_quantity(shortfall: float, min_order_qty: float = 0.0, pack_size: float = 1.0) -> float:
    """将理论缺口转为 MOQ/包装倍数约束下的建议量；无缺口时不因 MOQ 强制下单。"""
    unconstrained = _nonnegative("理论缺口", shortfall)
    minimum = _nonnegative("最小订货量", min_order_qty)
    pack = float(pack_size)
    if pack <= 0:
        raise ValueError("包装倍数必须大于 0")
    if unconstrained == 0:
        return 0.0
    return float(np.ceil(max(unconstrained, minimum) / pack) * pack)


def simulate_replenishment(
    forecast: Iterable[float],
    residual_sigma: float,
    lead_time_days: int,
    service_level: float,
    on_hand_inventory: float,
    inbound_inventory: float = 0.0,
    reserved_inventory: float = 0.0,
    backorder_qty: float = 0.0,
    min_order_qty: float = 0.0,
    pack_size: float = 1.0,
    lead_time_std_days: float = 0.0,
    holding_cost_per_unit: float = 0.0,
    stockout_cost_per_unit: float = 0.0,
) -> dict[str, float]:
    values = np.maximum(np.asarray(list(forecast), dtype=float), 0)
    if values.size == 0:
        raise ValueError("至少需要一个预测值")
    lead_demand = lead_time_demand(values, lead_time_days)
    mean_daily_demand = float(values.mean())
    stock = safety_stock(residual_sigma, lead_time_days, service_level, mean_daily_demand, lead_time_std_days)
    reorder_point = lead_demand + stock
    position = inventory_position(on_hand_inventory, inbound_inventory, reserved_inventory, backorder_qty)
    shortfall = max(0.0, reorder_point - position)
    order_qty = constrained_order_quantity(shortfall, min_order_qty, pack_size)
    return {
        "lead_time_demand": lead_demand,
        "mean_daily_forecast": mean_daily_demand,
        "safety_stock": stock,
        "reorder_point": reorder_point,
        "on_hand_inventory": float(on_hand_inventory),
        "inbound_inventory": float(inbound_inventory),
        "reserved_inventory": float(reserved_inventory),
        "backorder_qty": float(backorder_qty),
        "inventory_position": position,
        "lead_time_std_days": float(lead_time_std_days),
        "min_order_qty": float(min_order_qty),
        "pack_size": float(pack_size),
        "unconstrained_order_qty": shortfall,
        "recommended_order_qty": order_qty,
        "holding_cost_proxy": stock * _nonnegative("单位持有成本", holding_cost_per_unit),
        "stockout_cost_proxy": shortfall * _nonnegative("单位缺货成本", stockout_cost_per_unit),
    }


def sensitivity_analysis(
    forecast: Iterable[float],
    residual_sigma: float,
    on_hand_inventory: float,
    lead_times: Iterable[int],
    service_levels: Iterable[float],
    holding_costs: Iterable[float],
    stockout_costs: Iterable[float],
    inbound_inventory: float = 0.0,
    reserved_inventory: float = 0.0,
    backorder_qty: float = 0.0,
    min_order_qty: float = 0.0,
    pack_size: float = 1.0,
    lead_time_std_days: float = 0.0,
) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    for lead_time in lead_times:
        for service_level in service_levels:
            for holding_cost in holding_costs:
                for stockout_cost in stockout_costs:
                    row = simulate_replenishment(
                        forecast, residual_sigma, lead_time, service_level, on_hand_inventory,
                        inbound_inventory, reserved_inventory, backorder_qty, min_order_qty, pack_size,
                        lead_time_std_days, holding_cost, stockout_cost,
                    )
                    rows.append({"lead_time_days": lead_time, "service_level": service_level,
                                 "holding_cost_per_unit": holding_cost, "stockout_cost_per_unit": stockout_cost, **row})
    return rows


def portfolio_sensitivity(
    forecasts_by_sku: dict[str, tuple[Iterable[float], float]],
    on_hand_inventory: float,
    lead_times: Iterable[int],
    service_levels: Iterable[float],
    holding_cost_per_unit: float,
    stockout_cost_per_unit: float,
    inbound_inventory: float = 0.0,
    reserved_inventory: float = 0.0,
    backorder_qty: float = 0.0,
    min_order_qty: float = 0.0,
    pack_size: float = 1.0,
    lead_time_std_days: float = 0.0,
) -> list[dict[str, float]]:
    """聚合全 SKU 参数情景；高风险 SKU 指库存位置低于 ROP 而非真实缺货。"""
    rows: list[dict[str, float]] = []
    for lead_time in lead_times:
        for service_level in service_levels:
            scenarios = [
                simulate_replenishment(
                    forecast, residual_sigma, lead_time, service_level, on_hand_inventory,
                    inbound_inventory, reserved_inventory, backorder_qty, min_order_qty, pack_size,
                    lead_time_std_days, holding_cost_per_unit, stockout_cost_per_unit,
                )
                for forecast, residual_sigma in forecasts_by_sku.values()
            ]
            rows.append({
                "lead_time_days": lead_time,
                "service_level": service_level,
                "total_recommended_order_qty": float(sum(item["recommended_order_qty"] for item in scenarios)),
                "high_risk_sku_count": float(sum(item["unconstrained_order_qty"] > 0 for item in scenarios)),
                "total_holding_cost_proxy": float(sum(item["holding_cost_proxy"] for item in scenarios)),
                "total_stockout_cost_proxy": float(sum(item["stockout_cost_proxy"] for item in scenarios)),
            })
    return rows
