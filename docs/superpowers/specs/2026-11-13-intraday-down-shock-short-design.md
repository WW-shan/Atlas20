# Atlas20 研究预注册：intraday down-shock weak-tail short

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 候选族 ID | `PR2026-11-LS70-DOWN-SHOCK-WEAK-SHORT` |
| 来源 | LS63–LS67 的 long-short lead-lag 成本过高；本轮只检验同一机制的空头腿 |
| 状态 | 研究回测；不连接实盘、不修改 live target |
| 数据 | Binance 30m OHLC proxy；2022-01-01 → 2026-09-30；OOS 2026-10-01 → 2026-11-13 |
| Discovery | 2022-01-01 → 2023-12-31 |
| Validation | 2024-01-01 → 2026-09-30 |
| 执行 | 30m signal close，下一根 30m open 入场，持有 h 根 bar |
| 成本 | 6 / 12 / 20bps 每边；初步筛查不计 funding |
| 方向 | 只在 BTC 下跌 shock 后做空 relative gap 最弱的 10% |

## 0. 研究问题

LS64/LS65 的 long-short 事件交易被两侧成本和重叠信号吃掉，但 LS63 的预测关系主要来自
**弱资产继续弱**。如果下行 shock 后的弱资产空头腿本身有足够 gross alpha，那么单腿结构可能比
long-short 更适合当前账户：不需要为多头腿支付成本和承担 beta，且可在 LS57 多头空窗时作为
小 gross overlay。

这不是把 LS65 的失败结果换个名字：本族冻结为 negative-shock-only、short-only、单事件，
不交易强资产，不做 long leg，不根据 LS66 的 phase/3.5σ 结果选参数。

## 1. 冻结网格

```text
btc_shock_k(t) = log(close_btc(t) / close_btc(t-k))
z_k(t)         = btc_shock_k(t) / rolling_30D_std(btc_shock_k)
gap_i,k(t)     = log(close_i(t) / close_i(t-k)) - beta_i(t) * btc_shock_k(t)
```

- beta：30D / min 15D rolling BTC beta，clip `[0, 4]`；
- `k ∈ {1, 2, 4}` 根 30m bar；
- gate：`z <= -2.5` 与 `z <= -3.0`；
- `h ∈ {4, 8, 16}` 根 bar；
- short tail：relative gap 最弱 10%；
- 每个横截面至少 8 个 PIT Top20 资产；
- 一次只允许一个 active short event，事件退出后才接受下一信号；
- 共 `3 × 2 × 3 = 18` 个 cell。

短腿内等权，事件 gross 固定 1.0；overlay 只使用 10%/20% 的 sleeve gross 做 return-space 诊断。

## 2. 选择与验收

只在 discovery 上按 6bps Sharpe 选一个 cell；要求 discovery 6bps 和 12bps Sharpe 都 >0。
Validation 和 OOS 不参与参数选择。候选必须满足：

- validation 6bps Sharpe >0 且 12bps Sharpe >0；
- OOS 2026-10-01 → 2026-11-13 的 6bps 终值 >1.0；
- full 6bps Sharpe >0.5，MDD 不差于 -30%；
- full 6bps 终值 >1.0；
- 若用于 LS57 overlay，10%/20% sleeve 的 full 终值和 Sharpe 均不得低于 LS57；MDD 允许不变差超过 2pp；
- 报告事件数、平均 gross、turnover、缺失 bar、月度/资产贡献。

通过只进入下一阶段：真实 Bitget mark/order-book、funding 和 partial-fill 检验；不直接接实盘。

## 3. 失败后动作

如果失败，不扫描 phase、offset、tail 8/12/15%、threshold 1.5/2.0/4.0、k/h 邻近值或把 short
改成 long-short。后续必须换经济机制或数据源，并把失败的粗结果保留在研究记录中。

## 4. 复现

```bash
.venv/bin/python scripts/run_intraday_down_shock_short.py \
  --bar-dir data/raw/binance_30m \
  --oos-bar-dir data/raw/binance_30m_oos_20261113 \
  --start-date 2022-01-01 --end-date 2026-09-30 \
  --output-dir reports/intraday_down_shock_short_2026
```
