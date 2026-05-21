# Atlas20 Rotation

Atlas20 Rotation is a reproducible crypto research framework for testing
whether rotation inside a top-20 non-stablecoin universe can outperform simple
benchmarks such as BTC buy-and-hold and top-20 equal weight.

The repository now includes both the Python research engine and a desktop-first
Atlas20 Research Console built with FastAPI and React/Vite.

> Research only. This project is not financial advice and does not execute
> trades.

## What Is Included

- Point-in-time top-20 universe construction from public cached data.
- Momentum, sector, and benchmark strategy backtests.
- Bull-regime and BTC trailing-stop risk overlays.
- Report generation with CSV and PNG artifacts.
- FastAPI read/write API for the research console.
- React/Vite web console for champion review and constrained reruns.
- Python, API, and frontend tests plus GitHub Actions CI.

## Repository Layout

```text
.
|-- apps/web/                 # React/Vite research console
|-- config/                   # Research windows and sector mappings
|-- data/                     # Cached raw and processed public data
|-- docs/                     # Design docs and implementation plans
|-- reports/                  # Included research output snapshots
|-- scripts/                  # Data, research, API, and verification commands
|-- src/atlas20/              # Python package
|-- tests/                    # Python tests
|-- pyproject.toml
`-- README.md
```

## Core Design

- Market cap is used for universe selection only.
- Portfolio construction is not market-cap weighted.
- Strategies allocate by momentum, sector strength, and risk-regime logic.
- The universe is rebuilt point in time at every rebalance date.
- Data assumptions are explicit and documented in generated reports.

## Data Stack

- CoinGecko: candidate universe snapshots, market cap snapshot, metadata.
- CryptoCompare: long daily price and dollar-volume history.
- Historical market-cap proxy:
  `current_market_cap * historical_price / latest_historical_price`.

This keeps the project public-data friendly and reproducible. The trade-off is
that long-history market-cap ranks are approximations, not perfect historical
constituent data.

## Install

Python:

```bash
python -m pip install -e ".[dev]"
```

> **Editable (`-e`) is required for local development.** A non-editable
> `pip install .` copies the package into `site-packages`, and on the
> default Python `sys.path` that copy will shadow the repo's `src/` tree —
> edits to `src/atlas20/**.py` then have no runtime effect even though
> `pytest` still passes (pytest is configured with `pythonpath=["src"]`).
> If you previously ran `pip install .` without `-e`, remove the stale
> copy with `python -m pip uninstall -y atlas20-rotation` before
> reinstalling.

Frontend:

```bash
npm --prefix apps/web install
```

## 30-Minute Quickstart

1. Seed the local database once with `python -m atlas20.api.seed`.
2. Start the API with `make dev`.
3. Start the frontend with `npm --prefix apps/web run dev`.
4. In another terminal, start the worker with
   `python -m atlas20.api.worker.main`.
5. For Docker, launch the API, worker, and web containers with
   `docker compose up -d --build`,
   then seed the mounted data volume with
   `docker compose exec backend python -m atlas20.api.seed`.
6. Check the API probe at `http://127.0.0.1:8000/healthz`.
7. Open the web console and confirm the seeded runs and reports are visible.

## Research Commands

Download and cache raw data:

```bash
python scripts/download_data.py --config config/base.yaml
```

Build processed datasets:

```bash
python scripts/build_datasets.py --config config/base.yaml
```

Run the full research pipeline:

```bash
python scripts/run_research.py --config config/base.yaml
```

Use `--refresh-raw` when you intentionally want to refresh public API data:

```bash
python scripts/run_research.py --config config/base.yaml --refresh-raw
```

## Web Console

Start the API:

```bash
python scripts/run_api.py
```

Start the frontend:

```bash
npm --prefix apps/web run dev
```

Open the Vite URL printed by the dev server. In development, `/api` is proxied
to `http://127.0.0.1:8000`.

## Verification

Run everything required before publishing:

```bash
python scripts/verify_release.py
```

Individual checks:

```bash
pytest -q
npm --prefix apps/web test
npm --prefix apps/web run build
```

## Main Output Files

The end-to-end pipeline writes research artifacts to `reports/latest/`:

- `atlas20_report.md`
- `strategy_summary.csv`
- `turnover_summary.csv`
- `yearly_returns.csv`
- `regime_performance.csv`
- `daily_returns.csv`
- `equity_curves.csv`
- `drawdowns.csv`
- `equity_curves.png`
- `drawdowns.png`
- `rolling_12m_returns.png`
- `sector_exposure_<best_sector_strategy>.csv`
- `sector_exposure_<best_sector_strategy>.png`

Generated console reruns are written to `reports/app_runs/` and are ignored by
Git except for the directory placeholder.

## Current Included Snapshot

Using the cached public-data run included in this workspace:

- Best momentum variant: `TOP20_MOM_top8_biweekly__bull_only`
- Best sector variant: `TOP20_SECTOR_top3_biweekly__bull_only`
- BTC buy-and-hold CAGR: about 16.8%
- Top-20 equal-weight CAGR: about -5.0%
- Best momentum CAGR: about 8.1%
- Best sector CAGR: about -0.4%

See `reports/latest/atlas20_report.md` and the dated report folders for full
interpretation and caveats.

## Key Limitations

1. Long-history market caps are proxied because free public APIs do not reliably
   expose complete point-in-time daily market-cap history.
2. Candidate coverage reduces survivorship bias but is not perfectly
   survivorship-free.
3. Sector labels use human-editable mappings and manual overrides.
4. Included results depend on cached data snapshots and should be rerun before
   making new research claims.

## License

MIT. See `LICENSE`.
