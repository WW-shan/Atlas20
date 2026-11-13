# Atlas20 研究预注册：intraday BTC lead-lag phase/tail follow-up

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | follow-up backtest；不是实盘候选 |
| 候选族 ID | `PR2026-11-LS66-INTRADAY-LEADLAG-PHASE-TAIL` |
| 来源 | LS63 的 phase-0 抽样、LS64/LS65 的重叠与单一事件失败 |
| 数据 / universe | Binance 30m + strict PIT CMC Top20，2022-01-01 → 2026-09-30 |
| Discovery / validation | 2022–2023 / 2024–2026-09 |
| 信号日程 | phase-0 UTC：每 `h` 根 bar 检查一次，h=8 为 00/04/08/… UTC |
| 执行 | 信号 close → 下一根 open，单笔 full gross，持有 h bars |
| 成本 | 6 / 12 / 20bps per one-way gross turnover；funding 未计 |

## 0. 研究问题

LS63 的固定 phase-0 抽样在 discovery 和 validation 都出现正 contrarian spread，但 LS64/LS65
显示：把所有 phase 的信号都交易、或允许重叠 tranche，会被集群信号和费用吃掉。进一步的分
phase 诊断显示，phase-0（固定 UTC 日程）在 10% tail 和更高 shock 阈值下仍有较厚的事件
gross PnL；但这是事后观察到的时间相位，因此本轮明确把它登记为**有选择偏差的 follow-up**，
不是新的独立 OOS。

## 1. 冻结变体

只使用 phase-0 日程，tail 固定为 lowest/highest **10%**，并在两个要求更高的 shock 阈值上
各测两个持有期：

| ID | k signal bars | h hold bars | 阈值 |
|---|---:|---:|---:|
| `LL_P2_8_T30` | 2 | 8 | abs(z) >= 3.0 |
| `LL_P2_8_T35` | 2 | 8 | abs(z) >= 3.5 |
| `LL_P4_8_T30` | 4 | 8 | abs(z) >= 3.0 |
| `LL_P4_8_T35` | 4 | 8 | abs(z) >= 3.5 |
| `LL_PHASE_ENSEMBLE` | — | — | 四者等资金 |

这是一组固定的 4-cell follow-up，不扫描其他 phase、tail、阈值或持有期。每个 cell 使用
full gross 1.0x，且同一时间最多一个事件；ensemble 等权分配 1/4 资金。

## 2. 记账与分层

沿用 LS65 的 open→close bar 记账、单事件容量限制、成本 per side 和缺失收益显式计数。样本
分段仍为 discovery / validation / full。分层：

- `candidate-for-shadow`：ensemble 6bps full Sharpe > 1.0、MDD > -30%，两个分段 6bps
  Sharpe 均 > 0.5，12bps full 终值 > 1.0；
- `watch`：12bps full 终值 > 1.0；
- `rejected-now`：其余。

即使通过，这也仍是 phase-selected backtest；必须用 2026-09-30 后的实时数据和真实 Bitget
盘口重新验证，不能把 phase-0 的结果直接当成实盘 alpha。

## 3. 复现

```bash
.venv/bin/python scripts/run_intraday_btc_leadlag_phase_backtest.py \
  --start-date 2022-01-01 \
  --end-date 2026-09-30 \
  --output-dir reports/intraday_btc_leadlag_phase_tail_2026
```
