# 衍生品轨（Bitget USDT-M）实盘 Runbook

> 适用规格：**`PR2026-10-D-L125-V2`** —— H5 多头账本 × 1.25x 名义、**隔离保证金**、
> 每腿 50% 保证金缓冲、20 bps 成本、T+1 +3h 成交。规格已冻结，本文只描述**执行**，
> 不允许在实盘中改参数。
>
> 证据与门槛状态：`RESEARCH.md` §9.8–9.9、`docs/research/derivatives_track_research_2026-10.md` §13。
> 门槛 #9（pre-2022 压力）为 partial-with-bounding、#10（12 个月样本外）进行中；
> 其余门槛已通过。**在 #10 满 12 个月之前，仓位上限就是「总资金的 3%」小规模试运行。**

---

## 0. 一句话

每天 10:00（北京）左右收到一条 Telegram 播报：**买什么、卖什么、买多少名义、每腿划多少
隔离保证金、调仓后的目标持仓**。照着下单，5 分钟完成；其余一切自动化。

---

## 1. 账户设置（一次性）

| 项目 | 设定 | 理由 |
|---|---|---|
| 交易品种 | Bitget **USDT-M 永续**，仅做多 | 规格冻结为 long-only；开空从未进入候选族 |
| 保证金模式 | **逐仓（isolated）**，不用全仓 | 全仓会把单腿风险扩散到整段资金；隔离下强平距离固定 -51.01% |
| 每腿保证金 | **名义 × 51.5%**（≈ 1.94x；= 50% buffer + 1% 维持保证金 + 0.5% 手续费缓冲） | 这个比例对应强平距离 **-51.01%**；只划 50% 会把强平距离拉近到 -49.49%（§12.8.5/§12.8.10 校准：历史最坏腿 MAE -44.35%，余量 6.66pp） |
| 名义上限 | 账户权益 × **1.25** | 冻结规格；播报里会写「上限 125%」 |
| 杠杆倍数显示 | 以名义为准，不必纠结交易所的杠杆滑杆 | 风险由名义与保证金决定，不由滑杆名字决定 |
| 资金规模 | 总资金的 **3%** 一个 sleeve | 最深回撤 -42.5% ⇒ 总资金约 -1.27%；隔离保证金理论下限是这 3% 全损 |

**不要做的事**：不要用全仓、**每腿保证金不要低于名义的 51.5%**、不要上 >1.25x、不要开空、
不要手动换币、不要「补仓摊平」。

---

## 2. 每日流程（自动 + 手动各一步）

自动（Ubuntu systemd，`ops/systemd/atlas20-derivatives-signal.{service,timer}`）：

```bash
make derivatives-oos-data   # 拉最新 Bitget mark（滚动 3 天窗口，见下），刷新样本外账本
make derivatives-oos        # 只做记录：信号 → 目标仓位 → 与现货路径对照
make derivatives-notify     # 发送当日 Telegram 播报（同日幂等，重跑不会重复发）
```

> **数据新鲜度是硬约束**：下载器按「窗口起点」做增量缓存，所以 Makefile 用**滚动起点**
> （今天 −3 天 → 明天）。若改成固定起点，窗口会被标记 complete 后永久跳过，样本外时钟
> 会静默停住（2026-10-09 实际发生过一次，已修复）。`run_derivatives_oos.py` 还会检查
> 最新 mark 距今不超过 `--max-staleness-hours`（默认 30h），超时直接失败而不是写出一份
> 冻结的账本；确需回放旧数据时用 `--allow-stale`。信号日同样被封顶在**最近一个已收盘的
> UTC 日**，避免用未收盘的当日 bar 生成仓位。

定时器在 **02:00 UTC（北京 10:00）** 与 **03:00 UTC（北京 11:00，模型成交点）** 各跑一次；
第一次成功即发送，同日重跑自动跳过。

手动（收到消息后）：

1. 对照播报里的「今日调仓」，在 Bitget 下限价/市价单，把每腿名义调到目标值；
   （如果当天**没有收到**播报，先看 timer 是否失败：发送器在模型成交时点过去 36h 后会
   拒绝发送并报错——「没消息」不等于「今天不用调仓」。）
2. 每腿划入 `名义 × 51.5%` 的隔离保证金（≈ 1.94x）；
3. 播报若带「该执行时点已过去…请勿追单」，就**当天不做**，等次日信号；
4. 播报里的「参考缩放系数」按你的实际权益换算（模型账本以 1000 USDT 权益计）。

### 2.1 按真实余额计算订单与保证金（推荐；账号接入后全自动）

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
| 强平距离 | 每腿浮亏 | 任一腿浮亏接近 **-35%** → 记录并复核（样本内最坏 -41.14%/-44.35%，-51% 即强平） |
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
