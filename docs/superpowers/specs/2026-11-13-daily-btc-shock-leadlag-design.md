# Atlas20 研究预注册：daily BTC shock relative-gap diagnostic

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 新信号族诊断；不是实盘候选 |
| 候选族 ID | `PR2026-11-LS68-DAILY-BTC-SHOCK-LEADLAG` |
| 数据 | strict PIT CMC Top20，`data/processed/panel_daily.csv`，2022-01-01 → 2026-11-12 |
| Discovery | 2022-01-01 → 2023-12-31 |
| Validation | 2024-01-01 → 2026-11-12 |
| beta | 120D rolling BTC beta，至少 90 个日收益 |
| 执行基准 | 信号日 close；未来收益从下一日 close 起算，避免同日成交假设 |
| 成本 | 本诊断只报 gross spread；下一阶段回测再扣 20/50/100bps round-trip |

## 0. 研究问题

30m lead-lag 在 LS63–LS67 显示出条件预测，但 phase 选择和 12bps round-trip 使实盘化困难。
现在把同一个经济机制降到日频：BTC 发生 1/3/5/10 日冲击后，relative-gap 最低的 Top20 alt
是否在接下来的 1/3/5/10 日跑赢 relative-gap 最高的 alt？日频持有期降低换手，允许更大的
gross edge 覆盖成本。

## 1. 冻结网格

```text
btc_shock_k(t) = log(close_btc(t) / close_btc(t-k))
gap_i(t)       = log(close_i(t) / close_i(t-k)) - beta_i(t) * btc_shock_k(t)
future_i,h(t)  = log(close_i(t+1+h) / close_i(t+1))
future_res    = future_i,h - beta_i(t) * future_btc
z(t)           = btc_shock_k(t) / rolling_120D_std(btc_shock_k)
```

冻结网格：

- `k ∈ {1, 3, 5, 10}` 日；
- `h ∈ {1, 3, 5, 10}` 日；
- shock bucket：`all`、`|z| >= 2.0`、`|z| >= 2.5`；
- long/short tail：10% 与 20%；
- beta 120D / min 90；每个横截面至少 8 个合格资产；
- 所有 `4 × 4 × 3 × 2 = 96` 个 cell 全部记录，不按中间结果改参数。

为了避免 phase 选择，本诊断使用每个交易日的所有观测；同一 cell 的日频重叠会造成 t-stat
自相关，因此 t-stat 只作描述，不作为独立样本推断。另报每个 cell 的 discovery/validation
分段均值和 hit rate；如果同一 cell 两段都为正，下一步才做严格非重叠/cooldown 回测。

## 2. 分层

- `candidate-for-backtest`：discovery 与 validation 的 contrarian spread 都 > 0、IC 都 < 0，
  且 gross spread 至少比该 cell 的持有期 round-trip 成本高 10bps；
- `watch`：两段同号但成本缓冲不足；
- `rejected-now`：其余。

分层只是研究优先级，不是永久禁令。任何通过者仍必须做 T+1 close、真实 funding、成本
20/50/100bps、组合 gross 上限和独立 OOS；不能直接接实盘。

## 3. 复现

```bash
.venv/bin/python scripts/run_daily_btc_shock_leadlag_diagnostic.py \
  --start-date 2022-01-01 \
  --end-date 2026-11-12 \
  --output-dir reports/daily_btc_shock_leadlag_2026
```
