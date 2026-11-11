# Atlas20 无杠杆多空候选 LS2：H5 - 月频板块轮动空头

日期：2026-11-11  
候选：`PR2026-11-LS2-H5-MONTHLY-SECTOR`  
状态：**rejected（研究失败）**  
实盘：**不接；H5 现有多头配置不变**

## 一、结论

20bps 正式结果为：

- H5 基线：**21.3487x / Sharpe 1.7361 / MDD -33.36%**
- LS2 候选：**6.1748x / Sharpe 1.2122 / MDD -30.13%**

候选在所有成本档都显著低于基线，且 Broker 观测 gross 超过硬上限：

1. **20bps 终值和 Sharpe 失败**：候选 6.1748x，基线 21.3487x。
2. **双边目标 gross 被正确压到 0.95，但观测 gross 仍漂移到 1.2318x**：主样本出现 `observed gross > 1.00`，按预注册规则直接失败。
3. **100bps MDD = -52.77%**，越过 50% kill line。
4. **365 天滚动最差 = 0.7671x**，低于基线 0.7970x。
5. **45/45 月初后续路径切片的终值和 Sharpe 都低于基线**。
6. **全项目 DSR = 0.4634**，远低于 0.95。

所以 LS2 立即判定为 **rejected**。不允许通过把空头权重从 1.0 降到 0.2/0.5、改 stop、改 buffer、改月频为双周、改板块数或改 gross 定义来救参。

## 二、为什么这个试验仍然值得记录

LS1 失败后，研究问题变成：

> 是否存在一个低换手、来自旧负收益长策略的空头，能够在无杠杆和 total gross 约束下提高 H5 的收益，而不是像 LS1 一样依赖 2023 和高成本下消失的优势？

LS2 选择的旧长策略是：

```text
TOP20_SECTOR_top3_monthly_bull__none
```

它在 `reports/no_leverage_ablation_v2/` 中的历史记录为：

| 指标 | 长策略 |
|---|---:|
| 总收益 | -65.07% |
| Sharpe | -0.455 |
| MDD | -73.94% |
| 年化换手 | 1.747 |
| 平均 gross | 7.18% |

预注册前的只读日收益反向诊断看起来很好（H5 19.53x → 线性反向约 37.78x），但正式生产引擎否定了它。这正是为什么不能用“负收益策略直接反做”作为验证结论：空头止损、保证金、双边 gross、持仓漂移、funding 和真实执行会把线性诊断完全改写。

## 三、冻结构造

```text
w_raw = 1.0 * w_H5
      - 1.0 * w_TOP20_SECTOR_top3_monthly_bull__none
```

| 项目 | 冻结值 |
|---|---|
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| 日收益行数 | 1,724 |
| H5 权重 | 1.0x |
| 月频板块空头 | 1.0x 旧长策略目标 |
| 板块策略 | `TOP20_SECTOR_top3_monthly_bull` |
| 频率 | monthly |
| regime | bull_only |
| 板块数 | 3 |
| overlay | none |
| total gross 口径 | `long + short` |
| target total gross | 0.95 |
| hard total gross | 1.00 |
| long buffer | 0.75 |
| short buffer | 0.50 |
| 空头 adverse mark stop | 20% |
| 执行 | T+1 UTC +3h |
| 成本 | 2 / 20 / 50 / 100bps |
| funding | Binance proxy + `skip`；另跑 3x short-adverse |
| mark | Bitget mark，缺失 carry 最多 3 小时 |

预注册：

- Spec：`docs/superpowers/specs/2026-11-11-monthly-sector-short-design.md`
- `spec_sha256`：`27c9e78c38d3fd7ba07d34f59444aa8bbd3887d478ae9ed2322f9ffb8932423d`
- `registration_sha256`：`e9216eac0210aa7d594c9b14ff4a0dfbfc568d05c0867593e6d9e117995bd790`

## 四、20bps 主口径

