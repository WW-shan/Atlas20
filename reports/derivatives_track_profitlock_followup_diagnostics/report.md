# Profit-lock follow-up diagnostics (2022-01-01 → 2026-09-21)

These are exploratory diagnostics run after LS57. They are **not** promotion trials:
the variants below were evaluated with the same 20bps, T+1 +3h, Bitget mark,
Binance funding-proxy/skip and hard-gross engine, but the target schedules were
patched in a research script rather than promoted through a new frozen runner.
The LS45 and LS57 rows are the reproducible reference runs from their formal
candidate reports.

| variant | multiple | Sharpe | MDD | status |
|---|---:|---:|---:|---|
| LS45 baseline | **69.2088x** | 1.9846 | -39.835% | formal baseline |
| LS57 baseline | 68.8077x | 1.9819 | -39.835% | formal baseline |
| BTC fallback when BTC > MA200 | 68.0224x | 1.9715 | -40.023% | rejected |
| BTC fallback when BTC > MA100 | 64.5174x | 1.9489 | -40.023% | rejected |
| Deep-7D full exit (-5%) | 67.5924x | 1.9759 | -39.056% | rejected |
| Deep-7D full exit (-8%) | 67.8148x | 1.9767 | -39.835% | rejected |
| Deep-7D full exit (-10%) | 68.3776x | 1.9802 | -39.835% | rejected |
| Shallow-7D skip (-10%) | 69.8013x | 1.9881 | -39.835% | post-hoc diagnostic |

## What was tested

1. **BTC fallback**: after an LS45 trim, put the otherwise-cash residual into
   BTC when BTC is above its 100D or 200D moving average. This was intended to
   reduce cash drag in bull markets. It lowered the terminal multiple and
   Sharpe in both cases; the MA100 and always-on versions were identical.
2. **Deep-7D full exit**: after the LS45 half-trim, fully exit the leader when
   its 7D return is below a deep threshold. This reduced some drawdown at -5%
   but gave up more return; the best deep variant (-10%) still stayed below
   LS45.
3. **Shallow-7D skip**: LS57 skips only when the last day is non-negative.
   Adding `7D >= -10%` trimmed the 2024 SHIB event that LS57 skipped, producing
   a small in-sample improvement. This was found after scanning thresholds and
   the changed event is outside the current 2026 OOS window; it is therefore
   **post-hoc, not independent evidence**.
4. **Post-skip MA21 stop**: no actionable stop target was created before the
   next scheduled H5 event in the tested paths, so the result was a null
   diagnostic and is not a separate candidate.

## Verdict

The only positive number, shallow-7D skip, is a post-hoc in-sample improvement
with no new OOS observation. It does not replace LS57 or LS45 and does not
justify a live change. The BTC fallback and deep-exit families are rejected.
The next useful work is execution quality (maker-first fills) and accumulation
of independent OOS, not another scan of the same profit-lock thresholds.
