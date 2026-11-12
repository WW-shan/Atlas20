# Atlas20 候选：LS23 利润保护跳过 7D 转负的减仓

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已预注册；主样本评估中；不接实盘 |
| 候选 ID | `PR2026-11-LS51-H5-LS23-PROFITLOCK-SKIP7DNEG` |
| 基线 | LS23；LS44 |
| 机制 | LS22 的 21D>=100% 单龙头减半保持不变；但如果该龙头自己的 7D trailing return <0，则不执行这次减半，保留原 H5 权重；7D 为正或缺失时仍按 LS22 半仓 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；missing mark carry 3h；20% short stop；hard total gross 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS44 已经检验过相反方向：21D 极端上涨且 7D 转负时把龙头全部退出，结果 20bps 终值和 Sharpe
低于 LS23。这说明“7D 转负”并不足以证明剩余的一半应继续减仓。LS51 因此做更保守的反事实：
只在 7D 转负时**不执行 LS22 的半仓减半**，保留完整龙头；7D 非负时仍执行原来的半仓。

```text
if leader 21D trailing return >= 100%:
    if leader 7D trailing return < 0:
        keep full leader weight
    else:
        leader *= 0.5
```

LS12 空头 router、成本、stop、gross 和 H5 其他规则不变。该候选不新增空头，不改变 H5 选币，
也不使用未来价格。

## 1. 诊断依据

LS44 的 9 次 7D 转负事件中，完整退出降低了 MDD 约 0.78pp，但终值下降约 2.25%、Sharpe 下降
0.0087；说明这些事件并非稳定继续下跌。LS51 检验同一事件状态下的另一种动作：不削减可能仍
有右尾的龙头，而不是把风险全部移走。

## 2. 验收标准

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

若主样本不通过，记录为 rejected；不扫描 5D/10D/14D、阈值、scale 或再分配。后续继续研究
其他利润保护和反手空头机制。

## 3. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS51-H5-LS23-PROFITLOCK-SKIP7DNEG \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_skip7dneg
```

研究输出不是订单，也不是实盘批准。
