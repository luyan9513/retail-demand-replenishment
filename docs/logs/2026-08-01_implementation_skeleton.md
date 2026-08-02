# 实现骨架日志｜2026-08-01

> 日志性质：本阶段完成可运行的实现骨架，但当时尚未安装第三方包或下载原始数据。文中“待运行”是历史状态；实际运行、修复和结果在 [数据运行与验收日志](2026-08-01_data_run_and_validation.md)。

## 1. 阶段目标与完成标准

**目标**：在不下载数据、不安装新依赖的条件下，实现完整项目结构和可审查的业务逻辑，使授权到位后可以按 README 的顺序复现。

**完成标准**：

1. 有明确的数据导入、质量审计、日级主题表、回测、选模、未来预测、补货情景和看板入口；
2. 关键公式与时序边界有单元测试；
3. DuckDB/dbt/Python/Streamlit 的职责不混杂；
4. 依赖缺失时不伪装为已经成功运行；
5. 许可证、归因与公开数据边界可从 README 和 notices 找到。

## 2. 实际修改文件与实现内容

### 2.1 可运行性、许可与项目入口

| 文件 | 具体改动 | 为什么这样做 | 验收关联 |
|---|---|---|---|
| `README.md` | 写入运行顺序、架构、UCI CC BY 4.0 归因、公式、边界和结果占位说明 | 不看源码也能知道从哪里开始和哪些结论不能说 | 文档验收、许可、复现 |
| `requirements.txt` | 固定 DuckDB、dbt-duckdb、Pandas、scikit-learn、Plotly、Streamlit、openpyxl、pytest 的版本范围 | 让安装器解析得到可预期的技术栈 | 环境可复现 |
| `.gitignore` | 忽略 `data/raw/`、`data/processed/`、DuckDB 文件、本地 dbt profile、虚拟环境和缓存 | 防止受许可原始数据、运行结果和本机配置被误提交 | 数据与隐私边界 |
| `THIRD_PARTY_NOTICES.md` | 记录 UCI 数据归因与 CC BY 4.0；声明未复用 MIT Forecasting App 代码 | 满足来源和未来复用代码时的许可追踪 | 许可审阅 |
| `.github/workflows/ci.yml` | 定义持续集成中可执行的检查入口 | 让代码可在干净环境复验 | 工程化展示 |

### 2.2 Python 数据与建模模块

| 文件 | 具体职责 | 关键业务控制 | 为什么不放进看板 |
|---|---|---|---|
| `src/ingest.py` | 读取 Excel、统一列名、写入 DuckDB 原始表 | 支持两张年度工作表；生成来源行号；缺少关键列即失败 | 导入必须可批处理和可审计 |
| `src/features.py` | SKU×日补零、分层统计、滞后和滚动特征 | 日历只对实验 SKU 连续；分层标签伴随原始指标 | 防止 UI 临时计算导致口径不一致 |
| `src/metrics.py` | WAPE、MAE、sMAPE、偏差 | 零分母保护，避免 MAPE 问题 | 保证报告、训练、测试同用一套实现 |
| `src/backtest.py` | 滚动切分与三类预测器 | 预测起点后 7 天不可参与训练或特征 | 防止未来泄漏 |
| `src/train.py` | 模型对比、SKU 选模、未来 7 天预测 | 逐 SKU 基线、每窗口共享 HGB 的设计接口 | 将训练从 UI 交互中隔离 |
| `src/replenishment.py` | 正态近似、SS、ROP、建议量 | 库存与成本均显式作为入参；整件向上取整 | 防止把假设藏在前端 |
| `src/scenarios.py` | 生成默认和可调情景输出 | 输出残差标准差来源和成本代理 | 让批量结果可保存和审查 |
| `src/run_pipeline.py` | 编排审计、主题表、回测、选模、导出 | 固定产物文件名和执行顺序 | 使复现不依赖手工点击 |

### 2.3 DuckDB、dbt 与 SQL 数据层

| 位置 | 具体改动 | 选择理由 |
|---|---|---|
| `sql/01_quality_checks.sql` | 取消单、数量异常、价格异常、候选重复、缺字段、日期缺口、稀疏度等审计查询 | SQL 可单独复核而不依赖 Python 训练代码 |
| `sql/02_sku_daily_mart.sql` | SKU×日主题表核验查询 | 为 dbt 之外的快速数据检查提供同口径入口 |
| `dbt/models/staging/` | 原始字段类型/命名标准化 | 保留原始数据痕迹，降低下游差异 |
| `dbt/models/intermediate/` | 质量标记和有效正向销售口径 | 取消、异常、候选重复与有效销售可分开追溯 |
| `dbt/models/marts/` | 日级需求与分层模型、schema tests | 将业务可用表作为唯一的训练输入 |
| `dbt/tests/` | 日级唯一、有效销售正向等数据测试 | 防止粒度破坏或负值重新流入主题表 |
| `dbt/profiles.yml.example` | 本地 DuckDB profile 示例 | 实际路径不应写死在受版本控制的文件里 |

### 2.4 看板、测试与交付材料

