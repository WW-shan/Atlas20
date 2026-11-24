# Atlas20 Bitget USDT-M 多空实盘 Runbook

> 当前启用的 aggressive track：**`PR2026-11-LS104-H5-LS23-PROFITLOCK-STRONGER21-S050-G175-M090`**
> （`LS104-G175-M090`）。LS45-G125 保留为独立可回滚 profile。
>
> - 标的：Bitget **USDT-M 永续**，允许有符号多空账本；
> - H5 多头 + 利润保护 + 空头路由 + 21D 强持有者再分配；
> - LS104：H5 long 1.25x、short request 0.50x、目标 **gross 硬上限 1.75x 权益**；
> - 交易所杠杆配置 **4x isolated**，多空每腿 initial buffer 均为 **50%**；
> - 组合 isolated-margin utilization 硬上限 **0.90**；
> - 空头开/加仓附带 **20% adverse move、mark-price、market stop**；
> - 信号账本、live-parity 回测和实盘统一使用 **T+1 01:05 UTC**
>   （北京 09:05，约为收盘后 +1h5m）；旧 03:00 UTC 报告只作为 legacy 对照；
> - 实盘主任务在 **01:05 UTC** 运行；
> - 成本口径 20 bps，funding 使用 Bitget exact；
> - 当前策略书：`docs/superpowers/specs/2026-11-15-ls104-g175-m090-live-design.md`；
> - 研究记录：`RESEARCH.md` §00.152；执行与数据链硬化见 §00.153–00.155；回测产物：`reports/ls104_g175_m090_20261115/`；
> - 实盘冻结账本：`reports/ls45_live_g175/`。
>
> 本文只描述执行与恢复，不允许在实盘中临时改参数。运行时代码和状态优先于本文摘要。

两个 profile 的隔离文件：

| Profile | Spec | Leverage | Gross cap | Margin cap | Targets / state / journal |
|---|---|---:|---:|---:|---|
| `ls45-g125` | `PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21` | 2x | 1.25x | 0.85 | `reports/ls45_live_g125/`, `data/ls45_g125_execution_state.json` |
| `ls104-g175-m090` | `PR2026-11-LS104-H5-LS23-PROFITLOCK-STRONGER21-S050-G175-M090` | 4x | 1.75x | 0.90 | `reports/ls45_live_g175/`, `data/ls45_g175_execution_state.json` |

持久选择写入仓库内、无凭据的 `config/track.env`：

```sh
ATLAS20_TRACK_PROFILE=ls104-g175-m090
```

wrapper 只在环境没有显式设置 `ATLAS20_TRACK_PROFILE` 时读取该文件；文件缺失或变量为空会直接
`exit 1`，不会再静默回退 LS45。LS45 只能通过显式设置
`ATLAS20_TRACK_PROFILE=ls45-g125` 启用。因此紧急回滚可以临时用
`ATLAS20_TRACK_PROFILE=ls45-g125 ops/run_derivatives_daily.sh ...` 覆盖，但已持有的 LS104
仓位必须先按 LS104 目标降低到 LS45 的风险范围，不能只切配置留下超风险仓位。

---

## 1. 当前自动化拓扑

### 1.1 四个每日节点

当前生产链固定为四个业务节点，各自只做一件事：

| 节点 | 北京时间 | 作用 | 日志 |
|---|---|---|---|
| 数据 | 08:30 | CMC/Binance/Gate 面板 + Bitget mark/market/funding + Top50 readiness | `~/Library/Logs/atlas20-daily-refresh.log` |
| 信号 | 08:35 | 构建冻结目标账本 + data/venue/signal 审计 | `~/Library/Logs/atlas20-derivatives-refresh.log` |
| 执行 | 09:05 | 按 T+1 01:05 UTC 的真实账户执行一次 | `~/Library/Logs/atlas20-derivatives-execute.log` |
| 巡检 | 19:00 | 只读全链路核对；异常才告警 | `~/Library/Logs/atlas20-live-monitor.log` |

不再存在 prepare/finalize 补跑、09:35/11:05/11:35/12:35/14:35 执行重试、top50 独立重试或
盘前自动自愈。任一节点失败即保持失败；19:00 巡检负责提示，是否人工修复由负责人决定。

主任务入口：

```text
08:30  ops/run_derivatives_data.sh
         -> scripts/refresh_daily_data.py
         -> make derivatives-live-data
         -> make top50-readiness-unlocked / top50-readiness-check

08:35  ops/run_derivatives_signal.sh
         -> make derivatives-ls104-signal
         -> audit-data-chain / audit-data-ls104
         -> audit_venue_symbols.py / audit-contract-specs-ls104
         -> audit-signal-ls104

09:05  ops/run_derivatives_daily.sh
         -> scripts/execute_live_plan.py --live --notify --require-isolated

19:00  ops/run_live_monitor.sh
         -> scripts/monitor_live_track.py --notify
```

### 1.2 执行时钟

- 回测、target ledger 和实盘统一使用 **T+1 01:05 UTC = 北京 09:05**；
- 回测成交价使用 Bitget 01:00 UTC 的 1H market open；
- 日线信号只依赖已完成的日线数据，不等待 01:00 的 mark bar；
- 执行器只有一次尝试，另有 15 分钟调度/进程宽限；超过即失败，不做自动晚跑；
- 01:00 的 fill bar 由执行器在 09:05 现场校验，而不是让信号构建等待它。

### 1.3 信号与数据边界

