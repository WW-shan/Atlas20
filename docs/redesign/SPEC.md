# Atlas20 Redesign — Master SPEC

整体设计规范（消化三方 cross-review 的 1 Critical / 15 Warning / 9 Info 修正）。
本文件优先级 **高于** 7 份页面计划：凡有冲突，以本 SPEC 为准。
落地范围：`apps/web/src/**`，FastAPI 后端契约由 `lib/api.ts` mock + fallback 先行，后端补齐再切真接口。

---

## 0. 术语与作用域

- **6 页**：`overview` / `backtest` / `compare` / `history` / `universe` / `reports`
- **R3 Crypto-Native Premium** 视觉语言：暗背景 + 6 色 token + Mono 数字 + gold 极度节制
- **现有 `lib/api.ts`**（实测）已有：`OverviewPayload` / `ChampionSummary` / `StrategySummary` / `SeriesPoint` / `SelectionHistoryRow` / `RunStatus` / `fallbackOverview` / `getOverview` / `getOptions` / `runBacktest`。本 SPEC 在其上**扩展**，不删除已有字段。
- **非目标**：移动端原生 / SSR / i18n / 多语言（先做桌面 ≥ 1280px，但保留响应式断点契约）

---

## 1. 颜色 Token（CSS custom properties）

写入 `apps/web/src/styles/index.css` 的 `:root`：

```css
:root {
  --bg:        #0A0E14;
  --surface:   #111827;
  --border:    #1F2937;
  --text:      #E2E8F0;
  --muted:     #94A3B8;
  --gold:      #F59E0B;
  --violet:    #8B5CF6;
  --emerald:   #10B981;
  --rose:      #F43F5E;
  --cyan:      #06B6D4;

  /* Derived */
  --surface-2:  rgb(255 255 255 / 0.02);
  --gold-glow:  rgb(245 158 11 / 0.18);
  --row-stripe: rgb(255 255 255 / 0.015);

  /* Spacing */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;

  /* Layout heights */
  --topnav-h:       56px;
  --pageheader-h:   64px;
  --row-h:          44px;

  /* Radii */
  --radius-card:    8px;
  --radius-pill:    999px;
  --radius-input:   6px;
}
```

### 1.1 Gold 使用白名单（**强制收紧**）

Gold 仅允许出现在以下槽位，**其余一律不得用 gold**。三方 review 抓到的 5 处违规已修订到此清单：

| 槽位 | 示例位置 |
|---|---|
| Champion hero 边缘 halo | page1 hero, page6 featured digest |
| 主要 CTA / 主按钮 fill | `+ NEW RUN`, `RUN BACKTEST`, `+ NEW REPORT`, `DOWNLOAD ALL`, `↻ FORCE REFRESH` |
| Active nav tab 下划线 + 文本 | 顶导 6 标签当前激活态 |
| 主线 chart（仅 1 条） | page1 / page2 / page3 的 ATLAS equity 线（带 soft glow） |
| 收藏星 实心 | page4 RUN 表行的 ★ |
| Best-in-column cell tint | page3 Metric Comparison 每行最佳值 |
| Highlight selected row 左 3px 竖条 | page4 选中行 |
| 列表内 "DOWNLOAD ↓" 文字按钮 | page6 archive 卡 |
| Pagination active page number | page4 `1` |
| Universe timeline active segments (gold band) | page5 UniverseTimeline 每个 token 处于 top-20 的日段填充矩形 |
| Jaccard 对角格 solid（self-similarity = 1.00） | page3 |

**已修订为非 gold** 的位置（由原 page 计划纠正）：
- ❌ ~~page1 AUM tile 30d sparkline~~ → **violet**
- ❌ ~~page2 slider 旋钮~~ → **violet**（与 fill 同色），track 仍 muted
- ❌ ~~page3 Jaccard 非对角格 → gold 渐变~~ → **violet→cyan 渐变**
- ❌ ~~page3 Top shared holdings 横向 bars~~ → **violet bars**
- ❌ ~~page6 Featured Digest 的 `PDF` format pill `tone="gold"`~~ → **violet**（与其余 3 个 format pill 统一 muted-outline，仅 hover 时浅 tint）

---

## 2. 字体 / 数字规范

```css
:root {
  --font-sans: "Inter Display", "Inter", system-ui, sans-serif;
  --font-mono: "JetBrains Mono", ui-monospace, "SF Mono", monospace;
}

.mono {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum";
}
```