| 文件/目录 | 具体改动 | 为什么这样做 |
|---|---|---|
| `app/app.py` | 建立总览、评估、SKU 预测、补货、例外 5 类页面和侧栏参数 | 把“数据质量→模型可信度→预测→情景复核”按业务阅读顺序串联 |
| `tests/test_metrics.py` | 断言指标公式和零分母边界 | 防止评价结果被无意改坏 |
| `tests/test_features.py` | 断言日历/特征行为 | 保证日级补零和时间特征规则可复核 |
| `tests/test_backtest.py` | 断言滚动窗口只向前推进 | 防止未来信息泄漏 |
| `tests/test_replenishment.py` | 断言 SS、ROP、建议量和边界 | 确保库存公式可重复、可解释 |
| `docs/data_card.md`、`docs/model_card.md`、`docs/metrics_dictionary.md` | 建立数据、模型和指标说明 | 让招聘方或业务方不必读代码 |
| `docs/resume_bullets.md`、`docs/interview_guide.md`、`reports/*.md` | 建立面试与报告模板 | 为后续用实际运行结果回填留出位置 |

## 3. 重要实现取舍（含原因与影响）

| 取舍 | 采用方案 | 原因 | 影响与防护 |
|---|---|---|---|
| 两年数据 | 导入器设计为读取并合并所有工作表 | 只读第一张会丢失一年数据、扭曲训练和验证窗口 | 后续运行中额外记录工作表数和总行数 |
| 取消单 | 先标记，后从正向需求排除 | 取消是业务信号，不是应静默删除的“脏数据” | 审计表保留数量和比例 |
| 候选重复 | 使用业务键做候选标记而非断言系统重复 | 缺订单行唯一键，无法证明同键一定重复录入 | 报告明确要求业务复核 |
| 长尾 | 主实验只聚焦 Top SKU，长尾仍保留分层/监控 | 在小项目中对稀疏 SKU 做日级统一模型会掩盖风险 | 预留周级或间歇需求方法升级方向 |
| 机器学习 | 设置 HGB 为候选而非默认赢家 | 复杂模型可能不如基线，必须让数据决定 | 所有基线和全指标必须保留 |
| 补货 | 用用户输入库存和成本生成情景 | UCI 没有真实库存或成本 | 不把建议量称为订单或真实改进 |

## 4. 遇到的问题、排查和解决过程

### 问题 A：第三方依赖在当时均不可用

- **现象**：本机初始解释器为 Python 3.9.6；DuckDB、Pandas、scikit-learn、Plotly、Streamlit、pytest、dbt 均未安装。
- **风险**：若假装执行回测、dbt 或看板，所有数字都不可审计；若擅自安装/下载，又违反用户的明确权限要求。
- **处理**：未安装、未下载；只完成不依赖这些包的源码与文档骨架，依赖范围写入 `requirements.txt`，运行顺序写入 README。
- **结果**：保留了正确的权限边界。后续用户明确同意后，实际安装与运行见后续日志。

### 问题 B：语法编译触发 macOS 缓存权限错误

- **首次命令**：`python3 -m compileall -q src app tests`
- **现象**：macOS Python 尝试把 `.pyc` 缓存写到受沙箱限制的 `~/Library/Caches/com.apple.python`，多文件报 `PermissionError`。
- **判断**：错误发生在缓存写入，并非 `SyntaxError` 或项目源码语法错误。
- **解决命令**：`PYTHONPYCACHEPREFIX=/private/tmp/retail-demand-replenishment-pycache python3 -m compileall -q src app tests`
- **为什么安全**：变量仅作用于这一次验证进程；`/private/tmp` 是允许的临时目录；未改用户系统配置、未改项目源码。
- **验证结果**：命令成功完成，所有 Python 源文件通过语法编译。

### 本阶段未遇到其他阻塞问题

## 5. 验证记录（当时可执行的部分）

| 验证项 | 命令/方式 | 实际结果 | 解释 |
|---|---|---|---|
| Python 语法 | `PYTHONPYCACHEPREFIX=/private/tmp/retail-demand-replenishment-pycache python3 -m compileall -q src app tests` | 通过 | 仅验证语法，不代表第三方依赖或业务逻辑已运行 |
| 文档完整性 | 项目脚本检查 | 输出 `文档完整性检查通过：16 个文件` | 必需开发前/交付材料齐备 |
| 第三方依赖探测 | Python 导入检查 | 均缺失 | 如实记录，不替换为其他工具链 |
| 单测 | `pytest -q` | 当时不可运行 | 缺 pytest 和项目依赖 |
| dbt | `dbt parse/build` | 当时不可运行 | 缺 dbt-duckdb 和数据 |
| 回测/情景 | 管道命令 | 当时不可运行 | 缺 DuckDB/Pandas/sklearn 与原始数据 |
| Streamlit | `streamlit run` | 当时不可运行 | 缺 Streamlit 与产物数据 |

## 6. 交接清单、剩余风险与下一步

1. 等待用户授权后，使用 uv 的已有 Python 创建项目 `.venv`；注意实际 DuckDB 包可能对 Python 小版本有额外约束，必须以安装器结果为准。
2. 从 UCI 官方来源取得数据，记录文件大小、工作表数、哈希和归因信息。
3. 依次执行：导入 → dbt debug/build → 数据管道 → 情景 → pytest → Streamlit 冒烟。
4. 将真实数值写入数据卡、模型卡、README、技术报告、业务报告、简历 bullet、追溯矩阵和下一份日志。
5. 重点审查：两张工作表是否都导入、候选重复是否被正确措辞、Top SKU 是否完成全部 3×7 回测、补货页面是否清楚标“模拟”。

后续实测证明上述交接项均已执行；完整证据位于 [数据运行与验收日志](2026-08-01_data_run_and_validation.md)。
