# 衍生品轨（Bitget USDT-M）实盘 Runbook

> 适用规格：**`PR2026-10-D-L125-V2`** —— H5 多头账本 × 1.25x 名义、**隔离保证金**、
> 每腿 50% 保证金缓冲、20 bps 成本、T+1 +3h 成交。规格已冻结，本文只描述**执行**，
> 不允许在实盘中改参数。
>
> 证据与门槛状态：`RESEARCH.md` §9.8–9.9、`docs/research/derivatives_track_research_2026-10.md` §13。
> 门槛 #9（pre-2022 压力）为 partial-with-bounding、#10（12 个月样本外）进行中；
> 其余门槛已通过。**在 #10 满 12 个月之前，仓位上限就是「总资金的 3%」小规模试运行。**

---

## 0. 部署到 Ubuntu 服务器（一次性；数据不会随 git 带过去）

`data/` 全部在 `.gitignore` 里（唯一例外：`data/derivatives_telegram_state.json`，它随 git 走，
用来跨机器保持"同一天不重复播报"）。**git clone 只带代码，不带数据**。

| 目录 | 大小（本机实测） | 服务器上要不要 | 说明 |
|---|---:|---|---|
| `data/raw/`（除 bitget） | ≈750 MB | **要** | CMC 日线（是 PIT Top20 排名的权威来源）+ Binance/Gate 缓存；空缓存时刷新要全量重拉（慢、可能被限流） |
| `data/raw/bitget_derivatives/merged_*` | 846 MB | 日常**不用**（只有 `merged_oos_*` 4.6 MB 要带） | 那是回测研究用的全历史 mark；日常链只用 OOS 目录 |
| `data/processed/` | 24 MB | **要** | `panel_daily.csv` + `metadata.csv` 等；信号重算直接读这里 |
| `data/*telegram_state*.json` | 几 KB | **要** | 幂等状态；少了会在部署当天重复发一次播报 |

**部署顺序**（一步步来）：

```bash
# 1) 服务器
sudo mkdir -p /opt/atlas20 /etc/atlas20
sudo chown "$USER" /opt/atlas20
git clone <repo> /opt/atlas20 && cd /opt/atlas20
make setup                       # 建 .venv 装依赖

# 2) 从 Mac 同步数据（在 Mac 上执行；rsync 一次，之后服务器自己增量刷新）
rsync -avh --progress data/raw/coinmarketcap data/raw/binance data/raw/binance_1h \
    data/raw/gateio data/raw/coinpaprika data/raw/coingecko <user>@<host>:/opt/atlas20/data/raw/
rsync -avh data/processed/ <user>@<host>:/opt/atlas20/data/processed/
rsync -avh data/raw/bitget_derivatives/merged_oos_20261009/ \
    <user>@<host>:/opt/atlas20/data/raw/bitget_derivatives/merged_oos_20261009/

# 3) 环境文件（token + chat ids；以后再加 Bitget 只读 key）
sudo install -m 600 /dev/null /etc/atlas20/atlas20.env
sudo tee /etc/atlas20/atlas20.env >/dev/null <<'ENV'
ATLAS20_TELEGRAM_BOT_TOKEN=...
ATLAS20_TELEGRAM_CHAT_ID=1231093599,5582320122
ENV

# 4) 先手动验证一遍（dry-run，不发消息）
make refresh-data            # 面板增量刷新（首次约几分钟）
make derivatives-oos-data derivatives-oos derivatives-signal
make execution-plan EQUITY=1000

# 5) 装 timer —— 装「面板刷新 + 自动调仓」两个就够；不要装 atlas20-telegram-signal（现货）
sudo cp ops/systemd/atlas20-data-refresh.{service,timer} /etc/systemd/system/
sudo cp ops/systemd/atlas20-derivatives-execute.{service,timer} /etc/systemd/system/
# 可选：只想要「模型播报」、不想真下单时，装这个代替 execute
# sudo cp ops/systemd/atlas20-derivatives-signal.{service,timer} /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now atlas20-data-refresh.timer atlas20-derivatives-execute.timer
systemctl list-timers 'atlas20-*'
```

> **两个 timer 不要同时装**：`derivatives-signal`（模型播报）与 `derivatives-execute`（真单 + 真持仓播报）
> 各发一条消息。要自动下单就只装 execute；信号内容都在 execute 的消息里。

