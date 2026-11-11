# Atlas20 无杠杆多空候选预注册：H5 退出币资金费率拥挤空头

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-11 |
| 状态 | 研究预注册；不接实盘，不改 H5 多头账本 |
| 候选 ID | `PR2026-11-LS6-H5-FUNDING-EXIT-RISK05` |
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| 多头 | 冻结 H5 `PR2026-10-H5`，1.0x |
| 空头信号 | H5 完全退出，且退出资产 7D funding 位于当时 PIT Top20 上三分之一 |
| 持有期 | 21 个日历日 |
| 单腿 notional | 2.5% NAV |
| 单腿名义风险 | 0.5% NAV |
| 空头 stop | 20% adverse mark |
| 资金约束 | 仅使用 H5 未使用 gross |
| target total gross | 0.95x |
| hard observed gross | 1.00x |
| 执行 | T+1 UTC +3h |
| 数据 | 严格 point-in-time CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS4 的 H5 exit-short 信号真实、成本稳健，但失败于：

- 365 天滚动最差 0.7838x < 基线 0.7970x；
- Top20 DSR 0.9424、全项目 DSR 0.9207；
- 140 个 episode 中有 61 个负贡献。

LS5 试图用 14D weak-four 增加信号，但 weak4 sleeve 550 笔净贡献 -2.662%，并把 100bps 成本推失败。

本轮不再叠加高换手信号。只检验一个已有先验支持的入场条件：

> H5 卖出的资产，只有在 funding 拥挤度高时才做空；funding 不高时不交易。

项目 §00.17 已发现 7 日 funding level 是全部候选状态里最强的崩溃月区分变量。LS4 的预注册后诊断显示：

| funding 状态 | episode | episode PnL / 开仓权益 | 平均 | 中位 | 胜率 | 最差 |
|---|---:|---:|---:|---:|---:|---:|
| 上三分之一 | 50 | +7.196% | +0.1439% | +0.1849% | 66.0% | -0.5879% |
| 下三分之一 | 48 | +1.568% | +0.0327% | +0.0164% | 52.1% | -0.5150% |

上三分之一按资产净贡献：NEAR 33.5%、Dogecoin 19.0%、Cardano 12.5%，前 3 合计 65.0%。
该诊断不是正式回测，只用于决定冻结一个机制。

## 1. 冻结构造

### 1.1 Funding rank

在 H5 退出信号日 `D`：

1. 取过去 7 个日历日内每个资产的 Binance funding settlement；
2. 资产必须有至少一个有效 settlement，否则 fail closed；
3. 只对当日 PIT Top20 且有有效 funding 的资产计算 7D 均值；
4. 若有效资产少于 5 个，该日不产生新空头；
5. 对有效资产按 funding 7D 均值做升序百分位排名；
6. 退出资产必须满足 `rank >= 2/3` 才允许加入 sleeve。

不要求 funding 均值为正，因为横截面拥挤度才是冻结变量。

### 1.2 空头 sleeve

- H5 前一个目标持有、当前目标完全退出；
- 退出资产仍属于 PIT Top20；
- Bitget execution mark 可用；
- funding rank 通过；
- 固定持有 21 个日历日；
- H5 重新买入时提前关闭；
- 同一资产只在没有活跃空头时进入；
- 每腿固定 2.5% NAV。

### 1.3 H5 与 gross

- H5 保持 1.0x；
- H5 long gross > 0.95 时只缩放多头至 0.95；
- 空头只使用 `max(0, 0.95 - scaled_H5_long_gross)`；
- 空头资金不足时所有活跃空头等比例缩减；
- target total gross 0.95；
- hard observed gross 1.00；
- next-tick gross guard：observed > 1.00 后下一小时按比例减仓到 0.95。

### 1.4 风险与执行

- 20% adverse mark stop；
- long buffer 0.75；
- short buffer 0.50；
- T+1 UTC +3h；
- missing mark carry 最多 3 小时；
- funding 主口径 Binance proxy/skip；
- 另跑 3x short-adverse。

## 2. 评估门槛

### 2.1 主口径

1. 20bps 终值严格高于 H5 基线；
2. 20bps Sharpe 严格高于 H5 基线；
3. MDD 不差于基线 5pp；
4. 0 次强平；
5. max target total gross <= 1.00；
6. max observed gross <= 1.00；
7. 所有 stop、funding、费用和 gross guard 成交计入。

### 2.2 成本

- 2/20/50/100bps 全部重跑；
- 50bps 和 100bps 终值均高于同成本基线；
- 四档 Sharpe 均高于同成本基线；
- 100bps MDD <= 50%；
- 四档 observed gross <= 1.00。

### 2.3 funding 与尾部

- 3x short-adverse funding 下 0 强平且 MDD <= 50%；
- 实际最大 adverse short mark loss 超过名义 0.5% 必须披露；
- 报告每个资产的最大 adverse excursion 和 episode PnL。

### 2.4 日历、起点和集中度

- 分年收益；
- 删除最佳年份后仍高于基线；
- 365 天滚动最差不低于基线；
- 12 个真实月初引擎启动，至少剩余 365 天：
  - 终值胜过基线 >= 8/12；
  - Sharpe 胜过基线 >= 8/12；
  - MDD 5pp 门槛 12/12；
- 单资产空头贡献 <= 50%；
- 前 3 资产空头贡献 <= 80%。

### 2.5 多重检验

- PBO/CSCV <= 0.50；
- White Reality Check single-step p <= 0.05；
- Top20/2022 和全项目 DSR >= 0.95；
- 报告 family、Top20/2022 和 all_trials scope。

### 2.6 样本外

- 2026-09-22 后为真 OOS，不得用于调参数；
- 不足 12 个月 OOS 时最高 provisional；
- 无 Bitget 精确 funding、isolated margin、ADL/强平审查，禁止接实盘。

## 3. 失败后动作

- 不扫描 funding lookback 3/7/14/30D；
- 不扫描 rank 50%/60%/67%/75%/80%；
- 不扫描 min_assets 3/5/8；
- 不扫描 expiry 7/14/28/30/60D；
- 不扫描 stop 15%/20%/25%/30%；
- 不扫描单腿 1%/2.5%/5%；
- 不扫描 gross 0.90/0.95/1.00；
- 失败后必须设计机制不同的新候选并重新预注册。

## 4. 复现接口

```bash
.venv/bin/python scripts/run_h5_funding_exit_short.py --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_funding_exit_short

.venv/bin/python scripts/run_h5_funding_exit_short.py --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_funding_exit_short
```

## 5. 状态

- 当前状态：pre-registered research candidate；
- 是否接实盘：否；
- 是否修改 H5：否；
- 是否增加杠杆：否；
- 是否允许失败后参数搜索：否。
