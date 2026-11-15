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
> - 研究记录：`RESEARCH.md` §00.152；回测产物：`reports/ls104_g175_m090_20261115/`；
> - 实盘冻结账本：`reports/ls45_live_g175/`。
>
> 本文只描述执行与恢复，不允许在实盘中临时改参数。运行时代码和状态优先于本文摘要。

两个 profile 的隔离文件：

| Profile | Spec | Leverage | Gross cap | Margin cap | Targets / state / journal |
|---|---|---:|---:|---:|---|
| `ls45-g125` | `PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21` | 2x | 1.25x | 0.85 | `reports/ls45_live_g125/`, `data/ls45_g125_execution_state.json` |
| `ls104-g175-m090` | `PR2026-11-LS104-H5-LS23-PROFITLOCK-STRONGER21-S050-G175-M090` | 4x | 1.75x | 0.90 | `reports/ls45_live_g175/`, `data/ls45_g175_execution_state.json` |

持久选择写入仓库外文件 `~/.config/atlas20/track.env`：

```sh
ATLAS20_TRACK_PROFILE=ls104-g175-m090
```

wrapper 只在交互环境没有显式设置 `ATLAS20_TRACK_PROFILE` 时读取该文件；因此紧急回滚可以临时用
`ATLAS20_TRACK_PROFILE=ls45-g125 ops/run_derivatives_daily.sh ...` 覆盖，但已持有的 LS104
仓位必须先按 LS104 目标降低到 LS45 的风险范围，不能只切配置留下超风险仓位。

---

## 1. 当前自动化拓扑

### 1.1 macOS（本机默认）

| launchd 任务 | 北京时间 | 作用 | 日志 |
|---|---|---|---|
| `com.atlas20.daily-refresh` | 08:30、08:50、10:30、10:55、14:30 | 刷新 CMC/Binance/Gate 面板；已有完整数据时跳过 | `~/Library/Logs/atlas20-daily-refresh.log` |
| `com.atlas20.cmc-probe` | 08:05–11:50 每 15 分钟 | 记录 CMC 发布完成时刻，研究用 | `~/Library/Logs/atlas20-cmc-probe.log` |
| `com.atlas20.derivatives-execute` | **09:05**；重试 09:35、11:05、11:35、12:35、14:35 | 刷新 Bitget mark → 生成当前 profile 账本 → 数据/信号/venue 审计 → 按真实权益执行 → 写 journal → 执行后立即只读 monitor；当日已完成时先跑 risk-reducing protect-only（禁止开仓/加仓）再 monitor → Telegram | `~/Library/Logs/atlas20-derivatives-execute.log` |
| `com.atlas20.live-monitor` | 19:00 | 只读全链路巡检；异常才发消息 | `~/Library/Logs/atlas20-live-monitor.log` |
| `com.atlas20.protect-live-logs` | 登录时 + 每 5 分钟 | 保护运营日志不被清理工具删除 | `~/Library/Logs/atlas20-log-protect.log` |
| `com.atlas20.keep-awake` | 登录时常驻 | `caffeinate -dimsu` 防止机器/磁盘空闲睡眠；KeepAlive 自动拉起 | `~/Library/Logs/atlas20-keep-awake.log` |

主任务入口固定为：

```text
com.atlas20.derivatives-execute
  -> ops/run_derivatives_daily.sh
  -> make derivatives-live-data <profile-signal-target>
     -> audit-data-chain
     -> audit_venue_symbols.py
     -> audit-data-ls104 / audit-signal-ls104
     -> scripts/execute_live_plan.py --live --notify --require-isolated
     -> scripts/monitor_live_track.py --notify
```

LS104 首次运行且 `data/ls45_g175_execution_state.json` 不存在时，wrapper 额外传入
`--bootstrap-track`。该旗标只允许 state、journal 均为空且 manifest 有 `targets_sha256`；它把当前
冻结账本作为新 track 的首个事件应用，不重放 LS45 历史 PnL/funding，也不复用 LS45 state/journal。
继承仓位的累计 `totalFunding` 只写入首行 positions 作为下一日差分基线；该行 `funding_total` 固定为
0，不会把迁移前 funding 计入 LS104 收益。
一旦 state 文件存在，后续重试只走 `active_event` 的 complete/maintain 路径。

若窗口闸返回 `DONE=4`，wrapper 不刷新数据、不重读新的 alpha 目标，而是先运行：

```text
scripts/execute_live_plan.py --live --notify --require-isolated --protect-only
scripts/monitor_live_track.py --notify
```

`protect-only` 只允许 reduce/close、止损恢复/归一、风险 cap 缩减和逐仓保证金维护；OPEN/INCREASE
在计划器与执行器两层都被禁止。因此执行后若止损被修改、消失，或 gross 越过硬上限，下一次 fallback
会立即修复，而不是只等 Telegram 告警。它不按旧目标权重重新贴仓。

需要“只补 journal、连 reduce/close 也不做”时，可单独人工运行 `--reconcile-only`；该模式不进入交易
计划器，也不调用任何下单函数。

