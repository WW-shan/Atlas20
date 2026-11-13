# LS45-G125 Bitget USDT-M 实盘 Runbook

> 当前实盘规格：**`PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21`**
>
> - 标的：Bitget **USDT-M 永续**，允许有符号多空账本；
> - H5 多头 + 利润保护 + 空头路由 + 21D 强持有者再分配；
> - 目标 **gross 硬上限 1.25x 权益**，实际 gross 可以更低，空仓即 100% cash；
> - 交易所杠杆配置 **2x isolated**，多空每腿 initial buffer 均为 **50%**；
> - 空头开/加仓附带 **20% adverse move、mark-price、market stop**；
> - 研究执行口径为 **T+1 +3h = 03:00 UTC**；事件账本保留自己的 `execution_hint`；
> - 实盘采用负责人批准的早盘快路径：manifest 最新完成日 **T+1 01:05 UTC**
>   （北京 09:05，约为收盘后 +1h5m），目标权重仍取最新事件行；
> - 实盘主任务在 **01:05 UTC** 运行；
> - 成本口径 20 bps，funding 使用 Bitget exact；
> - 当前策略书与选择证据：`docs/superpowers/specs/2026-11-13-ls103-live-candidate-selection.md`；
> - 研究记录：`RESEARCH.md` §00.138；回测产物：`reports/ls45_live_g125/`。
>
> 本文只描述执行与恢复，不允许在实盘中临时改参数。运行时代码和状态优先于本文摘要。

---

## 1. 当前自动化拓扑

### 1.1 macOS（本机默认）

| launchd 任务 | 北京时间 | 作用 | 日志 |
|---|---|---|---|
| `com.atlas20.daily-refresh` | 08:30、08:50、10:30、10:55、14:30 | 刷新 CMC/Binance/Gate 面板；已有完整数据时跳过 | `~/Library/Logs/atlas20-daily-refresh.log` |
| `com.atlas20.cmc-probe` | 08:05–11:50 每 15 分钟 | 记录 CMC 发布完成时刻，研究用 | `~/Library/Logs/atlas20-cmc-probe.log` |
| `com.atlas20.derivatives-execute` | **09:05**；重试 09:35、11:05、11:35、12:35、14:35 | 刷新 Bitget mark → 生成 LS45 账本 → 按真实权益执行 → 写 journal → Telegram | `~/Library/Logs/atlas20-derivatives-execute.log` |
| `com.atlas20.live-monitor` | 19:00 | 只读全链路巡检；异常才发消息 | `~/Library/Logs/atlas20-live-monitor.log` |
| `com.atlas20.protect-live-logs` | 登录时 + 每 5 分钟 | 保护运营日志不被清理工具删除 | `~/Library/Logs/atlas20-log-protect.log` |
| `com.atlas20.keep-awake` | 登录时常驻 | `caffeinate -dimsu` 防止机器/磁盘空闲睡眠；KeepAlive 自动拉起 | `~/Library/Logs/atlas20-keep-awake.log` |

主任务入口固定为：

```text
com.atlas20.derivatives-execute
  -> ops/run_derivatives_daily.sh
  -> make derivatives-live
     -> derivatives-live-data
     -> derivatives-ls45-signal
     -> scripts/execute_live_plan.py --live --notify --require-isolated
```

`derivatives-live-data` 使用稳定目录：

```text
data/raw/bitget_derivatives/merged_oos_20261112/
```

下载器每天用滚动窗口追加/修复 mark，不再回退到旧的 `merged_oos_20261009` 实盘源。

### 1.2 Ubuntu（可选，不能与 macOS 同时跑）

```bash
sudo cp ops/systemd/atlas20-data-refresh.{service,timer} /etc/systemd/system/
sudo cp ops/systemd/atlas20-derivatives-execute.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now atlas20-data-refresh.timer atlas20-derivatives-execute.timer
```

