"""SKU 分层和仅使用历史信息的滞后特征。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class SegmentationConfig:
    intermittent_nonzero_rate: float = 0.30
    intermittent_gap_days: float = 5.0
    high_volatility_cv: float = 1.20
    cyclic_lag7_correlation: float = 0.35


def add_lag_features(frame: pd.DataFrame) -> pd.DataFrame:
    """为每个 SKU 构造特征；shift 保证目标日不读取自身或未来销量。"""
    required = {"stock_code", "demand_date", "daily_qty"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"缺少构造特征所需字段：{sorted(missing)}")
    result = frame.sort_values(["stock_code", "demand_date"]).copy()
    grouped = result.groupby("stock_code", group_keys=False)["daily_qty"]
    for lag in (1, 7, 14):
        result[f"lag_{lag}"] = grouped.shift(lag)
    prior = grouped.shift(1)
    result["rolling_mean_7"] = prior.groupby(result["stock_code"]).transform(lambda x: x.rolling(7, min_periods=7).mean())
    result["rolling_mean_14"] = prior.groupby(result["stock_code"]).transform(lambda x: x.rolling(14, min_periods=14).mean())
    result["rolling_std_7"] = prior.groupby(result["stock_code"]).transform(lambda x: x.rolling(7, min_periods=7).std(ddof=0))
    dates = pd.to_datetime(result["demand_date"])
    result["day_of_week"] = dates.dt.dayofweek
    result["month"] = dates.dt.month
    return result


def _average_nonzero_gap(dates: pd.Series) -> float:
    dates = pd.to_datetime(dates).sort_values()
    if len(dates) < 2:
        return float("inf")
    return float(dates.diff().dt.days.iloc[1:].mean())


def classify_skus(daily: pd.DataFrame, config: SegmentationConfig | None = None) -> pd.DataFrame:
    """输出透明的分层驱动指标；标签不能替代原始统计量。"""
    config = config or SegmentationConfig()
    required = {"stock_code", "demand_date", "daily_qty", "daily_revenue"}
    missing = required - set(daily.columns)
    if missing:
        raise ValueError(f"缺少 SKU 分层字段：{sorted(missing)}")
    rows: list[dict[str, float | str]] = []
    for stock_code, group in daily.sort_values("demand_date").groupby("stock_code"):
        qty = group["daily_qty"].astype(float)
        nonzero_dates = group.loc[qty > 0, "demand_date"]
        mean_qty = float(qty.mean())
        std_qty = float(qty.std(ddof=0))
        cv = std_qty / mean_qty if mean_qty > 0 else np.nan
        nonzero_rate = float((qty > 0).mean())
        gap = _average_nonzero_gap(nonzero_dates)
        lag7 = qty.shift(7)
        valid = lag7.notna() & qty.notna()
        lag7_corr = float(qty[valid].corr(lag7[valid])) if valid.sum() >= 8 else np.nan
        rows.append({
            "stock_code": str(stock_code),
            "sku_revenue": float(group["daily_revenue"].sum()),
            "nonzero_day_rate": nonzero_rate,
            "avg_nonzero_gap_days": gap,
            "daily_qty_mean": mean_qty,
            "daily_qty_std": std_qty,
            "demand_cv": cv,
            "lag7_correlation": lag7_corr,
        })
    result = pd.DataFrame(rows)
    high_value_cutoff = result["sku_revenue"].quantile(0.75) if not result.empty else 0.0

    def label(row: pd.Series) -> str:
        if row["nonzero_day_rate"] < config.intermittent_nonzero_rate or row["avg_nonzero_gap_days"] > config.intermittent_gap_days:
            return "间歇/长尾型"
        if row["sku_revenue"] >= high_value_cutoff and row["demand_cv"] >= config.high_volatility_cv:
            return "高价值高波动型"
        if pd.notna(row["lag7_correlation"]) and row["lag7_correlation"] >= config.cyclic_lag7_correlation:
            return "周期型"
        return "稳定型"

    result["demand_segment"] = result.apply(label, axis=1)
    return result


def feature_row(history: Iterable[float], forecast_date: pd.Timestamp) -> dict[str, float]:
    """单步递归预测的特征；history 必须止于 forecast_date 前一天。"""
    values = list(map(float, history))
    if len(values) < 14:
        raise ValueError("至少需要 14 天历史才能生成机器学习特征")
    return {
        "lag_1": values[-1],
        "lag_7": values[-7],
        "lag_14": values[-14],
        "rolling_mean_7": float(np.mean(values[-7:])),
        "rolling_mean_14": float(np.mean(values[-14:])),
        "rolling_std_7": float(np.std(values[-7:], ddof=0)),
        "day_of_week": float(pd.Timestamp(forecast_date).dayofweek),
        "month": float(pd.Timestamp(forecast_date).month),
    }
