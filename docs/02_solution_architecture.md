# 方案架构

```text
UCI Online Retail II Excel/CSV
        ↓  ingest.py（字段标准化、原始落盘）
DuckDB raw_transactions
        ↓  dbt staging（类型与口径）
stg_online_retail
        ↓  dbt intermediate（取消单/异常/重复标记）
int_valid_sales_lines + int_data_quality_audit
        ↓  dbt mart（SKU×日、日期补全、SKU 分层）
mart_sku_daily_demand
        ↓  Python 特征、滚动回测、训练与预测
mart_sku_forecast + model_metrics
        ↓  Python 补货情景计算
mart_replenishment_scenario
        ↓  Streamlit + Plotly 决策看板
```

## 分层职责

- `staging`：只做列名、数据类型和原始标记的标准化，保留可追溯原始值。
- `intermediate`：明确区分取消单、异常行、重复行和有效正向销售行；异常进入审计表。
- `mart`：把有效销售行聚合为 SKU×日，并为选中的 SKU 补齐日历日期与零销量。
- Python：仅从已完成的日级主题表构造滞后特征、运行回测、输出预测与情景表。

## 为什么是 SKU×日

补货提前期与目标预测窗口均以“天”为单位；SKU×日既保留周内规律，又能直接汇总提前期内需求。对所有销售日补零能区分“无需求”和“缺失日期”。若实际审计显示 Top SKU 仍过稀疏，才可切到 SKU×周，并在报告中记录这一变更及影响。

## 为什么使用滚动回测

随机切分会把未来模式泄漏给训练集，也不能反映上线时“只知道过去”的处境。滚动回测按时间依次选择多个预测起点：每个起点只使用之前的数据，预测其后 7 天；最终同时报告总体、窗口、SKU 层级与偏差。

## 看板信息架构

默认页面先显示高价值 SKU 和质量护栏，再依次提供预测比较、单 SKU 走势、参数化补货模拟和例外清单。全局控制放在侧栏，避免把复杂设置隐藏在图表里。

## 物理数据血缘与接口契约

| 阶段 | 输入 | 主要处理 | 输出 | 关键契约/失败处理 |
|---|---|---|---|---|
| 原始导入 | `data/raw/online_retail_II.xlsx` | 合并工作表、列名标准化、来源行号 | DuckDB `raw_transactions` | 关键列缺失时明确失败；不悄悄改字段含义 |
| staging | raw 表 | 类型、命名、基础字段标准化 | `stg_online_retail` | 原始字段可追溯，未在此层丢弃异常 |
| intermediate | staging 表 | 取消、异常、候选重复、有效销售标记 | 有效销售与质量审计中间表 | 同一行可有多个质量标记；有效条件必须显式满足 |
| mart | 有效销售 | 聚合、日历补零、SKU 统计与分层 | `mart_sku_daily_demand` / `daily_demand.csv` | `stock_code+demand_date` 唯一；只为实验 SKU 补全活跃区间 |
| 回测 | 日级主题表 | 时间切分、基线/HGB、逐日预测与指标 | `backtest_predictions.csv` 和各类 metrics CSV | 预测日期不能进入该窗口训练集 |
| 未来预测 | 已选模型、最新历史 | 生成 7 日点预测与近似不确定性 | `future_forecast.csv` | 只为完整回测 SKU 生成 |
| 补货情景 | 预测、误差波动、用户参数 | SS、ROP、理论缺口、成本代理 | `replenishment_scenarios.csv` | 强制保留库存假设和 σ 来源字段 |
| 展示 | CSV 运行产物 | Plotly/表格/参数控件 | Streamlit 五页 | 没有产物时应提示先运行管道，不自行伪造数据 |

## 为什么 DuckDB、dbt 和 Python 各做不同事情

| 工具 | 最适合解决的事 | 本项目中的具体使用 | 不让它承担的事 |
|---|---|---|---|
| DuckDB | 本地列式分析和持久化 | 保存原始交易与 dbt 模型的数据库 | 不承担交互看板或模型训练编排 |
| dbt-duckdb | SQL 数据建模、测试和血缘 | staging/intermediate/mart，5 模型、15 测试 | 不在 dbt 中写复杂滚动回测循环 |
| Python/Pandas | 时序特征、回测编排、CSV 导出 | 特征、指标、三模型、情景计算 | 不绕过 dbt 直接把原始 Excel当业务主题表 |
| scikit-learn | 可控机器学习基线/候选 | HistGradientBoosting 共享窗口训练 | 不替代基线，不声明因果关系 |
| Streamlit/Plotly | 参数透明的沟通与探索 | 五页决策看板与敏感性展示 | 不作为真实采购系统或数据写回入口 |

## 实际运行路径示例

2026-08-01 的实际运行遵循：两张 Excel 表 → DuckDB 1,067,371 原始行 → dbt 5 模型和 15 测试 → Top 30 日级主题表 19,772 行 → 3 个滚动窗口的 1,701 行全部模型预测 → 25 个正式 SKU 的 175 行未来预测 → 25 行默认情景。每一跳的文件名、命令和计数见 `docs/logs/2026-08-01_data_run_and_validation.md` 的“产物位置、可复算方式与验收证据”。
