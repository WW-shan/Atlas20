# Atlas20 候选 LS28：H5 利润保护 + 优先级空头预算

日期：2026-11-12
候选：`PR2026-11-LS28-H5-PROFIT-LOCK-PRIORITY-SHORT`
状态：**rejected（高成本与 gross guard 失败）**
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS28 是 LS27 的低换手修正：LS12 空头优先级最高，最多使用 0.25x；R6 bottom-four 只能在 LS22
利润保护释放出剩余 gross 后才获得仓位。正常满多头时 LS28 应接近 LS23，而不是长期同时持有
两套空头。

20bps 结果仍与 LS27 接近：

| 成本 | LS23 终值 | LS28 终值 | LS23 Sharpe | LS28 Sharpe | LS23 MDD | LS28 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 84.4362x | **110.1001x** | 2.0719 | **2.1494** | -37.57% | -38.19% |
| 20bps | 61.9150x | **68.9318x** | 1.9448 | **1.9612** | -39.84% | -41.32% |
| 50bps | **36.8788x** | 31.5191x | **1.7319** | 1.6457 | **-43.45%** | -46.22% |
| 100bps | **15.5037x** | 8.5055x | **1.3745** | 1.1158 | **-49.48%** | **-56.00%** |

优先级控制没有改变成本曲线：50bps 起低于 LS23，100bps MDD 跌破 50%。gross guard 也未闭合：
目标 1.50x，observed max **1.5219x**，breach hours **82**（100bps 口径）；20bps 为 69 小时、
最大 1.5169x。无强平。

## 二、预注册与实现

- Spec：`docs/superpowers/specs/2026-11-12-h5-profit-lock-priority-short-design.md`
- Spec SHA-256：`fd6098244616203732a2ea9ea8dc81182cefd130a34cf5f9a9945d46ceb2f224`
- 优先空头：LS12 router，最多 0.25x
- 额外空头：R6 bottom-four，只使用剩余 gross
- 总目标/硬上限：1.50x；20% stop、50% buffer、T+1 +3h、missing-mark carry 3h
- 新增 `combine_long_with_priority_short_sleeves`：先 funding priority，再按 residual 给 extra；
  同资产短腿上限 0.25x

## 三、判定

**rejected。** 20bps 收益和 Sharpe 高于 LS23，但 50/100bps 成本门槛失败，100bps MDD 失败，
gross breach 未消除。优先级本身没有把 R6 的高换手成本变成可接受的成本。

不扫描 priority ratio、extra weight、stop、bottom-N、gross buffer 或 regime 参数；不运行
funding/年度/路径/冷启动/多重检验；不修改实盘。

## 四、复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS28-H5-PROFIT-LOCK-PRIORITY-SHORT \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_profit_lock_priority_short
```

四档汇总：`reports/derivatives_track_h5_profit_lock_priority_short/cost_summary.csv`。