- 00:30 UTC 的数据节点以增量缓存刷新上一完整 UTC 日的 CMC 面板、Bitget
  mark/market/funding 与 Top50 readiness；整个节点在 00:50 UTC（08:50 北京）仍未完成时会
  被总时限终止并失败，不会拖到 09:05 才由执行器发现；
- 00:35 UTC 的信号节点先校验数据节点写出的 `data/derivatives_data_ready.json`
  完成凭证，确认面板、metadata、Bitget symbol map 与当前 READY Top50 指针完全一致后，
  才消费这些冻结输入生成 target ledger 和审计；08:35 起最多等待 15 分钟（即 08:50 北京），
  超时则信号节点直接失败，09:05 执行器不会拿半成品下单；由 19:00 巡检报告，不自动重跑；
- 最新事件的 T+1 01:00 market bar 可以尚未发布；该 bar 由 09:05 执行器负责获取和校验；
- 历史 target 的 01:00 bar 仍必须完整；缺历史 bar 会阻止信号发布；
- 不使用 23:00 mark bar 冒充 00:00 数据，也不在数据缺失时下单。

### 1.4 失败处理

数据、信号或执行任一节点失败时：

1. 不自动重试、不补跑、不执行 finalize；
2. 19:00 巡检读取真实账户、state、journal 和审计，报告异常；
3. 负责人确认后，才允许手工运行对应节点；
4. 手工补跑不是常规路径，也不能改变回测冻结的 01:05 时钟。

## 2. 信号与执行时点

事件账本每行包含权威字段 `execution_hint`。当前 LS104 账本固定为：

```text
signal_date D 00:00 UTC
execution_hint D+1 01:05 UTC
```

这个字段描述**该事件行**的统一执行口径（T+1 +1h5m），与 live-parity 回测和
实盘执行一致。每日自动执行不能直接拿事件行当窗口：如果账本连续多日没有新事件，
它会被误判为“数天前的任务已过期”。
执行器改为从 manifest 的最新已完成数据日计算：

```text
daily_execution_hint = manifest.signal_end_date + 1 day + 1 hour 5 minutes
                     = signal_end_date + T+1 01:05 UTC
```

live-parity 回测的 `engine_end` 必须覆盖这个执行点。由于引擎区间是右开区间，且
`01:05` 会 floor 到 `01:00` mark bar，runbook 使用：

```text
engine_end = signal_end_date + 1 day + 1 hour 5 minutes + 1 second
           = signal_end_date + T+1 01:05:01 UTC
```

若仍以 `signal_end_date + 1 day 00:00` 结束，目标账本虽然存在，最后一批 OPEN/CLOSE
却不会进入回测成交、持仓、量化和止损统计；`audit-signal-ls104` 会因此硬失败。

目标事件第一次应用时，计划器按当时真实权益 × 目标权重下单，并把每个腿的
`target_quantities` 冻结到 `active_event`。此后：

- 没有新目标行时，保留同方向持仓的价格漂移，不按旧权重每天重新贴回目标；
- 只关闭方向错误、计划外风险，并维护逐仓保证金和止损；
- 上次 OPEN/INCREASE 失败、事件仍为 `partial` 时，重试按冻结币数量补齐，不按今日权益重算；
- 某条腿已经被交易所策略止损平掉时，本事件剩余期间该 symbol 的目标强制为 0，
  不重新开仓；只有新的目标事件才解除；
- 止损校验、实际数量审计、账户对账和 journal 每天都按 `daily_execution_hint` 运行。

因此事件信号可以显示旧信号日，但定时任务不会因为“今天没有新交易事件”而失效。

实盘主任务在 01:05 UTC 开始，信号只使用 D 日收盘及之前的数据。全天只有一个执行时点：

```text
01:05 UTC = 09:05 北京  single execution attempt
```

正常执行允许 15 分钟的调度/进程宽限（最晚 01:20 UTC）；超过即失败，不自动晚跑。交易窗口
不再延伸到 07:05 UTC，也没有 01:35/03:05/03:35/04:35/06:35 的补跑。窗口外人工 `--force`
只能用于负责人明确确认的异常修复，不是自动流程。

---

## 3. 四节点幂等与失败处理

1. **数据节点** `ops/run_derivatives_data.sh`：刷新面板、Bitget mark/market/funding、Top50
   readiness，并在全部检查通过后原子写出 `data/derivatives_data_ready.json`。失败即停，不重试。
2. **信号节点** `ops/run_derivatives_signal.sh`：先验证数据节点完成凭证（最多等待 15 分钟），
   再构建冻结账本并运行 data/venue/signal 审计。失败即停，不重试。
3. **执行节点** `ops/run_derivatives_daily.sh`：只调用 `execute_live_plan.py --live`，不刷新
   数据、不构建信号、不 finalize、不重试。
4. **巡检节点** `ops/run_live_monitor.sh`：只读核对账户、目标、止损、journal、审计和新鲜度；
   异常才告警。

执行器自身保留的安全门禁：

- 持有 `data/derivatives_execution.lock` 的进程级 `flock`（LS45/LS104 共用）；另一个实例直接退出；
- mark 新鲜度硬阈值 30h；日线信号只要求上一完整日线收盘，不要求 00:00 hourly mark bar；
- 目标账本评估日必须等于数据最新可判定日；
- `manifest.targets_sha256` 必须与 `oos_targets.csv` 字节哈希一致，防止“新账本 + 旧 manifest”
  或进程中断留下的半写账本被当成完整目标；
- 实时 ticker 不得超过 120s、价格必须可用；
- account equity 不低于 20 USDT；
- kill switch 文件存在时拒绝一切操作；
- 每个 run day + `targets_sha256` 只允许一个 `ok`；`partial` 不会在当天自动补跑，留给
  19:00 巡检告警和负责人决定；
