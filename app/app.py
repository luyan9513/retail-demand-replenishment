"""Streamlit 决策看板：数据文件由 src/train.py 与 src/scenarios.py 可复现生成。"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.replenishment import portfolio_sensitivity, sensitivity_analysis, simulate_replenishment  # noqa: E402

DATA_DIR = PROJECT_ROOT / "data" / "processed"
DISPLAY_NAMES = {
    "stock_code": "SKU", "demand_segment": "需求分层", "total_qty": "累计销量", "total_revenue": "累计销售额",
    "demand_cv": "需求 CV", "nonzero_day_rate": "非零天占比", "model_name": "模型", "mae": "MAE",
    "wape": "WAPE", "smape": "sMAPE", "forecast_bias": "预测偏差", "observations": "回测观测数",
    "window_number": "回测窗口", "lead_time_days": "提前期（天）", "service_level": "服务水平",
    "recommended_order_qty": "建议补货量", "reorder_point": "补货点", "safety_stock": "安全库存",
    "inventory_position": "库存位置", "on_hand_inventory": "现货库存", "inbound_inventory": "在途库存",
    "reserved_inventory": "已预留库存", "backorder_qty": "已欠交数量", "min_order_qty": "最小订货量",
    "pack_size": "包装倍数", "lead_time_std_days": "提前期标准差（天）",
    "unconstrained_order_qty": "理论缺口（未约束）",
    "backtest_coverage": "回测覆盖",
    "total_recommended_order_qty": "建议补货总量", "high_risk_sku_count": "高风险 SKU 数",
    "total_holding_cost_proxy": "持有成本代理合计", "total_stockout_cost_proxy": "缺货成本代理合计",
}
QUALITY_METRIC_LABELS = {
    "raw_rows": "原始记录数",
    "cancellation_rows": "取消单行数",
    "cancellation_row_rate": "取消单比例",
    "invalid_quantity_rows": "异常数量行数",
    "invalid_price_rows": "异常价格行数",
    "missing_sku_rows": "缺失 SKU 行数",
    "missing_invoice_date_rows": "缺失日期行数",
    "candidate_duplicate_rows": "候选重复行数",
    "valid_positive_sales_rows": "有效正向销售行数",
    "missing_calendar_dates": "缺交易日期数",
    "sparse_sku_count_30pct": "稀疏 SKU 数",
}

st.set_page_config(page_title="零售需求预测与补货决策系统", page_icon="📦", layout="wide")


@st.cache_data(show_spinner=False)
def load_csv(filename: str, parse_dates: tuple[str, ...] = ()) -> pd.DataFrame:
    path = DATA_DIR / filename
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, parse_dates=list(parse_dates))


def fmt(value: float | None, digits: int = 1) -> str:
    return "—" if value is None or pd.isna(value) else f"{value:,.{digits}f}"


def display_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.rename(columns=DISPLAY_NAMES)


@st.cache_data(show_spinner=False)
def to_csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8-sig")


def empty_state() -> None:
    st.info("尚未发现运行产物。请先完成数据导入、dbt 模型、训练与情景生成；看板不会用虚构数据替代真实结果。")
    st.code("python -m src.ingest --input data/raw/online_retail_II.xlsx\n"
            "dbt run --project-dir dbt --profiles-dir dbt\n"
            "python -m src.run_pipeline\n"
            "python -m src.scenarios", language="bash")


def main() -> None:
    daily = load_csv("daily_demand.csv", ("demand_date",))
    future = load_csv("future_forecast.csv", ("forecast_date", "forecast_origin"))
    sku_metrics = load_csv("sku_model_metrics.csv")
    model_metrics = load_csv("model_metrics.csv")
    backtest = load_csv("backtest_predictions.csv", ("forecast_date", "forecast_origin"))
    quality = load_csv("quality_audit.csv")
    duplicate_sensitivity = load_csv("duplicate_sensitivity.csv")

    st.title("零售需求预测与补货决策系统")
    st.caption("面向 SKU 级销售计划的时序预测与库存模拟")
    st.warning("补货结果为参数化情景模拟，不代表真实库存、缺货减少、利润提升或已上线效果。")
    if future.empty or daily.empty:
        empty_state()
        return

    sku_options = sorted(future["stock_code"].astype(str).unique())
    with st.sidebar:
        st.header("情景参数")
        selected_sku = st.selectbox("SKU", sku_options)
        lead_time = st.slider("提前期（天）", min_value=1, max_value=28, value=7)
        service_level_pct = st.slider("服务水平（%）", min_value=50.0, max_value=99.9, value=95.0, step=0.5)
        service_level = service_level_pct / 100
        on_hand_inventory = st.number_input("假设现货库存（件）", min_value=0.0, value=0.0, step=1.0)
        inbound_inventory = st.number_input("假设在途库存（件）", min_value=0.0, value=0.0, step=1.0)
        reserved_inventory = st.number_input("假设已预留库存（件）", min_value=0.0, value=0.0, step=1.0)
        backorder_qty = st.number_input("假设已欠交数量（件）", min_value=0.0, value=0.0, step=1.0)
        min_order_qty = st.number_input("最小订货量 MOQ（件）", min_value=0.0, value=0.0, step=1.0)
        pack_size = st.number_input("包装倍数（件）", min_value=1.0, value=1.0, step=1.0)
        lead_time_std_days = st.number_input("提前期标准差（天）", min_value=0.0, value=0.0, step=0.5)
        holding_cost = st.number_input("单位持有成本（假设）", min_value=0.0, value=0.0, step=0.1)
        stockout_cost = st.number_input("单位缺货成本（假设）", min_value=0.0, value=0.0, step=0.1)
        st.caption("参数只用于模拟；数据源不包含真实库存、在途、MOQ、箱规或采购成本。")

    sku_future = future[future["stock_code"].astype(str) == selected_sku].sort_values("forecast_date")
    sku_daily = daily[daily["stock_code"].astype(str) == selected_sku].sort_values("demand_date")
    residual_sigma = float(sku_future["residual_sigma"].iloc[0])
    simulation = simulate_replenishment(
        sku_future["predicted_qty"], residual_sigma, lead_time, service_level, on_hand_inventory,
        inbound_inventory, reserved_inventory, backorder_qty, min_order_qty, pack_size, lead_time_std_days,
        holding_cost, stockout_cost,
    )

    tabs = st.tabs(["SKU 总览", "预测评估", "SKU 预测", "补货模拟", "例外清单"])
    with tabs[0]:
        if not quality.empty:
            columns = st.columns(4)
            for card, (_, row) in zip(columns, quality.head(4).iterrows()):
                value = float(row["value"])
                display = f"{value:.2%}" if str(row["metric"]).endswith("_rate") else fmt(value, 0)
                card.metric(QUALITY_METRIC_LABELS.get(str(row["metric"]), str(row["metric"])), display)
        overview = daily.groupby(["stock_code", "demand_segment"], as_index=False).agg(
            total_qty=("daily_qty", "sum"), total_revenue=("daily_revenue", "sum"), demand_cv=("demand_cv", "max"),
            nonzero_day_rate=("nonzero_day_rate", "max"),
        ).sort_values("total_revenue", ascending=False)
        st.subheader("Top SKU 与需求波动")
        st.dataframe(display_frame(overview), width="stretch", hide_index=True)
        st.caption("数据质量完整指标见 `data/processed/quality_audit.csv`；取消单、异常行与重复行不会混入正向销量。")
        if not duplicate_sensitivity.empty:
            st.subheader("候选重复处理敏感性")
            st.dataframe(display_frame(duplicate_sensitivity), width="stretch", hide_index=True)
            st.caption("默认口径保留候选重复；严格去重仅作为对照。没有订单行唯一键前，不能把候选重复直接当作系统错误。")

    with tabs[1]:
        st.subheader("滚动时间回测：模型对比")
        if model_metrics.empty:
            st.info("尚无回测结果。")
        else:
            chart = px.bar(model_metrics, x="model_name", y="wape", color="model_name", text_auto=".3f",
                           labels={"model_name": "模型", "wape": "WAPE"})
            chart.update_layout(showlegend=False)
            st.plotly_chart(chart, width="stretch")
            st.dataframe(display_frame(model_metrics), width="stretch", hide_index=True)
        if not sku_metrics.empty:
            st.subheader("按 SKU 分层的误差")
            st.dataframe(display_frame(sku_metrics.sort_values("wape", na_position="last")), width="stretch", hide_index=True)

    with tabs[2]:
        st.subheader(f"SKU {selected_sku}：历史需求与未来 7 天预测")
        figure = go.Figure()
        figure.add_trace(go.Scatter(x=sku_daily["demand_date"], y=sku_daily["daily_qty"], mode="lines", name="历史日销量"))
        upper = sku_future["predicted_qty"] + 1.96 * residual_sigma
        lower = (sku_future["predicted_qty"] - 1.96 * residual_sigma).clip(lower=0)
        figure.add_trace(go.Scatter(x=sku_future["forecast_date"], y=upper, mode="lines", line=dict(width=0), showlegend=False))
        figure.add_trace(go.Scatter(x=sku_future["forecast_date"], y=lower, mode="lines", fill="tonexty", line=dict(width=0),
                                    fillcolor="rgba(32, 113, 180, 0.18)", name="近似不确定性带"))
        figure.add_trace(go.Scatter(x=sku_future["forecast_date"], y=sku_future["predicted_qty"], mode="lines+markers", name="预测"))
        figure.update_layout(xaxis_title="日期", yaxis_title="件数", legend_title="序列")
        st.plotly_chart(figure, width="stretch")
        st.caption("不确定性带基于滚动回测残差标准差的正态近似；不是经校准的概率区间。")
        st.download_button("下载该 SKU 的未来预测 CSV", to_csv_bytes(sku_future), f"forecast_{selected_sku}.csv", "text/csv", icon=":material/download:")

    with tabs[3]:
        st.subheader(f"SKU {selected_sku}：补货情景")
        metrics = st.columns(5)
        metrics[0].metric("未来7天预测需求", fmt(sku_future["predicted_qty"].sum(), 0))
        metrics[1].metric("安全库存", fmt(simulation["safety_stock"], 0))
        metrics[2].metric("补货点", fmt(simulation["reorder_point"], 0))
        metrics[3].metric("库存位置", fmt(simulation["inventory_position"], 0))
        metrics[4].metric("建议补货量", fmt(simulation["recommended_order_qty"], 0))
        st.caption("库存位置 = 现货 + 在途 − 已预留 − 已欠交；补货点 = 提前期内预测需求 + 安全库存；建议量再应用 MOQ 与包装倍数。")
        sensitivity = pd.DataFrame(sensitivity_analysis(
            sku_future["predicted_qty"], residual_sigma, on_hand_inventory,
            [max(1, lead_time - 3), lead_time, lead_time + 3], [0.90, service_level, 0.99],
            [holding_cost], [stockout_cost], inbound_inventory, reserved_inventory, backorder_qty,
            min_order_qty, pack_size, lead_time_std_days,
        ))
        sensitivity_chart = px.line(sensitivity, x="lead_time_days", y="recommended_order_qty", color="service_level", markers=True,
                                    labels={"lead_time_days": "提前期（天）", "recommended_order_qty": "建议补货量", "service_level": "服务水平"})
        st.plotly_chart(sensitivity_chart, width="stretch")
        st.dataframe(display_frame(sensitivity), width="stretch", hide_index=True)
        st.subheader("组合层面敏感性：高风险 SKU 覆盖")
        portfolio_inputs = {
            str(stock_code): (group.sort_values("forecast_date")["predicted_qty"].tolist(), float(group["residual_sigma"].iloc[0]))
            for stock_code, group in future.groupby("stock_code")
        }
        portfolio = pd.DataFrame(portfolio_sensitivity(
            portfolio_inputs, on_hand_inventory, [max(1, lead_time - 3), lead_time, lead_time + 3],
            [0.90, service_level, 0.99], holding_cost, stockout_cost, inbound_inventory, reserved_inventory,
            backorder_qty, min_order_qty, pack_size, lead_time_std_days,
        ))
        portfolio_chart = px.line(portfolio, x="lead_time_days", y="high_risk_sku_count", color="service_level", markers=True,
                                  labels={"lead_time_days": "提前期（天）", "high_risk_sku_count": "高风险 SKU 数", "service_level": "服务水平"})
        st.plotly_chart(portfolio_chart, width="stretch")
        st.dataframe(display_frame(portfolio), width="stretch", hide_index=True)
        st.caption("高风险 SKU 指在当前统一库存位置假设下理论缺口大于 0 的 SKU。成本参数只改变成本代理；本版没有把成本自动转化为服务水平或订货策略。")
        st.download_button("下载当前 SKU 情景 CSV", to_csv_bytes(pd.DataFrame([simulation])), f"scenario_{selected_sku}.csv", "text/csv", icon=":material/download:")

    with tabs[4]:
        st.subheader("优先复核：高不确定性或系统性低估的 SKU")
        if sku_metrics.empty:
            st.info("尚无回测指标。")
        else:
            selected_metrics = sku_metrics.sort_values(["stock_code", "wape"], na_position="last").groupby("stock_code", as_index=False).first()
            selected_metrics["backtest_coverage"] = selected_metrics["observations"].map(
                lambda count: "完整：3 个窗口" if count >= 21 else "不足 3 个窗口：仅监控"
            )
            exceptions = selected_metrics[(selected_metrics["forecast_bias"].fillna(0) < -0.10) | (selected_metrics["wape"].fillna(0) >= selected_metrics["wape"].quantile(0.75))]
            st.dataframe(display_frame(exceptions.sort_values("wape", ascending=False),), width="stretch", hide_index=True)
            st.caption("例外清单是复核优先级，不等价于已发生缺货。回测不足 3 个窗口的 SKU 仅监控，不进入正式选模或补货情景。")


if __name__ == "__main__":
    main()
