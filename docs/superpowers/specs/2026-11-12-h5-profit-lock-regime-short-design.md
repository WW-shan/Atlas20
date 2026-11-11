# Atlas20 候选预注册：H5 利润保护 + LS12 空头 router

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS23-H5-PROFIT-LOCK-REGIME-SHORT` |
| 基线 ID | `PR2026-10-D-L125` |
| 多头 | 冻结 H5 1.25x + LS22 单龙头极端涨幅减半 |
| 空头 | 冻结 LS12 BTC-200D 双空头 regime router |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| gross | target/hard total 1.50x；short <=0.25x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS22 单独已经在四档成本上提高终值、Sharpe 和回撤，但 45 个月初路径只通过 37/45，主要拖累来自
2024-03 SHIB 连续被减半。LS12 空头 router 在 20bps 有明显增量，但 100bps 略低于 L125。两者修改的
是不同层：

- LS22 只改变 H5 多头最大持仓的极端涨幅减仓；
- LS12 只改变空头 sleeve 的 regime、funding、stop 和 gross 使用。

LS23 检验这两个已冻结机制的组合是否能同时保留多头利润保护、空头收益和 100bps 成本生存性。
这不是对 LS22 阈值或 LS12 参数的扫描。

## 1. 冻结构造

```text
long_base = frozen H5 1.25x
long_trimmed = LS22 profit lock on long_base
short_targets = frozen LS12 router (bear weak4 / non-bear funding exit)
combined = long_trimmed + cash-budgeted short_targets
max_total_gross = 1.50x
```

- LS22：最大多头腿的 21D trailing return >=100% 时减半，释放权重留现金；
- LS12：BTC <200D 做空 PIT Top20 14D 最弱四币；BTC >=200D 做 21D funding-top-tercile 的
  H5 退出币空头；
- short 仍只用未使用 gross，目标总 gross <=1.50x；
- 20% short stop、50% long/short buffer、missing-mark carry 3h 和 T+1 +3h 全部沿用；
- 不扫描组合权重、short 权重、stop、regime 窗口、profit-lock 阈值或再分配规则。

## 2. 预注册门槛

1. 20bps 终值 > L125；
2. 20bps Sharpe >= L125；
3. 20bps MDD <= L125 +5pp；
4. 主样本 0 次强平；
5. 2/20/50/100bps 终值和 Sharpe 均高于同成本 L125；
6. 100bps MDD <=50%；
7. 3x short-adverse 0 强平且 MDD <=50%；
8. 删除任一最佳年份后终值仍高于同成本 L125；
9. 365 天滚动最差 >= L125；
10. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
11. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过基线，12/12 MDD 5pp；
12. 单资产空头贡献 <=50%，前 3 <=80%；
13. observed gross <=1.50 且无 gross breach hour；
14. PBO/CSCV <=0.50，White Reality Check p <=0.05；
15. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
16. 12 个月真实 OOS 未满前最高只能 provisional。

## 3. 失败后动作

如果 LS23 失败：

- 不扫描 profit-lock 阈值、short 权重、组合权重、stop、regime 窗口或再分配；
- 将 LS22 和 LS12 分别保留为已记录的孤立机制；
- 提出新的独立信息源或新的风险层，并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS23-H5-PROFIT-LOCK-REGIME-SHORT \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_profit_lock_regime_short
```

## 5. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
