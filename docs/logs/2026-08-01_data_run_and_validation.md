# 数据运行与验收日志｜2026-08-01

## 1. 阶段目标、授权范围与验收标准

**本阶段目标**：在用户明确同意后，使用 uv 管理的本机 Python 完成依赖安装、UCI 官方数据下载、DuckDB 导入、dbt 构建、滚动回测、补货情景、单元测试与 Streamlit 本地验证；只把实测得到的数字回填交付物。

**用户授权范围**：安装项目依赖、下载 UCI Online Retail II 数据、创建项目内虚拟环境和本地运行产物。未修改系统级 Python、uv 配置或网络/端口的永久设置。

**本阶段验收标准**：

1. UCI 数据来源、许可、文件完整性和两张工作表的导入范围可追溯；
2. dbt 模型与测试全部通过；
3. 回测严格按时间滚动，生成逐日、总体、分层、窗口和 SKU 级产物；
4. 仅纳入完成 3×7 天验证的 SKU 进入正式选模/预测/情景；
5. 安全库存、ROP、建议量的测试和情景导出通过；
6. Streamlit 页面在桌面与 390px 窄屏均能读取真实产物；
7. 结果、问题和局限被同步写入报告、追溯矩阵和日志。

## 2. 执行时间线与实际改动

### 2.1 环境、数据和配置

| 修改文件/对象 | 具体改动 | 原因 | 影响/验证 |
|---|---|---|---|
| `.venv/`（本地忽略） | 使用 uv 的现有 Python 3.12.13 创建项目隔离环境 | 依赖解析证明 DuckDB 1.5.5 要求 Python 3.10+ | 避免改系统解释器；安装后可运行全部命令 |
| `requirements.txt` | 调整为可由 Python 3.12 解析的依赖范围 | 将“文档假设”改为安装器验证后的真实环境约束 | 共解析并安装 92 个包 |
| `data/raw/online_retail_II.zip`、`.xlsx`（本地忽略） | 下载官方 zip、解压 Excel | 获得可复现原始输入 | zip 43.5 MB，SHA-256 已记录；两张工作表均被导入 |
| `dbt/profiles.yml`（本地忽略） | 使 DuckDB 路径相对项目根目录为 `data/retail.duckdb` | 初版 `../data` 指向项目外层目录，dbt 找不到数据库 | `dbt debug` 连接成功，`dbt build` 20/20 |
| `dbt/profiles.yml.example` | 同步正确相对路径与使用说明 | 防止新克隆者复制错误路径 | 示例与本地 profile 一致 |
| `.gitignore` | 继续忽略原始数据、数据库、产物、`.venv` 和本地 profile | 不把受许可数据或机器特定文件提交到仓库 | `git status` 不将这些文件作为交付代码 |
| `pytest.ini` | 把项目根路径放入 pytest 导入路径 | pytest 首次无法导入 `src` | `pytest -q` 从导入失败变为 9 passed |

### 2.2 数据导入、回测与情景逻辑

