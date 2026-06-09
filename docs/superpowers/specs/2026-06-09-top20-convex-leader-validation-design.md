# Top20 Convex Leader Validation Design

## Goal

Build a focused Atlas20 research pack that can both validate the current
high-convexity Top20 champion and discover better candidates under realistic
liquidity, cost, and overfitting controls.

The goal is not to prove that one historical run is good. The goal is to find
strategy families that can plausibly support small-capital, high-convexity
real use: strong upside, Top20 liquidity, bounded ruin risk, and measurable
resistance to overfitting.

This remains research software only. Atlas20 does not provide financial advice
and does not execute trades.

## Current Context

Atlas20 already has most of the required infrastructure:

- Point-in-time Top20 universe construction with stablecoin, wrapped asset,
  history, price, and dollar-volume filters.
- A long-only pandas backtest engine with daily returns, equity, drawdown,
  turnover, holdings, sector exposure, and friction support.
- Existing momentum, sector, benchmark, regime, and BTC stop overlays.
- A concentrated `momentum_lead` strategy that produced the current best local
  high-convexity result.
- Profit-max refinement scripts and generated reports under
  `reports/*/profit_max_refine/`.
- Strategy Lab and report APIs that can later expose ranked research outputs.

The current local champion is useful but not sufficient:

- It achieved about `237x` over the 2022-11-21 to 2026-04-21 window.
- It used a Top1 leader, 14-day rebalance, loose liquidity, BTC initial
  exposure, BTC parking, and an 11-day BTC trailing stop with 2-day
  confirmation.
- It may be structurally good, but it may also depend on start date, parameter
  selection, or a narrow market regime.

## Research Evidence Behind The Direction

The design uses these research findings as constraints rather than as direct
strategy recipes:

- Crypto momentum is documented in cross-sectional crypto returns, with stronger
  evidence among larger coins than smaller coins in the NBER factor study.
- CTREND-style multi-indicator trend signals remain meaningful in larger and
  more liquid cryptocurrency subsets, not only in obscure assets.
- Risk-managed crypto momentum studies show that raw momentum can have severe
  tail events, while volatility or trend risk management can improve realized
  payoff profiles.
- Deflated Sharpe and backtest overfitting research imply that trial count,
  parameter search width, non-normal returns, and repeated holdout use must be
  tracked explicitly.
- Crypto execution research implies that Top20 liquidity is still not enough by
  itself; turnover, assumed bps costs, and participation-style stress must be
  visible in the output.

## Product Scope

Add one research script and one reusable strategy scoring module.

Primary entry point:

- `scripts/run_top20_convex_validation.py`

Primary report directory:

- `reports/<window>/top20_convex_validation/`

Primary new module:

- `src/atlas20/strategies/convex_leader.py`

The pack should produce ranked candidate strategies, diagnostic validation
tables, and a markdown report. It should not change the default Atlas20
baseline pipeline until a candidate is validated.

## Non-Goals

This first slice intentionally excludes:

- Live trading or exchange integration.
- Leverage.
- Top100 or illiquid small-cap expansion.
- Black-box machine learning.
- Bayesian, genetic, or reinforcement-learning search.
- A full frontend redesign.
- Any claim that a historical 100x result guarantees future performance.

## Core Design

The research pack has two lanes:

1. **Champion validation lane**
   - Tests whether the existing 237x-style result survives ablations, stricter
     liquidity, different rebalancing cadences, different risk-off assets, and
     different start dates.

2. **Candidate discovery lane**
   - Searches for better Top20 high-convexity candidates inside a constrained,
     predeclared strategy family.
   - The search is deliberately narrow enough to reduce overfitting risk, but
     broad enough to discover stronger combinations than the current champion.

Both lanes share the same validation and reporting system.

## Strategy Families

### 1. Leader Momentum

This is the transparent baseline built from existing `momentum_lead` behavior.

Parameters:

- `top_n`: 1, 2, 3
- `rebalance`: 7D, 14D, 21D, 28D
- score variants:
  - base
  - short acceleration
  - breakout
  - balanced
- universe liquidity:
  - loose: 30 history days, 1M minimum daily dollar volume
  - medium: 60 history days, 10M minimum daily dollar volume
  - strict: 90 history days, 25M minimum daily dollar volume

Purpose:

- Keep a clean bridge from the current champion to the new validation pack.
- Identify whether the useful edge is concentration, rebalance cadence,
  parking, stop behavior, or a specific score weighting.

### 2. CTREND-Lite Leader

This is the main discovery lane. It adds broader trend-quality information
without becoming a black-box model.

