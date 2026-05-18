# Page 3 — Strategy Compare 实施计划

视觉来源：`output/imagegen/atlas20_page3_strategy_compare.png`（已验收）。
落点 feature：`apps/web/src/features/compare/StrategyCompareTab.tsx`（新建）。
前置：[[00-design-system]]，复用 [[page2-backtest-studio]] 的 `OverlayLineChart`。

## 1. 信息架构

```
[Page Header · 64px]   左：标题+副标   右：3 个 strategy chips + + Add strategy
[Equity Overlay · 全宽 · ~ 360px]
[Metric Comparison 60% · Holdings Overlap 40% · 并排 · ~ 440px]
```

## 2. Page Header

- 左：`Strategy Compare` / 副 muted `Side-by-side performance, risk, and holdings overlap`。
- 右：横向 chip cluster（多选态）
  - `<Chip color="gold">ATLAS Adaptive v3</Chip>`（gold 圆点 + gold 边）
  - `<Chip color="violet">Momentum Top-10</Chip>`
  - `<Chip color="cyan">Mean Reversion v2</Chip>`
  - `<Button variant="outline-dashed">+ Add strategy</Button>` → 打开选择器（先做按钮，弹窗后续）。

数据：`compareSelection` 状态本地维护（最多 4 条曲线，颜色按 `gold / violet / cyan / emerald` 顺序分配）。

## 3. Equity Curves · YTD 卡

- 头：标题 + segmented control `1M | 3M | YTD(active gold) | 1Y | ALL`。
- legend 行：`● ATLAS Adaptive v3 +1,247%` / `● Momentum Top-10 +682%` / `● Mean Reversion v2 +214%`。
- 图：OverlayLineChart 多线（最多 N=4），波动率不同；gold 线带 soft glow，其他无。
- Y 轴 mono % 右对齐，X 轴 mono 月份 Jan-May 2026。

## 4. Metric Comparison（左 60%）

- 头：`Metric Comparison` + 右上 legend `● Best in column`（gold dot）。
- 表（8 行 4-5 列）：

| METRIC | ATLAS v3 | Momentum Top-10 | Mean Reversion v2 | DIFF vs ATLAS |
|---|---|---|---|---|
| CAGR | **158.4%** | 92.1% | 41.6% | — |
| Sharpe | **3.42** | 2.81 | 1.94 | — |
| Sortino | **5.18** | 4.02 | 2.71 | — |
| Max DD | -32.04% (rose) | -28.7% | **-18.4%** | better in MR |
| Calmar | **4.95** | 3.21 | 2.26 | — |
| Win Rate | **68.5%** | 61.2% | 54.8% | — |
| Avg Turnover | 18.2% | 24.6% | **8.3%** | better in MR |
| Trades / yr | 248 | 312 | **96** | — |

实现：`<ComparisonTable>` 组件，逻辑「每行选 best（按 metric 定义的方向）→ 该 cell 加 gold 背景 tint + gold 左侧点」。封装 `metricDirection: 'higher-is-better' | 'lower-is-better'`。

## 5. Holdings Overlap（右 40%）

- 头：`Holdings Overlap` + 副 muted `Pairwise Jaccard similarity over rolling 30d windows`。
- 3×3 对称矩阵热图：
  - 对角线 solid gold cell（`1.00` 暗色 mono 文字 in gold bg）；
  - 非对角线 `var(--border) → var(--gold)` 渐变（按 similarity 插值）；
  - 数值 mono：ATLAS×Momentum 0.62 / ATLAS×MeanRev 0.18 / Momentum×MeanRev 0.31。
- 行/列 label mono：`ATLAS v3 / Momentum / MeanRev`。
- 下方 bar 列表 `Top shared holdings`：5 行 `SOL / TIA / SUI / INJ / SEI`，水平 gold bar，右侧 mono `3/3 / 2/3 / 2/3 / 2/3 / 1/3`。

组件：`<JaccardHeatmap symbols values />` + `<SharedHoldingsBars items />`。

## 6. 数据接入

- `lib/api.ts` 新增：
  ```ts
  getCompare(strategyIds: string[]): Promise<{
    equity: { ts; values: Record<id, number> }[];
    metrics: Record<metric, Record<id, number>>;
    overlap: { matrix: number[][]; sharedHoldings: { symbol; count }[] };
  }>;
  ```
- TanStack Query key：`["compare", sortedIds.join(",")]`。
- fallback：mock 数据按当前截图数值写死。

## 7. 现有代码改造点

- `ResearchConsolePage` 添加 `tab === "compare"` 分支。
- 复用 [[page2-backtest-studio]] 中 `OverlayLineChart`。
- 新增组件 `components/compare/ComparisonTable.tsx` / `JaccardHeatmap.tsx` / `SharedHoldingsBars.tsx` / `StrategyChip.tsx`。

## 8. 测试

- `StrategyCompareTab.test.tsx`：
  - 默认渲染 3 chips；
  - ComparisonTable 中 CAGR 行 ATLAS 单元格带 `data-best="true"`；
  - Heatmap 3 个非对角 cell 渲染 mono 数值；
  - 点 segmented 1M → query key 包含 `range=1M`。

## 9. 验收对照

- chip 边色三种对应 gold/violet/cyan ✓
- best 列高亮仅在该列最佳值 ✓
- heatmap 对角 gold solid ✓
- 全数字 mono ✓
