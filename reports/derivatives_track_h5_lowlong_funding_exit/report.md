# Atlas20 无杠杆多空候选 LS8：H5 低多头 gross + funding 退出空头

日期：2026-11-11
候选：`PR2026-11-LS8-H5-LOWLONG-FUNDING-EXIT`
状态：**rejected（研究失败）**
实盘：**不接；H5 现有多头配置不变**

## 一、结论

LS8 只允许在 H5 退出后目标 long gross ≤ 0.50 时，对 7D funding 位于 PIT Top20 上三分之一的
H5 退出资产开 21 天空头。

20bps：

- H5 基线：**21.3487x / Sharpe 1.7361 / MDD -33.36%**
- LS8 候选：**22.8336x / Sharpe 1.7744 / MDD -33.52%**
- 最大 requested short gross：**0.1000x**
- 最大 observed gross：**0.9568x**
- 强平：0
- 空头 open / stop：37 / 5

LS8 在成本、funding、gross、年度、最佳年份移除、45/45 路径切片、12/12 真实引擎冷启动、
集中度、PBO 和 Reality Check 上通过；但：

1. **365 天滚动最差 0.7909x，低于 H5 基线 0.7970x**；
2. **Top20/2022 DSR 0.9302、全项目 DSR 0.9055**，均低于 0.95。

因此判定 **rejected**。

## 二、关键数据修复

此前一次 LS8 运行把 H5 gross 的 naive datetime 与 UTC schedule 日期直接比较，导致所有入场检查返回
false，并错误报告“0 激活”。修复 `_long_gross_series` 为 UTC 归一化后，LS8 实际产生 37 个空头。

因此旧结论“机制从未触发”作废；本报告和账本使用修复后的真实结果。该 bug 同时影响过 LS9，
两处副本都已修复并加入回归测试。

## 三、预注册与机制

- Spec：`docs/superpowers/specs/2026-11-11-h5-lowlong-funding-exit-design.md`
- registered spec hash：`f0798e30b37c903b0676a6f5c68157b24ca7d59eb8d39f08aa73ed7675928f1b`
- registration hash：`148c31d2dcf2cfeddf0a64ffdfed0f3bf82de5d77bf0e733a2a44bcb44555134`

冻结构造：

| 项目 | 值 |
|---|---|
| H5 多头 | 1.0x |
| 退出定义 | 前一个 H5 目标持有、当前目标完全退出 |
| funding rank | 7D 均值，PIT Top20 上三分之一，最少 5 个有效资产 |
| low-long 条件 | 退出后的 H5 target long gross ≤ 0.50 |
| 持有期 | 21 个日历日 |
| 提前关闭 | H5 重新买入 |
| 单腿 | 2.5% NAV |
| stop | 20% adverse mark |
| gross | target 0.95，hard observed 1.00 |
| 执行 | T+1 UTC +3h |
| 成本 | 2/20/50/100bps |

## 四、成本压力

| 成本 | H5 终值 | LS8 终值 | H5 Sharpe | LS8 Sharpe | H5 MDD | LS8 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 25.6692x | **27.5593x** | 1.8277 | **1.8682** | -31.41% | -31.55% |
| 20bps | 21.3487x | **22.8336x** | 1.7361 | **1.7744** | -33.36% | -33.52% |
| 50bps | 15.6946x | **16.6799x** | 1.5826 | **1.6173** | -36.59% | -36.78% |
| 100bps | 9.3848x | **9.8685x** | 1.3251 | **1.3534** | -41.92% | -42.15% |

四档终值和 Sharpe 全部高于基线，100bps MDD -42.15% < 50%。

## 五、funding 压力

3x short-adverse funding：

| 指标 | 结果 |
|---|---:|
| 终值 | 24.4605x |
| Sharpe | 1.8078 |
| MDD | -33.60% |
| 强平 | 0 |
| stop | 5 |
| 最大 observed gross | 0.9564x |
| gross breach hours | 0 |
| funding 净额 | -0.0076 |

