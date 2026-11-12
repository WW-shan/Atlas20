# Atlas20 候选：7D 负确认 skip 只在龙头 1D 止跌后生效

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已预注册；等待主样本评估；不接实盘 |
| 候选 ID | `PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE` |
| 基线 | LS23；LS51；LS54；LS55；LS56 |
| 机制 | LS54 的 MA21-confirmed 7D 负确认 skip 增加最后一个完整日确认：只有 leader 1D return >= 0 才保留完整权重，否则执行原 0.5 half-trim；未 skip 的 trim 继续使用 LS45 的 21D 强持有者再分配 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；missing mark carry 3h；20% short stop；hard total gross 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS56 的 rolling 结果仍低于 LS23。逐日分解显示 365D worst window 的差异几乎全部集中在
2023-02-04 APTOS skip 后的 2023-02-05/06 两天：APTOS 在 7D 已转负时仍未出现单日止跌，
随后继续下跌。LS55/LS56 的 scale 调整只能压缩这一事件，不能区分“强趋势中的一日反弹/整理”
与“仍在破位”。

LS57 因此加入一个没有额外窗口参数的确认：

```text
if 21D >= 100% and 7D < 0 and close > MA21 and 1D >= 0:
    keep full leader weight
elif 21D >= 100% and leader_weight >= min:
    leader_weight *= 0.50
```

1D 使用信号日之前最后一个完整日收盘，不使用未来价格。缺失或非有限 1D 收益时 fail closed，
执行原 0.5 trim。未 skip 的 trim 继续按 LS45 只向 21D 更强的既有 H5 持有者再分配，单币 cap
60% NAV。不扫描 1D 阈值、2D/3D 确认或其他 scale。

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

不因 LS54/LS55/LS56 的主样本表现放宽 rolling、100bps MDD 或任何其他预注册门禁。若失败，
记录为 rejected/partial mechanism，并继续研究下一个独立机制。

## 2. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_stable1d_redistribute
```

研究输出不是订单，也不是实盘批准。