| 修改文件 | 具体改动 | 为什么这样做 | 产生/改变的证据 |
|---|---|---|---|
| `src/ingest.py` | 默认遍历并合并 Excel 的两张年度工作表；保留 `source_sheet`/来源行信息 | 初步实现若只读取首表会丢失第二年数据 | 导入结果为 2 张表、1,067,371 行 |
| `src/backtest.py` | 为 HGB 改为“每个滚动窗口在所有可用 SKU 上共享一次拟合”，使用 SKU one-hot；限制树复杂度 | 原版逐 SKU×逐窗口重训耗时过长，不适合本地演示与复现 | 回测重构后约 3 秒完成，不改变时间边界 |
| `src/train.py` | 只让完整 3×7 天（21 条测试观测）的 SKU 进入正式模型选择、未来预测与补货 | 不能让少一个窗口的 SKU 与完整 SKU 的误差不公平比较 | Top 30 候选中 25 个正式纳入；3 个仅监控 |
| `src/replenishment.py` | 输出残差标准差来源、库存假设、成本代理字段 | 让情景输入/输出可审查，避免“库存事实”误解 | `replenishment_scenarios.csv` 保留参数和来源 |
| `src/scenarios.py` | 增加组合层面的参数敏感性汇总 | 单 SKU 结果难回答组合订货量如何随参数变化 | 看板可汇总建议补货总量和建议量大于 0 的 SKU 数 |
| `sql/01_quality_checks.sql` | 将“重复”明确命名为候选业务重复 | 无订单行号时相同业务键不等于确定的系统重复 | 输出字段 `candidate_duplicate_rows`，报告保留复核说明 |
| `dbt/models/staging/stg_online_retail.sql` | 对齐实际导入字段和类型 | 让 dbt 从标准化 raw 表读取 | staging→intermediate→mart 完整通过 |
| `dbt/models/marts/schema.yml` | 按当前 dbt 参数结构修复 `accepted_values` 书写 | 消除构建时的弃用警告并保持测试语义 | 15 个数据测试通过 |

### 2.3 看板、测试与交付材料

| 修改文件 | 具体改动 | 原因 | 验证 |
|---|---|---|---|
| `app/app.py` | 取消单比例使用百分比格式；质量标签/例外状态中文化；加入组合敏感性；替换弃用的 `use_container_width` | 修复“0”显示、提高业务读者可读性、清理 Streamlit 1.60 警告 | 浏览器检查五页、桌面与 390px 窄屏均通过 |
| `tests/test_replenishment.py` | 增加组合/边界情景测试 | 确保补货量、提前期/服务水平变化和成本代理不发生回归 | 完整测试集 9 passed |
| `README.md`、`docs/data_card.md`、`docs/model_card.md`、`docs/resume_bullets.md` | 将模板占位替换为真实导入、回测和情景数字 | 交付材料不能继续写“待运行” | 数值可由 CSV 复算 |
| `reports/technical_report.md`、`reports/business_report.md` | 回填模型对比、情景解释、业务限制 | 让不读代码的读者也能审查结论 | 报告与 `data/processed/` 一致 |
| `docs/04_model_and_experiment_design.md`、`docs/05_implementation_plan_and_risks.md`、`docs/traceability.md` | 记录实际的 25 SKU 纳入门槛、运行风险和验证状态 | 设计、实现、结果保持同步 | 追溯表链接到本日志与产物 |

## 3. 从授权到验收的真实执行过程

### 3.1 uv 环境和依赖

1. 初次创建环境时，uv 默认缓存目录没有写权限。
   - 首次命令：`uv venv --python 3.9 .venv`
   - 现象：uv 尝试访问用户缓存目录时遭遇权限问题。
   - 处理：仅在当前命令设置 `UV_CACHE_DIR=/private/tmp/retail-demand-replenishment-uv-cache`；缓存写入被限制在允许的临时目录。
2. 使用 Python 3.9 解析依赖时，DuckDB 1.5.5 的实际包元数据要求 Python 3.10+。
   - 处理：用 `uv python list --only-installed` 核实本机已有 CPython 3.12.13；不下载新解释器，改为 `uv venv --clear --python 3.12 .venv`。
   - 结果：创建成功，项目实际解释器为 Python 3.12.13。
3. 初次从 PyPI 安装受沙箱网络限制，出现隧道/网络权限错误。
   - 处理：在用户已同意“安装依赖、下载数据”的范围内，以受控网络权限重试 `uv pip install --python .venv/bin/python -r requirements.txt`。
   - 结果：成功解析并安装 92 个包；没有替换技术栈，也没有修改系统级包。

### 3.2 UCI 数据取得与导入

