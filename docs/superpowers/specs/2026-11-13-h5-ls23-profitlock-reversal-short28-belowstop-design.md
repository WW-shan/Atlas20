# Atlas20 候选：LS47 反手空头的止损价回踩重武装

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已预注册；主样本评估中；不接实盘 |
| 候选 ID | `PR2026-11-LS50-H5-LS23-PROFITLOCK-REVERSAL-SHORT28-BELOWSTOP` |
| 基线 | LS23；LS46；LS47；LS48；LS49 |
| 机制 | LS47 的 0.20x / 28D 反手空头；20% short stop 后，同一 28 天窗口内只有在最后一个完整日收盘重新跌回实际 stop 成交价之下，才允许 routine rebalance 重开；否则保持空仓等待 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；missing mark carry 3h；20% short stop；hard total gross 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS48 证明“stop 后整个窗口禁止重开”会把有利的二次入场删掉；LS49 的 MA21 确认虽然恢复了部分
二次入场，但会晚一天，错过 stop 后的第一段下跌。LS50 改为更直接的状态：stop 已经突破了一个
明确价格，只有价格重新跌回 stop 成交价之下，才认为突破失败、允许同窗口重开。

```text
after a reversal short is stopped:
    record the actual stop fill price
    block routine re-entry while the last completed daily close >= stop price
    re-arm once the last completed daily close < stop price
    reset the state at window expiry or a new full-exit window
```

这不是按 OOS 日期写死的过滤，也不改变 stop 百分比、空头权重或持有期。

## 1. 诊断依据

LS47 OOS 的 NEAR 第一次空头在 2026-10-11 被 stop 于约 5.78；10-14 价格回到约 5.16，已经低于
stop 成交价，随后继续下跌。LS48 完全禁止重开，反而错过这段收益；LS50 用 stop price 作为
“突破是否失败”的可观察边界，既能允许这种回踩，也能阻止价格仍在 stop 上方时的无确认重开。

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

若 LS50 仍不能同时改善主样本和 OOS，记录为 rejected/partial mechanism，不降低门槛；继续研究
其他反手空头状态、确认信号和负收益策略反向利用。

## 3. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS50-H5-LS23-PROFITLOCK-REVERSAL-SHORT28-BELOWSTOP \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_reversal_short28_belowstop
```

研究输出不是订单，也不是实盘批准。
