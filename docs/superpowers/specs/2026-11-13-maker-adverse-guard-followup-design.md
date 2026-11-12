# Atlas20 execution research: maker-first adverse guard follow-up

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 事后 follow-up 已完成；shadow candidate；不接实盘 |
| 候选 ID | `PR2026-11-EX2-MAKER-GUARD30` |
| 基线 | `PR2026-11-EX1-MAKER-FIRST`（5bps offset / 2 bars / 1bp through） |
| 交易样本 | `PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE` |
| 主数据 | Bitget USDT-M mark 1h K 线 |
| 交叉检查 | Binance 30m K 线 |
| 冻结参数 | adverse guard **30bps**；offset 5bps；timeout 2 bars；through 1bp；maker 2bps；taker/base 20bps |

## 0. 为什么做这个 follow-up

第一轮 maker-first 诊断的平均改善为 +11.55bps，但未成交回退的尾部很大：
未成交名义占 8.60%，改善中位数 -76.26bps，5% 分位 -278.55bps。仅靠 2 bars timeout
会在第一小时已经明显逆向时继续等待第二根 K 线，可能把可控的 taker 回退拖成更大的追价。

**这不是独立样本外的预注册。** 30bps guard 是在看到第一轮尾部后提出的 follow-up；
它的作用是把风险控制写清楚并验证，不是把结果包装成新的 alpha 或 promotion 证据。

## 1. 规则

```text
在每个冻结成交时点：
    reference = 第一根 1h bar 的 open
    buy limit  = reference * (1 - 5bps)
    sell limit = reference * (1 + 5bps)
    through    = limit 再向不利方向 1bp

    每根未成交 bar 检查：
        adverse_move = (close - reference)/reference（buy）
        adverse_move = (reference - close)/reference（sell）
        若 adverse_move >= 30bps：
            立即在该 bar close 以 taker 回退
        否则继续等待，最多 2 bars
```

- 填满：maker 2bps，成交价=limit；
- adverse guard 或 timeout：taker 20bps，成交价=触发 bar close；
- 其余 alpha、目标权重、T+1、空头、stop、gross 均不变。

## 2. 验收标准

1. Bitget mark 成交名义覆盖率 >=95%；
2. 名义加权被动成交率 >=85%；
3. 有效成本相对 20bps 基线改善 >=8bps；
4. 未成交回退改善 5% 分位不差于第一轮的 -278.55bps，且中位数有改善；
5. 2022–2026 至少 4/5 年改善为正；
6. Binance 30m 交叉检查方向一致；
7. 不改变 LS57/LS23/L125-V2 的任何实盘规则。

若通过，最高状态仍是 **shadow execution candidate**，必须用真实盘口/订单簿验证；不能把模拟
成本直接写入 live 成本假设。若失败，记录负结果，不通过继续调 guard、offset、timeout 或费率
救活。

## 3. 复现

```bash
.venv/bin/python scripts/analyze_maker_execution.py \
  --trades-path reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_stable1d_redistribute/PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE/trades.csv \
  --bar-source bitget-mark \
  --raw-dir data/raw/bitget_derivatives/merged_20261009 \
  --adverse-guard-bps 30 \
  --output-dir reports/derivatives_track_maker_execution_guard30_bps
```

## 4. 结果（2026-11-13）

Bitget mark 主结果（2,524 笔，名义 1,707.1142）：

| 指标 | 无 guard（第一轮） | 30bps guard |
|---|---:|---:|
| 名义覆盖率 | 100% | **100%** |
| 被动成交率 | 91.40% | **90.48%** |
| 有效成本 | 8.45bps | **7.06bps** |
| 相对基线改善 | +11.55bps | **+12.94bps** |
| guard 触发名义占比 | — | 8.49% |
| 未成交名义占比 | 8.60% | 9.52% |
| 未成交改善中位数 | -76.26bps | **-64.17bps** |
| 未成交改善 5% 分位 | -278.55bps | **-214.08bps** |

2022–2026 年度改善为 **+15.00 / +14.97 / +11.91 / +14.15 / +12.05bps**，五年全为正。
Binance 30m 交叉检查（覆盖率 81.61%）为 +11.46bps，未成交 5% 分位 -136.83bps，方向一致。

**判定：follow-up 通过，但仍是事后 shadow 结果。** 30bps guard 改善了平均成本和尾部，但没有
解决 mark K 线触碰不等于真实成交、队列位置、部分成交和撤单延迟。下一步必须是真实
盘口/订单簿 shadow，不是直接改 live executor。

报告：`reports/derivatives_track_maker_execution_guard30_bps/`；
交叉检查：`reports/derivatives_track_maker_execution_guard30_bps_binance_30m/`。

## 5. 状态

- 预注册：是（事后 follow-up）；
- 正式运行：是；
- 实盘：否；
- 修改当前实盘：否。
