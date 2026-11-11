# Atlas20 无杠杆多空候选 LS5：H5 退出币 + 14D 最弱篮子固定风险空头

日期：2026-11-11
候选：`PR2026-11-LS5-H5-EXIT-WEAK4-RISK05`
状态：**rejected（研究失败）**
实盘：**不接；H5 现有多头配置不变**

## 一、结论

LS5 将两个已经分别测试过的空头信号合并：

- sleeve A：H5 完全退出资产，固定 21 天；
- sleeve B：PIT Top20 内 14D 最弱 4 币，固定 7 日再平衡；
- 每腿 2.5% NAV，20% adverse stop；
- 同资产两条 sleeve 重叠时只保留一条 2.5% 腿；
- H5 保持 1.0x，只使用未使用 gross，target total gross 0.95，hard observed gross 1.00。

20bps 主口径：

- H5 基线：**21.3487x / Sharpe 1.7361 / MDD -33.36%**
- LS5 候选：**24.1210x / Sharpe 1.8424 / MDD -34.31%**
- 最大 observed gross：**0.9669x**
- 强平：0
- 空头 stop：87
- 短仓开仓：721

主口径收益、Sharpe、MDD 和 gross 门槛都通过，但预注册硬门槛仍失败：

1. **100bps 失败**：7.7417x，低于基线 9.3848x；Sharpe 1.2552，也低于 1.3251。
2. **移除 2022 后失败**：24.4989x，低于基线 25.3369x。
3. **全项目 DSR 失败**：N=14,175 时 **0.9334**。
4. **前 3 资产集中度失败**：净空头贡献 126.5%，高于 80% 上限。
5. **实际单笔 adverse loss 超预算**：最大 0.7088% NAV，高于名义 0.5%。
6. **weak4 sleeve 自身为负**：550 笔净贡献 -2.66% 开仓权益；收益主要来自 exit sleeve 和 overlap。

因此判定 **rejected**。LS5 的改动虽然把 365 天滚动最差从 LS4 的 0.7838x 改善到 0.8083x，但没有解决成本、年份依赖和组合集中度，且新增信号本身未产生正贡献。

## 二、预注册

- Spec：`docs/superpowers/specs/2026-11-11-h5-exit-weak4-risk-combo-design.md`
- registered spec hash：`fdf8fb8c7bf831f98096f7ec7b398ba73817d6b876d2686bab6dfb51cff81286`
- registration hash：`113030ad110255ca8c9064f8fb948c3bfb8961e397f21faaebc58aa944a31f96`

正式运行前完成登记；本报告不修改 LS5 参数。

## 三、冻结构造

| 项目 | 冻结值 |
|---|---|
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| H5 多头 | 1.0x |
| sleeve A | H5 完全退出，固定 21 日历日 |
| sleeve B | 14D 最弱 4 币，7 日网格 |
| sleeve B 过滤 | PIT Top20、Bitget mark 可用、最近 3 个 funding settlement mean > -0.0002 |
| sleeve B 排除 | 当前 H5 多头持仓 |
| 单腿 notional | 2.5% NAV |
| 单腿名义风险 | 0.5% NAV |
| 重叠 | 同资产 `max(A, B)`，不求和 |
| stop | 20% adverse mark |
| 资金约束 | 仅 H5 未使用 gross |
| target total gross | 0.95 |
| hard observed gross | 1.00 |
| execution | T+1 UTC +3h |
| costs | 2/20/50/100bps |
| funding | Binance proxy/skip；另跑 3x short-adverse |

## 四、成本压力

| 成本 | H5 终值 | LS5 终值 | H5 Sharpe | LS5 Sharpe | H5 MDD | LS5 MDD | 最大 observed gross |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 25.6692x | **31.1231x** | 1.8277 | **1.9732** | -31.41% | -31.68% | 0.9664x |
| 20bps | 21.3487x | **24.1210x** | 1.7361 | **1.8424** | -33.36% | -34.31% | 0.9669x |
| 50bps | 15.6946x | **15.7624x** | 1.5826 | **1.6231** | -36.59% | -38.48% | 0.9680x |
| 100bps | **9.3848x** | 7.7417x | **1.3251** | 1.2552 | -41.92% | -45.20% | 0.9697x |

