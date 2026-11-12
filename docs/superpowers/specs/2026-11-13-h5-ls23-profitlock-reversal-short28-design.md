# Atlas20 候选：LS44 利润保护全退后反手 28 天空头

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 主样本已评估；成本/funding/稳健性继续补测；不接实盘 |
| 候选 ID | `PR2026-11-LS46-H5-LS23-PROFITLOCK-REVERSAL-SHORT28` |
| 基线 | LS23；LS44 作为多头触发分支 |
| 机制 | LS44 在 21D>=100% 且该龙头 7D<0 时完全退出；释放出来的风险预算反手做空该龙头，总空头 0.20x，持有 28 个日历日，20% short stop；反转空头优先于 LS12 router |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；missing mark carry 3h；成本 2/20/50/100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

用户提出：既然平仓后已经看空，为什么不直接反手开空，而不是只留现金？LS44 已经证明“7D 转负
时把极端上涨龙头全部退出”能降低 MDD，但单独全退的终值低于 LS23。本候选把 LS44 释放出来的
风险预算用于同一资产的反转空头，检验“退出 + 反手”是否能把防守动作变成正收益来源。

这不是把所有 H5 多头整体翻空，也不是加杠杆：

- 只在 LS44 的 9 次 full-exit 事件触发；
- 空头总请求不超过 0.20x NAV；
- 与 LS12 router 二选一，不叠加两个 0.25x 空头 sleeve；
- hard total gross 仍为 1.50x；
- 20% adverse short stop 继续由引擎逐小时执行。

## 1. 机制

```text
at each H5 target event:
  if leader 21D trailing return >= 100% and leader 7D trailing return < 0:
      long leader = 0
      activate short(leader) for 28 calendar days
  elif leader 21D trailing return >= 100%:
      long leader *= 0.5
  else:
      unchanged

short priority:
  if any reversal short is active:
      allocate 0.20x equally across distinct active reversal assets
      do not use the LS12 router at the same time
  else:
      use the frozen LS12 dual-short router as before
```

同一资产在重叠事件中只保留一条空头腿，不因为 SHIB 连续四个事件而叠加到 0.8x；这保证单资产
和总空头都受 0.20x 上限约束。LS12 router 的 0.25x 请求只在没有反转空头时生效。

## 2. 诊断筛选

在正式主样本前做了小范围诊断：

- 持有期 14/21/28/35 天；
- 反转空头总权重 0.15/0.20/0.25x；
- 0.25x 版本在 20bps 出现 observed gross 1.534x，超过 1.50x hard cap，不能作为候选；
- 0.20x / 28D 在修正重叠 SHIB 事件后，正式 20bps 为 **67.6951x / 1.9919 / -34.916%**，
  0 强平、0 gross breach、max observed gross **1.4778x**；
- 该结果优于 LS23 的 61.9150x / 1.9448 / -39.84%，也优于 LS44 的 60.5213x / 1.9361 /
  -39.06%。

诊断已经看过主样本，因此 0.20x / 28D 不是独立预注册选择；后续 promotion 需要选择后的真实
OOS。该候选的机制集中度很高：只有 9 次 full-exit 事件，不能把主样本增量当作稳定 alpha。

## 3. 验收标准

1. 20bps 终值 >= LS23 61.9150x，Sharpe >= 1.9448，MDD 不差于 -44.84%；
2. 2/20/50/100bps 终值和 Sharpe 均 >= 同成本 LS23 与 L125；
3. 100bps 终值 > LS23 15.5037x、Sharpe > 1.3745、MDD <=50%；
4. 3x short-adverse funding 0 强平、MDD <=50%；
5. 0 强平、0 gross breach、observed gross <=1.50x；
6. 删除任一最佳年份后终值仍高于 L125；
7. 365D rolling worst >= L125 0.7325x；
8. 45 个路径月初切片通过终值、Sharpe 和 MDD 5pp；
9. 12 个真实 cash-start 至少 10/12 终值和 Sharpe 胜 L125，12/12 MDD 5pp；
10. 单资产空头贡献 <=50%，前 3 <=80%；
11. PBO/CSCV <=0.50，White Reality Check p <=0.05；
12. 选择后的独立 OOS 至少 12 个月；未完成前最高只能 provisional。

这些是验收标准，不是停止研究的限制。若 LS46 失败，继续研究其他多空机制，不把本候选失败
解释为“反手空”方向无效。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS46-H5-LS23-PROFITLOCK-REVERSAL-SHORT28 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_reversal_short28
```

研究输出不是订单，也不是实盘批准。
