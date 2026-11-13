# Atlas20 Execution Latency Operations

> **Historical note (2026-11-13):** the +1h fill experiment below is no longer
> the live default. The current LS45-G125 production chain keeps T+1 +3h and
> starts at 03:05 UTC; see “Current live schedule” before applying any
> historical recommendation in this document.

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
| +3h (previous live timing) | 24.42x | 19.56x | 13.50x | 7.27x |

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

## Current live schedule (2026-11-13)

The production track is now LS45-G125. It keeps the frozen T+1 +3h research
convention: the target weights come from the latest event row, while the
**daily execution timestamp** comes from the manifest's latest completed data
day plus T+1 +3h. That distinction matters because the event book can stay
unchanged for many days while the executor still reconciles and journals every
day.

| UTC | What happens | Where |
| --- | --- | --- |
| 00:00 | Day D-1 closes; CMC starts writing D-1 rows asset by asset | provider |
| 00:30 / 00:50 | early panel refresh and catch-up | `ops/com.atlas20.daily-refresh.plist`, `scripts/refresh_daily_data.py` |
| 03:05 / 03:35 / 04:35 / 06:35 | primary live chain and retries | `ops/com.atlas20.derivatives-execute.plist`, `ops/run_derivatives_daily.sh` |
| 06:30 | late panel catch-up | `scripts/refresh_daily_data.py` |

The 01:05/01:35 early-fill experiment documented below is historical. It was
superseded on 2026-11-13 and must not be used to infer the current schedule.

Before every order the wrapper now checks both the panel date and the
finished-last-day volume/market-cap coverage. If either is stale or partial it
forces a rebuild and checks again; a second failure stops before trading. At
order time, Bitget tickers supply fresh last/mark/best-bid/best-ask/size
snapshots. Stale or missing required quotes fail closed; wide spreads, large
last/mark gaps and orders larger than the visible top-of-book are surfaced in
the execution report.

## The previous chain

This table records the earlier L125 timing for comparison:

| UTC | What happens | Where |
| --- | --- | --- |
| 00:00 | Day D-1 closes; CMC starts writing D-1 rows asset by asset | provider |
| 02:30 | former panel refresh (now a fallback) | `src/atlas20/api/scheduler.py`, `ops/com.atlas20.daily-refresh.plist` |
| ~02:30-03:00 | `download_and_cache_raw_data` pulls each coin's CMC tail, cross-checks, rebuilds `data/processed/panel_daily.csv` | `src/atlas20/data/processor.py` |
| after that | `scripts/run_derivatives_oos.py` writes the frozen target snapshot | live wrapper |
| ~03:00 | former order fill; the backtest models +3h as its conservative protocol | `reports/phase_momentum_execution_lag_2022/` |
| 06:30 | conditional catch-up refresh | `daily_refresh_catchup_offset_hours` |

## The real bottleneck

It is **CoinMarketCap's publication latency**, not our job time. CMC writes day
D-1 row by row, and the panel refuses to append a day until
`data_quality.min_daily_coverage` (0.9) of live assets carry it
(`_panel_end` in `src/atlas20/data/processor.py`). `src/atlas20/api/settings.py`
already records that CMC "is sometimes still writing it when the first job
runs" at 02:00. The measured curve and the production completeness gate are
what make the earlier fill safe; without either, do not claim +1h is reachable.

## Step 0 - Measure the publication curve (gate; do this first)

Run `scripts/probe_cmc_publication.py` every 15 minutes from about 00:05 UTC to
03:50 UTC for 7-10 days. Each run spends one CMC request per sampled asset (the
launchd job samples 10, the script default is 20) and appends one row.

```bash
.venv/bin/python scripts/probe_cmc_publication.py \
  --sample-size 20 --output reports/provider_publication/cmc_publication_probe.csv
```

`--from-cache` reads the cache instead of spending requests; use it only as a
sanity check, because a cache read reflects the last refresh, not the provider.

The probe caches its CMC fetches under `data/raw/cmc_publication_probe`
(`--cache-dir`), **never** in the production `data/raw/coinmarketcap/history`.
Writing them into the shared cache advances the sampled coins' CMC history
without refreshing their Binance/Gate windows, so the next
`build_datasets.py` sees CMC one day ahead of every venue and excludes the
sampled assets - which are the largest coins - as unverified. Keep the two
caches separate.

