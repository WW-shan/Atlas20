# Atlas20 候选 LS27：H5 利润保护 + 动态多空预算

日期：2026-11-12
候选：`PR2026-11-LS27-H5-PROFIT-LOCK-DYNAMIC-SHORT`
状态：**rejected（高成本与 gross guard 失败）**
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS27 把 LS22 利润保护、LS12 双空头 router 和 R6 bottom-four 空头合并：两个空头组件各请求
0.25x，目标 total gross 1.48x，1.50x hard gross guard；正常满多头时只能使用 0.25x 空头，
LS22 释放 cash 后才可能扩大短 gross。20bps 表面结果很强：

| 成本 | LS23 终值 | LS27 终值 | LS23 Sharpe | LS27 Sharpe | LS23 MDD | LS27 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 84.4362x | **109.9219x** | 2.0719 | **2.1476** | -37.57% | -38.30% |
| 20bps | 61.9150x | **68.8876x** | 1.9448 | **1.9599** | -39.84% | -41.40% |
| 50bps | 36.8788x | 31.4739x | 1.7319 | 1.6443 | -43.45% | -46.34% |
| 100bps | **15.5037x** | 8.4896x | 1.3745 | 1.1146 | **-49.48%** | **-56.08%** |

20bps 终值和 Sharpe 高于 LS23，MDD 在 5pp 容忍内；但 50bps 终值/Sharpe 已低于 LS23，
100bps 同时跌破 50% MDD kill line，说明新增 bottom-four 换手不具成本生存性。

gross 也不合格：即使使用 1.48x target buffer 和 1.50x hard guard，仍有 **5 个 observed
breach hours**，最大 observed gross **1.5157x**。无 1.50x buffer 的初始版本有 259 个 breach
hours、最大 1.5627x；修正版只是把问题压小，没有闭合。

## 二、预注册与实现

- Spec：`docs/superpowers/specs/2026-11-12-h5-profit-lock-dynamic-short-design.md`
- Spec SHA-256：`5ae61863378fc0e4cf9a220c9fccafc392fee68d3d390c5904dc903cd8af44f6`
- 多头：LS22（21D、100%、0.5）
- 空头：LS12 router + R6 bottom-four，各名义 0.25x，按 unused gross 缩放
- 空头 stop 20%，short buffer 50%，T+1 +3h，missing-mark carry 3h
- 数据：严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip

实现过程中修复了两个研究口径问题：

1. bottom-four 周频短腿在进入 H5 多头或离开 PIT Top20 时必须提前退出，不能等到下一次周频
   调仓；新增 `route_short_schedule_with_long_exclusions`，使 LS27 与 R6 的真实语义一致；
2. 允许 `hard_gross_exposure == max_gross_exposure`，并给 LS27 配置逐小时 gross guard；
   该修改不把 breach 当作合规，只把超额暴露限制在一个可观察的 guard 周期内。

## 三、判定

**rejected。** 失败项：

- 50bps 和 100bps 终值/Sharpe 低于 LS23；
- 100bps MDD -56.08%；
- 仍有 5 个 gross breach hours；
- 未运行 3x funding、年度删除、路径切片、冷启动或 PBO/RC/DSR，因为成本与 gross 已先行失败。

不扫描 bottom-N、stop、target gross、buffer、空头权重、等权比例或 regime 参数。保留组件实现
和报告作为负结果证据，不修改实盘。

## 四、复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS27-H5-PROFIT-LOCK-DYNAMIC-SHORT \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_profit_lock_dynamic_short
```

四档汇总：`reports/derivatives_track_h5_profit_lock_dynamic_short/cost_summary.csv`。
