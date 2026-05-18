# Page 5 — Universe & Data Health 实施计划

视觉来源：`output/imagegen/atlas20_page5_universe_health.png`（已验收）。
落点 feature：`apps/web/src/features/universe/UniverseHealthTab.tsx`（新建）。
前置：[[00-design-system]]。

## 1. 信息架构

```
[Page Header · 64px]   左：标题+副标   右：cyan "Last refreshed ..." pill + ↻ FORCE REFRESH outline gold
[Top-20 Universe Timeline · 全宽 · ~ 440px]
[Data Sources 50% · Data Quality Alerts 50% · 并排 · ~ 360px]
```

## 2. Page Header

- 标题 `Universe & Data Health` / 副 muted `Top-20 token composition over time + data source status`。
- 右：
  - `<Pill tone="cyan">Last refreshed 2026-05-18 14:32 UTC</Pill>`
  - `<ButtonGoldOutline>↻ FORCE REFRESH</ButtonGoldOutline>` → 触发 `POST /api/universe/refresh`，期间按钮自旋。

## 3. Top-20 Universe Timeline 卡

- 头：标题 + 副 muted `Daily composition · last 180 days` + 右侧 legend `● in universe (gold)  ● rotation event (violet vertical line)`。
- 主图自定义渲染（SVG 或 Canvas，建议 SVG 因为 lane 数 32 可控）：
  - Y 轴：32 个 mono ticker（按规模或字母序），每行一条 lane。BTC lane muted（excluded）。
  - 每 lane：dark base track `var(--border)` 全宽；其上分段渲染 gold 填充矩形（subtle gold luminous edge），仅在该 token 处于 top-20 的天数上。
  - 顶部叠 3-4 条 violet 虚线 vertical（rotation events），每条顶部一个 mono 小 tag `MAJOR ROTATION`。
  - X 轴底：6 个月份 mono `Dec 2025 / Jan / Feb / Mar / Apr / May 2026`。
- 组件：`components/universe/UniverseTimeline.tsx`，props：
  ```ts
  { tokens: string[]; segments: { token; start; end }[]; rotations: { ts; label }[]; range: [Date, Date] }
  ```

## 4. 左卡 — Data Sources（50%）

- 头：`Data Sources` + 副 muted `9 sources monitored`。
- 3×3 grid，9 个 tile，每 tile：
  - 第 1 行：source 名 + `<Pill>` `HEALTHY` emerald / `DEGRADED` cyan / `ERROR` rose；
  - 第 2 行：mono `Last sync: 12s ago` / `14m ago` / `2h 14m ago`；
  - ERROR 左侧 3px rose 竖条；DEGRADED 左侧 3px cyan 竖条；HEALTHY 无竖条。
- 9 个名字按截图：CoinGecko · Markets / CryptoCompare · OHLCV / Binance · Spot / Coinbase · Spot / Kraken · Spot / DefiLlama · TVL / Glassnode · On-chain / Messari · Metrics / Custom · CSV uploads。
- 状态分布：6 HEALTHY / 2 DEGRADED / 1 ERROR。

## 5. 右卡 — Data Quality Alerts（50%）

- 头：`Data Quality Alerts` + 右侧 rose count badge `6 open`。
- 列表 6 行，每行：
  - 左：severity icon — rose triangle `<AlertTriangle>` / cyan circle `<Info>` / emerald check `<CheckCircle>`（lucide-react）；
  - 中：标题（white）+ 副 muted 元数据（时间 / 间隙 / 来源 / 处置）；
  - 右：mono 时间戳 + `▾` action menu。
- 6 条按截图：
  1. (rose) `BNB · price gap detected — auto-imputed`
  2. (rose) `RNDR · volume outlier (5σ) — flagged for review`
  3. (cyan) `DOT · stale tick > 30s on Coinbase`
  4. (rose) `ICP · OHLCV mismatch CoinGecko vs Kraken`
  5. (emerald) `ATOM · validator slashing event resolved`
  6. (cyan) `Universe diff: 2 in / 2 out at 2026-05-15 00:00 UTC rebalance`

## 6. 数据接入

- `lib/api.ts` 新增：
  ```ts
  getUniverseTimeline(): Promise<{ tokens; segments; rotations; range }>;
  getDataSources(): Promise<DataSource[]>;
  getDataAlerts(): Promise<DataAlert[]>;
  ```
- 三个独立 query keys：`["universe","timeline"] / ["universe","sources"] / ["universe","alerts"]`。
- fallback mock 与截图一致（32 ticker、9 source、6 alert）。

## 7. 现有代码改造点

- `ResearchConsolePage` 加 `tab === "universe"` 分支。
- 新建：
  - `components/universe/UniverseTimeline.tsx`（SVG 渲染）
  - `components/universe/DataSourceTile.tsx`
  - `components/universe/DataAlertRow.tsx`
- 复用 `<Pill>` / `<SectionHeader>` / `<Card>`。

## 8. 测试

- `UniverseHealthTab.test.tsx`：
  - 渲染 32 lane（含 BTC muted）；
  - 至少 3 条 rotation 竖线在 DOM；
  - 9 source tiles，状态分布 6/2/1；
  - 点 FORCE REFRESH 触发 mutation；
  - 6 alert rows，含 3 rose / 2 cyan / 1 emerald（按内容分类）。

## 9. 验收对照

- gold 仅在 universe band 与激活态导航 ✓
- 异常状态左竖条颜色对应 ✓
- timeline 横向月份 X 轴 ✓
- 全数字 mono ✓
