# Atlas20 候选 LS31：H5 + market-neutral funding carry（60% long buffer）

日期：2026-11-12
候选：`PR2026-11-LS31-H5-FUNDING-CARRY-LONG60`
状态：**rejected（50/100bps 成本失败；20bps 风险修正成功）**
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS31 与 LS30 完全相同，只把 long buffer 从 50% 提高到 60%，处理 LS30 在 DOT 上出现的
50% long 强平。四档成本：

| 成本 | L125 终值 | LS31 终值 | L125 Sharpe | LS31 Sharpe | L125 MDD | LS31 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 50.6408x | **70.9970x** | 1.8249 | **1.9655** | -38.42% | **-37.11%** |
| 20bps | 40.2200x | **48.9593x** | 1.7330 | **1.8168** | -40.65% | **-40.13%** |
| 50bps | **27.3725x** | 26.3191x | **1.5790** | 1.5675 | **-44.20%** | -44.89% |
| 100bps | **14.3794x** | 9.3188x | **1.3204** | 1.1491 | **-50.02%** | **-56.40%** |

20bps 风险修正成功：**0 强平、0 gross breach hours**，max observed gross **1.4364x**；carry
sleeve 的 long leg 不再被 50% buffer 直接清算。2/20bps 终值、Sharpe 和 MDD 均优于 L125。

但 50bps 起终值和 Sharpe 低于 L125，100bps MDD -56.40%，成本门槛失败。因此不能把 LS31
称为可上线策略；它是有价值的低换手 carry 研究资产，但不是 LS23 的替代。

## 二、预注册与实现

- Spec：`docs/superpowers/specs/2026-11-12-h5-funding-carry-long60-design.md`
- Spec SHA-256：`2a5b3ce2ad123546d48d7e296d5dfbc7338a06ef510c7a547787f0d1b9915e5d`
- 与 LS30 相同：7D funding 最低 2 多 / 最高 2 空，每腿 6.25% NAV，20% short stop
- 唯一变化：long buffer 50% → 60%
- 0 强平、0 gross breach；max observed gross 1.4468x（100bps 口径）

## 三、判定

**rejected。** 20bps 通过收益、Sharpe、MDD、强平和 gross；50/100bps 成本门槛失败。按预注册
不扫描 55/65/70% long buffer、不扫 funding lookback/rank/count/腿权重，不运行 funding stress、
路径、冷启动或 PBO/RC/DSR；不修改实盘。

## 四、复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS31-H5-FUNDING-CARRY-LONG60 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_funding_carry_long60
```

四档汇总：`reports/derivatives_track_h5_funding_carry_long60/cost_summary.csv`。
