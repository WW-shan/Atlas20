# Atlas20 研究预注册：intraday BTC lead-lag single-event backtest

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | follow-up 实时策略回测；不是实盘候选 |
| 候选族 ID | `PR2026-11-LS65-INTRADAY-BTC-LEADLAG-SINGLE` |
| 来源 | LS63 diagnostic + LS64 overlapping-tranche backtest |
| 数据 / universe | Binance 30m + strict PIT CMC Top20，2022-01-01 → 2026-09-30 |
| Discovery / validation | 2022–2023 / 2024–2026-09 |
| 执行 | 信号 bar close → 下一根 30m open；单笔 tranche gross 1.0x；最多一个活跃事件 |
| 成本 | 6 / 12 / 20bps per one-way gross turnover |
| Funding | 未计入；持仓 2–4h，结算边界仍需另测 |

## 0. 研究问题

LS64 的“每根 bar 都可开一个 1/h tranche”在 shock 后产生大量重叠、陈旧信号。平均 active gross
只有约 3%，但事件数超过 2,400–2,700，费用把 gross alpha 全部吃掉。LS63 的非重叠抽样却显示
稳定正 spread。这里检验更符合事件研究的经济实现：**一次 BTC 冲击只做一个完整事件，持有
h 根 bar，期间不叠加新 tranche**；因此每笔可用 full gross，且不会把同一冲击拆成多次付费交易。

## 1. 冻结构造

四个 cell 与 LS64 完全相同：

- `LL_1_4`: k=1, h=4
- `LL_2_4`: k=2, h=4
- `LL_2_8`: k=2, h=8
- `LL_4_8`: k=4, h=8

规则：

```text
if no active event and abs(z) >= 2.5 and current cross-section >= 8:
    long  = exact lowest 20% gap assets
    short = exact highest 20% gap assets
    enter at next 30m open
    hold h bars and exit at that bar close
    entry/exit costs = 6/12/20bps per side on gross 1.0x
```

- 一个事件持有期间，后续 shock 被跳过；exit bar 的 close 之后允许下一笔在下一根 open 入场；
- 不做杠杆、不做重叠 tranche、不做动态加仓、不扫描 threshold 或 quantile；
- 单 cell 与四 cell 等资金 ensemble 都报告；
- 2022–2023 为 discovery，2024–2026-09 为 validation；LS63 已看过 validation，因此它不是
  全新 OOS，不能据此宣称 promotion。

## 2. 分层

- `candidate-for-shadow`：ensemble 6bps full Sharpe > 1.0、MDD > -30%，discovery / validation
  6bps Sharpe 均 > 0.5，12bps full 终值 > 1.0；
- `watch`：12bps full 终值 > 1.0，但分段或风险不足；
- `rejected-now`：其余。

这仍只是研究分层；不接实盘，不修改 LS57。若通过，下一步必须在 2026-09-30 之后的实时数据
和 Bitget 盘口/成交数据上做独立 shadow，不能回填历史来制造新 OOS。

## 3. 复现

```bash
.venv/bin/python scripts/run_intraday_btc_leadlag_single_event.py \
  --start-date 2022-01-01 \
  --end-date 2026-09-30 \
  --output-dir reports/intraday_btc_leadlag_single_event_2026
```
