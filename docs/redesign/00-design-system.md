# Atlas20 Redesign — 00 Design System Baseline

定位：R3 Crypto-Native Premium。这一份是 6 个页面共享的视觉与结构地基，必须最先落地，否则后续每一页都会重复改全局样式。

## 1. 颜色 Token（写进 `apps/web/src/styles/index.css` 的 `:root`）

```
--bg:        #0A0E14   /* page background */
--surface:   #111827   /* card / panel surface */
--border:    #1F2937   /* hairline divider, chart grid, table border */
--text:      #E2E8F0   /* primary text */
--muted:     #94A3B8   /* label / secondary text */
--gold:      #F59E0B   /* champion / primary CTA / active nav / 主要曲线 */
--violet:    #8B5CF6   /* 次级曲线 / secondary CTA / filter active */
--emerald:   #10B981   /* 正向 delta / completed / healthy */
--rose:      #F43F5E   /* 负向 delta / failed / error */
--cyan:      #06B6D4   /* info / running 脉冲 / running spark */
```

派生：
- `--surface-2: rgb(255 255 255 / 0.02)` 叠加在 surface 上做 card 顶亮的 gradient。
- `--gold-glow: rgb(245 158 11 / 0.18)` 仅用于 hero 卡边缘与 RUN/+NEW 按钮 halo。
- `--row-stripe: rgb(255 255 255 / 0.015)` 表格隔行底色。

## 2. 字体

```
--font-sans: "Inter Display", "Inter", system-ui, sans-serif;
--font-mono: "JetBrains Mono", ui-monospace, "SF Mono", monospace;
```

规则：
- body / 标题用 sans；
- 所有数字、ticker、ID、时间戳、% 走 `font-variant-numeric: tabular-nums; font-family: var(--font-mono);`。封装成 `.mono` 工具类。

字号梯度：12 / 13 / 14 / 16 / 18 / 24 / 28（page hero）。muted label 用 11px uppercase letter-spacing 0.08em。

## 3. 卡片与栅格

- card：`background: var(--surface); border: 1px solid var(--border); border-radius: 8px;` 顶部叠 1px linear-gradient highlight。
- 外栅 24px gutter，卡间距 24px，标题与卡间 12px。
- shadow 默认无；只有 hero 与主要 CTA 用 gold-glow 外发光。

## 4. AppShell + 顶导（重构 `components/layout/AppShell.tsx` + `components/navigation/TabSwitcher.tsx`）

现状：只有 `overview | dashboard` 两个 tab。重构后：

```ts
export type ConsoleTab =
  | "overview"
  | "backtest"
  | "compare"
  | "history"
  | "universe"
  | "reports";
```

- 顶导高度 56px，左侧 `ATLAS20` wordmark（sans 700）+ `Research Console` muted tag；中间 6 个 tab；右侧 search input（图标 +「Search strategies, metrics, runs…」placeholder）+ cog + avatar。
- 激活态：gold 文本 + 底部 2px gold 下划线 + 轻微 gold 外发光（`text-shadow` 或下划线 box-shadow）。

## 5. 路由

`apps/web/src/pages/ResearchConsolePage.tsx` 当前是「`useState<tab>` 二选一」。重构为：

- 引入 `react-router-dom`（已经在 deps 里？需 grep；若无，先用 state-based router 等价物，新增 6 个 *Tab feature 文件）。
- 推荐：保留状态化 router（最小改动），把 6 个 tab 各自作为一个 feature 子目录：
  - `features/overview/OverviewTab.tsx`（已存在，重写内容）
  - `features/backtest/BacktestStudioTab.tsx`（dashboard 拆出来 + 重组）
  - `features/compare/StrategyCompareTab.tsx`（新）
  - `features/history/RunHistoryTab.tsx`（新）
  - `features/universe/UniverseHealthTab.tsx`（新）
  - `features/reports/ReportsTab.tsx`（新）

## 6. 通用组件（先打底，后被 6 页消费）

| 组件 | 路径 | 用途 |
|---|---|---|
| `Pill` | `components/ui/Pill.tsx` | 状态/格式胶囊（emerald/cyan/rose/violet/cyan/muted 变体） |
| `StatusDot` | `components/ui/StatusDot.tsx` | 带可选脉冲 |
| `KpiTile` | `components/ui/KpiTile.tsx` | label uppercase muted + 大号 mono 数字 + 可选 delta |
| `SectionHeader` | `components/ui/SectionHeader.tsx` | uppercase muted 11px + 右侧 slot |
| `Card` | `components/ui/Card.tsx` | 含 `<header>` `<body>` 槽位 |
| `ButtonGold` `ButtonOutline` | `components/ui/Button.tsx` | gold 主按钮 + outline（violet/gold 两个变体） |
| `Sparkline` | 已有 `components/charts/SparklineChart.tsx`，扩展支持 4 色变体 |
| `OverlayLineChart` | `components/charts/OverlayLineChart.tsx` | 多线叠加（Page 1/2/3 共用）— 基于 Recharts 或 visx |

## 7. 构建顺序

1. 写 token + 字体到 `styles/index.css`，全局禁用现有暖色调。
2. 重写 `AppShell` + `TabSwitcher` 到 6 标签结构。
3. 新建 `components/ui/*` 基础组件，给单元测试每个 Variant。
4. 拆出 6 个空 `*Tab.tsx`（先放占位 SectionHeader），保证导航跑通。
5. 然后逐页填充内容（按 [[page1-home-overview]] → [[page2-backtest-studio]] → … 顺序）。

## 8. 测试

- Vitest 现有 `ResearchConsolePage.test.tsx` 必须更新到 6 标签集合。
- 给每个 `ui/*` 组件一个最小 snapshot/role 测试，保证后续重构不破基线。
