# Atlas20 无杠杆多空候选预注册：H5 退出币固定风险空头

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-11 |
| 状态 | 研究预注册；不接实盘，不改 H5 多头账本 |
| 候选 ID | `PR2026-11-LS4-H5-EXIT-RISK05` |
| 主样本 | 2022-01-01 → 2026-09-21（UTC，左闭右开） |
| 多头 | 冻结 H5 `PR2026-10-H5`，1.0x |
| 空头信号 | H5 实际退出资产，固定 21 个日历日 |
| 单笔风险 | 20% stop 触发时最多损失账户 **0.50%** |
| 单腿 notional | `0.005 / 0.20 = 2.5% NAV` |
| 资金约束 | 只使用 H5 未使用的 gross 预算 |
| target total gross | **0.95x** |
| hard observed gross | **1.00x** |
| 执行 | T+1 UTC +3h |
| 数据 | 严格 point-in-time CMC Top20；Bitget mark；Binance funding proxy/skip |

## 0. 研究问题

LS3 证明 H5 退出后 21 天继续跑输的信号很强：20bps 下 45.9190x，高于基线 21.3487x，
但风险分配不合格：

- MDD -40.75%，比基线差 7.39pp；
- observed gross 1.0820x，145 个 breach hours；
- PBO 0.8225、all-project DSR 0.9043；
- NEAR 单资产贡献 63.5%，前 3 资产 99.0%。

本轮不是扫描 LS3 的空头总权重，而是改用**固定风险预算法**：

> 每笔空头按 20% stop 计算 worst-case loss；单笔最多损失账户 0.50%。
> 因此每笔空头 notional 固定为 2.5% NAV，不随当下闲置 gross 全额扩张。

这个规则直接限制单腿尾部，不需要扫描 0.1/0.2/0.5/1.0 的空头总权重。

## 1. 为什么是 0.50% / 2.5%

- 20% adverse mark stop 是事先固定的尾部保险；
- 若单笔风险预算为 0.50% NAV，则：
  `short_notional = 0.005 / 0.20 = 0.025 = 2.5% NAV`；
- 该腿即使 stop 成交，理论上只让账户损失约 0.50%；
- 多条同时存在时风险仍按各自 0.5% 独立累加，但 target total gross 仍受 H5 闲置 gross 和
  0.95 上限约束；
- 不是根据 LS3 的结果扫描权重，而是采用固定 fractional-risk 规则。

这个规则的风险是：如果 stop 滑点超过 20%，单笔损失会大于 0.5%；报告必须用实际成交费用和
adverse mark 路径核算，不能把 0.5% 当作保证。

## 2. 冻结构造

### 2.1 退出信号

与 LS3 相同：

- H5 前一个目标持有、当前目标完全退出；
- 退出资产仍属于 point-in-time Top20；
- Bitget execution mark 可用；
- 固定 21 个日历日；
- H5 重新买入时提前关闭；
- 同一资产只在没有活跃空头时进入。

### 2.2 固定风险空头

对每个活跃退出资产：

```text
w_short_i = -2.5% NAV
```

然后：

- 多头 H5 保持原目标；
- 空头只使用 `max(0, 0.95 - H5 long gross)`；
- 如果活跃空头总额超过未使用 gross，则统一等比例缩减所有空头；
- H5 多头本身超过 0.95 时缩放到 0.95，不开新空头。

### 2.3 风险与执行

- 20% adverse mark stop；
- long buffer 0.75；
- short buffer 0.50；
- target total gross 0.95；
- hard observed gross 1.00；
- next-tick gross guard：收盘 observed >1.00 后下一小时按比例减仓到 0.95；
- T+1 UTC +3h；
- 缺失 mark 最多 carry 3 小时；
- funding 主口径 Binance proxy/skip；另跑 3x short-adverse。

## 3. 评估门槛

### 3.1 主口径

1. 20bps 终值严格高于 H5 基线；
2. Sharpe 严格高于基线；
3. MDD 不差于基线 5pp；
4. 0 次强平；
5. max target total gross <= 1.00；
6. max observed gross <= 1.00；
7. 所有 stop、funding、费用和 gross guard 成交计入。

### 3.2 成本

- 2/20/50/100bps 全部重跑；
- 50bps 和 100bps 终值均高于同成本基线；
- 100bps MDD <= 50%；
- 四档都满足 gross 硬约束。

### 3.3 funding 与尾部

- 3x short-adverse funding 下 0 强平且 MDD <= 50%；
- 空头单笔实际最大损失不能超过账户 0.50% 太多；超过必须报告原因；
- 报告每个资产的最大 adverse excursion 和 episode PnL。

### 3.4 日历、起点和集中度

- 分年收益；
- 删除最佳年份后仍高于基线；
- 365 天滚动最差不低于基线；
- 至少 12 个真实月初引擎启动，至少剩余 365 天：
  - 终值胜过基线 >= 8/12；
  - Sharpe 胜过基线 >= 8/12；
  - MDD 5pp 门槛 12/12；
- **单资产空头贡献 <= 50%**；
- **前 3 资产空头贡献 <= 80%**；
- 任一集中度门槛失败即不能升级。

### 3.5 多重检验

- PBO/CSCV <= 0.50；
- Reality Check single-step p <= 0.05；
- 全项目 DSR >= 0.95；
- 报告 family、Top20/2022 和 all_trials scope。

### 3.6 样本外

- 2026-09-22 后为真 OOS，不得用于调风险预算；
- 不足 12 个月 OOS 时最高 provisional；
- 无 Bitget 精确 funding、isolated margin、ADL/强平审查，禁止接实盘。

## 4. 失败后动作

- 不扫描 0.25%/0.75%/1.0% per-trade risk；
- 不扫描 15%/25%/30% stop；
- 不扫描持有期 7/14/28/30/60D；
- 不把 2.5% NAV 改成 1%/5%；
- 不改变总 gross 口径；
- 不把 LS4 失败后调成 LS3 或反向；
- 下一轮必须换新的机制并重新预注册。

## 5. 与 LS3 的区别

| 维度 | LS3 | LS4 |
|---|---|---|
| 空头大小 | 吃满 H5 闲置 gross | 每腿固定 2.5% NAV |
| Stop 风险 | 无固定每笔风险预算 | 每笔最多 0.5% NAV |
| 集中度控制 | 等权但总 gross 大 | 单腿固定风险 |
| 预期 gross | 平均 83% | 预计显著更低 |
| 研究目的 | 最大化信号暴露 | 信号 + 固定风险预算 |

## 6. 复现接口

```bash
.venv/bin/python scripts/run_h5_exit_short.py --risk-budget --baseline --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_exit_risk_budget

.venv/bin/python scripts/run_h5_exit_short.py --risk-budget --cost-bps 20 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_exit_risk_budget
```

## 7. 状态

- 当前状态：pre-registered research candidate；
- 是否接实盘：否；
- 是否修改 H5：否；
- 是否增加杠杆：否；
- 是否允许失败后参数搜索：否。
