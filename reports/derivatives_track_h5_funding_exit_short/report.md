# Atlas20 无杠杆多空候选 LS6：H5 退出币资金费率拥挤空头

日期：2026-11-11
候选：`PR2026-11-LS6-H5-FUNDING-EXIT-RISK05`
状态：**rejected（研究失败）**
实盘：**不接；H5 现有多头配置不变**

## 一、结论

LS6 只做 H5 退出币空头，并要求退出资产在信号日的 7D funding 横截面中位于当时 PIT Top20 的上三分之一。

20bps：

- H5 基线：**21.3487x / Sharpe 1.7361 / MDD -33.36%**
- LS6 候选：**22.9279x / Sharpe 1.7811 / MDD -33.40%**
- 最大 observed gross：**0.9568x**
- 强平：0
- 空头 open / stop：52 / 8

LS6 是首个同时通过成本、最佳年份移除、集中度和 12/12 真实引擎冷启动的多空候选，但仍有两个硬失败：

1. **365 天滚动最差失败**：0.7923x，低于基线 0.7970x；
2. **多重检验失败**：Top20/2022 DSR 0.932636、全项目 DSR 0.908511。

因此判定 **rejected**。LS6 证明 funding crowding 过滤可以显著降低换手、保住成本并消除集中度问题，但没有足够提高 Sharpe 和滚动最差。

## 二、预注册与机制

- Spec：`docs/superpowers/specs/2026-11-11-h5-funding-rank-exit-short-design.md`
- registered spec hash：`6b91d61ea6c88da6daf81ee1b9e4d39bf7b8eab4c45910338cde01406871e35e`
- registration hash：`1bcd620f657249f4f272142a272972c953cbb624b51fc0e73bb430d04f453594`

冻结构造：

| 项目 | 值 |
|---|---|
| H5 多头 | 1.0x |
| 退出定义 | 前一个 H5 目标持有、当前目标完全退出 |
| funding rank | 7D 均值，PIT Top20 上三分之一，最少 5 个有效资产 |
| 持有期 | 21 个日历日 |
| 提前关闭 | H5 重新买入 |
| 单腿 | 2.5% NAV |
| 名义 stop 风险 | 0.5% NAV |
| stop | 20% adverse mark |
| gross | target 0.95，hard observed 1.00 |
| 执行 | T+1 UTC +3h |
| 成本 | 2/20/50/100bps |

缺失 funding 或有效横截面不足 5 个资产时 fail closed，不开新空头。

## 三、成本压力

| 成本 | H5 终值 | LS6 终值 | H5 Sharpe | LS6 Sharpe | H5 MDD | LS6 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 25.6692x | **27.7169x** | 1.8277 | **1.8760** | -31.41% | **-31.39%** |
| 20bps | 21.3487x | **22.9279x** | 1.7361 | **1.7811** | -33.36% | -33.40% |
| 50bps | 15.6946x | **16.7044x** | 1.5826 | **1.6221** | -36.59% | -36.72% |
| 100bps | 9.3848x | **9.8394x** | 1.3251 | **1.3552** | -41.92% | -42.20% |

四档终值和 Sharpe 全部高于基线，100bps MDD -42.20% < 50%。空头 open 在各成本档都是 52 次，费用从 0.1092 增至 2.6043。

## 四、funding 压力

3x short-adverse funding：

| 指标 | 结果 |
|---|---:|
| 终值 | 24.5246x |
| Sharpe | 1.8139 |
| MDD | -33.51% |
| 强平 | 0 |
| stop | 8 |
| 最大 observed gross | 0.9564x |
| gross breach hours | 0 |
| funding 净额 | -0.0090 |

funding 压力通过；funding 仍是 Binance proxy，不是 Bitget 精确历史。

## 五、年度、最佳年份和滚动最差

| 年份 | H5 基线 | LS6 |
|---|---:|---:|
| 2022 | -15.74% | **-14.20%** |
| 2023 | +201.14% | **+203.82%** |
| 2024 | +94.61% | **+96.24%** |
| 2025 | +112.35% | **+117.93%** |
| 2026（至 09-20） | +103.60% | **+105.66%** |

所有年份都不低于基线。

删除最佳年份后：

| 删除年份 | H5 基线 | LS6 |
|---:|---:|---:|
| 2022 | 25.3369x | **26.7220x** |
| 2023 | 7.0894x | **7.5465x** |
| 2024 | 10.9698x | **11.6838x** |
| 2025 | 10.0538x | **10.5207x** |
| 2026 | 10.4858x | **11.1485x** |