| 指标 | H5 基线 | LS2 候选 |
|---|---:|---:|
| 终值 | **21.3487x** | 6.1748x |
| CAGR | **91.26%** | 47.06% |
| Sharpe | **1.7361** | 1.2122 |
| 最大回撤 | -33.36% | **-30.13%** |
| 强平 | 0 | 0 |
| 空头开仓 episode | 0 | 137 |
| 空头 stop | 0 | 47 |
| 最大 unscaled target total gross | 1.0000x | 2.0000x |
| 最大 scaled target total gross | 0.9500x | 0.9500x |
| 平均 scaled target total gross | 0.4561x | 0.8193x |
| 平均 scaled target net gross | 0.4561x | 0.6930x |
| **最大观测 Broker gross** | 0.9568x | **1.2318x（失败）** |
| 平均观测 Broker gross | 0.2371x | 0.4159x |
| 费用总额 | 0.8830 | 0.6811 |
| funding 净额 | -0.3416 | +0.0842 |

候选的 MDD 略好于基线，但这是靠大幅降低 H5 收益换来的，不是可接受的收益提升。空头腿有 137 次开仓、47 次 stop，说明这个“低换手长策略反向”在衍生品 stop 和逐小时 mark 下仍然产生较高的尾部换手。

## 五、双边 gross 与观测漂移

目标层：

| 指标 | 候选 |
|---|---:|
| 最大 unscaled long gross | 1.0000x |
| 最大 unscaled short gross | 1.0000x |
| 最大 unscaled total gross | 2.0000x |
| 最大 scaled total gross | 0.9500x |
| 需要缩放的 target events | 450 / 579 |

也就是说，组合器确实先按 `long + short <= 0.95` 缩放了多空两侧，没有重现 LS1 的目标层 gross bug。但实际逐小时持仓在两次目标事件之间漂移，观测 Broker gross 达到 **1.2318x**。预注册要求主样本任何一小时出现 `observed gross > 1.00` 即失败，故该候选不能通过风险门槛。

这不是可以通过“目标层 0.95”轻描淡写的账面问题：在 1.0x 空头 + 20% stop + 月频目标下，实际持仓会反复穿越 1.0 gross。若未来重新设计，必须加入逐小时 gross guard 或在目标层预留更大的漂移缓冲。

## 六、成本压力

| 成本 | 基线终值 | 候选终值 | 基线 Sharpe | 候选 Sharpe | 基线 MDD | 候选 MDD | 最大候选观测 gross |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 25.6692x | 7.9019x | 1.8277 | 1.3533 | -31.41% | -27.43% | 1.2314x |
| 20bps | 21.3487x | 6.1748x | 1.7361 | 1.2122 | -33.36% | -30.13% | 1.2318x |
| 50bps | 15.6946x | 4.0904x | 1.5826 | 0.9774 | -36.59% | -38.79% | 1.2324x |
| 100bps | 9.3848x | 2.0544x | 1.3251 | 0.5877 | -41.92% | **-52.77%** | 1.2333x |

四个成本档全部失败；100bps 还额外越过 MDD kill line。

## 七、funding 压力

3x short-adverse funding（20bps；空头 adverse funding ×3，多头 funding 置零）：

| 指标 | 结果 |
|---|---:|
| 终值 | 5.2363x |
| Sharpe | 1.1183 |
| MDD | -34.61% |
| 强平 | 0 |
| 空头 stop | 47 |
| 最大观测 gross | 1.2329x |
| funding 净额 | -0.2545 |

没有强平，但 gross 仍超过 1.00，终值仍远低于基线；funding 仍是 Binance proxy。

## 八、年度与稳定性

### 8.1 年度收益

| 年份 | H5 基线 | LS2 候选 |
|---|---:|---:|
| 2022 | -15.74% | **+5.12%** |
| 2023 | **+201.14%** | +149.46% |
| 2024 | **+94.61%** | -4.53% |
| 2025 | **+112.35%** | +57.78% |
| 2026（至 09-20） | **+103.60%** | +56.32% |

