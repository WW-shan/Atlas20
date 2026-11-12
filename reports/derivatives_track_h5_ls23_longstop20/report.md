# Atlas20 LS41：LS23 + 20% 多头逐腿止损

日期：2026-11-12
候选：`PR2026-11-LS41-H5-LS23-LONGSTOP20`
状态：**rejected at 20bps primary gate**
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS41 在冻结 LS23 上给每个 H5 多头腿增加 20% adverse stop：从平均入场价回撤 20% 时按 Bitget
逐小时 mark 路径止损，先结算 funding，再执行 long/short stop，最后才检查 isolated liquidation；
止损后的腿只能在下一次 H5 target event 重新进入。20% 沿用现有 short stop，不是新扫描阈值。

20bps 主样本：

| 策略 | 终值 | Sharpe | MDD | 强平 | long stops | short stops | fees total |
|---|---:|---:|---:|---:|---:|---:|---:|
| LS23 | **61.9150x** | **1.9448** | **-39.84%** | 0 | 0 | 29 | 3.1262 |
| LS41 | 57.2522x | 1.9036 | -39.835% | 0 | **19** | 29 | **2.9556** |

LS41 保住了回撤，略微降低费用，没有强平；但终值下降约 7.5%，Sharpe 低 0.0412。预注册的终值和
Sharpe 两条主门槛失败。

## 二、机制判读

- 19 次多头止损说明该风险控制确实改变了执行；
- 止损减少了一部分后续损失，也反复切断随后恢复或继续上涨的 H5 龙头；
- 由于只能等下一次 H5 target event 再入场，止损失去了路径内的再暴露机会；
- max observed gross 1.3308x、0 gross breach、0 强平，说明失败不是执行或 gross 问题；
- MDD 没有实质改善，说明该样本中 20% adverse stop 并没有解决主要的组合级回撤来源。

**判定：rejected。** 不运行 2/50/100bps、funding stress、路径、冷启动或 PBO/RC/DSR；不扫描
10%/15%/25%/30%、ATR stop、trailing stop、不同 re-entry delay 或组合层 stop。停止 H5 多头固定
百分比止损家族，保留 LS23 和现有 20% short stop 不变。

## 三、复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS41-H5-LS23-LONGSTOP20 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_longstop20
```
