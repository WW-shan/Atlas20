# Atlas20 风险修正预注册：H5 + market-neutral funding carry（60% long buffer）

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS31-H5-FUNDING-CARRY-LONG60` |
| 基线 | L125；LS30 为同 sleeve 的 50% long-buffer 对照 |
| 多头 | 冻结 H5 1.25x；long buffer 从 50% 提高到 60% |
| 中性 sleeve | LS30 完全相同的 2 low-funding long / 2 high-funding short，每腿 6.25% NAV |
| 总预算 | long 1.25x + sleeve 0.25x = 1.50x hard total gross |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；short stop 20%；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS30 的 20bps 结果为 **48.9409x / 1.8110 / -40.34%**，高于 L125 的 40.2200x/1.7330，
但有 **1 次 long 强平**：2022-05-11 DOT long 从 17.5681 跌到 8.4220，正好越过 50% long
buffer 的理论强平价 8.4263。这个结果不能因为收益和 Sharpe 好看就被忽略。

LS31 只改一个风险参数：long buffer 50% → 60%。这不改变 H5 选币、carry 选币、空头 stop、
gross cap 或成本；目的是让 carry long 腿在 50%–60% 的 idiosyncratic drawdown 中先保留，
而不是被 50% 的清算边界直接清掉。若 60% buffer 仍不能消除强平，则停止这个 carry sleeve，
不继续扫 65/70/75%。

## 1. 冻结构造

```text
H5_long = frozen H5 1.25x, long_buffer=0.60
carry = LS30 frozen 7D funding carry: +6.25% x 2 low funding, -6.25% x 2 high funding
combined = H5_long + carry
max_total_gross = 1.50x
```

- 其余规则完全继承 LS30；
- 不改变 short buffer、short stop、rebalance、lookback、count、per-asset weight 或 min_assets；
- 不扫描 long buffer 的 55/65/70。

## 2. 预注册门槛

1. 20bps 终值 > L125；
2. 20bps Sharpe > L125；
3. 20bps MDD <= L125 +5pp；
4. 主样本 **0 次强平**；
5. 2/20/50/100bps 终值和 Sharpe 均高于同成本 L125；
6. 100bps MDD <= 50%；
7. 3x short-adverse 0 强平且 MDD <= 50%；
8. 删除任一最佳年份后终值仍高于 L125；
9. 365 天滚动最差 >= L125 的 0.7325x；
10. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
11. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过 L125，12/12 MDD 5pp；
12. 单资产空头贡献 <= 50%，前 3 <= 80%；
13. observed gross <=1.50 且无 gross breach hour；
14. PBO/CSCV <=0.50，White Reality Check p <=0.05；
15. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
16. 12 个月真实 OOS 未满前最高只能 provisional。

## 3. 失败后动作

如果 LS31 仍出现 long 强平，或收益/Sharpe 低于 L125，停止 carry sleeve 家族，不扫描 long buffer。
如果 20bps 通过但成本/路径失败，不接实盘并继续累积真实 OOS。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS31-H5-FUNDING-CARRY-LONG60 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_funding_carry_long60
```

## 5. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
