# Page 4 — Run History 实施计划

视觉来源：`output/imagegen/atlas20_page4_run_history.png`（已验收）。
落点 feature：`apps/web/src/features/history/RunHistoryTab.tsx`（新建）。
前置：[[00-design-system]]。

## 1. 信息架构

```
[Page Header · 64px]   左：标题+ "1,284 records"   右：↻ RE-RUN SELECTED gold + ⬇ EXPORT CSV violet outline
[Toolbar Strip · 64px]  search + filter chips + 右侧 date range + view toggle + cog
[Run Table Card · 720px]  table 14 行 + pagination
```

## 2. Toolbar

- 左 cluster：
  - `<SearchInput>` 280px, placeholder `Search by name, id, tag...`，左前置 magnifier 图标。
  - filter chips（多选）：`All / Favorited ★(active gold) / Completed(active emerald outline) / Failed / Running / ATLAS family / Momentum family / MeanRev family`
- 右 cluster：
  - `<DateRangePill>` `Last 30 days ▾` mono cyan；
  - view toggle list/grid 两个 icon button；
  - columns settings cog。

状态：`HistoryFilter = { q, chips: Set, dateRange, view }`；通过 URL search params 同步（便于分享链接）。

## 3. Table

13 列（含一列 actions），固定表头，可水平滚动。

| 列 | 渲染 |
|---|---|
| ★ | gold 实心 / muted 空心，点击切收藏 |
| RUN ID | mono `btk_0142` |
| STRATEGY | sans `ATLAS Adaptive v3` |
| UNIVERSE | mono `Top-20` |
| WINDOW | mono `2024→2026` |
| RETURN | mono，emerald 正 / rose 负 / muted `—` |
| SHARPE | mono |
| MAX DD | mono rose |
| STATUS | `<Pill>`：emerald COMPLETED / cyan RUNNING(+脉冲) / rose FAILED |
| DURATION | mono `1m 28s` / 进行中 `0m 24s / ~1:00` |
| SPARK | `<Sparkline color="gold|violet|cyan|rose|dashed" />` ~ 80px |
| CREATED | mono `2026-05-18 14:02` |
| ACTIONS | `• • •` menu trigger |

行样式：
- 高 44px，mono 数字右对齐 + tabular-nums；
- 隔行底色 `var(--row-stripe)`；
- 选中行：左侧 3px gold 竖条；
- hover：surface +2% 亮度。

数据：截图中 14 行（标题给出前 7 行 + "continue with 7 more plausible rows ending around 2026-05-15"），fallback mock 直接照抄。

## 4. Pagination

- 卡底：muted `Showing 1-14 of 1,284` 左；右侧 `1 2 3 ... 92` page nums，`1` active gold。
- 实现 `<Pager total page pageSize onChange />` 通用组件。

## 5. 选择 + 批量动作

- 表头 `★` 之前可加 checkbox（视觉里没有强调，但 RE-RUN SELECTED 按钮需要状态）。或换设计：通过收藏 + chip 过滤来选 → 但 Re-run Selected 通常指 multi-select。
- **决策**：先以「点击某行 = 选中」单选实现，gold 左竖条态。RE-RUN SELECTED 启用时跳 `backtest` tab 并预填该 runId 的参数。多选可在后续迭代加 checkbox 列。

## 6. 数据接入

- `lib/api.ts`：
  ```ts
  listRuns(filter): Promise<{ items: RunRow[]; total: number; page; pageSize }>;
  ```
- TanStack Query key：`["runs", filter]`。
- fallback：mock 至少 14 行（含 RUNNING、FAILED、负收益等多态）。

## 7. 现有代码改造点

- 旧 `SelectionHistoryTable.tsx`（在 `components/dashboard/`）废弃或拆为 `components/history/RunTable.tsx` 的素材。
- 新建：
  - `components/history/Toolbar.tsx`
  - `components/history/RunTable.tsx`（核心；接 `rows + selectedId + onSelect`）
  - `components/history/RunStatusPill.tsx`（也可以直接复用通用 `<Pill>` + 状态映射）
  - `components/ui/Pager.tsx`
- `ResearchConsolePage` 加 `tab === "history"` 分支。

## 8. 测试

- `RunHistoryTab.test.tsx`：
  - 渲染 fallback 数据，断言 14 行 + 头部 13 列；
  - 点收藏图标 → 状态翻转；
  - 选择 chip `Favorited` → 行集合缩为收藏行；
  - 点行 → `selectedId` 改变；
  - 点页码 `2` → query key 含 `page=2`。

## 9. 验收对照

- 顶导 `History` 激活态 gold ✓
- gold 仅出现在收藏星、选中行竖条、`1` page、`RE-RUN SELECTED` 按钮 ✓
- RUNNING 行 status pill cyan + 脉冲 ✓
- duration 进行中显示 `now / eta` ✓
- 全部数字 mono tabular ✓