- `active_event` 保存事件日、最终应用时间、冻结方向/价格/币数量、应用状态和已止损腿；
  若硬 gross/margin cap 触发了风险缩减，额外保存 `risk_overlay.target_quantities` 作为**有效**
  数量锚点，原始事件目标仍保留在 `target_quantities`，不会静默改写 alpha 目标；
- `stop_reconciliation_through` 保存已经完整扫描过的止损历史高水位；`last_run_mode` 区分
  `execution` / `protect_only` / `reconcile_only`，防止把补账运行误读成 alpha 执行；
- 已止损腿在旧事件中永久保持目标 0，新目标事件才会重新授权同 symbol 开仓；
- 同一 run day 的 clientOid 稳定；请求超时或缺少 `orderId` 时按 clientOid 回查，避免重启
  把“已接受但响应丢失”的订单再下一遍；
- 同日手工重跑会按 `orderId/clientOid` 合并已有成交，不会用当前轮的空 `trades` 覆盖已落账成交；
- 若订单已在交易所成交、但进程在写 journal 前崩溃，下一次运行会从当日 `order-history`
  找回当前 prefix 的成交并补入 journal；
- journal/state/latest/audit/monitor/capital-flow 写入均为同目录临时文件 + `fsync` + `os.replace`；
- 成交、journal、latest.json、通知全部成功后才写 `ok`；
- journal 或 Telegram 写失败时不会把 run 标记为完成，下一次运行可以继续；
- 未捕获的顶层异常会写 `latest.json(status=error)` 并尝试发 Telegram 告警，不写 `ok`。

kill switch：

```bash
touch data/ls45_g175_execution.KILL   # LS104 当前 track：立即阻止新的执行
rm data/ls45_g175_execution.KILL      # LS104 当前 track：恢复

touch data/ls45_g125_execution.KILL   # LS45 rollback only
rm data/ls45_g125_execution.KILL      # LS45 rollback only
```

kill switch 路径必须与当前 profile 一致，不能误以为 LS45 的开关会阻断 LS104。

注意：kill switch 阻止完整执行链和 `--protect-only` 的风险维护，不会自动平仓；已有仓位仍由交易所
止损及人工操作管理。只有 `--reconcile-only` 可在 kill switch 存在时运行，因为它只补记已经发生的
交易所止损与 journal，不计划、不调用下单函数。

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
- 目标 gross 硬上限为账户权益 × 1.25；
- 没有新目标事件时仍保留同方向价格漂移，但如果**实际 gross 已超过硬上限**，执行器按现有
  各腿名义比例做风险降低，只发 reduce/close，不重新开仓、不加仓；这是风险 overlays，不是 alpha 再平衡；
- 若达到 cap 所需的最小减少量低于交易所最小下单额，则使用交易所允许的最小减仓量；只有连最小减仓
  也不可行时才平掉该腿，仍不得跳过 gross 硬上限。

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
- 下一次运行会重新读取真实账户，不会重复开仓；
- `audit-live` 会核对 journal 中带止损的空头成交与交易所订单历史的 `stopLoss / slTriggerBy / slOrderType`。
- `audit-live` 必须独立确认实际止损价格严格早于逐仓强平价；`liquidationPrice` 缺失、非法或
  `stop >= liquidationPrice` 都硬失败。执行器在最终保护判定中也使用同一约束，不会把晚于强平的
  stop 当作有效保护。

Bitget 的策略止损是**按入场订单/加仓订单保留**，不会自动合并：

- 空头 2 → 4 加仓后，交易所会同时保留旧 `qty=2` 和新 `qty=2` 两张止损策略单；
- 空头 4 → 2 部分减仓后，交易所不会自动把两张策略单缩成一张，仍可能保留总 `qty=4`；
- 因此每轮执行在最终验仓前会把当前空头归一为**一张策略单**：`qty = 当前空头数量`，
  `stopLoss = 最新加权入场价 × 1.20`（向上取整），`slTriggerBy=mark`，`slOrderType=market`；
- 归一使用 Bitget `modify-strategy-order` 调整保留单，再用 `cancel-strategy-order` 取消重复单；
- 若同一 symbol 出现无法识别的策略单，不猜测、不修改，直接按空头止损未证实处理并 emergency close；
- 归一后重新查询交易所；必须恰好一张、数量等于当前仓位、价格等于目标止损，否则本次 run 为 `partial`；
  `audit-live` 另有“每个空头只有一张降险策略单”的独立硬检查，不能用多张合计数量绕过。

止损保护按当前空头开仓周期维护。平仓后旧 journal 中的历史 stop 不会继续保护后续重开的空头；
当前空头若没有完整的当周期入场 stop 记录，会先被 `EMERGENCY_CLOSE`。

Bitget 的策略止损行和真正平仓单不是同一个 order id：策略行变成 `status=success` 后，实际
market close 会以另一张普通订单出现，`clientOid` 也由交易所生成。执行/对账逻辑因此必须：

- 按 symbol、`side/posSide`、请求数量、触发时间 ±10 秒唯一匹配，不做模糊猜测；
- 匹配成功才写 `reason=venue_strategy_stop` 的 CLOSE，保存策略 order id、执行 order id、均价和费用；
- 多候选、零候选或数量不一致一律 hard failure；
- `active_event.stopped_symbols` 记录该事件已经止损的腿；旧事件重试时目标数量置 0，禁止重开；
- 完整止损和部分止损都落 journal；部分止损的剩余仓位由下一次风险降低路径处理并保持 `partial`；
- 只有止损历史完整扫描成功才推进 `stop_reconciliation_through`，失败不得跳过高水位。

