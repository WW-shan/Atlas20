# Atlas20 预注册：LS91 core-satellite 的 maker-shadow 成本敏感性

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；execution shadow；不接实盘 |
| 组合 ID | `PR2026-11-LS92-LS91-MAKER25-SHADOW` |
| 组成 | 与 LS91 相同：50% LS57 60%/1.45x、25% LS82 market-neutral carry、25% LS88 long-only carry |
| 成本 | 13.0164bps 每边；来自 2026 Bitget 逐笔/L1 maker shadow 的 25% capacity haircut |
| 权重/调仓 | 初始资本 50/25/25；不调仓；无跨账户再平衡 |
| 窗口 | 2022-01-01 → 2026-09-20 |
| 数据 | 每个子账户重新用同一 Bitget mark/market/funding 引擎，成本参数改为 13.0164bps |
| 风险 | 13.0164bps 是 shadow 假设，不是已验证的 2022–2026 真实成交成本 |

## 0. 研究问题

LS91 在 20bps 下通过 full/validation 主门槛，但 50/100bps 失败。此前 §00.92/§00.95 的 maker
shadow 给出 25% volume-capacity haircut 下有效成本 13.0164bps；本 trial 只问：如果同一执行
机制在历史窗口能达到该成本水平，LS91 的收益和回撤是否仍值得继续验证？

这不是新 alpha，也不修改 live cost assumption。13.0164bps 来自单一 2026 execution 样本，
必须保留 queue/部分成交/撤单/ADL 外推限制。

## 1. 冻结构造

```text
subaccounts = LS57, LS82 25%, LS88 10%
weights = 50% / 25% / 25% initial capital, no rebalance
cost = 13.0164bps per side for each subaccount engine run
```

- 交易规则、universe、funding、mark/fill、stops、gross cap 与 LS57/LS82/LS88 完全相同。
- 不使用 20bps 日收益曲线线性减成本；重新运行每个子账户的 13.0164bps 引擎。
- 不扫描 10/13/15/17bps，不改变 maker offset、timeout、through 或 adverse guard。
- 共同样本必须对齐；缺失 fail closed。

## 2. 预注册判定

1. 13.0164bps LS92 full multiple >= LS57 13.0164bps；
2. full Sharpe > LS57 13.0164bps；
3. MDD 不差于 LS57 13.0164bps - 1pp；
4. validation multiple/Sharpe 不低于 LS57 13.0164bps；
5. 报告每个子账户贡献和相关矩阵；
6. 如果收益只来自 LS57 或 13.0164bps 不具跨年可迁移性，标记 shadow-only，不晋级。

通过仍是 shadow candidate，必须有真实小单/队列数据和独立 OOS 才能讨论 live。

## 3. 复现

先分别运行 13.0164bps 的 LS57/LS82/LS88 引擎，再用 LS90 组合器组合：

```bash
.venv/bin/python scripts/run_ls90_multi_strategy_ensemble.py \
  --trial-id PR2026-11-LS92-LS91-MAKER25-SHADOW \
  --weights 0.50,0.25,0.25,0.00 --cost-bps 13.0164 \
  --output-dir reports/ls92_core_satellite_maker_shadow_2026
```
