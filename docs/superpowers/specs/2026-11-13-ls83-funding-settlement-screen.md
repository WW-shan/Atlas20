# Atlas20 预注册：core8 funding settlement 短周期事件筛选

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；事件筛选；不接实盘 |
| 筛选 ID | `PR2026-11-LS83-CORE8-FUNDING-SETTLEMENT-SCREEN` |
| 数据 | Bitget core8 mark/market 小时线；Binance 8h funding settlements |
| Universe | BTC/ETH/SOL/XRP/BNB/DOGE/ADA/AVAX；固定，不按结果改名单 |
| 事件 | 每日 00:00 UTC funding settlement；signal 只用该时刻已知的 Binance funding rate |
| 执行 | 事件后 1h 的 Bitget market close 入场；8h / 24h 后同一 close 出场 |
| 组合 | funding 最低 2 币做多、最高 2 币做空，每腿 25% NAV；多空各 50% gross |
| 窗口 | 2022-01-01 → 2026-09-20；discovery 2022–2023，validation 2024–2026 |
| 成本 | 20 / 50 / 100bps per side；事件筛选先报告 gross 和 cost-adjusted spread |
| 负控 | funding 在事件内随机错配的同数量 placebo，至少 2,000 次 |

## 0. 研究问题

carry 研究使用了 7D funding level；它回答的是持续持有成本。这里改问一个不同的短期问题：

> 在 funding settlement 刚发生、且信号已知后，core8 中 funding 最高/最低的资产在接下来 8h 或
> 24h 是否有可交易的横截面反转/延续？

这是一个 event screen，不是组合策略。若事件 spread 在 2024–2026 validation 扣成本后仍为正且
显著，再建立 LS84 的真实 isolated-margin 引擎 trial；否则直接记录失败，不进入回测。

## 1. 冻结构造

```text
for each UTC date D with a 00:00 settlement:
  rank core8 by funding_rate(D) at the settlement
  long  = two lowest funding rates
  short = two highest funding rates
  entry = market_close(D + 1h)
  exit8 = market_close(D + 9h)
  exit24 = market_close(D + 25h)
  event_spread = mean(long forward returns) - mean(short forward returns)
```

- 00:00 而不是 08/16 UTC 是为了得到每日一个非重叠 8h 事件；不扫描 settlement hour。
- 只使用 entry 前后不超过 1h 的 exact market candle；缺失事件跳过并报告。
- 不做 universe 过滤、funding 阈值、count、短期 lookback 或事件方向的事后调整。
- 成本按每个事件完整多空组合的 turnover 计：`cost = 2 * cost_bps`（入场 + 出场）。
- 24h 是有重叠的辅助 horizon，必须同时报告 HAC t；8h 是主 horizon。

## 2. 预注册判定

事件筛选只有在以下条件全部满足时才允许进入 LS84：

1. validation 2024–2026 的 8h 成本后 mean spread > 0；
2. validation 的 Newey-West t >= 2.0；
3. discovery 与 validation 方向一致，且 validation 不依赖单一资产或单一年份；
4. 50bps 成本后仍为正；20bps 后更不必说；
5. placebo（同事件内 funding 随机错配）的 95% spread 不高于真实 spread；
6. 24h 辅助 horizon 不出现方向相反且显著的结果。

若不满足，记录 rejected，不再扫描 event hour、horizon、count、anchor 或阈值。

## 3. 复现

```bash
.venv/bin/python scripts/run_ls83_funding_settlement_screen.py \
  --start-date 2022-01-01 --end-date 2026-09-21 \
  --output-dir reports/ls83_funding_settlement_screen_2026
```
