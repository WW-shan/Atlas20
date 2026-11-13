# Atlas20 研究预注册：intraday BTC shock lead-lag diagnostic

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 实时信号诊断；不是回测候选；不修改 live |
| 候选族 ID | `PR2026-11-LS63-INTRADAY-BTC-LEADLAG-DIAGNOSTIC` |
| 数据 | Binance 30m OHLC，`data/raw/binance_30m/`，32 个可用资产 |
| Universe | strict PIT CMC Top20，仅保留 Binance 30m 可用且当天在 Top20 的资产 |
| 样本 | 2022-01-01 → 2026-09-30（UTC） |
| Discovery | 2022-01-01 → 2023-12-31 |
| Validation | 2024-01-01 → 2026-09-30 |
| 执行 | 诊断收益从信号 bar 后的下一根 bar open 开始，不发送订单 |
| 成本 | 本诊断不计成本；下一阶段才做可交易组合和费率 |

## 0. 研究问题

如果 BTC 在 30m/1h/2h/4h 上先发生冲击，而某个 Top20 alt 的同期 beta-adjusted move 落后于 BTC，
它是否会在接下来 30m–4h 补涨/补跌？这是实时 lead-lag 假设，不是 LS60/LS61 的 28D residual
factor，也不依赖月末调仓。

先做纯预测诊断，不构造可交易收益曲线：

```text
beta_i(t)       = rolling 30D covariance(r_i, r_btc) / variance(r_btc), clipped to [0, 4]
btc_shock_k(t)  = log(close_btc(t) / close_btc(t-k))
gap_i,k(t)      = log(close_i(t) / close_i(t-k)) - beta_i(t) * btc_shock_k(t)
future_i,h(t)   = log(close_i(t+h) / open_i(t+1))
future_resid_i  = future_i,h(t) - beta_i(t) * future_btc,h(t)
```

`gap` 高表示资产相对 BTC 冲击已经反应过度；`gap` 低表示还没跟上。如果 lead-lag 补涨/补跌
存在，`gap` 与 `future_resid` 的横截面 rank correlation 应为负，且 low-gap 减 high-gap 的
contrarian spread 应为正。

## 1. 冻结诊断网格

- signal window `k ∈ {1, 2, 4, 8}` 根 30m bar（30m/1h/2h/4h）；
- future horizon `h ∈ {1, 2, 4, 8}` 根 30m bar；
- BTC shock bucket：`all`、`|z| >= 1.5`、`|z| >= 2.5`，其中 `z = btc_shock_k / rolling_30D_std`；
- beta 30D rolling，最少 960 根 bar（20 天）；
- 每个 `(k,h)` 按 `h` 根 bar 做非重叠采样，避免把重叠 future return 当成独立观测；
- 每个横截面至少 8 个合格资产；
- 只做预测统计，不按结果临时改 k/h/beta/shock 阈值。

诊断只记录：

1. 每个 cell/样本的 cross-sectional rank IC 均值、t-stat、IC<0 比例；
2. contrarian spread（low-gap long / high-gap short）的 bar 收益 bps 均值、t-stat、正比例；
3. discovery 排序与 validation 对照，不能反过来用 validation 挑参数；
4. 资产覆盖、bar 数量、缺失和异常 beta 数量。

若 discovery 与 validation 都显示稳定负 IC、正 spread，并且 spread 的均值在扣除 12bps/bar
的保守单边换手成本后仍有空间，下一步才登记可交易 backtest。若没有，则记录该机制失败并继续
其他实时假设，不使用永久禁止条款。

## 2. 复现

```bash
.venv/bin/python scripts/run_intraday_btc_leadlag_diagnostic.py \
  --start-date 2022-01-01 \
  --end-date 2026-09-30 \
  --output-dir reports/intraday_btc_leadlag_diagnostic_2026
```

研究输出不是订单，也不是实盘批准。
