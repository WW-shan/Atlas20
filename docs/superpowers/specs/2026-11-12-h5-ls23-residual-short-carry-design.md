# Atlas20 候选预注册：LS23 优先 + 剩余 gross short-only carry

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS36-H5-LS23-RESIDUAL-SHORT-CARRY` |
| 基线 | L125；LS23；LS33 为完整双腿 carry 对照 |
| 基础 book | 冻结 LS23：H5 1.25x 利润保护 + LS12 双空头 router |
| 新增 sleeve | 只做 funding carry 的空头腿：highest positive 7D funding 2 币 |
| 预算 | LS23 优先；carry 只用剩余、非重叠 gross；hard total gross 1.50x |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；short stop 20%；missing mark carry 3h |
| 成本 | 2 / 20 / 50 / 100bps |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS33 的完整 market-neutral carry 在 20bps 为 **80.6764x / 2.0566 / -39.19%**，但 100bps 为
**11.8172x / 1.2648 / -52.87%**，低于 LS23 15.5037x / 1.3745 / -49.48% 且越过 50% MDD。
LS34 的持有带和 LS35 的 true-carry 过滤都没有修复成本尾部。

只读归因显示 LS33 carry 空头几乎 100% 是正 funding，且短腿本身贡献了稳定 carry；long carry
贡献了收益但也增加了 gross、换手和尾部。LS36 做单腿分解：

> 保留 LS33 的空头 carry 腿（highest positive 7D funding 2 币，每腿 6.25% NAV），完全关闭
> long carry。这样 carry gross 从最多 0.25x 降到最多 0.125x，换手和 long tail 同时下降。

这不是扫描 count/weight；它固定沿用 LS33 的空头腿结构，只删除 long 腿。

## 1. 冻结构造

```text
base(D) = 冻结 LS23
carry_short(D) = highest positive-funding 2 names, 6.25% NAV each
carry_long(D) = none
combined(D) = 冻结 LS33 residual-budget combiner
```

- funding score = 7D mean settlement，min_settlements=3，min_assets=8；
- 只允许 funding>0 的空头腿；不足 2 个时持有更少或现金；
- base 优先；carry 只用 `1.50 - base_gross` 的剩余、非重叠 gross；
- long buffer 60%；short stop 20%；T+1 +3h；
- 不扫描 count、weight、lookback、min_assets、sign threshold、stop 或 buffer。

## 2. 预注册门槛

主门槛（20bps）：

1. LS36 终值 > LS23 的 61.9150x；
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

LS36 不要求 20bps 超过 LS33；LS33 已被 100bps 成本门拒绝。LS36 的目标是比 LS23 更强且
100bps 可接受。

## 3. 失败后动作

如果 LS36 的 20bps 不超过 LS23，或 100bps 低于 LS23 或 MDD 超过 50%，停止 short-only carry
家族，不扫描空头数量、权重、lookback、stop 或 buffer。保留 LS33 作为高收益但高成本的对照，
不修改实盘。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS36-H5-LS23-RESIDUAL-SHORT-CARRY \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_residual_short_carry
```

## 5. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
