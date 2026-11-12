# LS23 Shadow OOS：2026-09-22 → 2026-11-11

- 研究状态：**provisional / research-only**，不接实盘，不修改 `PR2026-10-D-L125-V2`
- 窗口：51 个日行，50 个有效收益观测（首行是引擎初始化点）
- OOS mark：Bitget `oos_refresh_20261112`，88 个资产，窗口内 **0 missing hours、0 gap**
- warmup mark：`merged_20261009`；OOS 快照覆盖重叠部分
- funding：zero 上界与 Bitget exact 两套；exact funding 最新到 `2026-11-12 12:00 UTC`
- 成本：20bps；T+1 03:00 UTC；LS23 与 L125 同一窗口、同一 mark、同一执行
- 空头 sleeve：BTC 在 200D 上方，两组 LS23 均为 **0 次空头开仓**；本窗口只检验 LS22 利润保护

## 零 funding 上界

| arm | multiple | Sharpe | MDD | max gross | trims |
| --- | ---: | ---: | ---: | ---: | ---: |
| L125 | 0.9484x | -0.2743 | -17.47% | 0.8149x | 0 |
| LS23 | 0.9403x | -0.5584 | -17.47% | 0.8153x | 8 |

LS23 比 L125 低 -0.85%，
Sharpe 低 0.2841；
MDD 基本不变。8 次 trim 没有带来正增量。

## Bitget 精确 funding

| arm | multiple | Sharpe | MDD | funding total | fees | trims |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| L125 | 0.9440x | -0.3270 | -17.65% | -0.4808% | 1.1656% | 0 |
| LS23 | 0.9365x | -0.6125 | -17.65% | -0.4088% | 1.2690% | 8 |

精确 funding 下，LS23 仍比 L125 低
-0.79%，
Sharpe 低 0.2855，
MDD 略差 0.00pp。

## 判定

- 51 天只覆盖 12 个月 OOS 门槛的约 **14.0%**，且 LS23 的空头 sleeve 仍未触发，不能外推到完整 LS23。
- 新增的 2026-11-11 日收益为 0，所以终值倍数和 MDD 与 50 天版本相同；Sharpe/CAGR 因多一个零收益观测而变化。
- 零 funding 和 Bitget exact 两种口径都显示 LS23 略低于 L125；保持 provisional，不 promotion、不修改实盘。
- 继续研究应扩大真实 OOS、等待空头 regime 触发，或寻找真正独立且与 isolated margin 兼容的 alpha。

## 数据链路修复

旧默认目录 `merged_oos_20261009` 在窗口内有 4 个全体资产共同缺失的小时
（2026-09-22 14:00、09-26 19:00、10-01 00:00、10-05 05:00），共 352 个资产小时缺口。
本次新快照 `oos_refresh_20261112` 以 `--force` 重新拉取 88 个 mark 序列，88/88 完整，0 missing。
shadow manifest/summary 现在同时记录 `raw_dir` 和 `warmup_raw_dir`，默认 raw dir 已切到
`merged_oos_20261112`，避免默认指向已知有缺口的旧树而不自知。
