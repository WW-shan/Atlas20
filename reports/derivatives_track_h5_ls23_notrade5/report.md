# Atlas20 候选 LS38：LS23 + 5% NAV same-side no-trade band

日期：2026-11-12
候选：`PR2026-11-LS38-H5-LS23-NOTRADE5`
状态：**rejected at 20bps primary gate**
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS38 在冻结 LS23 上只增加 5% NAV 同方向 no-trade band：开仓、清仓、反手和 gross guard
仍精确执行。它确实降低了 base turnover：

| 策略 | 20bps 终值 | Sharpe | MDD | fees total | short opens | short stops |
|---|---:|---:|---:|---:|---:|---:|
| LS23 | **61.9150x** | **1.9448** | -39.84% | 3.1262 | 335 | 29 |
| LS38 | 54.5335x | 1.9102 | **-38.69%** | **2.5007** | 333 | 27 |

但终值低约 11.9%、Sharpe 低约 0.0346，低于预注册的 LS23 主门槛。no-trade band 通过保留
旧权重降低了费用，也牺牲了 H5 利润保护和 LS12 router 的目标响应，净效果为负。

**判定：rejected。** 不运行 100bps、funding stress、路径、冷启动或 PBO/RC/DSR；不扫描 1%/
2.5%/5%/7.5%/10%/15%，不尝试只对多头或只对空头设置容差。停止 LS23 no-trade 家族，不修改实盘。

## 二、预注册与实现

- Spec：`docs/superpowers/specs/2026-11-12-h5-ls23-notrade5-design.md`
- Spec SHA-256：`58dcedc6e38a0788e92178817947d7bb05de08e4f789794ee23a34a2e98e9fbd`
- 只改变执行容差：`rebalance_no_trade_band=0.05`
- LS23 的选币、利润保护、LS12 router、20% stop、50% buffer、T+1 +3h 全部冻结

## 三、复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS38-H5-LS23-NOTRADE5 \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_notrade5
```