1. 从 README/数据卡标明的 UCI 官方 CDN 下载 `online_retail_II.zip`；未使用不明镜像。
2. 通过压缩包目录检查 Excel 文件存在，解压到 `data/raw/online_retail_II.xlsx`。
3. 计算 SHA-256：`572e36277c2390fbfde10664750731e0a86f55e33470d91919085f0408e67bfb`；文件大小 43.5 MB。
4. 执行：`python -m src.ingest --input data/raw/online_retail_II.xlsx`。
5. 导入器合并两张年度工作表，写入 DuckDB `raw_transactions`；结果为 **1,067,371 行、2 张工作表**。这一步是后续日期范围覆盖 2009-12-01 至 2011-12-09 的基础。

### 3.3 dbt 构建与数据契约

1. 首次 `dbt debug` 暴露 DuckDB 文件路径错误：profile 中的 `../data/retail.duckdb` 实际指向工作区外层的 `data`，不是项目内 `data/`。
2. 修改本地 profile 和示例为 `data/retail.duckdb`，重新执行：

   ```bash
   dbt debug --project-dir dbt --profiles-dir dbt
   dbt build --project-dir dbt --profiles-dir dbt
   ```

3. 构建中出现 schema 测试参数的弃用提醒。按当前 dbt 约定，把 `accepted_values` 的参数改置于 `arguments:` 下；这是兼容性修复，不改变测试条件。
4. 最终结果：**5 个模型、15 个测试，20/20 通过**。测试覆盖原始字段可用性、有效正向销售约束和 SKU×日唯一性等契约。

### 3.4 回测性能、完整性门槛与产物

1. 初版 HGB 对每个 SKU、每个窗口单独训练。实际运行中耗时明显偏长，并出现 joblib 的物理核心数提示；长期运行不利于在本机稳定复现。
2. 采取最小模型设计调整：每个预测起点只拟合一次 HGB，训练集包含当时所有有足够历史的 SKU；以 SKU one-hot 区分系列，特征仍只包含 `lag_1/7/14`、滚动统计和当时已知日历字段。seasonal naive/移动平均仍逐 SKU 严格计算。
3. 这不是把未来数据并入训练：对每一窗口，训练截止日仍严格小于预测起点；共享的是同一时点的横截面信息。模型复杂度也被限制，避免“性能提升”来自无限加树。
4. 重跑：`python -m src.run_pipeline --top-skus 30`，约 3 秒完成。产生：11 项质量审计、30 个候选 SKU、25 个完整回测 SKU、1,701 行逐日回测预测（3 个模型合计）、175 行未来预测。
5. 3 个预测起点和逐模型预测行数为：

| 预测起点 | 每个模型的预测行数 | 说明 |
|---|---:|---|
| 2011-11-18 | 196 | 28 个当时可预测 SKU × 7 天 |
| 2011-11-25 | 196 | 28 个当时可预测 SKU × 7 天 |
| 2011-12-02 | 175 | 25 个当时可预测 SKU × 7 天 |

三个模型合计为 588 + 588 + 525 = **1,701** 行。正式比较只保留三个窗口均完整的 25 个 SKU，因此每个模型的公平比较观测为 25 × 3 × 7 = **567**。

6. 初版选模包含未完成所有窗口的 SKU。为避免 14 条观测与 21 条观测被放在一起排名，增加完整性过滤：`observations >= 21`。结果为候选 Top 30 中 25 个进入正式选模，另外 3 个在例外页面显示为“仅监控”。

### 3.5 测试、情景和看板

