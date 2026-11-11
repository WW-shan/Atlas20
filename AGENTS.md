# Agent Instructions

## Strategy Research Constraints

### Current stage and scope

- Atlas20 evolves through research and trading stages. Rules used by one stage describe that stage; they are not permanent prohibitions on later stages.
- The earlier spot long-only strategy is a previous stage, not the current live default.
- The current live track is **`PR2026-10-D-L125-V2`** on Bitget USDT-M: the frozen H5 long book with a **1.25x target notional exposure**, isolated margin, a **50% per-leg long buffer**, and the venue configured at **2x isolated leverage** to implement that exposure and buffer. The target book can be empty, in which case the live plan is 100% cash.
- Current live execution is T+1 at approximately **01:05 UTC**, with the runbook's data-freshness, preflight, reconciliation and idempotency gates. Authoritative runtime details live in `scripts/plan_live_execution.py`, `scripts/execute_live_plan.py`, and `docs/operations/derivatives_live_runbook.md`; runtime code/state wins over this summary.
- Research may also cover spot or derivatives, long-only or long-short portfolios, leverage or isolated margin, and single-venue or multi-venue execution when the track specification says so. Research and live execution must stay clearly separated by track name, specification and reporting.

### Objective and acceptance

- The current primary research objective is at least **20x total return** from **2022-01-01** through the latest fully verified data while materially outperforming BTC buy-and-hold with acceptable risk.
- The objective is a research target, not a substitute for validation. Each candidate or track must declare its acceptance criteria before evaluation: benchmark, return target, drawdown/risk tolerance, leverage and gross limits, capacity, execution assumptions and required out-of-sample evidence.
- Use the owner's real operating standards for those acceptance criteria. Do not add universal gates that the owner has not requested, and do not relax a declared criterion after seeing the result merely to make a candidate pass.

### Data and universe

- Every backtest must state its universe and membership method. When market-cap ranks are used, reconstruct them point in time and do not backfill membership with a current ranking.
- CoinMarketCap remains the authoritative source for market-cap ranking unless a track explicitly documents another ranking source.
- Assets without valid point-in-time data are ineligible for that track. Newly listed or newly included assets use only their available history and actual inclusion date.
- Missing, stale, duplicate or corrupt data must be detected and reported. Never silently fill missing returns with zero or stale prices.

### Portfolio and execution

- Each track specification must state instrument type (spot or derivative), direction (long-only or long-short), target gross and notional exposure, venue leverage, margin mode and buffer, execution schedule, fill model, fees, slippage and funding treatment where applicable.
- No strategy form is excluded merely because it was not used in the previous stage. Shorting, derivatives, leverage and isolated margin are valid research and live candidates when their risk and execution model is explicitly defined and verified.
- A track is not live-ready until its specification, implementation, risk controls, reconciliation, failure handling and operational runbook have been verified. Live promotion requires explicit owner approval.
- Signals, fills and defensive assets are defined by the track. T+1 execution and cash-only defence are current live conventions, not universal requirements.

### Validation and evidence

- Register each serious trial before running it and record every trial, variant, failure and rejected hypothesis.
- Validate data quality, execution feasibility and accounting independently from the alpha result.
- Stress-test costs and fills at levels appropriate to the venue and instrument, including fees, slippage, funding and financing where applicable.
- Use parameter-neighborhood, start-date, regime and rolling-window checks where relevant to the claim. Use genuinely out-of-sample or walk-forward evidence appropriate to the number of trials already examined.
- Use a multiple-testing or selection-bias correction appropriate to the number of trials, or an equivalent predeclared out-of-sample acceptance protocol.
- Do not call a track robust if its result depends on one narrow parameter, one phase, one year, one asset or a small number of trades. State remaining concentration and tail risk explicitly.
- `RESEARCH.md` is the authoritative research record. Supersede stale conclusions explicitly instead of leaving contradictory active claims.
- Commit and push after each substantive research milestone. Run the relevant tests, lint and type checks before claiming a code change is complete.

## Python Environment

- Do not install Python dependencies into the system interpreter.
- Use the project virtual environment at `.venv` for every Python command in this repository.
- Bootstrap it with `make setup`, or run the equivalent commands:

```bash
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"
```

- Prefer the Makefile targets because they call `.venv/bin/python` directly:
  `make test`, `make lint`, `make typecheck`, `make dev`, and `make openapi`.
- If a one-off isolated check is needed before `.venv` exists, use
  `UV_CACHE_DIR=/tmp/atlas20-uv-cache uv run --isolated --with-editable ".[dev]" ...`
  instead of global `pip`.
- Never commit `.venv/`; it is a local environment directory.

## Frontend

- Keep frontend dependencies under `apps/web/node_modules` via
  `npm --prefix apps/web ci`.
- Use the existing `npm --prefix apps/web ...` scripts for tests, typecheck,
  build, lint, and development server commands.
