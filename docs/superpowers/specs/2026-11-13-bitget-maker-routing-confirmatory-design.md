# Atlas20 execution research: long-open taker routing confirmatory test

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已预注册；独立确认样本；不接实盘 |
| 候选 ID | `PR2026-11-EX5-LONG-OPEN-TAKER-ROUTING` |
| 发现来源 | EX4 的 2026 样本显示 25% haircut 下 long open maker 改善为负 |
| 确认样本 | 2024-07-01 → 2025-12-31，完全早于 2026 discovery 样本 |
| 数据 | Bitget 官方 transaction history + Level1 depth，规则同 EX3/EX4 |
| 执行 baseline | 5bps offset；2h timeout；1bp through；30bps guard；2bps maker；20bps taker；25% volume haircut |
| 路由规则 | `position_side=long` 且 `action=open` 的 leg 立即 taker；其余 leg 保持 maker-first |
| 参考账户 | 500 USDT |

## 0. 为什么做

EX4 在 2026 样本中发现：25% haircut 下整体 maker 改善仍为 +6.9836bps，但 long open 的
14 个 event、54,810 USDT 名义为 **-6.0770bps**。这是一个事后观察，不能直接作为规则。
本轮只检验一个事先可解释的机制：开多腿更接近信息交易和竞争性买入，2h 被动等待更容易遭遇
逆向选择；因此把 **long open** 直接 taker，其他腿仍保留 maker-first。规则不按资产、月份、
信号强度或历史输赢切换。

## 1. 数据与规则

- 确认样本为 LS57 在 2024-07-01 → 2025-12-31 的 target trades；Level1 depth 可用性从
  2024-07 起纳入验收。
- 数据校验、UTC+8 日切、跨日窗口、价格尺度校正、重复 trade_id/时间顺序 fail-closed 与 EX3 相同。
- 每个 event 在同一数据读取中计算 25% haircut maker outcome，然后由路由分析器替换 long-open leg：
  - long open: maker fill = 0，taker fill = requested notional，effective cost = 20bps；
  - 其他 leg: 使用 25% haircut maker outcome。
- 不修改 offset、timeout、guard、fee 或 haircut；不扫描其他 action 组合。

## 2. 预注册验收

1. 确认样本至少 **300** 个 covered event，名义覆盖率 >= **70%**；
2. baseline（全 maker、25% haircut）加权改善 >= **5bps**；
3. long-open subgroup 的 baseline maker 加权改善必须 **<= 0bps**，支持路由机制；
4. routed policy 相对 baseline 的加权成本改善 >= **0.5bps**，且 routed 自身改善 >= **5bps**；
5. routed policy 在至少 **70%** 的有事件月份中改善 >= 5bps；
6. 剔除最大节省贡献资产后，routed 改善仍 >= **5bps**；
7. 按 side/action/asset/month 报告，并显式报告 taker 路由名义占比和尾部成本。

若任一项失败，reject 该路由规则；不得在确认样本上改成“所有 buy taker”、只对负贡献资产 taker、
缩短 timeout 或降低 haircut 来救结论。

## 3. 复现

先跑 25% haircut 的确认样本：

```bash
.venv/bin/python scripts/simulate_bitget_trade_tape_maker.py \
  --start-date 2024-07-01 --end-date 2025-12-31 \
  --equity 500 --haircut-sensitivity 0.25 \
  --output-dir reports/derivatives_track_trade_tape_maker_routing_confirm_2024_2025
```

然后运行路由分析器：

```bash
.venv/bin/python scripts/analyze_bitget_maker_routing.py \
  --events-path reports/derivatives_track_trade_tape_maker_routing_confirm_2024_2025/events.csv \
  --output-dir reports/derivatives_track_trade_tape_maker_routing_confirm_2024_2025/routing
```

研究输出不是订单，也不是 live 执行批准。
