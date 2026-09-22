# Agent Instructions

## Strategy Research Constraints

- The research, backtest, and live strategy universe must be strictly **point-in-time Top 20 by market cap**.
- Never expand candidate selection to Top 50, Top 100, or any broader universe, including "sensitivity" experiments. If a hypothesis requires a broader universe, reject it or reformulate it inside Top 20.
- Top 20 membership must be reconstructed from point-in-time market-cap data. Never backfill historical membership using the current Top 20.
- Long-only spot only: no shorting, no leverage, and gross exposure must not exceed 1.0.
- Signals are generated at close and executed T+1; backtests must include trading costs.

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
