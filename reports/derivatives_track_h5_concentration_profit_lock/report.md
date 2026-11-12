# Atlas20 候选 LS29：H5 集中度条件利润保护 + LS12 空头

日期：2026-11-12
候选：`PR2026-11-LS29-H5-CONCENTRATION-PROFIT-LOCK-REGIME-SHORT`
状态：**rejected（20bps 收益和 Sharpe 均低于 LS23）**
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS29 只把 LS22 的利润保护加上一个集中度条件：只有最大多头腿权重至少 25% NAV 时才减半，
希望避免像 2024 SHIB 那样在不足 25% 的龙头腿上进行过早削减。20bps 结果：

| 策略 | 终值 | Sharpe | MDD | trim | max observed gross | 强平 | gross breach |
|---|---:|---:|---:|---:|---:|---:|---:|
| LS23 | **61.9150x** | **1.9448** | **-39.84%** | 57 | 1.3308x | 0 | 0 |
| LS29 | 60.4392x | 1.9325 | -39.84% | 41 | 1.3308x | 0 | 0 |

集中度条件把 trim 从 57 次降到 41 次，但没有改善 2024 右尾补偿；终值低 2.38%，Sharpe 低
0.0123，MDD 相同。20bps 第一、第二门槛失败，按预注册不运行 2/50/100bps、funding、路径、
冷启动或多重检验。

## 二、预注册与实现

- Spec：`docs/superpowers/specs/2026-11-12-h5-concentration-profit-lock-regime-short-design.md`
- Spec SHA-256：`2ff20b3d86d83f309106294f864d6d8fd6e3e704a46b1de0a95338e1347d7a16`
- `min_leader_weight=0.25`，其余 LS22 参数 21D / 100% / 0.5 不变
- 空头、gross、stop、buffer、执行时点和数据口径全部沿用 LS23
- 没有扫描 20/30/35% 或其他门槛

## 三、判定

**rejected。** 集中度条件利润保护家族停止；保留 LS22/LS23 作为已验证的对照。不修改实盘。

## 四、复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS29-H5-CONCENTRATION-PROFIT-LOCK-REGIME-SHORT \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_concentration_profit_lock
```
