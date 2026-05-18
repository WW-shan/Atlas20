# Atlas20 Redesign — Master PLAN

实施分阶段构建顺序。**前置阅读**：[[SPEC]]（本 PLAN 的所有规范引用以 SPEC 为准）。
**执行策略**：本 PLAN 中每个 Phase 由 **Claude 直接编码 → Codex 复核**（codeagent-wrapper `--backend codex` spec-review 风格）。
**串行 vs 并行**：Phase 0-1 严格串行；Phase 2+3 可**并行**（ui/* 和 charts/* 无依赖）；Phase 4 串行（被 P2/P3 产物消费）；Phase 5-10 各页相互独立，可在 Phase 4 完成后**并行委派**（多 agent 各占一页）。

---

## 总览（11 个 Phase）

```
P0 tokens/字体  ── P1 AppShell/6tab  ── P2 ui/* baseline ──┐
                                                            ├── P4 lib/api.ts schema ──┬── P5 page1 ──┐
                                       P3 charts baseline ──┘                          ├── P6 page2 ──┤
                                                                                       ├── P7 page3 ──┤
                                                                                       ├── P8 page4 ──┼── P11 cleanup
                                                                                       ├── P9 page5 ──┤
                                                                                       └── P10 page6 ─┘
```

---

## Phase 0 · CSS Tokens + 字体 + Reset

**目标**：暗背景 + 6 色 + Mono 数字 + 通用工具类一次性进入全局 stylesheet。

**改动文件**
- `apps/web/src/styles/index.css` — 替换 `:root` 为 SPEC §1 完整 token，加 `@font-face` 或 import URL；新增 `.mono` 工具类。
- `apps/web/index.html` — `<link>` 字体（Inter Display / JetBrains Mono — Google Fonts CDN 或本地）。

**验收**
- 在浏览器开发者工具看任意元素，computed `--bg` 等 9 个色值匹配 SPEC §1。
- 任一现有页面：用 `.mono` 包裹的数字呈现 JetBrains Mono + tabular-nums。
- 现有 `pnpm test` 全绿（无 token-name 硬编码到 JS 的回归）。

**估时**：30 min（含字体加载验证）

---

## Phase 1 · AppShell + 6-Tab 路由重构

**目标**：左 wordmark + 中 6 tab + 右 search/cog/avatar 的顶导落地，6 个 \*Tab 文件均创建为占位（仅 `<SectionHeader>{title}</SectionHeader> placeholder`），导航点击切换可用。

**改动文件**
- `apps/web/src/components/navigation/TabSwitcher.tsx` — 改 `ConsoleTab` 为 6-tuple union；render 6 个 button，active 态用 SPEC §1.1 gold underline。
- `apps/web/src/components/layout/AppShell.tsx` — 加 search input 占位 + 高度 56px。
- `apps/web/src/pages/ResearchConsolePage.tsx` — `useReducer` 维护 `{ tab, prefillRunId? }`；switch 6 个 case 渲染对应 *Tab。
- **新增** 6 文件（占位骨架 — 纯 `<div>` + `<h2>` 文本，**不引用任何 ui/* 组件**，P2 建完后再升级）：
  - `features/overview/OverviewTab.tsx`（已有，本期改为占位骨架，下个 phase 重写）
  - `features/backtest/BacktestStudioTab.tsx`
  - `features/compare/StrategyCompareTab.tsx`
  - `features/history/RunHistoryTab.tsx`
  - `features/universe/UniverseHealthTab.tsx`
  - `features/reports/ReportsExportsTab.tsx`
- `apps/web/src/pages/ResearchConsolePage.test.tsx` — 更新到 6 标签集合。

**验收**
- 6 tab 切换无报错；激活态视觉 = SPEC §1.1 gold underline。
- `pnpm test` 全绿。
- 键盘 Tab 顺序覆盖 6 个 tab + search input + avatar。

**估时**：45 min

---

## Phase 2 · `components/ui/*` Baseline

**目标**：所有 6 页消费的通用组件按 SPEC §6 typed API 一次性建立。

**改动文件**（新建）
- `components/ui/Pill.tsx` + `Pill.test.tsx`
- `components/ui/StatusDot.tsx` + test
- `components/ui/KpiTile.tsx`（含 `inline` 变体） + test
- `components/ui/SectionHeader.tsx` + test
- `components/ui/Card.tsx`（含 `hero`/`default`/`report` variant） + test
- `components/ui/Button.tsx`（5 variant + `loading` + `disabled`） + test
- `components/ui/Pager.tsx` + test
- `components/ui/EmptyState.tsx` + `ErrorBanner.tsx` + `Skeleton.tsx` + test

**验收**
- 每组件至少 1 个 snapshot/role 测试。
- Storybook 不要求（不在 deps），但每组件必须有一个 `.example.tsx` 子目录或在 test 文件 demonstrate 三种 prop 组合。
- 类型契约与 SPEC §6 完全一致（含 `PillTone` typed union）。

**估时**：90 min（含 30 min buffer for review fixes）

---

## Phase 3 · `components/charts/*` Baseline

**目标**：扩展 Sparkline + 新建 OverlayLineChart。

**改动文件**
- `components/charts/SparklineChart.tsx` — 加 `tone` prop 支持 6 色 + `dashed`；保持向后兼容。
- `components/charts/OverlayLineChart.tsx` — **新建**（SPEC §6.6 完整 API）；基于 Recharts `ResponsiveContainer + LineChart + Tooltip`；color 走 CSS var；主线 `glow` 用 `filter: drop-shadow(0 0 6px var(--gold-glow))`。
- 各自 test：snapshot + 至少 2 个 tone 渲染。

**验收**
- 任一 dev 页面临时挂载 OverlayLineChart 渲染 mock 数据，浏览器肉眼看金色发光主线 + violet 副线。
- Test 全绿。

**估时**：60 min

---

## Phase 4 · `lib/api.ts` Schema + Fallback + `qk` Registry

**目标**：所有 6 页消费的 type / 函数 / fallback / query-key 单源就位（**最关键的一个 Phase**，6 页并行依赖此完成）。

**改动文件**
- `apps/web/src/lib/api.ts` —
  - 扩展 `OverviewPayload`（SPEC §7.1 新增字段）
  - 新增 SPEC §7.2 全部 types
  - 新增 SPEC §8 函数（mock 实现：先返回 `fallback*` 常量；后端没接前用 `setTimeout(resolve, 300)` 模拟延迟）
  - 新增 SPEC §8 fallback 常量（数据照 7 份 page plan 的固定 mock）
- `apps/web/src/lib/qk.ts` — **新建**，导出 SPEC §9 的 `qk` 对象。
- 现有 `fallbackOverview` 扩展新增字段（aum / strategies / regime / rebalance / equity_overlay / hero_kpi），数据值见 page1 plan 描述。

**验收**
- TypeScript 编译 0 错误（`pnpm typecheck`）。
- `fallbackOverview` 渲染到 page1 占位组件无 undefined。
- 每个 fallback 常量都通过新增 `lib/api.test.ts` 一个 minimal shape 断言（确保未漏字段）。

**估时**：120 min（含 30 min buffer for fallback data alignment + typecheck）

**Codex 复核重点**：types 是否与 SPEC §7 字段名/可选性一一对应；qk 是否覆盖所有 page 使用点；fallback 数据是否与各 page plan 内固定 mock 对应。

---

## Phase 5 · Page 1 Overview 实施

**前置**：P0-P4 完成。
**参考**：[[page1-home-overview]] + SPEC § 全部相关条款。

**改动文件**
- `features/overview/OverviewTab.tsx` — 重写完整布局
- 新增内部小组件：
  - `components/overview/StrategyBarRow.tsx`
  - `components/overview/RegimeGauge.tsx`
- 删除：`components/overview/HeroSummary.tsx` / `TopStrategiesTable.tsx` / `StrategyLogicSummary.tsx`（迁移完成后）

**关键修订（来自 review）**
- AUM tile sparkline tone = **violet**（非 gold）。
- 4 个 hero KPI 含 `ytdReturn/sharpe/maxDd/winRate`，从 `overview.hero_kpi` 读。
- §9 加 "顶导 `Overview` 激活态 gold underline" 显式行。

**测试**：SPEC §13 page1 条目。

**估时**：120 min

---

## Phase 6 · Page 2 Backtest Studio 实施

**前置**：P0-P4 完成。
**参考**：[[page2-backtest-studio]] + SPEC。

**改动文件**
- `features/backtest/BacktestStudioTab.tsx` — 完整三栏。
- `features/backtest/useRunBacktest.ts` — 从 `features/dashboard/` 迁移。
- `features/backtest/useRunQueue.ts` — 新建，调 `qk.runs.queue()` + `listRunsQueue()`。
- `features/backtest/useChampionPreset.ts` — 迁移。
- `components/backtest/ParameterSidebar.tsx` — 重写（5 SectionHeader 分组）。
- `components/backtest/EquityWorkspace.tsx` — 重写（tab strip + OverlayLineChart + KPI ribbon）。
- `components/backtest/RunQueue.tsx` — 重写（6 张卡）。
- 删除：`features/dashboard/DashboardTab.tsx` + 其余 dashboard 旧文件。

**关键修订**
- Slider 旋钮 = violet（**非 gold**）。
- RUN ID 短格式：page header 也用 `btk_0142`（不再用 `btk_2026-05-18_0142`）。
- BacktestConfig 走 SPEC §7.2 typed shape。

**测试**：SPEC §13 page2 条目。

**估时**：150 min（迁移成本含进去）

---

## Phase 7 · Page 3 Strategy Compare 实施

**前置**：P0-P4 + Phase 3 OverlayLineChart 已就位。
**参考**：[[page3-strategy-compare]] + SPEC。

**改动文件**
- `features/compare/StrategyCompareTab.tsx`
- `components/compare/StrategyChip.tsx`
- `components/compare/ComparisonTable.tsx`（含 `compareMetricMeta` driven best-cell）
- `components/compare/JaccardHeatmap.tsx`（**非对角格 violet→cyan 渐变**，仅对角 gold solid）
- `components/compare/SharedHoldingsBars.tsx`（**violet bars**）

**关键修订**
- `getCompare` 调用必须传 `range`，query key 含 range。
- 视觉上 gold 仅在对角格 + legend dot + best-cell tint。
- §9 加 "顶导 `Compare` 激活态 gold underline" 显式行。

**测试**：SPEC §13 page3。

**估时**：120 min

---

## Phase 8 · Page 4 Run History 实施

**前置**：P0-P4。
**参考**：[[page4-run-history]] + SPEC。

**改动文件**
- `features/history/RunHistoryTab.tsx`
- `components/history/Toolbar.tsx`（search + chips + date + view + cog）
- `components/history/RunTable.tsx`（13 列 + 隔行 stripe + selectedId gold 竖条）
- `components/history/useHistoryFilter.ts` — URL search params ↔ `HistoryFilter` typed shape 双向同步。

**关键修订**
- `HistoryFilter.chips: string[]`（**非 Set** — URL serializable）。
- query key = `qk.runs.list(filter)`。
- RE-RUN SELECTED → `onNavigate("backtest", { prefillRunId })`（跨 tab 携带）。

**测试**：SPEC §13 page4。

**估时**：150 min

---

## Phase 9 · Page 5 Universe & Data Health 实施

**前置**：P0-P4。
**参考**：[[page5-universe-health]]（**已修正 alert 计数** Critical） + SPEC。

**改动文件**
- `features/universe/UniverseHealthTab.tsx`
- `components/universe/UniverseTimeline.tsx`（SVG 32 lane × 180 day，BTC lane muted；3-4 violet 虚线 vertical rotation）
- `components/universe/DataSourceTile.tsx`（左 3px 竖条按 status 着色 + 内嵌 Pill 文本，redundant a11y）
- `components/universe/DataAlertRow.tsx`（icon shape + 颜色）
- `features/universe/useRefreshUniverse.ts` — mutation hook（invalidate 三个 query key）

**关键修订**
- DataAlert icon 名：`alert-triangle` / **`info`** / `check-circle`（**非 `InfoCircle`** — lucide 不存在）。
- alerts 数量分布 = **3 rose / 2 cyan / 1 emerald**（共 6 行）。alert 头 badge 显 `6 open`（不是 7）。

**测试**：SPEC §13 page5。

**性能门槛**：32 lane SVG 首次渲染 < 60ms（Performance.now() 测）；超时则降级 Canvas（在 Phase 11 决定是否触发）。

**估时**：180 min（含 SVG 自定义渲染）

---

## Phase 10 · Page 6 Reports & Exports 实施

**前置**：P0-P4。
**参考**：[[page6-reports-exports]]（**已基于真实视觉修订**） + SPEC。

**改动文件**
- `features/reports/ReportsExportsTab.tsx`
- `components/reports/FeaturedDigestCard.tsx`
- `components/reports/ReportCard.tsx`
- `components/reports/ReportThumbnail.tsx`（6 种 thumbnail kind 的 SVG switch）
- `components/reports/SortSelect.tsx`
- 新增 `components/ui/PillButton.tsx`（hero 内 4 个大号 format 按钮专用 — `<Pill>` 不可点）

**关键修订**
- Featured Digest 4 个 format 按钮：MARKDOWN/PDF/PNG report/CSV data 全部 **muted-outline** 基线 + hover/active 时浅 tint（PDF **不再 gold**）。
- DOWNLOAD ALL 才是 gold filled 主 CTA。
- 6 张 archive 卡：5 READY + 1 GENERATING（无 EXPIRED — 视觉里没有）。

**测试**：SPEC §13 page6。

**估时**：120 min

---

## Phase 11 · Cleanup + Cross-Page Acceptance

**目标**：清残 + 全测 + 视觉对照 6 张设计 PNG。

**任务**
1. 删除 SPEC §12 列出的所有旧文件 + 三个空目录（`components/dashboard/` / `components/overview/`（保留新增的小组件）/ `features/dashboard/`）。
2. `pnpm typecheck && pnpm test && pnpm lint`（如有 lint）全绿。
3. 视觉对照：浏览器逐页打开，与 `output/imagegen/atlas20_pageN_*.png` 并排比对（截屏对比 / 简单 hover 视觉一致性）。
4. 跑 [[SPEC §14 验收 5 条公共项]] 全 6 页清单 — 任一项未过 → 该页 §9 不算完工。

**估时**：90 min

---

## 并行委派策略（建议）

完成 P0-P4 后，可由 1 个 Claude 主 agent 分别 spawn：
- **Worker A**：Phase 5 (page1)
- **Worker B**：Phase 6 (page2) — 需独占 `features/dashboard/` 迁移锁
- **Worker C**：Phase 7 (page3)
- **Worker D**：Phase 8 (page4)
- **Worker E**：Phase 9 (page5)
- **Worker F**：Phase 10 (page6)

文件所有权锁：每个 Worker 独占自己 page 的 `features/<area>/**` 与 `components/<area>/**`；都不动 `lib/api.ts`（已锁）、`components/ui/**`（已锁）、`components/charts/**`（已锁）。

Phase 6 因迁移 `features/dashboard/` 影响多文件，**必须在 ParameterSidebar/ChartWorkspace/RunStatusRail 删除前**完成；否则 Worker A 重写 OverviewTab 时引用旧组件会编译失败。**串行约束**：Worker B 必须**先于** Worker A 启动且至少先完成"迁移 hooks"步骤。

Codex 复核回路：每个 Worker 提交后即可启动 codex spec-review，针对该 page 的 plan + SPEC §相应章节，**Critical = 0** 方可进入 Phase 11。

---

## 执行启动检查

- [ ] 用户已确认 SPEC + PLAN（本步）
- [ ] git working tree 干净，开新分支 `redesign/r3-premium`
- [ ] `output/redesign-progress.json` 用作 phase 状态板，每个 phase 完成写 `{phase, status, codex_review_id, timestamp}`
- [ ] 启动顺序：P0 → P1 → P2 + P3（可并行）→ P4 → P5-P10（可并行，但 Worker B page2 需先于 Worker A page1 完成迁移步骤）→ P11

---

## 风险登记

| 风险 | 影响 | 缓解 |
|---|---|---|
| Recharts 在 violet/cyan/gold 混色下 anti-alias 偏色 | page1/page2/page3 主图视觉 | 改用 visx 或纯 SVG path（Phase 3 留出 1h buffer） |
| UniverseTimeline 32×180 = 5760 矩形 SVG 卡顿 | page5 滚动卡帧 | 渲染层分组（每 token 一个 `<g>`），rotation 用 `<use>`；性能 < 60ms 阈值检查 |
| `features/dashboard/` 迁移期间引用断裂 | 全站不可编译 | Phase 6 用 `git mv` + 一次性提交，避免 half-state |
| TanStack `placeholderData` 模式与 mock 函数返回类型不一致 | page 渲染 undefined | Phase 4 必须 `as const` 锁定 fallback 类型，test 覆盖 |
| 真实后端 endpoint 尚未实现 | mutation 提交后报 404 | Phase 6/9 mutation 默认 `if (import.meta.env.DEV) return mockSuccess()`，prod 再切真接口 |
| Recharts ResponsiveContainer 在 jsdom 测试中报 ResizeObserver | CI 测试全挂 | Vitest setup 加 `global.ResizeObserver = class { observe(){} unobserve(){} disconnect(){} }`；或 OverlayLineChart test 用 `canvas.mock` |
| URLSearchParams 手动同步遗漏状态 | page4 filter → URL 写入后刷新丢失 | 抽 `useQueryState` hook 单测覆盖 serialize/parse 往返 |
| 字体 CDN 加载慢导致 FOUT | 首屏字体闪烁 | `font-display: swap` + preload `<link rel="preload" as="font">`；fallback 到 system-ui 不破布局 |
| 并行 Worker 改动同一文件冲突 | merge 时 git conflict | 文件所有权锁严格执行（见并行委派策略），`ResearchConsolePage.tsx` 只在 Phase 1 和 Phase 11 改 |
| CCG hook 干扰 codex review | hook 在 codeagent-wrapper 会话内触发重复操作 | codex review 时传 `--skip-git-repo-check`，且 review 不写文件只读 |