候选只在 2022 年优于基线，2023–2026 全部落后。这不是稳定的收益提升，而是熊市对冲/牛市拖累。

### 8.2 最佳年份移除

候选最佳年份是 2023。删除 2023 后：

- 候选：2.4753x
- 基线：7.0894x

失败。

### 8.3 365 天滚动最差

| 候选 | 最差滚动 365 天 | 中位数 |
|---|---:|---:|
| H5 基线 | **0.7970x** | 2.1634x |
| LS2 候选 | 0.7671x | 1.5269x |

候选滚动最差更差，中位数也明显更低，失败。

### 8.4 月初起点

45 个“至少剩余 365 天”的月初后续路径切片：

- 候选终值高于基线：**0 / 45**
- 候选 Sharpe 高于基线：**0 / 45**
- 三项同时通过：**0 / 45**

预注册原本要求 12 个真实引擎启动重跑；由于主口径、gross、成本、年份和 45 个路径切片已经全部给出同一结论，本轮没有继续做高成本的 12 次重跑，报告明确记录这一执行偏差，不能把该门槛写成通过。

## 九、多重检验

统计使用同一 1,724 天共同样本。

| 项目 | 结果 | 门槛 | 判定 |
|---|---:|---:|---|
| PBO / CSCV | 0.1407 | ≤0.50 | 通过（但最常被选的是基线） |
| White Reality Check vs zero | p=0.003996 | ≤0.05 | 通过（最优候选是基线） |
| White Reality Check vs BTC | p=0.050949 | ≤0.05 | 失败（略高于门槛） |
| DSR，候选族 N=2 | 0.9907 | ≥0.95 | 仅 family 口径通过 |
| DSR，Top20/2022 N=6,142 | 0.5233 | ≥0.95 | 失败 |
| DSR，全项目 N=14,172 | 0.4634 | ≥0.95 | 失败 |

多重检验没有挽救任何东西：CSCV 的最常选中候选是 **H5_BASELINE**，不是 LS2；全项目 DSR 只有 0.4634。

## 十、失败后禁止动作

按预注册，不允许：

- 把空头权重从 1.0 降到 0.2/0.5；
- 把 20% stop 改成 10%/15%/25%/30%；
- 把 monthly 改成 biweekly/weekly；
- 把板块数 3 改成 2/4/5；
- 把 bull_only 改成 always_on；
- 改变 target total gross 或 hard gross 定义；
- 只报 2022 年正收益；
- 用 H5 基线的偏高 gross 来为 LS2 的 1.23x 观测 gross 开脱。

## 十一、最终判定

**LS2 rejected。**

这次结果说明：

1. “负收益长策略直接反向”不能当作 alpha；线性日收益反向的诊断严重高估了可执行结果。
2. 低换手并不自动带来高成本鲁棒性；在 1.0x 空头、20% stop 和月频目标下，stop 与 gross 漂移仍然很重。
3. 先把目标层 gross 压到 0.95，并不等于实际小时级 gross 不超过 1.00；今后任何多空候选都必须在 runner 中加入逐小时 gross guard，或预留足够的漂移缓冲。
4. H5 仍是唯一实盘配置；LS2 不接执行器、不接 Telegram、不修改 H5。

完整明细：

- `cost_comparison.csv`
- `returns_20bps.csv`
- `robustness/yearly_returns.csv`
- `robustness/best_year_removal.csv`
- `robustness/rolling_worst.csv`
- `robustness/monthly_start_slices.csv`
- `multiple_testing/summary.json`
- `multiple_testing_project/deflated_sharpe.csv`
- `PR2026-11-LS2-H5-MONTHLY-SECTOR_cost20_proxy/target_gross.csv`
- `PR2026-11-LS2-H5-MONTHLY-SECTOR_cost20_proxy/trades.csv`
