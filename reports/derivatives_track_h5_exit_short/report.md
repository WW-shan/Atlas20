# Atlas20 无杠杆多空候选 LS3：H5 退出币 21 天空头

日期：2026-11-11  
候选：`PR2026-11-LS3-H5-EXIT-SHORT21`  
状态：**rejected（研究失败）**  
实盘：**不接；H5 现有多头配置不变**

## 一、结论

20bps 正式结果：

- H5 基线：**21.3487x / Sharpe 1.7361 / MDD -33.36%**
- LS3 候选：**45.9190x / Sharpe 1.8107 / MDD -40.75%**

候选收益和 Sharpe 都明显提高，但预注册风险与稳健性门槛失败：

1. **MDD 失败**：候选 -40.75%，比基线 -33.36% 差 **7.39pp**，超过 5pp 容忍线。
2. **observed gross 失败**：最高 **1.0820x**；有 **145** 个小时越过 1.00。逐小时 guard 触发 **502** 次减仓，但不能把“曾经超过 1.00”改写成通过。
3. **100bps 失败**：候选 7.1521x 低于基线 9.3848x，MDD **-57.32%** 越过 50% kill line。
4. **365 天滚动最差失败**：候选 0.5957x，基线 0.7970x。
5. **PBO 失败**：CSCV/PBO **0.8225**，远高于 0.50。
6. **全项目 DSR 失败**：N=14,173 时 **0.9043**；Top20/2022 scope 也只有 0.9277。
7. **单资产依赖失败**：空头总贡献中 `NEAR` 占 **63.5%**，前 3 资产占 **99.0%**。

因此判定 **rejected**。45.92x 说明“H5 卖出后继续跑输”这个信号值得继续研究，但当前 21D + 全额闲置 gross + 20% stop 的实现不是可上线策略。

## 二、信号依据：H5 退出后的前向收益

预注册前的纯诊断（不是生产引擎）：

- H5 完全退出的资产；
- 仍属于信号日 point-in-time Top20；
- 入场取退出信号后的下一个日线交易日；
- 对比当时 Top20 等权篮子。

| 窗口 | 观测数 | 平均相对收益 | 中位数 | 跑输概率 | iid t |
|---:|---:|---:|---:|---:|---:|
| 7D | 117 | -1.10% | -1.36% | 61.5% | -1.30 |
| 14D | 117 | -2.44% | -1.94% | 61.5% | -2.23 |
| **21D** | **117** | **-4.18%** | **-4.97%** | **66.7%** | **-3.18** |
| 30D | 117 | -4.66% | -4.05% | 63.2% | -2.89 |
| 60D | 117 | -5.46% | -6.70% | 65.0% | -2.61 |

21D 分年：2022 -0.61%、2023 +0.93%、2024 -9.50%、2025 -5.98%、2026 -0.18%。信号不是只在 2022 出现，但也不是每年都有效。

## 三、冻结构造

```text
H5 long = 1.0x
exit short = equal-weight active H5 exits, 21 calendar days
short budget = max(0, 0.95 - H5 long gross)
```

| 项目 | 冻结值 |
|---|---|
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| H5 权重 | 1.0x |
| 空头事件 | 前一个 H5 目标持有、当前目标完全退出 |
| Top20 条件 | 退出信号日仍是 point-in-time Top20 |
| 持有期 | 21 个日历日 |
| 提前关闭 | H5 重新买入 |
| 空头分配 | 活跃退出资产等权 |
| 空头预算 | 只用 H5 未使用的 gross，不重分配 H5 |
| target total gross | 0.95 |
| hard observed gross | 1.00 |
| 空头 stop | 20% adverse mark |
| long buffer | 0.75 |
| short buffer | 0.50 |
| 执行 | T+1 UTC +3h |
| 成本 | 2/20/50/100bps |
| funding | Binance proxy + `skip`；另跑 3x short-adverse |
| mark | Bitget mark，缺失 carry 最多 3 小时 |
| gross guard | observed breach 后下一小时按比例减仓到 0.95 |

预注册：

- Spec：`docs/superpowers/specs/2026-11-11-h5-exit-short-design.md`
- `spec_sha256`：`4596615470a3933b3fc10c04cb1a9a7e7683b0d36598f28ede4d49733785b00c`
- `registration_sha256`：`1018daeee77d256c0f347d5eee0093c417833a18e4ddbdc9059d31b9ded7878d`

