# Page 1 — Home / Overview 实施计划

视觉来源：`output/imagegen/atlas20_page1_home_overview.png`（已验收）。
落点 feature：`apps/web/src/features/overview/OverviewTab.tsx`（重写）。
前置：[[00-design-system]] 必须先就位。

## 1. 信息架构（自上而下，4 个 section）

```
[Hero 卡 · 全宽 · ~ 156px]
[KPI 三联卡 · 3 列 · ~ 200px]
[Equity Curve + Latest Rebalance · 2 列 (66% / 34%) · ~ 360px]
[Action Strip · 全宽 · ~ 56px]
```

## 2. Hero 卡（Champion）

- 容器：`<Card variant="hero">`，整体 surface + 极淡 gold 边缘 halo（仅在 `border-image` 或外阴影上挂 `var(--gold-glow)`）。
- 左侧：
  - `<Pill tone="gold-outline" size="xs">CURRENT CHAMPION</Pill>`
  - 大标题 `ATLAS Adaptive v3` 28px sans 600
  - 副标题 muted：`Top-3 momentum × volatility filter · 2026-05-18`
- 右侧 4 个 inline KPI（label 上 / value 下两行）：
  - `YTD RETURN` → `+1,247.56%` 32px gold mono
  - `SHARPE` → `3.42` mono
  - `MAX DD` → `-32.04%` rose mono
  - `WIN RATE` → `68.5%` mono
- 数据：`overview.champion`（API `getOverview` 返回，已有 `fallbackOverview`，按需补字段：`ytdReturn`, `sharpe`, `maxDd`, `winRate`）。

## 3. KPI 三联卡

| 卡 | 关键内容 |
|---|---|
| Total AUM Tracked | 大号 `$847.2M` mono 28px + 30d sparkline（gold） + 副 `+8.4% vs prev 30d` emerald mono |
| Active Strategies | 数字 `12` + 一组水平条：Trend Following 5 / Momentum 3 / Mean Rev 2 / Carry 1 / Other 1，每行 `name … bar … count` |
| Market Regime | 大标签 `RISK-ON` gold + 横向 3 段渐变 gauge（rose → muted → emerald）+ 标尺指针 + 副 muted `Risk model · v2.1 · regime score 0.72` |

组件：复用 `ui/KpiTile.tsx`，但 KPI #2 内嵌「label + bar + count」小子组件 `StrategyBarRow`，KPI #3 内嵌 `RegimeGauge`。

数据：扩展 `overview` schema：

```ts
overview.aum = { current: 847_200_000, deltaPct: 0.084, sparkline: number[] }
overview.strategies = { total: 12, breakdown: [{family, count}] }
overview.regime = { label: "RISK-ON", score: 0.72, model: "v2.1" }
```

## 4. Equity Curve · YTD（左 66%）

- 标题 `Equity Curve · YTD` + 右上段控件 `1M | 3M | YTD(active gold) | 1Y | ALL`。
- 主图 OverlayLineChart：
  - line A：`ATLAS Adaptive v3` gold，soft glow（`filter: drop-shadow(0 0 6px var(--gold-glow))`）；
  - line B：`BTC Benchmark` 半透明 violet。
- 注释：在峰值附近钉一个 `+1,247.6%` gold tag 与 `+171.3%` violet tag。
- Tooltip 悬浮态（mock）：`2025-11-14 · ATLAS +847.2% · BTC +124.6%`。
- 底部图例：gold dot `ATLAS Adaptive v3` / violet dot `BTC Benchmark`。
- 数据：`overview.equity.series = [{ts, atlas, btc}]`。

实现：包装 Recharts `ResponsiveContainer + LineChart + Tooltip`；color tokens 走 CSS var；轴线 mono；网格线 `var(--border)`。

## 5. Latest Rebalance（右 34%）

- 卡标题 `Latest Rebalance`，副标题 muted `2026-05-18 weekly · 4 swaps`。
- 内容：4 行 swap row，每行：
  - 左侧两枚 mono ticker：`OUT: TIA` muted / `IN: DOT` text-primary
  - 一个 `→` 箭头 muted
  - 右侧 mono delta：`+4.2%` emerald（或 rose 若负）
- 底部 link：`View full rebalance →` gold 文字按钮。
- 数据：`overview.rebalance.entries = [{out, in, deltaPct}]`。

## 6. Action Strip（页脚）

- 左：3 个按钮，主→副渐次降权
  - `▶ RUN NEW BACKTEST` gold 主按钮 → 切到 `backtest` tab。
  - `COMPARE STRATEGIES` violet outline → 切到 `compare` tab。
  - `GENERATE REPORT` 纯 outline → 切到 `reports` tab。
- 右：mono 文本 `Last sync: 18s ago` + emerald 圆点（活跃）。

实现：复用 `ui/Button.tsx`。tab 切换通过父级 `setTab` prop 注入。

## 7. 现有代码改造点

- `features/overview/OverviewTab.tsx`：从「Hero + Top Strategies Table + Strategy Logic」改写为本计划布局；保留 `props.overview` 和 `props.onOpenDashboard`（后者改为 `onNavigate(tab)`）。
- 旧 `components/overview/HeroSummary.tsx` / `TopStrategiesTable.tsx` / `StrategyLogicSummary.tsx`：废弃或转作内部小组件素材；删除前确认 `OverviewTab.test`（可能没有）。
- `lib/api.ts` 的 `fallbackOverview` 需扩字段（aum/strategies/regime/rebalance/equity）。

## 8. 测试

- `OverviewTab.test.tsx`：渲染含 fallback 数据，断言：
  - `CURRENT CHAMPION` pill 与 ATLAS 标题在 DOM；
  - 4 个 KPI label 都可见；
  - 3 个 KPI 卡标题（AUM / Strategies / Regime）都可见；
  - 点击 `RUN NEW BACKTEST` → 调用 `onNavigate("backtest")`。

## 9. 验收对照

- 字体：全部数字 mono？✓
- 颜色：仅 gold/violet/emerald/rose/cyan 出现？✓ 无暖棕。
- 暗背景 #0A0E14 + 卡 surface #111827？✓
- Hero 边缘有极淡 gold halo？✓
- 与 [[page2-backtest-studio]] 顶导一致 6 标签？✓
