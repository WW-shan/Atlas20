# LS46：LS44 全退后反手 28D 空头

- 候选：`PR2026-11-LS46-H5-LS23-PROFITLOCK-REVERSAL-SHORT28`
- 状态：provisional；OOS 诊断失败；不接实盘
- 机制：LS44 在 21D>=100% 且 7D<0 时全退；同一龙头以 0.20x 总空头反手 28 个日历日，
  优先于 LS12 router；20% short stop；hard total gross 1.50x。

## 主结果

| 成本 | LS23 | LS46 | LS23 Sharpe | LS46 Sharpe | LS46 MDD |
|---:|---:|---:|---:|---:|---:|
| 2bps | 84.4362x | **92.8053x** | 2.0719 | **2.1221** | -32.658% |
| 20bps | 61.9150x | **67.6951x** | 1.9448 | **1.9919** | -34.916% |
| 50bps | 36.8788x | **39.9697x** | 1.7319 | **1.7737** | -38.709% |
| 100bps | 15.5037x | **16.5589x** | 1.3745 | **1.4077** | -45.371% |

20bps：0 强平、0 gross breach、max observed gross 1.4778x、343 个 short episodes、28 个 stop；
3x short-adverse funding **66.9159x / 1.9857 / -35.273%**。

## 稳健性

- 365D rolling worst **0.9279x**；
- 删除 2024 后 **37.1511x**，高于 LS23 的 34.3343x；
- 45/45 路径胜 L125；12/12 真实 cash-start 终值和 Sharpe 胜 L125，MDD 12/12；
- short attribution 单资产最大 23.18%、前 3 63.08%；
- 13 候选 PBO 0.193723、RC zero p=0.003996、BTC p=0.008991、Top20/2022 DSR 0.979268、
  all-project DSR 0.969481（N=14,215）。

## OOS

2026-09-22 → 2026-11-11，20bps，Bitget mark，0 missing hours：

| funding | LS23 | LS46 |
|---|---:|---:|
| zero | 0.9403x | **0.9218x** |
| exact | 0.9365x | **0.9192x** |

OOS 中 NEAR 反手空头在 10-04 开仓，10-11 被 20% stop 平掉，随后重开并继续亏损。

**判定：provisional，不接实盘。** 主样本和多重检验很强，但 OOS 为负；不能把 2024 的增量当作稳定 alpha。
