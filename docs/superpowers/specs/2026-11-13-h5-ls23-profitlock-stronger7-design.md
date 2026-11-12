# Atlas20 候选预注册：LS23 利润保护只向更强 7D 持有者再分配

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已评估，provisional；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS43-H5-LS23-PROFITLOCK-STRONGER7` |
| 基线 | L125；LS23；LS42 仅作机制对照 |
| 基础 book | 冻结 LS23：H5 1.25x 利润保护 + LS12 双空头 router |
| 新机制 | LS22 减半龙头后，只把释放权重分给 7D trailing return **严格强于被减半龙头**的同一事件既有 H5 多头；没有合格接收者则留现金 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；short stop 20%；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS42 把利润保护释放的权重按既有相对权重分给同一事件的所有正权重 H5 多头。主样本内它确实提高
终值和 Sharpe，但 2026-09-22 → 2026-11-11 的 shadow 窗口里，LS42 把 `NEAR` 减半释放的权重
主要分给 `ZEC`；随后 `ZEC` 明显下跌而 `NEAR` 保持强势，导致 LS42 在该窗口落后 LS23 和 L125。
这不是“再分配一定错误”，而是“不能把已实现的风险预算机械地转给相对更弱的持有者”。

LS43 因此只增加一个确认条件：

```text
recipient 7D return(D) > leader 7D return(D)     (strict)
```

7D 已经是冻结 H5 多周期信号中的最短现有 horizon，不是新阈值；没有扫描 5D/10D/14D，也没有
扫描收益差、分位数或排名带宽。

## 1. 运行前诊断（不作为独立 OOS）

只读诊断对 LS42 的利润保护事件计算了接收者篮子未来 21D 等权/权重收益：

| 样本 | 规则 | 再分配权重 | 接收者篮子平均未来 21D |
|---|---|---:|---:|
| 2022–2026 主样本 | 分给所有接收者 | 4.438 | +4.18% |
| 2022–2026 主样本 | 只分给 7D 为正者 | 4.072 | +6.68% |
| 2022–2026 主样本 | 只分给 7D 强于 leader 者 | 1.961 | +8.39% |
| 2026-09-22 → 11-11 shadow | 分给所有接收者 | 0.715 | **-19.05%** |
| 2026-09-22 → 11-11 shadow | 只分给 7D 为正者 | 0.406 | **-18.24%** |
| 2026-09-22 → 11-11 shadow | 只分给 7D 强于 leader 者 | 0.000 | 无分配，保留现金 |

诊断已经查看了当前 51 天 shadow，因此 **LS43 不能把这段窗口当作独立 12 个月 OOS**；它只能
用于失败诊断和机制压力测试。promotion 仍必须等待预注册后的新数据。

## 2. 冻结构造

```text
at each H5 long target event:
  leader = largest target-weight asset
  if leader 21D trailing return >=100%:
      leader_weight *= 0.5
      recipients = other positive target-weight H5 assets
      eligible = recipients where 7D return(recipient) > 7D return(leader)
      allocate freed weight pro-rata to eligible recipients' existing weights,
        capped at 0.60 NAV per asset
      any residual stays in cash
  else: unchanged
```

- 不新增资产，不增加事件原始 gross；
- 没有合格接收者时释放权重全部留现金；
- LS12 short router、20% short stop、50% buffers、1.25x H5 和 1.50x hard gross 不变；
- 不扫描 21D/100%/0.5、7D confirmation、60% cap、recipient 权重或 rebalance 频率。

## 3. 预注册门槛

1. 20bps LS43 终值 >= LS23 的 61.9150x；
2. Sharpe >= LS23 的 1.9448；
3. MDD 不得比 LS23 的 -39.84% 恶化超过 5pp，即不差于 -44.84%；
4. 主样本 0 次强平；
5. 2/20/50/100bps 终值和 Sharpe 均 >= 同成本 LS23，且均高于同成本 L125；
6. 100bps 终值 > LS23 的 15.5037x、Sharpe > 1.3745、MDD <=50%；
7. 3x short-adverse funding 0 强平且 MDD <=50%；
8. observed gross <=1.50x 且 gross breach hour = 0；
9. 删除任一最佳年份后终值仍高于 L125；
10. 365 天滚动最差 >= L125 的 0.7325x；
11. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
12. 12 个真实现金起点中至少 10/12 终值和 Sharpe 胜过 L125，12/12 MDD 5pp；
13. 单资产空头贡献 <=50%，前 3 <=80%；
14. PBO/CSCV <=0.50，White Reality Check p <=0.05；
15. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
16. 12 个月预注册后真实 OOS 未满前最高只能 provisional。

此外必须报告：LS43 相对 LS42 的终值、Sharpe、MDD、再分配 weight、现金 weight 和 OOS 差异。
LS42 不再作为独立 incumbent；如果 LS43 只在样本内超过 LS23、但预注册后 OOS 不改善，则保持
LS23 为当前最强实盘候选。

## 4. 失败后动作

若 LS43 失败，停止 LS22 释放权重的全部再分配家族，不扫描 7D 确认、收益差阈值、接收者数量、
cap、再平衡或只对部分事件分配。保留 LS23，不修改实盘；下一轮转向机制不同的新数据源或风险层。

## 5. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS43-H5-LS23-PROFITLOCK-STRONGER7 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_stronger7
```

## 6. 状态

- 预注册：是；
- 正式运行：是（2022-01-01 → 2026-09-21；2/20/50/100bps；3x short-adverse funding）；
- 主结果：20bps **66.6800x / 1.9667 / -40.134% / 0 强平**；四档成本均高于同成本 LS23、
  LS42 和 L125；100bps **16.4391x / 1.3932 / -49.775%**；
- 机制：57 次 trim，14 次存在 7D 强于 leader 的接收者；再分配 1.9606、留现金 7.2826；
- 稳健性：删除最佳年份、365D rolling、45/45 paths、12/12 cash-start、集中度、PBO/RC/DSR 全过；
- 诊断：当前 51 天 shadow 为预注册前已查看窗口，不构成独立 OOS；LS43 在该窗口无合格接收者，
  与 LS23 完全一致；
- 风险：删除 2024 后 LS43 低于 LS23 2.71%，增量集中于 2024；pre-2022 proxy MDD 比 LS23 差
  约 1.85–2.99pp；
- 结论：provisional；等待预注册后的新 12 个月 OOS，不 promotion；
- 实盘：否；
- 修改当前实盘：否。

报告：`reports/derivatives_track_h5_ls23_profitlock_stronger7/report.md`。
机器门禁：`reports/derivatives_track_h5_ls23_profitlock_stronger7/PR2026-11-LS43-H5-LS23-PROFITLOCK-STRONGER7/gate_audit.json`。
