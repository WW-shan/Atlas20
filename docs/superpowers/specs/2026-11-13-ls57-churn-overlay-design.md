# Atlas20 研究预注册：LS57 + residual-gross Top20 churn overlay

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 候选 ID | `PR2026-11-LS75-LS57-CHURN-RESIDUAL-GROSS` |
| 基线 | `PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE` @20bps |
| Sleeve | `PR2026-11-LS74-TOP20-CHURN-ALT-WEAK-FULLGROSS` @20bps |
| 数据 | Bitget target gross + 日频 PIT Top20 churn returns |
| 窗口 | 2022-01-01 → 2026-09-20 |
| 硬 gross | 1.50x |
| 成本 | 两边均为 20bps；funding 尚未合并 |

## 0. 研究问题

LS74 的 return-space 20% overlay 看似把 LS57 从 68.8077x 提高到 78.2480x，但直接相加没有
使用 LS57 的真实 gross 占用。LS57 刷新后的 `target_gross.csv` 显示平均 `total_gross`
约 0.534x、最大 1.30x，说明组合确实存在 residual gross；本族只检验：**把 LS74 sleeve 限制在
`1.50 - LS57_total_gross` 的剩余 gross 内，收益改善是否仍存在。**

## 1. 冻结规则

对每个交易日：

```text
residual = max(0, 1.50 - ls57_total_gross)
scale = min(allocation, residual / ls74_gross) if ls74_gross > 0 else 0
combined_return = ls57_return + scale * ls74_return
```

- allocation 固定为 10% / 20% / 25% NAV 三档，全部报告；
- 不使用未来 gross 或未来收益来选分配；
- LS74 使用预先冻结的 `alt_rel_60, m=7, h=28, full-gross` 日收益；
- 不重新计算 LS57 的选币、利润锁、空头 stop 或 funding；
- 这是 **return-space gross-budget diagnostic**，不是完整合并引擎；
- funding 未合并，不能用这个结果 promotion。

## 2. 验收

对每个 allocation 同时检查：

- full 20bps 终值 > LS57 基线 68.8077x；
- full Sharpe > LS57 基线 1.9819；
- full MDD 不差于 -40.84%（相对基线允许 1pp 恶化）；
- validation 终值和 Sharpe 都高于同窗口 LS57；
- 实际 combined gross <=1.50x，且报告的 residual scale 没有负值。

选取满足全部门槛的**最大 allocation**；如果 25% 也通过，不继续加到 30% 或更高。通过只进入
真实 funding/Bitget mark/fill 合并引擎，不直接接实盘。

## 3. 复现

```bash
.venv/bin/python scripts/run_ls57_churn_overlay.py \
  --start-date 2022-01-01 --end-date 2026-09-20 \
  --output-dir reports/ls57_churn_overlay_2026
```
