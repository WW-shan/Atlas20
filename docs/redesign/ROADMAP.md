# Atlas20 全栈完工清单 v2 (Post-R3 Roadmap)

**生成时间**: 2026-05-19  
**基线 commit**: `a43a304` → 本次修订 `HEAD`  
**v2 修订原因**: codex 交叉审查 (session `019e3f06`) 指出事实错误 14 处、遗漏 11 项、范围漂移 7 项、顺序错位 6 项。本版本全部吃进。

**2026-05-27 校准**: 代码已推进到「可用研究控制台 + 真实后端接入 + DB-backed 回测 worker + 多格式报告生成/下载」状态。本文件已按当前实现重新勾选；仍未勾选的项表示尚未达到本清单原定义的生产级验收，而不是 UI/MVP 不可用。

---

## 修订总览（vs v1）

**强制修正（codex 验证后属实）**
- R1 "31 strategies" → **30 strategies**；`hero_kpi.ytdReturn` 不能从 `strategy_summary.csv` 取（全窗指标），必须从 `daily_returns.csv` 或 `equity_curves.csv` 计算 YTD
- R2 不要从目录名派生 RunRow 字段；用 `params.json` / DB 作 source of truth，目录名只作 id
- R3/R6 `selection_history.csv` 仅 `profit_max_refine` 子配置导出，**标准 pipeline 不导**；必须先在 pipeline 加 `weights.csv` 或 `rebalance_targets.csv` 导出
- R7 删除 HEAD probe（会烧 CoinGecko 速率配额）；改用「缓存 last-sync + 可选轻量 authenticated GET」
- R10/E2/E4/E5/E6 `BackgroundTasks + asyncio.Semaphore` **不是生产安全方案**（pandas 是 CPU-bound，GIL 阻塞；进程重启丢任务；多 worker 部署下竞态）。改用 **DB-backed 作业队列 + 子进程 worker**
- E1 配置字段映射写错——`positionPct/slots` 不映射到 `StrategyConfig.max_weight/max_positions`（不存在）；实际是 `FrictionConfig.max_weight_per_coin`，slots 按 strategy family 各不相同
- F1 `app.mount("/static", StaticFiles(directory="reports"))` **不安全**；用鉴权检查的 download 路由替代
- F4 Playwright 截 PNG 是错工具——研究截图要确定性，用 matplotlib 出图；Playwright 保留给 visual regression test
- U1/U2/U3 **三个组件已存在**（`components/ui/Skeleton.tsx` / `ErrorBanner.tsx` / `EmptyState.tsx`）；改为「把现有组件接到 query 状态」
- U4 Overview query 在 `pages/ResearchConsolePage.tsx`，不在 `features/overview/OverviewTab.tsx`；wiring 要在 page 层做
- S7 `constr(regex=...)` 是 pydantic v1 写法；v2 用 `Annotated[str, StringConstraints(pattern=...)]` 或 `Field(pattern=...)`
- C3 `date.today()` 是 timezone-naive；该用 `datetime.now(timezone.utc).date()` 或注入时钟
- D6 CI **已存在** (`.github/workflows/ci.yml`)；改为「扩展现有 CI 加 lint / type-check / deploy」

**新增（codex 指出遗漏，全部纳入）**
- 持久化作业表 + 重启恢复
- 报告产物原子写入（immutable dir + `latest` symlink）
- 每个 run 的可复现性 manifest（config hash, code commit, data snapshot mtimes）
- Pipeline 增加 `weights.csv` / `selection_history.csv` 标准导出
- DB 与产物的备份/恢复/保留策略
- Backtest 资源校验（max window, topN/slots 上限, 未来日期策略, idempotency key）
- 鉴权 download 路径（已覆盖；其他公网 GET 仍需边界保护）
- 日志保留/轮转/密钥脱敏
- OpenAPI snapshot 测试 / TS client 自动生成防契约漂移
- `/api/options` 必须暴露真实 strategy id 列表（compare modal 用）
- SaaS 部署的法律基线（隐私/条款/数据导出删除）—— 仅外网部署时

**移除/降级**（scope drift）
- Q1 mock data 拆 JSON（DB seeding 之后冗余）
- Q7 「每文件 < 100 LOC」（武断指标）
- C6 query 字段顺序对齐（非功能）
- C7 `/api/v1` 路径版本化（本地研究 MVP 不需要）
- A5 i18n（无翻译需求前过度工程）
- A6 light mode（dark-only 研究控制台不是生产 readiness）
- O6 SIEM（措辞过企业化）

