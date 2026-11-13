# Atlas20 预注册：LS57 核心 + carry 卫星组合

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；研究输出不接实盘 |
| 组合 ID | `PR2026-11-LS91-LS57-CORE-CARRY-SATELLITE` |
| 组成 | 50% LS57 60%/1.45x、25% LS82 market-neutral carry 25%、25% LS88 low-funding long-only 10% |
| 权重 | 初始资本 50/25/25；不调仓；LS89 风险 overlay 权重 0 |
| 数据 | 已保存真实引擎 20bps 日收益；成本已内含 |
| 窗口 | 2022-01-01 → 2026-09-20，validation 2024-01-01 → 2026-09-20 |
| 成本 | 20bps 主结果；50/100bps 使用对应成本档 |
| 总 gross | 子账户 gross 的加权平均，不增加额外杠杆 |

## 0. 研究问题

LS90 四等权把 LS89 风险 overlay 也算成收益子账户，导致 validation multiple 略低于 LS57。LS91
不调 LS57/LS82/LS88 的内部规则，只按角色设定固定核心-卫星资本：LS57 是主收益引擎，LS82 是
中性 carry，LS88 是低 funding long satellite；LS89 已被证明主要是 risk-only，因此权重为 0。
这不是根据 validation 选权重，而是把风险 overlay 和收益引擎分开。

## 1. 冻结构造

```text
weights = {LS57: 0.50, LS82: 0.25, LS88: 0.25, LS89: 0.00}
no rebalance; total equity = sum(weight_i * subaccount equity_i)
```

- 子策略参数、成本、执行和 funding 不变；不使用 LS89 的收益。
- 20/50/100bps 分别使用已保存的真实引擎日收益，不把 20bps 曲线线性减成本。
- 不扫描 40/50/60% core、20/25/30% satellite 或四舍五入权重；不加入新 sleeve。
- 共同样本必须完全对齐，缺失 fail closed。

## 2. 预注册判定

1. 20bps 组合终值 >= LS57 60%/1.45x baseline；
2. 20bps 组合 Sharpe > baseline；
3. 20bps MDD 不差于 baseline - 1pp；
4. validation multiple/Sharpe 不低于 baseline；
5. 50/100bps 不出现终值和 Sharpe 同时低于 baseline；
6. 子账户贡献和相关矩阵必须报告；若收益只来自 LS57，标记 no incremental alpha。

通过只是 portfolio candidate，不接实盘；仍需滚动、bootstrap、PBO/DSR 和独立 OOS。

## 3. 复现

```bash
.venv/bin/python scripts/run_ls90_multi_strategy_ensemble.py \
  --trial-id PR2026-11-LS91-LS57-CORE-CARRY-SATELLITE \
  --weights 0.50,0.25,0.25,0.00 --cost-bps 20 \
  --output-dir reports/ls91_core_satellite_ensemble_2026
```
