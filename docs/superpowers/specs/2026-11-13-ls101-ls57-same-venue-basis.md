# Atlas20 预注册：LS57 + LS100 同 venue basis residual-gross 集成

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；research-only；不接实盘 |
| Trial ID | `PR2026-11-LS101-LS57-SAME-VENUE-BASIS` |
| 基线 | LS57 @20bps：68.8077x / Sharpe 1.9819 / MDD -39.835% |
| Sleeve | LS100 always-on BTC+ETH，Bitget 同 venue spot/perp 日线，实际 gross 1.00x |
| 集成 | 只使用 LS57 residual gross；25/50/100% 三档 |
| Gross cap | 1.45x（hard 1.50x 不触碰） |
| 窗口 | 2022-01-01 → 2026-09-20 |

## 0. 研究问题

LS100 的 spot/perp 价格已换成 Bitget 同 venue，但 funding 仍是 Binance proxy。它给出 2022-01-02
起的 1,723 个有效日收益。本 trial 只检验 LS100 sleeve 能否在不降低 LS57 收益/Sharpe 的前提下，
使用 LS57 未占用的 gross 提高组合表现；不重新选币、不改 LS100 的 0.25x/0.25x 两腿结构、不加
杠杆、不改 funding proxy、不扫描 gross cap 或 allocation。

## 1. 冻结对齐与规则

- LS57 日收益、target gross 和全部规则不变；
- LS100 日收益取其 `daily_return`（basis+funding，未扣组合 scale 成本）；LS100 实际两腿 gross
  为 1.00x；
- LS100 样本首个完整日收益是 2022-01-02；为了让 2022-01-01 的共同样本与 LS57 对齐，LS100 在
  2022-01-01 记零收益、零 gross，表示尚未建仓；不把未来收益回填到 2022-01-01；
- `scale = min(allocation, max(1.45 - LS57_gross, 0) / 1.00)`；
- 组合 gross = LS57_gross + scale * 1.00，必须 <=1.45；
- LS100 的 scale 变化按每腿每边 10bps 计成本（初始建仓、调仓、最终退出都计入；20bps 为压力档）；
- 25/50/100% 三档固定，不新增 10/20/40/60/80% 扫描。

## 2. 评估标准

1. 100% residual 在 LS100 10bps 下 full multiple >= LS57、Sharpe > LS57、MDD 不差于 LS57 -1pp；
2. validation（2024-01-01 → 2026-09-20）multiple 和 Sharpe 不低于 LS57；
3. 25/50/100% 三档全部报告；只有 100% 通过时标为 `partial`，不能当三档稳健通过；
4. LS100 20bps 压力档下 100% residual 的 full multiple 和 Sharpe 不低于 LS57；
5. 任何时点组合 gross 不得超过 1.45x；若 LS57 自身已超过 cap，直接报错，不用负 scale 兜底；
6. 通过后才允许做同 venue 执行、funding settlement、保证金和小单研究；不直接改 live。

## 3. 数据与已知限制

LS100 的价格是同 venue，但完整历史 funding 仍是 Binance proxy；Bitget 精确 funding 只有最近
完整 settlement 窗口，不能回填 2022–2026。因此即使 LS101 pass，也只是“同 venue 价格 + funding
proxy”的研究结论，不是 live-ready。当前 live track 仍为 `PR2026-10-D-L125-V2`。

## 4. 复现

```bash
.venv/bin/python scripts/run_ls101_ls57_same_venue_basis.py \
  --output-dir reports/ls101_ls57_same_venue_basis_2026
```
