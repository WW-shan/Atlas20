# PR2026-11-LS42-H5-LS23-PROFITLOCK-REDISTRIBUTE

- 状态：**provisional**；当前最强的 LS42 样本内候选，但 51 天 OOS 尚未证明增量，不接实盘
- 基线：`PR2026-10-D-L125-V2`（L125）与 `PR2026-11-LS23-H5-PROFIT-LOCK-REGIME-SHORT`（LS23）
- 主样本：2022-01-01 → 2026-09-21（UTC），20bps，T+1 UTC +3h
- 数据：严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip
- 冻结机制：LS22 21D/100% 单龙头减半后，把释放权重按同一事件其他既有 H5 多头的相对权重分配，单币上限 60% NAV；未分配部分留现金；不新增资产、不改变 LS12 空头 router、20% short stop、50% buffer、1.25x H5 和 1.50x hard gross

## 1. 主结果

| 成本 | L125 终值 | LS23 终值 | LS42 终值 | L125 Sharpe | LS23 Sharpe | LS42 Sharpe | LS23 MDD | LS42 MDD |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 50.6408x | 84.4362x | **90.2632x** | 1.8249 | 2.0719 | **2.0874** | -37.57% | -37.865% |
| 20bps | 40.2200x | 61.9150x | **65.8147x** | 1.7330 | 1.9448 | **1.9589** | -39.84% | -40.134% |
| 50bps | 27.3725x | 36.8788x | **38.8335x** | 1.5790 | 1.7319 | **1.7437** | -43.45% | -43.744% |
| 100bps | 14.3794x | 15.5037x | **16.0700x** | 1.3204 | 1.3745 | **1.3825** | -49.48% | -49.775% |

20bps 下 LS42 相对 LS23 的终值提高 **6.30%**、Sharpe 提高 **0.0141**，MDD 只恶化
**0.294pp**；2/50/100bps 同样提高终值和 Sharpe，成本尾部没有失效。100bps 终值和 Sharpe 均
高于 LS23，MDD -49.775% 仍在 50% 容差内。

主样本 0 强平、0 gross breach；20bps max observed gross **1.3308x**。3x short-adverse funding
压力下为 **66.0923x / 1.9593 / -40.253%**，0 强平、0 gross breach。

## 2. 机制审计与归因

- 57 次利润保护 trim；总释放权重 **9.2432 NAV-weight**；
- 其中 **4.3556** 重新分配给同一事件的既有 H5 多头，**4.8876** 因重分配后 gross/60% cap 留现金；
- 不新增资产，重分配前后事件 gross 不变；短端 selection 与 LS23 的 548 行 target schedule
  **逐元素完全一致**，short opens 335、short stops 29；
- short attribution：335 个 episode（169 正 / 166 负），单资产最大贡献 **23.32%**、前 3
  **61.95%**，均通过 <=50% / <=80% 集中度门槛；最差 episode -1.3807% NAV。

## 3. 稳健性与多重检验

- 删除任一最佳年份后终值均高于 L125；365 天滚动最差 **0.8508x**，高于 L125 的 **0.7325x**；
- 45 个已保存路径月初切片 **45/45** 通过终值、Sharpe、MDD 5pp；
- 12 个真实 cash-start 引擎月初起点：终值和 Sharpe **12/12** 胜 L125，MDD 5pp **12/12**，
  0 强平 / 0 gross breach；L125 baseline 使用 LS23 同一组已归档真实 cash-start 结果；
- 10 候选（L125、LS12、LS17–LS23、LS42）同一 1,724 天面板：PBO **0.2132**；
  White Reality Check zero p=**0.003996**、BTC p=**0.009990**；
- 当前台账 N=**14,211**（Top20/2022 N=**6,142**）下，LS42 DSR：family **0.999998**、
  Top20/2022 **0.973375**、all-project **0.961571**，均通过 >=0.95。

## 4. 51 天 shadow OOS（2026-09-22 → 2026-11-11）

同一 `oos_refresh_20261112` mark 快照（88/88 资产、0 missing hours、max gap 1h），20bps，
首日初始化收益排除在 Sharpe/volatility 外：

| funding | 策略 | 终值 | Sharpe | MDD | 0 强平 |
|---|---|---:|---:|---:|---:|
| zero | L125 | 0.9484x | -0.2743 | -17.47% | 是 |
| zero | LS23 | 0.9403x | -0.5584 | -17.47% | 是 |
| zero | **LS42** | **0.9220x** | **-0.7874** | -17.47% | 是 |
| Bitget exact | L125 | 0.9440x | -0.3270 | -17.65% | 是 |
| Bitget exact | LS23 | 0.9365x | -0.6125 | -17.65% | 是 |
| Bitget exact | **LS42** | **0.9183x** | **-0.8405** | -17.65% | 是 |

LS42 在该窗口触发 8 次 trim、重分配 0.7148、留现金 0.9365；但 51 天 BTC 在 200D 上方，
短端 0 次开仓，且 LS42 比 LS23 低约 **1.82pp（zero）/1.82pp（exact）** 终值。窗口仅覆盖
12 个月 OOS 的 **51/365 天（14.0%）**，因此不能判定 12 个月 OOS 失败，也不能 promotion。
结论：LS42 在样本内是最强的利润保护再分配版本；真实 OOS 早期反而落后于 incumbent，继续
观察但不修改实盘。

## 5. 门禁状态

| 门禁 | 状态 |
|---|---|
| 20bps 终值、Sharpe、MDD 对 LS23 | pass |
| 2/20/50/100bps 对同成本 LS23 与 L125 | pass |
| 100bps 尾部（终值、Sharpe、MDD） | pass |
| 零强平 / gross cap / 0 breach | pass |
| 3x short-adverse funding | pass |
| 删除最佳年份 / 365D rolling / 45 paths | pass |
| 12 个 cash-start 引擎起点 | pass |
| short 集中度 | pass |
| PBO / RC / DSR | pass |
| 12 个月真实 OOS | **pending，51/365 天** |

完整机器可读门禁：`PR2026-11-LS42-H5-LS23-PROFITLOCK-REDISTRIBUTE/gate_audit.json`。

## 6. 复现与证据

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS42-H5-LS23-PROFITLOCK-REDISTRIBUTE \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_redistribute
```

- 主输出：`PR2026-11-LS42-H5-LS23-PROFITLOCK-REDISTRIBUTE/`
- 成本档：`cost2/`、`cost50/`、`cost100/`
- 稳健性：`robustness/`
- cash-start：`engine_monthly_starts/`
- 多重检验：`multiple_testing/`
- shadow OOS：`shadow_oos_2026_11_12/`
- Spec：`docs/superpowers/specs/2026-11-12-h5-ls23-profit-lock-redistribute-design.md`

Research output only; not an order or a live approval. 当前实盘仍为 `PR2026-10-D-L125-V2`。