时间线（UTC）：**02:30 刷面板 → 03:00 合约链（若 02:00 那次已用旧面板，会自动跳过同日旧信号并等这次）**；
06:30 再刷一次面板作为 CMC 发布晚点的兜底。**面板冻结时会怎样**：播报内容停在旧信号日，
超过 36h 后发送器开始报错、timer 变红——"没消息 + timer 失败 = 管线坏了"，不会静默。

---

## 0.1 一句话

每天 10:00（北京）左右收到一条 Telegram 播报：**买什么、卖什么、买多少名义、每腿划多少
隔离保证金、调仓后的目标持仓**。照着下单，5 分钟完成；其余一切自动化。

---

## 1. 账户设置（一次性）

| 项目 | 设定 | 理由 |
|---|---|---|
| 交易品种 | Bitget **USDT-M 永续**，仅做多 | 规格冻结为 long-only；开空从未进入候选族 |
| 保证金模式 | **交易所默认（全仓 crossed）** —— 2026-10-11 负责人决定 | 负责人明确「全仓和杠杆无所谓，只要开的仓位价值对」；跟单 key 也不支持逐仓。**风险由名义上限约束，不再由逐仓保证金率约束** |
| 每腿保证金 | 不再单独划拨（全仓口径） | 逐仓的「名义 × 51.5%」只是**模型口径**；实盘全仓下不适用，`set-margin` 也不支持 |
| 名义上限 | 账户权益 × **1.25** | 冻结规格；**这是实盘唯一的仓位约束**，播报里写「仓位价值 / 占权益」 |
| 杠杆倍数显示 | 以名义为准，不必纠结交易所的杠杆滑杆 | 风险由名义与保证金决定，不由滑杆名字决定 |
| 资金规模 | 总资金的 **3%** 一个 sleeve | 最深回撤 -42.5% ⇒ 总资金约 -1.27%；隔离保证金理论下限是这 3% 全损 |

**不要做的事**：不要上 >1.25x、不要开空、不要手动换币、不要「补仓摊平」、不要让总名义超过权益。

> **逐仓 → 全仓的影响（2026-10-11 记录）**：模型里的 -51.01% 逐腿强平线在全仓下**不存在**
> （交易所对全仓持仓的 `liquidationPrice` 返回 0）。全仓下 1.25x 名义要亏到 ≈-78% 才触及账户强平，
> 所以"−51% 被强平"这件事既不会发生、也不再保护你：单腿亏多少就亏多少，上限是整段 sleeve 全损
> （= 总资金的 3%）。模型规格本身没改，隔离口径仍是回测口径，二者在 −51% 以内路径一致。

### 1.1 API key 与账户前置条件（2026-10-10 真钱实测，必读）

> 教训：第一次真钱 drill（100 USDT）在"下单"这一步走得通，但**逐仓**根本开不出来 ——
> 卡点不在代码，在 key 的类型。上实盘前先跑下面的自检，30 秒，别等下单才发现。

**必须用「普通 API key」，不要用「精英交易 / 跟单 API key」**（Bitget 个人中心 → API 管理里是
两个不同的入口）。官方《Elite Trading API Guide》写明该 key 类型**不支持**：现货、非精英交易对、
**逐仓保证金**、**单边持仓**、**账户模式切换**。用错 key 的实测症状：

| 症状 | 错误码 | 真实含义 |
|---|---|---|
| 下单带 `marginMode=isolated` | `25200 fixedMargin not support` | 该 key 账户不能持逐仓（**与 symbol 无关**） |
| 不带 `marginMode` 下单 | 成交，但 `marginMode=crossed`、`liquidationPrice=0` | 只能全仓 |
| `set-margin(add)` | `40731` | 补 51.5% 保证金这步做不了 |
| `set-hold-mode` / `adjust-account-mode` / `pre-set-leverage` | `40731 This product does not support copy trading` | key 被跟单产品锁死（持仓模式在 Web 端也是灰的） |
| 现货单 | `40020 Parameter symbol not support copy trading` | key 只服务跟单组合 |

**上实盘前的 4 项自检**（任何一项不过就不要上）：

1. `GET /api/v3/account/settings` → `holdMode` 能改（不是 40731）；
2. 设 `set-leverage(symbol, 2, marginMode="isolated", pos_side="long")` 后**下一张单**回读
   `marginMode == "isolated"`（只有配置项变成 isolated 不算数）；
