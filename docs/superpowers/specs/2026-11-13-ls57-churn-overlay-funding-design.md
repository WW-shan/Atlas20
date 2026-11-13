# Atlas20 研究预注册：LS57 + residual-gross churn overlay（含 funding proxy）

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 候选 ID | `PR2026-11-LS76-LS57-CHURN-RESIDUAL-GROSS-FUNDING` |
| 基线 | `PR2026-11-LS75-LS57-CHURN-RESIDUAL-GROSS` 的 return-space gross-budget 结果 |
| 数据 | LS57 已含 Binance funding proxy；LS74 sleeve 增加逐资产 Binance 8h funding |
| 窗口 | 2022-01-01 → 2026-09-20 |
| 硬 gross | 1.50x |
| 成本 | 20bps 每边；sleeve funding 只做 proxy，不声称 Bitget exact |

## 0. 研究问题

LS75 在不加总 gross 的情况下把 LS57 从 68.8077x 提高到约 **81.26x / Sharpe 2.054 /
MDD -36.59%**（25% allocation），但 sleeve 未计 funding。由于 sleeve 是“空 churn 资产 + 多
BTC”的 market-neutral book，funding 可能从正收益变成负收益，必须单独检验。

## 1. 冻结规则

- 沿用 LS75 的 10%/20%/25% NAV allocation 和 `1.50x - LS57_target_gross` residual 规则；
- sleeve funding 使用 `data/raw/binance_funding/<coin>.csv` 的 `last_funding_rate`，按 UTC
  日聚合 8h settlement；缺失资产/日期按 skip 处理并报告覆盖率，不向零收益静默填充；
- long weight 支付正 funding，short weight 收取正 funding；
- LS57 自身仍使用已有 funding proxy 结果，不重复计；
- 只做 return-space funding diagnostic，不重算 Bitget mark/fill 或强平。

## 2. 验收

每个 allocation 必须同时满足：

- LS75 全部门槛；
- funding-adjusted full 终值 > LS57 68.8077x；
- funding-adjusted full Sharpe >1.9819、MDD 不差于 -40.84%；
- validation 终值和 Sharpe 高于同窗口 LS57；
- funding 覆盖率、缺失事件数和净 funding 贡献必须报告；覆盖率低于 90% 只能判 partial。

选择满足门槛的最大 allocation；若 25% 通过，不继续加到 30% 或更高。即便通过，也只进入真实
Bitget funding/mark/fill 引擎，不直接接实盘。

## 3. 复现

```bash
.venv/bin/python scripts/run_ls57_churn_overlay_funding.py \
  --start-date 2022-01-01 --end-date 2026-09-20 \
  --output-dir reports/ls57_churn_overlay_funding_2026
```
