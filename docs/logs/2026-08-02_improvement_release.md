# 2026-08-02：可投递性改进发布（真实过程记录）

## 阶段目标

把已有作品集从“功能演示已完成”推进到“结论可复核、技术债务已收口、可在面试中经得起追问”。本阶段不是新建项目，也不安装新依赖、不下载新数据；所有验证使用工作区已有的 uv 环境、UCI 原始文件和本地 DuckDB。开发前重新阅读了数据质量、看板和报告相关的工作规范，并核对了 Streamlit 下载组件、GitHub Actions Python 缓存和 dbt 测试的官方文档，以避免按过时写法改动。

## 修改文件、内容与动机

| 文件 | 具体改动 | 动机 |
|---|---|---|
| `dbt/models/intermediate/int_valid_sales_lines.sql` | 移除默认 `duplicate_rank = 1` 条件 | 候选业务键相同不等于已经证明重复录入；没有订单行 ID 时默认删除会把假设伪装成事实 |
| `dbt/models/intermediate/int_valid_sales_lines_deduped.sql` | 新增严格候选去重对照视图 | 让读者可比较两种口径，而不是只能接受一种不可逆的清洗结果 |
| `dbt/models/intermediate/int_sku_daily_base_deduped.sql` | 新增严格去重日聚合层 | 为后续真正的口径敏感性实验预留可追溯输入 |
| `dbt/models/marts/schema.yml`、`sql/01_quality_checks.sql`、`sql/03_duplicate_sensitivity.sql` | 更新默认口径说明，新增 9 项行数/销量/销售额敏感性指标 | 把候选重复的影响量化，并避免质量审计与 dbt 的处理口径不一致 |
| `src/run_pipeline.py` | 管道同时导出 `duplicate_sensitivity.csv` | 使重复敏感性成为标准运行产物，不依赖手工 SQL |
| `src/backtest.py` | 新增 Croston-SBA；共享 HGB 对历史少于 14 天 SKU 回退移动平均；日期偏移改为标准库 `timedelta` | 处理间歇需求候选、真实运行暴露的短历史边界，以及 Pandas/NumPy 弃用警告 |
| `src/train.py` | 未来 HGB 改为调用共享全局 HGB；Croston-SBA 只允许间歇/长尾层参与选择 | 让回测模型与未来模型同构，防止跨层不适用的模型胜出 |
| `src/replenishment.py` | 引入库存位置、提前期波动、MOQ、箱规、理论缺口和受约束建议量 | 让补货演算从“可用库存减法”升级为可解释的情景输入，仍不越界为真实优化 |
| `src/scenarios.py` | CLI 采用现货/在途/预留/欠交等显式参数 | 消除“可用库存”这一含混输入，确保结果行保留假设边界 |
| `app/app.py` | 展示重复敏感性、库存位置、供应约束；支持预测和情景 CSV 下载 | 看板不只展示结论，也让使用者可带走当前筛选/参数下的证据 |
| `tests/test_backtest.py`、`tests/test_train.py`、`tests/test_replenishment.py` | 覆盖 Croston、短历史回退、HGB 统一路径、库存位置/MOQ/提前期波动 | 为本次新增和修复的关键分支建立回归保护 |
| `tests/test_integration_pipeline.py` | 新增合成 CSV/Excel 到 ingest→dbt build→训练→敏感性 SQL 的端到端测试 | 验证各层接口，而不只验证单个函数 |
| `.github/workflows/ci.yml` | Python 3.12，启用 pip 缓存；CI 运行新增端到端测试 | 与项目实际解释器对齐并缩短重复安装耗时 |
| `.gitignore` | 忽略机器本地 `dbt/.user.yml` | 避免把个人/本机 dbt 配置误提交 |
| `README.md`、`docs/09_improvement_release_notes.md` 及本日志 | 更新运行命令、公式、最新指标和可投递边界 | 保证读者不看代码也能复现口径、理解取舍和面试表达 |

## 实际问题、定位过程与解决结果

### 问题 1：uv 在受限执行环境无法初始化缓存

首次执行 `uv run pytest -q` 时，uv 无法打开已有的 `/Users/luyan/.cache/uv`，报 `Operation not permitted`。这不是依赖缺失或测试失败，因此没有擅自安装任何包。获得仅用于读取既有缓存的执行许可后，用同一条命令重跑，测试通过。此问题的结论是：环境沙箱限制了缓存路径；项目代码与依赖状态没有异常。

### 问题 2：测试通过但有 442 条日期弃用警告

