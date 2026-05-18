# Page 2 — Backtest Studio 实施计划

视觉来源：`output/imagegen/atlas20_page2_backtest_studio.png`（已验收）。
落点 feature：`apps/web/src/features/backtest/BacktestStudioTab.tsx`（新建，吸收旧 `features/dashboard/DashboardTab.tsx` 的运行能力）。
前置：[[00-design-system]]。

## 1. 信息架构

```
[Page Header · 全宽 · 64px]   左：标题+副标   右：RUN ID pill + + NEW RUN gold 按钮
[三栏工作台 · 占满剩余 880px]
  ├─ Parameters 列 · 340px 固定
  ├─ Equity Workspace 列 · flex auto
  └─ Run Queue 列 · 320px 固定
```

## 2. 左栏 — Parameters（`components/backtest/ParameterSidebar.tsx`）

> 现有 `components/dashboard/ParameterSidebar.tsx` 可继承命名空间，重写内容。

字段分组（每组以 `<SectionHeader>STRATEGY</SectionHeader>` 起头，uppercase 11px muted mono）：

| 分组 | 控件 |
|---|---|
| STRATEGY | `<Select>` Preset = `ATLAS Adaptive v3`（focus 态 violet 1px ring） |
| UNIVERSE | `<Slider>` Top-N，track muted、fill violet、knob gold，右侧 mono `N = 20`；`<Toggle>` Exclude stablecoins (on)；`<Toggle>` Exclude wrapped tokens (on) |
| WINDOW | 两个 `<DateInput>` Start/End；`<Select>` Rebalance = `Weekly (Mon 00:00 UTC)` |
| ALLOCATION | `<Slider>` Position size `5.0% per slot`；`<NumberInput>` Slots = 10 |
| COSTS | 两个 `<NumberInput>` 并排：Fee bps 10 / Slippage bps 5 |

底部：`▶ RUN BACKTEST` gold 主按钮（全宽，gold-glow halo）。

数据/状态：本地 `useReducer` 维护 `BacktestConfig`；提交时调用 `useRunBacktest` mutation（已存在 `features/dashboard/useRunBacktest.ts`，迁移到 `features/backtest/`）。

## 3. 中栏 — Equity Workspace

- Tab strip：`Equity (active gold underline) · Drawdown · Returns · Turnover · Trades`。
- 主图：OverlayLineChart：
  - 主 line：ATLAS（gold + soft glow），Y 轴 mono `0% / +200% / +400% / +800% / +1200%`；
  - 副 line：BTC Benchmark（半透明 violet）；
  - X 轴 mono `Jan 2024 - May 2026`；
  - 悬浮 crosshair tooltip：`2025-11-14 · ATLAS +847.2% · BTC +124.6%`（mock 默认显示）。
- 图下 KPI Ribbon（6 个 inline）：`CAGR 158.4% / SHARPE 3.42 / SORTINO 5.18 / MAX DD -32.04% / CALMAR 4.95 / WIN RATE 68.5%`；label uppercase muted 10px，value 16px mono；正值 emerald 微染、负值 rose。

组件：复用 [[page1-home-overview]] 的 `OverlayLineChart`；KPI ribbon 是 `KpiTile` 的紧凑 inline 变体（`<KpiTile inline />`）。

## 4. 右栏 — Run Queue

- 头：`Run Queue` + cyan `4 active` count badge。
- 列表 6 张 run card（与现有 `RunStatusRail.tsx` 形似，但更紧凑）。每卡：
  - 行1：`<Pill>` 状态（cyan RUNNING + 脉冲 / emerald COMPLETED / rose FAILED / muted QUEUED）+ mono `btk_0142`
  - 行2：策略名 `ATLAS Adaptive v3`（white）+ 参数摘要 muted `N=20 · Weekly · 2024→2026`
  - 行3：progress bar（running gold fill / done emerald full / failed rose）+ mono 右对齐 `0:42 / ~1:30`
- 顺序：RUNNING ×2 → COMPLETED ×2 → FAILED ×1 → QUEUED ×1。
- 底部：muted `Showing 6 of 24` + gold link `View all →`（点击切到 `history` tab）。

## 5. 数据接入

- `features/backtest/useRunQueue.ts`：TanStack Query 拉 `GET /api/runs?state=active|recent` 列表（后端接口若没有，先在 `lib/api.ts` 加 mock + fallback）。
- `useRunBacktest.ts`：维持 mutation，submit 后乐观地往 queue 顶部插 `QUEUED` 卡。
- Equity 图数据从最近 COMPLETED 跑的 `runId` 拉取（默认 `btk_0142`）；提供 `selectedRunId` 状态。

## 6. 页面头

- 标题 `Backtest Studio`，副标 muted `Configure, run, and inspect strategy backtests`。
- 右侧：`<Pill tone="cyan">RUN ID: btk_2026-05-18_0142</Pill>` + `<ButtonGold>+ NEW RUN</ButtonGold>`（点击 = 重置 Parameters 表单）。

## 7. 现有代码改造点

- 删除 `features/dashboard/DashboardTab.tsx`（拆解到 `features/backtest/`）。
- 旧 `components/dashboard/*` 拆分：
  - `ParameterSidebar.tsx` → `components/backtest/ParameterSidebar.tsx`（重写）；
  - `ChartWorkspace.tsx` → `components/backtest/EquityWorkspace.tsx`（重写）；
  - `RunStatusRail.tsx` → `components/backtest/RunQueue.tsx`（视觉重做）；
  - `SelectionHistoryTable.tsx` → 移到 [[page4-run-history]] 的素材池或废弃。
- `ResearchConsolePage.tsx` `tab === "backtest"` 渲染 `<BacktestStudioTab>`。

## 8. 测试

- 沿用 `useChampionPreset.test.ts` 思路给 `useRunBacktest`、`useRunQueue` 单测。
- `BacktestStudioTab.test.tsx`：
  - 渲染默认 fallback，看到 5 个 section header + 6 个 KPI label；
  - 点 RUN BACKTEST → mutation 调用一次；
  - Queue 中 mock 一个 RUNNING，断言脉冲 dot 在 DOM。

## 9. 验收对照

- 顶导 `Backtest` 激活态 gold underline ✓
- gold 仅出现在 RUN 按钮、KPI 正向值、+NEW RUN、激活态 ✓
- 三栏严格 340 / flex / 320 ✓
- 数字全部 mono tabular ✓
