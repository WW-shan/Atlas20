# Atlas20 Execution Latency Operations

How to shorten the gap between the 00:00 UTC signal close and the live fill, and
why that is the one remaining compliant lever on the frozen champion.

## Goal and expected gain

The frozen champion is filled about **three hours** after the close. Moving the
fill to about **one hour** after the close recovers roughly 1.7x of terminal
wealth at 20 bps, with no rule change, no new parameter and no new trial.

| Fill (worse missing-candle policy) | 2 bps | 20 bps | 50 bps | 100 bps |
| --- | ---: | ---: | ---: | ---: |
| At the signal close (lag 0) | 28.80x | 23.09x | 15.97x | 8.62x |
| **+1h** | **26.48x** | **21.22x** | **14.66x** | **7.90x** |
| +3h (current live timing) | 24.42x | 19.56x | 13.50x | 7.27x |

Source: `reports/phase_momentum_execution_lag_2022/fill_timing.csv`. The +3h
figure is the `--fill-hours 3` run that already backs `RESEARCH.md` section 00.1.

**Why this is compliant.** Signals are still generated at the 00:00 UTC close
and executed afterwards. Intraday data is used only to time the fill, which the
task brief allows. `docs/research/literature_review_2026-09.md` section 4 (H1)
records this as the compliant alternative to the 23:00-decision variant that
needs the owner's sign-off.

**What it does not fix.** The Deflated Sharpe (0.731) and PBO (0.526) gates fail
on the selection history, not on execution. Only data no trial has seen can move
them. This work is operational; the champion stays provisional either way.

## The current chain

| UTC | What happens | Where |
| --- | --- | --- |
| 00:00 | Day D-1 closes; CMC starts writing D-1 rows asset by asset | provider |
| 02:30 | `daily_universe_refresh` job runs (deployment; `.env.example` default is 02:00) | `src/atlas20/api/scheduler.py`, `ATLAS20_DAILY_REFRESH_HOUR_UTC/MINUTE_UTC` |
| ~02:30-03:00 | `download_and_cache_raw_data` pulls each coin's CMC tail, cross-checks, rebuilds `data/processed/panel_daily.csv` | `src/atlas20/data/processor.py` |
| after that | `scripts/run_phase_momentum_live_signal.py` writes the target snapshot | manual today |
| ~03:00 | order fills; the backtest models this as +3h | `reports/phase_momentum_execution_lag_2022/` |
| 06:30 | conditional catch-up refresh | `daily_refresh_catchup_offset_hours` |

## The real bottleneck

It is **CoinMarketCap's publication latency**, not our job time. CMC writes day
D-1 row by row, and the panel refuses to append a day until
`data_quality.min_daily_coverage` (0.9) of live assets carry it
(`_panel_end` in `src/atlas20/data/processor.py`). `src/atlas20/api/settings.py`
already records that CMC "is sometimes still writing it when the first job
runs" at 02:00. Until that curve is measured we cannot claim +1h is reachable.

## Step 0 - Measure the publication curve (gate; do this first)

Run `scripts/probe_cmc_publication.py` every 10-15 minutes from about 00:05 UTC
to 03:00 UTC for 7-10 days. Each run spends one CMC request per sampled asset
(default 20, the largest cached candidates) and appends one row.

```bash
.venv/bin/python scripts/probe_cmc_publication.py \
  --sample-size 20 --output reports/provider_publication/cmc_publication_probe.csv
```

`--from-cache` reads the cache instead of spending requests; use it only as a
sanity check, because a cache read reflects the last refresh, not the provider.

Example crontab entry (probe at :05, :20, :35, :50 every hour):

```cron
5,20,35,50 0-3 * * * cd /path/to/Atlas20 && .venv/bin/python scripts/probe_cmc_publication.py >> reports/provider_publication/probe.log 2>&1
```

**Decision rule.** Let `T90` be the earliest UTC time by which >=90% of the
sample carries D-1 on >=90% of days (the P90 across days):

| `T90` | Action |
| --- | --- |
| `<= 00:30` | refresh at `T90 + 10 min`; fill at **+1h** (01:00) |
| `00:30 < T90 <= 01:30` | fill at **+2h** (02:00); refresh at `T90 + 10 min` |
| `> 01:30` | keep the current +3h chain and record why |

Do not move the schedule before this measurement exists; a refresh that runs
too early appends nothing (the coverage gate holds the panel end) and only
produces a wasted run and a PARTIAL-day warning.

## Step 1 - Move the refresh (only after Step 0 passes)

- Set `ATLAS20_DAILY_REFRESH_HOUR_UTC` / `ATLAS20_DAILY_REFRESH_MINUTE_UTC` to
  `T90 + 10 min` in the deployment environment (see `.env.example`).
- Keep the catch-up job (`ATLAS20_DAILY_REFRESH_CATCHUP_OFFSET_HOURS`) as the
  retry for days CMC is late.
- Re-check `ATLAS20_DAILY_REFRESH_GRACE_MINUTES` and
  `data_freshness_max_primary_lag_days`: both are written for the 02:00
  schedule and must still describe the new one.
- Optional hardening: gate the job on the probe's coverage so a refresh is not
  queued before CMC has the day. Without it the existing freshness guard
  (`scripts/run_phase_momentum_live_signal.py`) still refuses to trade a stale
  or partial last day, which is the safe failure mode.

## Step 2 - Move the fill

- Schedule `scripts/run_phase_momentum_live_signal.py` to finish before the
  target fill hour, then place the order so the fill lands at the intended time.
- Record which missing-candle case actually occurred each day (the live analogue
  of `observed_weight_share` in `fill_timing.csv`): 91.8% of the historical fill
  weight had an observed hourly candle, and the backtest decides on the worse of
  the `day_close` / `prior_close` policies.
- Keep the audit's hourly source identical to the venue that would print the
  live fill (`data-api.binance.vision` 1h candles, see
  `src/atlas20/data/binance.py`).

## Step 3 - Audit (required)

The review states the compliant alternative "needs only an audit that the live
data reproduce the historical daily snapshot". Concretely, for every new day:

1. Re-run `.venv/bin/python scripts/audit_data_chain.py --config config/base.yaml`
   and require `FAIL=0`. This already checks freshness, the finished-last-day
   volume/market-cap floors, and that no live asset dropped out of the newest
   dates.
2. Compare the live-built D-1 rows with a fresh CMC re-fetch for the same date;
   a mismatch is a provider revision, not something to smooth over.
3. Re-run `.venv/bin/python scripts/run_phase_momentum_oos.py` so the frozen
   specification keeps accumulating genuine out-of-sample days.

## Rollback

Only the refresh hour and the order timing change. Reverting
`ATLAS20_DAILY_REFRESH_HOUR_UTC`/`MINUTE_UTC` and the order schedule restores the
current +3h chain; no strategy, universe, cost or execution-rule state moves.

## Record

After the measurement, record `T90` (median and P90 across days), the chosen
fill hour and the resulting OOS tracking numbers in `RESEARCH.md` as a new
section, and supersede this document's decision table if the numbers disagree.
