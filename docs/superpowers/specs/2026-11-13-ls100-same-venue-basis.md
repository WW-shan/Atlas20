# Atlas20 预注册：Bitget 同 venue spot-perp basis

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；research-only；不接实盘 |
| Trial ID | `PR2026-11-LS100-SAME-VENUE-BASIS` |
| 资产 | BTC、ETH |
| 结构 | Bitget spot long + Bitget USDT-M perp short；每资产各 0.50x NAV，总 gross 1.00x |
| 样本 | 2022-01-02 → 2026-09-20（spot/perp 同 venue 日收盘） |
| 成本 | 每腿每边 10bps 主档，20bps 压力档 |
| Funding | 全样本 Binance 8h funding proxy；2026-07-11 起用 Bitget 精确 funding 做子样本校验 |

## 0. 研究问题

LS98 的 basis sleeve 结论受跨所 spot 价格和 Binance funding proxy 影响。本 trial 只把 spot 价格
换成 Bitget 同 venue 的 UTC 日线 `1Dutc`，把 perp 价格换成 Bitget mark；不扫描资产、不改
0.50x/0.50x 结构、不改持有方向、不加入 funding filter、不使用杠杆。目标是判断同 venue 价格
后，LS98 的 funding-dominated basis 结论是否仍成立，以及历史上不可得的精确 Bitget funding
是否会造成方向或量级上的致命偏差。

## 1. 冻结数据与对齐

- Spot：Bitget 公共 `GET /api/v2/spot/market/history-candles`，`granularity=1Dutc`，抓取
  `BTCUSDT`/`ETHUSDT`；本地保存原始快照、SHA-256、行数、起止日期和缺口审计。
- Perp：本地 Bitget `merged_20261009` mark 1h；每天取 23:00 UTC 小时线收盘，并在 00:00 UTC
  日界对齐。若 23:00 缺失，只允许使用 00:00 前最多 2h 的最近 mark；记录 staleness，不能静默
  forward-fill。超过 2h 的缺失日剔除并报告，覆盖率必须 >=95%。
- Spot 日线 open_time 为 UTC 日初，close 是当日 23:59:59；组合索引使用下一日 00:00，避免
  把当日未结束价格用于当日收益。
- Funding proxy：Binance `calc_time` 的 00/08/16 三个 settlement 按日求和；必须每天恰好 3 条，
  否则报错。Funding 索引与同一日 spot/perp 收盘对齐。
- Funding exact：Bitget `funding/{bitcoin,ethereum}.csv`，仅在最近完整 settlement 窗口做校验；
  feed 从 2026-07-11 08:00 起，前两天不是完整 3 次 settlement，因此实际校验从 2026-07-13
  开始；不把最近数据回填进历史。
- 缺失、重复、非有限价格或 funding 必须记录；不允许用零收益填补价格缺口。

## 2. 收益与成本

每个资产：

```text
basis_pnl = 0.50 * (spot_return - perp_return)
funding_pnl = 0.50 * daily_funding_sum
net_return = basis_pnl + funding_pnl - spot_turnover_cost - perp_turnover_cost
```

- 初始建仓和最终退出都计入 turnover；always-on 只建仓一次、退出一次，但日收益重新对齐时
  必须显式处理最后的退出成本。
- 主成本为每腿每边 10bps；20bps 为压力档。成本按每个资产腿的 notional 计算，不使用 portfolio
  级免费再平衡。
- 不把 funding 当价格收益；basis 和 funding 分开报告。

## 3. 预注册变体与门槛

正式主变体只有 `always-on BTC+ETH equal weight`。`BTC-only` 和 `ETH-only` 只作为归因诊断，
不作为可挑选的新配置。判定标准在看结果前冻结为：

1. 10bps 和 20bps 的 full、validation（2024-01-01 → 2026-09-20）终值都为正；
2. 10bps full Sharpe > 1.0，MDD 不差于 -5%；
3. 5 个日历年至少 4 年净收益为正；
4. BTC-only 和 ETH-only 都为正，且单资产或单年净 PnL 不超过总净 PnL 的 70%；
5. funding 与 basis 分开后，不能是纯方向性 basis；若 funding 不占主导必须标
   `basis-dominated` 或 `inconclusive`，不能晋级；
6. 精确 Bitget funding 子样本与 proxy 的 funding 方向一致；若符号相反或子样本 funding
   差异超过 50%，标记 `funding-proxy-mismatch`，不晋级；
7. mark staleness、spot 缺口和逐日覆盖满足第 1 节；否则只能给 `partial`，不能给 `pass`。

所有门槛同时满足才记为 `pass`；任何一条失败不通过调参、换资产或重设成本救结果。

## 4. 与实盘的关系

即使 pass 也只是研究代理升级：完整历史的 Bitget funding 仍不可得，真实 spot 成交、跨账户
保证金、借币、转账、USDT/USD 和 funding settlement 仍未闭合。LS100 不改变
`PR2026-10-D-L125-V2`，不发送订单。若 pass，下一步才允许做 LS101：把 LS100 的 sleeve
按 LS99 相同的 residual-gross 规则并入 LS57，并重新过 LS57 的 full/validation/stress 门槛。

## 5. 复现

```bash
.venv/bin/python scripts/fetch_bitget_spot_daily.py \
  --output-dir data/raw/bitget_spot/20261113 \
  --start 2021-08-01 --end 2026-09-20

.venv/bin/python scripts/run_ls100_same_venue_basis.py \
  --output-dir reports/ls100_same_venue_basis_2026
```
