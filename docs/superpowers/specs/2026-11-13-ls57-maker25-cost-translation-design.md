# Atlas20 execution research: LS57 maker-25% haircut cost translation

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13（本地） |
| 状态 | 已预注册；execution sensitivity；不接实盘 |
| 候选 ID | `PR2026-11-EX6-LS57-MAKER25-COST-TRANSLATION` |
| 基线 | 现有 LS57 20bps 回测 |
| 新成本 | **13.0164bps per side** |
| 来源 | EX4 在 2026 LS57 样本的 25% volume-capacity haircut 加权有效成本 |
| 样本 | LS57 2022-01-01 → 2026-09-21，策略交易、funding、mark、gross 全部不变 |

## 0. 研究问题

EX4 的真实逐笔 + Level1 修复显示，25% haircut 下的 maker-first 加权有效成本为
**13.0164bps**，而当前 LS57 回测和实盘保守口径使用 **20bps**。本轮不改变任何选币、
权重、profit lock、short router、stop 或 gross，只把同一个 LS57 的每边成本替换为 13.0164bps，
量化 maker-first 如果真的达到该成本水平时对复利终值和风险的影响。

这不是 alpha 回测，也不是 live promotion。13.0164bps 来自单一 2026 execution 样本，外推到
2022–2026 是明显的数据可用性限制；只能作为 execution value 的上界估计。

## 1. 预注册验收

1. 13.0164bps 终值高于 20bps LS57；
2. Sharpe 不低于 20bps LS57；
3. MDD 不差于 20bps LS57 加 1pp；
4. 0 强平、0 gross breach、observed gross <=1.50x；
5. 与既有 2/20/50/100bps 成本结果并列报告，不把 13.0164bps 称为已验证 live 成本；
6. 不扫描 5/10/15/18bps，不改变 LS57 的任何交易规则；
7. 结果最高状态为 execution shadow，不修改 `PR2026-10-D-L125-V2` 或 live executor。

## 2. 复现

```bash
.venv/bin/python scripts/run_h5_regime_short_router.py \
  --trial-id PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE \
  --start-date 2022-01-01 --end-date 2026-09-21 --cost-bps 13.0164 \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --funding-source binance-proxy --funding-missing-policy skip \
  --output-dir reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_stable1d_redistribute_cost130164
```

研究输出不是订单，也不是实盘批准。
