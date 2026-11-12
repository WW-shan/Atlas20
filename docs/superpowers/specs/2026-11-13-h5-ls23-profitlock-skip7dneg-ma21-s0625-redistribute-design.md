# Atlas20 候选：LS54 的负 7D skip 保留 62.5% 龙头

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已预注册；等待主样本评估；不接实盘 |
| 候选 ID | `PR2026-11-LS56-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-S0625-REDISTRIBUTE` |
| 基线 | LS23；LS51；LS54；LS55 |
| 机制 | LS54 的 MA21-confirmed 7D 负确认 skip 保留 62.5% 龙头；未 skip 的 LS22 trim 仍是 0.5，并继续使用 LS45 的 21D 强持有者再分配 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；missing mark carry 3h；20% short stop；hard total gross 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS55 的 75% skip 已修复 100bps MDD（-49.879%），并把 365D rolling worst 从 0.843596x
提高到 0.849344x，但仍低于 LS23 的 0.855093x，差 0.575pp。LS55 同时保留了高于 LS23 的
OOS 和主样本收益。

LS56 是 0.50 与 0.75 的唯一预注册中点，不改任何其他规则：

```text
if 21D >= 100% and 7D < 0 and close > MA21:
    leader_weight *= 0.625
elif 21D >= 100% and leader_weight >= min:
    leader_weight *= 0.50
```

释放的 0.375 权重留现金；未 skip 的 0.5 trim 继续按 LS45 只向 21D 更强的既有 H5 持有者
再分配，单币 cap 60% NAV。不扫描 0.55/0.60/0.65/0.70。

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

不因 LS55 的改善或本次 OOS 表现放宽 rolling、100bps MDD 或任何其他预注册门禁。若失败，记录为
rejected/partial mechanism，并继续研究下一个独立机制。

## 2. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS56-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-S0625-REDISTRIBUTE \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_s0625_redistribute
```

研究输出不是订单，也不是实盘批准。