空头止损阈值与回测一致：`entry_price × 1.20` 先按 Bitget 合约价格步长向上取整，再由
mark price 触发。回测、计划器、成交后归一化与 `audit-live` 必须使用同一价格网格。

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
- 2 NEAR 多头：2x isolated 开仓、方向/保证金/杠杆回读、立即平仓，通过；这是 LS45 时代的
  venue capability drill，LS104 的 4x 回读由独立 executor 和 audit 固化；
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

> 2026-11-14 22:14 北京，负责人明确授权使用 `--force` 做了迟到补跑，已真实成交四腿空头并
> 通过 `audit-live`；本次历史空仓状态已被 `RESEARCH.md` §00.143 取代。自动任务仍必须先通过
> 窗口、数据和全部执行门禁，不能把这次人工授权当作常规迟到交易许可。

保证金路径：

1. Symbol 先设置当前 profile 的 venue leverage；LS104 为 4x isolated，现有持仓和待开腿都要
   在风险订单前做 set + readback；
2. 成交后交易所自动占用约 50% 名义；
3. 执行器按交易所实际仓位重算并调用 `set-margin(add/remove)`，把每腿保证金补到约 51.5%；
   杠杆切换可能改变 `positionBalance`，所以不能只使用下单前的静态 delta；
4. 交易所拒绝 `set-margin` 时同时记录 margin note 和失败；本次 run 必须是 `partial`，后续窗口重试
   会重新读取账户并再次尝试，不能写成 `ok` 后被当日幂等跳过。若持仓模式本身不是 isolated，则按上面的硬失败处理。

---

## 6. 关键文件与状态

| 路径 | 内容 |
|---|---|
| `reports/ls45_live_g175/oos_targets.csv` | LS104 冻结的有符号目标账本 |
| `reports/ls45_live_g175/manifest.json` | 数据覆盖、spec、funding、冻结参数、评估日、4x/0.90 pins |
| `reports/ls45_live_g175/data_audit.json` | 数据输入、funding cadence/publication 与合约规格门禁的完整检查 |
| `reports/ls45_live_g175/contract_spec_snapshots.json` | 冻结 track 在保留合约快照之间的规格差异 |
| `reports/ls45_live_g175/funding_publication_boundary_probe.json` | 真实结算边界上 `current-fund-rate` 与 history 的发布时间证据 |
| `reports/ls45_live_g175/funding_semantics_audit.json` | Bitget `totalFunding` 与真实 position cycle 的独立对账 |
| `data/raw/bitget_derivatives/merged_oos_20261112/funding_publication.json` | 每个合约的 publication request time、rate relation、interval 和文件哈希 |
| `data/raw/bitget_derivatives/merged_oos_20261112/contract_snapshots/index.json` | 合约规格变化点索引 |
| `reports/ls104_g175_m090_20261115/README.md` | LS104 live-parity 研究摘要 |
| `reports/ls45_live_g175_live/latest.json` | LS104 最近一次真实执行或对账的计划/报告与状态 |
| `reports/ls45_live_g175_live/journal.csv` | LS104 每日权益、仓位、成交、止损记录、notes |
| `reports/ls45_live_g175_live/audit.json` | LS104 只读对账输出 |
| `reports/ls45_live_g175_live/health.json` | LS104 巡检快照 |
| `reports/ls45_live_g175_live/prior_track_order_registry.json` | LS45 迁移前已成交生产订单的精确 orderId 清单；只豁免这些历史单，不代表 PnL/funding 继承 |
| `data/ls45_g175_execution_state.json` | LS104 幂等 key/status、`active_event`、风险 overlay、止损高水位 |
| `data/ls45_g175_telegram_state.json` | LS104 Telegram 播报幂等状态 |
| `data/ls45_g175_execution.KILL` | LS104 kill switch（存在即停止新执行） |
| `data/derivatives_execution.lock` | LS45/LS104 共用的进程级执行锁，防止两个 profile 同时下单 |
| `reports/derivatives_track_live/capital_flows.csv` | 账户级外部资金流；入金/出金不能计为策略 PnL |

LS45-G125 的全部同名文件保留为独立回滚 profile，LS104 不覆盖它们。

`data/` 是本地运行状态，不随 git 部署。**同一账户**迁移机器时必须同步 credentials、
当前 profile 的 execution state、telegram state、journal 和
所需 raw/processed 数据，否则会重复执行或重复播报。换 Bitget 账户时必须归档旧 state/journal
并建立新 baseline，不能让旧账户的 `account_fingerprint` 混入新账户。

---

## 7. 常用命令

### 7.1 只读检查

```bash
make audit-live-ls104
make audit-data-chain             # CMC 缓存 → canonical panel → PIT universe 全链审计
make audit-symbols AUDIT_REQUIRED_LEVERAGE=4.0 AUDIT_SYMBOL_OUT=reports/ls45_live_g175_live/venue_symbol_audit.json  # 全部标的：4x、多空、翻转、止损和报价
make derivatives-notify-ls104 ARGS=--dry-run  # LS104 Telegram 文本 dry-run
make execution-plan-live-ls104          # 当前 LS104：读真实账户，只发计划，不下单
make execute-plan-ls104                 # 当前 LS104：读真实账户，执行器 dry-run，不下单
make protect-live-ls104                 # 当前 LS104：只减仓/止损/保证金维护；禁止开仓、加仓
make reconcile-live-ls104               # 当前 LS104：只补记 journal；不计划、不下单
ops/run_live_monitor.sh                 # 只在异常时发 Telegram
```