字号梯度：`11 / 12 / 13 / 14 / 16 / 18 / 24 / 28`。

强制规则：
- **数字 / ticker / 运行 ID / 时间戳 / % / 文件大小 / 字节数 → mono + tabular-nums**
- 标签 / 状态文本 / 描述 → sans
- 11px uppercase letter-spacing 0.08em 仅用于 `SectionHeader` / KPI label
- `RISK-ON` / `HEALTHY` / `DEGRADED` 这类**枚举状态值** = sans 700 uppercase（不是 mono — review 已订正）

行内时间戳必须 mono（包括 `2026-05-18` 这种日期，page1 hero 副标的日期遵循此规则）。

---

## 3. 布局 / 栅格

- 顶导高 **56px**（`--topnav-h`），sticky top。
- 每页 page-header 高 **64px**（`--pageheader-h`），左标题区 + 右动作区。基线与首个卡顶对齐。
- 外栅 **24px** gutter，卡间距 24px，标题与卡间 12px。
- Card：`background: var(--surface); border: 1px solid var(--border); border-radius: 8px;` 顶部 1px linear-gradient highlight。
- Hero card 高度统一 **180px**（`page1` 与 `page6` 原 156/200 → 收敛到 180）。
- Card variant：`hero` / `default` / `report`。
- BacktestStudio 三栏：`340 / flex / 320`（page2）。
- Row height：表格行 **44px**（`--row-h`）。

### 3.1 响应式断点

| 断点 | 行为 |
|---|---|
| `≥ 1280px` | 默认布局（设计基准） |
| `1024-1279px` | page2 右栏 RunQueue 折叠为浮窗（FAB 触发）；page3 metric+overlap 改纵向堆叠 |
| `< 1024px` | 全部 6 页降级为单列堆叠；顶导 6 tab 改为 horizontal scroll；page4 表格隐藏 `WINDOW / UNIVERSE / CREATED` 三列 |
| `< 640px` | 不在本期目标 — 显示 muted "Open on a larger screen" 占位 |

---

## 4. 加载 / 空 / 错误 / 禁用 状态契约（**新增基线**）

所有 query 驱动组件 **必须** 覆盖以下 4 态。封装为通用 `<QueryBoundary>` Hook + UI 套件：

| 态 | 视觉 | 组件 |
|---|---|---|
| `loading` | 骨架屏 shimmer（surface ↔ surface-2 1.2s sweep）；保留卡外框 | `<Skeleton variant="text\|chart\|table\|card" />` |
| `empty` | 居中 muted 文案 + 可选 violet outline action（如 `+ Add strategy`） | `<EmptyState title sub action />` |
| `error` | 卡内 rose 顶 border + `<AlertTriangle>` + 文案 + `Retry` outline | `<ErrorBanner message onRetry />` |
| `disabled` | 整卡 opacity 0.5 + pointer-events: none + 右上 muted "—" | `aria-disabled="true"` |

```ts
export type SkeletonProps = { variant: "text" | "chart" | "table" | "card"; width?: string; height?: string };
export type EmptyStateProps = { title: string; sub?: string; action?: { label: string; onClick: () => void } };
export type ErrorBannerProps = { message: string; onRetry?: () => void };
```

每页 §9 验收必须明确：本页 **N 个 query 驱动区** 都已实现 loading / empty / error。

---

## 5. 可访问性 a11y 基线（**新增**）

- **色彩对比** 文本 ≥ 4.5:1，非文本数据标记 ≥ 3:1；
- **冗余编码**：仅靠颜色区分状态的位置必须叠加 **形状 / 图标 / 文字** 之一：
  - page4 STATUS 列 → 颜色 + 文本 label（COMPLETED / RUNNING / FAILED）✓
  - page4 RETURN 正负 → 颜色 + 前缀 `+` / `-` 符号
  - page5 Data Source 左竖条 → 颜色 + 内嵌 status pill 文本 ✓
  - page5 Data Alert → 颜色 + icon shape（triangle/circle/check）✓
  - page1 RegimeGauge → 颜色 + 文字 `RISK-ON` label ✓
  - page3 Jaccard heatmap → 每格 mono 数值 + `aria-label="ATLAS × Momentum: 0.62"` ✓
  - page4 selected row → gold 竖条 + `aria-selected="true"`
