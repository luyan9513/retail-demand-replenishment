# 零售需求预测与补货决策系统

面向数据科学、供应链分析、零售分析和经营分析岗位的作品集项目：以 SKU 需求分层和滚动回测为基础，将未来 7 天预测转化为**参数化补货情景模拟**。

> 重要边界：UCI Online Retail II 不包含真实库存、在途、供应商提前期、MOQ、缺货、持有成本或利润。因此本项目不做“真实库存优化”“降缺货”“提升利润”或“已上线”的声明。

## 项目亮点

- 取消单、异常数量/价格、重复记录、缺 SKU、时间缺失和 SKU 稀疏度均有可复现审计。
- 以 SKU×日为主题表粒度，并按稳定、周期、高波动、间歇/长尾需求分层。
- 使用时间滚动回测（至少 3 个 7 天窗口）比较 seasonal naive、移动平均和 HistGradientBoosting。
- 报告 WAPE、MAE、sMAPE、预测偏差以及分层误差；不会仅报告不适合零销量的 MAPE。
- 根据服务水平、提前期、假设库存和预测残差波动计算安全库存、补货点和建议补货量，并做敏感性分析。

## 架构

```mermaid
flowchart LR
  A["UCI Online Retail II"] --> B["DuckDB 原始交易表"]
  B --> C["dbt: staging → intermediate → mart"]
  C --> D["SKU×日需求与分层"]
  D --> E["滚动回测与模型选择"]
  E --> F["未来 7 天预测"]
  F --> G["安全库存/补货点情景"]
  G --> H["Streamlit 决策看板"]
```

## 目录

```text
retail-demand-replenishment/
├── app/app.py                         # Streamlit 五个决策页面
├── src/                               # 导入、特征、回测、训练、补货模拟
├── dbt/                               # staging → intermediate → mart 与质量测试
├── sql/                               # DuckDB 可单独执行的质量审计与 mart 核验 SQL
├── tests/                             # 指标、特征、滚动切分、补货公式单测
├── docs/                              # 章程、数据/模型卡、假设、日志、面试指南
├── reports/                           # 技术报告与业务报告
└── data/                              # 本地原始与运行产物（均不提交）
```

## 数据来源与归因

- 数据：UCI Machine Learning Repository，[Online Retail II](https://archive-beta.ics.uci.edu/dataset/502/online%2Bretail%2Bii)。
- 许可：[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)。使用、分享或演示时请保留 UCI、数据集名称、链接和该许可。
- 详情见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) 与 [数据卡](docs/data_card.md)。

本项目目前未复用 Streamlit Forecasting App 的代码；若未来复制其 MIT 许可文件，将同时保留版权、LICENSE、commit 与修改说明。

## 运行前提

本项目需要 Python 3.10+。本机可由 uv 管理多个解释器；本项目使用已存在的 Python 3.12。依赖为 DuckDB、dbt-duckdb、Pandas、scikit-learn、Plotly、Streamlit、openpyxl 和 pytest，版本范围见 `requirements.txt`。虽然 DuckDB 通用文档仍写有 Python 3.9+ 的说明，但实际解析的 DuckDB 1.5 包要求 Python 3.10+，因此以安装器的真实约束为准。

## 运行顺序

> 原始数据和运行产物默认被 `.gitignore` 忽略，避免将受许可数据误提交。下载与安装应先获得使用者授权。

```bash
# 1) 创建虚拟环境并安装依赖（仅在已获授权后）
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt

# 2) 将 UCI 下载文件放入 data/raw/，然后导入
python -m src.ingest --input data/raw/online_retail_II.xlsx

# 3) 配置 dbt（从示例复制，不提交本地 profile）
cp dbt/profiles.yml.example dbt/profiles.yml
dbt debug --project-dir dbt --profiles-dir dbt
dbt build --project-dir dbt --profiles-dir dbt

# 4) 导出质量审计、执行回测并生成未来 7 天预测
python -m src.run_pipeline --top-skus 30

# 5) 生成默认参数化补货情景；库存和成本均为假设
python -m src.scenarios --available-inventory 0 --lead-time-days 7 --service-level 0.95

# 6) 运行单测与看板
pytest -q
streamlit run app/app.py
```

## 关键公式

- 安全库存：`SS = z(服务水平) × σ(需求或回测残差) × sqrt(提前期)`
- 补货点：`ROP = 提前期内预测需求 + SS`
- 建议补货量：`ceil(max(0, ROP - 假设可用库存))`

公式采用独立日需求的正态近似。提前期大于预测窗口时，用预测日均值外推；该简化、残差来源和成本代理边界详见 [assumptions.md](docs/assumptions.md)。

## 实际运行快照（2026-08-01）

UCI 两张工作表共导入 1,067,371 行，其中 1,007,913 行进入正向销售需求；取消单比例为 1.83%。销售额 Top 30 SKU 中，25 个 SKU 完成完整 3×7 天回测。总体结果如下：

| 模型 | WAPE | MAE | sMAPE | 预测偏差 |
|---|---:|---:|---:|---:|
| HistGradientBoosting | 0.7316 | 69.0483 | 0.9991 | -0.0218 |
| 移动平均 | 0.8668 | 81.8123 | 0.9818 | 0.0467 |
| Seasonal naive | 0.9371 | 88.4427 | 0.7754 | 0.0467 |

HGB 的总体 WAPE/MAE 最好，但 sMAPE 并非最好；项目因此保留基线及全指标。默认库存为 0 的演示情景下，25 个 SKU 的建议补货量合计 26,079 件，这只是参数假设下的理论缺口，绝非真实库存建议。

## 结果阅读顺序

1. `quality_audit.csv`：先确认取消、异常、重复、缺失和稀疏情况。
2. `model_metrics.csv`、`segment_model_metrics.csv`、`window_model_metrics.csv`：确认复杂模型是否真的超过基线，检查低估偏差。
3. `selected_models.csv`、`future_forecast.csv`：理解每个 SKU 选择了哪种方法及其未来预测。
4. `replenishment_scenarios.csv`：将其作为参数假设下的复核清单，而非采购订单。

## 文档与面试材料

- [项目章程](docs/00_project_charter.md)、[技术架构](docs/02_solution_architecture.md)、[数据设计](docs/03_data_design.md)、[模型卡](docs/model_card.md)
- [指标字典](docs/metrics_dictionary.md)、[假设](docs/assumptions.md)、[追溯矩阵](docs/traceability.md)
- [端到端项目说明书](docs/06_end_to_end_project_manual.md)、[代码与数据血缘导读](docs/07_code_and_data_lineage_guide.md)、[求职与面试复盘手册](docs/08_job_search_and_interview_playbook.md)
- [技术报告](reports/technical_report.md)、[业务报告](reports/business_report.md)、[面试指南](docs/interview_guide.md)、[简历 bullet](docs/resume_bullets.md)

真实数值只能在数据导入、dbt、回测和测试成功后填入上述材料；目前所有待运行位置均已明确标注。
