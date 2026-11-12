# Atlas20 候选 LS37：LS23 优先 + 14D residual carry

日期：2026-11-12
候选：`PR2026-11-LS37-H5-LS23-RESIDUAL-CARRY-14D`
状态：**rejected at 100bps cost gate**
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS37 只把 LS33 residual carry 的 rebalance 从 7D 改为 14D；funding score 仍为 7D mean，
count=2、每腿 6.25%、exact ranking、60% long buffer 和 20% short stop 全部冻结。14D 由预注册的
funding rank persistence 选择：7D rank corr 0.6655、14D 0.5576、21D 0.5004、28D 0.4726。

| 成本 | LS23 终值 | LS37 终值 | LS23 Sharpe | LS37 Sharpe | LS23 MDD | LS37 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 20bps | 61.9150x | **73.2343x** | 1.9448 | **2.0172** | -39.84% | -41.26% |
| 100bps | **15.5037x** | 12.8731x | **1.3745** | 1.2993 | **-49.48%** | **-52.75%** |

20bps 0 强平、0 gross breach、max observed gross 1.4429x；费用 4.6678（低于 LS33 的 5.4067）。
100bps 仍低于 LS23 三项门槛并越过 50% MDD kill line。

**判定：rejected。** 14D 低频化降低了费用，但 base LS23 在 100bps 已接近边界；停止 carry 低频
rebalance 家族，不扫描 21D/28D 或其他频率。不修改实盘。

## 二、预注册与实现

- Spec：`docs/superpowers/specs/2026-11-12-h5-ls23-residual-carry-14d-design.md`
- Spec SHA-256：`b4ee432893bae26bfae23b04ff803042bd063533867109337c71746127dde7d3`
- 唯一变化：`rebalance_days` 7 → 14；其余 LS33 构造不变
- LS23 base、residual budget、long buffer、stop 和 execution 全部冻结

## 三、复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS37-H5-LS23-RESIDUAL-CARRY-14D \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_residual_carry_14d
```
