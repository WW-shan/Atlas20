# Atlas20 无杠杆多空候选 LS4：H5 退出币固定风险空头

日期：2026-11-11
候选：`PR2026-11-LS4-H5-EXIT-RISK05`
状态：**rejected（研究失败）**
实盘：**不接；H5 现有多头配置不变**

## 一、结论

LS4 把 H5 退出后的 21 天空头从 LS3 的“吃满闲置 gross”改成每腿固定风险预算：

- 每腿 notional 固定为 **2.5% NAV**；
- 20% adverse mark stop 对应名义单笔风险 **0.5% NAV**；
- 空头仍只使用 H5 未使用的 gross；
- target total gross 0.95，hard observed gross 1.00；
- 不扫描 LS3 的权重、stop、持有期或 gross 阈值。

20bps 正式结果：

- H5 基线：**21.3487x / Sharpe 1.7361 / MDD -33.36%**
- LS4 候选：**23.8448x / Sharpe 1.8091 / MDD -34.12%**

收益、Sharpe 和成本生存性都改善，且 gross 硬约束通过。但预注册的稳健性硬门槛仍失败：

1. **365 天滚动最差失败**：LS4 **0.7838x**，基线 **0.7970x**；
2. **Top20/2022 DSR 失败**：**0.94236**，低于 0.95；
3. **全项目 DSR 失败**：**0.92072**，低于 0.95；
4. 名义单笔 0.5% 风险不是实际损失上限：最大 adverse mark loss 为 **0.6491% NAV**，比预算高 0.1491pp。

因此判定 **rejected**。LS4 明确改善了 LS3 的 gross、回撤和集中度问题，但还不能证明它在完整搜索偏差和滚动最差窗口下足够稳健，也不能接实盘。

## 二、研究问题与预注册

LS3 的 H5 exit-short 信号有统计价值，但其 45.92x 伴随：

- observed gross 1.0820x、145 个 breach hours；
- MDD -40.75%，比基线差 7.39pp；
- PBO 0.8225、全项目 DSR 0.9043；
- NEAR 单资产贡献 63.5%，前 3 资产 99.0%。

LS4 测试的是一个新的风险分配机制，而不是 LS3 参数扫描：

```text
short_notional = risk_budget / stop_distance
               = 0.005 / 0.20
               = 0.025 NAV
```

预注册文档：

- Spec：`docs/superpowers/specs/2026-11-11-h5-exit-risk-budget-design.md`
- registered spec hash：`8f23a564e870b5bb22afe230d0241ca0d491361a8aa6f76119bf4d0f0fd16d01`
- registration hash：`425dcbbf78acd4fa4399e780a8c87cad9bb5f5afd02783d41075c263bdbab087`

## 三、冻结构造

| 项目 | 冻结值 |
|---|---|
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| 多头 | 冻结 H5 `PR2026-10-H5`，1.0x |
| 空头事件 | H5 前一个目标持有、当前目标完全退出的 Top20 资产 |
| 持有期 | 21 个日历日 |
| 提前关闭 | H5 重新买入时 |
| 单腿 notional | 2.5% NAV |
| 名义单笔 stop 风险 | 0.5% NAV |
| 空头 stop | 20% adverse mark |
| 空头资金 | 只使用 H5 未使用 gross，不重分配 H5 |
| target total gross | 0.95 |
| hard observed gross | 1.00 |
| gross guard | observed breach 后下一小时按比例减仓到 0.95 |
| long buffer | 0.75 |
| short buffer | 0.50 |
| 执行 | T+1 UTC +3h |
| 成本 | 2/20/50/100bps |
| funding | Binance proxy + `skip`；另跑 3x short-adverse |
| mark | Bitget mark，缺失 carry 最多 3 小时 |

## 四、20bps 主口径

| 指标 | H5 基线 | LS4 候选 |
|---|---:|---:|
| 终值 | 21.3487x | **23.8448x** |
| CAGR | 91.26% | **95.79%** |
| Sharpe | 1.7361 | **1.8091** |
| 最大回撤 | **-33.36%** | -34.12% |
| 强平 | 0 | 0 |
| 空头开仓 | 0 | 140 |
| 空头 stop | 0 | 18 |
| 最大 target total gross | 0.9500x | 0.9500x |
| 最大 target net gross | 0.9500x | 0.9500x |
| 平均 target total gross | 0.4561x | **0.4683x** |
| 最大 requested short gross | 0 | 0.1750x |
| 最大 funded short gross | 0 | 0.1750x |
| **最大 observed gross** | 0.9568x | **0.9616x** |
| observed gross breach hours | 0 | **0** |
| gross guard reductions | 0 | **0** |
| 费用总额 | 0.8830 | 1.0140 |
| funding 净额 | -0.3416 | -0.3381 |

