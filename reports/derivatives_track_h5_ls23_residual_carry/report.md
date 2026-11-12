# Atlas20 候选 LS33：LS23 优先 + 剩余 gross funding carry

日期：2026-11-12
候选：`PR2026-11-LS33-H5-LS23-RESIDUAL-CARRY-LONG60`
对照：`PR2026-11-LS33C-H5-LS23-LONG60-CONTROL`
状态：**rejected at 100bps cost gate（2/20/50bps 强，100bps 失败）**
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS33 保留冻结 LS23 作为最高优先级多空 book，只把未使用、非重叠的 gross 分配给 LS31
市场中性 funding carry。20bps：

| 策略 | 终值 | Sharpe | MDD | 强平 | max observed gross | breach hours |
|---|---:|---:|---:|---:|---:|---:|
| L125 | 40.2200x | 1.7330 | -40.65% | 0 | — | 0 |
| LS23 | 61.9150x | 1.9448 | -39.84% | 0 | 1.3308x | 0 |
| LS33C LONG60 control | 61.9150x | 1.9448 | -39.84% | 0 | 1.3308x | 0 |
| **LS33 residual carry** | **80.6764x** | **2.0566** | **-39.19%** | **0** | 1.4420x | **0** |

LONG60 control 与 LS23 的日收益完全相同，所以 20bps 增量来自 carry，而不是 buffer。年度收益：

| 年份 | LS23 | LS33 |
|---|---:|---:|
| 2022 | +23.71% | **+25.25%** |
| 2023 | +264.98% | 262.29% |
| 2024 | +80.33% | **+112.61%** |
| 2025 | +194.07% | **+213.89%** |
| 2026 | +158.57% | **+166.42%** |

carry 平均只占用 **0.2201x NAV**，60.2% 的 target event 能用满 0.25x；base gross 平均
0.5188x，说明 residual budget 真实存在。carry 与 LS23 日收益相关性约 0.9905，增量主要来自
2022 和 2024–2026。

## 二、四档成本

| 成本 | LS23 终值 | LS33 终值 | LS23 Sharpe | LS33 Sharpe | LS23 MDD | LS33 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 84.4362x | **124.0468x** | 2.0719 | **2.2326** | -37.57% | **-36.07%** |
| 20bps | 61.9150x | **80.6764x** | 1.9448 | **2.0566** | -39.84% | **-39.19%** |
| 50bps | 36.8788x | **39.3242x** | 1.7319 | **1.7612** | -43.45% | -44.07% |
| 100bps | **15.5037x** | 11.8172x | **1.3745** | 1.2648 | **-49.48%** | **-52.87%** |

2/20/50bps 终值和 Sharpe 均高于同成本 L125 与 LS23；但 100bps 终值、Sharpe 和 MDD 三项都失败，
并越过 50% MDD kill line。按预注册，**不能因为前三档很强就放宽 100bps 门**。

**判定：rejected at cost gate。** 不运行 funding stress、路径、冷启动或 PBO/RC/DSR；不扫描
carry count/weight/lookback、gross priority、stop 或 buffer。保留 LS33 作为“residual carry 有真实
alpha、但高换手成本未解决”的研究资产。

## 三、预注册与实现

- Spec：`docs/superpowers/specs/2026-11-12-h5-ls23-residual-carry-design.md`
- Spec SHA-256：`7afd165ba27aa5d8edde18139bd59c1a054730b44ad96c30f4c925ab003f2983`
- 新增 `combine_signed_book_with_residual_sleeve`：base book 优先；carry 移除所有与 base 同资产
  的腿；剩余 gross = `1.50 - base_gross`；carry 按比例缩放；base 从不被反向缩放。
- LS33C control 证明 60% long buffer 本身不改变 LS23 的收益路径。

## 四、复现

```bash
# primary 20bps
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS33-H5-LS23-RESIDUAL-CARRY-LONG60 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_residual_carry

# 60% buffer-only control
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS33C-H5-LS23-LONG60-CONTROL \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_residual_carry/control
```

四档成本汇总：`reports/derivatives_track_h5_ls23_residual_carry/cost_summary.csv`。
