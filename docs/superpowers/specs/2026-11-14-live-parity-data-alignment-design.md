# LS45-G125 实盘/回测/数据全链路对齐设计

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-14 |
| 状态 | 已获负责人批准，进入实施 |
| 当前策略 | `PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21` |
| 唯一成交时钟 | `D+1 01:05 UTC`（北京 09:05） |
| 目标 | 信号、数据、目标账本、回测、实盘执行、对账和监控使用同一口径；不静默覆盖旧 03:00 结果 |

## 1. 问题

当前代码和研究记录存在两套成交时钟：

- 冻结研究账本的 `execution_hint` 是 `D+1 03:00 UTC`；
- 实盘执行器使用 `D+1 01:05 UTC`；
- 研究引擎只支持整点 `execution_hour`，不能表达 01:05；
- 实盘每日把逐仓保证金归一到当前名义的约 51.5%，研究引擎没有同一日级保证金归一化；
- 实盘使用 Bitget 合约步长/最小下单量，研究主结果使用理想名义；
- 数据采集、目标账本、manifest、审计和监控缺少统一的输入哈希与数据质量门禁。

因此不能把当前实盘称为“与回测一比一”。

## 2. 目标口径

### 2.1 唯一时间

- 信号日：`D` 的 UTC 日线收盘后，只使用已完成日线。
- 目标账本：`execution_hint = D+1 01:05 UTC`。
- 回测成交：`D+1 01:05 UTC`。
- 实盘执行：`D+1 01:05 UTC`，窗口内重试，窗口外必须人工确认。
- 01:05 落在 01:00 开始的 1H mark candle 内。历史 1H 数据无法证明 01:05 的逐笔成交，因此研究使用 `01:00 mark open` 作为执行价代理，并在 manifest 中明确记录 `execution_price_model=mark_1h_open_floor`。
- 实盘使用真实 ticker/market order；回测与实盘的差异作为执行偏差报告，不伪称为相同成交。

### 2.2 回测模型

保留两种结果：

1. **ideal research**：无合约量化、无每日保证金归一化，用于和历史结果比较。
2. **live-parity research**：与实盘执行层同口径，作为当前 LS45 的主报告。

live-parity 必须包含：

- `01:05 UTC` 执行时钟；
- 逐仓保证金每日归一到当前名义的 51.5%；
- Bitget 合约 `size_multiplier`、`min_trade_usdt`、数量/价格精度；
- 20% mark-price short stop；
- 止损触发后的 5bps adverse slippage；
- 20bps 保守成本主口径；
- 6bps venue taker fee 作为敏感性口径；
- 当前约 500 USDT 账户规模，并附 1000 USDT 参考规模；
- 所有未成交、低于最小下单量、保证金调整和量化误差都写入审计文件。

历史合约规格无法从当前 Bitget 快照证明，因此：

- 全样本 live-parity 使用冻结 `symbol_map.csv` 的 `size_multiplier/min_trade_usdt`，并在 manifest 中记录这是 current-snapshot approximation；
- 当前/前向 live-parity 使用 `contracts.json` 的完整规格；
- 不把 current-snapshot 量化结果声称为历史真实成交。

### 2.3 数据可靠性

新增统一数据审计，至少覆盖：

- CMC/processed panel：文件可读、日期、重复 `(date, coin_id)`、未来日期、最后完成日、Top20 最小资产数、价格/市值/成交量有效性、最新日完整性。
- Symbol map：`coin_id` 唯一、`bitget_symbol` 唯一或明确 direct alias、费率/资金费间隔/最小下单/步长字段完整。
- Mark candles：每个所需资产文件存在、时间单调、无重复、无未来时间、OHLC 合法、价格为正、评估窗口小时覆盖、最大缺口、最后 mark。
- Funding：文件存在、时间单调、无重复、费率有限、最后结算时间、资金费间隔、持有资产覆盖率；funding 过期时不得继续选空头。
- Contracts：`online`、`perpetual`、2x 支持、数量/价格步长、最小下单量、taker fee、funding interval。
- Cross-source：mark/market 同日/同小时对齐、极端偏差、缺失和 stale 重复。
- Provenance：panel、symbol map、contracts、coverage、funding manifest、target ledger、mark 文件集合的 SHA-256。
- 数据审计必须 fail closed；历史已知缺口只作为明确 warning，不得静默填零。

### 2.4 实盘门禁

实盘执行前必须同时满足：

1. `audit-data` 通过；
2. `audit-signal` 通过；
3. manifest 的 `tracked_spec`、冻结参数、`execution_utc`、成本和数据哈希与当前文件一致；
4. 账户指纹绑定；
5. isolated 2x、保证金缓冲、空头 stop、无未成交普通单、无孤立策略单；
6. `audit-live` 通过；
7. 当日幂等/窗口/补跑门禁通过。

### 2.5 验收标准

- 所有信号账本 `execution_hint` 为 `D+1 01:05 UTC`。
- LS45 全样本 01:05 live-parity 报告生成，并与旧 03:00 ideal 报告并列保存。
- 01:05 live-parity 回测的每个 rebalance 能被 live planner 逐笔复现；量化误差、跳过订单、保证金调整全部有审计记录。
- 数据审计对当前 raw data 通过；任何未来时间、重复、非法 OHLC、缺失最后完成日、funding 过期或 symbol 歧义必须失败。
- 实盘 dry-run、`audit-live`、`audit-signal`、`audit-data` 全部通过。
- Python 全量测试、前端测试、Ruff、mypy、前端 lint/typecheck/build 全部通过。
- 旧 03:00 结果不被删除或覆盖；新结果明确标注 provisional/live-parity。
