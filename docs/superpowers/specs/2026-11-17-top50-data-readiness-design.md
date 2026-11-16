# Atlas20 Top50 数据就绪与 Top20 信号交接设计

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-17 |
| 状态 | Owner directed；已实现并接入 LS104 live signal 构建；真实数据与逐节点审计通过 |
| 适用轨道 | LS104 live data readiness、executable Top20 signal membership 与可复现审计 |
| 运行频率 | 每日一次，在 CMC 日线完成后、Top20 信号构建前 |
| 数据源 | CMC 日线；现有 Bitget mark/market/funding 目录 |
| 关键规则 | Top50 成员必须有完整数据；无 Bitget 合约跳过并递补下一名；数据不完整阻断并告警 |

## 0. 目标

把当前“Top20 进入后才临时发现数据不够”的链路，改为：

1. 每天收盘后先确定可执行 Top50；
2. 对 Top50 中每个成员确保 CMC、Bitget warmup、Bitget live OOS、funding 和合约规格完整；
3. 只有完整 Top50 才发布当日 ready snapshot；
4. Top20 从 ready Top50 中产生，成员进入 Top20 时不再下载历史数据，直接进入现有策略信号构建；
5. 新成员进入 Top50、数据审核完成、进入 Top20 三类事件通过 Telegram 提醒；
6. 使用原有数据格式、原有目录、原有 gap repair 和 audit，不建立第二套数据定义。

## 1. 现有构建链路

实现必须复用以下既有链路：

- CMC 候选与历史：`scripts/refresh_daily_data.py` → `scripts/download_data.py` → `atlas20.data.processor.download_and_cache_raw_data`；`config/base.yaml` 当前抓取 Top60 候选，CMC 历史起点为 2020-01-01。
- 面板：`scripts/build_datasets.py` → `atlas20.data.processor.build_processed_datasets`；输出 `data/processed/panel_daily.csv`。
- Bitget warmup mark：`data/raw/bitget_derivatives/merged_20261009/`，历史窗口以现有目录内容为准（约 2022-01-01 → 2026-09-20）。
- Bitget warmup market fill：`data/raw/bitget_derivatives/merged_market_20261009/`。
- Bitget live mark/market：`data/raw/bitget_derivatives/merged_oos_20261112/`，当前 live OOS 从 2026-09-01 开始滚动追加。
- Bitget funding：现有 downloader 的精确 funding 缓存和 publication 记录；只使用实际可见历史，不补零、不伪造。
- gap repair：`scripts/repair_bitget_mark_gaps.py`。
- audit：`scripts/audit_derivatives_data.py`、`scripts/audit_venue_symbols.py`、`scripts/audit_signal_equivalence.py`。
- 信号：`scripts/run_ls45_live_signal.py` / `scripts/run_derivatives_shadow.py`，现有 LS104 参数和信号计算不变。

Top50 扩展只增加符号和成员，不改变已有 raw 目录结构、字段名、时间口径或策略计算。

## 2. 每日流程

每日在 CMC 最新已完成 UTC 日出现后执行：

```text
CMC panel complete
  -> build CMC-eligible current Top60
  -> filter Bitget USDT-M contract availability
  -> fill executable Top50 by skipping no-contract names
  -> compare with previous ready Top50
  -> for each new member: build missing full data using existing downloaders
  -> repair gaps with existing repair script
  -> run data completeness and venue audits
  -> publish top50-ready snapshot with fingerprint
  -> construct Top20 from ready Top50
  -> existing LS104 signal construction
  -> existing executor / protection gates
```

若 CMC 面板尚未完成，Top50 readiness 不启动；不得用前一日的 current ranking 冒充今日排名。

### 2.1 排名与递补

- 市值排名权威是 CMC point-in-time；CoinGecko 只用于候选发现和元数据，不用于最终排名。
- 以 CMC eligible 排名为准，从高到低检查 Bitget USDT-M perpetual。
- 没有合约的币记录为 `VENUE_UNAVAILABLE`，不占 Top50 名额，继续取下一名。
- 递补后的 Top50 必须保存完整审计轨迹：原始排名、被跳过币、跳过原因、最终排名。
- 有合约但数据不完整不自动递补；否则会把数据故障伪装成排名变化。该日 readiness 失败并告警。

### 2.2 Top20 生成

