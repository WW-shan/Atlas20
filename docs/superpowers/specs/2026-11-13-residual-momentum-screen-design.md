# Atlas20 研究预注册：PIT Top20 residual momentum screen

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 预注册筛查；不是实盘候选；不修改 live |
| 候选 ID | `PR2026-11-LS60-RESIDUAL-MOMENTUM-SCREEN` |
| 样本 | 2022-01-01 → 2026-09-21（UTC） |
| 数据 | 严格 PIT CMC Top20；`data/processed/panel_daily.csv`；日收益 |
| 因子 | 60D 滚动 BTC beta；28D 残差收益动量 |
| 组合 | 月度（28D）多高残差/空低残差，各 4 个资产，每腿 12.5% NAV，gross 1.0x |
| 执行 | 信号日收盘生成，下一交易日生效；逐日盯市；换手收成本 |
| 成本 | 2 / 20 / 50 / 100bps |
| Funding | 本筛查不计 funding，明确列为后续集成门槛 |

## 0. 研究问题

现有 H5/LS57 的收益主要来自价格动量和少数极端赢家，PBO 仍高。文献索引中列出的 crypto
residual momentum 尚未在 Atlas20 的严格 PIT Top20 中测试。这里先做一个独立因子筛查：

> 在同一时点 Top20 内，用 60D BTC beta 去掉市场共同波动后，过去 28D 残差收益最高的资产是否
> 继续跑赢残差收益最低的资产？

这是纯因子筛查，不把结果直接塞进 H5，也不改变 L125-V2。若因子有足够强的独立收益和稳定性，
下一步才讨论用 0.20x gross 以内的 sleeve 进行组合；若失败，停止该因子家族，不扫描窗口、数量、
权重或只做多/只做空版本。

## 1. 冻结构造

```text
universe(D) = PIT Top20 members at D
price_returns = daily log returns, no future data
market = bitcoin
beta_i(D) = Cov(r_i, r_btc) / Var(r_btc) over trailing 60 calendar days
residual_i(t) = r_i(t) - beta_i(D) * r_btc(t)
score_i(D) = sum of residual_i over the last 28 trading observations
long = top 4 scores
short = bottom 4 scores
weight = +0.125 each long / -0.125 each short
```

- 每个 rebalance 事件要求至少 8 个有效候选；
- 少于 45 个 beta 观测或少于 28 个残差观测的资产不合格；
- 缺失收益不静默填充：持有资产的缺失日按 0 计入当日组合收益，但必须报告缺失数量；
- 不扫描 20/40/60/90/120D beta、14/28/56D momentum、2/3/5/6 个资产、权重或调仓频率；
- 不做杠杆扩张；组合 gross 固定 1.0x。

## 2. 预注册筛查门槛

1. 20bps 年化 Sharpe >= **0.8**；
2. 20bps 期末 multiple > **1.0x**，MDD 不差于 **-40%**；
3. 50bps 期末 multiple > 1.0x 且 Sharpe >= **0.5**；
4. 2022–2026 至少 **4/5** 个日历年为正收益；
5. 前半年与后半年收益均为正（2022-01→2024-05 与 2024-05→2026-09，按实际交易日中点）；
6. 因子换手、gross、缺失收益、单资产贡献和年份分解完整报告；
7. 本筛查不计 funding，所以即使通过也只能进入组合集成研究，不能直接 promotion。

若任一门失败，停止该 residual momentum 家族；不通过参数邻域寻找替代版本。

## 3. 复现

```bash
.venv/bin/python scripts/run_residual_momentum_screen.py \
  --start-date 2022-01-01 --end-date 2026-09-21 \
  --output-dir reports/residual_momentum_screen_2026
```

研究输出不是订单，也不是实盘批准。
