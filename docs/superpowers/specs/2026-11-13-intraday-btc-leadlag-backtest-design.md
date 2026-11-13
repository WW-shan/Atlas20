# Atlas20 研究预注册：intraday BTC lead-lag tradable backtest

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 实时策略回测；不是实盘候选；不修改 live |
| 候选族 ID | `PR2026-11-LS64-INTRADAY-BTC-LEADLAG` |
| 诊断来源 | `PR2026-11-LS63-INTRADAY-BTC-LEADLAG-DIAGNOSTIC` |
| 数据 | Binance 30m OHLC + strict PIT CMC Top20 |
| 样本 | 2022-01-01 → 2026-09-30（UTC） |
| Discovery | 2022-01-01 → 2023-12-31 |
| Validation | 2024-01-01 → 2026-09-30 |
| 执行 | 信号 bar close 后，下一根 30m bar open 入场；按 bar open→close 逐 bar 记账 |
| 成本 | 6 / 12 / 20bps per one-way gross turnover；6bps 为 Bitget taker 费近似 |
| Funding | 未计入；持仓最多 2–4h，仍需在实盘前单独压测 |
| Leverage | 不使用；每个 tranche 占总 NAV 的 `1/h`，最多 h 个 tranche 同时活跃 |

## 0. 研究问题

LS63 在 48 个诊断 cell 中，41 个在 discovery 和 validation 同时出现负 IC 和正 contrarian
spread。最稳定的机制是：BTC 的 1h/2h 冲击超过滚动 30D 的 2.5σ 后，relative-gap 最低的
Top20 alt 在接下来 1–4h 跑赢 relative-gap 最高的 alt。现在检验扣费后是否仍能形成可交易组合。

LS63 已经看过 validation，因此 validation 对“signal family”不是全新 OOS；它只用于防止把
单一年份的噪声误当稳定机制。真正的新证据必须来自扣费回测、执行模型和后续未参与任何筛查的
实时数据。

## 1. 冻结策略与变体

横截面：

```text
beta_i(t)      = 30D rolling covariance(r_i, r_btc) / variance(r_btc), clipped [0, 4]
btc_shock_k(t) = log(close_btc(t) / close_btc(t-k))
gap_i(t)       = log(close_i(t) / close_i(t-k)) - beta_i(t) * btc_shock_k(t)
z(t)           = btc_shock_k(t) / rolling_30D_std(btc_shock_k)
long           = lowest 20% gap among eligible PIT Top20 alts
short          = highest 20% gap among eligible PIT Top20 alts
```

触发条件：`|z| >= 2.5`，横截面至少 8 个资产。多空各 50% tranche gross；每个 tranche
总 gross = `1/h`，最多 h 个 tranche 同时存在，因此组合 gross <= 1.0x。

预注册四个固定 cell，加上它们的等资金 ensemble：

| ID | signal bars k | future bars h | shock |
|---|---:|---:|---:|
| `LL_1_4` | 1 | 4 | abs(z) >= 2.5 |
| `LL_2_4` | 2 | 4 | abs(z) >= 2.5 |
| `LL_2_8` | 2 | 8 | abs(z) >= 2.5 |
| `LL_4_8` | 4 | 8 | abs(z) >= 2.5 |
| `LL_ENSEMBLE` | — | — | 四者等权，各占 1/4 资金 |

这四个 cell 覆盖 0.5h/1h/2h signal 与 2h/4h hold，不按 LS63 的排名只挑第一名；ensemble
是主候选，单 cell 用于机制分解。

## 2. 记账规则

- 每个 tranche 在信号后下一根 bar 的 open 入场，在该 bar 起第 h 根 bar 的 close 退出；
- 每个活跃 tranche 的资产权重：long leg `+0.5/h`、short leg `-0.5/h`；
- 每根 30m bar 用资产自己的 open→close 收益逐腿记账；缺失 bar 收益按 0 计入并显式计数；
- 入场和退出分别按 tranche gross 收取一次 one-way cost；
- 最多 h 个活跃 tranche；已有 h 个时跳过新信号，不挤掉旧仓；
- 不做杠杆、不做盘中再平衡、不扫描 long/short quintile 以外的权重；
- 按 UTC 日复合 30m returns 后计算日频 multiple / Sharpe / MDD，同期 BTC 为 benchmark。

成本档：

- `6bps/side`：Bitget taker fee 近似，主口径；
- `12bps/side`：加入一个保守滑点/冲击缓冲；
- `20bps/side`：极端压力。

## 3. 报告与分层

必须报告每个变体的 discovery、validation、full 三段；年度收益、事件数、活跃 tranche、
average/max gross、换手、缺失 bar、资产贡献和单资产集中度。

描述性分层：

- `candidate-for-shadow`：ensemble 在 6bps full Sharpe > 1.0、MDD > -30%，discovery 和
  validation 6bps Sharpe 都 > 0.5，12bps full 终值 > 1.0；
- `watch`：ensemble 12bps full 终值 > 1.0，但风险或分段稳定性不足；
- `rejected-now`：其余。

分层不阻止后续新假设；任何 shadow candidate 仍需 funding、真实盘口、订单延迟、部分成交、
交易所最小下单量和 12 个月未参与研究的 OOS。

## 4. 复现

```bash
.venv/bin/python scripts/run_intraday_btc_leadlag_backtest.py \
  --start-date 2022-01-01 \
  --end-date 2026-09-30 \
  --output-dir reports/intraday_btc_leadlag_backtest_2026
```

研究输出不是订单，也不是实盘批准。