- **键盘**：所有 chip / tab / button focus 状态 = 1px violet ring + 2px offset；Tab 顺序：page header → primary action → toolbar → main content → secondary。
- **ARIA**：每个 chart `role="img"` + `aria-label` 概述（如 `"ATLAS Adaptive v3 equity curve YTD: +1247.56%"`）；每个 heatmap cell 单独 `aria-label`；`<Pill>` 状态变化广播 `aria-live="polite"`。

---

## 6. 通用组件 API 合约（typed）

### 6.1 Pill

```ts
export type PillTone =
  | "emerald" | "cyan" | "rose" | "violet" | "muted" | "gold"
  | "gold-outline" | "cyan-outline" | "violet-outline";

export type PillProps = {
  tone: PillTone;
  size?: "xs" | "sm" | "md";
  pulse?: boolean;          // 仅 cyan 用，配合 running/generating
  children: React.ReactNode;
};
```

> Review 修订：原 00 列表里 `cyan` 出现两次、缺 outline 变体 — 此处固化为唯一枚举。

### 6.2 KpiTile

```ts
export type KpiTileProps = {
  label: string;            // uppercase muted 11px
  value: string | number;   // mono
  delta?: { value: string; tone: "emerald" | "rose" | "muted" };
  spark?: { points: number[]; tone: "violet" | "cyan" | "emerald" | "rose" };
  inline?: boolean;         // ribbon 内 inline 紧凑变体（page2 KPI ribbon 用）
};
```

`inline` 模式：label 14px sans uppercase + value 16px mono 同行；非 inline = 上下两行。

### 6.3 Card

```ts
export type CardProps = {
  variant?: "default" | "hero" | "report";
  header?: React.ReactNode;
  children: React.ReactNode;
};
```

`hero` 变体高度固定 **180px** + gold halo（`box-shadow: 0 0 24px var(--gold-glow)`）。
`report` 变体（page6）= default + 内置 thumbnail 顶部插槽。

### 6.4 Button

```ts
export type ButtonProps = {
  variant: "gold" | "outline-gold" | "outline-violet" | "outline-muted" | "outline-dashed" | "ghost";
  size?: "sm" | "md" | "lg";
  loading?: boolean;        // 旋转 icon 替换 leading slot
  disabled?: boolean;
  children: React.ReactNode;
};
```

`outline-dashed` 用于 page3 "+ Add strategy" 按钮。

### 6.5 StatusDot / Sparkline / SectionHeader / Pager

```ts
export type StatusDotProps = { tone: PillTone; pulse?: boolean };

export type SparklineProps = {
  points: number[];
  tone: "violet" | "cyan" | "emerald" | "rose" | "gold" | "muted-dashed";
  height?: number;          // default 24
};

export type SectionHeaderProps = {
  children: string;         // uppercase auto-applied
  rightSlot?: React.ReactNode;
};

export type PagerProps = {
  total: number;
  page: number;
  pageSize: number;
  onChange: (page: number) => void;
};
```

### 6.6 PillButton（page6 Featured Digest 专用）

```ts
export type PillButtonProps = {
  tone: PillTone;
  size?: "sm" | "md";
  active?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
};
```

大号可点胶囊（`<Pill>` 不可点、`<Button>` 太 button-y；此组件桥接两者）。

### 6.7 OverlayLineChart

**单一定义**位于 `components/charts/OverlayLineChart.tsx`（page1 拥有，page2/page3 复用 — review 已订正归属链）。

```ts
export type ChartRange = "1M" | "3M" | "YTD" | "1Y" | "ALL";

export type OverlayLine = {
  id: string;
  label: string;
  tone: "gold" | "violet" | "cyan" | "emerald" | "rose" | "muted";
  glow?: boolean;            // 仅 gold 主线开启
  dashed?: boolean;
};

export type OverlayLineChartProps = {
  series: { ts: string; values: Record<string /* line id */, number> }[];
  lines: OverlayLine[];
  range: ChartRange;
  yFormat?: "percent" | "absolute" | "compact";
  annotations?: { ts: string; label: string; tone?: "gold" | "violet" }[];
};
```

`ChartRange` 为共享 union，API 签名引用此类型（非反向依赖组件 props）。

---

## 7. 数据 Types（全部 typed，扩展现有 `lib/api.ts`）

### 7.1 保留并扩展现有 schema

