# Page 6 — Reports & Exports 实施计划

视觉来源：`output/imagegen/atlas20_page6_reports_exports.png`（已验收）。
落点 feature：`apps/web/src/features/reports/ReportsExportsTab.tsx`（新建）。
前置：[[00-design-system]]。

## 1. 信息架构

```
[Page Header · 64px]   左：标题+副标   右：+ NEW REPORT gold + TEMPLATES outline
[Featured · Weekly Digest 卡 · 全宽 · ~ 200px]
[REPORT ARCHIVE 小节头 · 32px]   左：section header   右：Sort: Most recent ▾ mono
[Archive Grid · 3×2 · ~ 560px]
```

## 2. Page Header

- 标题 `Reports & Exports` / 副 muted `Generated reports archive + format export center`。
- 右：
  - `<ButtonGold>+ NEW REPORT</ButtonGold>` → 弹出新建报告对话框（先实现按钮，对话框另开）。
  - `<ButtonOutline>TEMPLATES</ButtonOutline>` → 路由到模板库（先 stub）。

## 3. Featured · Weekly Digest 卡（hero）

- `<Card variant="hero">`，gold halo（同 page1 hero）。
- **左侧**：
  - `<Pill tone="cyan-outline" size="xs">FEATURED · WEEKLY DIGEST</Pill>`
  - 大标题 28px sans 600：`Atlas20 — Week 20 / 2026`
  - 副 muted mono：`ATLAS Adaptive v3 · YTD +1,247.56% · Top-20 universe · generated 2026-05-18 14:32 UTC`
- **右侧**（2×2 grid + 底部一个 gold 按钮宽度对齐）：
  - `<PillButton tone="violet" size="md">MARKDOWN</PillButton>`
  - `<PillButton tone="gold" size="md">PDF</PillButton>`
  - `<PillButton tone="cyan" size="md">PNG report</PillButton>`
  - `<PillButton tone="emerald" size="md">CSV data</PillButton>`
  - `<ButtonGold>↓ DOWNLOAD ALL</ButtonGold>` 占满下方一行
- 每个 format 按钮：点击触发 `downloadDigest(format)` mutation；DOWNLOAD ALL 触发 `downloadDigest("bundle")` 打包下载。

## 4. Report Archive 小节

- 左：`<SectionHeader>REPORT ARCHIVE</SectionHeader>`（uppercase 11px muted mono）。
- 右：`<Select size="sm">Sort: Most recent ▾</Select>`，options：`Most recent / Oldest / By size / By type`。
- 排序状态：`useState<SortKey>("recent")` → 传入 `listReports(sort)`。

## 5. Archive Grid（3×2 = 6 张 report card）

`<Grid cols={3} gap={16}>`。每张 `<Card variant="report">`，~ 260px 高：

- **上部 thumbnail strip** ~ 96px 高，按 report 类型不同 SVG 缩略：
  - `equity`：双线（gold + violet）折线缩略
  - `lines`：单 / 多 line 折线
  - `heatmap`：4×6 渐变色块（gold-violet）
  - `bars`：竖直 bar 群（violet）
  - `horizontal-bars`：横向 bar 堆叠（gold / emerald）
  - `sparkbar`：稀疏 cyan bars
- **中部第 1 行**：标题（white sans 600 16px）
- **副标 muted mono 12px**：`btk_id · date · size` 三段 `·` 分隔（或 `digest_wXX · date · size`）
- **底部 row**：右对齐 `DOWNLOAD ↓` gold 文字按钮（READY 态）/ `<Pill tone="cyan">GENERATING</Pill>` + 脉冲（生成中态，下载隐藏）
- **highlight 态**：左侧 3px gold 竖条 + 极淡 gold 内阴影（仅最新 weekly digest）

### 固定 6 张内容（fallback mock，按截图）

| # | 标题 | thumbnail | 元数据 | status | highlight |
|---|---|---|---|---|---|
| 1 | `Atlas20 — Week 19 / 2026` | equity | `digest_w19 · 2026-05-11 · 3.1 MB` | READY | ✓ gold left bar |
| 2 | `ATLAS Adaptive v3 — Tear sheet` | lines | `btk_0142 · 2026-05-18 · 2.4 MB` | READY | — |
| 3 | `Q1 2026 Performance Review` | heatmap | `q1_2026_review · 2026-04-02 · 4.6 MB` | READY | — |
| 4 | `Momentum Family Comparison` | bars | `cmp_momentum · 2026-05-09 · 1.8 MB` | READY | — |
| 5 | `Universe Composition · April 2026` | horizontal-bars | `uni_2026-04 · 2026-05-01 · pending` | GENERATING | — |
| 6 | `MeanRev v2 — Backtest Report` | sparkbar | `btk_0136 · 2026-05-07 · 2.1 MB` | READY | — |

## 6. 数据接入

- `lib/api.ts` 新增：
  ```ts
  getFeaturedDigest(): Promise<FeaturedDigest>;
  listReports(sort: SortKey): Promise<ReportEntry[]>;
  downloadDigest(format: "markdown" | "pdf" | "png" | "csv" | "bundle"): Promise<{ url: string }>;
  downloadReport(id: string): Promise<{ url: string }>;
  ```
  ```ts
  type ReportEntry = {
    id: string;
    title: string;
    subtitle: string;
    thumbnail: "equity" | "lines" | "heatmap" | "bars" | "horizontal-bars" | "sparkbar";
    status: "ready" | "generating";
    highlight?: boolean;
  };
  ```
- Query keys：`["reports","featured"]` / `["reports","archive",sort]`。
- fallback mock = 上表 6 行。

## 7. 现有代码改造点

- `ResearchConsolePage` 添加 `tab === "reports"` 分支。
- 新建：
  - `components/reports/FeaturedDigestCard.tsx`
  - `components/reports/ReportCard.tsx`
  - `components/reports/ReportThumbnail.tsx`（按 kind switch SVG）
  - `components/reports/SortSelect.tsx`（如不复用通用 Select）
  - 通用 `components/ui/PillButton.tsx`（与 Pill 区别：内含 icon 槽 / 可点 / focus ring）
- 复用 `<Pill>` / `<Card>` / `<Button>` / `<SectionHeader>`。

## 8. 测试

- `ReportsExportsTab.test.tsx`：
  - 渲染 featured：标题 `Atlas20 — Week 20 / 2026` + 4 format 按钮 + `DOWNLOAD ALL`；
  - 点 `+ NEW REPORT` → `onNewReport()` 调用；
  - 渲染 6 张 archive card；其中 5 READY / 1 GENERATING；
  - 第 1 张 `data-highlight="true"`；
  - 点 READY 卡的 DOWNLOAD ↓ → `downloadReport(id)` mutation 触发；
  - GENERATING 卡无 download 按钮，有 cyan pill；
  - 切 Sort → query key 含 `sort=...`。

## 9. 验收对照

- gold 仅出现在 + NEW REPORT、PDF 按钮 tint、DOWNLOAD ALL、highlight 竖条、卡内 DOWNLOAD ↓ ✓
- GENERATING 卡 cyan + 脉冲 ✓
- 全部数字 / 元数据 mono ✓
- 顶导 `Reports` 激活态 gold underline ✓
