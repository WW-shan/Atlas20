# Atlas20 候选：LS51 只在 BTC 牛市跳过 7D 负确认减仓

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已预注册；主样本评估中；不接实盘 |
| 候选 ID | `PR2026-11-LS52-H5-LS23-PROFITLOCK-SKIP7DNEG-BULL` |
| 基线 | LS23；LS44；LS51 |
| 机制 | LS51 的 7D 负确认跳过规则只在 BTC 收盘高于 200D MA 的 bull regime 生效；BTC 低于/等于 200D MA 时恢复 LS22 的半仓减半 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；missing mark carry 3h；20% short stop；hard total gross 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS51 在 20bps 的终值和 Sharpe 高于 LS23，OOS exact 也明显改善（0.9685x vs 0.9365x），但
365D rolling worst 为 0.8436x，低于 LS23 的 0.8551x；100bps MDD 为 -50.27%，略高于 50%
门槛。最可能的风险来源是：在广泛下跌或熊市里保留一个已经 7D 转负的龙头完整权重。

LS52 只加一个预注册 regime 条件：

```text
if BTC close > MA200:
    apply LS51 skip rule when leader 7D < 0
else:
    apply original LS22 half-trim
```

BTC 200D MA 是项目已冻结的熊市 regime 定义，不扫描 50/100/150D，也不按日期手写过滤。

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

若 LS52 不能修复 rolling/100bps MDD，记录为 rejected/partial mechanism；不降低门槛，继续研究
其他利润保护和多空机制。

## 2. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS52-H5-LS23-PROFITLOCK-SKIP7DNEG-BULL \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_skip7dneg_bull
```

研究输出不是订单，也不是实盘批准。
