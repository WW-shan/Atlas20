# Atlas20 全栈完工清单 (Post-R3 Roadmap)

**生成时间**: 2026-05-19  
**基线 commit**: `cef7f1b`  
**当前状态**: R3 UI 重设计 + mock 后端契约对齐已完成（三轮交叉审查），但真实数据/真实回测/持久化/部署全部缺失。

---

## 目录

- [Phase R — 真实数据接入 (Real-data integration)](#phase-r--真实数据接入-real-data-integration)
- [Phase E — 真实回测执行 (Engine integration)](#phase-e--真实回测执行-engine-integration)
- [Phase P — 持久化 (Persistence)](#phase-p--持久化-persistence)
- [Phase F — 报告生成与静态文件 (File generation)](#phase-f--报告生成与静态文件-file-generation)
- [Phase U — 前端 UI 收尾 (Loading/Error/Modals)](#phase-u--前端-ui-收尾-loadingerrormodals)
- [Phase S — 安全与认证 (Security & Auth)](#phase-s--安全与认证-security--auth)
- [Phase O — 可观测性 (Observability)](#phase-o--可观测性-observability)
- [Phase D — 部署与 DX (Deployment & DX)](#phase-d--部署与-dx-deployment--dx)
- [Phase T — 测试与质量门 (Tests & Quality gates)](#phase-t--测试与质量门-tests--quality-gates)
- [Phase Q — 代码质量重构 (Code quality)](#phase-q--代码质量重构-code-quality)
- [Phase C — 契约边角 (Contract edges)](#phase-c--契约边角-contract-edges)
- [Phase A — A11y & 国际化 (Accessibility / i18n)](#phase-a--a11y--国际化-accessibility--i18n)

---

## Phase R — 真实数据接入 (Real-data integration)

> 目标：把 `mock_data.py` 的字面量替换为从 `reports/` 和 `data/processed/` 读真实 CSV。

### R1 — Overview champion + top_strategies + equity 真实化
- [ ] `src/atlas20/api/services.py:get_overview` — 从 `reports/latest/strategy_summary.csv` 读 31 个策略，按 sharpe 降序取 top 3 → `top_strategies`；最高 sharpe 行 → `champion`
- [ ] 从 `reports/latest/equity_curves.csv` 读 champion 列时间序列 → `equity_curve`（按月 resample 取 6 个点）
- [ ] 从 `reports/latest/daily_returns.csv` 读 champion 列 → `daily_returns`
- [ ] `equity_overlay.series` 用 champion 累计回报 vs BTC_BH__always_on 列
- [ ] `hero_kpi.ytdReturn / sharpe / maxDd / winRate` 从同 csv 计算
- [ ] `aum / regime / rebalance` 暂时维持半字面量（无真实数据源），但 `rebalance.ts` 用 `equity_curves.csv` 最后一个交易日
- [ ] **Acceptance**: GET `/api/overview` 返回的 `champion.strategy` 是真实 strategy_summary.csv 里 sharpe 最高那行；hero_kpi 与该行的 sharpe / max_drawdown 一致
- **Files**: `services.py`, 新增 `services_real.py` 或 `data_access.py` 拆分

### R2 — Run History 真实化
- [ ] 在 `services.list_runs` 之前，扫描 `reports/app_runs/*/summary.csv`
- [ ] 每个 dir 一个 RunRow，缺字段从 dir name 派生（`btk_NNNN_strategy_window` 规范化）
- [ ] 如果 `reports/app_runs/` 为空，fallback 到 mock_data
- [ ] `services.get_run` / `get_run_detail` 同步走目录扫描
- [ ] `get_run_detail.kpi` 从 `summary.csv` 直接读，不再 derive
- [ ] `get_run_detail.equity_overlay` 从 `reports/app_runs/{id}/equity_curve.csv` 读
- [ ] **Acceptance**: 跑一次 `python -m atlas20.pipeline` 之后 GET `/api/runs` 看到真实 run

### R3 — Compare 真实化
- [ ] `services.get_compare` — 从 `reports/latest/strategy_summary.csv` 按 frontend 传入的 strategy id 精确匹配
- [ ] `equity` 数据用 `equity_curves.csv` 多列拼接
- [ ] `overlap.matrix` 用 `selection_history` 计算真实 Jaccard（暂可保留 mock）
- [ ] unknown ids → 404 而不是静默回退
- [ ] **Acceptance**: 用 strategy_summary.csv 真实列名调 `/api/compare?ids=BTC_BH__always_on,TOP20_MOM_top4_monthly__always_on` 拿到真实指标

### R4 — Reports 真实化
- [ ] `services.list_reports` — 扫描 `reports/latest/` 和 `reports/{config}/*` 目录
- [ ] `*.md / *.pdf / *.png` → ReportEntry
- [ ] `report_type` 推断：含 "weekly" → weekly；含 "btk_" → run；含 "compare" → compare；含 "universe" → universe
- [ ] `thumbnail` 推断：含 equity → equity；含 drawdown → lines；含 sector → bars
- [ ] `size_bytes` 来自 `path.stat().st_size`
- [ ] `generated_at` 来自 `path.stat().st_mtime` ISO
- [ ] **Acceptance**: GET `/api/reports` 至少返回 `atlas20_report.md` 一项

### R5 — Featured Digest 真实化
- [ ] `services.get_featured_digest` — 取 `reports/latest/` 中最新 `*.md` 文件作 featured
- [ ] subtitle 包含 champion strategy + YTD + universe 信息（拼自 strategy_summary）
- [ ] **Acceptance**: GET `/api/reports/digest/featured` `title` 含真实 generated date

### R6 — Universe Timeline 真实化
- [ ] `services.get_universe_timeline` — 读 `data/processed/rebalance_universe.csv`
- [ ] 每个 rebalance date 的 top-20 token 列表 → 转 segments
- [ ] rotations 用 selection_history 的 major-change 行（≥2 个 token 进出）
- [ ] `range.start/end` 用 csv 第一/最后日期
- [ ] **Acceptance**: 真实数据下应该看到 BTC、ETH 占满 180 天，altcoin 轮换

### R7 — Data Sources 真实化
- [ ] `services.get_data_sources` — probe CoinGecko / CryptoCompare 真实状态（HEAD 请求 + 计时）
- [ ] 用 `requests.get(timeout=2)`；网络不通设 `error`；>500ms 设 `degraded`；<200ms 设 `healthy`
- [ ] `last_sync_seconds` 从 `data/raw/{provider}/` 最新文件 mtime 算
- [ ] 用 in-memory TTL cache 5 分钟避免每请求都 probe
- [ ] **Acceptance**: GET `/api/universe/sources` 真实显示 CoinGecko/CryptoCompare 状态

### R8 — Data Alerts 真实化
- [ ] `services.get_data_alerts` — 读 `data/processed/data_quality.csv`
- [ ] 每行（gap/outlier/stale）→ DataAlert
- [ ] `severity` 从列 `severity` 或按规则推断（gap → rose；stale → cyan；resolved → emerald）
- [ ] **Acceptance**: data_quality.csv 是空时返回 `[]`，有行时正确映射

### R9 — Options 真实化
- [ ] `services.get_options_payload` — 当前返回 `{}`，扩为：
  ```json
  {
    "strategy_families": ["ATLAS", "Momentum", "MeanRev", "Carry", "Other"],
    "rebalance_frequencies": ["Weekly", "Biweekly", "Monthly"],
    "presets": [list of preset names from config/*.yaml],
    "date_ranges": ["7d", "30d", "90d", "ytd", "all"]
  }
  ```
- [ ] 前端 `ParameterSidebar` 的 `<select>` 改从 `/api/options` 拉
- [ ] **Acceptance**: 改 `config/*.yaml` 添加新 preset 后，前端下拉框自动看到

### R10 — Universe Refresh 真实化
- [ ] `services.refresh_universe` — 调 `atlas20.data.processor.download_and_cache_raw_data`
- [ ] 在 FastAPI BackgroundTasks 中执行，不阻塞响应
- [ ] 返回 `{"refreshed_at": now, "status": "queued"}`
- [ ] 加新端点 GET `/api/universe/refresh-status` 看进度
- [ ] **Acceptance**: 点 FORCE REFRESH 后 raw 目录里有新文件 mtime

---

## Phase E — 真实回测执行 (Engine integration)

> 目标：POST `/backtests/run` 真跑 `atlas20.backtest.engine.run_backtest`。

### E1 — BacktestConfig → ResearchConfig 适配
- [ ] 新增 `services.config_adapter.py`：把前端 R3 BacktestConfig 转换为 `atlas20.config.ResearchConfig`
- [ ] `preset` → 找 `config/{slug}.yaml` 或 `config/base.yaml`
- [ ] `universe.topN/excludeStable/excludeWrapped` → `UniverseConfig` 字段
- [ ] `window.start/end/rebalance` → `RebalancingConfig`
- [ ] `allocation.positionPct/slots` → `StrategyConfig.max_weight / max_positions`
- [ ] `costs.feeBps/slippageBps` → `FrictionConfig`
- [ ] **Acceptance**: 单测覆盖每种 BacktestConfig 都能合法转换

### E2 — 异步执行框架
- [ ] FastAPI `BackgroundTasks` 模式（单进程内异步）—— MVP 选这个
- [ ] 或 `arq`/Celery + Redis（生产推荐）—— 留 hook
- [ ] `services.execute_backtest_async(run_id, config)` —— 在后台执行，写 status
- [ ] 状态机：`queued` → `running` → `completed` / `failed`
- [ ] 异常捕获并写入 `error` 字段
- [ ] **Acceptance**: POST 立即 200 返回 queued；轮询 `/runs/{id}` 看到状态变化

### E3 — 写盘
- [ ] 每次回测结束写 `reports/app_runs/{run_id}/`：
  - `summary.csv` — 与 strategy_summary.csv 同 schema 的单行
  - `equity_curve.csv`
  - `daily_returns.csv`
  - `weights.csv`
  - `params.json` — 原始 BacktestConfig
- [ ] **Acceptance**: 跑完后 `reports/app_runs/btk_0150/` 目录齐全

### E4 — 失败/超时处理
- [ ] 单次回测最长 5 分钟 timeout（可配）
- [ ] 引擎抛 ValueError/RuntimeError → 写 `status=failed, error=<msg>`
- [ ] **Acceptance**: 故意传 start>2030 触发数据缺失，状态变 failed 错误信息可读

### E5 — 并发限流
- [ ] 同时跑回测数 ≤ N（默认 2，env 可配）
- [ ] 超过用 asyncio.Semaphore 排队
- [ ] **Acceptance**: 快速 POST 5 次，前 2 个 running，后 3 个 queued

### E6 — 取消
- [ ] 加 POST `/api/runs/{id}/cancel` 路由
- [ ] running → cancelled；queued → 移除
- [ ] **Acceptance**: POST cancel 之后 status 是 cancelled

---

## Phase P — 持久化 (Persistence)

> 目标：进程重启后所有状态保留。

### P1 — 选型决策
- [ ] **MVP**: SQLite + SQLModel（FastAPI 同生态、零运维）
- [ ] **生产**: 后续可迁 PostgreSQL（同 ORM 无痛切换）

### P2 — 表设计
- [ ] `runs` — id, strategy, family, universe, window_start, window_end, status, return_pct, sharpe, max_dd, duration_s, eta_s, spark (JSON), created_at, favorited, params (JSON), error
- [ ] `report_files` — id, run_id (FK), kind, path, size_bytes, generated_at
- [ ] `favorites` — 也可以就用 runs.favorited 列，单用户没必要单独表
- [ ] `kv_settings` — key, value, updated_at（杂项：anchor_date 覆盖、global counters）

### P3 — Repository 层
- [ ] `src/atlas20/api/repositories/runs_repo.py` — get/list/save/update/toggle_favorite
- [ ] `services.py` 改用 repository，不再直接读 mock_data
- [ ] mock_data 仅在表为空时作 seed 启动数据
- [ ] **Acceptance**: kill uvicorn 重启后 GET `/api/runs` 仍看到刚 POST 的回测

### P4 — Migration
- [ ] Alembic 初始化（或简单的 startup auto-create_all）
- [ ] `atlas20.api.db.init_db()` 在 app startup hook 执行
- [ ] **Acceptance**: `rm db.sqlite && uvicorn ...` 仍能正常启动并建表

### P5 — Seed 命令
- [ ] `python -m atlas20.api.seed` 把 mock_data 写入 db（demo 用）
- [ ] **Acceptance**: 新开发者 clone 之后一行命令初始化 demo 数据

---

## Phase F — 报告生成与静态文件 (File generation)

### F1 — 静态文件 mount
- [ ] `app.mount("/static", StaticFiles(directory="reports"))`
- [ ] `services.build_digest_download_url` / `build_report_download_url` 返回 `/static/{config}/{file}` 真实 URL
- [ ] **Acceptance**: 浏览器打开 download URL 真下载文件

### F2 — Featured Digest 自动生成
- [ ] 每周一 0:00 UTC 用 `atlas20.reporting.report.build_markdown_report` 生成 weekly digest
- [ ] APScheduler 或 cron 触发
- [ ] **Acceptance**: 可手动调 `python -m atlas20.api.scripts.generate_digest --week 20`

### F3 — PDF 渲染
- [ ] `weasyprint` 把 markdown → PDF（或 `pandoc`）
- [ ] 暴露 `/static/.../digest.pdf`
- [ ] **Acceptance**: GET `/api/reports/digest/download?format=pdf` 返回 URL，URL 真下 PDF

### F4 — PNG snapshot
- [ ] `playwright` 截前端 hero card 作 PNG
- [ ] 或 `matplotlib` 出 equity curve PNG
- [ ] **Acceptance**: format=png 真下载图片

### F5 — Bundle ZIP
- [ ] format=bundle 时 zip 所有格式打包
- [ ] **Acceptance**: 下载 ZIP 解开有 md/pdf/png/csv

### F6 — 防路径穿越
- [ ] `build_report_download_url(report_id)` 校验 `report_id` 不含 `..` / `/`
- [ ] 用 `Path.resolve()` 检查在白名单目录内
- [ ] **Acceptance**: POST `/api/reports/..%2F..%2Fetc%2Fpasswd/download` 返回 400

---

## Phase U — 前端 UI 收尾 (Loading/Error/Modals)

> 三轮审查中标记为 "deferred until real backend" 的全部前端项。

### U1 — `<Skeleton>` 组件
- [ ] 新建 `components/ui/Skeleton.tsx` — 灰色 placeholder + shimmer 动画
- [ ] 多种尺寸：line/card/chart
- [ ] **Acceptance**: 加 storybook story 看效果

### U2 — `<ErrorBanner>` 组件
- [ ] 新建 `components/ui/ErrorBanner.tsx` — rose 边框 + 重试按钮
- [ ] Props: `error: Error, onRetry?: () => void`
- [ ] **Acceptance**: 全局 retry 一次会重发 query

### U3 — `<EmptyState>` 组件
- [ ] 新建 `components/ui/EmptyState.tsx` — 居中 muted 文字 + 可选 CTA
- [ ] **Acceptance**: history 过滤无结果时显示

### U4 — Overview 接 loading/error
- [ ] `features/overview/OverviewTab.tsx` — `if (overviewQuery.isLoading) return <Skeleton />; if (overviewQuery.isError) return <ErrorBanner />;`
- [ ] 移除 `initialData: fallbackOverview` （改用 `placeholderData`）
- [ ] **Acceptance**: 断网/后端关时不再静默显示 mock

### U5 — Backtest Studio 同步
- [ ] 同上对 `detailQuery` 和 `queue`

### U6 — Compare 同步
- [ ] 同上对 `getCompare` query

### U7 — Run History 同步
- [ ] 同上对 `listRuns` query
- [ ] 添加 EmptyState 当过滤无结果

### U8 — Universe 同步
- [ ] 同上对 3 个 query

### U9 — Reports 同步
- [ ] 同上对 featured + archive

### U10 — `+ ADD STRATEGY` modal
- [ ] `components/compare/AddStrategyModal.tsx` — multi-select 真改 selections state
- [ ] 与 `/api/options` 拉取的策略列表联动
- [ ] **Acceptance**: 加策略后 compare 表格多一列

### U11 — `+ NEW REPORT` modal
- [ ] `components/reports/NewReportModal.tsx` — 选 type/format/strategy → POST `/api/reports/generate`
- [ ] 后端加对应 endpoint（Phase F1 后做）
- [ ] **Acceptance**: 提交后 archive 出现 generating 卡片

### U12 — Loading 期间禁用按钮
- [ ] `RUN BACKTEST` / `FORCE REFRESH` / `DOWNLOAD` 在 isLoading 时 disabled
- [ ] 已部分实现，需全面 audit

---

## Phase S — 安全与认证 (Security & Auth)

### S1 — Settings 中心
- [ ] `src/atlas20/api/settings.py` — pydantic-settings BaseSettings
- [ ] 字段：`env`, `cors_origins`, `db_url`, `secret_key`, `api_keys`, `enable_docs`
- [ ] 从 `.env` 读
- [ ] **Acceptance**: `ATLAS20_ENV=prod uvicorn ...` 启动行为变化

### S2 — CORS 配置化
- [ ] `app.py` 改读 settings.cors_origins
- [ ] **Acceptance**: prod 设 `cors_origins=https://atlas20.example.com` 后 vite dev 5173 被拒

### S3 — 文档开关
- [ ] `FastAPI(docs_url=None if settings.env == "prod" else "/docs", redoc_url=None if ...)` 
- [ ] **Acceptance**: prod 模式 GET `/docs` 404

### S4 — API Key 认证（MVP）
- [ ] `Depends(verify_api_key)` 从 `X-API-Key` header
- [ ] settings.api_keys 是 set
- [ ] 401 if missing/invalid
- [ ] **Acceptance**: 没带 header 的请求 401

### S5 — JWT/OAuth（生产，可选）
- [ ] FastAPI `OAuth2PasswordBearer` + Authlib
- [ ] 留 hook，先不实现

### S6 — Rate limiting
- [ ] `slowapi` 中间件
- [ ] POST `/backtests/run` 限 10/分钟/key
- [ ] POST `/universe/refresh` 限 1/分钟
- [ ] **Acceptance**: 11 次提交第 11 次 429

### S7 — Input sanitization
- [ ] `report_id` / `run_id` 用正则 `^btk_\d{4}$` / `^r\d+$` 校验
- [ ] 所有路径参数走 pydantic `constr(regex=...)`
- [ ] **Acceptance**: 路径穿越尝试返回 400

### S8 — Secret 管理
- [ ] `.env` 加入 `.gitignore`（验证）
- [ ] CoinGecko/CryptoCompare API key 走 env
- [ ] **Acceptance**: `git grep -i "api_key" -- '*.py'` 找不到硬编码

---

## Phase O — 可观测性 (Observability)

### O1 — 结构化日志
- [ ] `structlog` 或 `logging` + JSON formatter
- [ ] 每请求记录 method/path/status/duration/run_id
- [ ] **Acceptance**: 日志可被 `jq` parse

### O2 — Request ID
- [ ] 中间件加 `X-Request-ID` header（uuid4）
- [ ] 日志带 request_id 字段
- [ ] **Acceptance**: 一次请求所有日志行同 request_id

### O3 — Prometheus metrics
- [ ] `prometheus-fastapi-instrumentator`
- [ ] 暴露 `/metrics`
- [ ] 自定义业务指标：`atlas20_backtests_total`, `atlas20_backtest_duration_seconds`
- [ ] **Acceptance**: `curl /metrics` 输出 Prometheus exposition

### O4 — Error tracking
- [ ] Sentry SDK 集成（env-gated）
- [ ] **Acceptance**: 故意 raise 后 Sentry 仪表板看到

### O5 — Health endpoint
- [ ] GET `/healthz` — 简单 200 OK
- [ ] GET `/readyz` — 检查 DB 连接、数据目录可写
- [ ] **Acceptance**: 容器编排可挂

### O6 — 业务事件日志
- [ ] favorite/cancel/run_complete 等关键事件单独 log
- [ ] **Acceptance**: 业务事件可被 SIEM 索引

---

## Phase D — 部署与 DX (Deployment & DX)

### D1 — Dockerfile (backend)
- [ ] Multi-stage: builder（uv/pip install）+ runtime（python:3.11-slim）
- [ ] Healthcheck 指 `/healthz`
- [ ] Non-root user
- [ ] **Acceptance**: `docker build` + `docker run -p 8000:8000` 跑通

### D2 — Dockerfile (frontend)
- [ ] Multi-stage: builder（vite build）+ nginx 服务静态文件
- [ ] **Acceptance**: 同上

### D3 — docker-compose
- [ ] `compose.yml`：backend + frontend + （可选 postgres + redis）
- [ ] 一键 `docker compose up`
- [ ] **Acceptance**: 浏览器访问 localhost:80 看到完整应用

### D4 — .env.example
- [ ] backend `.env.example` 列所有 settings 字段 + 默认值
- [ ] frontend `apps/web/.env.example` 已存在，校验完整

### D5 — Makefile / npm-run-all
- [ ] `make dev` 同时启 uvicorn + vite
- [ ] `make test` 跑 pytest + vitest
- [ ] `make build` 双向构建
- [ ] `make lint` ruff + eslint
- [ ] **Acceptance**: 单命令启动所有

### D6 — CI (GitHub Actions)
- [ ] `.github/workflows/test.yml` — push/PR 跑 pytest + vitest + build
- [ ] `.github/workflows/lint.yml` — ruff + eslint + tsc --noEmit
- [ ] `.github/workflows/deploy.yml` — tag push 触发 docker build & push
- [ ] **Acceptance**: PR 自动 status check

### D7 — Pre-commit hooks
- [ ] `.pre-commit-config.yaml` — ruff/black/eslint/prettier
- [ ] **Acceptance**: `git commit` 触发自动 format

### D8 — Release 流程
- [ ] CHANGELOG.md 模板
- [ ] semver tag 规范
- [ ] **Acceptance**: `git tag v0.1.0` 触发自动 release

### D9 — README 完善
- [ ] Quickstart：clone → make dev → 浏览器
- [ ] 架构图
- [ ] 配置项一览
- [ ] **Acceptance**: 新人能 30 分钟跑起来

---

## Phase T — 测试与质量门 (Tests & Quality gates)

### T1 — 集成测试覆盖
- [ ] tests/test_api_routes.py 加：非 canonical run detail 200
- [ ] 加：extra field → 422
- [ ] 加：bad date format → 422
- [ ] 加：start > end → 422
- [ ] 加：unknown compare ids → 404
- [ ] **Acceptance**: 这些 case 各 1 个测试

### T2 — Fixture 复位
- [ ] tests/conftest.py 提一份全局 `restore_mock_data` autouse
- [ ] **Acceptance**: services 和 routes 测试都受保护

### T3 — Engine 真集成测试
- [ ] tests/test_api_engine_integration.py — POST `/backtests/run` 真跑（用小窗口快测）
- [ ] **Acceptance**: 端到端 60 秒内完成

### T4 — Playwright e2e
- [ ] `apps/web/e2e/` 加 spec：6 个 page 各 1 个 smoke
- [ ] 验证：hero 数字、表格行数、tab 切换、download 触发
- [ ] **Acceptance**: `npm run e2e` 全过

### T5 — axe-core a11y
- [ ] vitest 集成 `@axe-core/react`
- [ ] 每个 page 一个 a11y test
- [ ] **Acceptance**: 0 violations

### T6 — Load test
- [ ] `locust` 或 `k6` 脚本
- [ ] Target: 100 RPS、p95 < 200ms（mock data）
- [ ] **Acceptance**: 文档化 baseline

### T7 — Type check 严格化
- [ ] backend `mypy --strict src/atlas20/api/` 通过
- [ ] frontend `tsc --noEmit --strict` 通过
- [ ] **Acceptance**: 双 0 error

### T8 — Lint
- [ ] backend `ruff check src/ tests/` 0 warning
- [ ] frontend `eslint . --max-warnings 0` 0
- [ ] **Acceptance**: 双 0

---

## Phase Q — 代码质量重构 (Code quality)

### Q1 — mock_data 拆分
- [ ] 把 `mock_data.py` 拆成 `mock/overview.json`、`mock/runs.json` 等
- [ ] 加载用 `json.loads(Path(...).read_text())`
- [ ] **Acceptance**: 文件结构更清晰；非代码改动易 diff

### Q2 — Dependency Injection
- [ ] FastAPI `Depends(get_runs_repo)` 注入
- [ ] 测试时换 InMemoryRunsRepo
- [ ] **Acceptance**: 单测无需 patch 模块

### Q3 — Service 接口抽象
- [ ] `services/protocols.py` 定义 Protocol
- [ ] 实现 `services/mock_impl.py` + `services/real_impl.py`
- [ ] settings 切换
- [ ] **Acceptance**: 一行 env 切 mock/real

### Q4 — Pydantic Settings 配置中心
- [ ] 见 S1
- [ ] **Acceptance**: 所有常量集中

### Q5 — 时间戳 helper
- [ ] `utils/time.py:utc_now_iso()` 替换手撕字符串
- [ ] **Acceptance**: 一处定义

### Q6 — 错误处理统一
- [ ] FastAPI exception_handler 全局拦 ValidationError / not found
- [ ] 统一 error response shape `{error: {code, message, details}}`
- [ ] **Acceptance**: 前端可统一处理

### Q7 — services.py 拆分
- [ ] 按 domain 拆：`services/overview.py`、`services/runs.py`、`services/compare.py`、`services/universe.py`、`services/reports.py`
- [ ] **Acceptance**: 每文件 < 100 LOC

---

## Phase C — 契约边角 (Contract edges)

### C1 — `view` 参数
- [ ] 后端 `list_runs` 删 `view`，路由签名也删
- [ ] 前端 listRuns 不传
- [ ] **Acceptance**: query string 不含 view

### C2 — chip 语义对齐
- [ ] 后端 `_matches_chip` 家族 chip 改为 `family OR strategy.includes(chip)`
- [ ] **Acceptance**: 单测覆盖 family + strategy 不同名场景

### C3 — ANCHOR_DATE 动态化
- [ ] `ANCHOR_DATE = date.today()`
- [ ] 测试 mock today() 用 freezegun
- [ ] **Acceptance**: 5 月跑 5 月 7d 范围正确

### C4 — register_new_backtest 双写
- [ ] 新 RunRowSummary 也插入 runs_list 头部（completed/queued 状态根据 engine 结果）
- [ ] **Acceptance**: POST 后 GET `/runs/{newId}` 200

### C5 — favorite 同步 queue
- [ ] toggle_run_favorite 扫描 queue 也更新
- [ ] **Acceptance**: queue 里的 favorited 字段一致

### C6 — _matches_query 字段顺序
- [ ] 后端字段顺序与前端对齐 `run_id, strategy, universe`
- [ ] **Acceptance**: 顺序一致（非功能修复，避免漂移）

### C7 — API versioning
- [ ] 全部 routers prefix 改 `/api/v1`
- [ ] 前端 `buildApiUrl` base 改 `/api/v1`
- [ ] **Acceptance**: 留 v2 演进空间

### C8 — Pagination 一致性
- [ ] `/api/runs` 已有；如果 `/api/reports` 列表变长也加
- [ ] 统一 `{items, total, page, pageSize}` shape
- [ ] **Acceptance**: 同 shape 跨 endpoint

---

## Phase A — A11y & 国际化 (Accessibility / i18n)

### A1 — axe-core 在 CI 跑
- [ ] 见 T5
- [ ] **Acceptance**: PR 自动 a11y check

### A2 — 键盘导航完整 audit
- [ ] 所有交互元素可 Tab 到达
- [ ] Skip-to-content 链接
- [ ] Focus trap on modals
- [ ] **Acceptance**: 仅键盘走完全部 6 个 page

### A3 — Screen reader live regions
- [ ] Pill status 变化 `aria-live="polite"`（SPEC §1.6 已写）
- [ ] toast / 错误消息 live region
- [ ] **Acceptance**: NVDA / VoiceOver 朗读

### A4 — 颜色对比度
- [ ] 跑 axe contrast check
- [ ] 必要时调 tokens
- [ ] **Acceptance**: WCAG AA pass

### A5 — i18n 框架
- [ ] react-i18next 集成（仅基础设施，先不译）
- [ ] 提取所有 hardcoded 字符串到 `messages.en.json`
- [ ] **Acceptance**: 切换语言不报错（即使内容不变）

### A6 — Dark/light mode
- [ ] R3 是 dark-only；如需 light，添加 `[data-theme="light"]` 覆盖 token
- [ ] **Acceptance**: 切主题不破布局

### A7 — Mobile responsive
- [ ] 现 CSS 有部分 media query；audit 6 个 page 在 375/768/1024 宽度
- [ ] **Acceptance**: 无横向滚动

### A8 — Error Boundary
- [ ] React `<ErrorBoundary>` 包每个 page
- [ ] **Acceptance**: 某 page 崩溃不带挂全应用

### A9 — 404 page
- [ ] 应用不在路由层；如未来加路由，加 NotFoundPage
- [ ] 暂不适用

---

## 优先级与里程碑建议

### MS-1 (1 周) — Real Data Demo
完成：R1, R2, R3, R6, R8, F1, U1-U9 子集
价值：演示给真实用户时数据是真的

### MS-2 (1-2 周) — Real Backtests
完成：E1-E6, P1-P5, U10
价值：用户可以真跑回测

### MS-3 (1 周) — Production-ready
完成：S1-S8, O1-O6, D1-D6, T1-T4
价值：可部署上线

### MS-4 (按需) — Polish
完成：Q1-Q7, C1-C8, A1-A9, T5-T8, F2-F6, U11-U12
价值：长期可维护性 + a11y + i18n

---

## 工作量估算

| Phase | 估算（人天） | 备注 |
|---|---|---|
| R | 3-4 | 数据接入直接但量大 |
| E | 3-5 | 异步 + 状态机有坑 |
| P | 2-3 | SQLite + repository |
| F | 2 | 静态 + PDF 渲染 |
| U | 2-3 | 三个新组件 + 多页接入 |
| S | 2 | API key MVP |
| O | 1-2 | 标准库 |
| D | 2-3 | Docker + CI |
| T | 2-3 | 写测试本身 |
| Q | 2-3 | 重构 |
| C | 1 | 边角修复 |
| A | 2-3 | a11y audit |
| **总** | **24-36 人天** | ≈ 5-7 周单人 / 2-3 周两人 |

---

**Last updated**: 2026-05-19  
**Maintainer**: Atlas20 team
