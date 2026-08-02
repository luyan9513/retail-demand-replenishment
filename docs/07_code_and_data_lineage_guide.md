# 代码与数据血缘技术导读

> 这不是把源码逐行复制一遍，而是解释每个文件负责什么、关键函数收到什么输入、做了什么保护、输出什么、为何这样设计，以及它在整条业务链路中的位置。读完后应能带着明确问题进入代码，而不是面对一堆 `.py` 和 `.sql` 文件无从下手。

## 1. 先看目录：每类文件负责哪一层

| 目录/文件 | 职责 | 输入 | 输出 | 读代码时的重点 |
|---|---|---|---|---|
| `src/ingest.py` | 原始文件导入 | Excel/CSV | DuckDB 原始表 | 列名映射、两张工作表合并、类型转换、缺列失败 |
| `dbt/models/` | 数据质量和主题表 | DuckDB raw 表 | staging/intermediate/mart | 标记先于过滤；SKU×日唯一和补零 |
| `sql/01_quality_checks.sql` | 可独立执行的质量审计 | raw 表 | 11 项审计指标 | 每个计数的口径；候选重复的措辞 |
| `src/features.py` | 特征与分层规则 | SKU×日表 | 滞后/滚动特征、分层统计 | `shift(1)` 防止泄漏；分层优先级 |
| `src/metrics.py` | 误差指标 | 实际值、预测值 | WAPE/MAE/sMAPE/偏差 | 零需求/零分母边界 |
| `src/backtest.py` | 时间回测与候选预测器 | 日级需求 | 逐日回测预测、汇总指标 | 训练/测试日期边界、三个模型、HGB 共享训练 |
| `src/train.py` | 训练编排、选模、未来预测导出 | mart 表、回测预测 | 8 类 CSV 与 forecast mart | Top 30、21 观测门槛、选模排序、残差标准差 |
| `src/replenishment.py` | 纯公式与敏感性函数 | 预测、σ、参数 | SS/ROP/Q/成本代理 | 参数校验、L>7 外推、向上取整 |
| `src/scenarios.py` | 批量默认情景 | 未来预测 CSV | 情景 CSV + DuckDB 表 | 只接受显式假设，保留 σ/库存来源说明 |
| `src/run_pipeline.py` | 一键编排 | DuckDB、质量 SQL | 审计 CSV + 训练产物 | 它不替代导入和 dbt，顺序不可颠倒 |
| `app/app.py` | 只读展示与交互模拟 | `data/processed/*.csv` | Streamlit 看板 | 不会伪造没有生成的结果 |
| `tests/` | 回归保护 | 小型构造数据 | 9 个断言 | 保护公式、零值、特征泄漏和窗口逻辑 |

## 2. 主程序运行顺序与文件依赖

```text
src.ingest
  └─ raw_transactions (DuckDB)
       └─ dbt build
            └─ mart_sku_daily_demand (DuckDB)
                 └─ src.run_pipeline
                      ├─ quality_audit.csv (由 sql/01_quality_checks.sql)
                      ├─ daily_demand.csv
                      ├─ backtest_predictions.csv / *_metrics.csv / selected_models.csv
                      └─ future_forecast.csv + mart_sku_forecast
                           └─ src.scenarios
                                └─ replenishment_scenarios.csv + mart_replenishment_scenario
                                     └─ app/app.py
```

`src.run_pipeline` 的命令说明中明确写着“导入与 dbt run 需先分别完成”。原因是它从 DuckDB 读取 `mart_sku_daily_demand`，而该表不是 Python 导入器直接创建的。如果跳过 dbt，`run_training()` 会报“mart_sku_daily_demand 为空”。

## 3. 导入模块：`src/ingest.py`

### 3.1 常量和列名映射

`CANONICAL_COLUMNS` 将来源列名变成统一字段；`normalize_name()` 会小写化并移除空格/符号。例如 `Customer ID`、`CustomerID` 会映射到 `customer_id`。`REQUIRED_COLUMNS` 强制要求有发票、SKU、数量、日期和价格五个字段。