Candidate score components:

- Short momentum: 7, 14, 21, and 28-day trailing returns.
- Medium trend confirmation: 42 and 60-day trailing returns.
- Relative strength: performance versus BTC and ETH.
- Breakout quality: distance to 90-day high.
- Volume confirmation: recent dollar-volume expansion versus trailing average.
- Overheat penalty: very high short-term volatility or extreme one-window moves.

The score is rank-based within the point-in-time eligible Top20 universe.
Rank-based scoring keeps the method robust to crypto return scale changes and
keeps outputs explainable.

Initial score families:

- `ctrend_lite_balanced`
- `ctrend_lite_acceleration`
- `ctrend_lite_breakout`
- `ctrend_lite_relative_strength`
- `ctrend_lite_vol_adjusted`

Purpose:

- Discover candidates that are better than current momentum-lead variants.
- Test whether volume, relative strength, and volatility-aware trend quality
  improve upside or reduce false leaders.

### 3. Champion Ablation

This lane treats the current champion as a hypothesis to dissect.

Required ablations:

- Remove BTC parking.
- Replace BTC parking with cash.
- Replace BTC parking with ETH.
- Remove BTC stop overlay.
- Change stop lookback from 11D to 10D, 12D, 13D, 14D, and 15D.
- Change confirmation from 1 to 3 days.
- Change Top1 to Top2 and Top3.
- Change 14D rebalance to 7D, 21D, and 28D.
- Tighten liquidity from loose to medium and strict.
- Exclude BTC from the leader pool and compare with including BTC.

Purpose:

- Separate durable structure from accidental parameter fit.
- Identify which components create upside and which components control drawdown.

## Risk Overlay Matrix

Risk overlays are part of the strategy family, not an afterthought.

Initial variants:

- No extra stop.
- BTC trailing price stop:
  - lookback: 10, 11, 12, 13, 14, 15 days
  - confirmation: 1, 2, 3 days
- BTC moving average filter:
  - 50, 100, 120, 200 days
  - confirmation: 1, 2, 3 days
- Risk-off target:
  - cash
  - BTC
  - ETH
- Initial target before first valid leader signal:
  - cash
  - BTC
  - ETH

The first implementation should avoid combinatorial explosion by using curated
overlay sets:

- `champion_like`
- `btc_fast_stop`
- `btc_medium_stop`
- `btc_ma_defensive`
- `no_stop_control`

## Discovery Guardrails

The discovery lane must avoid uncontrolled parameter mining.

Rules:

- Every candidate gets a `family_id`.
- Every parameter combination is written to the output.
- The script records an estimated independent trial count.
- Search spaces are declared in code before execution.
- Ranking must support both raw performance and robustness-adjusted score.
- A candidate can be marked as a "winner" only if it survives the validation
  gates below.

## Validation Gates

### 1. Rolling Start Validation

For each candidate:

- Run from monthly start dates where enough history exists.
- Run from quarterly start dates for a lower-noise view.
- Record total multiple, CAGR, max drawdown, Sharpe, Calmar, and turnover.

Required outputs:

- `rolling_start_summary.csv`
- `rolling_start_by_candidate.csv`

### 2. Rolling 3-Year And 5-Year Windows

For each candidate:

- Compute rolling 3-year and 5-year compounded returns.
- Track windows that reach or exceed `100x`.
- Track max drawdown inside each window.

Required outputs:

- `rolling_window_summary.csv`
- `hundred_x_windows.csv`

### 3. Parameter Neighborhood Stability

For each top candidate:

- Compare nearby `top_n`, rebalance cadence, stop lookback, confirmation, and
  score family variants.
- Mark candidates as fragile if only one isolated parameter point works.

Required output:

- `stability_surface.csv`

### 4. Cost Stress

For each top candidate:

- Re-run at total transaction cost levels:
  - 20 bps
  - 50 bps
  - 100 bps
  - 150 bps

Required output:

- `cost_sensitivity.csv`

### 5. Liquidity Stress

For each top candidate:

- Compare loose, medium, and strict universe filters.
- Record turnover and estimated annual traded notional per dollar of capital.

Required output:

- Included in `candidate_summary.csv` and `liquidity_sensitivity.csv`.

### 6. Concentration And Dependency Check

For each top candidate:

- Record top contributing coins.
- Record percentage of final profit from the top 1, top 3, and top 5 selected
  coins.
- Record whether a candidate depends on one calendar period.

Required output:

- `contribution_summary.csv`

## Ranking Design

The pack should output two rankings.

### Raw Convexity Ranking

This ranks candidates by upside first.

