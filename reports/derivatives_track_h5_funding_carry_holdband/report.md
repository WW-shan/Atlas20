# Atlas20 候选 LS32：H5 + 2x-entry-count funding carry 持有带

日期：2026-11-12
候选：`PR2026-11-LS32-H5-FUNDING-CARRY-HOLD4-LONG60`
状态：**rejected（20bps 低于 LS23，且仍有 1 次 long 强平）**
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS32 在 LS31 的 60% long buffer 上，只给 carry sleeve 增加一个预注册的 2x entry-count
持有带：已有腿仍在最低/最高 4 名内就继续持有，跌出持有带才替换。它确实减少了机械换腿：

| 指标 | LS31 | LS32 | 变化 |
|---|---:|---:|---:|
| carry target cumulative L1 change | 70.5000x | **48.8750x** | **-30.7%** |
| long name changes | 440 | **280** | -36.4% |
| short name changes | 688 | **502** | -27.0% |
| short opens | 381 | **294** | -22.8% |

但 20bps 结果没有转化成正收益提升：

| 策略 | 终值 | Sharpe | MDD | 强平 | max observed gross | breach hours |
|---|---:|---:|---:|---:|---:|---:|
| L125 | 40.2200x | 1.7330 | -40.65% | 0 | — | 0 |
| LS23 incumbent | **61.9150x** | **1.9448** | **-39.84%** | 0 | 1.3308x | 0 |
| LS31 | 48.9593x | 1.8168 | -40.13% | 0 | 1.4364x | 0 |
| LS32 | 44.3989x | 1.7772 | -40.09% | **1** | 1.4331x | 0 |

LS32 的终值和 Sharpe 都低于 LS23，第一组研究价值门槛失败；同时 60% buffer 下仍出现 DOT
long 强平：

- entry price **20.0831785**；
- trigger timestamp **2022-05-12 05:00 UTC**；
- execution price **7.4284490**，跌幅约 **63.0%**；
- 持有带让 DOT 比 LS31 的精确排名退出多留了一段，因此 60% buffer 没有阻止该腿进入强平边界。

这不是实现错误，而是持有带降低了退出及时性。**判定：rejected。** 不扫描 hold_count 3/5/6/8，
不继续该 carry 持有带家族；不运行 2/50/100bps、funding stress、路径、冷启动或 PBO/RC/DSR。
不修改实盘。

## 二、预注册与实现

- Spec：`docs/superpowers/specs/2026-11-12-h5-funding-carry-holdband-design.md`
- Spec SHA-256：`7b87fb5684f21458704c884dadabe30576ca37612d4b2949a06820d6eb1cdd84`
- carry：7D mean funding，lowest 2 long / highest 2 short，每腿 0.0625x NAV
- hold band：当前腿在 lowest/highest 4 名内继续持有；跌出才换
- 其余 LS31 规则不变：long buffer 60%、20% short stop、T+1 +3h、hard gross 1.50x

## 三、顺带修复的记录问题

此前 LS30/LS31 的 `manifest.json` 只写了全局 `FROZEN_CONFIG`，没有记录实际 carry 配置，
且 LS31 的 frozen long buffer 误记为 0.5。此次新增 `_trial_frozen_config`，让后续 manifest
写入实际 long buffer、carry 参数和 `funding_carry_market_neutral` sleeve 标签，并有回归测试。

## 四、复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS32-H5-FUNDING-CARRY-HOLD4-LONG60 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_funding_carry_holdband
```
