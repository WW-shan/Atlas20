# Atlas20 候选 LS35：LS23 优先 + true-carry residual sleeve

日期：2026-11-12
候选：`PR2026-11-LS35-H5-LS23-RESIDUAL-CARRY-SIGN`
状态：**rejected at 100bps cost gate**
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS35 在 LS33 residual carry 上只增加经济定义上的 true-carry 条件：long 必须 funding<0，short 必须
funding>0，不足两腿时持有更少或现金。

| 成本 | LS23 终值 | LS35 终值 | LS23 Sharpe | LS35 Sharpe | LS23 MDD | LS35 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 20bps | 61.9150x | **74.0476x** | 1.9448 | **2.0383** | -39.84% | -39.50% |
| 100bps | **15.5037x** | 11.2205x | **1.3745** | 1.2515 | **-49.48%** | **-52.15%** |

20bps：0 强平、0 gross breach、max observed gross 1.4420x。100bps：11.2205x / 1.2515 /
-52.15%，低于 LS23 三项门槛并越过 50% MDD kill line。true-carry 过滤把 20bps 费用从 LS33 的
5.4067 降到 4.8798，但仍不足以修复高成本尾部。

**判定：rejected。** 不运行 2/50bps、funding stress、路径、冷启动或 PBO/RC/DSR；不扫描 sign
threshold、count、weight、lookback 或 buffer。

## 二、预注册与实现

- Spec：`docs/superpowers/specs/2026-11-12-h5-ls23-residual-carry-sign-design.md`（实际路径见报告目录）
- Spec SHA-256：`07ad42e900af3ddafdbba99a1e24a864886bff8417d78ea9fd0fad99401a44c3`
- 只加入 strict sign：long score<0、short score>0；exact lowest/highest ranking
- LS23 base、residual budget、60% long buffer、20% short stop、T+1 +3h 全部冻结

## 三、复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS35-H5-LS23-RESIDUAL-CARRY-SIGN \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_residual_carry_sign
```
