# Atlas20 候选 LS34：LS23 优先 + 剩余 gross carry（空头持有带）

日期：2026-11-12
候选：`PR2026-11-LS34-H5-LS23-RESIDUAL-CARRY-SHORTHOLD`
状态：**rejected at 20bps primary gate（低于 LS33）**
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS34 在 LS33 residual-budget carry 上只改变空头腿：已有空头仍在最高 4 名内就继续持有，跌出才替换；
多头腿保持 lowest 2 精确退出。换手确实下降：

| 指标 | LS33 | LS34 | 变化 |
|---|---:|---:|---:|
| carry target cumulative L1 change | 70.5000x | **58.8750x** | -16.5% |
| long name changes | 440 | 440 | 0% |
| short name changes | 688 | **502** | -27.0% |
| short opens | 629 | **556** | -11.6% |
| fees total @20bps | 5.4067 | **5.1618** | -4.5% |

但 20bps 终值和 Sharpe 下降：

| 策略 | 终值 | Sharpe | MDD | 强平 | max observed gross | breach hours |
|---|---:|---:|---:|---:|---:|---:|
| LS23 | 61.9150x | 1.9448 | -39.84% | 0 | 1.3308x | 0 |
| LS33 | **80.6764x** | **2.0566** | -39.19% | 0 | 1.4420x | 0 |
| LS34 | 77.3635x | 2.0396 | -39.48% | 0 | 1.4424x | 0 |

LS34 低于预注册要求：终值必须 > LS33 的 80.6764x，Sharpe 必须 >= 2.0566。空头持有带减少了
换手，却让部分已经失去 funding 优势的空头多留一周，损失超过节省的成本。

**判定：rejected。** 停止 residual carry 空头持有带家族；不扫描 hold_count 3/5/6/8、long/short
数量、权重或 stop；不运行 2/50/100bps、funding stress、路径、冷启动或 PBO/RC/DSR。

## 二、预注册与实现

- Spec：`docs/superpowers/specs/2026-11-12-h5-ls23-residual-carry-shorthold-design.md`
- Spec SHA-256：`e2848596071ad91d7d8be3cfb2ff9b6bd5541cb497ceda7faf017f1e4da83e93`
- `build_cross_sectional_funding_carry_schedule` 新增 `hold_long` / `hold_short`，当前候选固定为
  `hold_long=False`、`hold_short=True`、`hold_count=4`
- 其余 LS33 residual-budget、60% long buffer、20% short stop、T+1 +3h 全部不变

## 三、复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS34-H5-LS23-RESIDUAL-CARRY-SHORTHOLD \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_residual_carry_shorthold
```