## 四、20bps 主口径

| 指标 | H5 基线 | LS3 候选 |
|---|---:|---:|
| 终值 | 21.3487x | **45.9190x** |
| CAGR | 91.26% | **124.94%** |
| Sharpe | 1.7361 | **1.8107** |
| 最大回撤 | **-33.36%** | -40.75% |
| 强平 | 0 | 0 |
| 空头开仓 | 0 | 140 |
| 空头 stop | 0 | 19 |
| 最大 target total gross | 0.9500x | 0.9500x |
| 最大 target net gross | 0.9500x | 0.9500x |
| 平均 target total gross | 0.4561x | 0.8308x |
| 平均 target net gross | 0.4561x | 0.8308x |
| **最大 observed gross** | 0.9568x | **1.0820x** |
| observed gross breach hours | 0 | **145** |
| gross guard reductions | 0 | **502** |
| 费用总额 | 0.8830 | 3.5790 |
| funding 净额 | -0.3416 | -0.1891 |

平均 target total gross 从 45.6% 提高到 83.1%，证明 exit-short 几乎吃满了 H5 的闲置 gross。收益提升是真实的，但风险预算也明显放大。

## 五、gross guard 的作用与局限

guard 在下一小时按同一比例减仓，历史路径中共触发 502 次，且使用真实费用与 `reason=gross_guard`。它降低了持续风险，但：

- 不能防止第一次 mark 漂移越过 1.00；
- 主样本仍出现 145 个 breach hours；
- 按预注册，“任何 observed gross >1.00”都是失败；
- 不能把 guard 的减仓次数当作没有越过杠杆。

这个结果是下一轮设计的关键：**target-level gross cap 不够；需要在目标层预留漂移 buffer，或改变空头预算分配，使 observed gross 在 stop 和价格冲击下不越 1.00。**

## 六、成本压力

| 成本 | 基线终值 | 候选终值 | 基线 Sharpe | 候选 Sharpe | 基线 MDD | 候选 MDD | 最大候选 observed gross |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 25.6692x | **69.3355x** | 1.8277 | **1.9801** | -31.41% | -36.53% | 1.0819x |
| 20bps | 21.3487x | **45.9190x** | 1.7361 | **1.8107** | -33.36% | -40.75% | 1.0820x |
| 50bps | 15.6946x | **22.9462x** | **1.5826** | 1.5257 | -36.59% | -47.62% | 1.0823x |
| 100bps | **9.3848x** | 7.1521x | **1.3251** | 1.0497 | -41.92% | **-57.32%** | 1.0826x |

50bps 终值仍高于基线，但 Sharpe 已低于基线；100bps 终值和 MDD 都失败。

## 七、funding 压力

3x short-adverse funding：

| 指标 | 结果 |
|---|---:|
| 终值 | 39.2913x |
| Sharpe | 1.7466 |
| MDD | -42.91% |
| 强平 | 0 |
| 空头 stop | 19 |
| 最大 observed gross | 1.0825x |
| funding 净额 | -0.9955 |

funding 压力下 MDD 仍低于 50%，但 observed gross 继续超过 1.00；funding 仍是 Binance proxy。

## 八、年度与滚动风险

### 8.1 年度收益

| 年份 | H5 基线 | LS3 候选 |
|---|---:|---:|
| 2022 | -15.74% | **+23.46%** |
| 2023 | **+201.14%** | +185.34% |
| 2024 | +94.61% | **+156.38%** |
| 2025 | +112.35% | **+136.36%** |
| 2026（至 09-20） | +103.60% | **+115.11%** |

候选在 2023 略低，但在 2022/2024/2025/2026 更高。收益不是只靠一年。

### 8.2 最佳年份移除

候选最佳年份是 2023。删除后：

- 候选：16.0928x
- 基线：7.0894x

这一项通过。

### 8.3 365 天滚动最差

| 候选 | 最差滚动 365 天 | 中位数 |
|---|---:|---:|
| H5 基线 | **0.7970x** | 2.1634x |
| LS3 候选 | 0.5957x | 2.5089x |

