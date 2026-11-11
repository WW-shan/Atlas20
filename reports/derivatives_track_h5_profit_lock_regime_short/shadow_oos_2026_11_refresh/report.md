# LS23 Shadow OOS 复跑：2026-09-22 → 2026-11-10

- 研究状态：**provisional / research-only**，不接实盘，不修改 `PR2026-10-D-L125-V2`
- 本报告取代旧 `shadow_oos_2026_11/` 的 partial-funding 读数
- 完整日：50 个日行，49 个有效收益观测（首行是引擎初始化点）
- OOS mark：Bitget `merged_oos_20261112`，88 个资产，窗口内 **0 missing hours**，max gap 1h
- 状态 warmup：`merged_20261009` 完整历史；OOS 快照覆盖重叠部分
- 成本：20bps；T+1 03:00 UTC；long/short 均按冻结规格
- 空头 sleeve：该窗口 BTC 在 200D 上方，**0 次空头开仓**，本轮只检验 LS22 利润保护
- 数据审计：mark 88/88 complete；Bitget funding 88/88 present；跨所 funding overlap gate
  0/88 通过，因此 **Binance proxy 不能替代 Bitget 成本**，成本口径使用 Bitget exact funding

## 零 funding 上界

| arm | multiple | Sharpe | MDD | max gross | trims |
| --- | ---: | ---: | ---: | ---: | ---: |
| L125 baseline | 0.9484x | -0.2771 | -17.47% | 0.8149x | 0 |
| LS23 | 0.9403x | -0.5641 | -17.47% | 0.8153x | 8 |

LS23 终值比 L125 低约 0.0081x（约 -0.85%），Sharpe 低约 0.2870，MDD 基本不变。8 次 trim 没有带来正增量。

## Bitget 精确 funding（完整窗口）

| arm | multiple | Sharpe | MDD | funding total | fees | trims |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| L125 baseline | 0.9440x | -0.3303 | -17.65% | -0.4808% | 1.1656% | 0 |
| LS23 | 0.9365x | -0.6187 | -17.65% | -0.4088% | 1.2690% | 8 |

在完整 Bitget funding 下，LS23 终值仍比 L125 低约 0.0074x，Sharpe 低约 0.2884，MDD 略差。结论与零 funding 上界一致，不能 promotion。

## 判定

- 本轮没有证明 LS23 在真实 OOS 中优于 L125；反而在两个 funding 口径下都略差。
- 50 天仅覆盖 12 个月 OOS 门槛的 13.7%，且空头 sleeve 未被触发，不能外推到完整 LS23。
- 继续研究应优先补齐更长 OOS、扩展空头 regime 触发样本，或提出独立信息源；不要用这段结果反向调 profit-lock 或空头参数。
- 本轮不改变实盘，不新增杠杆，不把 shadow 结果当作下单信号。

## 数据修复记录

新快照首次下载时，Bitget `endTime` 按小时开区间处理，旧分页用 `first_open - 1ms`，导致每 100 行
边界少 1 小时（88 个资产、窗口内 1056 个缺失小时）。已修复为 `next_end = first_open`，并增加
shadow tracker 的 mark coverage fail-closed 检查；修复后 88/88 资产窗口内 0 missing hours。