`derivatives-live-data` 使用稳定目录：

```text
data/raw/bitget_derivatives/merged_oos_20261112/
```

下载器每天用滚动窗口追加/修复 mark，不再回退到旧的 `merged_oos_20261009` 实盘源。

01:05 UTC 刚触发时，Bitget 的 1H `history-candles` 可能还没发布刚在 01:00 UTC 收完的上一根
bar。下载器会在严格审计前做一次有上限的条件等待：

- 只对落后不超过 3 小时的 mark 做尾部重取；
- 默认最多等待 180 秒、每 30 秒检查一次；
- 只重取要求 bar 前后两小时，不使用宽松的“最后一根够新就放行”；
- 超过等待预算、文件损坏或缺口过深时仍然 fail closed；
- 后续 01:35、03:05、03:35、04:35、06:35 UTC 的定时重试继续保留。

2026-11-14 的失败是交易所发布延迟，而不是信号或下单逻辑错误。修复不会放宽 mark 完整性，
也不会在数据缺失时下单。

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
却不会进入回测成交、持仓、量化和止损统计；`audit-signal` 会因此硬失败。

目标事件第一次应用时，计划器按当时真实权益 × 目标权重下单，并把每个腿的
`target_quantities` 冻结到 `active_event`。此后：

- 没有新目标行时，保留同方向持仓的价格漂移，不按旧权重每天重新贴回目标；
- 只关闭方向错误、计划外风险，并维护逐仓保证金和止损；
- 上次 OPEN/INCREASE 失败、事件仍为 `partial` 时，重试按冻结币数量补齐，不按今日权益重算；
- 某条腿已经被交易所策略止损平掉时，本事件剩余期间该 symbol 的目标强制为 0，
  不重新开仓；只有新的目标事件才解除；
- 止损校验、实际数量审计、账户对账和 journal 每天都按 `daily_execution_hint` 运行。

因此事件信号可以显示旧信号日，但定时任务不会因为“今天没有新交易事件”而失效。

实盘主任务在 01:05 UTC 开始，信号仍只使用 D 日收盘及之前的数据。重试点在：

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
   - 只有 `signal_end_date` 与 `index_end_date` 都已覆盖最新完成 UTC 日、manifest 的
     `targets_sha256` 与磁盘上的目标 CSV 完全一致，并且当日状态已 `ok` 的目标身份与它相同时才退出；
   - 旧 manifest 落后一天或目标 CSV 是半写/混合快照时，**不得**先用旧账本的“成功空操作”
     跳过重试；窗口内必须继续刷新数据、重建账本，再由执行器按新目标哈希判断是否真的重复；
   - 超过 6 小时补跑窗口退出；
   - 退出码 3 表示“设计上不交易”，不是故障；
   - 退出码 4 表示“今天已经成功完成且 manifest/目标哈希仍匹配”；wrapper 仍会先运行
     `--protect-only`，恢复/归一切异常止损、执行必要的 risk-reducing 维护并补 journal，再运行
     只读 monitor，避免执行后风险漂移拖到下一日。
2. **面板自愈**：`--check panel`
   - 面板落后或最后一天不完整时，运行 `refresh_daily_data.py --force --wait-seconds 900`；
   - 刷新后再次检查，仍不完整就拒绝下单。
3. **数据与账本**：`make derivatives-live-data derivatives-ls104-signal`（当前 profile）
4. **数据审计**：`make audit-data-ls104` 后接 `make audit-data-chain`；任何未来时间、重复、非法 OHLC、最后完成日缺失、
   **任一 normal 合约 funding 过期**、合约规格缺失或 manifest fingerprint 不一致都会拒绝执行。
   `audit-data` 还校验 mark/funding 单调性、近期 funding 结算缺口、funding manifest 与实际最后时间一致，
   把每个 funding CSV 的字节哈希纳入 data fingerprint，并校验最新 panel 的 price/volume/market-cap 有效值；
   `audit-data-chain` 额外从 CMC/独立源缓存重建 panel，检查 point-in-time 排名、feed 连续性、跨源确认和缺失收益策略。
5. **全品种实时能力**：`make audit-symbols` 对全部映射资产逐项核对 Bitget v3 合约身份、
   online/perpetual/USDT、报价新鲜度，并按 `--required-leverage 4.0` 验证 all-universe 杠杆能力，
   生成多单、空单止损和 long→short 翻转计划；
   `audit-data-ls104 --required-leverage 4.0` 进一步要求目标账本内每个资产支持 4x。
6. **信号等价性**：`make audit-signal-ls104` 重新构建冻结账本并逐行比较；同时要求最新信号动作
   在 replay 中留下对应成交、持仓或显式的交易所最小额跳过记录，且成交时间必须落在执行时刻
   前 1 小时到执行时刻之间。任何差异都会拒绝执行。
7. **执行**：`scripts/execute_live_plan.py --live --notify --require-isolated`
8. **执行后即时审计**：无论执行成功、partial 还是失败，都立即运行
   `scripts/monitor_live_track.py --notify`；它重新执行独立的 `audit-live`，并可发送实际账户状态告警。
   wrapper 保留 executor 的失败退出码，不会因为 monitor 成功而把 partial 洗成 ok。