- Top20 从当日 ready Top50 的前 20 名生成，不重新下载数据。
- Top20 成员必须已经在 ready snapshot 中；若某成员在信号构建前掉出 ready snapshot，直接阻断该日新信号。
- 进入 Top20 的新币立刻使用已缓存的完整数据构建信号。
- 不改变 LS104 的 H5、LS23、利润保护、空头权重、stop、gross、margin 或执行时钟。

### 2.3 Signal 强绑定

LS104 signal 不再从 CMC panel 独立重算后“碰巧”与 readiness 一致，而是显式消费 READY payload：

- signal 的 `end_date` 必须等于 readiness `as_of`；
- 校验 payload 自身 fingerprint，并在 live 构建中校验当前 `panel_daily.csv`、`metadata.csv` 与
  `symbol_map.csv` 和 readiness 记录的文件哈希逐字节一致；
- 历史日期保留普通 PIT CMC Top20，signal 当日替换为 READY 可执行 Top20；
- 无合约导致的递补成员必须已经存在于原候选行情池，signal 不得为绑定而临时创造或拼接历史；
- manifest 写入 readiness fingerprint、source hash、完整 Top20 membership 与 skip 轨迹；
- signal 等价性审计使用 manifest 指向的 `ready/YYYY-MM-DD.json`，不能读取次日的新 pointer。

该绑定改变的是 universe membership，不改变 H5/LS23 的信号数学、风险参数或执行时钟。

## 3. “完整数据”的判定

一个币只有在以下所有条件通过时才是 `READY`：

### 3.1 CMC 数据

- `panel_daily.csv` 有该币从上市日或配置历史起点以来的连续可用日线；
- 最新一天是最近已完成 UTC 日；
- 无重复 `(date, coin_id)`、无未来日期、无静默零值；
- 用于排名的 market cap 必须是同一天 CMC 值，不能用 carry/stale 值参与排名；
- 价格、成交量、market cap 为正且可解析；
- 对不可解释的缺口 fail closed，不把缺失收益填 0。

### 3.2 Bitget warmup 数据

- `merged_20261009` 中 mark 文件存在且可读；
- `merged_market_20261009` 中 market fill 文件存在且可读；
- 从该币首个可用 bar 到 warmup 结束，小时连续性满足现有 audit；
- 无重复时间、无未来 bar、OHLC 合法、正价格；
- 内部缺口由 `repair_bitget_mark_gaps.py` 修补；修补后仍存在的缺口阻断；
- 不要求上市前数据；但首个可用 bar 之后的缺口不能沉默。

### 3.3 Bitget live OOS 数据

- `merged_oos_20261112` 中 mark 和 market 文件存在且可读；
- 从 2026-09-01 或该币首个可用 bar 到最新完成小时；
- 1 小时连续，最新 required bar 存在；
- 与 warmup 的衔接不能缺失；
- market fill 与 mark 的时间口径一致；
- 当前 quote 新鲜，满足执行 audit。

### 3.4 Funding

- 使用 Bitget exact funding 缓存；
- funding settlement 按合约 `fund_interval` 检查；
- live OOS 区间不得有缺失结算；
- publication request time、rate relation 和文件哈希保留；
- Bitget 历史接口不提供的更早 funding 不得伪造；对 live 信号，完整覆盖当前 OOS 即可。

### 3.5 合约与信号

- 合约在线、USDT-FUTURES、perpetual；
- 满足当前 track 的 4x、long/short/flip、最小下单量、报价和保证金能力；
- 用现有 audit 对合约快照和 venue 能力逐币检查；
- 使用 ready Top50 做一次信号 dry-run，验证 Top20 信号构建没有因该币缺数据而失败；
- 生成 readiness report 和数据指纹；任何一项失败都不得把币标为 READY。

## 4. Telegram 事件

所有通知复用现有 Telegram sender，使用幂等 state：

1. `TOP50_ENTER`
   - 币名、CMC id、原始排名、递补前排名、当前状态；
   - 明确“开始构建完整数据”。
2. `TOP50_DATA_READY`
   - 数据通过；报告 CMC 范围、warmup bar 数、live bar 数、funding 范围、最新时间戳。
3. `TOP50_DATA_BLOCKED`
   - 数据不完整或合约能力不满足；报告缺口和所需处理；
   - 该日 Top20 新信号阻断。