MDD 比基线差 **0.7547pp**，在预注册 5pp 容忍线内。空头最多只增加 17.5% NAV 的 requested gross；observed gross 仍低于 1.00，没有触发 gross guard。

## 五、成本与 funding 压力

| 成本 | 基线终值 | LS4 终值 | 基线 Sharpe | LS4 Sharpe | 基线 MDD | LS4 MDD | 最大 observed gross |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 25.6692x | **29.0746x** | 1.8277 | **1.9089** | -31.41% | -32.02% | 0.9614x |
| 20bps | 21.3487x | **23.8448x** | 1.7361 | **1.8091** | -33.36% | -34.12% | 0.9616x |
| 50bps | 15.6946x | **17.1246x** | 1.5826 | **1.6418** | -36.59% | -37.56% | 0.9618x |
| 100bps | 9.3848x | **9.8473x** | 1.3251 | **1.3610** | -41.92% | -43.35% | 0.9644x |

四档成本的终值和 Sharpe 都高于同成本基线；100bps MDD 为 **-43.35%**，低于预注册 50% kill line。四档 observed gross 都低于 1.00。

3x short-adverse funding：

| 指标 | 结果 |
|---|---:|
| 终值 | 25.1403x |
| Sharpe | 1.8347 |
| MDD | -34.34% |
| 强平 | 0 |
| 空头 stop | 18 |
| 最大 observed gross | 0.9615x |
| observed gross breach hours | 0 |
| funding 净额 | -0.3391 |

funding 压力下没有强平，MDD 低于 50%；但 funding 仍是 Binance proxy，不是 Bitget 精确历史。

## 六、单笔风险与空头归因

20bps 候选共有 **140** 个空头 episode、**31** 个资产：

| 指标 | 结果 |
|---|---:|
| 正贡献 episode | 79 |
| 负贡献 episode | 61 |
| episode PnL 对开仓权益合计 | +10.497% |
| 平均 episode PnL | +0.0750% |
| 中位 episode PnL | +0.0409% |
| 最差 episode | -0.6158% |
| 最好 episode | +1.6515% |
| **最大 adverse mark loss** | **0.6491% NAV** |

最大 adverse loss 发生在 `internet-computer` 2024-02-16 至 2024-03-05 的 episode。名义 2.5% NAV leg、20% stop 只保证在连续可成交 mark 下的预算；实际路径包含 intrabar/gap、权益变化和 stop 成交偏差，所以不能把 0.5% 当作严格损失上限。该偏差必须在任何实盘设计中显式建模，不能静默忽略。

集中度按净空头 PnL 贡献口径：

| 资产 | episode 数 | 净 PnL 对开仓权益 | 贡献占比 |
|---|---:|---:|---:|
| NEAR | 8 | +2.848% | **27.13%** |
| Avalanche | 3 | +1.474% | 14.05% |
| Dogecoin | 7 | +1.354% | 12.90% |
| 前 3 合计 | 18 | +5.676% | **54.08%** |

单资产 27.13% <= 50%，前 3 54.08% <= 80%，集中度门槛通过；即使用更保守的正贡献/绝对贡献分母，集中度也不会更高。LS4 相比 LS3 的 NEAR 63.5%、前 3 99.0% 明显改善，但还没有消除资产依赖。

## 七、年度与最佳年份移除

| 年份 | H5 基线 | LS4 |
|---|---:|---:|
| 2022 | -15.74% | **-13.79%** |
| 2023 | **+201.14%** | +200.54% |
| 2024 | +94.61% | **+98.91%** |
| 2025 | +112.35% | **+123.69%** |
| 2026（至 09-20） | +103.60% | **+106.85%** |

2023 略低于基线，但其余年份更高，且 2022 的亏损更小。

删除最佳年份后：

| 删除年份 | H5 基线 | LS4 |
|---:|---:|---:|
| 2022 | 25.3369x | **27.6603x** |
| 2023 | 7.0894x | **7.9341x** |
| 2024 | 10.9698x | **11.9875x** |
| 2025 | 10.0538x | **10.6597x** |
| 2026 | 10.4858x | **11.5278x** |

所有删除最佳年份的组合仍高于基线，该项通过。

## 八、滚动最差：硬失败

| 候选 | 365 天滚动最差 | 滚动中位数 |
|---|---:|---:|
| H5 基线 | **0.7970x** | 2.1634x |
| LS4 候选 | 0.7838x | 2.2637x |

候选的滚动中位数更高，但最差 365 天窗口比基线低 **0.0132x（约 1.32%）**。预注册要求“不低于基线”，因此该项硬失败。不能因为只差约 1.3% 就放宽规则；这是候选在压力窗口保护不足的直接证据。