- execute timer：01:05 / 01:35 / 03:05 / 03:35 / 04:35 / 06:35 UTC；
- `Persistent=true`：重启后补跑错过的一次；
- 补跑仍经过窗口闸和当日幂等闸；
- 不要同时安装 `atlas20-derivatives-signal.timer` 与 execute timer。signal timer 只给“不下单、只播报”的备用部署使用。

---

## 2. 信号与执行时点

事件账本每行包含权威字段 `execution_hint`。当前 LS45 账本固定为：

```text
signal_date D 00:00 UTC
execution_hint D+1 03:00 UTC
```

这个字段描述**该事件行**的研究回测成交口径（T+1 +3h）。Telegram 会同时显示
研究口径和实盘快路径，避免把 11:00 误认为真实下单时间。每日自动执行不能直接
拿事件行当窗口：如果账本连续多日没有新事件，它会被误判为“数天前的任务已过期”。
执行器改为从 manifest 的最新已完成数据日计算：

```text
daily_execution_hint = manifest.signal_end_date + 1 day + 1 hour 5 minutes
                     = signal_end_date + T+1 01:05 UTC
```

目标权重仍取最新事件行；止损校验、账户对账和 journal 则每天都按
`daily_execution_hint` 运行。因此事件信号可以显示旧信号日，但定时任务不会
因为“今天没有新交易事件”而失效。

实盘主任务在 01:05 UTC 开始，早于研究回测的 +3h 成交口径，但信号仍只使用
D 日收盘及之前的数据。重试点在：

```text
01:05 UTC = 09:05 北京  primary
01:35 UTC = 09:35 北京  retry
03:05 UTC = 11:05 北京  fallback
03:35 UTC = 11:35 北京  fallback
04:35 UTC = 12:35 北京  fallback
06:35 UTC = 14:35 北京  final retry
```

交易窗口从 01:05 UTC 起 6 小时，即最晚到 07:05 UTC / 15:05 北京。窗口外只允许人工显式 `--force` 补做；即使 `--force`，当日已成功、数据不新鲜、风险或对账闸门仍会阻止重复交易。

---

## 3. 自愈、补跑和幂等

`ops/run_derivatives_daily.sh` 在每次 launchd/systemd 启动时按顺序执行：

1. **窗口闸**：`scripts/live_chain_preflight.py --check window`
   - 01:05 UTC 前退出；
   - 当日状态已 `ok` 退出；
   - 超过 6 小时补跑窗口退出；
   - 退出码 3 表示“设计上不交易”，不是故障。
2. **面板自愈**：`--check panel`
   - 面板落后或最后一天不完整时，运行 `refresh_daily_data.py --force --wait-seconds 900`；
   - 刷新后再次检查，仍不完整就拒绝下单。
3. **数据与账本**：`make derivatives-live-data derivatives-ls45-signal`
4. **执行**：`scripts/execute_live_plan.py --live --notify --require-isolated`

执行器自身还有：

- 持有 `data/ls45_g125_execution.lock` 的进程级 `flock`；另一个实例直接退出；
- mark 新鲜度硬阈值 30h；
- 目标账本评估日必须等于数据最新可判定日；
- 实时 ticker 不得超过 120s、价格必须可用；
- account equity 不低于 20 USDT；
- kill switch 文件存在时拒绝一切操作；
- 每个 run day 只允许一个 `ok`；`partial` 会在后续重试窗口重读账户并自愈；
- 同一 run day 的 clientOid 稳定；请求超时或缺少 `orderId` 时按 clientOid 回查，避免重启重试
  把“已接受但响应丢失”的订单再下一遍；
- clientOid 按订单业务身份做稳定哈希，不再使用“当前订单数组下标”；前面订单成交后，
  下一轮计划不会因为序号左移而撞上已成交订单的 clientOid；
- 同日重试会按 `orderId/clientOid` 合并已有成交，而不会用当前轮的空 `trades` 覆盖当日已落账成交；
- 若订单已在交易所成交、但进程在写 journal 前崩溃，下一轮会从当日 `order-history`
  找回当前 prefix 的成交并补入 journal；