50bps 仅比基线高 0.43%，100bps 则低于基线且 Sharpe 更低。100bps MDD -45.20% 没有越过 50% kill line，但成本生存性硬失败。

成本失败的原因非常明确：weak4 weekly 篮子每周重新定权，产生 **721** 次 short open 和大量 reduce/increase；费用总额从 20bps 的 1.3161 增长到 100bps 的 2.9656。相对而言，LS4 的 exit-only 固定腿只有 140 次 open，100bps 时仍高于基线。

## 五、funding 压力

3x short-adverse funding：

| 指标 | 结果 |
|---|---:|
| 终值 | 23.9464x |
| Sharpe | 1.8372 |
| MDD | -34.58% |
| 强平 | 0 |
| stop | 87 |
| 最大 observed gross | 0.9661x |
| gross breach hours | 0 |
| funding 净额 | -0.2861 |

funding 压力和 MDD 门槛通过；funding 仍是 Binance proxy，不是 Bitget 精确历史。

## 六、年度、最佳年份和滚动最差

### 6.1 年度收益

| 年份 | H5 基线 | LS5 |
|---|---:|---:|
| 2022 | -15.74% | **-1.54%** |
| 2023 | **+201.14%** | +180.47% |
| 2024 | **+94.61%** | +80.70% |
| 2025 | +112.35% | **+130.39%** |
| 2026（至 09-20） | +103.60% | **+109.81%** |

候选明显改善 2022、2025 和 2026，但 2023、2024 明显落后。

### 6.2 最佳年份移除

| 删除年份 | H5 基线 | LS5 |
|---:|---:|---:|
| 2022 | **25.3369x** | 24.4989x |
| 2023 | 7.0894x | **8.6001x** |
| 2024 | 10.9698x | **13.3485x** |
| 2025 | 10.0538x | **10.4696x** |
| 2026 | 10.4858x | **11.4966x** |

删除 2022 后 LS5 低于基线，触发预注册失败。

### 6.3 365 天滚动最差

| 候选 | 滚动最差 | 滚动中位数 |
|---|---:|---:|
| H5 基线 | 0.7970x | 2.1634x |
| LS5 | **0.8083x** | 2.2738x |

滚动最差高于基线，该项通过。LS5 确实修复了 LS4 的滚动最差问题，但代价是 100bps 成本脆弱和更差的年份依赖。

## 七、路径切片与真实引擎冷启动

45 个已保存收益路径月初切片：

- 终值高于基线：39/45；
- Sharpe 高于基线：45/45；
- MDD 5pp：45/45；
- 三项同时通过：39/45。

12 个真实引擎月度冷启动全部进程成功：

| 门槛 | 结果 | 判定 |
|---|---:|---|
| 终值胜过 baseline | 11/12 | 通过（>=8/12） |
| Sharpe 胜过 baseline | 12/12 | 通过（>=8/12） |
| MDD 5pp | 12/12 | 通过 |
| 0 强平 | 12/12 | 通过 |
| observed gross <= 1.00 | 12/12 | 通过 |

唯一一个终值低于基线的起点是 2023-01：23.4557x vs 23.9469x。冷启动总体通过，但不能抵消 100bps、移除 2022、DSR 和集中度失败。

## 八、空头归因

20bps 候选产生 **713** 个可配对短仓 episode、36 个资产：

| 指标 | 结果 |
|---|---:|
| 正贡献 episode | 338 |
| 负贡献 episode | 375 |
| episode PnL 对开仓权益合计 | +7.724% |
| 平均 episode PnL | +0.0108% |
| 中位 episode PnL | -0.0093% |
| 最差 episode | -0.7333% |
| 最好 episode | +2.4820% |
| 最大 adverse mark loss | **0.7088% NAV** |

按 sleeve 归属：