| 函数 | 输入 | 核心处理 | 输出/失败方式 |
|---|---|---|---|
| `normalize_name(name)` | 任意列名 | 保留字母数字和下划线，转小写 | 标准化列名字符串 |
| `read_source(path, sheet_name=None)` | Excel/CSV 路径，可选指定 sheet | Excel 未指定 sheet 时读**全部**工作表并追加 `source_sheet`；统一列名；检查必要列；生成行号；转换日期/数值 | 标准化 DataFrame；缺必要列抛 `ValueError` |
| `ingest_to_duckdb(input_path, database_path, sheet_name=None)` | 标准化输入和数据库路径 | 注册 Pandas DataFrame；覆盖写 raw 表；写入导入元数据 | 返回行数；写 `raw_transactions` 与 `raw_ingestion_metadata` |
| `main()` | CLI 参数 | 解析 `--input/--database/--sheet` | 打印导入行数 |

### 3.2 为什么这个模块的处理顺序重要

1. 先合并两张表，再生成 `source_row_number`：因此行号是**合并后**的来源追踪号，不能作为原始 Excel 的业务订单行号。
2. 先检查列完整性，再写数据库：避免半残缺文件进入后续 SQL。
3. `errors="coerce"` 把不可解析日期/数值变为缺失：后续质量层会把它们明确标为异常，而不是在导入阶段悄悄删行。
4. 导入采用 `CREATE OR REPLACE TABLE`：这是有意的可重跑行为，但也意味着重新导入会覆盖本地原始表。因此若要保留多次数据快照，应先复制数据库或引入批次 ID；当前作品集没有版本化增量导入。

### 3.3 使用时的注意点

`--sheet` 未指定时，实际实现读取全部工作表；这是本项目使用两年数据的关键。CLI 参数帮助文本仍写“默认第一张”，与实现不一致，应以函数实现和本说明书为准；若后续维护代码，建议将帮助文本改为“默认所有工作表”。这是文档审计发现的低风险可维护性问题，不改变当前导入结果。

## 4. SQL 数据层：质量标记先于过滤

### 4.1 staging：`stg_online_retail.sql`

这个模型只做 `CAST` 和 `trim`。它刻意不在此层过滤任何记录：staging 的职责是让数据类型和命名稳定，保留原始业务证据。

### 4.2 标记层：`int_sales_line_flags.sql`

| 计算字段 | SQL 逻辑 | 业务含义 | 重要边界 |
|---|---|---|---|
| `is_cancellation` | 发票号大写后以 `C` 开头 | 取消/撤销信号 | 不假设取消一定与某笔原销售一一匹配 |
| `is_invalid_quantity` | 数量为空或 `<=0` | 不能作为正向成交量 | 与取消可同时为真 |
| `is_invalid_price` | 单价为空或 `<=0` | 不能形成正向销售额 | 赠品/折让是否另行保留由真实业务规则决定 |
| `is_missing_sku` | SKU 空字符串或 NULL | 无法聚合到商品 | 不能靠描述自动猜 SKU |
| `is_missing_invoice_date` | 日期为 NULL | 无法入时间序列 | 仍留在审计层 |
| `duplicate_rank` | 以发票、SKU、描述、数量、日期、价格、客户、国家分组，按来源行号排序 | 找到候选业务重复 | 同键不是铁证；没有订单行 ID 时不能断言系统重复 |

### 4.3 有效销售层：`int_valid_sales_lines.sql`

这层是一个明确的布尔交集：非取消、数量有效、价格有效、SKU/日期完整、`duplicate_rank=1`。只有这些行计算 `line_revenue = quantity × unit_price`。它的价值是让“有效正向成交”成为可检查的 SQL 条件，而不是散落在 Pandas 代码中的若干 `if`。

### 4.4 日级基础与 mart：`int_sku_daily_base.sql`、`mart_sku_daily_demand.sql`

