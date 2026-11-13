# Atlas20 预注册：BTC/ETH 跨所 spot-perp basis 研究

| 项目 | 内容 |
|---|---|
| 日期 | 2026-11-13 |
| 状态 | 已预注册；research-only；不接实盘 |
| Trial ID | `PR2026-11-LS98-CROSS-VENUE-BASIS` |
| 资产 | BTC、ETH |
| 结构 | long spot + short perp；每资产 spot/perp 各 0.50x NAV，总 gross 1.00x |
| 数据 | CMC/Binance spot 日价格（研究代理）；Bitget perp mark；Binance funding proxy |
| 成本 | 每腿每边 5/10/20bps；主档 10bps，20bps 为压力 |
| 窗口 | 2022-01-01 → 2026-09-20 |

## 0. 研究问题

前一轮 carry 家族失败于单资产/单年份集中，而不是 funding 机制本身完全无效。真正市场中性的
carry 需要 spot long + perp short；Bitget-only 合约账户不能复制这一点。本 trial 只做研究代理：
如果未来有第二个账户/spot 腿，BTC/ETH 的跨所 basis 是否能提供低回撤、正 funding 的独立 sleeve？

这不是把 LS82 的 alt carry 换个名字。它只交易 BTC/ETH，使用 spot-perp 两腿，不依赖横截面
alt funding 排序，也不加杠杆。

## 1. 冻结构造

- 每资产：spot long 0.50x NAV，perp short 0.50x NAV；两资产等权，总 gross 1.00x；
- perp short 的保证金按 50% 计，组合现金保留 0.25x；不使用额外杠杆；
- PnL 逐日按 `0.5*(spot_return - perp_mark_return) + 0.5*funding` 计；
- funding 为正时 short perp 收取，为负时支付；spot 腿不计 funding；
- 成本在每个 rebalance 的 spot/perp 两腿按 per-leg bps 计，主档 10bps/腿/边，20bps 压力；
- 两个预注册变体：`always-on` 和 `positive-funding`（每资产 trailing 7D funding sum >0 才持有，
  每周 rebalance；不扫描 lookback/threshold）。

## 2. 评估标准

1. full 和 validation（2024-01-01→2026-09-20）在 10bps 与 20bps 下均为正终值；
2. 20bps full Sharpe > 1.0，MDD 不差于 -5%；
3. 逐年不能只依赖单一年份；至少 4/5 年为正，且 BTC-only、ETH-only、equal-weight 都不能由单一
   资产解释；
4. funding 和 basis 分开报告；如果收益主要来自 spot/perp 价格方向而不是 funding/basis 收敛，
   标记为 directional，不晋级；
5. 通过后只做 LS57 的 residual-gross 集成研究，不直接把该 sleeve 当 live。

## 3. 数据限制

CMC spot 日价格不是可直接成交的 Bitget spot tape；Bitget perp mark 与 Binance funding 是
跨所代理。该 trial 只能证明机制是否值得继续，不能证明真实跨所成交、保证金、借币、转账或
USDT/USD 基差。任何 live 研究都必须换成同 venue 的真实 spot/perp/mark/funding 数据。

## 4. 复现

```bash
.venv/bin/python scripts/run_ls98_cross_venue_basis.py \
  --output-dir reports/ls98_cross_venue_basis_2026
```