LS104 维护命令必须使用上面两个带 profile 路径、spec 和风险参数的 Makefile target。裸跑
`scripts/execute_live_plan.py` 会使用脚本内保留的 LS45 回滚默认值，不是当前 live track。

### 7.2 手动执行

```bash
ops/run_derivatives_data.sh      # 数据节点；失败即停
ops/run_derivatives_signal.sh    # 信号节点；失败即停
ops/run_derivatives_daily.sh     # 唯一执行节点；不做数据/信号重建
```

自动流程不提供 `--force` 补跑，也不在 09:05 之后自动重试。负责人确认需要人工修复时，才按
顺序重跑对应节点；执行节点的窗口仍只允许 01:05–01:20 UTC，超过则需显式人工覆盖并重新核对
真实账户。`--force` 不是“强制重复交易”，不会绕过数据审计、manifest、isolated、风险、
对账或幂等门禁。

进程在状态落盘前崩溃时，下一次手工运行复用确定性 `clientOid`，以便从订单历史恢复已成交订单；
若前一次失败已经写入 state，则下一次 attempt 使用新的确定性前缀，避免交易所把新补单误判为旧
幂等键。同日手工重跑按前一次同日 journal 的 `run_at_utc` 只追加新的外部资金流；旧资金流/
数据新鲜度提示会被本轮提示替换，不会重复记账。来自公网的瞬时连接、TLS 或 429/5xx 会做有限
次指数退避；响应成功但内容无效仍然 fail closed。

权益跌到 20 USDT 以下或非正数时，执行器不再整体拒绝运行：它会抑制所有新开/加仓和保证金追加，
但仍允许 reduce/close、止损核对、记账和告警。这样不会因为“余额太小”把现有风险锁在仓位里。
任何已存在的异常策略单（例如无持仓的 TP/SL、long 上的策略单、short 上非 mark/market stop）
都会在真实下单前阻断新风险；策略单接口不可用时，开仓同样 fail closed，减仓/平仓仍继续。
同一轮中任何下单失败、未终态或成交数量/价格回读异常，都会阻断后续所有 OPEN/INCREASE；已经
发出的 reduce/close 仍可继续执行，下一窗口按真实账户重新规划。若空头止损无法确认而触发紧急平仓，
执行器会先撤销该 symbol 的活动策略单，再市价买回整条空头腿，避免留下孤立止损单。
保护性维护路径同样允许持有腿使用交易所 `markPrice` 作为平仓/减仓定价兜底；公开 ticker 缺失
或过期不会阻断风险降低，但新开/加仓仍必须使用新鲜报价。

### 7.3 资金流

任何入金/出金后：

```bash
make record-capital-flow AMOUNT=400 NOTE='入金'
make audit-live-ls104
```

资金流从当日 PnL 中剔除；不要把它算成收益或亏损。

---

## 8. `audit-live` 的硬校验

`scripts/audit_live_track.py` 只读。2026-11-15 真实账户输出为 **40 项硬检查 + 1 项非硬告警**；
下面按检查族归纳：

实盘执行器还会把 catch-up 窗口、报价最大年龄、权益下限、最小调仓额和 mark 最大陈旧度钉在 profile
默认值上；`--live` 下禁止 `--prices-file` / `--instruments-file` 离线覆盖。`--protect-only` 还必须
验证 `active_event.targets_sha256` 与当前 manifest 完全一致。

1. 冻结目标都有唯一 Bitget 合约映射；
2. venue drill 精确 `orderId` 登记表可读；只豁免登记过的 drill 订单；
3. 账户 API 必需字段完整且有限；
4. 账户权益不低于执行下限 20 USDT；
5. 持仓 API 必需字段完整、方向合法，且 `markPrice` / `avgPrice` 有限；
6. 同一合约没有重复或反向对冲腿；
7. 当前没有未成交普通订单；
8. `equity = USDT-equivalent collateral + isolated margin + unrealisedPnl`；multi-assets 账户的非 USDT
   抵押品按交易所 `usdValue` 计入；
9. 交易所 `positionValue` = `Σ abs(qty) × markPrice`；
10. 所有持仓合约都能在冻结 symbol map 中唯一映射；
11. 每腿 `marginMode=isolated`、杠杆为 profile 的 4x（LS104）/ 2x（LS45）、保证金缓冲不低于 45%；
12. API key/账户分类未命中 copy-trading/elite 逐仓限制；
13. 执行状态带账户指纹，且与当前 Bitget 账户一致；`last_key` 和每个 `runs[*].key` 的 track spec
    都必须等于当前 profile，`runs` 必须是完整数组；旧/未绑定/跨 track state 全部失败；
14. journal 最新权益按实时 mark 和外部资金流折算后等于账户；专用对账容差为
    `max(0.10 USDT, 权益的 2bps)`，只吸收两次交易所请求之间的 mark 快照差，不改变策略风险门禁；
15. journal PnL 链在剔除 capital flow 后连续；
16. journal `funding_total` 等于持仓未变化区间的累计资金费差；
17. journal 每笔成交都能在交易所订单历史对上数量、均价、手续费；
18. 交易所当前 prefix 的已成交 Atlas20 订单全部已记账（反向核对）；
    唯一例外是 drill registry 和 LS104 迁移 registry 中逐笔登记的精确历史 orderId；未登记订单仍然硬失败；
