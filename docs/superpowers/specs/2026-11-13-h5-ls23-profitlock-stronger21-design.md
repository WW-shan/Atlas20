# Atlas20 候选：LS23 利润保护释放权重只给更强 21D 持有者

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已做 4 个确认窗口的诊断筛选；21D 为当前主候选，等待独立 OOS |
| 候选 ID | `PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21` |
| 基线 | LS23：H5 1.25x + LS22 单龙头利润保护 + LS12 双空头 router |
| 机制 | LS22 触发并减半最大多头后，只有 21D trailing return 严格高于被减半龙头的其他已持有 H5 资产才接收释放权重；按相对权重重分配，单币 cap 60% NAV，剩余留现金 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；short stop 20%；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS43 已经把 LS22 释放权重从“任意其他持有者”收紧到“7D 强于被减半龙头”的持有者，并在主样本
把 LS23 的 61.9150x / 1.9448 / -39.84% 提升到 66.6800x / 1.9667 / -40.134%。但 LS43 的
增量高度集中在 2024 年，且 51 天诊断窗口没有合格接收者。

本候选检验一个更长的确认窗口：接收者必须在与利润保护触发相同的 **21D** 上仍然强于被减半
龙头。这个条件不是新增价格阈值；它复用 LS22 已经使用的 21D horizon，只改变释放权重的去向。

## 1. 诊断筛选

在正式主样本运行前，对接收者确认窗口做了 7/14/21/28D 的四个诊断变体。四者都保持 LS23 的
其余规则、20bps、同一主样本不变：

| 接收者确认窗口 | 终值 | Sharpe | MDD | 有接收者的事件 | 再分配权重 |
|---:|---:|---:|---:|---:|---:|
| 7D（LS43） | 66.6800x | 1.9667 | -40.134% | 14 | 1.9606 |
| 14D | 68.5933x | 1.9804 | -39.835% | 11 | 1.4350 |
| **21D** | **69.2088x** | **1.9846** | **-39.835%** | **6** | **0.4803** |
| 28D | 62.6057x | 1.9484 | -39.835% | 5 | 0.3698 |

21D 在四个窗口中终值和 Sharpe 最高，MDD 也比 LS43 改善约 0.30pp。代价是再分配事件从 14 个
降到 6 个，机制更集中；因此这不是一个“更多交易”的候选，而是一个更严格的接收者过滤。

该筛选已经看过主样本，不能把 21D 结果当作独立预注册证据。后续 promotion 需要：

- 21D 选择之后的新真实 OOS；
- 成本、funding、路径、滚动、集中度和多重检验；
- 若增量仍只来自单一年份，必须明确降级。

## 2. 冻结构造

```text
at each H5 long target event:
  leader = largest target-weight asset
  if leader 21D trailing return >= 100%:
      reduce leader weight by 50%
      freed = leader weight before - leader weight after
      recipients = other positive H5 holdings
      recipient is eligible only if:
          recipient 21D trailing return > leader 21D trailing return
      allocate freed pro-rata to eligible recipients
      cap each asset at 60% NAV
      any remainder stays in cash
  else: unchanged
```

- 不新增资产；
- 不改变 H5 选币、LS12 空头 router、20% short stop、50% buffers、1.25x H5 或 1.50x hard gross；
- 不扫描 threshold、scale、cap、空头权重或空头 stop；
- 21D 是 LS22 已经使用的 horizon，不是新的收益预测模型。

## 3. 验收标准

1. 20bps 终值 >= LS23 的 61.9150x，Sharpe >= 1.9448，MDD 不差于 -44.84%；
2. 2/20/50/100bps 终值和 Sharpe 均 >= 同成本 LS23 与 L125；
3. 100bps 终值 > LS23 的 15.5037x、Sharpe > 1.3745、MDD <=50%；
4. 3x short-adverse funding 0 强平，MDD <=50%；
5. 0 强平、0 gross breach、observed gross <=1.50x；
6. 删除任一最佳年份后终值仍高于 L125；
7. 365D rolling worst >= L125 的 0.7325x；
8. 45 个已保存收益路径月初切片通过终值、Sharpe 和 MDD 5pp；
9. 12 个真实 cash-start 中至少 10/12 终值和 Sharpe 胜 L125，12/12 MDD 5pp；
10. 单资产空头贡献 <=50%，前 3 <=80%；
11. PBO/CSCV <=0.50，White Reality Check p <=0.05；
12. 选择后的独立 OOS 至少 12 个月；未完成前最高只能 provisional。

这些是验收标准，不是阻止继续研究的禁令。若 LS45 失败，继续测试其他机制，不把本候选的失败
解释为“多空/利润保护方向无效”。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_stronger21
```

研究输出不是订单，也不是实盘批准。