1. 第一次 `pytest -q` 不能导入 `src`。新增最小 `pytest.ini` 指向项目根后重跑，最终 **9 passed**。
2. 执行默认情景：提前期 7 天、服务水平 95%、可用库存 0、持有/缺货单位成本均为 0。产出 25 个 SKU 的情景表。
3. 本地启动 Streamlit 时，沙箱默认不允许绑定端口，报 `PermissionError`。在用户已授权的范围内，以仅本机回环地址 `127.0.0.1:8501` 运行；没有暴露公网端口。
4. 浏览器验收发现取消单比例显示为 `0`，根因是小数使用整数/小数格式显示而非百分比。修正后显示 **1.83%**。
5. 新增函数后 Streamlit 热重载曾出现一次过期模块导入错误。直接用 Python 导入验证函数真实存在，重启本地服务后恢复；这是热重载缓存，不是源码缺失。
6. 发现 Streamlit 1.60 对 `use_container_width` 发出弃用警告，替换为 `width="stretch"` 后警告消除。
7. 最终检查总览、预测评估、SKU 预测、补货模拟、例外清单，以及库存/提前期/服务水平/成本交互；桌面和 390px 窄屏均正常渲染。测试后本地服务已停止。

## 4. 问题—根因—解决—证据对照表

| 编号 | 现象 | 根因判断 | 解决方式 | 修复后证据 | 是否改变业务结论 |
|---|---|---|---|---|---|
| E1 | uv 无法使用默认缓存 | 沙箱对用户缓存目录写权限受限 | 命令级 `UV_CACHE_DIR` 指向 `/private/tmp` | 环境成功创建 | 否 |
| E2 | Python 3.9 无法解析 DuckDB 1.5.5 | 实际 wheel 元数据要求 Python 3.10+ | 改用本机已有 Python 3.12.13 | 92 个包安装成功 | 否，只明确运行前提 |
| E3 | PyPI 访问失败 | 沙箱网络限制 | 在授权内受控网络重试 | 依赖安装成功 | 否 |
| E4 | dbt 找不到 DuckDB | profile 相对路径错误 | 改为项目内 `data/retail.duckdb` | `dbt debug` 成功 | 否 |
| E5 | dbt schema 有弃用提示 | 测试参数写法随 dbt 版本演进 | 改为 `arguments:` 结构 | 20/20 通过且无该弃用提示 | 否 |
| E6 | HGB 回测过慢 | 30 SKU × 3 窗口逐个重训 | 窗口内共享训练、SKU one-hot、限制复杂度 | 约 3 秒完成管道 | 可能影响模型表现，故保留基线和全部指标审查 |
| E7 | pytest 无法导入 `src` | 测试路径未声明 | 新增 `pytest.ini` | 9 passed | 否 |
| E8 | 取消单比率显示为 0 | UI 未格式化为百分数 | 改为百分比呈现 | 看板显示 1.83% | 否，修复展示 |
| E9 | Streamlit 热重载偶发导入错误 | 旧模块缓存 | 直接导入核验后重启服务 | 页面恢复 | 否 |
| E10 | 看板有弃用警告 | Streamlit 1.60 API 更新 | 使用 `width="stretch"` | 重新检查无该警告 | 否 |

**本阶段没有未解决的阻塞问题。**所有已发现问题都已在本地复现、修复并按下列命令验证；但公开数据的业务边界仍是设计限制，不是可“修复”的技术故障。

## 5. 实际验证命令、输入与输出