19. 每个当前空头都必须能由交易所 `avgPrice × 1.20` 和实时合约价格步长**独立重算**预期止损；缺 `avgPrice`、缺合约规格或无法重算都硬失败，不允许回退到 journal 旧值；
20. 每个实际空头止损必须严格早于 Bitget 逐仓 `liquidationPrice`；缺强平价、非法强平价或 `stop >= liquidationPrice` 都硬失败；
21. 空头 journal 入场必须记录已确认止损；
22. 当前每个空头仓都有交易所**当前可见**的 mark-price market 策略止损单；
23. 每个空头只能有一张活动降险策略单；多张合计数量即使覆盖仓位也不能绕过检查；
24. 策略单必须与当前空头止损/数量对应，不能有孤立策略单；
25. 有符号目标 vs 有符号实际仓位：多头正、空头负；先按 1 USDT、目标名义 1% 和 1.5 个合约步长三者取大判定。若略超容差但方向一致，且交易所**最小可成交订单**会让偏差变大（通常由最小下单额导致），允许该不可修复残差；只要存在一张可改善偏差的最小订单，仍然硬失败；
26. 无计划外持仓；
27. 冻结目标 gross 不超过 profile cap：LS104 为 1.75x，LS45 为 1.25x；
28. 实际 gross = `Σ abs(notional)` ≤ profile cap × equity；LS104 的组合 isolated margin 同时 ≤0.90×equity；
29. mark 数据 ≤ 30h，且 manifest 必须有真实 `last_mark`；
30. 账本评估日 = 数据最新可判定日；
31. manifest 的 `tracked_spec`、`frozen_config`、成本、funding source、venue leverage、margin cap 和 gross cap 与当前 profile 完全一致；
32. `oos_targets.csv` 的 SHA-256 与 manifest `targets_sha256` 完全一致；manifest 缺少
    `targets_sha256` 也是硬失败；
33. `audit-data` 必须 0 hard failure / 0 warning；输入指纹覆盖 panel、symbol map、contracts、coverage、funding manifest、全部 mark CSV 和全部 funding CSV；
34. manifest 的 `data_fingerprint` 必须等于当前输入指纹；
35. journal 信号日 = 冻结账本最新信号日。

另有 1 项非硬告警记录最近交易事件距今天数；事件驱动账本长期没有新事件是正常的。若 journal 为空，会先报“台账存在”硬失败并跳过依赖 journal 的检查。

少一头空头止损、方向搞反、把净仓当成 gross、把 old L125 账本混入 LS45，或出现未成交普通单/重复对冲腿，都会让 `audit-live` 失败。

---

## 9. 日常监控

每周至少看一次：

| 指标 | 位置 | 动作 |
|---|---|---|
| 执行状态 | `reports/ls45_live_g175_live/latest.json` | `status` 必须是 `ok`；`partial` 查 failures |
| 对账 | `reports/ls45_live_g175_live/audit.json` | `hard_failures = 0` |
| 巡检 | `reports/ls45_live_g175_live/health.json` | `issues` 为空 |
| journal | `reports/ls45_live_g175_live/journal.csv` | 每日一行；同日重跑覆盖 |
| 数据完成凭证 | `data/derivatives_data_ready.json` | `ready=true`，`completed_date_utc` 为当天，且 `ready_sha256`/`input_files` 与当前 Top50 指针及输入一致 |
| Top50 readiness | `reports/top50_data_readiness/latest.json` | `ready=true` 且 50 个成员全 READY；否则查 `failure_details`，不能手工改 status |
| Top50 ready pointer | `reports/top50_data_readiness/latest_ready.json` | 只应指向最近一个 50/50 READY 的 as-of；日期落后即阻断新 executable-universe 风险 |
| Top50 notifications | `data/top50_readiness_state.json` | `pending` 应为空；非空表示 Telegram 需重试，优先手工运行 `make top50-readiness ARGS=--notify` |
| 数据覆盖 | `reports/ls45_live_g175/manifest.json` | 当前 OOS `mark_coverage.missing_hours = 0`，mark 新鲜 ≤ 30h；历史 warmup 缺口已由 `repair_bitget_mark_gaps.py` 修到 0（87 个合约，25,555 → 0），不能和 live OOS 覆盖混为一谈 |
| 空头止损 | `audit-live` 输出 | 所有空头必须有 `stop_loss` |
| funding | Bitget `position-history.totalFunding` + journal | 当前持仓每日只记 `本次累计 - 上次累计`；平仓日从 position history 取最终累计并扣除上次基线；同一天多次开平分开归属；同日 retry 不得把已有 funding 覆盖成 0 |

---

## 10. 故障处置

### 09:20 UTC（北京 09:20）后仍未成功

```bash
launchctl print gui/$(id -u)/com.atlas20.derivatives-execute
tail -100 ~/Library/Logs/atlas20-derivatives-execute.log
make audit-live-ls104
```

自动流程不会在 09:05 之后重试。负责人确认需要修复时，先检查 08:30 数据、08:35 信号和
09:05 执行三个节点，再按需手工重跑对应节点；执行节点的正常窗口仍只有 01:05–01:20 UTC。

### 全链路核对失败

先运行 `--protect-only`（或只补账时 `--reconcile-only`），再跑 `make audit-live-ls104` 并查看
`audit.json.checks` / `health.json.issues`；
不要只看退出码。常见原因：

- mark / panel 数据过期；
- journal 和交易所订单不一致；
- 空头没有附带止损；
- 目标账本与数据评估日错位；
- 外部资金流未记录；
- 权限或 API key 类型不支持 isolated。

### Top50 readiness 为 BLOCKED