9. **当日已完成的重试**：preflight 返回 4 时先运行 `--protect-only`，再运行 monitor。
   这一步会补记交易所止损、更新 `active_event.stopped_symbols`/风险 overlay/高水位，并恢复或
   归一止损、执行 gross/margin 的风险降低；它没有任何 OPEN/INCREASE 路径。

执行器自身还有：

- 持有 `data/ls45_g125_execution.lock` 的进程级 `flock`；另一个实例直接退出；
- mark 新鲜度硬阈值 30h；
- 目标账本评估日必须等于数据最新可判定日；
- `manifest.targets_sha256` 必须与 `oos_targets.csv` 字节哈希一致，防止“新账本 + 旧 manifest”
  或进程中断留下的半写账本被当成完整目标；
- 实时 ticker 不得超过 120s、价格必须可用；
- account equity 不低于 20 USDT；
- kill switch 文件存在时拒绝一切操作；
- 每个 run day + `targets_sha256` 只允许一个 `ok`；同一天账本重建后会重新进入补跑链，
  `partial` 也会在后续重试窗口重读账户并自愈；
- `active_event` 保存事件日、最终应用时间、冻结方向/价格/币数量、应用状态和已止损腿；
  若硬 gross/margin cap 触发了风险缩减，额外保存 `risk_overlay.target_quantities` 作为**有效**
  数量锚点，原始事件目标仍保留在 `target_quantities`，不会静默改写 alpha 目标；
- `stop_reconciliation_through` 保存已经完整扫描过的止损历史高水位；`last_run_mode` 区分
  `execution` / `protect_only` / `reconcile_only`，防止把补账运行误读成 alpha 执行；
- 旧事件 `partial` 的重试只按冻结数量补齐；margin-only 失败不阻塞下一目标事件；
- 已止损腿在旧事件中永久保持目标 0，新目标事件才会重新授权同 symbol 开仓；
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

LS104 使用 `data/ls45_g175_execution.KILL`。kill switch 路径必须与当前 profile 一致，不能误以为
LS45 的开关会阻断 LS104。

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
- 下一次重试会重新读取真实账户，不会重复开仓；
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
make audit-symbols AUDIT_REQUIRED_LEVERAGE=4.0  # 全部标的：4x、多空、翻转、止损和报价
make derivatives-signal                 # Telegram 文本 dry-run
make execution-plan-live                # 读真实账户，只发计划，不下单
make execute-plan                       # 读真实账户，执行器 dry-run，不下单
.venv/bin/python scripts/execute_live_plan.py \
  --live --notify --require-isolated --protect-only
                                        # 只减仓/止损/保证金维护；禁止开仓、加仓
.venv/bin/python scripts/execute_live_plan.py \
  --live --notify --reconcile-only      # 只补记 journal；不计划、不下单
ops/run_live_monitor.sh                 # 只在异常时发 Telegram
```

### 7.2 手动执行链

```bash
ops/run_derivatives_daily.sh            # 遵守窗口和幂等
ops/run_derivatives_daily.sh --force    # 只跳过窗口闸
```

同日成功后普通重试会先走 `--protect-only` 风险维护，再做只读 monitor；不会重新贴旧权重。
`--force` 不是“强制重复交易”，只是允许窗口外补跑一次未完成的当日任务。
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

`scripts/audit_live_track.py` 只读。2026-11-14 真实账户输出为 **37 项硬检查 + 1 项非硬告警**；
下面按检查族归纳：

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
13. 执行状态带账户指纹，且与当前 Bitget 账户一致；旧/未绑定 legacy state 失败；
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
32. `oos_targets.csv` 的 SHA-256 与 manifest `targets_sha256` 完全一致；
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
| 执行状态 | `reports/ls45_live_g125_live/latest.json` | `status` 必须是 `ok`；`partial` 查 failures |
| 对账 | `reports/ls45_live_g125_live/audit.json` | `hard_failures = 0` |
| 巡检 | `reports/ls45_live_g125_live/health.json` | `issues` 为空 |
| journal | `reports/ls45_live_g125_live/journal.csv` | 每日一行；同日重跑覆盖 |
| 数据覆盖 | `reports/ls45_live_g125/manifest.json` | 当前 OOS `mark_coverage.missing_hours = 0`，mark 新鲜 ≤ 30h；历史 warmup 的 2h provider gaps 单独查看，不能和 live OOS 覆盖混为一谈 |
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

先运行 `--protect-only`（或只补账时 `--reconcile-only`），再跑 `make audit-live` 并查看
`audit.json.checks` / `health.json.issues`；
不要只看退出码。常见原因：

- mark / panel 数据过期；
- journal 和交易所订单不一致；
- 空头没有附带止损；
- 目标账本与数据评估日错位；
- 外部资金流未记录；
- 权限或 API key 类型不支持 isolated。

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
- 任何参数变更都必须新建 track/spec，不得静默改写本账本。
