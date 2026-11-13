# Atlas20 预注册：core8 realized-skew / lottery-demand 筛选

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；事件筛选；不接实盘 |
| 筛选 ID | `PR2026-11-LS86-CORE8-REALIZED-SKEW-SCREEN` |
| 数据 | Bitget core8 market 小时线 -> UTC 日收益 |
| Universe | BTC/ETH/SOL/XRP/BNB/DOGE/ADA/AVAX；固定 |
| Signal | 30D daily-return realized skewness，使用 D 收盘及之前数据 |
| 组合 | skew 最低 2 币做多、最高 2 币做空，每腿 25% NAV |
| 调仓 | 7D 周频；entry D+1 03:00 UTC market close，exit +7D 同一小时 |
| 窗口 | 2022-01-01 → 2026-09-20；discovery 2022–2023，validation 2024–2026 |
| 成本 | 20 / 50 / 100bps per side；事件按 entry+exit 计 `2 * cost_bps` |
| 负控 | 同一横截面随机选择 2 long / 2 short，2,000 次 |

## 0. 研究问题

文献中的 lottery-demand 机制认为，高偏度、彩票型资产容易被过度定价，未来风险调整收益较低；
低偏度资产可能提供补偿。此前 Atlas20 的研究主要使用 momentum、funding、churn、BTC shock 和
成交量；本 trial 检验 core8 的 realized skewness 是否是一个独立、低换手的横截面信号。

## 1. 冻结构造

```text
for each weekly signal date D:
  r_t = daily close(D) / daily close(D-1) - 1
  skew30_i(D) = skewness(r_i, D-29..D)
  require finite skew for all core8 and 30 observations
  long  = two lowest skew30
  short = two highest skew30
  entry = market_close(D+1 at 03:00 UTC)
  exit  = market_close(entry + 7D)
  spread = mean(long 7D return) - mean(short 7D return)
```

- 不扫描 skew lookback 20/30/60、周频/日频、count、volatility normalize 或 threshold。
- 如果 skew 缺失或 exit 价格不完整，跳过该周并记录；不填零、不把缺失当作低 skew。
- 事件只在 anchor 后每 7 天生成；不因结果改变 anchor。
- 主窗口结束后至少保留 7D exit 空间。

## 2. 预注册判定

1. validation 2024–2026 的 7D 成本后 spread > 0；
2. validation 的 NW t >= 2.0；
3. discovery 与 validation 方向一致；
4. 50bps 成本后仍为正；
5. placebo（同横截面随机 2/2）p95 不高于实际 spread，且实际 p <= 0.05；
6. 如果只靠单一币或单一年份，标记 concentration fail。

通过才进入 LS87 的真实 isolated-margin 引擎；否则记录 rejected，不进入组合回测。

## 3. 复现

```bash
.venv/bin/python scripts/run_ls86_realized_skew_screen.py \
  --start-date 2022-01-01 --end-date 2026-09-21 \
  --output-dir reports/ls86_realized_skew_screen_2026
```
