# Atlas20 候选：LS47 反手空头的止损后一次性状态

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已预注册；主样本评估中；不接实盘 |
| 候选 ID | `PR2026-11-LS48-H5-LS23-PROFITLOCK-REVERSAL-SHORT28-ONESHOT` |
| 基线 | LS23；LS46；LS47 |
| 机制 | LS47 的 0.20x / 28D 反手空头；若该反手空头被 20% short stop 平掉，在同一 28 天反转窗口内不再因其他资产触发的 routine rebalance 重开；新的 full-exit 窗口可以重新武装 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；missing mark carry 3h；20% short stop；hard total gross 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS46/LS47 的 OOS 失败不是来自反手空头方向本身，而是来自同一个 NEAR 反转事件在 20% stop
之后被下一次 H5 目标变化重新打开：stop 已经证明该交易路径不适合继续持有，但 target schedule
没有“止损后状态”，于是 routine rebalance 把它重新建了回来。

LS48 只增加一个执行状态，不改变信号、空头权重、持有期或 stop：

```text
reversal_short(asset) starts in an explicit 28-day execution window
if the 20% short stop closes that position:
    block a new short in the same asset for the remainder of this window
when the window ends, or a new full-exit event starts a new window:
    the asset can be armed again
```

该规则只作用于 reversal short 的 explicit window；LS12 router 的其他空头、H5 多头和其他资产
的 routine rebalance 不变。窗口由 profit-lock audit 的 full-exit 事件生成，不使用未来价格。

## 1. 诊断动机

现有 OOS 中，NEAR 在 2026-10-04 开反手空头，2026-10-11 被 20% stop 平掉；10-14 又因其他
资产的目标变化被重开。这个重开不是新的反转事件，也没有新的基本面信号，属于执行层状态缺失。
主样本中 reversal shorts 的 stop 次数也远高于 full-exit 事件数，说明“stop 后自动重开”可能把
一次失败的路径重复计入组合。

本试验不扫描 stop 百分比、持有期、空头权重、confirmation window 或阈值；只检验一个预注册的
状态机是否能减少重复 stop，同时不破坏 LS47 的主样本收益。

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

如果主样本收益下降但 OOS stop 重开被消除，仍按上述标准记录为失败/部分机制有效，不事后降低
门槛；后续继续研究 post-stop confirmation、状态重武装和负收益策略反向利用。

## 3. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS48-H5-LS23-PROFITLOCK-REVERSAL-SHORT28-ONESHOT \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_reversal_short28_oneshot
```

研究输出不是订单，也不是实盘批准。