- journal/state/latest/audit/monitor/capital-flow 写入均为同目录临时文件 + `fsync` + `os.replace`；
- 成交、journal、latest.json、通知全部成功后才写 `ok`；
- journal 或 Telegram 写失败时不会把 run 标记为完成，下一轮可以继续；
- 未捕获的顶层异常会写 `latest.json(status=error)` 并尝试发 Telegram 告警，不写 `ok`。

kill switch：

```bash
touch data/ls45_g125_execution.KILL   # 立即阻止新的执行
rm data/ls45_g125_execution.KILL      # 恢复
```

注意：kill switch 只阻止新一轮执行，不会自动平仓；已有仓位仍由交易所止损及人工操作管理。

---

## 4. 多空与空头止损

### 4.1 有符号账本

`target_weight > 0` 为多，`target_weight < 0` 为空。执行器：

- 开多：`buy + posSide=long`（hedge）或 `buy`（one-way）；
- 开空：`sell + posSide=short`（hedge）或 `sell`（one-way）；
- 平多：`sell`；
- 平空：`buy`；
- 方向翻转始终先 `CLOSE`，再 `OPEN`；
- gross 使用 `Σ abs(signed_notional)`，不是净头寸；
- 目标 gross 硬上限为账户权益 × 1.25。

### 4.2 空头 20% 止损

空头开/加仓时，订单本身附带：

```text
stopLoss    = 预计成交后的加权入场价 × 1.20
slTriggerBy = mark
slOrderType = market
```

计划器会按现有空头数量、已有入场价和新增订单数量计算预计加权入场价，因此加仓后止损不会停留在旧仓位的价格。

执行器成交后必须从交易所 `order-info` 回读 `stopLoss`：

- 同时核对 `stopLoss / slTriggerBy / slOrderType`，必须等于请求价格、`mark`、`market`（UI 文案仍称 mark-price）；
- 回读一致：把三字段和 `position_side / client_oid / status` 一并记录到 journal；
- 未确认：立即市价买回平掉该空头（`EMERGENCY_CLOSE`），并把本次 run 标记为 `partial`；
- 空头加仓的止损未确认时，平掉该 symbol 当前完整空头腿，而不只是新加的数量；
- 下一次重试会重新读取真实账户，不会重复开仓；
- `audit-live` 会核对 journal 中带止损的空头成交与交易所订单历史的 `stopLoss / slTriggerBy / slOrderType`。

Bitget 的策略止损是**按入场订单/加仓订单保留**，不会自动合并：

- 空头 2 → 4 加仓后，交易所会同时保留旧 `qty=2` 和新 `qty=2` 两张止损策略单；
- 空头 4 → 2 部分减仓后，交易所不会自动把两张策略单缩成一张，仍可能保留总 `qty=4`；
- 因此每轮执行在最终验仓前会把当前空头归一为**一张策略单**：`qty = 当前空头数量`，
  `stopLoss = 最新加权入场价 × 1.20`（向上取整），`slTriggerBy=mark`，`slOrderType=market`；
- 归一使用 Bitget `modify-strategy-order` 调整保留单，再用 `cancel-strategy-order` 取消重复单；
- 若同一 symbol 出现无法识别的策略单，不猜测、不修改，直接按空头止损未证实处理并 emergency close；
- 归一后重新查询交易所；必须恰好一张、数量等于当前仓位、价格等于目标止损，否则本次 run 为 `partial`。

止损保护按当前空头开仓周期维护。平仓后旧 journal 中的历史 stop 不会继续保护后续重开的空头；
当前空头若没有完整的当周期入场 stop 记录，会先被 `EMERGENCY_CLOSE`。

空头止损阈值与回测一致：`entry_price × 1.20`，mark price 触发。

---

## 5. 保证金与交易所限制

当前规格要求 **isolated**。自动链使用 `--require-isolated`：

- 逐仓杠杆设置失败：跳过该腿并写失败，不降级为 crossed；
- 下单时交易所拒绝逐仓：不重试 crossed，直接失败；
- 执行前持仓回读不是 isolated：阻断全部新开/加仓，只允许 reduce/close；
- 执行后持仓回读不是 isolated：增加硬失败，状态不会是 `ok`。

