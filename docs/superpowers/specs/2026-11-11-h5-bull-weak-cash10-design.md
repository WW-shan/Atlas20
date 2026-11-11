# Atlas20 候选预注册：H5 在牛市阶段弱于 BTC 时保留 10% 现金缓冲

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-11 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS15-H5-BULL-WEAK-CASH10` |
| 基线 ID | `PR2026-10-D-L125` |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 基础 alpha | 冻结 LS12：H5 1.25x + BTC 200D 双空头 regime router |
| 新增风险层 | BTC 在 200D 上方且 H5 影子 14D 弱于 BTC 时，整个目标账本保留 10% 现金 |
| risk-on gross scale | 1.0 |
| insurance gross scale | 0.9 |
| 执行 | T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| gross | target <=1.50x |

## 0. 研究问题

LS14 的 BTC rotation 证明了条件风险层可以把 20bps MDD 从 -40.65% 降到 -36.49%，但中高成本
和 2023-2024 多数路径起点失败。LS13 的 50% 现金减仓又把终值压到 33.7x，低于 L125。

LS15 改用更窄的风险状态和更小的现金缓冲：

> 只在 **BTC 仍在 200D 上方、但 H5 影子 14D 弱于 BTC** 时，把整个 LS12 目标账本缩小 10%，
> 其余时间保持 100% 目标 gross。

这针对的是“BTC 牛市里 H5 轮动落后”的路径，而不是所有 H5 相对走弱期；空头 router、H5 持币、
stop 和选币不变。10% 是明确的现金保险预算，不扫描 5%/15%/20%/30% 或把 90% 改成其他比例。

## 1. 冻结构造

```text
weak_t = H5_shadow_14d_t < BTC_14d_t
bull_t = BTC_close_t > SMA200(BTC_close)_t
insurance_t = weekly_sample(weak_t) and bull_t

target_t = 0.90 * (LS12 long_target_t - LS12 short_target_t) if insurance_t
           1.00 * (LS12 long_target_t - LS12 short_target_t) otherwise
```

- H5 shadow 使用未减仓 L125 的同 mark/funding/cost 路径；
- weekly sample 每 7 个自然日；T+1 UTC +3h；
- 空头 sleeve 和 H5 名单沿用 LS12；
- 10% scale 同时降低多头和空头的总风险预算，净方向和相对结构不变；
- 同一资产不能同时作为多头和空头。

## 2. 评估门槛

1. 20bps 终值 > L125；
2. 20bps Sharpe >= L125；
3. 20bps MDD <= L125 +5pp；
4. 主样本 0 次强平；
5. 2/20/50/100bps 终值和 Sharpe 均高于同成本 L125；
6. 100bps MDD <=50%；
7. 3x short-adverse 0 强平且 MDD <=50%；
8. 删除任一最佳年份后终值仍高于同成本 L125；
9. 365 天滚动最差 >= L125；
10. 45 个已保存收益路径月初切片全部通过；
11. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过基线，12/12 MDD 5pp；
12. 单资产空头贡献 <=50%，前 3 <=80%；
13. observed gross <=1.50 且无 gross breach hour；
14. PBO/CSCV <=0.50，White Reality Check p <=0.05；
15. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
16. 12 个月真实 OOS 未满前最高只能 provisional。

## 3. 失败后动作

如果 LS15 失败：

- 不扫描 cash buffer、bull/weak 阈值、lookback、频率或空头参数；
- 停止在同一 H5-bull-weak cash-buffer 家族内调参；
- 必须提出机制不同的新候选并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 4. 复现接口

```bash
.venv/bin/python scripts/run_h5_bull_weak_cash.py \
  --trial-id PR2026-11-LS15-H5-BULL-WEAK-CASH10 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_bull_weak_cash
```

## 5. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
