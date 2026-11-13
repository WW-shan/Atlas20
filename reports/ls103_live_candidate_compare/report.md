# LS103 实盘候选选择审计

状态：研究决策审计，不是实盘批准，不发送订单。

## 结论

在统一的 H5 1.25x 底稿、总目标 gross 1.25x、Bitget mark、T+1 +3h、20bps 成本下：

- **LS45-G125 为主候选**：68.95x / Sharpe 1.982 / MDD -39.96%。
- LS57-G125 为防御性 shadow：68.55x / 1.980 / -39.96%。
- LS23-G125 为保守回退：61.68x / 1.943 / -39.96%。
- 当前 L125 为 40.22x / 1.733 / -40.65%。

LS45 和 LS57 的差异很小；LS45 在基础、100bps、funding ×1.59 和 3x long-adverse
四个场景里都略高，而且少一个 1D 事后参数。LS57 的 51 天 exact OOS 更好
（0.9685x vs LS45 0.9365x），但 1D 规则只改变了 3 次减仓，事件支持太薄，因此保留为
shadow 而不是主候选。

## 机制归因

- L125 → LS23：利润保护 + 空头路由，40.22x → 61.68x。
- LS23 → LS45：只向 21D 更强的既有 H5 持有者再分配，61.68x → 68.95x；实际只有 6 次
  再分配，且增量集中在 2024。
- LS54 的一次性 7D skip 反而使结果降至 67.01x。
- LS57 增加 1D 止跌过滤后回到 68.55x，但仍略低于 LS45。

## 过拟合与风险

- LS57 的 1D 过滤只影响 3 次真正 skip：过滤 APTOS/BCH/DOGE，保留 SHIB/XLM/HBAR。
- LS45 超出 LS23 的增益集中在 2024；若未来没有合格接收者，应预期回落至 LS23 水平。
- PBO 仍偏高（LS57 口径 0.6093），不能把主样本最高点当成确定规律。
- 2023/2024 两个年度 LS45/LS57 低于 L125；优势主要在 2022 防守和 2025/2026 趋势段。
- 真实 funding、成交、空头止损和方向翻转尚未在执行层闭合。

## 证据

`comparison.csv` 包含所有 20/100bps、funding ×1.59 和 3x long-adverse 场景。
各候选的原始 summary、daily_returns、trades、funding、gross_exposure 和行为审计均在
本目录下对应子目录中。

Spec：`docs/superpowers/specs/2026-11-13-ls103-live-candidate-selection.md`。

## 复现

所有以下命令均使用项目 `.venv`，并把输出写到 `reports/ls103_live_candidate_compare/`：

```bash
# L125 baseline
.venv/bin/python scripts/run_derivatives_backtest.py \
  --trial-id PR2026-10-D-L125 --start-date 2022-01-01 --end-date 2026-09-21 \
  --cost-bps 20 --funding-source binance-proxy --funding-missing-policy skip \
  --missing-mark-policy carry --missing-mark-max-carry-hours 3 \
  --output-dir reports/ls103_live_candidate_compare/l125_proxy_20bps

# LS45 and LS57 use the same engine with FROZEN_CONFIG['max_total_gross'] temporarily
# set to 1.25 in a research-only process; the source tree is not modified.
# See the command pattern in the LS103 spec and the `run_h5_regime_short_router.py` CLI.
```

完整逐小时曲线、持仓和资金费 ledger 体积约 95 MB，已清理；保留的 summary、
daily returns、利润保护审计和空头归因在 `evidence/`，可按上述固定参数重建。
