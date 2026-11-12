# Atlas20 候选：LS54 的负 7D skip 只保留 75% 龙头

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已预注册；等待主样本评估；不接实盘 |
| 候选 ID | `PR2026-11-LS55-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-S075-REDISTRIBUTE` |
| 基线 | LS23；LS51；LS53；LS54 |
| 机制 | LS54 的 MA21-confirmed 7D 负确认 skip 从保留 100% 改成保留 75%；未 skip 的 LS22 trim 仍是 0.5，并继续使用 LS45 的 21D 强持有者再分配 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；missing mark carry 3h；20% short stop；hard total gross 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS51/LS53 保留完整 leader 时改善了 51 天 OOS（zero 0.9727x、exact 0.9685x，高于 LS23
的 0.9403x/0.9365x），但 365D rolling worst 为 0.8436x，低于 LS23 的 0.8551x；100bps MDD
为 -50.275%，比 50% 门禁差 0.275pp。LS54 的强 21D 再分配把 20bps 终值提高到 67.2667x，
但没有改变这两个尾部失败项。

LS55 只改变“7D 负确认且仍在 MA21 上方”时的保留比例：

```text
if 21D >= 100% and 7D < 0 and close > MA21:
    leader_weight *= 0.75
elif 21D >= 100% and leader_weight >= min:
    leader_weight *= 0.50
```

0.75 是完整保留（1.0）与原始半仓（0.5）的唯一预注册中点，不扫描 0.70/0.80/0.90。释放的
0.25 权重留现金，不分配给其他资产；未 skip 的 0.5 trim 继续按 LS45 规则只向 21D 更强的既有
H5 持有者再分配，单币 cap 60% NAV。

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

不因主样本或本次 OOS 表现放宽 rolling、100bps MDD 或任何其他预注册门禁。若失败，记录为
rejected/partial mechanism，并继续研究下一个独立机制。

## 2. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS55-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-S075-REDISTRIBUTE \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_s075_redistribute
```

研究输出不是订单，也不是实盘批准。