`int_sku_daily_base` 按 `stock_code,demand_date` 聚合三件事：`daily_qty`、`daily_revenue`、`daily_orders`（不同发票数）。mart 在此基础上：

1. 按历史 `daily_revenue` 排序只取 Top 30；
2. 找到每个 SKU 的 first/last date；
3. 用 DuckDB `generate_series` 生成每天的 calendar spine；
4. 左连接实际日级销量，缺失的日填 0；
5. 用窗口函数计算 7 日 lag，用聚合计算非零占比、均值、标准差、CV、7 日相关；
6. 依固定优先级输出 `demand_segment`。

这段 SQL 是“数据处理最重要的业务逻辑”：它把杂乱交易行变成模型需要的等间隔、可解释日序列。

### 4.5 独立质量 SQL：`sql/01_quality_checks.sql`

它与 dbt 标记口径保持一致，但把结果摊平成 `metric,value,definition`，便于 CSV、报告和看板读取。它输出 11 个指标；**不要对这些指标行求和**，因为同一原始行可以命中多个标签。

## 5. 特征与分层：`src/features.py`

### 5.1 `add_lag_features(frame)`：怎样防止未来泄漏

输入必须有 `stock_code,demand_date,daily_qty`。它首先按 SKU/日期排序，然后每个 SKU 内计算：

| 特征 | 实现 | 对预测日 t 的含义 | 为什么不会读取 t 或未来 |
|---|---|---|---|
| `lag_1` | `grouped.shift(1)` | t-1 日销量 | shift 后当前行拿的是上一行 |
| `lag_7` / `lag_14` | `shift(7/14)` | 上周同日/两周前销量 | 同上 |
| `rolling_mean_7/14` | 先 `shift(1)`，再 rolling | 截至 t-1 的最近 7/14 天均值 | 先 shift 是关键；直接 rolling 会把当天真实销量泄漏进特征 |
| `rolling_std_7` | 同上，`ddof=0` | 截至 t-1 的 7 日波动 | 同上 |
| `day_of_week`、`month` | 由日期派生 | 预测时已知的日历信息 | 不依赖销量 |

`feature_row(history, forecast_date)` 用于递归预测：它只接收预测日前的 `history`，要求至少 14 天。第一天预测后将**预测值**加回历史再预测第二天，因此不会把未知的真实未来销量喂给模型。

### 5.2 `classify_skus(daily)`：如何得到分层

它对每个 SKU 计算销售额、非零日占比、平均非零日期间隔、均值、标准差、CV、7 日相关性。分层优先级写在 `SegmentationConfig`：间歇优先，其次高价值高波动，再次周期，最后稳定。此函数与 dbt mart 采用同一套默认阈值思想；mart 是本次实际训练输入，Python 函数可用于独立实验或单元级复用。

## 6. 指标：`src/metrics.py`

| 函数 | 数学定义 | 代码的边界保护 | 业务解释 |
|---|---|---|---|
| `_arrays` | 无 | 确保长度相同且非空 | 避免错位数组产生静默错误 |
| `mae` | `mean(|y-yhat|)` | 可含零销量 | 平均每天差多少件 |
| `wape` | `sum(|y-yhat|)/sum(|y|)` | 全部真实值为 0 时返回 `None` | 总销量权重下的组合误差 |
| `smape` | `mean(2|y-yhat|/(|y|+|yhat|))` | 分母为 0 的日贡献 0 | 零需求较多时的辅助相对误差 |
| `forecast_bias` | `sum(yhat-y)/sum(|y|)` | 全部真实值为 0 时返回 `None` | 负值=系统性低估，正值=系统性高估 |

代码不实现 MAPE，原因是零销量日会除零或极度放大低量天误差。指标模块不决定“哪个模型最好”；它只保证计算一致，选择逻辑在 `train.py`。

## 7. 回测与模型：`src/backtest.py`

### 7.1 配置与时间切分