## 六、年度、最佳年份和滚动最差

| 年份 | H5 基线 | LS8 |
|---|---:|---:|
| 2022 | -15.74% | **-14.99%** |
| 2023 | +201.14% | **+203.28%** |
| 2024 | +94.61% | **+98.88%** |
| 2025 | +112.35% | **+116.78%** |
| 2026（至 09-20） | +103.60% | **+105.44%** |

删除最佳年份后：

| 删除年份 | H5 基线 | LS8 |
|---:|---:|---:|
| 2022 | 25.3369x | **26.8611x** |
| 2023 | 7.0894x | **7.5288x** |
| 2024 | 10.9698x | **11.4811x** |
| 2025 | 10.0538x | **10.5333x** |
| 2026 | 10.4858x | **11.1147x** |

365 天滚动最差：

| 候选 | 滚动最差 | 滚动中位数 |
|---|---:|---:|
| H5 基线 | **0.7970x** | 2.1634x |
| LS8 | 0.7909x | **2.2138x** |

候选滚动中位数更高，但最差窗口低于基线，硬失败。

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

37 个可配对 episode、16 个资产：

| 指标 | 结果 |
|---|---:|
| 正贡献 episode | 25 |
| 负贡献 episode | 12 |
| episode PnL 对开仓权益合计 | +6.2960% |
| 平均 | +0.1702% |
| 中位 | +0.1834% |
| 最差 episode | -0.5276% |
| 最好 episode | +1.3994% |
| 最大 adverse mark loss | **0.4714% NAV** |

资产集中度：

| 资产 | episode | 净贡献 | 占比 |
|---|---:|---:|---:|
| NEAR | 6 | +1.9034% | **30.23%** |
| Dogecoin | 4 | +0.9478% | 15.05% |
| Litecoin | 3 | +0.8388% | 13.32% |
| 前 3 合计 | 13 | +3.6900% | **58.61%** |

集中度通过。

## 九、多重检验

| 项目 | 结果 | 门槛 | 判定 |
|---|---:|---:|---|
| PBO / CSCV | **0.000000** | <=0.50 | 通过 |
| RC vs zero | **p=0.003996** | <=0.05 | 通过 |
| RC vs BTC | **p=0.015984** | <=0.05 | 通过 |
| DSR family N=2 | **0.999995** | >=0.95 | 仅 family 通过 |
| DSR Top20/2022 N=6,142 | **0.930232** | >=0.95 | **失败** |
| DSR 全项目 N=14,179 | **0.905502** | >=0.95 | **失败** |

## 十、最终判定

**LS8 rejected。**

通过：

- 四档成本和 Sharpe；
- 100bps MDD；
- 3x short-adverse；
- gross、0 强平；
- 年度和最佳年份移除；
- 45/45 saved-path starts；
- 12/12 real-engine starts；
- 集中度；
- PBO 和 RC。

失败：

- 365 天滚动最差 0.7909x < 0.7970x；
- Top20/2022 DSR 0.9302；
- 全项目 DSR 0.9055。

按预注册不得扫描 0.30/0.40/0.50/0.60/0.70 long-gross 阈值，也不得扫描 funding/holding/stop/gross
参数。LS8 不接执行器。

## 十一、复现与文件

```bash
.venv/bin/python scripts/run_h5_lowlong_funding_exit_short.py --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_lowlong_funding_exit

.venv/bin/python scripts/run_h5_lowlong_funding_exit_short.py --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_lowlong_funding_exit
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
- `PR2026-11-LS8-H5-LOWLONG-FUNDING-EXIT_cost20_proxy/short_episodes.csv`
- `PR2026-11-LS8-H5-LOWLONG-FUNDING-EXIT_cost20_proxy/short_asset_attribution.csv`
- `PR2026-11-LS8-H5-LOWLONG-FUNDING-EXIT_cost20_proxy/short_episode_summary.csv`

研究输出不是订单，也不是实盘批准。