```ts
// 已存在，扩展字段
export type OverviewPayload = {
  // ↓ 已有
  champion: ChampionSummary;
  top_strategies: StrategySummary[];
  equity_curve: SeriesPoint[];
  daily_returns: SeriesPoint[];
  selection_history: SelectionHistoryRow[];

  // ↓ 新增（page1 redesign 需要）
  aum: { current: number; deltaPct: number; sparkline: number[] };
  strategies: { total: number; breakdown: { family: string; count: number }[] };
  regime: { label: "RISK-ON" | "NEUTRAL" | "RISK-OFF"; score: number; model: string };
  rebalance: {
    ts: string;
    swaps: { out: string; in: string; deltaPct: number }[];
  };
  equity_overlay: {
    series: { ts: string; atlas: number; btc: number }[];
    range: "YTD";
  };
  hero_kpi: { ytdReturn: number; sharpe: number; maxDd: number; winRate: number };
};
```

### 7.2 新增 types

```ts
// ===== Runs（page2 + page4 共用底层 type, review 强制） =====
export type RunStatusEnum = "queued" | "running" | "completed" | "failed";

export type RunRow = {
  run_id: string;             // 短格式 "btk_0142"（review 修订：page2 不再用长格式）
  strategy: string;
  strategy_family?: "ATLAS" | "Momentum" | "MeanRev" | "Carry" | "Other";
  universe: string;           // e.g. "Top-20"
  window: { start: string; end: string };  // ISO date
  status: RunStatusEnum;
  return_pct?: number;
  sharpe?: number;
  max_dd?: number;
  duration_s?: number;
  eta_s?: number;             // running 时填，否则 undefined
  spark?: number[];
  created_at: string;         // ISO
  favorited?: boolean;
};

export type RunRowSummary = Pick<RunRow,
  "run_id" | "strategy" | "status" | "duration_s" | "eta_s"
> & { params_summary: string };  // page2 RunQueue 卡片用紧凑变体

export type RunDetailPayload = RunRow & {
  equity_overlay: { series: { ts: string; atlas: number; btc: number }[] };
  kpi: {
    cagr: number; sharpe: number; sortino: number;
    max_dd: number; calmar: number; win_rate: number;
  };
};

// ===== Backtest config（page2，review 强制） =====
export type BacktestConfig = {
  preset: string;                          // "ATLAS Adaptive v3"
  universe: { topN: number; excludeStable: boolean; excludeWrapped: boolean };
  window: { start: string; end: string; rebalance: "Weekly" | "Biweekly" | "Monthly" };
  allocation: { positionPct: number; slots: number };
  costs: { feeBps: number; slippageBps: number };
};
export const defaultBacktestConfig: BacktestConfig = {
  preset: "ATLAS Adaptive v3",
  universe: { topN: 20, excludeStable: true, excludeWrapped: true },
  window: {
    start: new Date(new Date().setFullYear(new Date().getFullYear() - 2)).toISOString().slice(0, 10),
    end: new Date().toISOString().slice(0, 10),
    rebalance: "Weekly",
  },
  allocation: { positionPct: 5.0, slots: 10 },
  costs: { feeBps: 10, slippageBps: 5 },
};

// ===== History filter（page4，review 强制可序列化） =====
export type HistoryFilter = {
  q: string;
  chips: string[];           // 不再用 Set — URL serializable
  dateRange: "7d" | "30d" | "90d" | "ytd" | "all";
  view: "list" | "grid";
  page: number;
  pageSize: number;          // default 14
};
export const defaultHistoryFilter: HistoryFilter = {
  q: "", chips: [], dateRange: "30d", view: "list", page: 1, pageSize: 14,
};

// ===== Compare（page3，review 强制 range） =====
export type CompareMetricKey =
  | "cagr" | "sharpe" | "sortino" | "max_dd" | "calmar"
  | "win_rate" | "avg_turnover" | "trades_per_year";

export const compareMetricMeta: Record<CompareMetricKey, {
  label: string;
  direction: "higher-is-better" | "lower-is-better";
  format: "percent" | "ratio" | "count";
}> = {
  cagr:            { label: "CAGR",         direction: "higher-is-better", format: "percent" },
  sharpe:          { label: "Sharpe",       direction: "higher-is-better", format: "ratio" },
  sortino:         { label: "Sortino",      direction: "higher-is-better", format: "ratio" },
  max_dd:          { label: "Max DD",       direction: "lower-is-better",  format: "percent" },
  calmar:          { label: "Calmar",       direction: "higher-is-better", format: "ratio" },
  win_rate:        { label: "Win Rate",     direction: "higher-is-better", format: "percent" },
  avg_turnover:    { label: "Avg Turnover", direction: "lower-is-better",  format: "percent" },
  trades_per_year: { label: "Trades / yr",  direction: "lower-is-better",  format: "count" },
};

export type CompareSelectionItem = {
  id: string;
  label: string;
  tone: "gold" | "violet" | "cyan" | "emerald";
};

export type ComparePayload = {
  equity: { ts: string; values: Record<string /* selection id */, number> }[];
  metrics: Record<CompareMetricKey, Record<string /* id */, number>>;
  overlap: {
    symbols: string[];
    matrix: number[][];               // square; diagonal = 1.00
    sharedHoldings: { symbol: string; count: number; total: number }[];
  };
};

// ===== Universe（page5） =====
export type UniverseTimelinePayload = {
  tokens: string[];                   // 32 mono tickers, BTC included
  segments: { token: string; start: string; end: string }[];
  rotations: { ts: string; label: string }[];
  range: { start: string; end: string };
};

export type DataSourceStatus = "healthy" | "degraded" | "error";
export type DataSource = {
  id: string;
  name: string;                       // e.g. "CoinGecko · Markets"
  status: DataSourceStatus;
  last_sync_seconds: number;
};

export type DataAlertSeverity = "rose" | "cyan" | "emerald";
export type DataAlert = {
  id: string;
  severity: DataAlertSeverity;
  title: string;
  meta: string;                       // 时间 / 间隙 / 来源 / 处置
  ts: string;
  icon: "alert-triangle" | "info" | "check-circle";  // 注意：不是 InfoCircle
};

// ===== Reports（page6） =====
export type ReportFormat = "markdown" | "pdf" | "png" | "csv";
export type ReportStatus = "ready" | "generating";
export type ReportThumbKind =
  | "equity" | "lines" | "heatmap" | "bars" | "horizontal-bars" | "sparkbar";
export type ReportSortKey = "recent" | "oldest" | "size" | "type";

export type FeaturedDigest = {
  id: string;
  title: string;                      // "Atlas20 — Week 20 / 2026"
  subtitle: string;                   // mono
  formats: ReportFormat[];            // 默认全部 4 种
  defaultFormat: ReportFormat;        // 默认选中（不应是 "pdf gold tinted"）
  generated_at: string;
};

export type ReportEntry = {
  id: string;
  title: string;
  subtitle: string;                   // derived display text
  thumbnail: ReportThumbKind;
  status: ReportStatus;
  highlight?: boolean;
  // ↓ structured fields for sorting (codex review)
  generated_at: string;
  size_bytes: number;
  report_type: "weekly" | "run" | "compare" | "universe";
};
```

