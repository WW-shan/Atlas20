# Atlas20 候选预注册：LS23 优先 + 剩余 gross funding carry（空头持有带）

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS34-H5-LS23-RESIDUAL-CARRY-SHORTHOLD` |
| 基线 | L125；LS23；LS33 |
| 多头 | 冻结 H5 1.25x + LS22 单一龙头利润保护 |
| 基础空头 | 冻结 LS12 BTC-200D 双空头 router，总空头 <=0.25x |
| 新增 sleeve | LS31 carry，但只对空头腿使用 2x entry-count 持有带 |
| 预算 | LS23 优先；carry 只用剩余、非重叠 gross；hard total gross 1.50x |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；short stop 20%；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS33 的 20bps 为 **80.6764x / 2.0566 / -39.19% / 0 强平**，但 100bps 为
**11.8172x / 1.2648 / -52.87%**，低于 LS23 的 15.5037x / 1.3745 / -49.48% 并越过 50% MDD
kill line。失败点是 carry 换手成本，不是方向或 residual budget。

LS32 的双边持有带把 carry target cumulative L1 change 从 70.5x 降到 48.875x，但让 DOT long
多留到 -63% 的强平边界，说明 **long 腿不能用滞后排名退出**。同时 LS30/LS31 的换手统计显示，
空头 name changes 为 688，高于多头 440；空头已有 20% adverse mark stop 作为尾部保护。

LS34 因此只改变空头腿的持续性：

> 空头已有腿仍在最高 4 名内时继续持有，跌出最高 4 才替换；多头腿始终按最低 2 名精确退出。
> 不扫描持有带宽度、空头数量、权重、funding lookback 或 stop。

## 1. 冻结构造

```text
base(D) = 冻结 LS23
carry_candidates(D) = 冻结 LS31 7D funding carry
carry_long(D) = lowest 2 exact
carry_short(D) = 最高 4 名内保留已有空头腿；否则替换为 highest 2
carry(D) = carry_long + carry_short
combined(D) = 冻结 LS33 residual-budget combiner
```

- 多头不持有旧排名，必须仍在 lowest 2，否则当周退出；
- 空头持有带宽度为 `2 × count = 4`，即已存在的空头只要仍在最高 4 名就保留；
- 空头新开仓仍只选 highest 2；short stop 20% 不变；
- 其余规则完全继承 LS33：base 优先、重叠资产移除、`1.50 - base_gross` 缩放、
  long buffer 60%、T+1 +3h、hard gross 1.50x；
- 不扫描 hold_count、long/short 数量、权重、lookback、rank、min_assets、stop 或 buffer。

## 2. 预注册门槛

研究价值（20bps）：

1. LS34 终值 > LS33 的 80.6764x；
2. LS34 终值 > LS23 的 61.9150x；
3. Sharpe >= LS33 的 2.0566；
4. MDD 不得比 LS23 的 -39.84% 恶化超过 5pp，即不差于 -44.84%。

风险与成本：

5. 主样本 0 次强平；
6. 2/20/50/100bps 终值和 Sharpe 均高于同成本 L125；
7. 2/20/50/100bps 终值和 Sharpe 均不低于同成本 LS23；
8. 100bps 终值 > LS23 的 15.5037x；
9. 100bps Sharpe > LS23 的 1.3745；
10. 100bps MDD <=50%；
11. 3x short-adverse 0 强平且 MDD <=50%；
12. observed gross <=1.50 且无 gross breach hour。

稳健性：

13. 删除任一最佳年份后终值仍高于 L125；
14. 365 天滚动最差 >= L125 的 0.7325x；
15. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
16. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过 L125，12/12 MDD 5pp；
17. 单资产空头贡献 <=50%，前 3 <=80%；
18. PBO/CSCV <=0.50，White Reality Check p <=0.05；
19. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
20. 12 个月真实 OOS 未满前最高只能 provisional。

## 3. 失败后动作

如果 LS34 的 20bps 终值不超过 LS33，或 100bps 任一门槛失败，停止 residual-carry 空头持有带
家族，不扫描 hold_count 3/5/6/8、long/short 数量或 stop。保留 LS33 作为已观察的 residual-carry
研究资产，不修改实盘。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS34-H5-LS23-RESIDUAL-CARRY-SHORTHOLD \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_residual_carry_shorthold
```

## 5. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
