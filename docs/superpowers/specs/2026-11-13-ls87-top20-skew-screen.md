# Atlas20 预注册：PIT Top20 realized-skew 宽币池筛选

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；事件筛选；不接实盘 |
| 筛选 ID | `PR2026-11-LS87-PIT-TOP20-REALIZED-SKEW-SCREEN` |
| Universe | PIT CMC Top20，信号使用每日 price；执行只用 Bitget market candle 存在的成员 |
| Signal | 30D daily-return realized skewness |
| 组合 | 每 7D，skew 最低 2 做多、最高 2 做空，每腿 25% NAV |
| 执行 | D+1 03:00 UTC market close 入场，+7D 同一小时出场 |
| 窗口 | 2022-01-01 → 2026-09-20；discovery 2022–2023，validation 2024–2026 |
| 成本 | 20 / 50 / 100bps per side；事件按 entry+exit 计 `2 * cost_bps` |
| 负控 | 在每个事件的 PIT Top20 可执行成员内随机选择 2 long / 2 short，2,000 次 |

## 0. 研究问题

LS86 在 core8 上 realized-skew 失败，可能是主力币过度有效、横截面离散度太小。LS87 只改变
universe：使用项目冻结的 PIT CMC Top20，且只在信号日有 Bitget market candle、能在 D+1 03:00
成交的成员中排序。full/validation 必须和 LS86 独立报告，不能因为宽币池结果更好就把 core8
结果改写。

## 1. 冻结构造

```text
eligible(D) = PIT Top20 member at D
              with finite 30D skew and Bitget market entry/exit candles
if |eligible| < 6: skip
long  = two lowest skew
short = two highest skew
entry = Bitget market close(D+1 03:00 UTC)
exit  = entry + 7D
```

- 不扫描 Top20 的 rank 边界、skew lookback、weekly horizon、count 或量能过滤。
- 信号价来自 CMC/PIT daily price；执行价来自 Bitget market candle；mark/funding 不在本 screening
  阶段使用，若通过后才进入 LS88 真实引擎。
- 缺失/不可成交的成员在每个事件跳过并记录；不允许用当前 universe 回填历史。
- 不在结果出来后改成 core8、Top20 子集或事件阈值。

## 2. 预注册判定

1. validation 2024–2026 的 7D 成本后 spread > 0；
2. validation NW t >= 2.0；
3. discovery 与 validation 方向一致；
4. 50bps 成本后仍为正；
5. placebo p<=0.05 且 p95 不高于真实 spread；
6. 事件数 >= 150，且不依赖单一年份或单一资产。

若失败，记录 rejected，不进入 LS88；若通过，才建立真实 isolated-margin 引擎。

## 3. 复现

```bash
.venv/bin/python scripts/run_ls87_top20_skew_screen.py \
  --warmup-start 2021-01-01 --start-date 2022-01-01 --end-date 2026-09-21 \
  --output-dir reports/ls87_top20_skew_screen_2026
```
