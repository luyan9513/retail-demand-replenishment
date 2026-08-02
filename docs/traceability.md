# 需求追溯矩阵

> 阅读方法：每一行把“用户要求”连接到设计、实现、可复算产物和实际验证。状态“已验证”仅表示本地本次运行通过，不表示公开数据已经证明真实经营收益。

## 1. 需求到证据的完整映射

| 原始要求 | 设计与口径位置 | 主要实现位置 | 可复算产物/实际验证证据 | 状态、结果与边界 |
|---|---|---|---|---|
| 使用 UCI Online Retail II 并遵守 CC BY 4.0 | `README.md`、`docs/data_card.md`、`THIRD_PARTY_NOTICES.md` | `src/ingest.py` | 官方 zip SHA-256：`572e...e67bfb`；`raw_transactions` 1,067,371 行、2 张表 | 已验证；原始数据不提交，发布时必须保留归因与许可链接 |
| DuckDB、dbt-duckdb、Python、SQL、Pandas、sklearn、Plotly、Streamlit | `README.md`、`docs/02_solution_architecture.md` | `src/`、`sql/`、`dbt/`、`app/app.py` | `.venv` Python 3.12.13，92 包；`dbt build` 20/20；Streamlit 本地冒烟 | 已验证；DuckDB 1.5.5 实际需要 Python 3.10+ |
| 取消单、数量/价格异常、重复、稀疏审计 | `docs/03_data_design.md`、`docs/data_card.md` | `sql/01_quality_checks.sql`、dbt intermediate、`src/run_pipeline.py` | `quality_audit.csv` 11 项；取消 19,494、数量异常 22,950、价格异常 6,207、候选重复 34,335、稀疏 SKU 3,135 | 已验证；候选重复不等于确认的系统重复 |
| SKU×日需求主题表 | `docs/02_solution_architecture.md`、`docs/03_data_design.md` | dbt marts、`src/features.py` | `daily_demand.csv` 19,772 行，Top 30 SKU，2009-12-01 至 2011-12-09；dbt 日级唯一测试通过 | 已验证；只对实验 SKU 连续补零 |
| 稳定、周期、高波动、间歇/长尾分层 | `docs/04_model_and_experiment_design.md` | `src/features.py` | 日级 CSV 含 `demand_segment`；30 SKU：稳定 18、周期 4、高价值高波动 7、间歇/长尾 1 | 已验证；阈值是分析规则，不是自然分类事实 |
| 基线与机器学习候选 | `docs/04_model_and_experiment_design.md`、`docs/model_card.md`、`docs/07_code_and_data_lineage_guide.md` | `src/backtest.py`、`src/train.py` | `backtest_predictions.csv`、`model_metrics.csv` | 已验证回测；已披露 HGB 回测共享训练与未来单 SKU 训练不完全同构，下一轮需统一后重验 |
| 滚动回测而非随机切分 | `docs/02_solution_architecture.md`、`docs/04_model_and_experiment_design.md` | `src/backtest.py`、`tests/test_backtest.py` | 起点 2011-11-18/11-25/12-02；7 天窗口；1,701 行全部模型预测；相关单测通过 | 已验证；正式比较仅保留 25 个完整 3×7 SKU |
| WAPE、MAE、sMAPE、偏差及分层误差 | `docs/01_requirements_and_metrics.md`、`docs/metrics_dictionary.md` | `src/metrics.py`、`tests/test_metrics.py` | 总体/窗口/分层/SKU 四类 metrics CSV；HGB WAPE 0.7316、MAE 69.0483、偏差 -0.0218 | 已验证；HGB sMAPE 不是最佳，故不宣称全面胜出 |
| 安全库存、ROP、建议补货量与敏感性 | `docs/assumptions.md`、`docs/01_requirements_and_metrics.md` | `src/replenishment.py`、`src/scenarios.py`、`tests/test_replenishment.py` | `replenishment_scenarios.csv`；默认合计 SS 12,195.01、ROP 26,066.41、建议量 26,079；9 passed | 已验证；均为用户参数驱动的模拟 |
| 提前期、服务水平、库存、持有/缺货成本参数 | `docs/assumptions.md`、`reports/business_report.md` | `app/app.py`、`src/replenishment.py` | Streamlit 交互、情景 CSV 保留参数和成本代理字段 | 已验证；成本不自动反推最优服务水平 |
| 明确公开数据不能得出真实库存结论 | 章程、假设、数据卡、模型卡、两份报告、README | 看板补货页文案与情景字段 | 默认库存 0 的结果被明确标为演示参数 | 已验证；禁止主张已下单、降缺货、增利润或已上线 |
| Streamlit 看板 | `docs/02_solution_architecture.md`、业务报告 | `app/app.py` | 本地 `127.0.0.1:8501`；总览/评估/预测/补货/例外页，桌面与 390px 窄屏检查 | 已验证；服务仅用于本机测试，随后已停止 |
| 数据卡、模型卡、指标字典、假设、技术/业务报告 | `docs/`、`reports/` | Markdown 交付物 | 数据卡、端到端说明书、代码导读、两份报告和阅读路线 | 已验证；数值均与 `data/processed/` 可互相核对，已披露实现一致性风险 |
| 5 条简历 bullet、20 个面试问题及岗位化讲稿 | `docs/resume_bullets.md`、`docs/interview_guide.md`、`docs/08_job_search_and_interview_playbook.md` | Markdown 交付物 | 5 条简历 bullet、20 问、30 秒/2 分钟/5 分钟讲稿、4 个 STAR 故事 | 已实现并已用真实结果更新 |
| 每阶段记录改动、理由、困难、验证与风险 | `docs/logs/` | 开发过程记录 | 初始设置、实现骨架、数据运行、文档深化、项目手册扩展共五份日志 | 已验证；历史状态与后续结果分开记录，避免事后改写 |

