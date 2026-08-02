"""预测评估指标；所有函数都显式处理零销量，避免 MAPE 的除零问题。"""
from __future__ import annotations

from typing import Iterable

import numpy as np


def _arrays(actual: Iterable[float], predicted: Iterable[float]) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(list(actual), dtype=float)
    yhat = np.asarray(list(predicted), dtype=float)
    if y.shape != yhat.shape:
        raise ValueError("actual 与 predicted 长度必须一致")
    if y.size == 0:
        raise ValueError("评估指标至少需要一条记录")
    return y, yhat


def mae(actual: Iterable[float], predicted: Iterable[float]) -> float:
    y, yhat = _arrays(actual, predicted)
    return float(np.mean(np.abs(y - yhat)))


def wape(actual: Iterable[float], predicted: Iterable[float]) -> float | None:
    y, yhat = _arrays(actual, predicted)
    denominator = float(np.sum(np.abs(y)))
    if denominator == 0:
        return None
    return float(np.sum(np.abs(y - yhat)) / denominator)


def smape(actual: Iterable[float], predicted: Iterable[float]) -> float:
    y, yhat = _arrays(actual, predicted)
    denominator = np.abs(y) + np.abs(yhat)
    terms = np.divide(2 * np.abs(y - yhat), denominator, out=np.zeros_like(y), where=denominator != 0)
    return float(np.mean(terms))


def forecast_bias(actual: Iterable[float], predicted: Iterable[float]) -> float | None:
    """标准化预测偏差；负值代表系统性低估。"""
    y, yhat = _arrays(actual, predicted)
    denominator = float(np.sum(np.abs(y)))
    if denominator == 0:
        return None
    return float(np.sum(yhat - y) / denominator)
