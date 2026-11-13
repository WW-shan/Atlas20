# Atlas20 预注册：LS57 + BTC/ETH basis residual-gross 集成

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；research-only；不接实盘 |
| Trial ID | `PR2026-11-LS99-LS57-BASIS-RESIDUAL` |
| 基线 | LS57 @20bps：68.8077x / Sharpe 1.9819 / MDD -39.835% |
| Sleeve | LS98 always-on BTC+ETH long spot / short perp，10bps/腿/边主档，20bps 压力 |
| 集成 | 只在 LS57 的 residual gross 内使用；25/50/100% residual 三档 |
| Gross cap | 1.45x（hard 1.50x 不触碰） |
| 窗口 | 2022-01-01 → 2026-09-20 |

## 0. 研究问题

LS98 给出一个与 LS57 日收益相关性约 0.01、Sharpe >2、MDD <3% 的 BTC/ETH basis sleeve。本 trial
只检验它能否在不降低 LS57 收益的情况下，用 residual gross 提高组合收益和 Sharpe。不是重新
选 basis 资产、不是改 funding filter、不是提高 gross cap。

## 1. 冻结规则

- LS57 日收益、target gross 和所有交易规则不变；
- basis sleeve 固定 BTC/ETH 各 0.50x spot + 0.50x perp，gross 1.00x；
- `scale = min(1, allocation * max(1.45 - LS57_gross, 0) / 1.00)`；
- 组合 gross = LS57_gross + scale * 1.00，必须 <=1.45；
- basis return 已含 10bps/腿/边成本；scale 变化按 10bps 额外计成本；20bps 档为压力；
- 不扫描 1.30/1.40/1.50 gross cap，不扫描 30/40/60/80% allocation。

## 2. 评估标准

1. 100% residual 在 basis 10bps 下 full multiple >= LS57，Sharpe > LS57，MDD 不差于 LS57 -1pp；
2. validation（2024-01-01→2026-09-20）multiple 和 Sharpe 不低于 LS57；
3. 25/50/100% 三档全部报告；如果只有 100% 通过，仍标记为 gross-budget candidate；
4. basis 20bps 压力下 100% residual 仍不能低于 LS57 的 terminal/Sharpe；
5. 通过后只做同 venue spot/perp、真实 funding、保证金和小单执行研究，不直接改 live。

## 3. 复现

```bash
.venv/bin/python scripts/run_ls99_ls57_basis_residual.py \
  --output-dir reports/ls99_ls57_basis_residual_2026
```
