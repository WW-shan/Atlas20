# Atlas20 候选 LS36：LS23 优先 + 剩余 gross short-only carry

日期：2026-11-12
候选：`PR2026-11-LS36-H5-LS23-RESIDUAL-SHORT-CARRY`
状态：**rejected at 100bps cost gate**
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS36 把 LS33 的 carry 缩减为只做空头腿：highest positive 7D funding 2 币，每腿 6.25% NAV，
总 carry gross 最多 0.125x，long carry 关闭。base LS23、residual budget、60% long buffer、
20% short stop 和 T+1 +3h 全部不变。

| 成本 | LS23 终值 | LS36 终值 | LS23 Sharpe | LS36 Sharpe | LS23 MDD | LS36 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 20bps | 61.9150x | **69.5943x** | 1.9448 | **2.0159** | -39.84% | -39.94% |
| 100bps | **15.5037x** | 12.6244x | **1.3745** | 1.3029 | **-49.48%** | **-51.37%** |

20bps：0 强平、0 gross breach、max observed gross 1.4368x，费用 4.2032（低于 LS33 的 5.4067）。
100bps：12.6244x / 1.3029 / -51.37%，仍低于 LS23 三项门槛并越过 50% MDD kill line。

**判定：rejected。** short-only carry 的增量是真实的，但 base LS23 在 100bps 已接近成本尾部，
任何持续 weekly carry 换手都会把组合推过门槛；不扫描 short count、weight、lookback、stop 或
buffer。下一步应研究低频 rebalance，而不是继续加/减单腿。

## 二、预注册与实现

- Spec：`docs/superpowers/specs/2026-11-12-h5-ls23-residual-short-carry-design.md`
- Spec SHA-256：`77fe71cabe3cdfee63087f7cc1acd1af115131324fda49e5e738b336128f96ce`
- `long_enabled=False`、`short_enabled=True`、`carry_sign_only=True`
- 只删除 long carry，不改变 short 腿的 count/weight/rank

## 三、复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS36-H5-LS23-RESIDUAL-SHORT-CARRY \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_residual_short_carry
```
