"""Download orchestration and processed dataset builders.

Data chain (single source of truth):

* CoinGecko - candidate universe (current top-N plus a legacy watchlist),
  coin metadata, and the fallback second-source price check for assets Gate.io
  does not list.
* CoinMarketCap - daily price, dollar volume, market cap and circulating
  supply for every asset in the panel.
* Gate.io - preferred independent exchange-venue price check for every listed
  asset.
* CoinPaprika - fallback adjudication when neither the second source nor
  CoinGecko can provide the tie-break vote. No validator ever rewrites a panel
  value.

CoinMarketCap is the only historical provider. Because price, volume and
market cap come from one snapshot, the price/market-cap ratio is internally
consistent and the point-in-time Top-N ranks are built from real supply data
instead of a price-scaled proxy.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from atlas20.config import ResearchConfig, SectorConfig
from atlas20.data.catalog import asset_is_excluded, deduplicate_assets, metadata_is_excluded
from atlas20.data.coingecko import CoinGeckoClient
from atlas20.data.coinmarketcap import CoinMarketCapClient
from atlas20.data.coinpaprika import CoinPaprikaClient
from atlas20.data.crosscheck import adjudicate_daily_prices, compare_daily_prices
from atlas20.data.gateio import GateIOClient
from atlas20.data.validation import summarize_market_history
from atlas20.logging_utils import ensure_dir, get_logger
from atlas20.sectors.mapping import resolve_sector_map

LOGGER = get_logger(__name__)


CANDIDATE_ASSETS_FILE = "candidate_assets.json"


def _candidate_assets_path(config: ResearchConfig) -> Path:
    return config.resolve_path(config.paths.raw_dir) / "coingecko" / CANDIDATE_ASSETS_FILE


def _history_window(config: ResearchConfig) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return the [start, end] range that must be cached.

    The window starts well before the backtest so universe eligibility
    (history/volume floors) can already be satisfied on the first rebalance
    date; the panel is trimmed back to the needed buffer afterwards.
    """
    start = pd.Timestamp(config.providers.coinmarketcap.history_start)
    return start, config.end_timestamp