3. `set-margin(add)` 能补到「名义 × 51.5%」，且 `liquidationPrice` 给出 ≈ −51% 口径的强平价；
4. 权限里**不应**出现 `copy_futures_order` / `copy_futures_position`（那是跟单 key 的标志）。

**持仓模式差异已被代码吸收**：hedge 账户下 `posSide` 必填、`posSide`+`reduceOnly` 同用报 `25238`；
单边账户反过来。`close_position()` 会读账户 `holdMode` 自动选正确的写法，平仓请用它，不要手搓。

**账户若有活跃的精英交易组合**：本账户下单可能镜像给跟随者，上实盘前先确认组合状态。

---

## 2. 每日流程

### 2.0 全自动（默认路线，2026-10-11 起）

`ops/systemd/atlas20-derivatives-execute.{service,timer}` 每天 **03:05 UTC（北京 11:05）** 跑：

```bash
make derivatives-oos-data derivatives-oos   # 刷 mark + 冻结账本 → 当日目标仓位
make execute-plan-live                      # = scripts/execute_live_plan.py --live --notify
```

它做四件事，全部自动：① 按**账户真实权益**把目标仓位换算成"买/卖多少枚"；② 直接市价下单
（先减后加，和引擎同序）；③ 回读成交均价/手续费/持仓，拼出播报；④ 发 Telegram（同日幂等）。

播报里的每个数字都来自交易所：**今天买了/卖了多少枚、成交均价、手续费、当前每个币的真实持仓
和占比、可用保证金、目标 vs 实际**。它还会说明「保证金模式」「未完成的单」「被跳过的动作」。

**安全闸**（都在脚本里，出事就停而不是偷偷下单）：

| 闸门 | 行为 |
|---|---|
| `data/derivatives_execution.KILL` 存在 | 立刻拒绝交易（删文件即恢复） |
| 信号日期超过 36h（`--max-signal-age-hours`） | 拒绝执行，提示先刷数据管线；确需补跑加 `--allow-stale-signal` |
| 账户权益 < `--equity-floor`（默认 20 USDT） | 拒绝交易 |
| 同一信号日已成功执行 | 直接跳过（`--force` 才能重跑），避免一天重复调仓 |
| 单笔失败 | 记录进播报并等下一次（次日计划从真实持仓重算，自我修正），exit 1 让 timer 变红 |
| 逐仓不可用的账户 | 自动退回全仓，并在播报里用 ⚠️ 明写（见 §1.1） |

**只想看不想下单**：`make execute-plan`（dry run，照常读真账户、照常打印播报但不发单、不发消息）。

**每天记账**：每次执行都会往 `reports/derivatives_track_live/journal.csv` 写**一行/天**（同日重跑覆盖，
不重复计），字段 = 日期、信号日、权益、仓位价值、现金、**当日盈亏**、当日收益率、手续费、funding、
未实现盈亏、持仓明细、成交明细、备注。第二天播报里的「今日/昨日盈亏」就是这张表算出来的。
配套 `make audit-live`（只读）会把台账和交易所逐项对账：账户恒等式、仓位市值、成交记录、冻结目标、
总名义上限、PnL 链。

**播报风格（2026-10-11 负责人要求）**：只留「总权益 / 仓位价值 / 今日盈亏 / 昨日盈亏 / 今日成交 /
当前持仓 / 目标 vs 实际」；保证金模式、强平口径、方法论这些不占版面，出问题才出现。

**为什么信号日有时看着是「前几天」？**（2026-10-11 记录）冻结账本不是"每天换一个仓位"，
而是**事件序列**：只有某个 sleeve 真的换了标的，账本才会多一行。例如 10-08 那行是 `BUY NEAR 0.7768`，
之后 10-09、10-10 都没有 sleeve 换仓，所以账本最新一行仍然是 10-08 —— **这就是当前信号**，
持仓继续拿 NEAR 就是对的，不是数据没更新。判断"数据有没有更新"要看两件事，`make audit-live`
会替你查：① mark 最新到几小时前（门槛 30h）；② 账本评估到的日期 = 数据能判定的最新日期（没有跳日）。
两个都过，就说明没有漏掉任何变化。

### 2.1 两个只读核对

