# Atlas20 候选预注册：H5 集中度条件利润保护 + LS12 空头

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS29-H5-CONCENTRATION-PROFIT-LOCK-REGIME-SHORT` |
| 基线 | LS23（当前最强研究候选）和 L125 |
| 多头 | 冻结 H5 1.25x；仅当最大多头腿权重 >=25% NAV 且 21D trailing return >=100% 时减半该腿 |
| 空头 | 冻结 LS12 BTC-200D 双空头 router |
| 总预算 | long 1.25x；short <=0.25x；hard total gross 1.50x |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；20% short stop；50% buffer；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS22 的利润保护对“任何最大权重腿”生效，即使该腿只占 NAV 的 6%–20%；这在 2024 年
SHIB 事件中多次削减了一个本来可以继续复利的集中龙头。LS25 的状态化版本又因为锁定过久而
失去右尾，LS26 与 LS22 等价。

LS29 不改变 21D/100%/0.5 三个已有参数，只增加一个**集中度条件**：只有当最大腿本身已经达到
25% NAV 时才认为它构成组合集中风险并执行减半。低于 25% 的最大腿仍可能极端上涨，但它不是
组合的主要风险来源，保留其右尾。25% 是 NAV 的四分之一，也是 H5 多 sleeve 结构下一个资产
覆盖约三个 sleeve 的自然集中度节点；不在结果后扫描 20/30/35%。

## 1. 冻结构造

```text
long = frozen H5 1.25x
leader = argmax(long)
if leader_weight >= 0.25 * NAV and 21D_return(leader) >= 100%:
    leader_weight *= 0.50
    freed weight stays cash
short = frozen LS12 router, funded only by unused gross, <=0.25x
combined = cash-budget(long_trimmed, short, max_total_gross=1.50)
```

- 选币、H5 相位、BTC/宽度/离散度闸门、空头 router、20% stop、50% buffer、gross cap 全部不变；
- 不在减半后向其他币再分配；
- 不扫描 25% 门槛、21D lookback、100% 阈值、50% scale 或空头权重；
- 不使用未来价格或当前 Top20 回填。

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

如果 LS29 的 20bps 主门槛或成本门槛失败，停止集中度条件利润保护家族，不扫描 20/30/35% 或
其他减半规则；保留 LS22/LS23 结果并继续研究新的独立信息源或风险层。

不修改当前实盘 `PR2026-10-D-L125-V2`。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS29-H5-CONCENTRATION-PROFIT-LOCK-REGIME-SHORT \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_concentration_profit_lock
```

## 5. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