## 九、真实引擎月度冷启动

为补齐 LS3 未执行的执行偏差，本轮按预注册的 12 个起点分别启动真实引擎。每个起点独立加载数据，baseline 和候选各自运行一个冷进程：

- 2022-01、2022-05、2022-09
- 2023-01、2023-05、2023-09
- 2024-01、2024-05、2024-09
- 2025-01、2025-05、2025-09

结果：

| 门槛 | 结果 | 判定 |
|---|---:|---|
| 终值胜过 baseline | **12/12** | 通过（要求 >=8/12） |
| Sharpe 胜过 baseline | **12/12** | 通过（要求 >=8/12） |
| MDD 不差于 baseline + 5pp | **12/12** | 通过（要求 12/12） |
| 0 强平 | **12/12** | 通过 |
| observed gross <= 1.00 | **12/12** | 通过 |

所有 24 个进程退出码为 0。该门槛通过，但它不能覆盖滚动最差和全项目 DSR 的失败。

另外，45 个已保存收益路径的月初切片全部通过终值、Sharpe 和 MDD 5pp 三项；这些路径切片不是真实引擎冷启动，仅作为补充敏感性证据，不能替代上表的独立引擎运行。

## 十、多重检验

| 项目 | 结果 | 门槛 | 判定 |
|---|---:|---:|---|
| PBO / CSCV | **0.00649** | <=0.50 | 通过 |
| White Reality Check vs zero | **p=0.003996** | <=0.05 | 通过 |
| White Reality Check vs BTC | **p=0.018981** | <=0.05 | 通过 |
| DSR，family N=2 | **0.999997** | >=0.95 | 仅 family 通过 |
| DSR，Top20/2022 N=6,142 | **0.942360** | >=0.95 | **失败** |
| DSR，全项目 N=14,174 | **0.920719** | >=0.95 | **失败** |

PBO 和 RC 都支持信号有真实信息；但 family 只有 2 个候选，不能代表整个项目搜索历史。扩大到 Top20/2022 和全项目后，DSR 都低于预注册门槛，因此不能升级。

## 十一、最终判定

**LS4 rejected。**

通过项：

- 20bps 终值、Sharpe 高于基线；
- MDD 只比基线差 0.75pp，在 5pp 容忍线内；
- 2/20/50/100bps 四档终值和 Sharpe 都高于同成本基线；
- 100bps MDD -43.35% < 50%；
- 0 强平、observed gross 全部 <=1.00；
- 年度、最佳年份移除、12 个真实引擎冷启动和集中度门槛通过；
- PBO、RC 通过。

硬失败项：

- 365 天滚动最差 0.7838x < 基线 0.7970x；
- Top20/2022 DSR 0.942360 < 0.95；
- 全项目 DSR 0.920719 < 0.95；
- 实际最大单笔 adverse loss 0.6491% NAV，超过名义 0.5% 风险预算，必须披露。

按预注册，不能在 LS4 失败后扫描 0.25%/0.75%/1.0% risk budget、15%/25%/30% stop、7/14/28/30/60D 持有期、权重或 gross 阈值。下一轮若继续研究，必须换新的机制并重新预注册；H5 实盘不变。

## 十二、复现与关键文件

主口径：

```bash
.venv/bin/python scripts/run_h5_exit_short.py \
  --risk-budget --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_exit_risk_budget

.venv/bin/python scripts/run_h5_exit_short.py \
  --risk-budget --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_exit_risk_budget
```

真实引擎冷启动的逐起点命令、日志和状态：

- `engine_monthly_starts/status.csv`
- `engine_monthly_starts/summary.csv`
- `engine_monthly_starts/summary.json`
- `engine_monthly_starts/logs/`

主要结果文件：

- `returns_20bps.csv`
- `cost_comparison.csv`
- `cost_runs_long.csv`
- `funding_stress_summary.csv`
- `robustness/yearly_returns.csv`
- `robustness/best_year_removal.csv`
- `robustness/rolling_worst.csv`
- `robustness/monthly_start_slices.csv`
- `robustness/monthly_start_slice_summary.json`
- `multiple_testing/summary.json`
- `multiple_testing_project/deflated_sharpe.csv`
- `PR2026-11-LS4-H5-EXIT-RISK05_cost20_proxy/short_episodes.csv`
- `PR2026-11-LS4-H5-EXIT-RISK05_cost20_proxy/short_asset_attribution.csv`
- `PR2026-11-LS4-H5-EXIT-RISK05_cost20_proxy/short_episode_summary.csv`
- `PR2026-11-LS4-H5-EXIT-RISK05_cost20_proxy/summary.json`

研究输出不是订单，也不是实盘批准；LS4 不接执行器，不修改 H5 账本。
