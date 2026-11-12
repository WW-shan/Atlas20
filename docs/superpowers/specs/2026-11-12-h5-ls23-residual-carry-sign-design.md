# Atlas20 候选预注册：LS23 优先 + true-carry residual sleeve

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS35-H5-LS23-RESIDUAL-CARRY-SIGN` |
| 基线 | L125；LS23；LS33 为高收益但高成本对照 |
| 基础 book | 冻结 LS23：H5 1.25x 利润保护 + LS12 双空头 router |
| 新增 sleeve | LS31 carry 的 true-carry 子集：long funding<0，short funding>0 |
| 预算 | LS23 优先；carry 只用剩余、非重叠 gross；hard total gross 1.50x |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；short stop 20%；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS33 在 20bps 为 **80.6764x / 2.0566 / -39.19%**，但 100bps 为
**11.8172x / 1.2648 / -52.87%**，低于 LS23 的 15.5037x / 1.3745 / -49.48% 并越过 50% MDD
kill line。LS34 证明只降低空头换手会让 alpha 损失大于成本节省。

只读归因显示 carry 空头约 **99.7%** 的时间是正 funding，而 carry 多头只有约 **78.8%** 的时间
是负 funding；2024 年只有约 64.9%。LS33 的 long carry 中，正 funding 腿贡献了部分收益，但也
增加了换手和不利 funding 暴露。

LS35 因此保留 exact lowest/highest 2 ranking，只加一个零阈值的经济条件：

> long carry 必须 funding<0，short carry 必须 funding>0；不足 2 个合格腿时持有更少或现金，
> 不把不合格腿替换成负 carry 资产。

这不是扫描阈值；0 是 carry 的定义边界。

## 1. 冻结构造

```text
base(D) = 冻结 LS23
carry_long(D) = lowest negative-funding assets, up to 2
carry_short(D) = highest positive-funding assets, up to 2
carry(D) = carry_long + carry_short
combined(D) = 冻结 LS33 residual-budget combiner
```

- funding score 仍为 7D mean settlement，min_settlements=3；
- 每腿 0.0625x NAV；不足两腿时 gross 自然降低，不重新分配到不合格资产；
- base 优先；carry 只使用 `1.50 - base_gross` 的剩余、非重叠 gross；
- long buffer 60%；short stop 20%；T+1 +3h；
- 不扫描 count、权重、lookback、min_assets、sign threshold、stop 或 buffer。

## 2. 预注册门槛

主门槛（20bps）：

1. LS35 终值 > LS23 的 61.9150x；
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

LS35 不要求 20bps 超过 LS33；LS33 已被 100bps 成本门拒绝。LS35 的目标是比 LS23 更强且在
四档成本上可接受。

## 3. 失败后动作

如果 LS35 的 20bps 不超过 LS23，或 100bps 低于 LS23 或 MDD 超过 50%，停止 true-carry 子集
家族，不扫描 sign threshold、count、weight、lookback、stop 或 buffer。保留 LS33 作为高收益
但高成本的研究资产，不修改实盘。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS35-H5-LS23-RESIDUAL-CARRY-SIGN \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_residual_carry_sign
```

## 5. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