## 2. 关键证据索引

| 想核对的问题 | 首选阅读/文件 | 如何自行复核 |
|---|---|---|
| 原始数据是否可靠、许可是什么 | `docs/data_card.md`、`THIRD_PARTY_NOTICES.md`、README | 对照 UCI 链接、文件 SHA-256 与归因文字 |
| 哪些行被排除、为何排除 | `docs/03_data_design.md`、`sql/01_quality_checks.sql`、`quality_audit.csv` | 运行质量 SQL，再比较 11 项计数 |
| 为什么要按 SKU×日和补零 | `docs/02_solution_architecture.md`、`docs/03_data_design.md` | 查看 `daily_demand.csv` 的 `stock_code,demand_date` 唯一性和零销量天 |
| 是否发生未来泄漏 | `docs/04_model_and_experiment_design.md`、`src/backtest.py`、逐日预测 CSV | 抽查任一 `forecast_origin`：特征训练截止日应早于该日期 |
| 模型是否真实超过基线 | `data/processed/model_metrics.csv`、`segment_model_metrics.csv`、技术报告 | 核对 HGB 的 WAPE/MAE 优势与 sMAPE 非优势是否同时被报告 |
| 哪个 SKU 使用哪种模型 | `selected_models.csv`、`sku_model_metrics.csv` | 检查每个 SKU 有 21 个比较观测，按低 WAPE 选模 |
| 补货建议是否被误解为真实订单 | `docs/assumptions.md`、业务报告、情景 CSV | 查看 `inventory_assumption`、`residual_sigma_source` 与参数字段 |
| 能否通过面试讲明白项目 | `docs/interview_guide.md`、两份报告、各日志 | 先按“质量→分层→回测→情景→边界”顺序讲解 |

## 3. 阶段记录与状态演进

| 日期 | 阶段 | 进入时状态 | 实际结论 | 主要证据 | 是否存在未解决阻塞 |
|---|---|---|---|---|---|
| 2026-08-01 | 初始规划 | 无数据、无依赖、无现成项目代码 | 固定口径、权限边界、验收要求和目录；未下载/未安装 | `docs/logs/00_initial_setup.md` | 否；等待授权是正常前置条件 |
| 2026-08-01 | 实现骨架 | 仍无数据和依赖 | 完成全量代码、dbt、测试、看板与报告结构；语法编译通过 | `docs/logs/2026-08-01_implementation_skeleton.md` | 否；依赖未装为权限约束 |
| 2026-08-01 | 数据运行与验收 | 用户已授权 | 环境、数据、dbt、回测、情景、9 项单测、看板均完成 | `docs/logs/2026-08-01_data_run_and_validation.md` | 否；公开数据限制仍存在 |
| 2026-08-01 | 文档深化 | 代码和产物已通过验收 | 扩充文档、日志、证据索引和报告阅读路径；只复核现有产物，不重跑或改数据 | `docs/logs/2026-08-01_documentation_deepening.md` | 否；字段核对差异已通过 CSV schema 复核 |
| 2026-08-02 | 项目手册与代码导读扩展 | 用户要求文档可独立作为说明书、技术讲解稿和面试复盘材料 | 新增端到端说明、函数/SQL/测试导读和岗位化求职材料；复核并修正回测预测期日期；披露 HGB 训练路径不完全同构 | `docs/logs/2026-08-02_project_manual_expansion.md` | 否；发现的是已记录技术债务，未在本次文档阶段修改代码 |
| 2026-08-02 | 首次远端发布 | 用户要求推送项目到已配置 origin | 创建首个本地提交 `771b905` 和发布日志提交 `82d6e26`；认证恢复后将 origin 从无法认证的代理地址改为同一目标仓库的直连 GitHub 地址；`main` 已成功推送并跟踪 `origin/main` | `docs/logs/2026-08-02_remote_publish.md` | 否；仅保留未提交的本机 `dbt/.user.yml` |

## 4. 文档验收阅读路线（无需看代码）

1. 先读 `README.md` 的边界、实际运行快照与运行顺序。
2. 再读 `docs/00_project_charter.md`、`docs/01_requirements_and_metrics.md` 和 `docs/02_solution_architecture.md`，理解目标、成功标准和整体数据流。
3. 读 `docs/03_data_design.md`、`docs/data_card.md` 和 `docs/assumptions.md`，确认数据口径、异常处理和哪些输入是业务假设。
4. 读 `docs/06_end_to_end_project_manual.md`，先把数据处理、模型、补货和看板的完整链路串起来；再读 `docs/04_model_and_experiment_design.md`、`docs/model_card.md`、`docs/07_code_and_data_lineage_guide.md`、`docs/metrics_dictionary.md` 和 `reports/technical_report.md`，审查模型、代码逻辑、时间回测和真实指标。
5. 读 `reports/business_report.md`，理解结果如何支持复核而非自动采购。
6. 最后读 `docs/logs/`、本矩阵、`docs/interview_guide.md`、`docs/resume_bullets.md`、`docs/08_job_search_and_interview_playbook.md`，核验开发过程并准备面试回答。
