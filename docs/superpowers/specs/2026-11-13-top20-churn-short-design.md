# Atlas20 研究预注册：Top20 churn short against BTC

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 候选族 ID | `PR2026-11-LS72-TOP20-CHURN-SHORT` |
| 来源 | LS71 事件诊断显示 entry 和 exit 事件都可能继续跑输 BTC |
| 状态 | 组合级研究回测；不连接实盘、不修改 live target |
| 数据 | strict PIT CMC Top20 + `data/processed/panel_daily.csv` |
| Discovery | 2022-01-01 → 2023-12-31 |
| Validation | 2024-01-01 → 2026-11-12 |
| Independent OOS | 2021-01-01 → 2021-12-31 |
| 执行 | 事件确认日 close 后，下一 close 起持有 h 日 |
| 成本 | 2 / 20 / 50 / 100bps 每边；初步筛查不计 funding |

## 0. 机制与冻结规则

LS71 的事件级描述发现，Top20 `entry` 与 `exit` 事件在 discovery/validation 都没有稳定的
BTC 超额正收益；多数方向是**继续跑输 BTC**。本轮因此检验一个 market-neutral churn short：

- 事件确认窗口 `m ∈ {3, 7, 14}` 个交易日；
- 每个事件日把当天所有 entry/exit 事件资产等权做空；
- 用 BTC 多头对冲空头总名义，保持每腿 0.5/h 的总 gross；
- 持有 `h ∈ {7, 14, 28, 56}` 个交易日；
- 同一资产同类型事件冷却 30 天；
- 每个事件日作为一个 tranche，所有 phase 等权，组合总 gross <=1；
- 共 `3 × 4 = 12` 个 cell。

事件定义和 LS71 完全一致；本轮不允许根据 validation 改变 m/h、加入资产白名单或把 entry/exit
拆成事后方向。

## 1. 选择与验收

只按 discovery 20bps Sharpe 选一个 cell，要求 discovery 20bps 与 50bps Sharpe 都 >0。候选必须：

- validation 20bps 与 50bps Sharpe >0；
- 2021 independent OOS 20bps Sharpe >0；
- full 20bps 终值 >1.0、Sharpe >0.5、MDD 不差于 -30%；
- full 20bps 与 50bps 终值均高于 1.0；
- 报告事件数、平均 gross、turnover、资产贡献和 overlay 到 LS57 的 return-space 结果。

通过只进入 funding、Bitget mark/fill、gross 和 live shadow 阶段，不直接接实盘。

## 2. 失败后动作

若失败，不扫描同一事件的更多 m/h、冷却期、权重、BTC hedge 比例或 entry/exit 组合；停止
Top20 churn 家族，另起机制。LS71 的事件级描述因为同日事件过滤只留下极少 cell，保留为诊断限制，
不会在 LS72 中伪装成已通过的事件研究。

## 3. 复现

```bash
.venv/bin/python scripts/run_top20_churn_short.py \
  --start-date 2021-01-01 --end-date 2026-11-12 \
  --output-dir reports/top20_churn_short_2026
```