第一次测试得到 16 passed，但 `pd.Timedelta(days=...)` 在当前 Pandas 2.3.3 / NumPy 2.5.1 组合下触发 “generic unit” 弃用警告。先尝试把 NumPy 整数显式转换为 Python `int`，警告仍存在；用一行最小复现实验确认 `datetime.timedelta(days=1)` 不触发警告。于是只把日期加法替换为标准库 `timedelta`，不改变滚动窗口长度、预测日期或任何业务逻辑。修复后全部测试无警告。

### 问题 3：真实数据链路第一次运行失败

`dbt build` 已成功（24/24），但 `src.run_pipeline` 在未来预测阶段报“至少需要 14 天历史才能生成机器学习特征”。原因是共享 HGB 用长历史 SKU 成功训练后，会遍历 Top 30 的所有 SKU；其中某些非 HGB 选择 SKU 历史不足 14 天，仍被统一预测函数尝试构造 lag-14 特征。单元测试此前没有混合长/短历史的共享模型场景，所以未发现。

解决方法是在共享 HGB 的预测循环前判断历史长度：小于 14 天直接输出移动平均回退，不假装它是 HGB 预测；同时新增回归测试，构造一个 35 天 SKU 和一个 3 天 SKU。重跑后端到端成功。这一过程说明“真实数据端到端验证”不是形式检查，确实发现了单测遗漏的集成边界。

## 验证命令与真实结果

1. `uv run pytest -q`：**17 passed**，无弃用警告。
2. `uv run dbt build --project-dir dbt --profiles-dir dbt`：识别 **7 个模型、17 个数据测试、1 个 source**；最终 **24/24 PASS，0 WARN，0 ERROR**。
3. `uv run python -m src.run_pipeline --top-skus 30`：导出 **11** 项质量审计、**9** 项候选重复敏感性；30 个候选 SKU、25 个满足完整回测的 SKU、2,268 条回测预测行、175 条未来预测行。
4. `uv run python -m src.scenarios --on-hand-inventory 0 --inbound-inventory 0 --reserved-inventory 0 --backorder-qty 0 --min-order-qty 0 --pack-size 1 --lead-time-std-days 0 --lead-time-days 7 --service-level 0.95`：生成 25 个 SKU 的默认参数化情景。
5. `uv run streamlit run app/app.py --server.headless true --server.port 8502` 后访问 `/_stcore/health`：服务返回 `ok`；随后停止服务，不保留后台进程。
6. `from streamlit.testing.v1 import AppTest` 实际执行 `app/app.py`：`exceptions=0`、`tabs=5`。这比仅检查 HTTP 健康端点更进一步，确认 CSV 读取、控件构建和本次新增的库存/下载组件在当前产物下没有运行时异常。
7. `uv run python -m compileall -q src app tests` 与最终 `uv run pytest -q`：语法编译成功，**17 passed**；`git diff --check` 无空白错误。

关键结果以本轮默认“保留候选重复”口径为准：1,041,670 条默认正向销售行；严格去重对照为 1,007,913 行；HGB WAPE/MAE 为 0.7534/71.7433；默认情景建议量为 26,879 件。完整数字、分层解释和边界见 `docs/09_improvement_release_notes.md`。

## 本阶段未遇到阻塞问题

本阶段没有未解决的阻塞问题。uv 缓存访问限制、日期弃用警告和短历史共享 HGB 边界均已定位、修复并验证。由于没有新增依赖、下载数据或修改系统设置，不需要额外安装授权。

## 剩余风险与下一步

仍需在真实业务中补充订单行 ID、库存位置、在途、实际提前期分布、MOQ/箱规、成本、可售状态、促销和缺货记录。公开数据下的结果仍只能是参数化情景模拟；本阶段的改进是把这个边界表达和代码实现得更诚实、更可复核，而不是把模拟升级成了真实采购优化。下一步为最终文档一致性检查、看板人工启动检查、Git 提交并推送远端。

## 交付确认

最终一致性检查已完成：除历史日志（它们保留当时真实状态）外，README、当前 `docs/`、`reports/` 中没有残留旧版 WAPE、补货量、`available-inventory` 或“未来 HGB 单 SKU”的表述；`git diff --check` 无空白问题。已将本阶段 37 个受控文件提交为 Git commit `8f07400`（`feat: harden replenishment decision workflow`），并成功推送到 `origin/main`。原始 Excel、压缩包、DuckDB、处理结果和 `dbt/.user.yml` 均仍受 `.gitignore` 保护，未进入提交。
