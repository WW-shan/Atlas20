# LS104 S050/G175/M090 实盘候选报告

- Track: `PR2026-11-LS104-H5-LS23-PROFITLOCK-STRONGER21-S050-G175-M090`
- 基线信号: `PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21`
- 目标: H5 long 1.25x + short request 0.50x，总 gross cap 1.75x
- 执行: 4x isolated venue leverage；每腿 50% explicit buffer；组合 margin cap 0.90
- 时钟: T+1 01:05 UTC / 09:05 Beijing
- 空头保护: 每个 open/increase 使用 20% mark-price market stop

## 成本压力

以下均为同一 01:05 floor、Bitget exact funding、contract quantization 和
isolated-margin 引擎的 live-parity 结果。20/50bps 是硬压力，100bps 只作诊断。

| Cost | Terminal | Sharpe | MDD | Max observed gross | Gross breach hours | Liquidations |
|---:|---:|---:|---:|---:|---:|---:|
| 20bps | 77.8524x | 1.9637 | -40.77% | 1.4986x | 0 | 1 |
| 50bps | 41.4492x | 1.7174 | -46.55% | 1.4961x | 0 | 1 |
| 100bps diagnostic | 19.09x | 1.406 | -52.77% | 未用于晋级 | 未用于晋级 | 继承 1 |

LS45-G125 的同口径对照为 20bps 65.2592x / 1.9792 / -34.06%，50bps
39.3339x / 1.7694 / -39.75%。LS104 提高了 20/50bps 终值，但 Sharpe 略低、MDD
更深；这是负责人基于未来低波动、存量博弈环境主动接受的 aggressive allocation，
不是风险改善结论。

## 离散性、成交与尾部

- 20bps: order skips 402，quantizations 1648，margin events 1586。
- 50bps: order skips 437，quantizations 1613，margin events 1586。
- 两次运行的唯一强平均为继承的 XRP long，2025-02-03 02:00 UTC；没有新增强平。
- 20/50bps 均 0 gross breach hours；历史最高观测 gross 约 1.50x，低于 1.75x cap。

## 当前 live 激活账本

`reports/ls45_live_g175/manifest.json` 已冻结：

- `tracked_spec` = LS104
- `short_scale` = 2.0
- `max_total_gross` = 1.75
- `max_margin_utilization` = 0.90
- `venue_leverage` = 4.0
- `targets_sha256` = `2ef4e701d29376ec0073bd589424dbcf30525914f7eb587459de88a263863930`
- 最新信号日 2026-11-13：BCH/HYPE/NEAR/ZEC 各 -0.125，short gross 0.50x

数据审计 0 hard failure / 0 warning；信号等价性 72/72 行、0 差异。

## 已知限制

- 12 个月独立 OOS 尚未完成；2022-01-01 至 2026-09-21 是当前可用 live-parity 样本。
- 50bps 下 MDD 为 -46.55%，离 50% kill line 只有约 3.45 个百分点。
- 4x 是 venue leverage ceiling，不是 4x 实际仓位；实际 gross 由目标账本和 0.90 margin cap 控制。
- 本次上线要求每个 open/increase 的 venue stop 确认、4x/isolated 回读、最终保证金至少 45%
  以及 gross/margin cap 全部通过；任何一项失败都必须 partial + 下一窗口 retry，不得宣告完成。