| 步骤 | 命令/操作 | 主要输入 | 主要输出/实际结果 |
|---|---|---|---|
| 创建环境 | `UV_CACHE_DIR=/private/tmp/retail-demand-replenishment-uv-cache uv venv --clear --python 3.12 .venv` | uv 已安装的 Python 3.12.13 | 成功创建 `.venv` |
| 安装依赖 | `uv pip install --python .venv/bin/python -r requirements.txt` | `requirements.txt` | 成功安装 92 个包 |
| 文件完整性 | `shasum -a 256 data/raw/online_retail_II.zip` | 官方 zip | `572e...e67bfb` |
| 导入 | `.venv/bin/python -m src.ingest --input data/raw/online_retail_II.xlsx` | 两张 Excel 工作表 | `raw_transactions`：1,067,371 行、2 张表 |
| dbt 联通 | `.venv/bin/dbt debug --project-dir dbt --profiles-dir dbt` | `dbt/profiles.yml`、DuckDB | profile/adapter/连接成功 |
| dbt 构建 | `.venv/bin/dbt build --project-dir dbt --profiles-dir dbt` | raw 表、dbt 模型 | 5 个模型 + 15 测试，20/20 通过 |
| 运行管道 | `.venv/bin/python -m src.run_pipeline --top-skus 30` | DuckDB mart | 11 审计项、1,701 回测预测、175 未来预测 |
| 情景 | `.venv/bin/python -m src.scenarios --available-inventory 0 --lead-time-days 7 --service-level 0.95` | 未来预测、选模、参数 | 25 SKU 默认情景 CSV |
| 单测 | `.venv/bin/pytest -q` | `tests/` | `9 passed` |
| 看板 | `.venv/bin/streamlit run app/app.py --server.address 127.0.0.1 --server.port 8501` | `data/processed/*.csv` | 桌面与 390px 窄屏冒烟通过；服务随后停止 |

## 6. 实际数据、回测与情景结果

### 6.1 数据质量和日级主题表

| 指标 | 实测值 | 处理/解释 |
|---|---:|---|
| 原始交易行 | 1,067,371 | 两张年度工作表合并导入 |
| 有效正向销售行 | 1,007,913 | 非取消、数量/价格为正、SKU/日期完整且通过候选重复口径 |
| 取消单行 | 19,494（1.8264%，看板显示 1.83%） | 独立审计，不进入正向需求 |
| 数量异常行 | 22,950 | 审计保留，不进入正向需求 |
| 价格异常行 | 6,207 | 审计保留，不进入正向需求 |
| 候选业务重复行 | 34,335 | 不是确定的系统重复；真实业务需结合订单行号确认 |
| 缺 SKU / 缺交易日期 | 0 / 0 | 原始字段质量检查结果 |
| 全局无交易日 | 135 | 实验 SKU 在自己的活跃日期范围内补零，区分无销量和记录缺失 |
| 稀疏 SKU | 3,135（非零天占比 <30%） | 留在分层/监控，不与 Top SKU 主实验混合 |
| 日级主题表 | 19,772 个 SKU×日记录 | Top 30 SKU，日期 2009-12-01 至 2011-12-09 |

### 6.2 模型总体、分层和选择结果

| 模型 | 公平比较观测数 | WAPE | MAE | sMAPE | 预测偏差 | 如何解读 |
|---|---:|---:|---:|---:|---:|---|
| HistGradientBoosting | 567 | 0.7316 | 69.0483 | 0.9991 | -0.0218 | 总体 WAPE/MAE 最好，但存在轻微总体低估，且 sMAPE 非最优 |
| 移动平均 | 567 | 0.8668 | 81.8123 | 0.9818 | 0.0467 | 简单平滑基线，个别 SKU 仍胜出 |
| Seasonal naive | 567 | 0.9371 | 88.4427 | 0.7754 | 0.0467 | sMAPE 最低，但 WAPE/MAE 最弱；不能据此称为总体最佳 |

| HGB 需求层级 | 观测数 | WAPE | MAE | sMAPE | 偏差 | 风险提示 |
|---|---:|---:|---:|---:|---:|---|
| 周期型 | 84 | 0.4525 | 52.4811 | 0.6407 | 0.0444 | 相对可预测，仍需保留窗口复核 |
| 稳定型 | 343 | 0.7516 | 72.2589 | 1.0614 | -0.1263 | 负偏差较显著，补货复核要防系统性低估 |
| 高价值高波动型 | 140 | 0.9226 | 71.1229 | 1.0617 | 0.2375 | 波动大且总体高估，不能只因高价值就提高库存 |

最终每 SKU 选择：**HGB 15 个、移动平均 8 个、seasonal naive 2 个**。这说明候选模型不是统一替换基线，而是按 SKU 的回测 WAPE 选择。