候选的最差一年显著更差，失败。

### 8.4 月初路径切片

45 个“至少剩余 365 天”的月初后续路径切片：

- 候选终值高于基线：**45/45**
- 候选 Sharpe 高于基线：**17/45**
- 候选 MDD 不差于基线 5pp：**8/45**
- 三项同时通过：**7/45**

这说明候选的“终值更高”极度普遍，但风险效率只在少数起点成立。预注册要求的 12 个真实引擎启动未继续执行，因为主口径、gross、MDD、成本和多重检验已经给出同一否决结论；该执行偏差明确记录，不能计为通过。

## 九、空头 episode 与集中度

20bps 候选的 140 个完整空头 episode、31 个资产：

| 指标 | 结果 |
|---|---:|
| 正贡献 episode | 73 |
| 负贡献 episode | 67 |
| episode PnL 对开仓权益合计 | +91.63% |
| 最差 episode | -17.11% |
| 最好 episode | +49.57% |
| 最大 adverse mark loss 对开仓权益 | 14.76% |

资产集中度：

| 资产 | episode 数 | 占总贡献 |
|---|---:|---:|
| NEAR | 8 | **63.5%** |
| Cardano | 5 | 20.7% |
| Avalanche | 3 | 14.8% |
| 前 3 合计 | 16 | **99.0%** |

这直接触发单资产依赖风险：NEAR 的一次大幅退出后下跌贡献了绝大部分空头收益。不能把 LS3 的 45.92x 当作可泛化 alpha。

## 十、多重检验

| 项目 | 结果 | 门槛 | 判定 |
|---|---:|---:|---|
| PBO / CSCV | 0.8225 | ≤0.50 | **失败** |
| White Reality Check vs zero | p=0.000999 | ≤0.05 | 通过 |
| White Reality Check vs BTC | p=0.008991 | ≤0.05 | 通过 |
| DSR，候选族 N=2 | 0.999985 | ≥0.95 | 仅 family 通过 |
| DSR，Top20/2022 N=6,142 | 0.9277 | ≥0.95 | **失败** |
| DSR，全项目 N=14,173 | 0.9043 | ≥0.95 | **失败** |

RC 说明 H5 exit signal 有正向统计信号，但 PBO 和全项目 DSR 说明它不够稳定、搜索偏差仍未闭合。

## 十一、最终判定

**LS3 rejected。**

主要否决理由：

- observed gross 1.0820x，145 个 breach hours；
- MDD 比基线差 7.39pp；
- 100bps 终值低于基线且 MDD -57.32%；
- 365 天滚动最差 0.5957x；
- PBO 0.8225；
- 全项目 DSR 0.9043；
- NEAR 单资产贡献 63.5%、前 3 资产 99.0%。

按预注册，不允许扫描持有期、stop、buffer、权重或 gross 阈值。后续若继续，只能设计一个**不同的风险分配机制**，例如：

- 预先留出 observed-gross 漂移 buffer；
- 让空头预算不随 H5 闲置 gross 全额线性扩张；
- 用风险平价而不是等权分配；
- 将 exit-short 作为小比例、独立的 tail sleeve，而不是吃满全部闲置 gross。

但这些都必须作为新机制重新预注册，不能就地修改 LS3。

## 十二、复现与明细

```bash
.venv/bin/python scripts/run_h5_exit_short.py \
  --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_exit_short

.venv/bin/python scripts/run_h5_exit_short.py \
  --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_exit_short
```

关键文件：

- `cost_comparison.csv`
- `returns_20bps.csv`
- `robustness/yearly_returns.csv`
- `robustness/best_year_removal.csv`
- `robustness/rolling_worst.csv`
- `robustness/monthly_start_slices.csv`
- `multiple_testing/summary.json`
- `multiple_testing_project/deflated_sharpe.csv`
- `PR2026-11-LS3-H5-EXIT-SHORT21_cost20_proxy/target_gross.csv`
- `PR2026-11-LS3-H5-EXIT-SHORT21_cost20_proxy/trades.csv`
- `PR2026-11-LS3-H5-EXIT-SHORT21_cost20_proxy/short_episodes.csv`
- `PR2026-11-LS3-H5-EXIT-SHORT21_cost20_proxy/short_asset_attribution.csv`