生产路径只设置目标方向的 isolated leverage，不要求 crossed leverage 设置成功。

若 API key 是“精英交易/跟单”类型，可能不支持逐仓、`set-margin`、one-way 或持仓模式切换。正确做法是换普通 API key，不是放宽执行器。

**2026-11-14 账户迁移与当前 key 真钱 venue drill：**

- 旧 elite/copy 账户已关闭，API 返回 `40037 Apikey does not exist`；旧账户的
  drill 报告已归到 `reports/archive/ls45_live_elite_20261113/`，不再作为当前账户证据；
- 新账户指纹 `cb05dac7a33ea24f`，`accountMode=unified`、`assetMode=multi_assets`；
  `traderType=trader`，但权限只有 `uta_trade` / `uta_mgt`，**没有**
  `copy_futures_*`；
- `traderType=trader` 本身不是 isolated 禁用条件；真正阻断的是 copy-futures 权限。
  该判断已由 `tests/test_derivatives_account.py` 固定；
- 2 NEAR 多头：2x isolated 开仓、方向/保证金/杠杆回读、立即平仓，通过；
- 2 NEAR 空头：2x isolated 开仓，附带 `stopLoss=entry×1.20`、`slTriggerBy=mark`、
  `slOrderType=market`；交易所策略单回读通过；
- 空头 2 → 4 加仓后出现两张 `qty=2` 策略单，执行器归一为一张 `qty=4`；
  4 → 2 部分减仓后缩为 `qty=2`；清仓后策略单自动消失，全程无 emergency close；
- `set-margin(add/remove)` 在 isolated 短仓上往返成功，保证金余额回读一致；
- 所有演练完成后为 0 持仓、0 普通挂单、0 策略单；演练后权益
  **499.6296 USDT**，作为新账户 journal baseline；
- 证据：`reports/ls45_live_g125_live/account_migration.json`；
  精确 drill `orderId` 登记在
  `reports/ls45_live_g125_live/venue_drill_order_registry.json`（当前 6 笔），
  不混入生产 journal。

当前账户已在真实交易所验证满足 isolated 规格。执行状态文件带账户指纹；
`audit-live` 会拒绝旧账户或未绑定的 legacy state。

保证金路径：

1. symbol 设置 2x isolated；
2. 成交后交易所自动占用约 50% 名义；
3. 执行器按计划调用 `set-margin(add/remove)`，把每腿保证金补到约 51.5%；
4. 交易所拒绝 `set-margin` 时记录 margin note；若持仓模式本身不是 isolated，则按上面的硬失败处理。

---

## 6. 关键文件与状态

| 路径 | 内容 |
|---|---|
| `reports/ls45_live_g125/oos_targets.csv` | 冻结的有符号目标账本 |
| `reports/ls45_live_g125/manifest.json` | 数据覆盖、spec、funding、冻结参数、评估日 |
| `reports/ls45_live_g125/report.md` | LS45 研究回测报告 |
| `reports/ls45_live_g125_live/latest.json` | 最近一次真实执行的计划、报价、报告 |
| `reports/ls45_live_g125_live/journal.csv` | 每日权益、仓位、成交、止损记录、notes |
| `reports/ls45_live_g125_live/audit.json` | 只读对账输出 |
| `reports/ls45_live_g125_live/health.json` | 19:00 巡检快照 |
| `reports/ls45_live_g125_live/account_migration.json` | 当前账户迁移、baseline 与 isolated 演练证据 |
| `data/ls45_g125_execution_state.json` | 执行幂等状态 |
| `data/ls45_g125_telegram_state.json` | Telegram 播报幂等状态 |
| `data/ls45_g125_execution.KILL` | kill switch（存在即停止新执行） |
| `data/ls45_g125_execution.lock` | 进程级执行锁；OS 在进程退出时自动释放 |
| `reports/derivatives_track_live/capital_flows.csv` | 账户级外部资金流；入金/出金不能计为策略 PnL |

