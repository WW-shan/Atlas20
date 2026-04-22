# Atlas20 Rotation

Atlas20 Rotation is a production-style crypto research framework for testing whether **rotation inside the top-20 non-stablecoin universe** can outperform simple benchmarks such as BTC buy-and-hold and top-20 equal weight.

## Core design

- **Market cap is only used for universe selection.**
- **Portfolio construction is never market-cap weighted.**
- Strategies allocate using equal weight after **momentum**, **sector strength**, and **bull-regime** logic.
- The universe is rebuilt **point in time** at every rebalance date.

## Implemented strategies

### Benchmarks
- BTC buy-and-hold
- ETH buy-and-hold
- Top-20 non-stablecoin equal weight

### Rotation strategies
- Top-20 momentum rotation
  - top 4 / 6 / 8 holdings
  - monthly and biweekly rebalancing
  - always-on and bull-only overlays
- Top-20 sector rotation
  - top 2 / 3 / 4 sectors
  - strongest 1-2 coins per sector
  - monthly and biweekly rebalancing
  - always-on and bull-only overlays

## Data design

Default data stack:

- **CoinGecko**: current candidate universe snapshot, current market cap snapshot, basic coin metadata
- **CryptoCompare**: long daily price and dollar-volume history
- **Historical market cap proxy**: `current_market_cap * historical_price / latest_historical_price`

This keeps the project fully public-data and reproducible, while avoiding a fixed historical top-20 list. The trade-off is that long-history market-cap ranks are an approximation rather than a perfect point-in-time series.

## Key assumptions and limitations

1. Long-history market caps are proxied because free public APIs do not reliably expose point-in-time daily market-cap history for the full sample.
2. Sector labels are driven by a human-editable YAML mapping, current metadata, and manual overrides.
3. Candidate coverage is **reduced survivorship bias**, not perfect survivorship-free coverage: the framework uses current large caps plus a curated legacy list.
4. Bull filter is evaluated on rebalance dates in the default implementation.

## Folder structure

```text
Atlas20/
?? config/
?  ?? base.yaml
?  ?? sectors.yaml
?? data/
?  ?? raw/
?  ?? processed/
?? reports/
?  ?? latest/
?? scripts/
?? src/atlas20/
?? tests/
```

## Installation

```bash
python -m pip install -e .
```

If you prefer not to install the package, the scripts also add `src/` to `sys.path` automatically.

## Main commands

### 1) Download and cache raw data

```bash
python scripts/download_data.py --config config/base.yaml
```

### 2) Build processed datasets

```bash
python scripts/build_datasets.py --config config/base.yaml
```

### 3) Run the full research pipeline

```bash
python scripts/run_research.py --config config/base.yaml
```

By default this now uses the existing raw cache so the research run stays fast. To refresh API data first:

```bash
python scripts/run_research.py --config config/base.yaml --refresh-raw
```

### 4) Run unit tests

```bash
pytest
```

## Main output files

The end-to-end pipeline writes to `reports/latest/`:

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

Processed datasets are written to `data/processed/`:

- `panel_daily.csv`
- `metadata.csv`
- `data_quality.csv`
- `rebalance_universe.csv`
- `regime_frame.csv`

Raw screening diagnostics are also written to `data/raw/coingecko/candidate_screen_log.csv`.

## Current default research result snapshot

Using the cached public-data run included in this workspace:

- Best momentum variant: `TOP20_MOM_top8_biweekly__bull_only`
- Best sector variant: `TOP20_SECTOR_top3_biweekly__bull_only`
- BTC buy-and-hold CAGR: about **16.8%**
- Top-20 equal-weight CAGR: about **-5.0%**
- Best momentum CAGR: about **8.1%**
- Best sector CAGR: about **-0.4%**
- Bull-only overlays improved average Sharpe versus always-on variants in this sample

See `reports/latest/atlas20_report.md` for the full interpretation and caveats.

## Research questions answered by the report

1. Does top-20 momentum rotation outperform BTC buy-and-hold?
2. Does sector rotation outperform top-20 equal weight?
3. Does the bull filter improve risk-adjusted returns?
4. Is sector rotation complexity justified?
5. What are the main practical risks and data limitations?

## Next recommended improvements

- Replace market-cap proxies with a commercial or archived point-in-time dataset.
- Add exchange-level liquidity and listing filters.
- Add statistical significance checks and cost sensitivity analysis.
- Add more robust stablecoin / tokenized-fund exclusion logic.
- Add time-aware sector mappings for rebrands and protocol evolution.
