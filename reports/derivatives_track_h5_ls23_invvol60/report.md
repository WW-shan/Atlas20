# Atlas20 LS40：LS23 + 60D 逆波动率多头权重

日期：2026-11-12
候选：`PR2026-11-LS40-H5-LS23-INVVOL60`
状态：**rejected at 20bps primary gate**
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS40 在冻结 LS23 的 H5 多头事件内部，用 60D 日对数收益逆波动率重新分配同一事件 gross；不增加
资产、gross 或杠杆，LS22 利润保护在重分配之后执行，LS12 双空头 router 完全不变。运行前审计显示
542 个目标事件中有 380 个多资产事件，所有事件都有完整 60D 历史，因此该试验确实改变了 book。

20bps 主样本：

| 策略 | 终值 | Sharpe | MDD | 强平 | max gross | gross breach | fees total |
|---|---:|---:|---:|---:|---:|---:|---:|
| LS23 | **61.9150x** | **1.9448** | **-39.84%** | 0 | 1.3308x | 0 | 3.1262 |
| LS40 | 29.8565x | 1.7063 | -41.30% | 0 | 1.3229x | 0 | **2.3195** |

LS40 降低了费用和部分 gross，但没有保留 H5 的收益：终值约为 LS23 的 48%，Sharpe 低 0.2385，
MDD 还恶化约 1.46pp。预注册的第一组三条 gate 全部失败。

## 二、机制判读

- 380/542 个事件发生重分配，累计 L1 变化 123.0207；单事件 gross 误差最大仅 `2.22e-16`；
- 0 个事件因波动率历史不足而 fail-closed；
- 55 次 LS22 profit-lock trim，LS23 为 57 次；
- 短头 open 335、stop 29、max funded short 0.25x，均与 LS23 相同。

因此结果不是 sleeve 没有运行，也不是风险控制拒绝交易。H5 原始权重反映 12 个相位 sleeve 的选币
共识和信号合流；逆波动率把权重从高波动但高信号共识的资产移走，等价于把 alpha 当成纯风险噪声
处理。费用下降没有补偿选币信息损失。

**判定：rejected。** 不运行 2/50/100bps、funding stress、路径、冷启动或 PBO/RC/DSR；不扫描
20/30/90/120D、等权、最小方差、协方差收缩、asset cap 或部分资产加权变体。保留 LS23 为 incumbent。

## 三、复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS40-H5-LS23-INVVOL60 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_invvol60
```