`data/` 是本地运行状态，不随 git 部署。**同一账户**迁移机器时必须同步 credentials、
`data/ls45_g125_execution_state.json`、`data/ls45_g125_telegram_state.json`、journal 和
所需 raw/processed 数据，否则会重复执行或重复播报。换 Bitget 账户时必须归档旧 state/journal
并建立新 baseline，不能让旧账户的 `account_fingerprint` 混入新账户。

---

## 7. 常用命令

### 7.1 只读检查

```bash
make audit-live
make derivatives-signal                 # Telegram 文本 dry-run
make execution-plan-live                # 读真实账户，只发计划，不下单
make execute-plan                       # 读真实账户，执行器 dry-run，不下单
ops/run_live_monitor.sh                 # 只在异常时发 Telegram
```

### 7.2 手动执行链

```bash
ops/run_derivatives_daily.sh            # 遵守窗口和幂等
ops/run_derivatives_daily.sh --force    # 只跳过窗口闸
```

同日成功后重跑会直接跳过。`--force` 不是“强制重复交易”，只是允许窗口外补跑一次未完成的当日任务。
进程在状态落盘前崩溃时，同日重试复用确定性 `clientOid`，以便从订单历史恢复已成交订单；
若前一次失败已经写入 state，则下一次 attempt 使用新的确定性前缀，避免交易所把新补单误判为旧幂等键。
失败重试按前一次同日 journal 的 `run_at_utc` 只追加新的外部资金流；旧资金流/数据新鲜度提示会被本轮提示替换，不会重复记账。
来自公网的瞬时连接、TLS 或 429/5xx 会做有限次指数退避；响应成功但内容无效仍然 fail closed。

权益跌到 20 USDT 以下或非正数时，执行器不再整体拒绝运行：它会抑制所有新开/加仓和保证金追加，
但仍允许 reduce/close、止损核对、记账和告警。这样不会因为“余额太小”把现有风险锁在仓位里。
任何已存在的异常策略单（例如无持仓的 TP/SL、long 上的策略单、short 上非 mark/market stop）
都会在真实下单前阻断新风险；策略单接口不可用时，开仓同样 fail closed，减仓/平仓仍继续。

### 7.3 资金流

任何入金/出金后：

```bash
make record-capital-flow AMOUNT=400 NOTE='入金'
make audit-live
```

资金流从当日 PnL 中剔除；不要把它算成收益或亏损。

---

## 8. `audit-live` 的硬校验

`scripts/audit_live_track.py` 只读，当前正常路径为 **28 项硬检查 + 1 项非硬告警**：

1. venue drill 精确 `orderId` 登记表可读；只豁免登记过的 drill 订单；
2. 账户 API 必需字段完整且有限；
3. 账户权益不低于执行下限 20 USDT；
4. 持仓 API 必需字段完整、方向合法且标记价有限；
5. 当前没有未成交普通订单；
6. 同一合约没有重复或反向对冲腿；
7. `equity = USDT-equivalent collateral + unrealisedPnl`；multi-assets 账户的非 USDT
   抵押品按交易所 `usdValue` 计入；
8. 交易所 `positionValue` = `Σ abs(qty) × markPrice`；
9. 所有持仓合约都能在冻结 symbol map 中唯一映射；
10. 每腿 `marginMode=isolated`、杠杆 2x、保证金缓冲不低于 45%；
11. API key/账户分类未命中 copy-trading/elite 逐仓限制；
12. 执行状态带账户指纹，且与当前 Bitget 账户一致；旧/未绑定 legacy state 失败；
13. journal 最新权益按实时 mark 和外部资金流折算后等于账户；
14. journal PnL 链在剔除 capital flow 后连续；
15. journal `funding_total` 等于持仓未变化区间的累计资金费差；
16. journal 每笔成交都能在交易所订单历史对上数量、均价、手续费；
17. 交易所当前 prefix 的已成交 Atlas20 订单全部已记账（反向核对）；
18. 空头 journal 入场必须记录已确认止损；
19. 当前每个空头仓都有交易所**当前可见**的 mark-price market 策略止损单；
20. 策略单必须与当前空头止损/数量对应，不能有孤立策略单；
21. 冻结目标 gross 不超过 1.25x；
22. 有符号目标 vs 有符号实际仓位：多头正、空头负；容差为 1 USDT、目标名义 1% 和 1.5 个合约步长三者取大；
23. 无计划外持仓；
24. 实际 gross = `Σ abs(notional)` ≤ 1.25 × equity；
25. mark 数据 ≤ 30h，且 manifest 必须有真实 `last_mark`；
26. 账本评估日 = 数据最新可判定日；
27. manifest 的 `tracked_spec`、冻结参数、成本、funding source 和 gross cap 与当前 LS45-G125 规格完全一致；
28. journal 信号日 = 冻结账本最新信号日。

