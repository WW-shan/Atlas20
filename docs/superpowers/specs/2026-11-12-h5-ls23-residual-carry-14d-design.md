# Atlas20 候选预注册：LS23 优先 + 14D rebalance residual carry

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS37-H5-LS23-RESIDUAL-CARRY-14D` |
| 基线 | L125；LS23；LS33 为 7D 高收益但高成本对照 |
| 基础 book | 冻结 LS23：H5 1.25x 利润保护 + LS12 双空头 router |
| 新增 sleeve | LS33 完整 market-neutral carry，只把 rebalance 从 7D 改为 14D |
| 预算 | LS23 优先；carry 只用剩余、非重叠 gross；hard total gross 1.50x |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；short stop 20%；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS33 的 7D residual carry 在 20bps 为 **80.6764x / 2.0566 / -39.19%**，但 100bps 为
**11.8172x / 1.2648 / -52.87%**。LS34/LS35/LS36 分别尝试了空头持有带、true-carry sign 和
short-only，均未修复 100bps。残差不是选币方向，而是 base LS23 在 100bps 已接近成本尾部，
任何持续 weekly carry 换手都会把组合推过门。

只读 rank persistence 审计（7D mean funding score 的跨期 rank 相关代理）：

| 跨期 | mean rank corr | median |
|---|---:|---:|
| 7D | 0.6655 | 0.6911 |
| **14D** | **0.5576** | **0.5766** |
| 21D | 0.5004 | 0.5102 |
| 28D | 0.4726 | 0.4893 |

14D 保留了一半以上的 rank 信息，同时把 rebalance 次数减半，因此是唯一预注册的低频候选。
不测试 21D/28D/其他频率。

## 1. 冻结构造

```text
base(D) = 冻结 LS23
carry(D) = LS33 7D mean funding carry，但每 14 天重新排名
carry_long = lowest 2, carry_short = highest 2, 每腿 0.0625x NAV
combined(D) = 冻结 LS33 residual-budget combiner
```

- funding lookback 仍为 7D，min_settlements=3，min_assets=8；
- exact lowest/highest 2，不使用持有带或 sign filter；
- base 优先；carry 只用剩余、非重叠 gross；
- long buffer 60%，short stop 20%，T+1 +3h；
- 不扫描 rebalance_days、count、weight、lookback、min_assets、stop 或 buffer。

## 2. 预注册门槛

主门槛（20bps）：

1. LS37 终值 > LS23 的 61.9150x；
2. Sharpe >= LS23 的 1.9448；
3. MDD 不得比 LS23 的 -39.84% 恶化超过 5pp，即不差于 -44.84%；
4. 主样本 0 次强平，observed gross <=1.50 且无 gross breach hour。

成本与稳健性：

5. 2/20/50/100bps 终值和 Sharpe 均高于同成本 L125；
6. 2/20/50/100bps 终值和 Sharpe 均不低于同成本 LS23；
7. 100bps 终值 > LS23 的 15.5037x，Sharpe > 1.3745，MDD <=50%；
8. 3x short-adverse 0 强平且 MDD <=50%；
9. 删除任一最佳年份后终值仍高于 L125；
10. 365 天滚动最差 >= L125 的 0.7325x；
11. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
12. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过 L125，12/12 MDD 5pp；
13. 单资产空头贡献 <=50%，前 3 <=80%；
14. PBO/CSCV <=0.50，White Reality Check p <=0.05；
15. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
16. 12 个月真实 OOS 未满前最高只能 provisional。

LS37 不要求 20bps 超过 LS33；LS33 已被 100bps 成本门拒绝。LS37 的目标是比 LS23 更强且
100bps 可接受。

## 3. 失败后动作

如果 LS37 的 20bps 不超过 LS23，或 100bps 低于 LS23 或 MDD 超过 50%，停止 carry 低频
rebalance 家族，不扫描 21D/28D 或其他频率。保留 LS33 作为高收益但高成本的对照，不修改实盘。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS37-H5-LS23-RESIDUAL-CARRY-14D \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_residual_carry_14d
```

## 5. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