**顺序重排**
- **P 早于 E2-E6** — 作业表/migration 早于异步引擎、取消、超时、并发
- **S 早于 F1 和 D 公开部署** — settings/auth/path 校验早于静态下载和部署
- **U4-U9 与 R 并行** — 真数据接入时同步移除 initialData mock 遮蔽
- **T 嵌入各 phase** — 集成/契约测试附在 R/E/P/F，不集中到末期
- **R7/R10 在 settings + rate limit 之后**
- **F2-F5 在 E/P 之后**

---

## 目录

- [Phase R — 真实数据接入](#phase-r--真实数据接入)
- [Phase E — 真实回测执行](#phase-e--真实回测执行)
- [Phase P — 持久化](#phase-p--持久化)
- [Phase F — 报告生成与下载](#phase-f--报告生成与下载)
- [Phase U — 前端 UI 收尾](#phase-u--前端-ui-收尾)
- [Phase S — 安全与认证](#phase-s--安全与认证)
- [Phase O — 可观测性](#phase-o--可观测性)
- [Phase D — 部署与 DX](#phase-d--部署与-dx)
- [Phase T — 测试与质量门（嵌入各 phase）](#phase-t--测试与质量门嵌入各-phase)
- [Phase Q — 代码质量](#phase-q--代码质量)
- [Phase C — 契约边角](#phase-c--契约边角)
- [Phase A — A11y](#phase-a--a11y)
- [Phase X — Pipeline 输出扩展（新增）](#phase-x--pipeline-输出扩展新增)
- [Phase L — 合规与法律（新增，按需）](#phase-l--合规与法律新增按需)

---

## Phase X — Pipeline 输出扩展（前置依赖）

> **必须先做**：R3/R6/E3 都依赖 pipeline 导出的 `weights.csv` / `selection_history.csv`；当前标准 pipeline 不导这些。

### X1 — 标准 pipeline 导出 `weights.csv`
- [x] `src/atlas20/reporting/report.py:export_result_tables` — 每个策略写 `{run_dir}/weights/{strategy_name}.csv`（rebalance_date × coin_id matrix）
- [x] 触发：`pipeline.py` 跑全集时；POST `/backtests/run` 执行时
- [x] **Acceptance**: `reports/latest/weights/` 目录有 30 个文件

### X2 — 标准 pipeline 导出 `selection_history.csv`
- [x] 当前仅 `profit_max_refine` 子配置导出；提到所有策略
- [x] schema: `rebalance_date, coin_id, coin_rank, coin_score, coin_weight, strategy`
- [x] **Acceptance**: `reports/latest/selection_history.csv` 包含全部策略行

### X3 — 每个 run 的可复现性 manifest
- [x] 每个 `reports/app_runs/{run_id}/manifest.json` 包含完整 provenance（已写 `code_commit`、`config_path`、`config_hash`、`params_hash`、`data_snapshot`、`pipeline_version`、`engine_version`、artifact sha）：
  - `config_path`, `config_hash` (sha256 of yaml)
  - `code_commit` (`git rev-parse HEAD`)
  - `data_snapshot`: `{provider: latest_file_mtime}`
  - `pipeline_version`, `engine_version`
  - `artifacts: [{kind, path, size, sha256}]`
- [x] **Acceptance**: manifest 不包含 timestamp；同 config / 同代码 / 同数据快照下的确定性字段已由 worker manifest 测试覆盖

### X4 — 原子产物写入
- [x] 每次 pipeline / backtest 写到 `{run_dir}.tmp/`，最后原子发布到目标目录
- [x] `reports/latest` 改为指向最新 run_dir 的 symlink/Junction（worker final publish 后切换，`latest.txt` 保留兼容）
- [x] API 读 latest 产物时通过 `_latest_report_dir` 解析，避免读取不存在的 `.tmp` 路径
- [x] **Acceptance**: 跑 pipeline 期间 GET `/api/overview` 不会 500（读端优先 `reports/latest`，worker 实战已覆盖）

---

## Phase R — 真实数据接入

> 依赖：Phase X 完成。所有 services 改为读真实 CSV。

### R1 — Overview 真实化
- [x] `services.get_overview` 改用真实数据 adapter
- [x] `top_strategies`: 读 **全部 30 行** `strategy_summary.csv`，按 sharpe 降序取 top 3
- [x] `champion`: top_strategies[0]
- [x] `equity_curve`: 从 `equity_curves.csv` 取 champion 列，按月 resample 6 个点
- [x] `daily_returns`: 从 `daily_returns.csv` 取 champion 列
- [x] `hero_kpi.ytdReturn`: **从 `daily_returns.csv` 当前年份首日到末日累积**（不是 strategy_summary.csv 的 total_return）
- [x] `hero_kpi.sharpe / maxDd`: 使用 strategy_summary.csv 全窗指标
- [x] `aum / regime / rebalance`: 保留半字面量（无真实数据源），但 `rebalance.ts` 用真实最近 rebalance_date
- [x] `equity_overlay.series`: champion 列 vs `BTC_BH__always_on` 列，按 ChartRange 截取
- [x] **Acceptance**: GET `/api/overview` `champion.strategy` 与 strategy_summary.csv 真实 sharpe 最高行一致

### R2 — Run History 真实化
- [x] `services.list_runs` 从 **DB**（不是目录名）查询；DB 由 Phase P 提供
- [x] 缺 DB 时 fallback: `glob(reports/app_runs/*/manifest.json)`，**从 manifest 读字段**，不解析目录名
- [x] `services.get_run_detail`: 从 `{run_dir}/manifest.json` + `summary.csv` + `equity_curve.csv` 组装
- [x] `mock_data.fallback_runs_list` 改为 seed/test fixture 输入；runtime service 不再从目录名合成 run 字段
- [x] **Acceptance**: 跑一次回测后 GET `/api/runs` 看到真实 run；重启后仍在

### R3 — Compare 真实化
- [x] `ids` 是 `strategy_summary.csv` 第一列的 strategy slug（如 `BTC_BH__always_on`）
- [x] unknown id → **404**（真实 reports 已加载时，无法解析的 compare id 不再 fallback/skip；legacy alias 仍兼容）
- [x] `equity` 从 `equity_curves.csv` 取传入 ids 各列
- [x] `metrics` 从 `strategy_summary.csv` 行映射；缺字段（sortino/calmar/win_rate 等已在 csv）
- [x] `overlap.matrix`: 从 `weights/*.csv`（Phase X1）读取最新持仓求 Jaccard，缺权重文件时回退旧 proxy
- [x] `sharedHoldings`: 从 `weights/*.csv` 各策略 union 计算出现次数
- [x] **Acceptance**: 调真实 strategy 名 `?ids=BTC_BH__always_on,TOP20_MOM_top4_monthly__always_on` 返回真实指标

### R4 — Reports archive 真实化
- [x] `services.list_reports` 扫描 report root 下真实产物（含 `reports/latest/`、历史目录、`reports/app_runs/*/`）
- [x] 每个 `*.md` / `*.pdf` / `*.png` / `*.csv` / `*.zip` → ReportEntry
- [x] `report_type` 推断规则落在 `_disk_report_type`
- [x] `thumbnail` 推断规则落在 `_disk_report_thumbnail`
- [x] `size_bytes`: `path.stat().st_size`
- [x] `generated_at`: `path.stat().st_mtime` ISO
- [x] **Acceptance**: GET `/api/reports` 至少返回 `reports/latest/atlas20_report.md`

### R5 — Featured Digest 真实化
- [x] `services.get_featured_digest`: 优先 DB/KV featured run；无 scheduled run 时回退 `reports/latest/*.md`（避免扫到未归属 archive markdown）
- [x] `subtitle`: 拼自 strategy_summary champion + YTD（来自 R1 计算）
- [x] **Acceptance**: title 含真实 generated date

### R6 — Universe Timeline 真实化
- [x] `services.get_universe_timeline`: 读 `data/processed/rebalance_universe.csv`
- [x] 每个 rebalance_date 的 top-N tokens → segments（按 token 聚合连续区间）
- [x] `rotations`: 当连续两次 rebalance 进/出 ≥ 2 个 token 时标 MAJOR ROTATION
- [x] **Acceptance**: BTC、ETH 占满 180 天，altcoin 有真实进出

### R7 — Data Sources 真实化（**等 S2/S6 完成后再做**）
- [x] `services.get_data_sources` 用缓存的 last-sync 状态，不每请求都 probe
- [x] last_sync_seconds: 从 `data/raw/{provider}/` 最新文件 mtime 算
- [x] status 推断：< 1h 健康；< 24h degraded；> 24h error
- [x] 不做 HEAD probe（会烧 CoinGecko 速率配额）
- [x] 5 分钟 TTL cache
- [x] **Acceptance**: 不依赖外网即可返回；如外网通有 cache TTL

### R8 — Data Alerts 真实化
- [x] `services.get_data_alerts` 读 `data/processed/data_quality.csv`
- [x] 列映射 `severity` / `title` / `meta` / `ts` / `icon`
- [x] data_quality.csv 缺时返回 fallback/empty-safe 数据
- [x] **Acceptance**: 改 data_quality.csv 后 API 反映

### R9 — Options 真实化
- [x] `services.get_options_payload` 已暴露真实 `strategies: [{strategy, display_name}]`，并继续返回 presets / universes / rebalances / fee/slippage ranges / sectors。当前 API shape 与下列草案不同，但满足前端 Compare modal 真实策略选择：
  ```json
  {
    "strategy_families": [...],
    "rebalance_frequencies": [...],
    "presets": [list from config/*.yaml],
    "strategies": [{"id": "BTC_BH__always_on", "label": "BTC Buy & Hold", "family": "Other"}, ...],
    "date_ranges": [...]
  }
  ```
- [x] **Acceptance**: compare modal (U10) 拉的 strategies 是真实列表

### R10 — Universe Refresh 真实化（**等 P/S 完成**）
- [x] `services.refresh_universe` 通过 `universe_refresh` DB job 调 `atlas20.data.processor.download_and_cache_raw_data`
- [x] 异步执行（用 Phase E2 的作业队列，不是 BackgroundTasks）
- [x] 加 GET `/api/universe/refresh-status` 查进度
- [x] **Acceptance**: 点 FORCE REFRESH 后 `data/raw/` 新文件 mtime；前端轮询 status

---

## Phase E — 真实回测执行

> 依赖 Phase P（作业表）。**`BackgroundTasks + asyncio.Semaphore` 不可用于 pandas CPU 任务**。

### E1 — BacktestConfig → ResearchConfig 适配器
- [x] 新增 `src/atlas20/api/config_adapter.py`
- [x] 映射（**修正自 v1**）:
  - `preset` → 选 `config/{slug}.yaml` 或 base + override
  - `universe.topN` → `UniverseConfig.top_n`
  - `universe.excludeStable/excludeWrapped` → `UniverseConfig.exclude_stablecoins / exclude_wrapped`
  - `window.start/end` → `ResearchConfig.start_date / end_date`
  - `window.rebalance` → `RebalancingConfig.frequencies` 单项
  - `allocation.positionPct` → `FrictionConfig.max_weight_per_coin`（百分比转小数）
  - `allocation.slots` → strategy-family 特定：momentum_hold_counts[0] / sector_top_k[0]
  - `costs.feeBps` → `FrictionConfig.transaction_cost_bps`（若已有；否则在 FrictionConfig 加字段）
  - `costs.slippageBps` → 新增 `FrictionConfig.slippage_bps`
- [x] **Acceptance**: 每种 BacktestConfig 都能合法转换，单测覆盖

### E2 — DB-backed 作业队列（**取代 BackgroundTasks**）
- [x] 选型：MVP 采用简易 DB poll worker
- [x] `runs` 表加 `worker_pid` / `started_at` / `heartbeat_at` 列；独立 Python 进程 `python -m atlas20.api.worker` 轮询 `status='queued'` 取任务
- [x] 子进程隔离（`subprocess.Popen([sys.executable, "-m", "atlas20.api.worker.run_one", run_id])`），避免主进程被 pandas 阻塞
- [x] **Acceptance**: 重启 uvicorn 后 queued 任务被 worker 重新拾起

### E3 — 写盘（依赖 Phase X4 原子写入）
- [x] worker 进程为每个 run 写 `reports/app_runs/{run_id}.tmp/` → 完成时原子发布
- [x] 产物：`summary.csv`、`equity_curve.csv`、`daily_returns.csv`、`weights/{strategy}.csv`、`selection_history.csv`、`manifest.json`、`params.json`（原始 BacktestConfig）
- [x] **Acceptance**: 跑完后 `reports/app_runs/btk_NNNN/` 完整

### E4 — 超时（**子进程模式**）
- [x] `subprocess.Popen(...).communicate(timeout=settings.run_timeout_seconds)` 在父进程超时杀子
- [x] worker 检测到非 0 退出 → `status=failed`, `error="timeout"`
- [x] **Acceptance**: 超时路径有 worker 队列测试覆盖

### E5 — 并发限流（**worker 池**）
- [x] worker 进程数 N（env `ATLAS20_WORKERS=2`）
- [x] N 个 worker 独立从 DB pull queued
- [x] **Acceptance**: POST 5 次，N=2 时两 running 三 queued（API 注册 + worker claim + `/api/runs/queue` 场景测试覆盖）

### E6 — 取消（**子进程 SIGTERM**）
- [x] POST `/api/runs/{id}/cancel`：DB 标记 `requested_cancel=True`
- [x] worker 心跳时检查 flag，向子进程发 SIGTERM
- [x] Pandas 自身不响应 SIGTERM，但子进程会被 OS 杀
- [x] **Acceptance**: cancel running 任务按 heartbeat + grace 设置进入 `cancelled`

### E7 — 资源校验（**S/E 交叉，新增**）
- [x] BacktestConfig 加约束：
  - 窗口跨度 ≤ 10 年
  - topN ≤ 50, slots ≤ topN
  - end_date ≤ 今天（不允许未来）
  - feeBps + slippageBps ≤ 1000
- [x] POST 带 `Idempotency-Key` header：同 key 24h 内返回原响应
- [x] **Acceptance**: 超界配置 422；重复 idem-key 同响应

### E8 — 重启恢复
- [x] uvicorn / worker 启动时扫描 `status='running'` 但 `heartbeat < now-60s` 的任务 → 标记 failed/timeout 或重新 queued
- [x] **Acceptance**: kill -9 worker 后 60 秒内 stale running 被恢复

---

## Phase P — 持久化（**早于 E2-E6**）

### P1 — 选型
- [x] MVP: SQLite + SQLModel；可平迁 PostgreSQL
- [x] DB 路径 `data/atlas20.sqlite`（从 settings 配）

### P2 — 表设计
- [x] `runs`: id, strategy, family, universe, window_start, window_end, status, return_pct, sharpe, max_dd, duration_s, eta_s, spark (JSON), created_at, favorited, params (JSON), error, worker_pid, started_at, heartbeat_at, requested_cancel
- [x] `report_files`: id, run_id (FK nullable), kind, path, size_bytes, sha256, generated_at
- [x] `kv_settings`: key, value, updated_at
- [x] `idempotency_keys`: key (PK), method, path, response_json, created_at, expires_at

### P3 — Repository 层
- [x] `src/atlas20/api/repositories/runs_repo.py`、`reports_repo.py`
- [x] services 改用 repo，FastAPI `Depends(get_session)` 注入

### P4 — Alembic migrations
- [x] `alembic init` + 第一版 schema
- [x] startup hook 自动 `upgrade head`
- [x] **Acceptance**: `rm data/atlas20.sqlite && uvicorn ...` 仍可启动

### P5 — Seed 命令
- [x] `python -m atlas20.api.seed` 把 `mock_data` 写入 DB
- [x] **Acceptance**: 新 clone 一行命令初始化 demo

### P6 — 备份/保留（**新增 codex**）
- [x] `python -m atlas20.api.backup` 把 DB + `reports/app_runs/` 打 tar 写到 `backups/`
- [x] 保留策略：30 天滚动
- [x] **Acceptance**: 文档化 RPO/RTO

---

## Phase F — 报告生成与下载

> 依赖 S（auth + path 校验）。**不要 mount StaticFiles 直接服务 reports/**。

### F1 — 鉴权 download 路由（**取代 static mount**）
- [x] `GET /api/reports/{report_id}/download?format=...` 流式返回 `FileResponse`
- [x] services 层做：(a) report_id 正则校验；(b) DB 查 `report_files` / manifest / sha256 确认 ownership；(c) 路径 resolve 在白名单根目录内
- [x] 同样替换 `/api/reports/digest/download` 直接返回 `FileResponse`，不返回 URL
- [x] **Acceptance**: 路径穿越 attempt 403；正常下载流式 200
- [x] GET download 路由鉴权：`X-API-Key` 配置后保护 report/digest download；前端 blob 下载会带 header

### F2 — Markdown 生成
- [x] 复用 `atlas20.reporting.report.build_markdown_report`
- [x] 写到 run 目录 `digest.md` + 入 `report_files`

### F3 — PDF 渲染
- [x] `weasyprint`(MD→PDF)，不可用时返回 warning 而非假 PDF
- [x] **Acceptance**: format=pdf 真下 PDF（依赖本机 weasyprint 可用性）

### F4 — PNG 图表（**修正**：matplotlib，不是 Playwright）
- [x] 复用 `atlas20.reporting.charts:plot_equity_curves` 等已有函数
- [x] **Acceptance**: format=png 真下确定性图片

### F5 — Bundle ZIP
- [x] `zipfile.ZipFile` 打包同 run 的全部 artifact
- [x] **Acceptance**: 下 ZIP 解开看到 md/pdf/png/csv

### F6 — 定时 Featured Digest 生成
- [x] APScheduler 周一 00:00 UTC 触发；产物入 DB
- [x] **Acceptance**: 可手动调用 `atlas20.api.scheduler.generate_featured_digest(week=N)`

### F7 — 报告 manifest
- [x] 每次生成写 `{run_dir}/report_manifest.json` 列举 artifact + sha256
- [x] download 路由用 manifest 做白名单校验
- [x] **Acceptance**: 直接 GET `path` not in manifest → 403

---

## Phase U — 前端 UI 收尾

> **修正**：U1-U3 组件已存在，本 phase 只是「接到 query 状态」。

### U4 — Overview wire（**修正**：在 ResearchConsolePage.tsx）
- [x] `pages/ResearchConsolePage.tsx` — 用 `<Skeleton>` `<ErrorBanner>` 包 overviewQuery
- [x] 移除 `initialData: fallbackOverview`
- [x] **Acceptance**: 断网时不再静默显示 mock

### U5 — Backtest Studio wire
- [x] `BacktestStudioTab.tsx` — detailQuery + queue 各自 isLoading/isError 分支

### U6 — Compare wire
- [x] `StrategyCompareTab.tsx` — query 状态

### U7 — Run History wire
- [x] `RunHistoryTab.tsx` — listRuns 状态 + 过滤空结果用 `<EmptyState>`

### U8 — Universe wire
- [x] `UniverseHealthTab.tsx` — 3 queries 各自

### U9 — Reports wire
- [x] `ReportsExportsTab.tsx` — featured + archive

### U10 — `+ ADD STRATEGY` modal
- [x] 真做 multi-select，selections 拉 `/api/options.strategies`（R9）
- [x] **Acceptance**: 加策略后 compare 表多一列；URL 反映

### U11 — `+ NEW REPORT` modal
- [x] 选 type/format/strategy → POST `/api/reports/generate`（需 F 完成）

### U12 — 全局 disabled-on-loading audit
- [x] 所有 mutation 触发按钮（RUN BACKTEST、FORCE REFRESH、DOWNLOAD、+ NEW REPORT）isLoading 时 disabled

---

## Phase S — 安全与认证（**早于 F1 和 D**）

### S1 — Settings 中心
- [x] `src/atlas20/api/settings.py` — pydantic-settings BaseSettings
- [x] 字段: `env`, `cors_origins: list[str]`, `db_url`, `secret_key`, `api_keys: set[str]`, `enable_docs`, `report_root: Path`, `anchor_date: date | None`, `data_root`
- [x] **Acceptance**: env 变量覆盖默认；prod 缺关键字段启动 fail-fast

### S2 — CORS 配置化
- [x] `app.py` 从 settings 读
- [x] dev 默认 `["http://localhost:5173", "http://127.0.0.1:5173"]`
- [x] prod 必须显式设
- [x] **Acceptance**: prod 模式 + 未配 origin → 启动 fail

### S3 — 文档开关
- [x] `docs_url=None` 当 `settings.env == "prod"` 且 `enable_docs=False`

### S4 — API Key 认证（MVP）
- [x] mutating routes 用 `Depends(verify_api_key)` 检 `X-API-Key`
- [x] settings.api_keys 集合校验
- [x] **Acceptance**: 无 header 401；download GET 也纳入 API-key 保护，其他 read-only GET 仍按 MVP 暴露

### S5 — JWT/OAuth（**生产留 hook，先不做**）

### S6 — Rate limit
- [x] `slowapi`
- [x] POST `/backtests/run` 10/分/key
- [x] POST `/universe/refresh` 1/分

### S7 — 路径与正则校验（**修正语法**：pydantic v2）
- [x] run_id: `Annotated[str, StringConstraints(pattern=r"^btk_\d{4,6}$")]`
- [x] report_id: 同模式
- [x] download 路径 resolve + 白名单 root 检查

### S8 — Secret 管理
- [x] `.env` in `.gitignore`（验证已加）
- [x] CoinGecko / CryptoCompare API key 走 env
- [x] grep 全仓无硬编码 secret

### S9 — Authorized static delivery（**新增 codex**）
- [x] 见 F1；不用 mount 已完成，download GET 鉴权已接入 `verify_api_key`

---

## Phase O — 可观测性

### O1 — 结构化日志
- [x] `structlog` JSON formatter
- [x] 每请求记录 method/path/status/duration_ms/run_id（如有）

### O2 — Request ID 中间件
- [x] 加 `X-Request-ID` (uuid4)；日志带 request_id

### O3 — Prometheus
- [x] `prometheus-fastapi-instrumentator`
- [x] 暴露 `/metrics`（auth 后或 internal only）
- [x] 业务指标：`atlas20_backtests_total{status}`, `atlas20_backtest_duration_seconds`

### O4 — Error tracking
- [x] Sentry SDK env-gated

### O5 — Health/Readiness
- [x] `/healthz` 简单 200
- [x] `/readyz` 检 DB 连接 + report_root 可写

### O6 — 日志保留/轮转/脱敏（**新增 codex**）
- [x] `logging.handlers.RotatingFileHandler`（local）或 stdout + journald（容器）
- [x] redact: `X-API-Key`, `Authorization`, `secret_key` 任何字段
- [x] 保留策略文档化

---

## Phase D — 部署与 DX

### D1 — Backend Dockerfile
- [x] Multi-stage builder + runtime；non-root user；HEALTHCHECK `/readyz`

### D2 — Frontend Dockerfile
- [x] Multi-stage vite build + nginx serve

### D3 — docker-compose
- [x] backend + worker + frontend
- [x] Volume: `data/` + `reports/`

### D4 — `.env.example` (backend)
- [x] 列全部 settings 字段

### D5 — Makefile
- [x] `make dev` / `make test` / `make build` / `make lint` / `make backup`

### D6 — CI（**扩展现有 `.github/workflows/ci.yml`**）
- [x] 加 `ruff check`
- [x] 加 `mypy --strict src/atlas20/api/`
- [x] 加 `tsc --noEmit`
- [x] 加 deploy job（tag 触发，当前为 deploy stub）

### D7 — Pre-commit
- [x] `.pre-commit-config.yaml`: ruff / prettier / eslint

### D8 — Release 流程
- [x] CHANGELOG.md 模板 + semver tag

### D9 — README
- [x] Quickstart 30 分钟可跑

### D10 — 磁盘配额监控（**新增 codex P/D**）
- [x] cron: `reports/` + `data/` 用量；超阈值告警（`python -m atlas20.api.storage` / `make storage`，超阈值 exit 2）

---

## Phase T — 测试与质量门（**嵌入各 phase**）

> **修正**：不是末期一次性写，而是每个 R/E/P/F 项 PR 自带测试。

### T1 — Schema validation 测试（嵌入 E7/S7）
- [x] POST extra field → 422
- [x] POST bad date / invalid model values → 422
- [x] POST start > end → 422（schema 明确用例覆盖）
- [x] GET unknown compare ids → 404
- [x] POST 越界 topN/slots → 422

### T2 — Fixture 复位
- [x] `tests/conftest.py` 提全局 autouse 环境/cache 隔离与 DB fixture seed

### T3 — Engine 集成
- [x] 用小窗口（30 天 Top-5）真跑一次 backtest，断言产物齐 + DB 行写

### T4 — Playwright e2e
- [x] `apps/web/e2e/` 6 page × 1 smoke
- [x] **嵌入 U phase**

### T5 — axe-core a11y
- [x] vitest 集成；每 page 一个 a11y test

### T6 — Load test
- [ ] `locust` 或 `k6`：100 RPS, p95 < 200ms（mock data 时基线）

### T7 — Type strict
- [x] `mypy --strict src/atlas20/api/`
- [x] `tsc --strict --noEmit`

### T8 — Lint 严格
- [x] `ruff check` 0
- [x] `eslint --max-warnings 0`

### T9 — OpenAPI snapshot（**新增 codex**）
- [x] CI 跑 `fastapi.openapi()` 写到 `apps/web/src/lib/api-schema.json`
- [x] frontend `lib/api.ts` 类型与 schema 不一致时 CI fail
- [x] 可选：`openapi-typescript` 自动生成 TS client

---

## Phase Q — 代码质量（**降级 Q1/Q7**）

### Q2 — Dependency Injection
- [x] FastAPI `Depends(get_session)` 注入 persistence session；services 使用 repositories

### Q3 — Service 接口抽象
- [ ] `services/protocols.py` Protocol；mock_impl + real_impl

### Q4 — Settings 中心（见 S1）

### Q5 — 时间戳 helper
- [x] `src/atlas20/api/_time.py:utc_now_iso()` / `today()` 替手撕字符串

### Q6 — 错误处理统一
- [ ] FastAPI exception_handler 全局；统一 `{error: {code, message, details, request_id}}`

### ~~Q1 mock_data 拆 JSON~~ — 删除（DB seeding 后冗余）

### ~~Q7 每文件 < 100 LOC~~ — 删除（武断指标）

---

## Phase C — 契约边角

### C1 — 删 `view` 参数（前端 + 后端）
### C2 — chip 语义对齐（家族 chip OR strategy substring）
### C3 — anchor date 用 UTC 时钟（**修正语法**）
- [x] `atlas20.api._time.today()` 使用 UTC 时钟并支持 `ATLAS20_ANCHOR_DATE`

### C4 — register_new_backtest 双写 runs_list（Phase P 之后自然解决）
### C5 — favorite 同步 queue（Phase P 之后自然解决）

### ~~C6 query 字段顺序对齐~~ — 删除（非功能）
### ~~C7 `/api/v1`~~ — 延期（本地 MVP 不需要）

---

## Phase A — A11y（**精简**）

### A1 — axe-core 在 CI 跑（同 T5） — [x]
### A2 — 键盘导航 audit + skip-to-content + focus trap — [ ] skip link / Dialog focus trap 已落地，仍需人工全量键盘 audit
### A3 — Screen reader live regions（Pill / Toast） — [x]
### A4 — 颜色对比度 WCAG AA — [ ] 需要浏览器/设计 token 人工复核
### A7 — Mobile responsive audit at 375/768/1024
### A8 — React `<ErrorBoundary>` 每 page 包 — [x]

### ~~A5 i18n~~ — 删除
### ~~A6 light mode~~ — 删除
### ~~A9 404 page~~ — 不适用（单页无路由）

---

## Phase L — 合规与法律（按需，外网部署才做）

### L1 — 隐私政策模板
### L2 — Terms / Disclaimer（金融数据非投资建议）
### L3 — 用户数据导出/删除接口（GDPR）
### L4 — Cookie 横幅（如有 tracking）
### L5 — 数据保留承诺文档化

> **本地/内网部署可全部跳过**，文档明示「不暴露外网」。

---

## 优先级与里程碑（**修订自 v1**）

### MS-1 — Real Data Demo（**7-10 天**，原 1 周低估）
**Status 2026-05-27**: 基本完成。剩余为个别生产验收用例收口。
- Phase X + R1/R2/R3/R6/R8 + U4-U9 部分（接现成组件）
- 不做 R7/R10（要等 S/E）

### MS-2 — Real Backtests + 持久化（**12-15 天**）
**Status 2026-05-27**: MVP 主链路完成。N worker API 场景验收、真实小窗口 engine 集成测试已补齐；剩余差距转入生产安全、质量门和 DX 项。
- P1-P6 + E1-E8 + X3/X4 完成
- T3 嵌入

### MS-3 — Production-ready（**8-12 天**）
**Status 2026-05-27**: 部分完成。Settings/auth/rate-limit/observability/Docker/CI 基线已落地；download GET 鉴权、`reports/latest` alias、磁盘阈值告警、OpenAPI snapshot、frontend schema drift gate、全 API mypy strict 已补齐。
- S1-S9 + O1-O6 + F1-F7 + D1-D10
- T9 OpenAPI snapshot

### MS-4 — Polish（按需）
**Status 2026-05-27**: 部分完成。U10/U11、axe、ErrorBoundary、Playwright e2e 已落地；load test、统一错误 envelope 仍未做。
- Q2-Q6, C1-C5, A1-A4/A7/A8, U10/U11, T4/T5/T6, F2-F5

---

## 工作量估算（**用 codex 修订值**）

| Phase | v1 估算 | v2 修订 | 修订原因 |
|---|---|---|---|
| X | — | 2-3 | 新增 |
| R | 3-4 | 5-7 | 加 CSV 适配 + 缓存 + provenance + race handling |
| E | 3-5 | 7-10 | 子进程 worker + 状态机 + 资源校验 |
| P | 2-3 | 4-6 | migration + 备份 + idempotency |
| F | 2 | 4-6 | 安全下载 + manifest + 多格式 |
| U | 2-3 | 2-3 | 不变（组件已有） |
| S | 2 | 4-6 | settings + authz + headers + secrets |
| O | 1-2 | 2-3 | + 日志轮转 + 脱敏 |
| D | 2-3 | 4-6 | + 卷 + envs + 健康检查 + 部署 workflow |
| T | 2-3 | 嵌入各 phase | 不单算 |
| Q | 2-3 | 2-3 | 删 Q1/Q7 后量等 |
| C | 1 | 0.5 | 删 C6/C7 |
| A | 2-3 | 2-3 | 删 A5/A6 |
| L | — | 2-3 | 仅外网部署 |
| **总** | **24-36** | **39-58** | **codex 翻倍属实**：约 8-12 周单人 / 4-6 周两人 |

---

**Last updated**: 2026-05-27 (implementation status calibration)
**Maintainer**: Atlas20 team  
**v1**: `a43a304`  
**v2**: post-codex roadmap, calibrated against current implementation
