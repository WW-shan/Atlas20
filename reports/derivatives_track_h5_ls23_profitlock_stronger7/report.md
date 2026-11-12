# PR2026-11-LS43-H5-LS23-PROFITLOCK-STRONGER7

- 状态：**provisional**；当前最强样本内利润保护再分配版本，但增量集中在 2024，且尚无预注册后的独立 12 个月 OOS
- 基线：`PR2026-10-D-L125-V2`（L125）、`PR2026-11-LS23-H5-PROFIT-LOCK-REGIME-SHORT`（LS23）
- 机制对照：`PR2026-11-LS42-H5-LS23-PROFITLOCK-REDISTRIBUTE`（LS42）
- 主样本：2022-01-01 → 2026-09-21（UTC），20bps，T+1 UTC +3h
- 数据：严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip

## 1. 机制

LS43 冻结 LS23，只改变 LS22 利润保护释放权重的接收者：

```text
leader = largest H5 long holding
if leader 21D return >= 100%:
    leader *= 0.5
    eligible = other existing H5 holdings where 7D return(asset) > 7D return(leader)
    allocate freed weight pro-rata to eligible assets, cap 60% NAV each
    any remainder stays in cash
```

7D 是冻结 H5 多周期信号中已经存在的最短 horizon，不是新阈值。没有合格接收者时，LS43 不把
利润保护释放的资金机械转给相对更弱的跟随者，而是保持现金。

## 2. 主结果

| 成本 | LS23 终值 | LS42 终值 | LS43 终值 | LS23 Sharpe | LS42 Sharpe | LS43 Sharpe | LS23 MDD | LS43 MDD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 84.4362x | 90.2632x | **91.2523x** | 2.0719 | 2.0874 | **2.0945** | -37.57% | -37.865% |
| 20bps | 61.9150x | 65.8147x | **66.6800x** | 1.9448 | 1.9589 | **1.9667** | -39.84% | -40.134% |
| 50bps | 36.8788x | 38.8335x | **39.4863x** | 1.7319 | 1.7437 | **1.7525** | -43.45% | -43.744% |
| 100bps | 15.5037x | 16.0700x | **16.4391x** | 1.3745 | 1.3825 | **1.3932** | -49.48% | -49.775% |

20bps 相对 LS23 提高终值 **7.70%**、Sharpe **0.0219**，MDD 只恶化 **0.294pp**；相对 LS42
提高终值 **1.31%**、Sharpe **0.0078**，MDD 相同。四档成本全部高于同成本 LS23、LS42 和 L125。

主样本 0 强平、0 gross breach，max observed gross **1.3308x**。3x short-adverse funding 为
**66.8826x / 1.9667 / -40.253%**，仍 0 强平、0 breach。

## 3. 机制审计

- 57 次 LS22 trim；只有 **14 次**存在 7D 强于 leader 的合格接收者；
- 释放总权重 **9.2432**，其中 **1.9606** 再分配、**7.2826** 留现金；
- 14 次分配都只有一个合格接收者；没有新增资产，事件原始 gross 不变；
- short target schedule 与 LS23 逐元素完全一致（548 行，335 opens / 29 stops）；
- short attribution 335 episodes（169 正 / 166 负），单资产最大 **23.35%**、前 3 **61.99%**，
  最差 episode -1.3807% NAV。

## 4. 稳健性

- 删除任一最佳年份后终值仍高于 L125；365 天滚动最差 **0.8508x**，高于 L125 **0.7325x**；
- 45 个已保存路径月初切片 **45/45** 通过终值、Sharpe、MDD 5pp；
- 12 个真实 cash-start 引擎起点：终值和 Sharpe **12/12** 胜 L125，MDD 5pp **12/12**，
  0 强平 / 0 gross breach；
- 11 候选面板 PBO **0.2532**；White Reality Check zero p=**0.003996**、BTC p=**0.008991**；
- 当前台账 N=**14,212**（Top20/2022 N=**6,142**）下，LS43 DSR：family **0.999997**、
  Top20/2022 **0.974767**、all-project **0.963433**，均通过 >=0.95。

集中度风险必须明确：2024 年对 LS43 的增量贡献最大。删除 2024 后 LS43 为 **33.4034x**，
比 LS23 的 **34.3343x** 低 **2.71%**；也就是说，相对 LS23 的样本内优势主要由 2024 的
利润保护再分配事件贡献，不能把全样本 Sharpe 改善等同于跨年份稳定 alpha。

## 5. 当前 51 天 shadow（诊断，不是独立 OOS）

预注册前已经检查过该窗口，因此它不能作为 LS43 的 promotion OOS，只能验证 fail-safe：

| funding | L125 | LS23 | LS42 | LS43 |
|---|---:|---:|---:|---:|
| zero | 0.9484x / -0.2743 / -17.47% | 0.9403x / -0.5584 / -17.47% | 0.9220x / -0.7874 / -17.47% | **0.9403x / -0.5584 / -17.47%** |
| Bitget exact | 0.9440x / -0.3270 / -17.65% | 0.9365x / -0.6125 / -17.65% | 0.9183x / -0.8405 / -17.65% | **0.9365x / -0.6125 / -17.65%** |

窗口内 8 次 trim，但 **0 次**有 7D 强于 `NEAR` 的接收者，所以 LS43 把释放权重全部留现金，
结果与 LS23 完全一致；这正是 LS43 设计要避免 LS42 把资金转给 `ZEC` 后遭遇的损失。由于窗口已被
诊断使用，promotion 仍要求预注册后的新 12 个月 OOS。

## 6. pre-2022 proxy 压力（补充诊断）

64 条代理 mark、0 强平、0 gross breach：

| funding | LS23 | LS43 |
|---|---:|---:|
| zero proxy | 3.5113x / 2.2331 / -19.49% | **4.4496x / 2.4105 / -22.48%** |
| Binance proxy | 2.5189x / 1.7131 / -20.88% | **3.1599x / 1.9261 / -22.73%** |

LS43 在两个口径都提高终值和 Sharpe，但 MDD 恶化约 1.85–2.99pp；该压力结果不支持把 LS43
当作低回撤替代品。

## 7. 判定

**provisional。** LS43 完成并通过了所有可完成的预注册样本内、成本、funding stress、路径、
cash-start、集中度、PBO/RC/DSR 门禁，并在四档成本上优于 LS23 与 LS42。但：

1. 增量集中在 2024；删除 2024 后低于 LS23；
2. 当前 51 天 shadow 已被诊断使用，不构成独立 OOS；
3. pre-2022 proxy 的 MDD 比 LS23 差约 2–3pp。

因此不接实盘、不修改 `PR2026-10-D-L125-V2`。后续必须等待预注册后的新数据；若独立 OOS 不能
保持对 LS23 的增量，则停止整个 LS22 释放权重再分配家族，不扫描 7D、cap、收益差或接收者数量。

## 8. 证据

- 主输出：`PR2026-11-LS43-H5-LS23-PROFITLOCK-STRONGER7/`
- 成本档：`cost2/`、`cost50/`、`cost100/`
- 稳健性：`robustness/`
- cash-start：`engine_monthly_starts/`
- 多重检验：`multiple_testing/`
- shadow：`shadow_oos_2026_11_12/`
- pre-2022：`pre2022/`
- 机器门禁：`PR2026-11-LS43-H5-LS23-PROFITLOCK-STRONGER7/gate_audit.json`
- Spec：`docs/superpowers/specs/2026-11-13-h5-ls23-profitlock-stronger7-design.md`

Research output only; not an order or a live approval.