---

## 8. `lib/api.ts` 函数 / 常量 注册表

| 函数 | 签名 | 用于 |
|---|---|---|
| `getOverview()` | `Promise<OverviewPayload>` | page1（已存在，扩展返回字段） |
| `getOptions()` | `Promise<Record<string, unknown>>` | page2 表单选项（已存在） |
| `runBacktest(payload: BacktestConfig)` | `Promise<RunRowSummary>` | page2 mutation（review：typed param + 返回 queue-compatible summary） |
| `listRunsQueue()` | `Promise<RunRowSummary[]>` | page2 右栏 |
| `listRuns(filter: HistoryFilter)` | `Promise<{ items: RunRow[]; total: number; page: number; pageSize: number }>` | page4 |
| `getRun(id: string)` | `Promise<RunRow>` | page2 selectedRunId 等用 |
| `getRunDetail(id: string)` | `Promise<RunDetailPayload>` | page2 EquityWorkspace 中栏图表+KPI ribbon |
| `toggleFavorite(id: string)` | `Promise<{ run_id: string; favorited: boolean }>` | page4 ★ |
| `getCompare(ids: string[], range: ChartRange)` | `Promise<ComparePayload>` | page3（review 加 range） |
| `getUniverseTimeline()` | `Promise<UniverseTimelinePayload>` | page5 |
| `getDataSources()` | `Promise<DataSource[]>` | page5 |
| `getDataAlerts()` | `Promise<DataAlert[]>` | page5 |
| `refreshUniverse()` | `Promise<{ refreshed_at: string }>` | page5 FORCE REFRESH mutation |
| `getFeaturedDigest()` | `Promise<FeaturedDigest>` | page6 |
| `listReports(sort: ReportSortKey)` | `Promise<ReportEntry[]>` | page6 |
| `downloadDigest(fmt: ReportFormat \| "bundle")` | `Promise<{ url: string }>` | page6 DOWNLOAD ALL |
| `downloadReport(id: string, fmt?: ReportFormat)` | `Promise<{ url: string }>` | page6 卡内 |

