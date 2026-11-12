# Atlas20 候选：LS46 反手空头 + 禁止同一资产立即回补

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 主样本、成本、funding、路径、冷启动和多重检验已评估；OOS 诊断失败；不接实盘 |
| 候选 ID | `PR2026-11-LS47-H5-LS23-PROFITLOCK-REVERSAL-SHORT28-NOREENTRY` |
| 基线 | LS23；LS46 作为机制父候选 |
| 机制 | LS46 的 0.20x / 28D 反手空头；当反手空头活跃时，把同一资产从 H5 多头目标中移除，防止下一次 H5 调仓立即回补该资产 |
| 主样本 | 2022-01-01 → 2026-09-21（UTC） |
| 执行 | T+1 UTC +3h；missing mark carry 3h；20% short stop；hard total gross 1.50x |
| 数据 | 严格 PIT CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS46 在主样本把 LS44 全退事件反手成 0.20x 空头，20bps 为 67.6951x / 1.9919 / -34.916%。
但它的短空头会在下一次 H5 target event 与多头目标重叠，组合层会把重叠腿平掉；如果 H5 很快
重新买入同一个刚被看空的资产，反手空头会被过早关闭。

LS47 只增加一条执行约束：

```text
while reversal_short(asset) is active:
    remove asset from the H5 long target
    keep the rest of the H5 book and LS12 router unchanged
```

这不是冻结整个 H5 账本，也不是把空头权重加倍；其他资产的 H5 调仓继续正常执行。

## 1. 结果

20bps 主样本：

| 指标 | LS23 | LS46 | LS47 |
|---|---:|---:|---:|
| 终值 | 61.9150x | 67.6951x | **69.4109x** |
| Sharpe | 1.9448 | 1.9919 | **2.0023** |
| MDD | -39.84% | -34.916% | **-34.916%** |
| 强平 | 0 | 0 | **0** |
| max observed gross | 1.3308x | 1.4778x | **1.4778x** |
| short opens / stops | 335 / 29 | 343 / 28 | 342 / 31 |
| fees total | 3.1262 | 3.4566 | 3.5272 |

成本族：

| 成本 | LS23 终值 | LS47 终值 | LS23 Sharpe | LS47 Sharpe | LS47 MDD |
|---:|---:|---:|---:|---:|---:|
| 2bps | 84.4362x | **94.7995x** | 2.0719 | **2.1309** | -32.658% |
| 20bps | 61.9150x | **69.4109x** | 1.9448 | **2.0023** | -34.916% |
| 50bps | 36.8788x | **41.2416x** | 1.7319 | **1.7868** | -38.709% |
| 100bps | 15.5037x | **17.2669x** | 1.3745 | **1.4252** | -45.371% |

3x short-adverse funding：**68.2319x / 1.9938 / -35.273% / 0 强平 / 0 gross breach**。

稳健性：

- 365D rolling worst **0.9279x**，高于 LS23 的 0.8551x 和 L125 的 0.7325x；
- 删除 2024 后 **38.7997x**，高于 LS23 的 34.3343x；删除 2023 后 16.4009x，略低于 LS23
  16.9638x 但仍高于 L125；
- 12 个真实 cash-start：multiple **11/12**、Sharpe **12/12**、MDD **12/12**、0 强平/0 breach；
- 45 个月初路径 vs L125：multiple 42/45、Sharpe 45/45、MDD 45/45；**3 条路径的 multiple
  未胜 L125，预注册 45/45 门槛失败**；
- vs LS23 的 45 条路径只有 21/45 全通过，说明相对 LS23 的优势并不普遍；
- short attribution：342 episodes，169 负/173 正；单资产最大 23.46%，前 3 64.87%；
- 14 候选 PBO **0.1775**、RC zero p **0.003996**、BTC p **0.008991**；N=14,215 下
  DSR family **0.999998**、Top20/2022 **0.980583**、all-project **0.971300**。

## 2. OOS 诊断

2026-09-22 → 2026-11-11，20bps，Bitget mark，0 missing hours：

| funding | LS23 | LS47 |
|---|---:|---:|
| zero | 0.9403x / -0.5584 / -17.47% | **0.9033x / -2.2542 / -11.02%** |
| Bitget exact | 0.9365x / -0.6125 / -17.65% | **0.9018x / -2.2925 / -11.21%** |

OOS 中 NEAR 的两次 full-exit 触发了反手空头；空头在 2026-10-04 开仓，2026-10-11 被 20%
short stop 平掉，随后又在 10-14 重开，最终造成明显负贡献。禁止回补降低了回撤（-11.2% vs
-17.65%），但没有把 OOS 变成正收益。**判定：provisional，主样本很强但 OOS 失败，不接实盘。**

## 3. 验收标准

1. 20bps 终值 >= LS23 61.9150x，Sharpe >= 1.9448，MDD 不差于 -44.84%；
2. 2/20/50/100bps 终值和 Sharpe 均 >= 同成本 LS23 与 L125；
3. 100bps 终值 > 15.5037x、Sharpe > 1.3745、MDD <=50%；
4. 3x short-adverse funding 0 强平、MDD <=50%；
5. 0 强平、0 gross breach、observed gross <=1.50x；
6. 删除任一最佳年份后终值仍高于 L125；
7. 365D rolling worst >= L125 0.7325x；
8. 45 个路径月初切片全部通过终值、Sharpe 和 MDD 5pp；
9. 12 个真实 cash-start 至少 10/12 终值和 Sharpe 胜 L125，12/12 MDD 5pp；
10. 单资产空头贡献 <=50%，前 3 <=80%；
11. PBO/CSCV <=0.50，White Reality Check p <=0.05；
12. 选择后的独立 OOS 至少 12 个月；未完成前最高只能 provisional。

LS47 已通过 1–7、9–11；第 8 条 42/45 失败，第 12 条 OOS 诊断失败。因此不能 promotion。

## 4. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS47-H5-LS23-PROFITLOCK-REVERSAL-SHORT28-NOREENTRY \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 20 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_reversal_short28_noreentry
```

研究输出不是订单，也不是实盘批准。