1. 打开 `reports/top50_data_readiness/latest.json`，按成员查看 `failure_details`；
2. `VENUE_UNAVAILABLE` 只会出现在 skipped 列表，不占 Top50 名额；
3. 有合约成员的 mark/market/funding/venue 缺口必须修复，不能把第 51 名自动补进来；
4. 只为失败层重跑原工具：`make top50-readiness`（warmup 失败才重建 warmup；live mark/market/funding
   或成员级 full-audit funding failure 才重建 OOS）；
5. 若仍阻塞，保留 `latest_ready.json` 的旧日期并禁止消费为今日 ready；
6. Telegram pending 不因重跑丢失；负责人确认后运行 `make top50-readiness ARGS=--notify`；
   同日先 BLOCKED 后 READY 时，未发送的相反状态会收敛为最终状态，避免重复噪音；
7. 任何 universe 规则变化必须另立 track/spec，不能借 readiness 修复静默改 LS104。

### 出现强平、止损失效或 gross 超限

1. 立即 `touch data/ls45_g175_execution.KILL`（LS104；LS45 回滚时用 `data/ls45_g125_execution.KILL`）；
2. 人工核对并平掉风险腿；
3. 修复原因；
4. 重跑 `make audit-live-ls104`；
5. 在 `RESEARCH.md` 记录事故与恢复；
6. 经负责人确认后再移除 kill switch。

---

## 11. 研究依据与已知限制

- LS104 在同一 01:05 live-parity 口径下：20bps 终值 **77.8524x / Sharpe 1.9637 / MDD -40.77%**，
  50bps **41.4492x / 1.7174 / -46.55%**；
- LS45-G125 对照：20bps 65.2592x / 1.9792 / -34.06%，50bps 39.3339x / 1.7694 / -39.75%；
- 100bps 诊断 19.09x / 1.406 / -52.77%，不作为晋级门槛；
- 报告：`reports/ls104_g175_m090_20261115/`；
- 当前选择是研究候选直接进入真实账户测试，不把 12 个月 OOS 或 PBO/DSR 作为额外实盘硬门槛；这不等于声称策略已被长期 OOS 证明；
- 仍需持续观察：空头实际成交与止损触发、funding、isolated 权限、资产上下架、滑点、数据缺口；
- 最后一轮 06:35 UTC 执行后若交易所止损才触发，Bitget 会立即执行止损并关闭风险；journal 补记由
  19:00 巡检告警、人工 `--protect-only`/`--reconcile-only` 或下一交易日执行器完成。该窗口是
  自动维护频率限制，不是仓位失保。
- 交易所 UI、风控或人工操作产生的外部成交通常不带 Atlas20 clientOid；`--reconcile-only`/
  `--protect-only` 会把未匹配成交导入为 `EXTERNAL_OPEN`/`EXTERNAL_CLOSE`，audit 对全部 tracked
  symbol 的已成交订单做反向核对。monitor 用 `active_event` 的冻结数量检查漂移，不用旧权重乘
  今日权益；外部成交必须补账后才能重新声明 `ok`。
- 任何参数变更都必须新建 track/spec，不得静默改写本账本。

---

## 12. 2026-11-17 实跑复核记录

本次生产复核不是只跑单元测试：

- `make audit-live-ls104` 42/42 通过；
- `audit-data-ls104` 3466 checks、0 hard failure、0 warning；
- `audit-data-chain` 52 PASS / 0 WARN / 0 FAIL；
- `audit-accounting-ls104` 44 PASS / 0 FAIL；
- `audit-signal-ls104` 72 行冻结账本 = 72 行重建账本，0 differences；
- `audit-symbols-ls104` 88/88 online，4x / long / short / flip 全部支持；
- `audit-contract-specs-ls104` 5 份快照通过；`SANDUSDT.maxLever 10 -> 20`
  是 non-material observation（所有值均支持 4x）；
- `audit-funding-semantics-ls104` 4 个真实 position cycle 通过；
- `com.atlas20.derivatives-refresh` 与 `com.atlas20.derivatives-execute` 两个
  LaunchAgent 均以 exit 0 收尾。

### 12.1 2026-11-17 可执行 Top50 真实构建与审计

- CMC as-of：**2026-11-15**；排名候选 **52** 个，最终可执行 **50/50 READY**；
- 无合约递补：`htx-dao`（原始 32）与 `mantle`（原始 35）跳过；`optimism`（原始 51）、
  `gala`（原始 52）进入最终 49/50；
- Top20 handoff：**20/20 READY**；
- 最终增量 refresh 覆盖 88 个已映射合约、177 requests；50 个选中合约的 mark/market 均覆盖
  **2026-09-01 00:00Z → 2026-11-16 21:00Z**，各 1846 rows，全量审计 0 duplicate / 0 interior gap；
- 原 `repair_bitget_mark_gaps.py`：50 个合约 `0 missing → 0`；
- scoped `audit_derivatives_data`：0 hard failure / 0 warning；
- 修复 warmup market 后的 readiness 数据指纹：
  `sha256:f36d22f966f97a9be8e112e4c4e87e4b0568c9442ca8712eba4354f05f816ecd`；
  同输入重复运行 fingerprint 不变；manifest 的 `executable_universe.fingerprint` 必须与它一致；
- 指纹逐成员提交 5 类原始文件、合计 250 个 SHA-256；ready payload 强制 50 个唯一
  coin_id/合约、连续 final rank 和 Top20=Top50 前 20，CSV 使用原子写；
