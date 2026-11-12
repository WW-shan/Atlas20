# Atlas20 候选预注册：LS23 利润保护权重再分配

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 已评估，provisional；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS42-H5-LS23-PROFITLOCK-REDISTRIBUTE` |
| 基线 | L125；LS23 |
| 基础 book | 冻结 LS23：H5 1.25x 利润保护 + LS12 双空头 router |
| 新机制 | LS22 减半龙头后，把释放权重按现有相对权重分配给同一事件的其他 H5 多头，单币上限 60% NAV |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；short stop 20%；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS22/LS23 的利润保护在单一龙头 21D trailing return >=100% 时把该腿减半，并把释放权重留在
现金。这个规则降低了集中度和回撤，但也把 book 的一部分主动暴露变成现金。LS40 已经证明，对正常
H5 权重做逆波动率重分配会破坏 sleeve 共识 alpha；本试验不改变任何资产的入场资格，也不做风险
模型，只处理利润保护本来就会释放的那部分权重。

LS42 把释放权重分给**同一事件里已经持有的其他 H5 资产**，保持这些资产之间的相对权重，并沿用
LS18 已使用的 60% NAV 单币上限。若没有其他持仓或上限挡住，剩余仍留现金。这样不会把低波动或
外部资产塞进 book，也不会增加事件原始 gross。

## 1. 冻结构造

```text
at each H5 long target event:
  leader = largest target-weight asset
  if leader 21D trailing return >=100% and leader_weight >=0:
      freed = leader_weight * (1 - 0.5)
      leader_weight = leader_weight * 0.5
      recipients = other positive target-weight assets
      allocate freed pro-rata to recipients' existing relative weights,
        capped at 0.60 NAV per asset
      unallocated remainder stays in cash
  else: unchanged

then combine with frozen LS12 dual-short router and all existing risk controls.
```

- 不新增资产，不改变 H5 选币；
- 不把释放权重分给空头、现金以外的资产或 LS12 short sleeve；
- 单币上限 60% NAV，沿用 LS18 的参数来源；
- H5 1.25x、21D/100%/0.5 profit lock、LS12 router、20% stop、50% buffers 和 1.50x hard gross 不变；
- 不扫描 21D/100%/0.5、60% cap、rebalance 或 allocation 方法。

## 2. 预注册门槛

研究价值（20bps，LS23 为 incumbent）：

1. LS42 终值 >= LS23 的 61.9150x；
2. Sharpe >= LS23 的 1.9448；
3. MDD 不得比 LS23 的 -39.84% 恶化超过 5pp，即不差于 -44.84%。

成本与尾部：

4. 主样本 0 次强平；
5. 2/20/50/100bps 终值和 Sharpe 均 >= 同成本 LS23，且均高于同成本 L125；
6. 100bps 终值 > LS23 的 15.5037x、Sharpe > 1.3745、MDD <=50%；
7. 3x short-adverse funding 0 强平且 MDD <=50%；
8. observed gross <=1.50 且 gross breach hour = 0。

稳健性：

9. 删除任一最佳年份后终值仍高于 L125；
10. 365 天滚动最差 >= L125 的 0.7325x；
11. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
12. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过 L125，12/12 MDD 5pp；
13. 单资产空头贡献 <=50%，前 3 <=80%；
14. PBO/CSCV <=0.50，White Reality Check p <=0.05；
15. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
16. 12 个月真实 OOS 未满前最高只能 provisional。

任一 20bps 主收益/Sharpe/MDD 门槛失败，LS42 不得因为“提高资金使用率”而保留为实盘候选。

## 3. 失败后动作

若 LS42 失败，停止 LS22 释放权重的再分配家族，不扫描 cap、redistribution 权重、再平衡频率或
只对部分事件分配。保留 LS23 作为 incumbent，不修改实盘。若通过主样本，仍需完成成本档、funding
stress、路径、冷启动、PBO/RC/DSR 和 12 个月真实 OOS。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS42-H5-LS23-PROFITLOCK-REDISTRIBUTE \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_redistribute
```

## 5. 状态

- 预注册：是；
- 正式运行：是（2022-01-01 → 2026-09-21；2/20/50/100bps；3x short-adverse funding）；
- 稳健性：删除最佳年份、365D rolling、45 个路径切片、12 个 cash-start 引擎起点全部通过；
- 多重检验：PBO 0.2132；RC zero p=0.003996、BTC p=0.009990；Top20/2022 DSR 0.973375、
  all-project DSR 0.961571；
- 51 天 shadow OOS：zero **0.9220x / -0.7874 / -17.47%**，Bitget exact
  **0.9183x / -0.8405 / -17.65%**；均落后 LS23 与 L125，12 个月门槛仍 pending；
- 结论：当前最强的样本内再分配版本，但真实 OOS 尚不支持 promotion，保持 provisional；
- 实盘：否；
- 修改当前实盘：否。

报告：`reports/derivatives_track_h5_ls23_profitlock_redistribute/report.md`。
机器可读门禁：`reports/derivatives_track_h5_ls23_profitlock_redistribute/PR2026-11-LS42-H5-LS23-PROFITLOCK-REDISTRIBUTE/gate_audit.json`。
