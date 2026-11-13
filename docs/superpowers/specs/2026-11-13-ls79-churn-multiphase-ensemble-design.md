# Atlas20 研究预注册：LS57 + 可执行多相位 churn ensemble

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 候选 ID | `PR2026-11-LS79-LS57-CHURN-MULTIPHASE-ENSEMBLE` |
| 基线 | LS57 20bps 68.8077x / Sharpe 1.9819 / MDD -39.84% |
| Sleeve | LS72 已注册的全部 12 个 `m ∈ {3,7,14} × h ∈ {7,14,28,56}` cell |
| 信号门 | LS73 `alt_rel_60`，所有 cell 相同 |
| 执行 | 空 alt 永续 + 多 BTC 现货；可执行性同 LS78 |
| 窗口 | 2022-01-01 → 2026-09-20 |
| 成本 | 20 / 50 / 100bps 每边 |
| 分配 | 10% / 20% / 25% residual gross |
| Gross | LS57 + sleeve 合计硬上限 1.50x |

## 0. 研究问题

LS74/LS78 只使用 discovery 排名第一的 `m=7/h=28`。这既继承了单 cell 的选参风险，也受到事件
稀疏和持有相位集中影响。LS79 不重新选 cell，而是把 LS72 已注册的全部 12 个 `m/h` cell
等权组合：

- 每个 cell 先生成自己的 gated target，并按 LS74 的 active-day gross=1 规则归一；
- 每个 cell 都只能使用 LS78 的可执行 alt 永续空头币池；
- 组合权重 = 当日所有 active cell 的归一权重之和 / active cell 数；
- 因此 ensemble 的总 gross 始终 <=1，不增加杠杆，也不在 validation 上挑选 cell。

这不是“把 12 个回测拼在一起”的收益相加；成本、funding、gross 和 residual scale 都在合成后的
权重上重新计算，避免重复占用同一 gross。

## 1. Funding

沿用 LS78：

- Binance / Bybit / Bitget 可用的逐日 funding settlement；
- normal：跨 venue 取最小日结算和（对 short 最不利）；
- adverse：逐日 settlement 绝对值求和，跨 venue 取最大，再乘 1/2/3；
- 只对 alt perp short 腿收费，BTC spot 腿不收费；
- 覆盖率 <95% 只能判 partial。

## 2. 预注册验收

最大可晋级 allocation 必须同时满足：

- 20bps normal：full 终值 > 68.8077x、Sharpe >1.9819、MDD 不差于 -40.84%；
- 20bps normal：validation 终值 >15.2386x 且 Sharpe >2.1079；
- 20bps normal：最大 combined gross <=1.50x、funding coverage >=95%；
- 同一 allocation 在 20bps + 1x adverse 下仍满足上述 full、validation、Sharpe、MDD 和 gross 门槛；
- 50bps normal 仍跑赢 LS57，作为成本压力闭合。

100bps、2x/3x adverse 全部报告但不作为本轮晋级阈值；任何一项失败都阻止 promotion，不阻止
继续研究。通过只进入真实 Bitget mark/fill/funding 引擎和 shadow，不接实盘。

## 3. 失败后动作

若 ensemble 不能优于单 cell，则说明多相位平均只是稀释收益，停止该家族，不再扫描 active-cell
数量、cell 权重、m/h 或 allocation。若仅 2x/3x adverse 失败，则保留为 conditional sleeve，
下一步研究真实 Bitget margin/liquidation 和 venue routing，不调阈值。

## 4. 复现

```bash
.venv/bin/python scripts/run_ls57_churn_multiphase_ensemble.py \
  --start-date 2022-01-01 --end-date 2026-09-20 \
  --output-dir reports/ls57_churn_multiphase_ensemble_2026
```
