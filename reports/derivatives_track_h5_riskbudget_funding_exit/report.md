# Atlas20 无杠杆多空候选 LS9：H5 连续未使用风险预算 + funding 退出空头

日期：2026-11-11
候选：`PR2026-11-LS9-H5-RISKBUDGET-FUNDING-EXIT`
状态：**rejected（研究失败）**
实盘：**不接；H5 现有多头配置不变**

## 一、结论

LS9 在每个 funding 合格的 H5 退出空头开仓时，用它当时可用的 H5 未使用 gross 预算定权：

`per-leg weight = 5% × max(0, 1 - post-exit H5 target long gross)`

20bps：

- H5 基线：**21.3487x / Sharpe 1.7361 / MDD -33.36%**
- LS9 候选：**23.8832x / Sharpe 1.7984 / MDD -33.54%**
- 最大 requested short gross：**0.1750x**
- 最大 observed gross：**0.9568x**
- 强平：0
- 空头 open / stop：49 / 8
- 空头权重出现 26 种不同取值，确认连续风险预算实际生效

LS9 通过成本、funding、gross、年度、最佳年份移除、45/45 路径切片、12/12 真实引擎冷启动、
集中度、PBO 和 Reality Check；仍有两个硬失败：

1. **365 天滚动最差 0.7865x，低于 H5 基线 0.7970x**；
2. **Top20/2022 DSR 0.9382、全项目 DSR 0.9156**，均低于 0.95。

因此判定 **rejected**，不进入实盘。

## 二、关键数据修复

首次 LS9 运行发现 H5 gross 序列使用 naive datetime，而空头 schedule 使用 UTC datetime。
成员判断失败后代码把 gross 当作 0，导致所有空头误用 5% 满额权重。该版本的 24.7348x 结果作废。

修复内容：

- `_long_gross_series` 统一把 H5 target/index 归一化到 UTC；
- 增加“naive H5 日期必须先归一化再做风险预算缩放”的回归测试；
- 修复后重跑全部成本档与 funding 压力。

修复后权重分布从“全部 0.05”变为 26 种取值，证明风险预算不再是 no-op。

## 三、预注册与机制

- Spec：`docs/superpowers/specs/2026-11-11-h5-riskbudget-funding-exit-design.md`
- registered spec hash：`d7c3f5f01bcd8231f4354ca0a196ebf56ce827fce741ae74899fb25bc7f6b22f`
- registration hash：`b37a27c5a6ba2742cb871b0290596f00aa745bdd751d5da96145821351269ceb`

冻结构造：

| 项目 | 值 |
|---|---|
| H5 多头 | 1.0x |
| 退出定义 | 前一个 H5 目标持有、当前目标完全退出 |
| funding rank | 7D 均值，PIT Top20 上三分之一，最少 5 个有效资产 |
| 持有期 | 21 个日历日 |
| 提前关闭 | H5 重新买入 |
| 单腿权重 | 5% × max(0, 1 − 开仓日 H5 target long gross)，开仓后固定 |
| stop | 20% adverse mark |
| gross | target 0.95，hard observed 1.00 |
| 执行 | T+1 UTC +3h |
| 成本 | 2/20/50/100bps |

## 四、成本压力

| 成本 | H5 终值 | LS9 终值 | H5 Sharpe | LS9 Sharpe | H5 MDD | LS9 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 25.6692x | **28.9016x** | 1.8277 | **1.8936** | -31.41% | -31.56% |
| 20bps | 21.3487x | **23.8832x** | 1.7361 | **1.7984** | -33.36% | -33.54% |
| 50bps | 15.6946x | **17.3705x** | 1.5826 | **1.6389** | -36.59% | -36.80% |
| 100bps | 9.3848x | **10.2023x** | 1.3251 | **1.3711** | -41.92% | -42.18% |

四档终值和 Sharpe 全部高于基线，100bps MDD -42.18% < 50%。

## 五、funding 压力

3x short-adverse funding：

| 指标 | 结果 |
|---|---:|
| 终值 | 25.4862x |
| Sharpe | 1.8299 |
| MDD | -33.62% |
| 强平 | 0 |
| stop | 8 |
| 最大 observed gross | 0.9564x |
| gross breach hours | 0 |
| funding 净额 | -0.0145 |

funding 压力通过；funding 仍是 Binance proxy，不是 Bitget 精确历史。

## 六、年度、最佳年份和滚动最差

| 年份 | H5 基线 | LS9 |
|---|---:|---:|
| 2022 | -15.74% | **-13.48%** |
| 2023 | +201.14% | **+204.10%** |
| 2024 | +94.61% | **+99.35%** |
| 2025 | +112.35% | **+119.77%** |
| 2026（至 09-20） | +103.60% | **+107.20%** |

删除最佳年份后：