| sleeve | episode | 合计 PnL / 开仓权益 | 平均 | 胜率 | 最大 adverse |
|---|---:|---:|---:|---:|---:|
| exit | 127 | +7.921% | +0.0624% | 51.2% | 0.6842% |
| overlap | 36 | +2.464% | +0.0685% | 41.7% | 0.4922% |
| weak4 | **550** | **-2.662%** | **-0.0048%** | 46.9% | **0.7088%** |

weak4 sleeve 自身为负，说明只看 R6 的总 Sharpe 不足以证明该信号在固定 2.5% 风险、无杠杆和 H5 1.0x 的上下文中仍有增量。

资产集中度：

| 资产 | episode | 净贡献（开仓权益） | 占比 |
|---|---:|---:|---:|
| Avalanche | 42 | +3.625% | **46.94%** |
| Cardano | 45 | +3.317% | **42.94%** |
| NEAR | 21 | +2.829% | **36.63%** |
| 前 3 合计 | 108 | +9.771% | **126.53%** |

单资产 Avalanche 46.94% <=50%，但前 3 合计 126.53% >80%，集中度硬失败。实际最大 adverse loss 0.7088% NAV 也高于名义 0.5%，风险预算不能视为严格封顶。

## 九、多重检验

| 项目 | 结果 | 门槛 | 判定 |
|---|---:|---:|---|
| PBO / CSCV | **0.09524** | <=0.50 | 通过 |
| RC vs zero | **p=0.003996** | <=0.05 | 通过 |
| RC vs BTC | **p=0.020979** | <=0.05 | 通过 |
| DSR，family N=2 | **0.999998** | >=0.95 | 仅 family 通过 |
| DSR，Top20/2022 N=6,142 | **0.952281** | >=0.95 | 通过 |
| DSR，全项目 N=14,175 | **0.933398** | >=0.95 | **失败** |

LS5 首次让 Top20/2022 DSR 超过 0.95，但全项目搜索偏差仍未闭合。

## 十、最终判定

**LS5 rejected。**

通过项：

- 20bps 收益、Sharpe、MDD、gross、0 强平；
- 2bps、20bps、50bps 终值和 Sharpe 高于基线；
- 3x short-adverse funding；
- 删除 2023/2024/2025/2026 的最佳年份移除组合；
- 365 天滚动最差 0.8083x；
- 12 个真实引擎冷启动；
- PBO、RC、Top20/2022 DSR。

硬失败项：

- 100bps 7.7417x < 基线 9.3848x，Sharpe 也更低；
- 移除 2022 后 24.4989x < 基线 25.3369x；
- 全项目 DSR 0.9334 < 0.95；
- 前 3 资产贡献 126.53% >80%；
- weak4 sleeve 净贡献 -2.662%；
- 最大实际 adverse loss 0.7088% NAV > 名义 0.5%。

按预注册，不得扫描 sleeve B 的 14D、4 币、7 日、funding、stop、单腿权重或 LS5 组合比例。下一轮必须换成新的机制，重点应是降低换手/改善非 2022 年份，而不是继续调 LS5。

## 十一、复现与明细

主口径：

```bash
.venv/bin/python scripts/run_h5_exit_weak_combo.py --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_exit_weak4_risk

.venv/bin/python scripts/run_h5_exit_weak_combo.py --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_exit_weak4_risk
```

关键文件：

- `returns_20bps.csv`
- `cost_comparison.csv`
- `cost_runs_long.csv`
- `funding_stress_summary.csv`
- `robustness/yearly_returns.csv`
- `robustness/best_year_removal.csv`
- `robustness/rolling_worst.csv`
- `robustness/monthly_start_slices.csv`
- `engine_monthly_starts/summary.csv`
- `multiple_testing/summary.json`
- `multiple_testing_project/deflated_sharpe.csv`
- `PR2026-11-LS5-H5-EXIT-WEAK4-RISK05_cost20_proxy/short_episodes.csv`
- `PR2026-11-LS5-H5-EXIT-WEAK4-RISK05_cost20_proxy/short_asset_attribution.csv`
- `PR2026-11-LS5-H5-EXIT-WEAK4-RISK05_cost20_proxy/short_episode_summary.csv`

研究输出不是订单，也不是实盘批准；LS5 不接执行器，不修改 H5 账本。
