# Agent Instructions

## Strategy Research Constraints

### Objective and acceptance

- The primary research target is a strategy with **at least 20x total return** from **2022-01-01** through the latest fully verified data, while materially beating BTC buy-and-hold and keeping risk acceptable.
- High return alone is not sufficient. A strategy is **not complete, validated, or live-ready** until it passes the robustness and anti-overfitting gates below. If any gate fails, keep the strategy marked provisional and continue research.
- Never weaken, reinterpret, or remove a constraint after seeing a backtest result in order to make a strategy pass.

### Universe and data

- The research, backtest, and live strategy universe must be strictly **point-in-time Top 20 by market cap**.
- Never expand candidate selection to Top 50, Top 100, or any broader universe, including "sensitivity" experiments. If a hypothesis requires a broader universe, reject it or reformulate it inside Top 20.
- Top 20 membership must be reconstructed from point-in-time market-cap data. Never backfill historical membership using the current Top 20.
- CoinMarketCap is authoritative for market-cap ranking and membership. Gate and Binance are independent validation sources, not replacements for CMC ranking.
- An asset absent from CMC is not eligible for ranking or strategy selection. A newly entered Top 20 asset must have its complete available history aligned to its actual entry date; never use look-ahead data or assume it was in Top 20 before then.
- Missing, stale, duplicate, or corrupt market data must be detected and reported. Never silently fill missing returns with zero or stale prices.

### Portfolio and execution

- Long-only spot only: no shorting, no leverage, and gross exposure must not exceed 1.0.
- Signals are generated at close and executed T+1. Cash is the only defensive asset when no eligible position passes the rules.
- Use the verified all-in trading cost as the baseline (currently 2 bps in project runs). Every candidate must also be stress-tested at 20, 50, and 100 bps, including fees, slippage, and rebate assumptions where applicable.

### Robustness and anti-overfitting gates

- The main backtest starts on **2022-01-01** to exclude the 2021 bubble. The 2020-10 to 2021-12 period is an additional stress check, not a source of headline performance.
- Do not treat a single in-sample parameter point, start date, or calendar phase as evidence. Every serious candidate must be checked with parameter-neighborhood sensitivity, multiple start dates/phases, rolling starts, nested walk-forward or genuinely out-of-sample splits, yearly and market-regime breakdowns, removal of the best year, and one-year rolling worst-case results.
- Every serious candidate must include multiple-testing/selection-bias analysis appropriate to the number of trials, such as White's Reality Check, Deflated Sharpe Ratio, or an equivalent documented method.
- Record every trial, failed variant, and rejected hypothesis. Do not report only the winning backtest or hide parameter instability.
- A strategy cannot be called robust if its result depends on one narrow parameter value, one phase, one year, one asset, or a small number of trades.

### Research evidence and process

- Every design decision, including selection, ranking, entry, exit, stop-loss, rebalancing, and risk control, must be supported by external research or a documented within-project ablation. Do not rely on intuition or "it looks good" backtests.
- Cite the source or reproducible experiment for each decision point. When external evidence conflicts, report the conflict and test the alternatives.
- `RESEARCH.md` is the authoritative research record. Supersede stale conclusions explicitly instead of leaving conflicting numbers active.
- Commit and push after each substantive research milestone. Run the relevant tests, lint, and type checks before claiming a code change is complete.

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
