# Atlas20 候选预注册：core8 carry risk-first follow-up

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；等待正式运行；研究输出不接实盘 |
| 候选 ID | `PR2026-11-LS82-LS57-CORE8-CARRY-RISK` |
| 基线臂 | LS57 + core8 carry，50% long buffer，目标 gross 1.50x |
| 风险臂 | LS57 + core8 carry，60% long buffer，目标 gross 1.45x，hard cap 1.50x |
| Sleeve | 与 LS81 完全相同的 core8 PIT funding carry；只固定 25% allocation |
| 主窗口 | 2022-01-01 → 2026-09-20（warmup 2021-01-01） |
| 执行 | T+1 UTC +3h；Bitget mark 做标记/强平，Bitget market candle 做成交；missing mark carry 最多 3h |

## 0. 研究问题

LS81 的 20bps normal 收益和 Sharpe 高于同一严格引擎基线，但 10/20/25% 三个 allocation 都出现
一次 SOL long 强平，25% 还出现 59 个 gross breach 小时。失败点不是信号排序，而是 carry long
腿的孤立保证金和贴近 1.50x 的目标 gross。

本 trial 不再扫 core8、funding lookback、腿数、权重或 allocation。它只检验一个预先声明的
风险包：

```text
long_buffer: 0.50 -> 0.60
target gross: 1.50 -> 1.45
hard gross: 1.50 (unchanged)
allocation: 0.25 (only the highest-risk LS81 allocation)
```

风险臂和基线臂使用完全相同的 LS57 base、carry schedule、成本、funding 和 mark/fill 数据，
因此差异只来自上述风险包。

## 1. 冻结构造

- 核心币与 LS81 相同：BTC/ETH/SOL/XRP/BNB/DOGE/ADA/AVAX；
- PIT funding：Binance 8h settlements，严格 `index < D`；
- 7D rebalance，2 low long + 2 high short，每腿 0.25x NAV，sleeve 原始 gross 1.0x；
- base book 已持有的资产从 carry 候选中剔除，避免隐藏净额化；
- Bitget mark availability/3D、market fill、missing mark carry 3h 与 LS81 相同；
- 不扫描 long buffer（60% 固定）、target gross（1.45 固定）、allocation（25% 固定）或止损。

## 2. 预注册验收

1. 风险臂 20bps normal 的 full multiple 和 Sharpe 高于同一 60%/1.45x 基线臂；
2. validation（2024-01-01 → 2026-09-20）multiple 和 Sharpe 高于同一基线臂；
3. 风险臂 0 次强平、0 gross breach、max observed gross <=1.50x；
4. mark carry 最长不超过 3h；
5. 50bps、100bps 和 3x two-sided adverse funding 作为必报压力带，不能只看 20bps；
6. 如果风险包消除了强平但收益优势消失，标记为风险修正成功/alpha 失败，不晋级；
7. 若风险臂仍出现强平或 gross breach，终止该 carry 家族，不再通过调 60%/1.45 或 allocation 救结果。

## 3. 复现

```bash
.venv/bin/python scripts/run_ls81_core_major_funding_carry.py \
  --warmup-start 2021-01-01 --start-date 2022-01-01 --end-date 2026-09-21 \
  --costs-bps 20 --allocations 0.25 --funding-scenarios normal \
  --long-buffer 0.60 --target-gross 1.45 \
  --output-dir reports/ls82_core8_carry_risk_2026
```
