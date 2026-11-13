# Atlas20 研究预注册：PIT Top20 membership event diagnostic

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 候选族 ID | `PR2026-11-LS71-TOP20-MEMBERSHIP-EVENT`（仅诊断阶段） |
| 数据 | strict PIT CMC Top20，`data/processed/panel_daily.csv` |
| 评估窗口 | 2021-01-01 → 2026-11-12 |
| Discovery | 2022-01-01 → 2023-12-31 |
| Validation | 2024-01-01 → 2026-11-12 |
| 研究问题 | 新进入 Top20 的资产是否继续跑赢，跌出 Top20 的资产是否继续跑输？ |

## 0. 机制

Top20 排名变化是现有动量、residual、lead-lag 和 carry 之外的新横截面信息源。新入榜资产可能
获得关注度和流动性，出榜资产可能遭遇资金流出；但日频排名边界会抖动，因此本诊断不直接使用
“今天是否刚好第 20 名”，而要求 membership 连续确认，并对同一资产的同类型事件设置冷却期。

## 1. 冻结诊断网格

- 确认窗口 `m ∈ {3, 7, 14}` 个交易日；
- 事件必须在确认后的当天或之后发生，收益从下一日 close 开始；
- forward horizon `h ∈ {7, 14, 28, 56}` 个交易日；
- 事件类型：`entry`（连续 m 日在 Top20）与 `exit`（连续 m 日不在 Top20）；
- 同一资产同类型事件冷却 `30` 个交易日；
- 至少 3 个同日事件才计算横截面均值；
- 每个事件记录 raw return、BTC excess return、Top20 equal-weight excess return；
- discovery 与 validation 分开报告，不使用 validation 选 m/h。

## 2. 预注册判断

只有同时满足以下条件的 cell 才允许进入组合回测：

- discovery 的 entry 平均 BTC excess >0，且 validation 也 >0；
- discovery 的 exit 平均 BTC excess <0，且 validation 也 <0；
- 两个方向各自至少有 20 个事件，且不是由单一年份贡献；
- 报告中明确列出事件数、资产分布和逐年结果。

任一项失败，LS71 在诊断阶段关闭；不扫描更多 m/h、不改确认窗口、不把 entry/exit 合成不透明
score。诊断本身不新增策略配置，不进入 trial inventory；若通过，再单独预注册组合级 LS71。

## 3. 复现

```bash
.venv/bin/python scripts/diagnose_top20_membership_events.py \
  --start-date 2021-01-01 --end-date 2026-11-12 \
  --output-dir reports/top20_membership_event_diagnostic_2026
```
