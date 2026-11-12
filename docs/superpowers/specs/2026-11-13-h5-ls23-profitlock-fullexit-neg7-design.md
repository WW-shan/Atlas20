# Atlas20 候选预注册：LS23 利润保护在 7D 转负时完全退出

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已评估，rejected at 20bps；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS44-H5-LS23-PROFITLOCK-FULLEXIT-NEG7` |
| 基线 | L125；LS23；LS42/LS43 仅作机制对照 |
| 基础 book | 冻结 LS23：H5 1.25x 利润保护 + LS12 双空头 router |
| 新机制 | LS22 触发时，如果被减半龙头自己的 7D trailing return < 0，则把该腿完全退出；否则维持原来的 0.5 scale |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；short stop 20%；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS22 在 21D 涨幅 >=100% 时把单一龙头减半，剩余一半继续承担趋势反转风险。只读事件审计显示，
57 次 trim 中，如果被减半龙头自己的 7D trailing return 已经转负，其后 21D 表现显著更差：

| 事件状态 | 次数 | 未来 21D 均值 | 中位数 | 正收益占比 |
|---|---:|---:|---:|---:|
| 7D < 0 | 9 | **-6.02%** | -4.49% | 33.3% |
| 7D >= 0 | 48 | **+0.87%** | -1.31% | 43.8% |

这不是新增阈值扫描：7D 已经是冻结 H5 信号中的最短 horizon。LS44 只检验一个不对称的利润保护：
**短线已经转负时不再保留一半，短线仍为正时继续沿用 LS22 的一半。**

当前 51 天 shadow 窗口此前已被用于诊断，因此它不能作为 LS44 的独立 12 个月 OOS；promotion 必须
等待预注册后的新数据。

## 1. 冻结构造

```text
at each H5 long target event:
  leader = largest target-weight asset
  if leader 21D trailing return >= 100%:
      leader_7D = price(D) / price(D-7) - 1
      if leader_7D < 0:
          leader_weight = 0
      else:
          leader_weight *= 0.5
      freed weight -> cash
  else: unchanged
```

- 不新增资产，不向其他资产再分配；
- 没有 7D 价格时 fail-safe 回到原来的 0.5 scale；
- LS12 short router、20% short stop、50% buffers、1.25x H5 和 1.50x hard gross 不变；
- 不扫描 5D/10D/14D、confirmation 阈值、scale 0.25/0.75、再分配或持有期。

## 2. 预注册门槛

1. 20bps LS44 终值 >= LS23 的 61.9150x；
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
12. 12 个真实 cash-start 中至少 10/12 终值和 Sharpe 胜过 L125，12/12 MDD 5pp；
13. 单资产空头贡献 <=50%，前 3 <=80%；
14. PBO/CSCV <=0.50，White Reality Check p <=0.05；
15. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
16. 预注册后 12 个月真实 OOS 未满前最高只能 provisional。

额外报告：full-exit 事件数、被完全退出权重、7D negative 与 positive 两个子样本的收益/回撤分解，
以及 LS44 相对 LS23/LS42/LS43 的逐年差异。若 LS44 的增量仍只来自单一年份，必须明确标注。

## 3. 失败后动作

若 LS44 失败，停止“极端涨幅 + 短周期 breakdown”全退家族，不扫描 confirmation window、阈值、
scale 或再分配。保留 LS23，不修改实盘；下一轮转向机制不同的新数据源或风险层。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS44-H5-LS23-PROFITLOCK-FULLEXIT-NEG7 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_fullexit_neg7
```

## 5. 状态

- 预注册：是；
- 正式运行：是（20bps 主样本）；
- 结果：**60.5213x / 1.9361 / -39.056%**，9 次 full exit、0 强平、0 gross breach；
- 判定：20bps 终值低于 LS23 61.9150x、Sharpe 低于 1.9448，主收益与 Sharpe 门槛失败；
  MDD 改善约 0.78pp，但不足以保留；
- 后续：不运行成本档、funding stress、路径、cash-start 或 PBO/RC/DSR；停止该家族；
- 实盘：否；
- 修改当前实盘：否。

报告：`reports/derivatives_track_h5_ls23_profitlock_fullexit_neg7/report.md`。