`BacktestConfig` 固定默认值：预测期 7 天、3 个窗口、至少 28 天训练历史、移动平均窗口 7 天。`rolling_origins()` 从完整日期轴末尾倒推，只有日期数至少为 `28 + 7×3` 才产生 3 个起点。

`run_backtest()` 对每个窗口、每个 SKU：

1. `train = dates <= origin`；
2. `test = origin < dates <= origin+7天`；
3. 若训练不足 28 天或测试不恰好 7 天，跳过该 SKU/窗口；
4. 预测后逐日写入 SKU、训练截止日、预测日、窗口号、模型、实际量、预测量、残差、分层。

这里的残差定义是 `actual_qty - predicted_qty`。后续残差标准差越大，安全库存越大；它不是“库存误差”。

### 7.2 三个预测器

| 函数 | 做法 | 细节 | 优点/局限 |
|---|---|---|---|
| `seasonal_naive` | 取 7 天前对应位置 | 若历史不足 7 天退回最后一个值；预测裁剪到不小于 0 | 极其可解释；不能学习趋势或复杂波动 |
| `moving_average` | 最近 7 天均值，复制到预测期 | 预测 7 天内不递归更新 | 平滑；对突发变化反应慢 |
| `machine_learning_forecast` | 单 SKU HGB + 递归预测 | 特征为 lag/rolling/day/month；训练样本从第 14 天起 | 可学习非线性；对单 SKU 历史量和递归误差敏感 |
| `global_machine_learning_forecasts` | 每个回测窗口共享一次 HGB | 合并 SKU 特征，one-hot 编码 SKU，再逐 SKU 递归 | 本地更快、可借跨 SKU 信号；模型形式不同于单 SKU HGB |

`_make_hgb()` 将 `max_iter=40`、`max_leaf_nodes=7`、`min_samples_leaf=20` 等复杂度限制写死在代码中。这是为了让作品集在本机可复现，而不是追求无限调参后的最高离线分数；`random_state=42` 使随机过程可复现。

### 7.3 一个必须理解的实现一致性风险

**回测**中，`run_backtest()` 调用 `global_machine_learning_forecasts()`，即“每窗口共享 HGB + SKU one-hot”。

**未来预测**中，`src/train.py` 的 `_future_prediction()` 对模型名 `hist_gradient_boosting` 调用的是 `machine_learning_forecast()`，即“每个 SKU 单独训练 HGB”。

这意味着被命名为 HGB 的未来预测，训练形式与其用于选模的共享 HGB 回测版本并不完全相同。它不影响已生成的回测指标本身，但会降低“未来预测与回测模型完全同构”的严格性。因此：

- 当前未来 HGB 预测可用于项目演示和参数化情景；
- 不能把它描述成“完全由同一个已回测 HGB 工件产出”；
- 若做生产化或下一轮技术迭代，应让未来预测复用与回测一致的全局 HGB 训练逻辑，或让回测改为单 SKU HGB，然后重新生成指标和情景；
- 本文档将该项列为**已识别但本次纯文档阶段未修改的技术风险**，避免用文档掩盖实现差异。

### 7.4 `metric_summary(predictions, group_columns)`

该函数只做分组汇总。传入不同分组列，就得到：总体模型指标（`model_name`）、分层指标（`demand_segment,model_name`）、窗口稳定性（`window_number,model_name`）、SKU 指标（`stock_code,model_name,demand_segment`）。这种设计使所有指标调用同一实现，降低“不同报告用不同公式”的风险。

## 8. 训练、选模和未来预测：`src/train.py`

| 函数 | 输入 | 关键步骤 | 输出 |
|---|---|---|---|
| `run_training` | DuckDB `mart_sku_daily_demand`、Top N | 销售额排序取 Top 30；回测；生成四类指标；选模；未来预测；导出 CSV | 8 类 CSV、`mart_sku_forecast`、行数摘要 |
| `select_models` | SKU×模型指标表 | 丢弃观测 `<21` 的 SKU；先 WAPE，再 MAE、绝对偏差、模型名做稳定排序 | 每 SKU 一个 `selected_model` |
| `create_future_forecast` | 日级数据、选模、回测逐日预测 | 对所选 SKU 预测 7 天；计算残差标准差；写 horizon day/分层 | 25×7 的未来预测表 |
| `_future_prediction` | 模型名、历史、起始日 | 分派到三种预测函数 | 单 SKU 7 个预测值 |