def download_and_cache_raw_data(
    config: ResearchConfig,
    force: bool = False,
    refresh_catalog: bool = True,
) -> pd.DataFrame:
    """Fetch the candidate catalog, metadata, and CMC histories into the cache.

    ``refresh_catalog`` re-reads the current Top-N listing and the CMC id map so
    a coin that just entered the top ranks is discovered on this run. It costs
    two requests. ``force`` additionally re-downloads every coin's full price
    history; without it, an already-covered coin triggers no request at all and
    a merely stale one pulls only its tail.
    """
    raw_dir = ensure_dir(config.resolve_path(config.paths.raw_dir))
    coingecko = CoinGeckoClient(config.providers.coingecko, raw_dir)
    cmc = CoinMarketCapClient(config.providers.coinmarketcap, raw_dir)
    gateio = GateIOClient(config.providers.gateio, raw_dir)
    coinpaprika = CoinPaprikaClient(config.providers.coinpaprika, raw_dir)

    LOGGER.info("Fetching current top-%s candidate assets from CoinGecko", config.universe.current_top_n_candidates)
    current_top = coingecko.fetch_top_markets(
        config.universe.current_top_n_candidates, force=force or refresh_catalog
    ).to_dict(orient="records")
    legacy = coingecko.fetch_markets_by_ids(config.universe.legacy_candidate_ids, force=force).to_dict(orient="records")
    candidates = deduplicate_assets([*current_top, *legacy])
    filtered_candidates = [asset for asset in candidates if not asset_is_excluded(asset, config.universe)]

    LOGGER.info("Fetching CoinMarketCap symbol->id map")
    id_map = cmc.fetch_id_map(force=force or refresh_catalog)
    # Curated aliases win: they cover tickers CMC no longer lists.
    id_map = {**id_map, **{k.upper(): int(v) for k, v in config.universe.cmc_symbol_aliases.items()}}

    # Refresh CoinPaprika's catalog at most once per run, and only if a
    # disputed asset actually needs it.  Resolving each disagreement against a
    # stale list would miss a new coin; refreshing eagerly would waste a 7.5 MB
    # request on every normal run.
    coinpaprika_catalog_ready: bool | None = None

    start, end = _history_window(config)

    valid_assets: list[dict] = []
    screening_rows: list[dict] = []
    total_candidates = len(filtered_candidates)
    for index, asset in enumerate(filtered_candidates, start=1):
        coin_id = str(asset["id"])
        symbol = str(asset["symbol"]).upper()
        name = str(asset.get("name", coin_id))
        status = "accepted"
        details = ""
        metadata_payload: dict | None = None

        LOGGER.info("Screening asset %s/%s: %s (%s)", index, total_candidates, coin_id, symbol)

        try:
            metadata_payload = coingecko.fetch_coin_metadata(coin_id, force=force)
        except Exception as exc:  # noqa: BLE001
            details = f"metadata_missing: {exc}"
            if config.data_quality.require_metadata:
                screening_rows.append({"coin_id": coin_id, "symbol": symbol, "name": name, "status": "excluded", "details": details})
                LOGGER.warning("Skipping %s (%s) because metadata is required: %s", coin_id, symbol, exc)
                continue
            LOGGER.warning("Metadata unavailable for %s (%s): %s", coin_id, symbol, exc)

        if metadata_payload and metadata_is_excluded(metadata_payload, config.universe):
            screening_rows.append(
                {"coin_id": coin_id, "symbol": symbol, "name": name, "status": "excluded", "details": "metadata_exclusion_rules"}
            )
            LOGGER.info("Excluded %s (%s) using metadata filters", coin_id, symbol)
            continue

        cmc_id = id_map.get(symbol)
        if cmc_id is None:
            screening_rows.append(
                {"coin_id": coin_id, "symbol": symbol, "name": name, "status": "excluded", "details": "no_coinmarketcap_id"}
            )
            LOGGER.warning("Skipping %s (%s): no CoinMarketCap id for symbol", coin_id, symbol)
            continue

        try:
            history = cmc.ensure_history(cmc_id, start=start.date(), end=end.date(), force=force)
        except Exception as exc:  # noqa: BLE001
            screening_rows.append(
                {"coin_id": coin_id, "symbol": symbol, "name": name, "status": "excluded", "details": f"coinmarketcap_history: {exc}"}
            )
            LOGGER.warning("CoinMarketCap unavailable for %s (%s): %s", coin_id, symbol, exc)
            continue

        if history.empty:
            screening_rows.append(
                {"coin_id": coin_id, "symbol": symbol, "name": name, "status": "excluded", "details": "coinmarketcap_history_empty"}
            )
            LOGGER.warning("Skipping %s (%s): CoinMarketCap returned no usable history", coin_id, symbol)
            continue

        enriched_asset = {**asset, "cmc_id": int(cmc_id)}

        # Gate.io is the preferred second source.  Unlike CoinGecko's free
        # public API, its daily candles have a generous request budget and
        # cover delisted assets, so a full 100-asset refresh does not stall on
        # 429s.  CoinGecko remains the second source only for Gate-unlisted
        # assets.
        secondary = pd.DataFrame()
        secondary_column = "cg_price"
        secondary_source = "coingecko"
        gate_frame = pd.DataFrame()
        try:
            gate_frame = gateio.fetch_daily_candles(symbol, force=force)
        except Exception as exc:  # noqa: BLE001
            details = f"{details} | gateio_history_missing: {exc}".lstrip(" |")
            LOGGER.warning("Gate.io history unavailable for %s (%s): %s", coin_id, symbol, exc)

        if not gate_frame.empty:
            enriched_asset["gateio_pair"] = gateio.resolve_pair(symbol)
            secondary = gate_frame
            secondary_column = "gate_price"
            secondary_source = "gateio"
        else:
            try:
                secondary = coingecko.fetch_daily_market_chart(
                    coin_id, config.data_quality.cross_check_recent_days, force=force
                )
            except Exception as exc:  # noqa: BLE001
                details = f"{details} | crosscheck_chart_missing: {exc}".lstrip(" |")
                LOGGER.warning("Validation chart unavailable for %s (%s): %s", coin_id, symbol, exc)

        secondary_result = compare_daily_prices(
            history.rename(columns={"close": "price"}),
            secondary,
            secondary_column=secondary_column,
            min_overlap_days=config.data_quality.cross_check_min_overlap_days,
            max_median_gap=config.data_quality.cross_check_max_median_gap,
            max_latest_gap=config.data_quality.cross_check_max_latest_gap,
        )

        if not secondary_result.passed:
            coingecko_chart_ready = secondary_source == "coingecko" and not secondary.empty
            if secondary_source == "gateio":
                # A Gate disagreement is rare.  Fetch CoinGecko only for that
                # adjudication, which keeps the normal refresh well below its
                # free-tier request ceiling.
                try:
                    coingecko.fetch_daily_market_chart(
                        coin_id, config.data_quality.cross_check_recent_days, force=force
                    )
                    coingecko_chart_ready = True
                except Exception as exc:  # noqa: BLE001
                    details = f"{details} | crosscheck_chart_missing: {exc}".lstrip(" |")
                    LOGGER.warning("Validation chart unavailable for %s (%s): %s", coin_id, symbol, exc)

            # CoinPaprika is the fallback when CoinGecko cannot provide the
            # tie-break vote.  It is never called for assets that already
            # passed their second-source comparison.
            if not coingecko_chart_ready and coinpaprika_catalog_ready is not False:
                if coinpaprika_catalog_ready is None:
                    try:
                        coinpaprika.fetch_coins(force=force or refresh_catalog)
                        coinpaprika_catalog_ready = True
                    except Exception as exc:  # noqa: BLE001
                        coinpaprika_catalog_ready = False
                        LOGGER.warning("CoinPaprika catalog unavailable: %s", exc)
                try:
                    pap_id = coinpaprika.resolve_coin_id(
                        coin_id=coin_id,
                        symbol=symbol,
                        name=name,
                        market_cap_rank=asset.get("market_cap_rank"),
                        force=False,
                        bypass_id_map=True,
                    )
                    if pap_id:
                        enriched_asset["coinpaprika_id"] = pap_id
                        cross_start = max(
                            end.normalize() - pd.Timedelta(days=max(config.data_quality.cross_check_recent_days - 1, 0)),
                            start.normalize(),
                        )
                        coinpaprika.fetch_daily_history(
                            pap_id,
                            start=cross_start.date(),
                            end=end.date(),
                            force=force,
                        )
                    else:
                        details = f"{details} | coinpaprika_id_missing".lstrip(" |")
                except Exception as exc:  # noqa: BLE001
                    details = f"{details} | coinpaprika_history_missing: {exc}".lstrip(" |")
                    LOGGER.warning("Third-provider history unavailable for %s (%s): %s", coin_id, symbol, exc)

        screening_rows.append({"coin_id": coin_id, "symbol": symbol, "name": name, "status": status, "details": details})
        valid_assets.append(enriched_asset)

    candidate_path = _candidate_assets_path(config)
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text(json.dumps(valid_assets, indent=2), encoding="utf-8")
    pd.DataFrame(screening_rows).to_csv(candidate_path.with_name("candidate_screen_log.csv"), index=False)
    LOGGER.info("Retained %s candidate assets with usable histories", len(valid_assets))
    return pd.DataFrame(valid_assets)


