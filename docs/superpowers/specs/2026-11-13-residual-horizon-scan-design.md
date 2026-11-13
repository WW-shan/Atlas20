# Atlas20 研究预注册：residual momentum horizon / sign scan

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 扩展因子筛查；不是实盘候选；不修改 live |
| 候选族 ID | `PR2026-11-LS62-RESIDUAL-HORIZON-SCAN` |
| 发现样本 | 2022-01-01 → 2023-12-31（UTC） |
| 验证样本 | 2024-01-01 → 2026-09-21（UTC） |
| 最新观察 | 2026-09-22 → 2026-11-12（UTC，仅记录，不用于调参） |
| 数据 | strict PIT CMC Top20；`data/processed/panel_daily.csv` |
| 市场因子 | Bitcoin 日 log return |
| beta | 120D rolling covariance / variance，至少 90 个有效观测 |
| 组合 | 月度 28D；多空各 4 个资产；每腿 12.5% NAV；gross 1.0x |
| 执行 | 信号日 close 生成，下一交易日生效；逐日盯市；换手收费 |
| 成本 | 2 / 20 / 50 / 100bps；本筛查暂不计 funding |

## 0. 研究问题与 owner 指令

LS60/LS61 只检验了 `60D beta + 28D residual score` 的动量和反转动量。两者在不同样本中符号
不稳定，但这不构成对整个 residual-factor 方向的否决。Owner 已明确要求持续研究、不要用
“family 失败即停止”的人为限制阻断后续试验。因此本轮把假设扩展为经典 residual momentum
的期限结构，并把所有配置一次性登记、一次运行、完整保留，不根据中间结果偷偷换参数。

经典 equity residual momentum 通常采用长 formation window 并跳过最近一个月，以避开短期反转。
本轮直接检验这个机制在 crypto PIT Top20 是否成立，同时检验相反符号，避免只用单边结果解释。

## 1. 冻结构造

```text
universe(D)       = PIT Top20 at D
market            = bitcoin
beta_i(D)         = Cov(r_i, r_btc) / Var(r_btc) over trailing 120 calendar days
residual_i(t)     = r_i(t) - beta_i(D) * r_btc(t)
score_i(D)        = sum residual_i over the last L observations, skipping the latest S observations
long              = top 4 scores if direction=+1, bottom 4 if direction=-1
short             = bottom 4 scores if direction=+1, top 4 if direction=-1
weight            = +/-0.125 per selected asset
```

冻结网格：

- `L ∈ {63, 126, 252}` 个有效日收益观测；
- `S ∈ {0, 21}` 个有效日收益观测；
- `direction ∈ {+1, -1}`；
- beta window 固定 120D / min 90 observations；
- 28D rebalance、4+4、12.5%/leg、gross 1.0x、min 8 eligible assets；
- 总共 **12 个配置**，全部写入同一 trial log。

不加入止损、杠杆、funding、资产白名单、波动率缩放或 2024 年后的二次参数扫描。

## 2. 评估与分层

发现样本只用于给配置排序；验证样本和最新观察都只记录，不参与选择。报告每个配置的：

1. 2/20/50/100bps 终值、CAGR、Sharpe、MDD；
2. discovery / validation / latest 三段 20bps 结果；
3. 年度收益、换手、max gross、缺失收益；
4. 资产贡献集中度和 Bitcoin realized beta；
5. 与 BTC buy-and-hold 的同段比较。

分层仅用于描述证据强度，不作为永久研究禁令：

- `candidate-for-integration`：20bps full sample 终值 > 1、Sharpe > 0.8，discovery 与 validation
  20bps 都为正且 Sharpe 均 > 0.5，50bps 终值 > 1；
- `watch`：至少两段同号，但未满足上项；
- `rejected-now`：证据不足或方向不稳定。

即使 12 个配置全部失败，也只记录这个网格失败；后续可以登记新的经济假设并继续研究，不需要
修改本轮结果或把它包装成成功。

## 3. 复现

```bash
.venv/bin/python scripts/run_residual_horizon_scan.py \
  --start-date 2022-01-01 \
  --end-date 2026-11-12 \
  --output-dir reports/residual_horizon_scan_2026
```

研究输出不是订单，也不是实盘批准。
