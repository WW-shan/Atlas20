# Atlas20 研究预注册：Top20 churn short with full-gross event tranches

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 候选族 ID | `PR2026-11-LS74-TOP20-CHURN-ALT-WEAK-FULLGROSS` |
| 来源 | LS73 `alt_rel_60` 通过但平均 gross 只有约 5%，收益被现金占用压低 |
| 状态 | 组合级研究回测；不连接实盘、不修改 live target |
| 冻结规则 | LS73 `m=7/h=28`、alt_rel_60 闸门、entry+exit、BTC 对冲 |
| 数据/窗口 | 同 LS73：2021-01-01 → 2026-11-12 |
| 成本 | 2 / 20 / 50 / 100bps 每边；初步筛查不计 funding |

## 0. 研究问题

LS73 的 `alt_rel_60` 在 2021 负控、discovery、validation 都满足预注册门槛，但 full 仅
**1.0608x / Sharpe 0.5686 / MDD -2.56%**；它的 event tranche 平均 gross 约 5%，大量时间
没有使用资本。本族只改变一个执行/仓位规则：当有 active churn tranche 时，把该日原始权重
按 gross 归一化到 1.0；没有事件时保持现金。**总 gross 仍然严格不超过 1.0，不增加杠杆。**

该规则不改变事件定义、m/h、gate、资产、空头/多头方向、冷却期或成本。

## 1. 验收

候选必须同时满足：

- discovery 20bps Sharpe >0；validation 20bps Sharpe >0；2021 负控终值 >=0.92x；
- full 20bps 和 50bps 终值 >1.0，Sharpe >0.5，MDD 不差于 -30%；
- full 20bps 终值至少为 LS73 的 1.10 倍（表示 gross 使用确实带来了可见收益）；
- 报告最大 gross、平均 gross、turnover、逐资产贡献和 LS57 return-space overlay。

通过只进入 funding、Bitget mark/fill、partial-fill 和 live shadow；不直接接实盘。

## 2. 失败后动作

若归一化后收益仍不足以覆盖成本，停止 churn 家族，不扫描 gross 目标、单资产 cap、m/h、
gate 或 overlay 权重。若收益显著提升但回撤恶化超过门槛，只保留为需要单独风险预算的 sleeve。

## 3. 复现

```bash
.venv/bin/python scripts/run_top20_churn_fullgross.py \
  --start-date 2021-01-01 --end-date 2026-11-12 \
  --output-dir reports/top20_churn_fullgross_2026
```