`ops/com.atlas20.cmc-probe.plist` is the launchd job that runs this grid. It is
installed on this workstation and fires every 15 minutes from 08:05 to 11:50
local (00:05 to 03:50 UTC at UTC+8), appending to
`reports/provider_publication/cmc_publication_probe.csv` with logs in
`~/Library/Logs/atlas20-cmc-probe.log`. That CSV is a local, untracked
operational log (`reports/provider_publication/*` is gitignored, the directory
is held by `.gitkeep`), so the 15-minute job never dirties the working tree. Verify or install it the same way as the
daily refresh:

```bash
launchctl print gui/$(id -u)/com.atlas20.cmc-probe | head
cp ops/com.atlas20.cmc-probe.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.atlas20.cmc-probe.plist
launchctl kickstart -k gui/$(id -u)/com.atlas20.cmc-probe   # one-off smoke run
```

launchd reads `StartCalendarInterval` in **local** time; the checked-in hours
are UTC+8 and must be converted on any other host
(`tests/test_launchd_probe_schedule.py` pins the conversion). On a Linux host,
the equivalent crontab entry is:

```cron
5,20,35,50 0-3 * * * cd /path/to/Atlas20 && .venv/bin/python scripts/probe_cmc_publication.py --sample-size 10 --output reports/provider_publication/cmc_publication_probe.csv >> reports/provider_publication/probe.log 2>&1
```

Cost: 16 runs/day at the default 10-asset sample is 160 CoinMarketCap requests
per day, about 1.5x a normal daily refresh. Raise the sample for a sharper
coverage estimate; lower it if the provider rate-limits.

**Historical decision rule.** Let `T90` be the earliest UTC time by which >=90% of the
sample carries D-1 on >=90% of days (the P90 across days):

| `T90` | Action |
| --- | --- |
| `<= 00:30` | refresh at `T90 + 10 min`; fill at **+1h5m** (01:05) |
| `00:30 < T90 <= 01:30` | fill at **+2h** (02:00); refresh at `T90 + 10 min` |
| `> 01:30` | keep the current +3h chain and record why |

Do not move the schedule before this measurement exists; a refresh that runs
too early appends nothing (the coverage gate holds the panel end) and only
produces a wasted run and a PARTIAL-day warning.

**Measured result.** The committed operational probe (10 largest candidates,
not the full 102-asset candidate pool) has 34 target days from 2026-10-08 to
2026-11-09. On the latest 32 target days, the 10/10 sample first reached full
coverage at 00:20 UTC every day; the first two probe days were setup outliers.
This is strong enough to justify the early execution path only because the
production gate now independently checks the **actual panel's** finished-day
volume and market-cap coverage. The 10-asset sample is not a claim that all
102 candidate histories are complete at 00:20, so fallback and self-healing
remain mandatory.

## Step 1 - Move the refresh (implemented)

- The workstation `ops/com.atlas20.daily-refresh.plist` now fires at 08:30 and
  08:50 Beijing (00:30/00:50 UTC), then keeps the legacy 02:30/02:55/06:30 UTC
  fires as fallbacks.
- `scripts/refresh_daily_data.py` owns the lock and skip-if-current behavior;
  the executor wrapper owns the stronger finished-last-day check.
- The API scheduler's `ATLAS20_DAILY_REFRESH_*` environment remains a separate
  deployment path and is not silently changed by this workstation plist.

## Step 2 - Move the fill (implemented)

- **Superseded 2026-11-13:** the L125 01:05 UTC experiment was replaced by the
  LS45-G125 T+1 +3h schedule. The execute plist/timer now start at 03:05 UTC and
  retry at 03:35/04:35/06:35 UTC. The earlier 01:05 timing is historical only.
- The live executor fetches one server-timestamped Bitget ticker snapshot for
  the required symbols. Missing/stale quotes fail closed; wide spreads,
  last/mark divergence and orders larger than the visible top-of-book level are
  printed in the daily report.
- The strategy selection, target weights, 1.25x gross cap and T+1 signal rule
  are unchanged. This is an execution-latency change, not a new alpha trial.

## Step 3 - Audit (required, ongoing)

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

Only the refresh and order schedules changed. Reverting the two launchd/systemd
calendars to the old 02:30/03:05 path restores the previous +3h chain; no
strategy, universe, cost or execution-rule state moves.

## Record

After the measurement, record `T90` (median and P90 across days), the chosen
fill hour and the resulting OOS tracking numbers in `RESEARCH.md` as a new
section, and supersede this document's decision table if the numbers disagree.
