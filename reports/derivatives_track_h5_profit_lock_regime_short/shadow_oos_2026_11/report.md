# LS23 Shadow OOS：2026-09-22 → 2026-11-10

- 研究状态：**provisional / research-only**，不接实盘，不修改 `PR2026-10-D-L125-V2`
- 完整日：50 个日行，49 个有效收益观测（首行是引擎初始化点）
- 数据：Bitget mark 到 2026-11-11 00:00 UTC；processed panel 到 2026-11-10
- 成本：20bps；T+1 03:00 UTC；long/short 均按冻结规格
- 空头 sleeve：该窗口 BTC 在 200D 上方，**0 次空头开仓**，因此本轮只检验 LS22 利润保护，不检验 LS12 空头

## 零 funding 上界

| arm | multiple | Sharpe | MDD | max gross | trims |
| --- | ---: | ---: | ---: | ---: | ---: |
| L125 baseline | 0.9484x | -0.2771 | -17.47% | 0.8149x | 0 |
| LS23 | 0.9403x | -0.5641 | -17.47% | 0.8153x | 8 |

LS23 终值比 L125 低约 0.0081x（约 -0.85%），Sharpe 低约 0.2870，MDD 基本不变（差异 0.0042%）。本窗口 LS22 的 8 次 trim 没有带来正增量。

## 部分真实 Bitget funding

Bitget 精确 funding 只到 2026-10-09 08:00 UTC。之后强制停止新的空头选择，已有空头在下一信号日 flatten；因此这不是完整 50 天 funding 路径，只是比零 funding 更保守的部分成本检查。

| arm | multiple | Sharpe | MDD | funding total | fees |
| --- | ---: | ---: | ---: | ---: | ---: |
| L125 baseline | 0.9465x | -0.2994 | -17.47% | -0.2083% | 1.1665% |
| LS23 | 0.9391x | -0.5818 | -17.47% | -0.1384% | 1.2700% |

在部分真实 funding 下，LS23 仍低于 L125；结论与零 funding 上界一致，不能据此 promotion。

## 判定

- 本轮没有证明 LS23 在真实 OOS 中优于 L125；反而在两个 funding 口径下都略差。
- 50 天仅覆盖 12 个月 OOS 门槛的 13.7%，且空头 sleeve 未被触发，不能外推到完整 LS23。
- 继续研究时，应先补齐 2026-10-09 之后的 Bitget funding 和更长的真实 OOS；不要用这段结果反向调 profit-lock 或空头参数。
- 本轮不改变实盘，不新增杠杆，不把 shadow 结果当作下单信号。
