# Atlas20 预注册：core8 高成交量过度反应反转筛选

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；事件筛选；不接实盘 |
| 筛选 ID | `PR2026-11-LS84-CORE8-VOLUME-REVERSAL-SCREEN` |
| 数据 | Bitget core8 market 小时线（close + quote_volume） |
| Universe | BTC/ETH/SOL/XRP/BNB/DOGE/ADA/AVAX；固定 |
| 信号日 | UTC 日 D 的完整 24h return 与日 quote_volume |
| 量能状态 | volume surprise = log(日 quote_volume / 过去 20 日 median)；只保留当日横截面量能最高的 4 个币 |
| 组合 | 高量能组中 24h return 最低 2 币做多、最高 2 币做空，每腿 25% NAV |
| 执行 | D+1 UTC +3h 的 Bitget market close 入场；24h / 72h 后同一 close 出场 |
| 窗口 | 2022-01-01 → 2026-09-20；discovery 2022–2023，validation 2024–2026 |
| 成本 | 20 / 50 / 100bps per side；事件组合按入场+出场计 `2 * cost_bps` |
| 负控 | 同一高量能组内随机选择 2 long / 2 short，2,000 次 |

## 0. 研究问题

短周期反转已经被分成两类研究过：LS60/LS61 使用 63–252D residual score，LS69/LS70 使用
BTC shock。这里不重复它们，而是检验一个更直接的市场微结构假设：

> 在 core8 中，当日成交量显著放大且价格出现大幅单向移动的资产，次日更可能发生过度反应反转。

信号只使用 D 日收盘后已知的 return 和 volume。高量能筛选是横截面前 4 名，不做绝对阈值；
组合只在高量能资产中选择最低/最高 24h return 各 2 个，避免用全 universe 的低量能噪声。

## 1. 冻结构造

```text
for each UTC date D:
  r24_i = close(D) / close(D-1) - 1
  volume_i = sum quote_volume over D
  surprise_i = log(volume_i / median(volume_i, D-20..D-1))
  high_volume = top 4 assets by surprise_i
  long  = two lowest r24 in high_volume
  short = two highest r24 in high_volume
  entry = market_close(D+1 at 03:00 UTC)
  exit24 = entry + 24h
  exit72 = entry + 72h
  spread = mean(long returns) - mean(short returns)
```

- `D` 日 volume/return 必须在 D 结束后才可用；入场固定在 D+1 03:00，严格 T+1。
- 不使用当天收盘后的未来价格；若 20D 量能中位数缺失、high-volume 少于 4 个或 exit 价格缺失，
  该日跳过并记录。
- 主 horizon 24h 不重叠；72h 仅辅助，必须报告 overlapping HAC t。
- 不扫描前 3/4/5 名量能过滤、1D/3D/7D return、2/3/4 腿或 horizon；不按结果改 core8。

## 2. 预注册判定

只有以下条件全部满足才进入 LS85 真实引擎回测：

1. validation 2024–2026 的 24h 成本后 spread > 0；
2. validation 的 NW t >= 2.0；
3. discovery 与 validation 方向一致；
4. 50bps 成本后仍为正；
5. 高量能组内随机选腿的 placebo p95 不高于真实 spread，且实际 p <= 0.05；
6. 72h 辅助 horizon 不出现相反且显著的结果。

若不满足，记录 rejected，不扫描量能分位、return horizon、腿数、anchor 或其他阈值。

## 3. 复现

```bash
.venv/bin/python scripts/run_ls84_volume_reversal_screen.py \
  --start-date 2022-01-01 --end-date 2026-09-21 \
  --output-dir reports/ls84_volume_reversal_screen_2026
```
