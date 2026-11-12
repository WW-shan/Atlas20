# LS42 Shadow OOS 2026-11-12

- window: 2026-09-22 → 2026-11-11 (51 daily rows / 50 metric returns)
- cost: 20bps; mark source: Bitget; raw: `oos_refresh_20261112`; warmup: `merged_20261009`
- research only: yes; live execution: no

| funding | strategy | multiple | Sharpe | MDD | Δ vs L125 | Δ vs LS23 | trim | redistributed | cash |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| zero | L125 | 0.9484x | -0.2743 | -17.4670% | +0.0000x | +0.0000x | 0 | 0.0000 | 0.0000 |
| zero | LS23 | 0.9403x | -0.5584 | -17.4712% | -0.0081x | +0.0000x | 8 | 0.0000 | 0.0000 |
| zero | LS42 | 0.9220x | -0.7874 | -17.4712% | -0.0263x | -0.0183x | 8 | 0.7148 | 0.9365 |
| exact | L125 | 0.9440x | -0.3270 | -17.6505% | +0.0000x | +0.0000x | 0 | 0.0000 | 0.0000 |
| exact | LS23 | 0.9365x | -0.6125 | -17.6547% | -0.0074x | +0.0000x | 8 | 0.0000 | 0.0000 |
| exact | LS42 | 0.9183x | -0.8405 | -17.6547% | -0.0257x | -0.0182x | 8 | 0.7148 | 0.9365 |

LS42 在两条 funding 口径下都落后 LS23；窗口 BTC 在 200D 上方，短端没有开仓。
51/365 天仅覆盖 12 个月 OOS 的 14.0%，因此 LS42 只能保持 provisional。

Research output only; not an order or a live approval.
