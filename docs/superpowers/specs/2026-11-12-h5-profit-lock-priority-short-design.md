# Atlas20 候选预注册：H5 利润保护 + 优先级空头预算

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS28-H5-PROFIT-LOCK-PRIORITY-SHORT` |
| 基线 | LS23（当前最强研究候选）和 L125 |
| 多头 | 冻结 H5 1.25x + LS22 单龙头极端涨幅减半 |
| 优先空头 | 冻结 LS12 BTC-200D 双空头 router，先使用最多 0.25x |
| 额外空头 | 冻结 R6 14D bottom-quintile 4 币周频空头，只使用优先空头之后的剩余 gross |
| 总预算 | target/hard total gross 1.50x；逐小时 hard gross guard |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；20% short stop；50% short buffer；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS27 证明“把 LS12 和 R6 两个空头组件等权混合、允许 0.50x 请求短 gross”能提高 20bps 收益和
Sharpe，但换手和成本使 50/100bps 变差，并且目标贴住 1.50x 时会出现短暂 gross breach。

LS28 只改一个机制：**优先保留 LS23 的 LS12 空头，R6 bottom-four 只用 LS22 利润保护释放出来的
剩余 gross。** 这样：

- 正常满多头时，LS28 与 LS23 的空头预算一致，R6 不会抢走 LS12 的 0.25x；
- LS22 减半龙头后，释放的 gross 才进入 R6，不再长期持有第二套空头；
- 不扫描优先比例、bottom-N、stop、lookback 或 target gross。

## 1. 冻结构造

```text
long = LS22(H5 1.25x)
priority_short = frozen LS12 router, requested <=0.25x
extra_short = frozen R6 bottom-four, requested <=0.25x
available = 1.50 - long_gross
funded_priority = min(priority_short, available)
residual = 1.50 - long_gross - funded_priority
funded_extra = min(extra_short, residual)
combined = long - funded_priority - funded_extra
```

- 优先空头先分配，额外空头只能吃剩余 gross；
- 同资产短腿不得超过 0.25x NAV；
- 1.50x hard gross guard 逐小时检查；目标层不得通过提高 long 权重或空头权重绕过；
- 不改变 LS22 的 21D/100%/0.5 参数，不改变 LS12 的 200D/14D/7D/4 币/20% stop，不改变 R6
  的 14D/7D/4 币/20% stop/funding 规则；
- 不使用近期 sleeve 表现、资产类别或 regime 进行权重切换。

## 2. 预注册门槛

以 LS23 为 incumbent：

1. 20bps 终值 > LS23 的 61.9150x；
2. 20bps Sharpe >= LS23 的 1.9448；
3. 20bps MDD <= LS23 的 -39.84% + 5pp；
4. 主样本 0 次强平；
5. 2/20/50/100bps 终值和 Sharpe 均高于同成本 LS23；
6. 100bps MDD <= 50%；
7. 3x short-adverse 0 强平且 MDD <= 50%；
8. 删除任一最佳年份后终值仍高于同成本 LS23；
9. 365 天滚动最差 >= LS23 的 0.8551x；
10. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
11. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过 LS23，12/12 MDD 5pp；
12. 单资产空头贡献 <= 50%，前 3 <= 80%；
13. observed gross <=1.50 且无 gross breach hour；
14. PBO/CSCV <=0.50，White Reality Check p <=0.05；
15. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
16. 12 个月真实 OOS 未满前最高只能 provisional。

## 3. 失败后动作

如果 LS28 的 20bps 主门槛或成本门槛失败，停止该优先级组合，不扫描优先比例、额外空头权重、
stop、bottom-N 或 gross 阈值；记录结果并继续研究新的独立信息源或新的风险层。

不修改当前实盘 `PR2026-10-D-L125-V2`。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS28-H5-PROFIT-LOCK-PRIORITY-SHORT \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_profit_lock_priority_short
```

## 5. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
