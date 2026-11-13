# Atlas20 预注册：四个真实引擎候选的等资本组合

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；研究输出不接实盘 |
| 组合 ID | `PR2026-11-LS90-REAL-ENGINE-FUND-OF-FUNDS` |
| 组成 | LS57 60%/1.45x baseline、LS82 core8 market-neutral carry 25%、LS88 low-funding long-only 10%、LS89 21D asset exit |
| 权重 | 每个子账户 25% 初始资本；不调仓、不跨账户再平衡 |
| 数据 | 已保存的 20bps 真实 Bitget 引擎日收益；每个子账户成本已内含 |
| 窗口 | 共同日收益交集，2022-01-01 → 2026-09-20 |
| 成本 | 20bps 主结果；50/100bps 只使用对应子账户已保存的 50/100bps 日收益 |
| 风险 | 组合总 gross 是子账户 gross 的加权平均；不增加额外杠杆 |

## 0. 研究问题

前面测试了多个独立机制，单独看都失败或只 provisional。但它们可能有不同的尾部/收益来源：
LS57 是主引擎，LS82 是 market-neutral carry，LS88 是 long-only low-funding，LS89 是 21D
逐腿退出。LS90 不重新挑因子、不按结果选权重，只检验最简单的组合假设：

> 四个已经真实引擎验证过的策略，按初始资本等权、买入后不调仓，能否比 LS57 单独持有获得更好的
> Sharpe/MDD，同时不牺牲终值？

这不是把多个回测收益做“无成本拼接”：每个子策略的收益已经是独立的 Bitget mark/market/funding
引擎结果；组合只是把初始资金分到四个子账户，不进行每日再平衡。

## 1. 冻结构造

```text
subaccounts = LS57 baseline (60% buffer, 1.45x target)
              LS82 market-neutral carry 25%
              LS88 long-only carry 10%
              LS89 21D exit
weights = 0.25 each at t0
no rebalance; total equity = sum(weight_i * equity_i)
portfolio daily return = total equity.pct_change()
```

- 子策略选择来自已登记的 LS57/LS82/LS88/LS89，不因组合结果重新调规则。
- 共同样本必须完全对齐；任何缺失日 fail closed，不做零填充。
- 20bps 是主结果；50/100bps 使用各自已保存的成本档，不能拿 20bps 曲线硬减成本。
- 若某子策略没有对应成本档，组合该成本档不报告，不把缺失当 0。

## 2. 预注册判定

1. 20bps 组合终值 >= LS57 60%/1.45x baseline；
2. 20bps 组合 Sharpe > baseline；
3. 20bps MDD 不差于 baseline - 1pp；
4. validation 2024–2026 multiple/Sharpe 不低于 baseline；
5. 50/100bps 组合不得出现终值/Sharpe 同时低于 baseline 的情况；
6. 报告每个子账户的贡献、相关性和最大回撤贡献；如果收益只来自 LS57，标记 no incremental alpha。

通过只是组合候选，不是 live promotion；还需要滚动、bootstrap、PBO/DSR 和独立 OOS。

## 3. 复现

```bash
.venv/bin/python scripts/run_ls90_multi_strategy_ensemble.py \
  --cost-bps 20 \
  --output-dir reports/ls90_multi_strategy_ensemble_2026
```