4. `TOP20_ENTER`
   - 进入 Top20 的时间、是否 READY、是否可进入信号；
   - 若不可用，明确“未进入信号，禁止用第 21 名掩盖数据故障”。

首次初始化只建立基线，不向 Telegram 发送 50 条历史消息。相同 `(event, coin_id, as_of)` 只发送一次；失败可重试。

## 5. Track 隔离

- 当前 LS104 live state、journal、manifest、target 和 Telegram state 不被本功能改写。
- Owner 已明确要求 executable Top20 进入当前策略信号；LS104 signal 构建读取当日 READY payload，
  但 readiness 任务本身仍不计划、不撤单、不开仓。
- 当前 LS104 的风险 profile 和 track ID 保持冻结；变更仅限 signal universe 的可执行成员绑定。
- 任何 READY 缺失、指纹不一致、日期不一致或成员不在候选行情池都必须 fail closed，禁止退回
  未审计的 CMC-only Top20。
- signal manifest 与 `prepared.json` 共同锁定 readiness 证据；执行器只能消费完成全链审计的产物。

## 6. 调度与失败处理

- 主运行：每日一次，接在现有 CMC daily refresh 后、现有 derivatives signal 前。
- 现有 08:35/08:55 北京 prepare/catch-up 可作为有界重试；不增加高频盘中扫描。
- 使用文件锁，避免 readiness、derivatives refresh、executor 并发写同一 raw 目录。
- 新成员构建失败时：不发布 ready snapshot、不构建新 Top20 风险、不触碰保护路径；发送 high-priority Telegram。
- 无合约递补失败时：记录失败，不用未审计的替代资产。
- 构建和 audit 必须在执行前完成；否则当天只允许 protect-only 路径。

## 7. 产物与状态

沿用现有数据目录，新增：

- `data/top50_readiness_state.json`：上次 ready Top50、成员首次发现时间、状态、幂等通知键；
- `reports/top50_data_readiness/latest.json`：当前 ready/blocked 摘要、原始排名、递补记录、指纹；
- `reports/top50_data_readiness/history/YYYY-MM-DD.json`：每日快照；
- `reports/top50_data_readiness/top50.csv`：人类可读的 rank、coin_id、symbol、contract、CMC coverage、mark coverage、market coverage、funding coverage、status；
- 现有 raw mark/market/funding 文件保持原路径和格式。

## 8. 验收标准

### 8.1 功能验收

- 当前 CMC 可执行 Top50 在没有新数据缺口时生成 50 个 READY 成员；
- HTX、MNT 等无合约成员被明确跳过，OP、GALA 等下一名可递补；
- 新成员首次进入 Top50 时触发一次数据构建和一次 Telegram；
- 新成员进入 Top20 时直接使用 ready snapshot，不发生临时历史下载；
- 数据不完整时不发布 ready snapshot，不构建新风险；
- 重复运行不重复下载、不重复通知；
- 现有 LS104 state/journal/manifest 字节级不被读取路径以外的逻辑改动。

### 8.2 审计验收

逐节点检查：

1. 排名来源和日期边界；
2. 无合约递补顺序和重复成员；
3. CMC history、当天 market cap、stale 与 future 数据；
4. warmup mark、market、gap repair 前后覆盖；
5. live OOS mark/market、latest required bar、小时连续性；
6. funding settlement、publication 和 interval；
7. contract snapshot、4x、long/short/flip、quote；
8. Top50 ready fingerprint；
9. Top20 handoff 和 signal dry-run；
10. signal 当日 universe 与 READY Top20 完全一致，历史 replay 固定同一 readiness payload；
11. Telegram 幂等；
12. 失败路径、锁、重试和 protect-only；
13. 风险参数、执行时钟与 state/journal 未被 readiness 任务改写。

### 8.3 命令验收

- 定向 Python 测试；
- `make lint`；
- `make typecheck`；
- 与数据链相关的既有测试；
- 对当前真实数据执行只读 readiness audit；
- 对比运行前后的 LS104 state/journal/manifest 哈希，证明未被改写；
- 不以“测试通过”替代真实 artifact 的逐节点审计。

## 9. 非目标

- 不改变 H5、LS23 或其他信号数学与风险参数；
- 不新增数据源来伪造 Bitget 早期 funding；
- 不重写历史 point-in-time 排名；
- 不把 Top50 全部变成持仓；
- 不因为 readiness 构建而自动下单；下单仍由现有 executor 和全部执行闸门控制。