### 8.1 为什么是 21 个观测门槛

`min_observations = horizon_days × n_windows = 7×3=21`。缺一个窗口的 SKU 只有 14 天测试值，可能因为样本更少而偶然排到前面。代码宁可不让它进入正式选模、未来预测和默认情景，也不把不公平的模型比较包装成完整结果。

### 8.2 为什么残差标准差会进入补货

`create_future_forecast()` 对“该 SKU + 选中模型”的全部回测残差计算总体标准差（`ddof=0`）；若不足两条，才退回历史日销量标准差。这是把预测不确定性传给安全库存的桥梁。它仍是近似，不是校准概率分布。

## 9. 补货计算：`src/replenishment.py` 与 `src/scenarios.py`

### 9.1 纯函数的好处

`replenishment.py` 不读取数据库、不写文件、不依赖 Streamlit。相同输入必得相同输出，所以最适合单元测试和在看板中复用。

| 函数 | 校验/逻辑 | 输出/用途 |
|---|---|---|
| `service_level_z` | 服务水平须在 `[0.5,1)`；用 `NormalDist().inv_cdf` | 正态近似的 z 值 |
| `lead_time_demand` | `L>=1` 且至少一个预测值；`L<=7` 时求前 L 日和，`L>7` 时用 7 日均预测 × L | 提前期点预测需求 |
| `safety_stock` | σ 不能为负 | `z×σ×sqrt(L)`，最小为 0 |
| `simulate_replenishment` | 库存不能为负 | 返回提前期需求、SS、ROP、库存、向上取整 Q、成本代理 |
| `sensitivity_analysis` | 遍历给定 L/SL/成本组合 | 单 SKU 多参数情景表 |
| `portfolio_sensitivity` | 对各 SKU 重复调用情景函数后汇总 | 组合建议量、高风险 SKU 数、成本代理 |

`lead_time_demand()` 的 `L>预测期` 实现是 `预测均值 × L`，这与端到端说明中的“前 7 天和 + 平均值×剩余天数”等价。它不生成额外模型预测，只作清晰的外推近似。

`src/scenarios.py` 负责把未来预测按 SKU 分组后调用 `simulate_replenishment()`，并把 `scenario_name`、`residual_sigma_source`、`inventory_assumption` 一起写入 CSV。这样任何人查看情景行都知道其来源是“假设库存”，而非库存系统事实。

## 10. 看板：`app/app.py`

### 10.1 为什么看板只读 CSV

看板的职责是读结果、展示和让用户调整参数，而不是在用户点按钮时重新训练模型。这样避免一次 UI 交互修改训练产物，保证与技术报告中的 CSV 可对照。`load_csv()` 还带 `@st.cache_data`，减少重复读文件。

### 10.2 五个页面的具体数据来源

| 页面 | 读取文件 | 主要计算/展示 | 保护语句 |
|---|---|---|---|
| 总览 | `daily_demand.csv`、`quality_audit.csv` | 质量卡、Top SKU、销量/销售额/CV/非零率 | 取消/异常/重复不混入正向销量提示 |
| 预测评估 | `model_metrics.csv`、`sku_model_metrics.csv` | WAPE 柱图、SKU 误差表 | 不隐藏模型/指标 |
| SKU 预测 | `daily_demand.csv`、`future_forecast.csv` | 历史线、未来 7 天、`±1.96σ` 近似带 | 明示不是校准概率区间 |
| 补货模拟 | future 预测 + `replenishment.py` | 指定 SKU SS/ROP/Q、单 SKU/组合敏感性 | 明示库存/成本是参数，不是事实 |
| 例外清单 | `sku_model_metrics.csv` | 偏差 `<-0.10` 或 WAPE 位于 75 分位以上的 SKU | 标记回测覆盖；不是缺货告警 |