| 删除年份 | H5 基线 | LS9 |
|---:|---:|---:|
| 2022 | 25.3369x | **27.6053x** |
| 2023 | 7.0894x | **7.8537x** |
| 2024 | 10.9698x | **11.9807x** |
| 2025 | 10.0538x | **10.8672x** |
| 2026 | 10.4858x | **11.5267x** |

全部通过。

365 天滚动最差：

| 候选 | 滚动最差 | 滚动中位数 |
|---|---:|---:|
| H5 基线 | **0.7970x** | 2.1634x |
| LS9 | 0.7865x | **2.2367x** |

候选滚动中位数更高，但最差窗口仍低于基线，硬失败。

## 七、路径切片与真实引擎冷启动

45 个已保存收益路径月初切片：终值、Sharpe、MDD 5pp 三项全部通过 **45/45**。

12 个真实引擎月度冷启动：

| 门槛 | 结果 |
|---|---:|
| 终值胜过 baseline | **12/12** |
| Sharpe 胜过 baseline | **12/12** |
| MDD 5pp | **12/12** |
| 0 强平 | **12/12** |
| observed gross <= 1.00 | **12/12** |

所有 24 个独立进程退出码为 0。

## 八、空头归因

49 个可配对 episode、18 个资产：

| 指标 | 结果 |
|---|---:|
| 正贡献 episode | 31 |
| 负贡献 episode | 18 |
| episode PnL 对开仓权益合计 | +11.3364% |
| 平均 | +0.2314% |
| 中位 | +0.1555% |
| 最差 episode | -1.0140% |
| 最好 episode | +3.1800% |
| 最大 adverse mark loss | **0.8762% NAV** |

资产集中度：

| 资产 | episode | 净贡献 | 占比 |
|---|---:|---:|---:|
| NEAR | 7 | +4.4404% | **39.17%** |
| Litecoin | 4 | +1.5144% | 13.36% |
| Uniswap | 1 | +1.4384% | 12.69% |
| 前 3 合计 | 12 | +7.3932% | **65.22%** |

单资产 39.17% < 50%，前 3 65.22% < 80%，集中度通过。

实际最大 adverse loss 0.8762% NAV，低于 5% 权重 × 20% stop 的名义 1.0% NAV 上限，但仍需披露
mark/gap 路径偏差。

## 九、多重检验

| 项目 | 结果 | 门槛 | 判定 |
|---|---:|---:|---|
| PBO / CSCV | **0.004329** | <=0.50 | 通过 |
| RC vs zero | **p=0.003996** | <=0.05 | 通过 |
| RC vs BTC | **p=0.014985** | <=0.05 | 通过 |
| DSR family N=2 | **0.999996** | >=0.95 | 仅 family 通过 |
| DSR Top20/2022 N=6,142 | **0.938229** | >=0.95 | **失败** |
| DSR 全项目 N=14,179 | **0.915567** | >=0.95 | **失败** |

## 十、最终判定

**LS9 rejected。**

通过：

- 20bps 收益、Sharpe、MDD、gross、0 强平；
- 四档成本和 Sharpe；
- 100bps MDD；
- 3x short-adverse；
- 所有年度和最佳年份移除；
- 45/45 saved-path starts；
- 12/12 real-engine starts；
- 集中度；
- PBO 和 RC。

失败：

- 365 天滚动最差 0.7865x < 0.7970x；
- Top20/2022 DSR 0.9382；
- 全项目 DSR 0.9156。

LS9 的连续风险预算提高了收益和 Sharpe，但没有修复最差路径。按预注册不得扫描 base weight、指数、
H5 gross 阈值或任何 funding/holding/stop/gross 参数。下一轮必须改成机制不同的新候选。

## 十一、复现与文件

```bash
.venv/bin/python scripts/run_h5_riskbudget_funding_exit_short.py --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_riskbudget_funding_exit

.venv/bin/python scripts/run_h5_riskbudget_funding_exit_short.py --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_riskbudget_funding_exit
```

关键文件：

- `returns_20bps.csv`
- `cost_comparison.csv`
- `funding_stress_summary.csv`
- `robustness/yearly_returns.csv`
- `robustness/best_year_removal.csv`
- `robustness/rolling_worst.csv`
- `robustness/monthly_start_slices.csv`
- `engine_monthly_starts/summary.csv`
- `multiple_testing/summary.json`
- `multiple_testing/reality_check_btc.csv`
- `multiple_testing_project/deflated_sharpe.csv`
- `PR2026-11-LS9-H5-RISKBUDGET-FUNDING-EXIT_cost20_proxy/short_episodes.csv`
- `PR2026-11-LS9-H5-RISKBUDGET-FUNDING-EXIT_cost20_proxy/short_asset_attribution.csv`
- `PR2026-11-LS9-H5-RISKBUDGET-FUNDING-EXIT_cost20_proxy/short_episode_summary.csv`

研究输出不是订单，也不是实盘批准；LS9 不接执行器，不修改 H5 账本。