全部通过。

365 天滚动最差：

| 候选 | 滚动最差 | 滚动中位数 |
|---|---:|---:|
| H5 基线 | **0.7970x** | 2.1634x |
| LS6 | 0.7923x | **2.2140x** |

候选中位数更高，但最差窗口仍低 0.0047x，硬失败。

## 六、路径切片与真实引擎冷启动

45 个已保存收益路径月初切片：

- 终值、Sharpe、MDD 5pp 三项全部通过 **45/45**。

12 个真实引擎月度冷启动：

| 门槛 | 结果 |
|---|---:|
| 终值胜过 baseline | **12/12** |
| Sharpe 胜过 baseline | **12/12** |
| MDD 5pp | **12/12** |
| 0 强平 | **12/12** |
| observed gross <= 1.00 | **12/12** |

所有 24 个独立进程退出码为 0。LS6 的起点稳健性明显强于 LS4/LS5。

## 七、空头归因

52 个可配对 episode、20 个资产：

| 指标 | 结果 |
|---|---:|
| 正贡献 episode | 33 |
| 负贡献 episode | 19 |
| episode PnL 对开仓权益合计 | +7.025% |
| 平均 | +0.1351% |
| 中位 | +0.1428% |
| 最差 episode | -0.5887% |
| 最好 episode | +1.5860% |
| 最大 adverse mark loss | **0.5971% NAV** |

资产集中度：

| 资产 | episode | 净贡献 | 占比 |
|---|---:|---:|---:|
| NEAR | 7 | +2.722% | **38.74%** |
| Dogecoin | 7 | +1.296% | 18.45% |
| Litecoin | 4 | +0.980% | 13.95% |
| 前 3 合计 | 18 | +4.998% | **71.15%** |

单资产 38.74% <50%，前 3 71.15% <80%，集中度通过。

实际最大 adverse loss 0.5971% NAV，高于名义 0.5% 约 0.0971pp，必须按 gap/intrabar 偏差披露，不能把 0.5% 视为严格封顶。

## 八、多重检验

| 项目 | 结果 | 门槛 | 判定 |
|---|---:|---:|---|
| PBO / CSCV | **0.004329** | <=0.50 | 通过 |
| RC vs zero | **p=0.003996** | <=0.05 | 通过 |
| RC vs BTC | **p=0.015984** | <=0.05 | 通过 |
| DSR family N=2 | **0.999996** | >=0.95 | 仅 family 通过 |
| DSR Top20/2022 N=6,142 | **0.932636** | >=0.95 | **失败** |
| DSR 全项目 N=14,176 | **0.908511** | >=0.95 | **失败** |

PBO 和 RC 强，但 Sharpe 只有 1.7811，仍低于项目历史选择的 deflation 门槛。

## 九、最终判定

**LS6 rejected。**

通过：

- 20bps 收益、Sharpe、MDD、gross、0 强平；
- 四档成本和 Sharpe；
- 100bps MDD；
- 3x short-adverse；
- 所有年度、所有最佳年份移除；
- 45/45 saved-path starts；
- 12/12 real-engine starts；
- 集中度；
- PBO 和 RC。

失败：

- 365 天滚动最差 0.7923x < 0.7970x；
- Top20/2022 DSR 0.932636；
- 全项目 DSR 0.908511。

LS6 是当前质量最高、风险最接近可用的空头机制，但按预注册仍不能升级。不得扫描 funding lookback、rank、min_assets、持有期、stop、单腿或 gross。下一轮必须改成机制不同的新候选。

## 十、复现与文件

```bash
.venv/bin/python scripts/run_h5_funding_exit_short.py --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_funding_exit_short

.venv/bin/python scripts/run_h5_funding_exit_short.py --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_funding_exit_short
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
- `multiple_testing_project/deflated_sharpe.csv`
- `PR2026-11-LS6-H5-FUNDING-EXIT-RISK05_cost20_proxy/short_episodes.csv`
- `PR2026-11-LS6-H5-FUNDING-EXIT-RISK05_cost20_proxy/short_asset_attribution.csv`
- `PR2026-11-LS6-H5-FUNDING-EXIT-RISK05_cost20_proxy/short_episode_summary.csv`

研究输出不是订单，也不是实盘批准；LS6 不接执行器，不修改 H5 账本。
