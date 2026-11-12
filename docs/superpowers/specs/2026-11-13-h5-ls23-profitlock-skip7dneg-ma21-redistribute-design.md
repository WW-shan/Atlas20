# Atlas20 候选：LS53 跳过规则 + LS45 强 21D 再分配

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已预注册；主样本评估中；不接实盘 |
| 候选 ID | `PR2026-11-LS54-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-REDISTRIBUTE` |
| 基线 | LS23；LS45；LS51；LS53 |
| 机制 | LS53 的 7D 负确认跳过规则；未跳过的 LS22 trim 使用 LS45 的再分配规则：释放权重只给 21D trailing return 更强的既有 H5 持有者，单币 cap 60% NAV，剩余留现金 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；missing mark carry 3h；20% short stop；hard total gross 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS53 保留了 LS51 的 OOS 改善（NEAR 在 MA21 上方时保留完整权重），但主样本回到 LS23 以下，
因为它在 SHIB 跌破 MA21 时恢复半仓。LS45 则在 2024 的 6 次 trim 中把释放权重转给 21D 更强的
既有持有者，主样本终值和 Sharpe 更高，但增量高度集中在 2024。

LS54 将两个独立预注册机制组合，检验“跳过强趋势浅回撤 + 把真正的减仓权重给更强持有者”是否
同时保留 LS53 的 OOS 防守和 LS45 的主样本收益。跳过的 event 不分配任何权重；未跳过的 event
才使用 LS45 的接收者条件。

## 1. 验收标准

1. 20bps 终值 >= LS23 的 61.9150x，Sharpe >= 1.9448，MDD 不差于 LS23 的 -39.84% 加 1pp；
2. 2/20/50/100bps 终值和 Sharpe 均不低于同成本 LS23；
3. 100bps 终值 > 15.5037x、Sharpe > 1.3745、MDD <=50%；
4. 3x short-adverse funding 0 强平、MDD <=50%；
5. 0 强平、0 gross breach、observed gross <=1.50x；
6. 删除任一最佳年份后终值仍高于 L125；
7. 365D rolling worst >= LS23 的 0.8551x；
8. 45 个月初路径全部通过终值、Sharpe 和 MDD 5pp（相对 L125）；
9. 12 个真实 cash-start 至少 10/12 终值和 Sharpe 胜 L125，12/12 MDD 5pp；
10. 单资产空头贡献 <=50%，前 3 <=80%；
11. PBO/CSCV <=0.50、White Reality Check p <=0.05，并在当前试验台账下报告 DSR；
12. 选择后的独立 OOS 至少 12 个月；未完成前最高只能 provisional。

如果组合不能同时通过主样本和 OOS，记录为 rejected/partial mechanism；不降低门槛，继续研究
其他利润保护和多空机制。

## 2. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS54-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-REDISTRIBUTE \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_redistribute
```

研究输出不是订单，也不是实盘批准。
