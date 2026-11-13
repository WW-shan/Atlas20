# Atlas20 预注册：LS79 churn ensemble 的 Bitget 可执行性审计

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 审计 ID | `PR2026-11-LS80-BITGET-EXECUTABLE-CHURN-ENSEMBLE` |
| 被审计对象 | `PR2026-11-LS79-LS57-CHURN-MULTIPHASE-ENSEMBLE` |
| 窗口 | 2022-01-01 → 2026-09-20 |
| 执行约束 | 信号日过去 3 天内有 Bitget market mark；过去 7 天有可用 funding |
| 成本 | 20 / 50 / 100bps 每边 |
| 分配 | 10% / 20% / 25% residual gross |
| Gross | 合并上限 1.50x |

## 0. 研究问题

LS79 的可执行条件只要求跨交易所 funding 存在，并未要求当时 Bitget 本身有可交易的
USDT-M mark。BTC 现货腿也不在 Bitget futures 数据里。本审计把空头腿进一步限制为：

- 信号日过去 3 个日历日内至少有一条 Bitget market mark；
- 信号日过去 7 个日历日内至少有一个 Binance/Bybit/Bitget funding settlement；
- 两项必须同时满足，否则该 alt 空头腿在事件内剔除，并把剩余腿等权重建。

这不是新 alpha，也不是重新调参。它回答一个更基本的问题：LS79 的收益是否来自当时在
Bitget 根本不能做空、或无法计 funding 的标的。

## 1. 预注册验收

LS79 只有在严格 Bitget 可执行币池中同时满足以下条件才保留为候选：

- funding 覆盖率 >=95%；
- 20bps normal 与 1x adverse 的 25% allocation 都跑赢 LS57 的 full/validation 收益与 Sharpe，
  MDD 不差于 -40.84%；
- 50bps normal 仍明显跑赢 LS57；
- 不出现任何“先用 mark-only、再在亏损时切换到严格池”的事后选择。

若严格池不能同时通过，LS79 的 conditional 结论作废，churn overlay 家族停止，不扫描
mark lookback、funding lookback、币种白名单或 allocation。

## 2. 预期数据缺口

Bitget `merged_market_20261009` 当前有 87 个合约的 market mark；LS79 的 34 个短币中只有 31 个
出现。MONERO、ZCASH、KASPA、MATIC 等上线显著晚于 LS79 的 Binance/Bybit funding proxy 起点。
审计必须逐币报告 mark coverage、funding coverage 和合成覆盖，而不是只报组合加权平均。

## 3. 复现

```bash
.venv/bin/python scripts/run_ls57_churn_bitget_executable.py \
  --start-date 2022-01-01 --end-date 2026-09-20 \
  --output-dir reports/ls57_churn_bitget_executable_2026
```