没有 CSV 时，`empty_state()` 明确显示运行顺序，**不会**用随机数据或硬编码指标填充 UI。这是作品集可信度的重要设计。

## 11. 测试：每个测试保护什么

| 测试文件 | 覆盖点 | 被防住的回归 |
|---|---|---|
| `test_metrics.py` | 含零销量时 MAE/WAPE/sMAPE/偏差有限；全零 WAPE 返回空 | MAPE 式除零、把不可算 WAPE 写成 0 |
| `test_features.py` | lag 和 rolling 在第 15 天不读取当天销量；递归行只读 history | 特征泄漏未来/当前真实值 |
| `test_backtest.py` | 起点有序、最后窗口仍保留完整预测期；历史不足不切分 | 无序或不完整时间验证 |
| `test_replenishment.py` | 预测需求+安全库存公式、非法服务水平、组合高风险计数 | ROP/Q 公式改坏、参数越界静默通过 |

当前执行 `.venv/bin/pytest -q` 的实际结果为 **9 passed**。测试是关键公式和时间边界的最小保护，不代替端到端业务验收，也没有覆盖所有外部数据格式异常。

## 12. 维护者排错地图

| 现象 | 最先检查 | 可能原因 | 推荐动作 |
|---|---|---|---|
| 导入报缺字段 | `src/ingest.py` 的列名映射、原文件表头 | 来源列名变化或 sheet 选错 | 先打印/比对列名，再扩展映射并新增测试 |
| `mart_sku_daily_demand` 为空 | dbt profile、raw 表、dbt 日志 | 未导入或未执行 dbt | 先 `dbt debug`，再 `dbt build` |
| 回测 SKU 数少 | 日级日期完整性、28 天训练/7 天测试条件 | 新品、停售、数据缺口 | 不放宽门槛来凑样本；记录为仅监控 |
| HGB 很慢 | `global_machine_learning_forecasts` 参数、SKU 数量 | Top N 太大或模型复杂度上升 | 先保留时间边界，再调整复杂度并重新完整回测 |
| 质量指标相加不等于总行 | SQL flags | 行可多标签重叠 | 按独立比例解释，不相加 |
| 情景量异常大 | 库存输入、L、SL、σ、预测是否为负被裁剪 | 默认库存 0、服务水平过高、外推期过长 | 先检查参数和 σ 来源，不直接判为数据错误 |
| 看板空白 | `data/processed/` 文件 | 未按顺序运行/路径不对 | 使用空状态列出的命令生成产物 |

## 13. 技术债务与建议的下一步代码改动

| 优先级 | 发现 | 为什么重要 | 建议改动与验证 |
|---|---|---|---|
| 高 | HGB 回测是共享模型，未来预测是单 SKU HGB | 选模和实际未来预测的模型形式不完全同构 | 统一两端：复用 global HGB 的训练/递归预测接口，或把回测改为单 SKU HGB；重跑全套回测、情景和报告 |
| 中 | `--sheet` 帮助文字与默认读所有 sheet 的实现不一致 | 新维护者可能误以为只导入第一张表 | 修改 help 文案，补导入单元测试 |
| 中 | 候选重复缺少订单行唯一键 | 可能过度/不足去重 | 接入原始订单行 ID 或让该规则变成可配置审计，不直接剔除 |
| 中 | 预测误差未做概率校准 | SS 用正态近似，服务水平不等于真实达成率 | 加分位数/共形预测或服务水平回测 |
| 低 | 输出 CSV 与 DuckDB 结果表分别存在 | 读者容易误以为全部结果都在 DB | 增加 manifest/运行批次 ID，统一产物目录和元数据 |

这些建议不是本次文档阶段偷偷修改的内容。它们是为了让下一次迭代能清楚地说明“改了什么、为什么改、是否改善”，并避免把已知差异藏在漂亮的项目叙述里。
