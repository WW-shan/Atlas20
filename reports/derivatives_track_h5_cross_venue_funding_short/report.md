# Atlas20 候选 LS24：H5 利润保护 + 跨所 funding 确认空头

日期：2026-11-12
候选：`PR2026-11-LS24-H5-PROFIT-LOCK-CROSS-VENUE-SHORT`
状态：**rejected（20bps 终值和 Sharpe 低于 LS23）**
实盘：**不接；当前 `PR2026-10-D-L125-V2` 不变**

## 一、结论

LS24 在 LS23 上只加一个独立信息源：每个空头候选必须同时得到 Binance 和 Bybit 的正 funding
确认。空头分数取两所最近 3 个 settlement 均值的**逐元素最小值**；任一 venue 缺失或不足 3 个
settlement，该资产不做空。

20bps 主样本：

| 指标 | LS23 | LS24 |
|---|---:|---:|
| 终值 | **61.9150x** | 52.7881x |
| Sharpe | **1.9448** | 1.8860 |
| MDD | -39.84% | **-39.71%** |
| 强平 | 0 | 0 |
| max observed gross | 1.3308x | **1.3029x** |
| gross breach hours | 0 | 0 |
| short open / stop | 335 / 29 | 343 / 27 |
| funding total | -0.7465 | **-0.5359** |

跨所确认确实降低了 funding 成本和 short stop 数，但没有把空头选择转成更高的收益或 Sharpe；
终值和 Sharpe 都低于 LS23，按预注册第一、第二门槛直接失败。

实现口径补充：funding 确认在每周目标事件上评估，和 LS12 一样，已停止的腿可以在下一次周度
rebalance 前从同一个 target 重新开仓。全样本 343 个 short open 中有 4 个这类 stale re-entry
在开仓时点的 funding 下界已转负；它们不是新的周度候选，也没有被事后过滤。这个行为与 LS12
的 stop/re-entry 机制一致，但会削弱“每次开仓都重新确认 funding”的强解释。

## 二、预注册与勘误

- 原 Spec：`docs/superpowers/specs/2026-11-12-h5-cross-venue-funding-short-design.md`
- 原 spec 文件 SHA-256：`f5200669908cf4a28b053be79ee1d697e6ae191fea0b9b7b2faf533774397091`
- 注册 canonical spec JSON SHA-256：`dbf834fdd99e6a7f33bec508f846354d430e62ef72c0aa9b413f0695bd353f99`
- registration hash：`a933acdcb585464733d338f82bcd98e4d47d045553933d9c2f456ae71de1c978`
- 覆盖率审计时点勘误：`docs/superpowers/specs/2026-11-12-h5-cross-venue-funding-short-design-erratum.md`

审计修正后，LS12 的 335 个空头 episode 中 Bybit 可用 **307 个（91.6%）**，高于预注册 90%
门槛；bear 297 个、Bybit 可用 270 个、两所同时为正 138 个；non-bear 38 个、Bybit 可用 37 个、
两所同时为正 34 个。原 spec 中的 92.8%/288/47 是错误时点，已由勘误取代；规则和 registration
hash 未改。

## 三、实现修正

首轮 LS24 使用精确 index union 对齐 Binance/Bybit settlement，Binance 的毫秒时间戳导致大量
NaN，输出被隔离在 `run_status/invalidated_misaligned_cross_venue/`，不计入正式结果。正式实现
把两所 settlement 先 floor 到分钟，再取最小值；不足 3 个 settlement 仍为不合格。官方结果来自
修复后的运行。

## 四、失败后的停止规则

LS24 已触发 20bps 终值和 Sharpe 硬失败，因此按预注册：

- 不运行 2/50/100bps；
- 不运行 3x funding stress、删除年份、滚动窗口、45 路径、冷启动或 PBO/RC/DSR；
- 不扫描 settlement 数、lookback、min/mean/median 组合、正阈值、basket size、stop、buffer、
  regime 窗口或组合权重；
- 不修改 LS23 的 provisional 状态，不接执行器。

## 五、最终判定

**LS24 rejected。** 跨所 funding 确认是一个有经济含义的新信息源，但在 Top20 + isolated margin
口径下，它降低的是 funding 成本和少量 stop，不是提高收益；它没有修复 LS23 的收益/Sharpe，
因此该分支停止。下一步必须换独立信息源，不能继续拆 funding 参数。

## 六、复现

```bash
.venv/bin/python scripts/audit_cross_venue_funding.py

.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS24-H5-PROFIT-LOCK-CROSS-VENUE-SHORT \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --bybit-funding-dir data/raw/alternative_funding/bybit \
  --output-dir reports/derivatives_track_h5_cross_venue_funding_short
```
