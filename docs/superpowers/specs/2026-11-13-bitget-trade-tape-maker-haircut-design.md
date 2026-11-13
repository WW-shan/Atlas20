# Atlas20 execution research: trade-tape maker fill haircut sensitivity

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已预注册；执行诊断；不接实盘 |
| 候选 ID | `PR2026-11-EX4-TRADE-TAPE-MAKER-HAIRCUT` |
| 上级诊断 | `PR2026-11-EX3-TRADE-TAPE-MAKER-SHADOW` |
| 交易样本 | LS57 在 2026-01-01 → 2026-09-21 的全部实际 target trades |
| 数据 | 与 EX3 相同的 Bitget transaction history + Level1 depth |
| 主参数 | 5bps offset；2h timeout；1bp through；30bps adverse guard；2bps maker；20bps taker；500 USDT |
| 敏感性 | 每个主动成交 print 只有 **25% / 50% / 75%** 的 quote notional 可被 hypothetical maker 获得 |
| 结论范围 | 只测队列位置不确定性对 EX3 成本结论的影响；不改策略、不改 live executor |

## 0. 为什么做

EX3 的 strict fill 要求主动成交价格穿过 hypothetical limit 至少 1bp，并把每笔 print 的完整
`volume(quote)` 当作可获得成交量。这仍然高估了假设订单的队列优先级：即使真实成交打印穿价，
我们前面可能仍有未成交的队列、隐藏单或更快的撤单/改单者。为了把这一不可观测项变成显式压力，
本轮不预测真实 queue，而是对每笔可成交量施加确定性的 haircut：

```text
available_maker_quote = trade.quote_notional * haircut
haircut ∈ {0.25, 0.50, 0.75}
```

未获得的剩余名义继续按 EX3 规则等待；timeout/guard 时以最后有效 trade price taker 回退。
这是比 EX3 更保守的成交能力假设，不是另一个策略 alpha，也不是对真实 fill 概率的校准。

## 1. 数据与规则

- 数据、UTC+8 日切、跨日窗口、depth/trade 价格尺度校验、重复 trade_id/时间顺序 fail-closed
  规则与 EX3 完全相同。
- 参考账户固定 500 USDT；每个 event 的订单名义与 EX3 相同。
- 三个 haircut 场景在同一次数据读取中计算，避免不同下载批次造成样本差异。
- maker 部分仍记 2bps，taker 回退仍记 20bps。
- touch（0 haircut strictness）不再作为主结论；主表只报告 25/50/75% 三个 strict 场景。
- 不重新选择 offset、timeout、guard、fee、asset、月份或样本起点。

## 2. 预注册验收标准

1. 覆盖与 EX3 相同的至少 200 个 event 和 70% 名义；
2. **25% haircut** 下，名义加权有效成本改善仍 >= **5bps**；
3. 50% 与 75% 场景必须单调不劣于 25% 场景（允许数值噪声，但不得出现方向性反转）；
4. 完整报告 maker fill、taker fallback、guard/timeout、有效成本 p05/p95；
5. 按 side、asset、月份报告，检查改善不能只来自单一资产或单周；
6. 若 25% 场景失败，不得通过扫描 haircut 或调参数来救结论；只能记录失败，并把 maker-first
   降级为需要真实小单挂撤单证据的执行假设。

## 3. 复现

```bash
.venv/bin/python scripts/simulate_bitget_trade_tape_maker.py \
  --start-date 2026-01-01 --end-date 2026-09-21 \
  --equity 500 --haircut-sensitivity 0.25,0.5,0.75 \
  --output-dir reports/derivatives_track_trade_tape_maker_haircut_2026
```

输出中的 `haircuts.csv` 是三个场景的汇总；`events.csv` 保留逐 event 的所有场景。研究输出不是
订单，也不是实盘批准。