| 命令 | 查什么 | 期望 |
|---|---|---|
| `make audit-live` | 账户恒等式、仓位市值重算、台账成交 vs 交易所订单历史、持仓 vs 冻结目标、无计划外持仓、总名义 ≤1.25x、台账 PnL 链、mark 新鲜度、账本评估日、信号日一致 | 全 ✅ |
| `make audit-signal` | 用**回测同一套函数**把账本重建两遍（结束日 = 回测终点 vs 今天），逐事件比对 | 重叠事件日 0 不一致、回测有而实盘没有 0 个 |

`make audit-signal` 是"信号到底是不是回测那个信号、有没有前视"的机器证明：2026-10-11 实测
重叠 599 个事件日全部一致（最大权重差 0），只在实盘侧多出 11 个样本外事件。

### 2.2 手动/半自动（备用）

自动路线的组件也可以单独用：

```bash
make derivatives-oos-data   # 拉最新 Bitget mark（滚动 3 天窗口，见下），刷新样本外账本
make derivatives-oos        # 只做记录：信号 → 目标仓位 → 与现货路径对照
make derivatives-notify     # 只发模型播报（同日幂等，重跑不会重复发）
```

> **数据新鲜度是硬约束**：下载器按「窗口起点」做增量缓存，所以 Makefile 用**滚动起点**
> （今天 −3 天 → 明天）。若改成固定起点，窗口会被标记 complete 后永久跳过，样本外时钟
> 会静默停住（2026-10-09 实际发生过一次，已修复）。`run_derivatives_oos.py` 还会检查
> 最新 mark 距今不超过 `--max-staleness-hours`（默认 30h），超时直接失败而不是写出一份
> 冻结的账本；确需回放旧数据时用 `--allow-stale`。信号日同样被封顶在**最近一个已收盘的
> UTC 日**，避免用未收盘的当日 bar 生成仓位。

定时器在 **02:00 UTC（北京 10:00）** 与 **03:00 UTC（北京 11:00，模型成交点）** 各跑一次；
第一次成功即发送，同日重跑自动跳过。

手动（只在需要人肉复核时，或者 `derivatives-signal` 路线下）：

1. 对照播报里的「今日调仓」，在 Bitget 下限价/市价单，把每腿名义调到目标值；
   （如果当天**没有收到**播报，先看 timer 是否失败：发送器在模型成交时点过去 36h 后会
   拒绝发送并报错——「没消息」不等于「今天不用调仓」。）
2. 每腿划入 `名义 × 51.5%` 的隔离保证金（≈ 1.94x）；
3. 播报若带「该执行时点已过去…请勿追单」，就**当天不做**，等次日信号；
4. 播报里的「参考缩放系数」按你的实际权益换算（模型账本以 1000 USDT 权益计）。

### 2.3 按真实余额计算订单与保证金（计划预览 / 排障用）

上面的播报以 1000 USDT 参考权益计价，实际下单还要自己换算。接入账号后可改为**按余额
动态计算**，直接给出「买/卖多少枚、名义多少 USDT、保证金加/减多少」：

```bash
# A. 手动填余额（不接 API，最快）
make execution-plan EQUITY=500

# B. 用导出的账户快照（JSON schema 见脚本 docstring）
.venv/bin/python scripts/plan_live_execution.py --account-file account.json --notify

# C. 直连 Bitget UTA API（推荐；只读账户，下单仍然手动）
export ATLAS20_BITGET_API_KEY=...      # UTA 只读+划转权限即可
export ATLAS20_BITGET_SECRET_KEY=...
export ATLAS20_BITGET_PASSPHRASE=...
export ATLAS20_BITGET_DEMO=1           # 演示盘（paptrading: 1），先在练习账户验证
make execution-plan-live               # 内部带 --notify，同日幂等
```

`make execute-plan-live` 是上一条自动路线的入口；下面这几个是**只看不下单**的排障入口。
计划脚本每天重新读取交易所的 `usdtEquity` / `positionBalance`，因此**不依赖前一天的缓存**，
下单误差最多持续一天就会在次日计划里自我修正（replay 实测 4.7 年累计偏差 +0.39%，见
`reports/derivatives_track_live_replay/`）。

**51.5% 保证金怎么落地**（Bitget 只能按杠杆整数倍自动划保证金）：

1. 先把该 symbol 设为 **逐仓 + 2x**（`set-leverage`，自动保证金 ≈ 名义 50%，强平距离 -49.49%）；
2. 成交后按计划里的「保证金调整 · 追加」用 `set-margin(operation=add)` 补到名义的 **51.5%**
   （强平距离 -51.01%，= 模型口径）；