**Fallback 常量统一命名**（review 强制）：
`fallbackOverview`（已存在）/ `fallbackRunsQueue` / `fallbackRunsList` / `fallbackRunDetail` / `fallbackCompare` / `fallbackUniverseTimeline` / `fallbackDataSources` / `fallbackDataAlerts` / `fallbackFeaturedDigest` / `fallbackReports`。所有 fallback 通过 TanStack `placeholderData` 注入，**不**作为 hard mock 替换 fetch。

---

## 9. TanStack Query Key 注册表（**避免冲突**）

```ts
export const qk = {
  overview:          () => ["overview"] as const,
  options:           () => ["options"] as const,

  runs: {
    queue:           () => ["runs", "queue"] as const,
    list:            (f: HistoryFilter) => ["runs", "list", canonicalizeFilter(f)] as const,
    detail:          (id: string) => ["runs", "detail", id] as const,
  },

  compare:           (ids: string[], range: ChartRange) =>
                       ["compare", [...ids].sort(), range] as const,

  universe: {
    timeline:        () => ["universe", "timeline"] as const,
    sources:         () => ["universe", "sources"] as const,
    alerts:          () => ["universe", "alerts"] as const,
  },

  reports: {
    featured:        () => ["reports", "featured"] as const,
    archive:         (sort: ReportSortKey) => ["reports", "archive", sort] as const,
  },
};
```

页面调用必须走 `qk.*`，禁止散写字符串数组（review 防回潜规则）。

```ts
// canonicalizeFilter — 排序 chips + 固定字段顺序，保证 key 稳定
function canonicalizeFilter(f: HistoryFilter): Omit<HistoryFilter, never> {
  return { ...f, chips: [...f.chips].sort() };
}
```

---

## 10. 路由 / Tab 状态

- 6 tab union `ConsoleTab`（[[00-design-system]] §4 已定，保留）。
- `ResearchConsolePage` 改造：用 `useReducer` 维护 `{ tab, prefillRunId? }`，`prefillRunId` 用于 page4 → page2 "RE-RUN" 跨 tab 携带参数。
- page1 Action Strip 三按钮分别 `onNavigate("backtest" | "compare" | "reports")`。
- page2 右栏 `View all →` `onNavigate("history")`。
- page4 选中 RE-RUN SELECTED → `setTab("backtest", { prefillRunId: selected.run_id })`。
- URL search params 同步（首期可选，最低先做 `?tab=history`）：
  - `?tab=<key>` — 6 选 1
  - `?q=` / `?range=` / `?page=` — page4 toolbar 状态
  - `?ids=ATLAS,Momentum&range=YTD` — page3 比较
  - `?sort=` — page6 archive 排序

---

## 11. 文件 / 目录 名约定（**review 修订**）

| feature 文件 | 路径 | 备注 |
|---|---|---|
| OverviewTab | `features/overview/OverviewTab.tsx` | 重写 |
| BacktestStudioTab | `features/backtest/BacktestStudioTab.tsx` | dashboard 拆出来 |
| StrategyCompareTab | `features/compare/StrategyCompareTab.tsx` | 新建 |
| RunHistoryTab | `features/history/RunHistoryTab.tsx` | 新建 |
| UniverseHealthTab | `features/universe/UniverseHealthTab.tsx` | 新建 |
| **ReportsExportsTab** | `features/reports/ReportsExportsTab.tsx` | review 决议：保留长名 |

`ResearchConsolePage` 的 import 与 [[00-design-system]] §5 的占位名 `ReportsTab.tsx` 冲突 — 以本表为准，**00 中那条作废**。

`components/ui/` 与 `components/charts/` 共享；`components/dashboard/` 在迁移完成后**整目录删除**（review #25）。

---

## 12. 现有组件迁移 / 弃用清单