def load_candidate_assets(config: ResearchConfig) -> pd.DataFrame:
    """Load cached candidate assets."""
    path = _candidate_assets_path(config)
    if not path.exists():
        raise FileNotFoundError(f"Candidate asset cache not found: {path}")
    return pd.DataFrame(json.loads(path.read_text(encoding="utf-8")))


def _load_cmc_history(raw_dir: Path, cmc_id: int) -> pd.DataFrame | None:
    """Load a cached CoinMarketCap history and normalize it for the panel.

    CMC stores 0 (not null) for assets it tracks without supply data, e.g.
    WhiteBIT Coin. A zero market cap is missing information, not a real value:
    keeping it would rank the asset inside the Top-N and displace a genuine
    constituent.
    """
    directory = raw_dir / "coinmarketcap" / "history"
    if not directory.exists():
        return None

    frames: list[pd.DataFrame] = []
    for path in sorted(directory.glob(f"{cmc_id}_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not payload:
            continue
        rows = []
        for row in payload:
            quote = row.get("quote") or {}
            opened = row.get("timeOpen")
            if not opened:
                continue
            ts = pd.Timestamp(opened)
            ts = ts.tz_localize(None) if ts.tzinfo is not None else ts
            rows.append(
                {
                    "date": ts.normalize(),
                    "price": quote.get("close"),
                    "volume_usd": quote.get("volume"),
                    "market_cap": quote.get("marketCap"),
                    "circulating_supply": quote.get("circulatingSupply"),
                }
            )
        if rows:
            frames.append(pd.DataFrame(rows))

    if not frames:
        return None

    merged = pd.concat(frames, ignore_index=True)
    merged["market_cap"] = pd.to_numeric(merged["market_cap"], errors="coerce")
    merged.loc[merged["market_cap"] <= 0, "market_cap"] = np.nan
    merged["price"] = pd.to_numeric(merged["price"], errors="coerce")
    merged["volume_usd"] = pd.to_numeric(merged["volume_usd"], errors="coerce")
    merged = merged.dropna(subset=["price"])
    merged = merged[merged["price"] > 0]
    merged = merged.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)

    # A coin cannot hold a Top-N rank before the provider reports a circulating
    # supply, so any earlier price row is uninvestable - and it is exactly
    # where CMC's data is least reliable. TAO's first print is $0.126 against a
    # $79.79 next-week median (a 696x artificial jump) and SHIB's first print
    # is 4x its neighbours; both sit before any supply exists. Keeping those
    # rows would let a broken placeholder feed the momentum score the moment
    # the coin becomes rankable.
    first_supply = merged.loc[merged["market_cap"].notna(), "date"].min()
    if pd.notna(first_supply):
        merged = merged[merged["date"] >= first_supply]

    merged = _drop_level_corruption(merged)
    return merged.reset_index(drop=True)


def _drop_level_corruption(frame: pd.DataFrame, factor: float = 20.0) -> pd.DataFrame:
    """Remove blocks where the provider reports a wildly wrong price level.

    Huobi Token is the motivating case: CMC served ~$0.000002 instead of ~$0.5
    for 34 consecutive days in early 2025, then returned to the correct level.
    Every one of those rows is internally consistent (``market_cap == price x
    supply``), so a per-row integrity check cannot see it - only the level
    shift against the surrounding weeks gives it away.

    The test is deliberately narrow so that genuine moves survive:

    * The reference is the median of an *outer* ring (31-60 days before and
      after). A ring this far out is not contaminated by a month-long bad
      block, which an adjacent window would be.
    * Both rings must agree with each other. A trending market has a much
      lower past level than future level, so it can never be flagged - that is
      what keeps a real launch rally (PEPE's first week, a 100x run) intact.
    * Only a row that is far from *both* rings, which by construction agree,
      can be a reversion artefact.
    """
    if frame.empty:
        return frame
    ordered = frame.sort_values("date").reset_index(drop=True)
    price = ordered["price"].astype(float)

    before = price.shift(31).rolling(30, min_periods=15).median()
    after = price.shift(-61).rolling(30, min_periods=15).median()
    rings_agree = (before / after).between(1.0 / 3.0, 3.0)
    baseline = (before * after) ** 0.5
    ratio = price / baseline

    corrupted = rings_agree & ((ratio > factor) | (ratio < 1.0 / factor))
    return ordered.loc[~corrupted.fillna(False)].reset_index(drop=True)


def _load_coingecko_chart(path: Path) -> pd.DataFrame:
    """Normalize a cached CoinGecko market chart into a daily close series."""
    if not path.exists():
        return pd.DataFrame(columns=["date", "cg_price"])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return pd.DataFrame(columns=["date", "cg_price"])
    prices = payload.get("prices") or []
    if not prices:
        return pd.DataFrame(columns=["date", "cg_price"])
    return pd.DataFrame(
        {
            "date": [pd.Timestamp(row[0], unit="ms").normalize() for row in prices],
            "cg_price": [row[1] for row in prices],
        }
    )


def build_processed_datasets(config: ResearchConfig, sector_config: SectorConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Create the processed long panel and metadata tables from cached raw files."""
    raw_dir = ensure_dir(config.resolve_path(config.paths.raw_dir))
    processed_dir = ensure_dir(config.resolve_path(config.paths.processed_dir))
    candidates = load_candidate_assets(config)
    if candidates.empty:
        raise ValueError("No candidate assets available in cache")

    metadata_rows: list[dict] = []
    panel_frames: list[pd.DataFrame] = []
    quality_rows: list[dict] = []
    sector_map = resolve_sector_map(config, sector_config)
    gateio = GateIOClient(config.providers.gateio, raw_dir)
    coinpaprika = CoinPaprikaClient(config.providers.coinpaprika, raw_dir)

    for _, asset in candidates.iterrows():
        coin_id = str(asset["id"])
        symbol = str(asset["symbol"]).upper()
        name = str(asset.get("name", coin_id))

        cmc_id = asset.get("cmc_id")
        if cmc_id is None or pd.isna(cmc_id):
            LOGGER.warning("Missing CoinMarketCap id for %s (%s); skipping", coin_id, symbol)
            continue
        history = _load_cmc_history(raw_dir, int(cmc_id))
        if history is None or history.empty:
            LOGGER.warning("Missing CoinMarketCap cache for %s (%s); skipping", coin_id, symbol)
            continue

        metadata_path = raw_dir / "coingecko" / "coin_metadata" / f"{coin_id}.json"
        metadata_payload = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
        if metadata_payload and metadata_is_excluded(metadata_payload, config.universe):
            LOGGER.info("Skipping %s (%s) during processing because metadata marks it ineligible", coin_id, symbol)
            continue

        validation = summarize_market_history(
            coin_id=coin_id,
            symbol=symbol,
            name=name,
            history=history,
            quality_config=config.data_quality,
        )

        chart_path = raw_dir / "coingecko" / "market_chart" / f"{coin_id}_{config.data_quality.cross_check_recent_days}d.json"
        chart = _load_coingecko_chart(chart_path)
        gateio_pair = asset.get("gateio_pair")
        gate_frame = pd.DataFrame()
        if gateio_pair is not None and not pd.isna(gateio_pair):
            gate_frame = gateio.load_daily_candles(symbol)

        # Gate.io is the preferred second source because its public candles do
        # not carry CoinGecko's low per-IP request ceiling.  CoinGecko remains
        # the second source for assets Gate.io does not list.
        secondary_source = "gateio" if not gate_frame.empty else "coingecko"
        secondary_frame = gate_frame if not gate_frame.empty else chart
        secondary_column = "gate_price" if secondary_source == "gateio" else "cg_price"
        secondary_result = compare_daily_prices(
            validation.history,
            secondary_frame,
            secondary_column=secondary_column,
            min_overlap_days=config.data_quality.cross_check_min_overlap_days,
            max_median_gap=config.data_quality.cross_check_max_median_gap,
            max_latest_gap=config.data_quality.cross_check_max_latest_gap,
        )
        tertiary = pd.DataFrame()
        tertiary_column = "pap_price"
        tertiary_source = ""
        pap_id = asset.get("coinpaprika_id")
        if not secondary_result.passed:
            if secondary_source == "gateio" and not chart.empty:
                tertiary = chart
                tertiary_column = "cg_price"
                tertiary_source = "coingecko"
            if tertiary.empty and pap_id is not None and not pd.isna(pap_id):
                tertiary = coinpaprika.load_daily_history(str(pap_id))
                if not tertiary.empty:
                    tertiary_column = "pap_price"
                    tertiary_source = "coinpaprika"
        cross = adjudicate_daily_prices(
            validation.history,
            secondary_frame,
            tertiary,
            secondary_column=secondary_column,
            tertiary_column=tertiary_column,
            tertiary_source=tertiary_source,
            min_overlap_days=config.data_quality.cross_check_min_overlap_days,
            max_median_gap=config.data_quality.cross_check_max_median_gap,
            max_latest_gap=config.data_quality.cross_check_max_latest_gap,
        )
        # "Disagrees" and "could not be checked" are different states. A proven
        # disagreement blocks the asset; a missing second source is recorded
        # and only blocks when the operator demands verification.
        unverified = cross.reason == "unverified"
        blocked_by_cross_check = not cross.passed and (
            (not unverified) or config.data_quality.require_cross_check
        )
        admitted = validation.passed and not (
            config.data_quality.exclude_on_cross_check_failure and blocked_by_cross_check
        )
        tertiary_result = cross.tertiary
        secondary_tertiary_result = cross.secondary_vs_tertiary
        confirmed_by = cross.confirmed_by or (secondary_source if secondary_result.passed else "")
        quality_rows.append(
            validation.summary
            | {
                "metadata_available": bool(metadata_payload),
                "crosscheck_passed": cross.passed,
                "crosscheck_verified": not unverified,
                "crosscheck_reason": cross.reason,
                "crosscheck_confirmed_by": confirmed_by,
                "crosscheck_overlap_days": cross.overlap_days,
                "crosscheck_median_gap": cross.median_gap,
                "crosscheck_latest_gap": cross.latest_gap,
                "crosscheck_effective_median_gap": cross.effective_median_gap,
                "crosscheck_third_source": tertiary_source,
                "crosscheck_third_source_checked": cross.tertiary_checked,
                "crosscheck_third_source_passed": (
                    tertiary_result.passed if tertiary_result is not None else pd.NA
                ),
                "crosscheck_third_source_reason": (
                    tertiary_result.reason if tertiary_result is not None else ""
                ),
                "crosscheck_third_source_overlap_days": (
                    tertiary_result.overlap_days if tertiary_result is not None else pd.NA
                ),
                "crosscheck_third_source_median_gap": (
                    tertiary_result.median_gap if tertiary_result is not None else pd.NA
                ),
                "crosscheck_third_source_latest_gap": (
                    tertiary_result.latest_gap if tertiary_result is not None else pd.NA
                ),
                "crosscheck_secondary_tertiary_median_gap": (
                    secondary_tertiary_result.median_gap if secondary_tertiary_result is not None else pd.NA
                ),
                "crosscheck_secondary_tertiary_latest_gap": (
                    secondary_tertiary_result.latest_gap if secondary_tertiary_result is not None else pd.NA
                ),
                "included_in_panel": bool(admitted),
            }
        )
        if cross.passed and cross.confirmed_by:
            LOGGER.warning(
                "Admitted %s (%s) with %s confirming CMC; CoinGecko median gap %.2f%%",
                coin_id,
                symbol,
                cross.confirmed_by,
                (cross.median_gap or 0.0) * 100,
            )
        if not admitted:
            if validation.passed and blocked_by_cross_check:
                median_ratio = 1.0 + cross.median_gap if pd.notna(cross.median_gap) else float("nan")
                latest_ratio = 1.0 + cross.latest_gap if pd.notna(cross.latest_gap) else float("nan")
                LOGGER.warning(
                    "Excluding %s (%s): independent source disagrees (%s, median %.2fx, latest %.2fx)",
                    coin_id,
                    symbol,
                    cross.reason,
                    median_ratio,
                    latest_ratio,
                )
            else:
                LOGGER.warning(
                    "Excluding %s (%s) from the panel: %s",
                    coin_id,
                    symbol,
                    validation.summary["validation_reason"],
                )
            continue

        framed = validation.history.copy()
        # Include pre-window history so universe eligibility (history_days) can
        # be satisfied at start_timestamp. Without this, history_count begins at
        # 0 on the backtest start date and the universe builder rejects every
        # coin until min_history_days has accumulated -- which for short
        # windows means no eligible assets at any rebalance. The end of the
        # window stays fixed because no data after the backtest end is needed.
        history_buffer = pd.Timedelta(days=config.universe.min_history_days)
        data_start = config.start_timestamp - history_buffer
        framed = framed[(framed["date"] >= data_start) & (framed["date"] <= config.end_timestamp)].copy()
        if framed.empty:
            continue

        framed["coin_id"] = coin_id
        framed["symbol"] = symbol
        framed["name"] = name
        framed["price_source"] = "coinmarketcap"
        framed["volume_source"] = "coinmarketcap"
        framed["market_cap_source"] = "coinmarketcap"
        framed["current_market_cap"] = float(asset.get("market_cap") or 0.0)
        framed["current_rank"] = asset.get("market_cap_rank")
        panel_frames.append(
            framed[
                [
                    "date",
                    "coin_id",
                    "symbol",
                    "name",
                    "price",
                    "volume_usd",
                    "market_cap",
                    "price_source",
                    "volume_source",
                    "market_cap_source",
                    "current_market_cap",
                    "current_rank",
                ]
            ]
        )

        categories = metadata_payload.get("categories") or []
        metadata_rows.append(
            {
                "coin_id": coin_id,
                "symbol": symbol,
                "name": name,
                "current_price": float(asset.get("current_price") or 0.0),
                "current_market_cap": float(asset.get("market_cap") or 0.0),
                "current_volume": float(asset.get("total_volume") or 0.0),
                "current_rank": asset.get("market_cap_rank"),
                "circulating_supply": asset.get("circulating_supply"),
                "categories": " | ".join(categories),
                "category_list": categories,
                "asset_platform_id": metadata_payload.get("asset_platform_id"),
                "sector": sector_map.resolve_coin_sector(coin_id, name, categories),
                "metadata_available": bool(metadata_payload),
                "validation_passed": validation.summary["validation_passed"],
                "latest_price_gap": validation.summary["latest_price_gap"],
                "median_price_gap": validation.summary["median_price_gap"],
                "direct_market_cap_days": validation.summary["direct_market_cap_days"],
                "direct_price_days": validation.summary["direct_price_days"],
                "history_days": validation.summary["history_days"],
            }
        )

    if not panel_frames:
        raise ValueError("No processed panel rows could be built")

    panel = pd.concat(panel_frames, ignore_index=True)
    panel = panel.sort_values(["date", "market_cap"], ascending=[True, False]).reset_index(drop=True)
    metadata = pd.DataFrame(metadata_rows).drop_duplicates(subset=["coin_id"]).set_index("coin_id")
    quality = pd.DataFrame(quality_rows).drop_duplicates(subset=["coin_id"]).set_index("coin_id")

    panel.to_csv(processed_dir / "panel_daily.csv", index=False)
    metadata.to_csv(processed_dir / "metadata.csv")
    quality.to_csv(processed_dir / "data_quality.csv")

    LOGGER.info(
        "Processed dataset written: %s rows across %s assets (all market caps from CoinMarketCap)",
        len(panel),
        metadata.shape[0],
    )
    return panel, metadata
