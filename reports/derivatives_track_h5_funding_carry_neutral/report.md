# Atlas20 候选 LS30：H5 + 市场中性 funding carry sleeve

日期：2026-11-12
候选：`PR2026-11-LS30-H5-FUNDING-CARRY-NEUTRAL`
状态：**rejected（1 次 long 强平 + gross breach）**
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS30 在 H5 1.25x 上叠加一个 0.25x gross 的市场中性 funding carry sleeve：PIT Top20 非 H5
成员中，7D funding 最低 2 币做多、最高 2 币做空，每腿 6.25% NAV，周频调仓。20bps：

| 策略 | 终值 | Sharpe | MDD | 强平 | max observed gross | breach hours |
|---|---:|---:|---:|---:|---:|---:|
| L125 | 40.2200x | 1.7330 | -40.65% | 0 | — | 0 |
| LS30 | **48.9409x** | **1.8110** | **-40.34%** | **1** | **1.5103x** | **26** |

收益和 Sharpe 均高于 L125，回撤略好，但风险门槛失败：

- 2022-05-11 DOT long 从 17.5681 跌到 8.4220，越过 50% long buffer 的理论强平价 8.4263；
- observed gross 最大 1.5103x，超过 1.50x hard cap；
- 26 个 breach hours。

因此不运行 2/50/100bps、funding stress、路径、冷启动或 PBO/RC/DSR；不扫描 funding lookback、
rank、count、腿权重或 min_assets。

## 二、预注册与实现

- Spec：`docs/superpowers/specs/2026-11-12-h5-funding-carry-neutral-sleeve-design.md`
- Spec SHA-256：`69b3c481b0bea714c730236e1150698c09b2b8e4da4cf77478f3461f11b63410`
- carry：7D mean funding，lowest 2 long / highest 2 short，每腿 0.0625x NAV，总 0.25x gross
- 周频 7D，min_assets 8，min_settlements 3；short stop 20%；T+1 +3h
- 新增 `build_cross_sectional_funding_carry_schedule`、`route_signed_sleeve_with_long_exclusions`
  和 `combine_long_with_signed_sleeve`

## 三、判定

**rejected。** 收益改善不能抵消 long 强平和 gross breach。失败后停止该 carry sleeve 参数搜索；
LS31 只作为已预注册的 60% long-buffer 风险修正对照，不继续扫 buffer。

## 四、复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS30-H5-FUNDING-CARRY-NEUTRAL \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_funding_carry_neutral
```