| 原文件 | 处置 |
|---|---|
| `components/dashboard/ParameterSidebar.tsx` | 重写并迁至 `components/backtest/ParameterSidebar.tsx` |
| `components/dashboard/ChartWorkspace.tsx` | 重写并迁至 `components/backtest/EquityWorkspace.tsx` |
| `components/dashboard/RunStatusRail.tsx` | 重写并迁至 `components/backtest/RunQueue.tsx` |
| `components/dashboard/SelectionHistoryTable.tsx` | 拆解：表骨架借给 `components/history/RunTable.tsx`，原文件**删除** |
| `components/overview/HeroSummary.tsx` | 删除（被新 `OverviewTab` 内联） |
| `components/overview/TopStrategiesTable.tsx` | 删除 |
| `components/overview/StrategyLogicSummary.tsx` | 删除 |
| `features/dashboard/DashboardTab.tsx` | 删除（拆到 features/backtest/） |
| `features/dashboard/useChampionPreset.ts` | 迁至 `features/backtest/useChampionPreset.ts` |
| `features/dashboard/useRunBacktest.ts` | 迁至 `features/backtest/useRunBacktest.ts` |

完成后空目录 `components/dashboard/` / `components/overview/` / `features/dashboard/` **删除**。

---

## 13. 测试覆盖最小集（**review 补强**）

每个 *Tab.test.tsx **必须**覆盖：
- 默认 fallback 渲染断言（标题 + 主要 section + 至少 1 个 mono 数字）
- 至少 1 个 mutation / navigate 行为断言
- loading skeleton 在 query pending 时可见（mock `placeholderData: undefined`）
- error 态可见（mock fetch reject）
- empty 态可见（mock 空数组）
- a11y：所有交互元素有 accessible name（用 `getByRole`，禁止 `getByText` 兜底 button）

按页面：
- **page1**：equity overlay 2 条线渲染 + rebalance 4 行 swap + Action Strip 3 按钮 navigate
- **page2**：5 SectionHeader + 6 KPI label + RUN BACKTEST mutation + Queue RUNNING 脉冲 dot
- **page3**：3 chip + ComparisonTable best-cell `data-best="true"` + 3 非对角 heatmap mono 数 + SharedHoldingsBars 5 行 + range 切换更新 query key
- **page4**：14 行 + 13 列 + ★ toggle + chip 过滤 + search 输入 + 日期切换 + 翻页 + RE-RUN SELECTED → navigate "backtest" with prefillRunId
- **page5**：32 lane SVG（含 BTC muted）+ 3+ rotation vertical + 9 source tile（6/2/1 分布）+ 6 alert（3 rose / 2 cyan / 1 emerald）+ FORCE REFRESH mutation
- **page6**：featured + 4 format button + DOWNLOAD ALL bundle + 6 archive（5 READY / 1 GENERATING）+ highlight `data-highlight="true"` + sort 切换 query key + + NEW REPORT 点击 stub

---

## 14. 验收对照（每页 §9 必须含此 5 条公共项）

1. 顶导 `<TabName>` 激活态 = gold 文本 + 2px gold 下划线 + glow ✓
2. 全部数字 / ticker / ID / 时间戳 mono tabular ✓
3. Gold 仅出现在 §1.1 白名单槽位 ✓
4. 所有 query 驱动区覆盖 loading / empty / error 三态 ✓
5. 色彩+冗余编码（icon/形状/文本）一致 ✓

---

## 15. 不在本期范围

- 实时 WebSocket 推送（page2 queue / page5 alerts 暂用 polling 30s）
- 多用户协同 / share link 后端
- Dark/Light mode toggle（暗模式唯一）
- 导出报告的真实生成（page6 download 走 mock URL）
- Mobile < 640px UI

---

## 16. Open Questions（实施前最后确认）

- [ ] page2 RunQueue 数据源：`listRunsQueue()` 是否直接复用 `listRuns({status: queued|running|recent_completed})` 而不另开接口？SPEC 倾向**另开**（语义更清，缓存独立）。
- [ ] page6 `+ NEW REPORT` 弹窗规格未定义 — 本期先做按钮 + console.log stub？
- [ ] page5 `<UniverseTimeline>` 32 lane × 180 day SVG 渲染性能：浏览器实测 < 60ms 否则降级 Canvas。
- [ ] 是否引入 `react-router-dom` 取代 state-based router？SPEC 倾向**先不引**（最小改动，搜索参数用 `URLSearchParams` 手动同步即可）。