另有 1 项非硬告警记录最近交易事件距今天数；事件驱动账本长期没有新事件是正常的。若 journal 为空，会先报“台账存在”硬失败并跳过依赖 journal 的检查。

少一头空头止损、方向搞反、把净仓当成 gross、把 old L125 账本混入 LS45，或出现未成交普通单/重复对冲腿，都会让 `audit-live` 失败。

---

## 9. 日常监控

每周至少看一次：

| 指标 | 位置 | 动作 |
|---|---|---|
| 执行状态 | `reports/ls45_live_g125_live/latest.json` | `status` 必须是 `ok`；`partial` 查 failures |
| 对账 | `reports/ls45_live_g125_live/audit.json` | `hard_failures = 0` |
| 巡检 | `reports/ls45_live_g125_live/health.json` | `issues` 为空 |
| journal | `reports/ls45_live_g125_live/journal.csv` | 每日一行；同日重跑覆盖 |
| 数据覆盖 | `reports/ls45_live_g125/manifest.json` | `missing_hours = 0`，mark 新鲜 ≤ 30h |
| 空头止损 | `audit-live` 输出 | 所有空头必须有 `stop_loss` |
| funding | Bitget `position-history.totalFunding` + journal | 当前持仓每日只记 `本次累计 - 上次累计`；平仓日从 position history 取最终累计并扣除上次基线；同一天多次开平分开归属 |

---

## 10. 故障处置

### 07:05 UTC（15:05 北京）后仍未成功

```bash
launchctl print gui/$(id -u)/com.atlas20.derivatives-execute
tail -100 ~/Library/Logs/atlas20-derivatives-execute.log
make audit-live
```

若在窗口内，下一次重试会自动补；窗口外需要人工确认后：

```bash
ops/run_derivatives_daily.sh --force
```

### 全链路核对失败

先看 `audit.json.checks` 和 `monitor` 告警里的具体 check 与数值差异，不要只看退出码。常见原因：

- mark / panel 数据过期；
- journal 和交易所订单不一致；
- 空头没有附带止损；
- 目标账本与数据评估日错位；
- 外部资金流未记录；
- 权限或 API key 类型不支持 isolated。

### 出现强平、止损失效或 gross 超限

1. 立即 `touch data/ls45_g125_execution.KILL`；
2. 人工核对并平掉风险腿；
3. 修复原因；
4. 重跑 `make audit-live`；
5. 在 `RESEARCH.md` 记录事故与恢复；
6. 经负责人确认后再移除 kill switch。

---

## 11. 研究依据与已知限制

- LS45-G125 在同一 20 bps 口径下：终值 **68.95x**、Sharpe **1.982**、MDD **-39.96%**；
- L125 基线同口径：40.22x、1.733、-40.65%；
- LS45 在 100 bps、funding ×1.59、3x long-adverse 压力下仍略优于 LS57；
- 报告：`reports/ls45_live_candidate_compare/`；
- 当前选择是研究候选直接进入真实账户测试，不把 12 个月 OOS 或 PBO/DSR 作为额外实盘硬门槛；这不等于声称策略已被长期 OOS 证明；
- 仍需持续观察：空头实际成交与止损触发、funding、isolated 权限、资产上下架、滑点、数据缺口；
- 任何参数变更都必须新建 track/spec，不得静默改写本账本。