3. 减仓日会自动算出「撤出」金额（`operation=remove`），同样来自交易所的真实
   `positionBalance`，不是估算值。

---

## 3. 监控清单（每周 5 分钟）

| 指标 | 在哪里看 | 触发动作 |
|---|---|---|
| 样本外账本 vs 模型 | `reports/derivatives_track_oos_2026/report.md` | 日收益应是现货 H5 路径的 1.2–1.32 倍；偏离到 1.0x 以下连续 5 天 → 检查是否漏单 |
| 强平距离 | 每腿浮亏 + 账户 `mgnRatio` | 全仓口径：`liquidationPrice` 恒为 0，看账户维持保证金率；任一腿浮亏接近 **-35%** → 记录并复核（样本内最坏 -41.14%/-44.35%） |
| funding 累计成本 | Bitget 账单 + `reports/derivatives_track_funding_calibration/` | 若 30 天累计 funding 超过模型 adverse 假设的 **3 倍** → 暂停开新仓复核 |
| 数据完整性 | `make derivatives-oos-data` 输出 | 单日缺失窗口 >5% → 当天不调仓，先修数据 |
| 资产上线/下线 | Bitget 公告 | 若持仓币种被下架 → 立即平仓该腿，其余照常 |

## 4. Kill criteria（预注册，出现即停）

1. **sleeve 回撤 > -45%**（样本内最差 -42.5%，3x funding 口径）→ 全部平仓，回研究；
2. **发生任何一次强平** → 全部平仓，回研究；
3. **连续 2 个月跑输同口径样本外模型 5pp 以上** → 暂停，核对成交价/漏单/数据；
4. **连续 3 周 funding 超过模型 adverse 带 3 倍** → 暂停开新仓；
5. **数据管线失效超过 5 个交易日** → 冻结调仓（持仓不动），修复后再恢复。

恢复条件：找到并修复原因、在 `RESEARCH.md` 记录，再按 3% sleeve 重新起跑。

---

## 5. 小规模试运行（shadow → micro-live）

| 阶段 | 规模 | 时长/条件 | 通过标准 |
|---|---|---|---|
| S0 影子 | 0 | 已有 17/365 天 OOS 记录 | 继续累积 |
| S1 微实盘 | sleeve 的 10% | ≥2 周 | 成交价与播报执行点偏差 <0.5%；无漏单；无强平 |
| S2 标准 | 100% of 3% sleeve | S1 通过后 | 逐周记录，直到 OOS 满 12 个月再做全量复核 |

任何阶段出现 §4 的 kill criterion 都退回上一阶段。

---

## 6. 复现与审计

- **执行逻辑实测（live-fire replay）**：`scripts/replay_live_execution.py` 把引擎 2022-01-01 →
  2026-09-21 的 534 次调仓 / 1185 笔订单逐笔喂给实盘计划器（`build_execution_plan`）：
  1185/1185 全部匹配、0 不匹配；再让账户完全按计划器自己的（含真实 Bitget 合约步长与
  最小下单量的）订单演化 4.7 年，最终 42.7206x vs 引擎 42.5559x（**+0.387%**），逐小时强平
  检查 **0 次**。报告：`reports/derivatives_track_live_replay/`。
- **合约量化代价**：1185 笔中 73 笔（6.2%）低于交易所最小下单量（多为零头再平衡，次日自我
  修正），其余订单名义误差均值 1.29%、p95 6.16%、最大 49.8%（全部是向下取整，不会超仓）。


```bash
make derivatives-oos-data derivatives-oos   # 刷新账本
make derivatives-signal                     # 干跑：只打印当日播报
git log --oneline -- reports/derivatives_track_oos_2026   # 每日账本的提交历史
```

- 每一条实盘播报都由 `scripts/send_derivatives_signal.py` 从冻结账本生成，
  消息里带 spec id、信号日、执行时点，事后可逐条比对；
- 账本的每日产物（`oos_daily.csv`、`oos_targets.csv`、`oos_trades.csv`）提交入库，
  实盘成交单应逐日与 `oos_trades.csv` 对照存档；
- funding 目前按零计（上界）。实盘请把 Bitget 实际 funding 记入对账表，
  用来逐步替换这个上界并复核 §3 的 3 倍规则。
