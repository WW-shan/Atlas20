# Atlas20 候选：LS51 只跳过仍在 MA21 上方的 7D 负确认

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已预注册；主样本评估中；不接实盘 |
| 候选 ID | `PR2026-11-LS53-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21` |
| 基线 | LS23；LS44；LS51；LS52 |
| 机制 | LS51 的 7D 负确认跳过规则只在龙头当前收盘仍高于自身 21D MA 时生效；若 7D 转负且已跌破 MA21，则恢复 LS22 半仓减半 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；missing mark carry 3h；20% short stop；hard total gross 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS51 的增量来自 9 次 7D 转负事件中保留完整龙头；其中 2024 年 SHIB 的三次事件已经跌破
自身 MA21，仍被保留完整权重，可能是 rolling worst 和 100bps MDD 变差的风险来源。LS53 用
单一趋势确认区分“强趋势中的浅回撤”和“已经破位的反转”：

```text
if 21D >=100% and 7D < 0:
    if close > MA21:
        keep full leader weight
    else:
        leader *= 0.5
```

MA21 与 H5/LS22 的利润保护 horizon 一致；不扫描 MA 窗口、阈值或 scale。OOS 中 NEAR 的两次
7D 负事件仍在 MA21 上方，因此 LS53 应保留 LS51 的样本外收益改善，同时尝试修复 2022/2024
rolling 与高成本回撤。

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

如果 LS53 仍不能修复 rolling/100bps MDD，记录为 rejected/partial mechanism；不降低门槛，
继续研究其他利润保护和多空机制。

## 2. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS53-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21
```

研究输出不是订单，也不是实盘批准。
