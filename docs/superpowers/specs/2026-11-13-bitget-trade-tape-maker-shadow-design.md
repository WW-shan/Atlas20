# Atlas20 execution research: Bitget trade-tape maker shadow

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已预注册；执行诊断；不接实盘 |
| 候选 ID | `PR2026-11-EX3-TRADE-TAPE-MAKER-SHADOW` |
| 交易样本 | LS57 在 2026-01-01 → 2026-09-21 的全部实际 target trades |
| 数据 | Bitget 官方历史 transaction history（逐笔成交）+ depth Level1（top-of-book 快照） |
| 执行 | maker offset 5bps；timeout 2h；through strictness 1bp；adverse guard 30bps；maker fee 2bps；taker fee 20bps |
| 参考账户 | 500 USDT |
| 结论范围 | 只测执行，不改 LS57/LS23/L125-V2 的任何选币、权重或风控规则 |

## 0. 为什么做

之前的 maker-first 研究只用 1h mark 的 high/low 判断“价格是否触碰限价”，无法回答真实逐笔成交、部分成交、
主动单方向和未成交尾部。Bitget 官方历史下载提供逐笔 `timestamp/price/side/volume/size`，以及每天一张
Level1 top-of-book 快照。它们可以把执行假设推进一层：

```text
03:00 UTC 参考 mid = 当时可见 bid/ask mid
buy limit  = mid * (1 - 5bps)
sell limit = mid * (1 + 5bps)
```

真实卖方主动成交 `side=sell` 且价格 <= buy limit，才可能填 hypothetical buy；真实买方主动成交
`side=buy` 且价格 >= sell limit，才可能填 hypothetical sell。订单最多等待 2 小时；未成交部分走 taker。
30bps adverse guard 一旦被真实成交价格触发，立即把剩余部分 taker 回退。

## 1. 数据与覆盖

- `dateType=1` 日档；文件时间按交易所日切分（UTC+8），查询日期使用事件时间对应的 UTC+8 交易所日；2h 窗口跨日时合并相邻日文件。
- 逐笔文件可能被拆成多个 zip；按顺序读取，只保留 `[entry_time, entry_time+2h]` 范围内的 trades。
- Level1 depth 为 xlsx/xml 内联表，字段 `timestamp, ask_price, bid_price, ask_volume, bid_volume`。
- 只在 depth 有合格参考快照、且逐笔文件可用时纳入样本；缺失覆盖单独报告，不用 mark 价补齐。
- depth 与逐笔价格若相差 10 的整数次幂，只接受能使 midpoint 与 contemporaneous trade median 相差不超过 2% 的校正；其他偏差 fail closed。全样本触发的校正逐条报告。
- 逐笔 `volume(quote)` 按 USDT 名义解释，`size(base)` 用于交叉检查；不在两者不一致时静默猜测。

## 2. 两层 fill 口径

1. **touch（上界）**：主动成交方向匹配且 trade price 穿过限价即视为成交。这个口径没有证明队列位置。
2. **strict（主口径）**：buy 要求 trade price <= limit 再向下 1bp，sell 要求 trade price >= limit 再向上 1bp；
   逐笔累计 `volume(quote)` 达到订单名义才视为完全成交。仍不能证明我们排在真实队列中的位置。

主结论使用 strict；touch 作为乐观上界。部分成交按累计成交名义保留，剩余部分在 timeout/guard 时 taker。

## 3. 规则

```text
entry_time = LS57 trade timestamp (usually 03:00 UTC)
reference = latest valid L1 mid at/ before entry_time, max age 10 minutes
执行方向:
  long open/increase = buy; long reduce/close = sell
  short open/increase = sell; short reduce/close = buy
order_notional = abs(LS57 trade notional) * 500

每个 event:
  active_trades = 逐笔中 entry_time <= ts <= entry_time + 2h
  strict fill: 方向匹配、价格穿过 limit 至少 1bp，累计 volume(quote) 达到 order_notional
  guard: buy 的 adverse move = (trade_price/reference - 1) >= 30bps
         sell 的 adverse move = (1 - trade_price/reference) >= 30bps
  timeout: 2h 后仍未完成的部分以最后有效 trade price taker 成交
```

- maker 成交部分记 2bps；taker 回退/超时部分记 20bps。
- 有效成本 = (reference - buy_vwap)/reference 或 (sell_vwap - reference)/reference + fees；以 bps 表示。
- 不把 funding、liquidation、ADL、queue priority 或隐藏流动性算进本次诊断。

## 4. 验收标准

1. 覆盖到至少 **200** 个 trade event，且覆盖名义不低于 LS57 2026 样本的 70%；
2. strict 名义被动成交率 >= 70%；
3. 相对 20bps immediate-taker baseline 的有效成本改善 >= 5bps；
4. 未成交/guard 回退的名义占比和 5% 分位成本尾部完整报告；
5. 按 side、asset、月份拆分，且改善不能只来自一个 asset 或一个星期；
6. 2026-09-22 之后的真实 OOS 若可用，单独列出，绝不并入主样本；
7. 任何缺失 depth、缺失 trade、重复 trade_id 或时间倒序都 fail closed 或显式标记。

若 strict 口径失败，停止把 maker-first 当作 live 候选；不调 offset/timeout/guard 去救结果。若 strict 通过，
最高状态仍只是 **shadow execution candidate**：需要真实小单挂单/撤单验证队列和部分成交。

## 5. 复现

```bash
.venv/bin/python scripts/simulate_bitget_trade_tape_maker.py \
  --trades-path reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_stable1d_redistribute/PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE/trades.csv \
  --start-date 2026-01-01 --end-date 2026-09-21 \
  --equity 500 --output-dir reports/derivatives_track_trade_tape_maker_shadow_2026
```

研究输出不是订单，也不是实盘批准。
