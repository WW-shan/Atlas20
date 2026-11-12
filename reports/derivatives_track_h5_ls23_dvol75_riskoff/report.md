# PR2026-11-LS58 — DVOL>75 H5 long risk-off

- status: **rejected**
- baseline: `PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE`
- main sample: 2022-01-01 → 2026-09-21 (UTC)
- funding: Binance proxy/skip; 20bps base cost; Bitget mark
- rule: when the completed signal-day Deribit BTC DVOL close is above 75, set the H5 long target to zero; all LS57 short, profit-lock, stop and gross rules stay unchanged

## Main sample

| cost | LS57 multiple | LS58 multiple | LS57 Sharpe | LS58 Sharpe | LS57 MDD | LS58 MDD |
|---:|---:|---:|---:|---:|---:|---:|
| 2bps | 93.9064x | **100.9431x** | 2.1088 | **2.1407** | -37.566% | -37.566% |
| 20bps | 68.8077x | **73.8729x** | 1.9819 | **2.0132** | -39.835% | -39.835% |
| 50bps | 40.9332x | **43.8564x** | 1.7694 | **1.7996** | -43.446% | -43.446% |
| 100bps | 17.1724x | **18.3357x** | 1.4128 | **1.4410** | -49.484% | -49.484% |

3x short-adverse funding: **73.8190x / 2.0115 / -39.951%**, 0 liquidations, 0 gross breach.
The main sample passes the pre-registered cost, funding, rolling, best-year-removal, monthly-start,
12-start, and short-concentration checks; 365D rolling worst is **0.855093x**, exactly LS57.
The expanded 23-unique-candidate PBO panel gives **0.617965** (LS57 reference: 0.609307), so the
multiple-testing procedure still fails.

## Why it is rejected

The improvement is not broad-based. The DVOL overlay changed gross on only **10 target events**:
the 2022-11-08 event had zero gross before the overlay, and the other nine events all occurred in
**March 2024**. Removing 2024 makes LS58 exactly equal to LS57 (34.3343x). The entire main-sample
gain is therefore one March-April 2024 episode, not a recurring cross-regime effect.

The independent pre-2022 proxy window is decisive:

| window | LS57 zero-funding | LS58 zero-funding | relative multiple |
|---|---:|---:|---:|
| 2021-03-24 → 2022-01-01 | **1.8872x** | 1.0738x | **-43.1%** |

The overlay triggered 79 times in that high-volatility window and repeatedly sold the H5 long book
into rebounds. Its MDD looked almost zero only because it was mostly in cash, while it gave up most
of the return. This is the same failure mode as a blunt risk-off filter: high DVOL is both a crash
state and a rebound state; DVOL level alone is not a directional exit signal.

A 51-day live OOS is not available with a trigger because DVOL remained below 75 after 2026-09-22;
the OOS path is therefore identical to LS57 and cannot validate the rule.

## Verdict

**Rejected.** No threshold scan (70/75/80/90), no half/full scale scan, no MA confirmation, and no
replacement of LS57. The useful finding is negative but actionable: BTC options DVOL level has
information about cross-sectional momentum returns, but using it as a persistent long-exit gate is
not robust. Future work should treat implied-vol shocks as a timing/execution problem or combine
them with a confirmation that distinguishes crash continuation from rebound, rather than lowering
the threshold to rescue this trial.

## Artifacts

- `dvol_risk_off_audit.csv`
- `robustness/calendar/`
- `robustness/monthly_starts_vs_l125/`
- `engine_monthly_starts/summary.csv`
- `short_attribution/short_attribution_summary.json`
- `pre2022/zero_proxy/`

Research output only; not an order or a live approval.