Suggested score:

- 45% full-window log multiple
- 25% rolling 5-year best-window log multiple
- 15% rolling 5-year 100x hit rate
- 15% drawdown penalty

Purpose:

- Find the highest-upside candidates.

### Robust Convexity Ranking

This ranks candidates by useful real-world survivability.

Suggested score:

- 30% median rolling-start log multiple
- 20% rolling 5-year 100x hit rate
- 20% max drawdown penalty
- 15% cost-stress survival
- 10% parameter-neighborhood stability
- 5% turnover penalty

Purpose:

- Find the candidates most worth optimizing next.

The report should show both rankings side by side. A candidate that is first by
raw convexity but fails robustness should be labeled as speculative, not as the
primary research winner.

## Output Files

The script writes:

- `candidate_summary.csv`
- `candidate_top50_raw.csv`
- `candidate_top50_robust.csv`
- `champion_ablation.csv`
- `rolling_start_summary.csv`
- `rolling_start_by_candidate.csv`
- `rolling_window_summary.csv`
- `hundred_x_windows.csv`
- `stability_surface.csv`
- `cost_sensitivity.csv`
- `liquidity_sensitivity.csv`
- `contribution_summary.csv`
- `trial_log.csv`
- `top20_convex_validation_report.md`

The markdown report includes:

- Executive summary.
- Best raw convexity candidate.
- Best robust convexity candidate.
- Current champion validation result.
- Candidates that achieved 100x in any 5-year window.
- Candidates rejected for fragility or overfitting risk.
- Recommended next research step.

## Data Flow

1. Load the selected research config.
2. Build processed datasets through the existing pipeline functions.
3. Prepare market data.
4. Build required universe variants.
5. Build regime and risk overlay series.
6. Generate candidate definitions from predeclared strategy families.
7. Run full-window backtests.
8. Rank candidates by raw convexity and robust convexity.
9. Select a bounded top subset for expensive validations.
10. Run rolling start, rolling window, cost, liquidity, stability, and
    contribution diagnostics.
11. Write CSV outputs and markdown report.

## Performance Controls

To keep runtime practical:

- Run full-window screening for all candidates.
- Run expensive validations only for:
  - the existing champion
  - top 25 raw-convexity candidates
  - top 25 robust-convexity candidates
  - any candidate with a full-window multiple above a configurable threshold
- Deduplicate candidates that overlap across those groups.

Initial defaults:

- `max_validation_candidates`: 60
- `min_multiple_for_validation`: 25x
- `max_full_screen_candidates`: no hard limit in code, but the declared matrix
  should target fewer than 2,500 full-window runs in the first implementation.

## Error Handling

- Missing BTC or ETH price data should fail fast with a clear message.
- Empty universe snapshots should be recorded and skipped, not silently treated
  as successful trades.
- A candidate with no selected assets should be marked invalid.
- Report writing should create directories if needed and fail with the exact
  output path on write errors.
- If no candidate passes validation, the report should state that directly and
  still write all diagnostic tables.

## Testing

Unit tests:

- CTREND-lite scoring handles missing returns, volume gaps, and empty universe
  inputs.
- Rank-based scoring is deterministic.
- Overheat penalty reduces scores for extreme short-window volatility.
- Candidate definition generation is deterministic and bounded.
- Ranking functions order candidates correctly and handle missing metrics.

Integration tests:

- A tiny synthetic panel can run through the validation script.
- Output CSV files are created with expected columns.
- Champion ablation rows include required variants.
- Cost stress changes friction assumptions without mutating the base config.
- Rolling start validation produces multiple start dates when data permits.

Regression checks:

- Existing `momentum_lead` behavior remains unchanged.
- Existing `run_profit_max_refine.py` remains available.
- Existing report generation and API tests are not affected.

## Acceptance Criteria

The implementation is complete when:

- `scripts/run_top20_convex_validation.py` can run against the bear-bottom config.
- The pack writes the required CSV files and markdown report.
- The report identifies:
  - current champion status
  - best raw-convexity candidate
  - best robust-convexity candidate
  - candidates with any 5-year 100x window
  - candidates rejected for fragility
- Every candidate has a parameter record and family id.
- Cost, liquidity, rolling start, rolling window, and stability diagnostics are
  present for the validation subset.
- Existing tests pass, and new focused tests cover candidate scoring, ranking,
  and script output shape.

## Recommended Next Step After This Spec

Create an implementation plan that starts with reusable scoring and candidate
definition code, then builds the script, then adds diagnostics and tests. The
first implementation should prioritize correctness and reproducibility over
large search size.
