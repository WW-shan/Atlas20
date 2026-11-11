# Atlas20 候选 LS22：H5 单一龙头极端涨幅利润保护

日期：2026-11-12  
候选：`PR2026-11-LS22-H5-EXTREME-RUN-PROFIT-LOCK`  
状态：**provisional（预注册路径门槛失败；不接实盘）**  
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS22 是首个在 2/20/50/100bps 四档成本上同时提高终值和 Sharpe，并改善最大回撤的候选。
它在 20bps 为 **44.6607x / 1.8257 / -39.84%**，L125 为 **40.2200x / 1.7330 / -40.65%**。
但预注册的 45 个“至少剩余 365 天”的月初路径切片只通过 **37/45**，因此不能晋级或接实盘。

## 二、预注册

- Spec：`docs/superpowers/specs/2026-11-12-h5-extreme-run-profit-lock-design.md`
- spec hash：`8763d4b303531ebfa2d830f5c0772ae1413f8e0a22b2bd6126f0d0a2a47ddb09`
- registration hash：`6cbb3b6b48a7e4f1d34607d3a72b0c1dfe1c6a0f3877d7b3166ab6654b7a4280`
- 运行前审计：`reports/derivatives_track_h5_regime_short_router/profit_lock_audit/`

审计显示，542 个 H5 target event 中 57 个触发减半，trim 时释放 gross 中位数 0.1717x NAV、
最大值 0.2806x NAV；按年触发次数为 2022/2023/2024/2025/2026 = 1/16/32/4/4。

## 三、四档成本

| 成本 | L125 终值 | LS22 终值 | L125 Sharpe | LS22 Sharpe | L125 MDD | LS22 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 50.6408x | **56.5820x** | 1.8249 | **1.9237** | -38.42% | **-37.61%** |
| 20bps | 40.2200x | **44.6607x** | 1.7330 | **1.8257** | -40.65% | **-39.84%** |
| 50bps | 27.3725x | **30.0813x** | 1.5790 | **1.6613** | -44.20% | **-43.40%** |
| 100bps | 14.3794x | **15.5305x** | 1.3204 | **1.3853** | -50.02% | **-49.40%** |

主样本 0 强平、0 gross breach；最大观测 gross 1.2957x，低于 1.50x hard cap。
100bps MDD 为 -49.40%，低于 50% kill line。

## 四、年度、最佳年份与滚动窗口

| 年份 | L125 | LS22 |
|---|---:|---:|
| 2022 | -19.61% | **-11.88%** |
| 2023 | +277.20% | **+292.41%** |
| 2024 | **+119.25%** | +96.09% |
| 2025 | +151.02% | **+172.80%** |
| 2026 | +141.01% | **+141.43%** |

删除任一最佳年份后的终值，LS22 全部高于 L125：

| 删除年份 | L125 | LS22 |
|---:|---:|---:|
| 2022 | 50.0330x | **50.6795x** |
| 2023 | 10.6628x | **11.3810x** |
| 2024 | 18.3441x | **22.7755x** |
| 2025 | 16.0225x | **16.3711x** |
| 2026 | 16.6884x | **18.4988x** |

365 天滚动最差从 L125 的 **0.7325x** 改善到 **0.8134x**，中位数从 2.5547x 改善到 2.6922x。

## 五、成本外压力

20bps + 3x long-adverse funding：**32.8229x / 1.6991 / -41.70% / 0 强平**。
funding total 从基准口径的 -0.6114 恶化到 -1.9415，但没有强平。

## 六、路径切片失败（预注册 gate）

45 个月初起点中：

- 终值胜 L125：**37/45**；
- Sharpe 胜 L125：**45/45**；
- MDD 不差于 L125 +5pp：**45/45**；
- 三项同时通过：**37/45**。

8 个终值失败起点：

| 起点 | L125 | LS22 | 相对差 |
|---|---:|---:|---:|
| 2023-03 | 42.1082x | 42.1081x | -0.0002% |
| 2023-04 | 45.6258x | 45.6257x | -0.0002% |
| 2023-05 | 50.7920x | 50.7919x | -0.0002% |
| 2023-06 | 54.4962x | 54.4961x | -0.0002% |
| 2023-12 | 22.4290x | 21.9841x | -1.98% |
| 2024-01 | 13.2643x | 12.9148x | -2.63% |
| 2024-02 | 15.4448x | 15.0378x | -2.63% |
| 2024-03 | 14.5476x | 14.1643x | -2.63% |

前四个只是浮点数值平局，但按冻结规则仍记为失败。真正经济上落后的是 2023-12 至 2024-03 四个
起点，原因是 2024-03 的 SHIB 连续触发 trim，牺牲了部分 2024 右尾。

## 七、判定与未执行阶段

**Provisional。** 四档成本、Sharpe、MDD、年度删除、滚动最差和 funding 压力都很强，但预注册
45/45 路径门槛未通过，因此：

- 不进入 12 个真实引擎月初冷启动；
- 不进入 PBO/RC/DSR promotion；
- 不接执行器，不修改实盘；
- 不扫描 75%/87%/125%、scale 0.25/0.75、top-2/top-3 或再分配规则。

该候选保留为研究资产：它的核心机制有效，但路径依赖仍需通过“独立机制组合”而不是调参修复。

## 八、复现

```bash
.venv/bin/python scripts/audit_h5_profit_lock.py
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS22-H5-EXTREME-RUN-PROFIT-LOCK \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_extreme_run_profit_lock
.venv/bin/python scripts/derivatives_robustness.py \
  --returns reports/derivatives_track_h5_extreme_run_profit_lock/robustness/candidate_returns.csv \
  --output-dir reports/derivatives_track_h5_extreme_run_profit_lock/robustness/calendar
.venv/bin/python scripts/derivatives_path_robustness.py \
  --returns reports/derivatives_track_h5_extreme_run_profit_lock/robustness/candidate_returns.csv \
  --output-dir reports/derivatives_track_h5_extreme_run_profit_lock/robustness/monthly_starts
```
