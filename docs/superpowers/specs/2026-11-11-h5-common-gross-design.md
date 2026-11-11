# Atlas20 候选预注册：H5 selection-event common-gross 再平衡

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-12 |
| 状态 | 研究预注册；不接实盘；不修改当前实盘 `PR2026-10-D-L125-V2` |
| 候选 ID | `PR2026-11-LS20-H5-COMMON-GROSS` |
| 基线 ID | `PR2026-10-D-L125` |
| 基础 alpha | 冻结 LS12：H5 1.25x + BTC 200D 双空头 router |
| 新机制 | 持币集合不变时保留旧相对权重，只按新 target gross 统一缩放 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| gross | target/hard total 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS16 的 no-trade band 会跳过小调整，导致 gross 和相对权重同时滞后；它修复了 100bps，却让
2023-2024 的路径回撤恶化。LS20 只改变**交易维度**，不设置任何距离/threshold：

> 当 H5 的持币集合不变时，保留上一事件的币间相对权重，只把所有旧权重统一缩放到新的 target
> gross；当持币集合发生变化时，严格执行新的 H5 target。

这样：

- 选币变化始终立即执行；
- 总 gross / 风险预算变化始终立即执行；
- 只跳过“同一个币集合内部的 relative-weight tilt”。

这条机制与 LS16 的区别是结构性的：LS16 用 5% NAV 距离决定是否交易、会让 gross 滞后；LS20
没有距离参数，且永远保持当前 target gross。

## 1. 换手审计

H5 long 目标事件：

| 项目 | 数值 |
|---|---:|
| 总事件 | 542 |
| 集合变化事件 | 208 |
| 集合不变事件 | 334 |
| long target L1 turnover | 129.7632x |
| same-set L1 turnover | 59.2774x（45.68%） |
| same-set common-gross 部分 | 39.0910x |
| same-set relative-tilt 部分 | 32.2448x |

两部分有方向重叠，不能相加解释总 turnover；但 same-set relative tilt 的规模足以值得一次正式试验。

## 2. 冻结构造

```text
for each H5 long target event D:
    if selected_set(D) != selected_set(previous):
        adjusted(D) = target(D)                    # exact selection change
    else:
        adjusted(D) = previous_adjusted * target_gross(D) / previous_adjusted_gross
```

- first event 使用原始 H5 target；
- 若 target gross 为零，集合变化到 cash，必须清仓；
- H5 选币、3 日相位、BTC gate、dispersion/volatility scaling 的**总 gross**不变；
- LS12 bear/non-bear 空头 router、20% short stop、buffer、missing-mark 和 gross cap 不变；
- T+1 UTC +3h；
- funding 主口径 Binance proxy/skip。

## 3. 预注册门槛

1. 20bps 终值 > L125；
2. 20bps Sharpe >= L125；
3. 20bps MDD <= L125 +5pp；
4. 主样本 0 次强平；
5. 2/20/50/100bps 终值和 Sharpe 均高于同成本 L125；
6. 100bps MDD <=50%；
7. 3x short-adverse 0 强平且 MDD <=50%；
8. 删除任一最佳年份后终值仍高于同成本 L125；
9. 365 天滚动最差 >= L125；
10. 45 个已保存收益路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
11. 12 个真实引擎月初冷启动中至少 10/12 终值和 Sharpe 胜过基线，12/12 MDD 5pp；
12. 单资产空头贡献 <=50%，前 3 <=80%；
13. observed gross <=1.50 且无 gross breach hour；
14. PBO/CSCV <=0.50，White Reality Check p <=0.05；
15. Top20/2022 与全项目 DSR >=0.95 才可 promotion；
16. 12 个月真实 OOS 未满前最高只能 provisional。

## 4. 失败后动作

如果 LS20 失败：

- 不扫描 lookback、确认天数、阈值、只多头/只空头、不同 gross scaling 或 selection 定义；
- 停止 common-gross 家族；
- 提出机制不同的新候选并重新预注册；
- 不修改当前实盘 `PR2026-10-D-L125-V2`。

## 5. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS20-H5-COMMON-GROSS \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_common_gross
```

## 6. 状态

- 预注册：是；
- 正式运行：否；
- 实盘：否；
- 修改当前实盘：否。