- 指纹同时提交完整 CMC `panel_daily.csv`、`metadata.csv`、`symbol_map.csv` 的文件哈希；
- 自动回填命令非零退出或抛异常时，先持久化受影响成员的 `BLOCKED` 报告/state 并排队
  Telegram，再向上返回失败；不允许静默跳过新成员或掩盖为第 51 名；
- CMC 历史 32 个 provider-zero cap 行由现有 `audit_market_cap_gaps.py` 明示为
  `provider_zero_supply`，其中 4 个当前 Top50 成员只作为 warning，不使用 carry/stale cap；
- 旧 warmup market 缓存的分页边界共漏 **15,565** 个小时，其中 **712** 个是 01:00Z 执行 bar；
  downloader 已改为对 `partial` 缓存自动重取，历史缺口只通过 Bitget API 原子补齐；
- 修复后 50/50 warmup market 的内部小时缺口为 **0**，共 **1,584,383** 行；新旧文件重叠
  **952,801** 行 0 mismatch；每合约抽 3 个 200h 窗口回源共 **30,000** 根 K 线、
  **180,000** 个数值字段，0 mismatch；readiness 新增内部小时连续性硬门禁；
- 3 个合约的 warmup market 首笔成交晚于首条 mark（INJ/LDO/OP），保留合同起点 warning；
  首条之后的小时连续性已全部通过；
- 无合约与 rebrand 导致的重复合约会分别记录 `VENUE_UNAVAILABLE` / `DUPLICATE_CONTRACT`
  并顺延；新合约没有已完成 live bar、回填失败或 Top20/Top50 状态不同步都会 fail closed；
- `oos_targets.csv` 哈希不变：`2ef4e701...`；execution state 与 journal 哈希不变；
  manifest 因 `market_fill_fingerprint` 从旧值更新为
  `sha256:f67d80499e580991a2520508bf1ec16e1a49e008fbf23a8c5586447e0971212c`；
- `audit-signal-ls104`：72 行冻结账本 / 72 行重建账本，重叠信号日 32，0 differences；
- `audit-data-ls104`：PASS，0 hard failure，0 warning；data fingerprint
  `sha256:416de82815c8116e01d7c0a9f0f21790544b47ab22086e50d5f6e2f0f21678a4`；
- 最终日频尾部检查发现 13 个 4h funding 成员缺 20:00Z settlement；修复成员级 audit
  funding 回填分层后，13 个成员以 599 requests 补齐，mark repair `0 missing -> 0`，
  最终 50/50 READY；
- `audit_market_cap_gaps.py`：PASS，32 行 all `provider_zero_supply`，0 unexplained。
- `reports/ls45_live_g175_live/prepared.json` 是旧 prepare/finalize 链的历史证据，不再由
  当前四节点数据/信号节点生成；当前执行门禁是数据完成凭证、manifest 指纹和 09:05 现场
  数据审计，不能把旧的 `prepared.json` 当作今天的成功标志；
- `audit-accounting-ls104`：44 PASS / 0 FAIL；55 日权益与 1322 小时 gross 独立重放一致；
- 最终代码门禁：Python 2705 passed / 1 skipped，前端 249 passed；lint、typecheck、build
  和新模块 strict mypy 均通过。

最终真实账户审计 `audit-live-ls104` 已通过 42/42：权益 490.9142 USDT、4 条当前持仓腿、
逐仓/4x/保证金缓冲、账户恒等式、订单历史与 journal、空头 20% stop 及其唯一性、
目标 gross 0.5000x、实际 gross 0.552x、isolated margin 0.279x 全部核对一致。
`audit-funding-semantics-ls104` 的 4 个 position cycle 也通过，最大绝对 funding
误差 3.89997e-05。

部署闭环已验证：运行时代码已推送 `origin/main`；旧的
`com.atlas20.top50-readiness` 09:45 兜底 job 已卸载并删除，不再进入生产拓扑。
数据节点仍在 08:30 完成 Top50 拉取与 Top20 数据池构建；信号节点通过
`data/derivatives_data_ready.json` 等待并校验这次完成，而不是另起一个重复 job。
`com.atlas20.derivatives-execute` 保持单次 09:05 触发。

2026-11-19 的 09:15 执行报告复盘：调度仍是 09:05，09:15 只是回退链完成时间。旧缓存规则
把 8h funding 的 freshness 宽限到 `interval + 1h`，导致 00:35/00:55 两次 prepare 在 00:00
settlement 已到期时仍跳过 funding 请求，信号在 08:43/08:57 北京因缺 BCH 00:00 settlement
失败，09:05 的完整回退链在 09:15 才完成。规则已改为 settlement 一到即请求 history 与
current-fund-rate；另加 publication evidence 完整性检查，CSV 虽新但 interval/current-rate/
发布时间证明不完整时也会主动重查。修复后用真实 Bitget 接口在隔离目录补齐 BCH/HYPE/
NEAR/ZEC，四条均为 history/current rate match；Top50 全 50 成员 6 小时 mark/market
共 600 根 K 线回源 0 mismatch，11 个成员各 5 个 funding settlement 重叠区 0 mismatch。

操作注意：结算后到下一次数据节点前，funding CSV 可能尚未包含新 settlement。
当前定时拓扑只有一个数据节点（08:30 北京）；若它失败，19:00 巡检会报告 settlement coverage
或 funding freshness 问题。负责人确认后先手工运行 `ops/run_derivatives_data.sh`，再运行
`ops/run_derivatives_signal.sh`，最后才运行 `ops/run_derivatives_daily.sh`。
若 `latest.json` 为 `status=error`，不要手工改写；按本文故障处置重新运行并让
下一次真实成功覆盖。
