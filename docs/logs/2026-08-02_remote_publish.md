# 远端发布日志｜2026-08-02

## 1. 阶段目标与授权范围

**目标**：将当前项目的可复现代码、文档、测试、配置和占位目录创建为首个 Git 提交，并推送到已配置的远端 `origin`。

**授权范围**：用户明确要求“把项目推送到远端”。本阶段未执行强制推送、历史改写、删除远端分支或修改远端地址；只使用普通的 `git push -u origin main`。

## 2. 提交前检查与文件范围

### 修改/纳入文件

首个提交纳入 58 个项目文件、3,616 行，包括：

- Python：`src/`、`app/app.py`；
- 数据建模：`dbt/` 的项目配置、模型、测试和 profile 示例；
- SQL：质量审计与日级主题表核验；
- 测试与 CI：`tests/`、`pytest.ini`、`.github/workflows/ci.yml`；
- 文档与报告：`README.md`、`docs/`、`reports/`、`THIRD_PARTY_NOTICES.md`；
- 空目录占位：`data/raw/.gitkeep`、`data/processed/.gitkeep`。

### 明确未纳入文件

| 文件类型 | 忽略规则/处理 | 为什么不提交 |
|---|---|---|
| UCI 原始 zip/Excel | `.gitignore` 的 `data/raw/*` | 受 CC BY 4.0 归因约束且文件较大；仓库保留来源、哈希和再生步骤 |
| DuckDB 数据库 | `*.duckdb` | 本地运行产物，不适合代码仓库 |
| 处理 CSV | `data/processed/*` | 可由受控流程重新生成，避免将数据产物当源码提交 |
| 虚拟环境/缓存 | `.venv/`、缓存规则 | 机器相关且体积大 |
| 本地 dbt profile | `dbt/profiles.yml` | 机器路径配置，不提交；保留 `profiles.yml.example` |
| `dbt/.user.yml` | 本地用户配置；本次未暂存 | 仅含本机 dbt 用户标识，不属于项目可复现配置，也不包含在首个提交中 |

## 3. 实际执行过程

1. 执行 `git status --short`、`git branch --show-current`、`git remote -v`、`git log --oneline -5`。
   - 结果：当前分支为 `main`；远端 `origin` 已配置；该分支尚无提交；全部项目文件未跟踪。
2. 检查 `.gitignore` 与 `git check-ignore -v`。
   - 结果：UCI Excel/zip、DuckDB、处理 CSV、`.venv` 和 `dbt/profiles.yml` 均被正确忽略。
3. 只读取 `dbt/.user.yml` 的键名并扫描潜在敏感文件路径。
   - 结果：该文件只显示 `id` 键；扫描未发现 API key、密码、token、私钥等敏感文件路径。为避免机器特定配置进入仓库，它未被暂存。
4. 显式执行 `git add`，仅暂存可复现项目文件；运行 `git diff --cached --check`。
   - 结果：58 个文件、3,616 行，空白检查通过。
5. 创建首个提交：

   ```text
   771b905 feat: add retail demand forecasting and replenishment system
   ```

6. 执行普通推送：

   ```bash
   git push -u origin main
   ```

   - 结果：失败，Git 返回 `fatal: could not read Username for 'https://ghfast.top': Device not configured`。
7. 只读检查认证状态。
   - 结果：系统 credential helper 为 `osxkeychain`；GitHub CLI 可执行，但账号 `luyan9513` 的默认令牌已失效，状态提示需运行 `gh auth login -h github.com`；没有修改远端或认证配置。

## 4. 问题、根因与解决路径

| 编号 | 现象 | 根因 | 已做处理 | 当前状态 |
|---|---|---|---|---|
| P1 | `git push` 无法读取用户名 | origin 使用 HTTPS 代理地址，当前环境没有对应认证设备/凭据 | 保留本地提交；只读检查 credential helper 和 GitHub CLI 登录状态 | 待用户重新认证 |
| P2 | GitHub CLI 提示默认令牌无效 | 已保存的 GitHub 令牌过期或被撤销 | 未显示、未修改、未删除任何令牌 | 待用户执行安全登录流程 |
| P3 | `dbt/.user.yml` 仍显示为未跟踪 | `.gitignore` 未专门匹配该本地文件；本次刻意未暂存 | 未提交该文件，避免将机器配置推送 | 非阻塞；后续可按用户意愿加入忽略规则 |

本阶段未遇到代码、数据、测试或文档阻塞问题；唯一阻塞是远端认证。首个提交安全保留在本地，远端尚未收到任何变更。

## 5. 验证结果

| 验证项 | 命令/方法 | 结果 |
|---|---|---|
| 提交内容 | `git diff --cached --name-only`、`git diff --cached --stat` | 58 个可复现文件；原始数据/数据库/CSV/虚拟环境未纳入 |
| 暂存质量 | `git diff --cached --check` | 通过 |
| 首个提交 | `git log --oneline -1` | `771b905 feat: add retail demand forecasting and replenishment system` |
| 远端推送 | `git push -u origin main` | 未通过；缺少 HTTPS 认证 |
| GitHub 登录 | `gh auth status` | 未通过；默认令牌无效 |

## 6. 认证恢复后的实际推送结果

用户完成 GitHub 重新认证后，本项目再次检查认证状态，确认账号 `luyan9513` 已通过 keyring 登录 GitHub.com，拥有 `repo` 和 `workflow` 等所需范围。

### 新发现与处理

首次重试仍失败，原因是原 `origin` 指向：

```text
https://ghfast.top/https://github.com/luyan9513/retail-demand-replenishment.git
```

这是一个代理地址，GitHub.com 的有效凭据不能用于该代理域名。该地址内嵌的目标仓库已经明确为 `github.com/luyan9513/retail-demand-replenishment.git`，因此在不改变目标仓库、不改写历史、不强制推送的前提下，将本地 `origin` 改为等价的直连地址：

```bash
git remote set-url origin https://github.com/luyan9513/retail-demand-replenishment.git
```

随后执行：

```bash
git push -u origin main
```

实际结果：

```text
To https://github.com/luyan9513/retail-demand-replenishment.git
 * [new branch]      main -> main
branch 'main' set up to track 'origin/main'.
```

远端现已包含以下两个提交：

1. `771b905 feat: add retail demand forecasting and replenishment system`
2. `82d6e26 docs: record remote publishing status`

本地 `main` 已跟踪 `origin/main`。唯一保留的本地未跟踪文件是 `dbt/.user.yml`；它是机器特定的 dbt 用户配置，仍未被提交或推送。原始 UCI 数据、DuckDB 数据库、处理 CSV 和虚拟环境也仍按 `.gitignore` 排除。

## 7. 下一步与风险

本次发布已完成。后续常规更新可使用：

```bash
git add <文件>
git commit -m "<说明>"
git push
```

仍需注意：`dbt/.user.yml` 是未跟踪的本机配置。若希望 `git status` 完全干净，可在下一次配置维护时将该文件加入 `.gitignore`；此操作不影响已完成的远端发布，也不应提交该文件本身。
