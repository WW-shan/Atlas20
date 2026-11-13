# Atlas20 研究预注册：LS66 intraday lead-lag fresh OOS

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | fresh OOS shadow validation；不是实盘候选 |
| 候选族 ID | `PR2026-11-LS67-INTRADAY-LEADLAG-FRESH-OOS` |
| 待验证 | LS66 的 `LL_P4_8_T35` 及四个固定 cell / ensemble |
| 数据 | Binance 30m，2026-09-01 起用于 beta warm-up；fresh OOS 从 2026-10-01 开始 |
| 最新数据 | 2026-11-13 02:30 UTC（下载时实际最后 bar） |
| 执行 | 完全沿用 LS66：phase-0 UTC、10% tail、3.0/3.5σ、单事件 full gross |
| 成本 | 6 / 12 / 20bps per one-way gross turnover |
| Funding | 未计；OOS 仅 6 周，不能替代 12 个月 OOS |

## 0. 研究问题

LS66 的 `LL_P4_8_T35` 在 2022–2026 样本上是 **1.5548x / Sharpe 0.9612 / MDD -4.28%**，但 phase、
tail 和 threshold 都来自之前的筛选，不能算独立验证。现在使用 2026-10-01 之后**没有参与
任何研究决策**的 Binance 30m 数据，检验同一冻结规则是否仍有可用净 edge。

由于 raw cache 原有历史止于 2026-09-30，且新的 30m cache 只有 30/32 个资产（MATIC/XMR 当前
Binance spot pair 不可用），本轮必须显式报告覆盖缺口，不能用历史缓存或零收益静默补齐。Beta
使用 2026-09-01 之后的 warm-up 数据；OOS 事件只允许在 2026-10-01 00:00 UTC 之后入场。

## 1. 冻结规则

- 变体：`LL_P2_8_T30`、`LL_P2_8_T35`、`LL_P4_8_T30`、`LL_P4_8_T35`、等权 ensemble；
- tail 10%，phase 0，单事件 full gross，最多一个活跃事件；
- 6/12/20bps per side；不扫描新参数；
- 事件必须在 OOS 窗口内入场，且在退出时完整结算；窗口边界外的持仓不进入统计；
- 只报告 OOS 描述性指标、事件数、覆盖和 benchmark，不因为短窗口结果修改 LS66。

## 2. 分层与解释

- `fresh-oos-positive`：`LL_P4_8_T35` 在 6bps 和 12bps 的 OOS 终值都 > 1.0，且 MDD > -15%；
- `fresh-oos-mixed`：6bps > 1.0，但 12bps 或风险不通过；
- `fresh-oos-failed`：6bps 终值 <= 1.0。

即使 positive，也只能把 LS66 留作 shadow；6 周不能建立 promotion 证据。若 failed，LS66 从
watch 降为 rejected，且不继续调 phase/tail/threshold 去救同一结果。

## 3. 复现

```bash
.venv/bin/python scripts/run_intraday_btc_leadlag_fresh_oos.py \
  --start-date 2026-09-01 \
  --end-date 2026-11-13 \
  --oos-start 2026-10-01 \
  --bar-dir data/raw/binance_30m_oos_20261113 \
  --output-dir reports/intraday_btc_leadlag_fresh_oos_20261113
```