### 6.3 默认补货情景（非库存事实）

| 参数/结果 | 实测值 | 必须同时阅读的边界 |
|---|---:|---|
| 纳入 SKU 数 | 25 | 都完成 3×7 天回测；不是全量 SKU |
| 提前期 | 7 天 | 用户输入的默认值，不是供应商实测提前期 |
| 服务水平 | 95% | 用正态近似取 z 值，不代表服务承诺已校准 |
| 假设可用库存 | 0 | 演示输入，不是仓库盘点结果 |
| 单位持有/缺货成本 | 0 / 0 | 仅控制成本代理；没有真实财务含义 |
| 安全库存合计 | 12,195.01 件 | 由回测残差或历史波动近似得到 |
| 补货点合计 | 26,066.41 件 | 提前期点预测需求 + 安全库存 |
| 建议补货量合计 | 26,079 件 | 对每个 SKU 的理论缺口向上取整后求和 |

因为库存输入为 0，所有 25 个 SKU 都出现理论缺口。这是公式在演示参数下的必然结果，**不能**解释为“当前缺货”“真实应下单 26,079 件”“已经减少缺货”或“提升利润”。

## 7. 产物位置、可复算方式与验收证据

| 目的 | 文件 | 可核查内容 |
|---|---|---|
| 质量审计 | `data/processed/quality_audit.csv` | 11 项质量计数与比例 |
| 日级需求 | `data/processed/daily_demand.csv` | SKU×日销量、销售额、分层和统计字段 |
| 逐日回测 | `data/processed/backtest_predictions.csv` | 预测起点、预测日、真实值、预测值、模型 |
| 总体/窗口/分层/SKU 误差 | `model_metrics.csv`、`window_model_metrics.csv`、`segment_model_metrics.csv`、`sku_model_metrics.csv` | 所有核心指标都可重新聚合 |
| 选模 | `selected_models.csv` | 每 SKU 的模型、WAPE、MAE、偏差 |
| 未来预测 | `future_forecast.csv` | 25 SKU × 7 天 = 175 行 |
| 情景 | `replenishment_scenarios.csv` | 参数、σ 来源、SS、ROP、库存假设、建议量、成本代理 |
| 契约验证 | `dbt/target/run_results.json`、`dbt/logs/dbt.log` | 20/20 dbt 成功记录 |
| 单测 | 终端 `pytest -q` 输出 | 9 passed |

## 8. 剩余风险、不可作出的结论与下一步

| 风险/限制 | 为什么存在 | 当前控制 | 业务落地前应补充 |
|---|---|---|---|
| 成交销量低估潜在需求 | 缺货时未成交需求不在交易数据中 | 文档始终称“需求代理” | 缺货/可售状态、库存快照 |
| 无真实库存/在途 | UCI 不含库存位置和采购订单 | 只允许用户输入假设库存 | 可用库存、预留库存、在途、调拨数据 |
| 提前期不确定 | 数据无供应商/收货记录 | `L` 作为可调参数 | 供应商与路线的提前期分布、延误记录 |
| 包装/采购约束缺失 | 无 MOQ、箱规、库容、产能 | 建议量只向上取整到单件 | MOQ、包装倍数、预算、库容、供应能力 |
| 模型不在全部指标上获胜 | HGB 的 sMAPE 不是最佳，且分层偏差有差异 | 保留三模型、所有指标、SKU 级选择 | 按关键 SKU/服务目标校准损失函数 |
| 长尾稀疏 | 3,135 SKU 非零天占比低 | 主实验不混合解释，例外页监控 | 间歇需求模型、周级规划或分层库存策略 |

**建议的下一步**：接入真实库存、在途、采购提前期和包装规则后，按同样的时间回测框架重估预测，并把情景模块替换为可审计的库存位置计算；任何“缺货减少/利润提升”主张都必须依赖上线前后或受控实验的真实业务数据。
