# Atlas20 双边轮动第四轮预注册：Bottom-Quincile 空头篮子

| 项目 | 内容 |
|---|---|
| 状态 | 研究预注册；不接实盘 |
| 触发 | 第三轮单币最弱空头被 XRP 逼空淘汰；检验分散尾部是否能保留横截面机制 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| 多头底稿 | 冻结 H5 / `PR2026-10-D-L125` |
| 空头 | Top20 中 14D 收益最弱的 4 个币，等权，合计 0.25x |
| 再平衡 | 每 7 个自然日；信号 UTC 收盘，T+1 +3h |
| 数据 | Bitget mark；Binance funding proxy/skip，明确不是精确 Bitget 历史 |

## 0. 研究问题

第三轮 `PR2026-11-RS3-X-WEAK14` 在 2023-07-13 被 XRP 单币逼空触发强平。单币最弱空头不是
[S2] 所研究的长短因子实现，而是一个高度集中的尾部押注；[S2] 使用横截面分位组合，[S14]
则明确警告单一币可能主导结果。

因此本轮只检验一个**风险分散机制**：

> 将 Top20 的 bottom quintile（20 / 5 = 4 个最弱币）等权做空，总空头仍为 0.25x，是否能在
> 不靠单币逼空尾部的情况下保留横截面相对价值？

这不是对第三轮结果的参数救活：不改变 14D lookback、不改变 7D holding、不改变 0.25x 总空头，
也不扫 2/3/4/5 个币。`4` 来自 Top20 的五分位定义。

## 1. 冻结试验

| trial_id | 构造 | 空头选择 | 单腿权重 | 总空头 |
|---|---|---:|---:|---:|
| `PR2026-11-RS4-X-WEAK4` | H5 多头 ×1.25 + 4 币等权空头 | 14D 最弱 4 个可交易、非 H5 多头持仓 | 0.0625x | 0.25x |

只跑这一条。

## 2. 精确规则

```text
long_i,t = 1.25 × w_H5_i,t
eligible_t = PIT_CMC_Top20_t
              ∩ Bitget mark available at next execution
              ∩ not currently held long
rank_t = ascending 14D return among eligible_t
short_basket_t = first 4 names in rank_t
short_i,t = -0.25 / 4 = -0.0625   for i in short_basket_t
```

- 空头篮子每 7 个自然日按锚点重新选择；
- 若某币离开 Top20、失去 mark、或成为 H5 多头持仓，下一可执行时点退出；
- funding guard：每个空头最近 3 个结算点均值 `> -0.0002`；失败则不纳入该周期；
- 允许不足 4 个腿，但每腿固定 `0.0625x`，不把剩余权重集中到更少币；
- 主口径使用 Binance funding proxy + `skip`；3x short-adverse 只作为压力带。

## 3. 预注册门槛

与第三轮相同，不因篮子分散而放宽：

1. 20bps 终值 > 修正 L125 基线；
2. Sharpe ≥ 基线；
3. MDD ≤ 基线 + 5pp；
4. 主样本 0 次强平；
5. 50bps 终值 > 基线；
6. 100bps MDD ≤ 50%；
7. 3x short-adverse 0 次强平且 MDD ≤ 50%；
8. 移除 2022 后仍高于基线；
9. PBO/CSCV ≤ 0.5；
10. 报告年度、滚动最差、空头开仓次数、单腿最大贡献、最佳年份移除；
11. 真 OOS 不足 12 个月时最多 provisional，禁止接实盘。

## 4. 试验记账

新增 `PR2026-11-RS4-X-WEAK4`，`counts_as_trial=True`。不能把“篮子分散”当作降低门槛的理由；
若本轮仍失败，横截面单币/篮子空头线停止，不继续扫篮子大小。

## 5. 复现

```bash
.venv/bin/python scripts/run_derivatives_backtest.py \
  --trial-id PR2026-11-RS4-X-WEAK4 \
  --start-date 2022-01-01 --end-date 2026-09-21 \
  --cost-bps 20 --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_cross_sectional_basket_round4
```

## 6. 边界

- 不修改当前 H5 多头实盘；
- 不接空头执行；
- 不把 basket 的分散效果称为已验证 alpha；
- 若失败，下一阶段只考虑完全不同的机制（事件驱动或真正的 portfolio-level hedge），不再微调本线。

---

## 7. 第四轮结果（2026-11-10）

20bps：基线 40.2200x / 1.7330 / -40.6506%；`PR2026-11-RS4-X-WEAK4`
53.0245x / 1.8980 / -41.5294%，但有 **3 次强平**（2023-07-13 XRP、2024-12-03 TRON、
2026-08-22 XRP）。主口径硬失败，停止；不测试 50/100bps。
