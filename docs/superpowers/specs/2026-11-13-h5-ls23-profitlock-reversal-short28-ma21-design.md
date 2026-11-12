# Atlas20 候选：LS47 反手空头的 MA21 止损后重武装

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已预注册；主样本评估中；不接实盘 |
| 候选 ID | `PR2026-11-LS49-H5-LS23-PROFITLOCK-REVERSAL-SHORT28-MA21` |
| 基线 | LS23；LS46；LS47；LS48 |
| 机制 | LS47 的 0.20x / 28D 反手空头；20% short stop 后，同一 28 天窗口内必须等到该资产最后一个完整日收盘低于 21 日移动平均，才允许因后续 routine rebalance 重新开空 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；missing mark carry 3h；20% short stop；hard total gross 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS48 把所有止损后的同窗口重开都禁止，结果 OOS 中 NEAR 在 10-11 stop 后的第二次空头被错误地
屏蔽，而该次空头在 10-14 之后实际继续获利。说明 stop 本身不是“方向失效”的充分条件，直接
禁止重开会把有利的二次入场也删掉。

LS49 因此保留 LS47 的完整信号和权重，只增加一个价格确认：

```text
after a reversal short is stopped:
    do not reopen on routine target changes
    re-arm only when the last completed daily close < MA21
    otherwise stay flat until the 28-day window ends or a new event starts
```

MA21 与 H5/LS22 使用的 21D 时间尺度一致；不扫描 MA 窗口、阈值、ATR 或 stop 百分比。

## 1. 诊断依据

LS47 的 2026-10-04 NEAR 反手空头在 10-11 被 20% stop 平掉，10-14 因其他资产目标变化重开；
这次重开在 11-02 前把价格从约 5.16 带到约 4.27，是有利的。LS48 的“禁止重开”反而让 OOS
exact 从 0.9018x 降到 0.8732x。价格确认规则的目标是只过滤没有趋势确认的重复开仓，而不是
过滤所有二次入场。

## 2. 验收标准

1. 20bps 终值 >= LS47 的 69.4109x，Sharpe >= 2.0023，MDD 不差于 LS47 的 -34.916% 加 1pp；
2. 2/20/50/100bps 终值和 Sharpe 均不低于同成本 LS47；
3. 100bps 终值 > 17.2669x、Sharpe > 1.4252、MDD <=50%；
4. 3x short-adverse funding 0 强平、MDD <=50%；
5. 0 强平、0 gross breach、observed gross <=1.50x；
6. 删除任一最佳年份后终值仍高于 L125；
7. 365D rolling worst >= LS47 的 0.9279x；
8. 45 个月初路径全部通过终值、Sharpe 和 MDD 5pp（相对 L125）；
9. 12 个真实 cash-start 至少 10/12 终值和 Sharpe 胜 L125，12/12 MDD 5pp；
10. 单资产空头贡献 <=50%，前 3 <=80%；
11. PBO/CSCV <=0.50、White Reality Check p <=0.05，并在当前试验台账下报告 DSR；
12. 选择后的独立 OOS 至少 12 个月；未完成前最高只能 provisional。

如果主样本或 OOS 不通过，记录为 rejected/partial mechanism，不降低门槛；继续研究其他
post-stop 状态和负收益策略反向利用。

## 3. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS49-H5-LS23-PROFITLOCK-REVERSAL-SHORT28-MA21 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_reversal_short28_ma21
```

研究输出不是订单，也不是实盘批准。
