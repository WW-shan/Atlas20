"""Download orchestration and processed dataset builders.

Data chain (single source of truth):

* CoinGecko - candidate universe (current top-N plus a legacy watchlist),
  coin metadata, and the fallback second-source price check for assets Gate.io
  does not list.
* CoinMarketCap - daily price, dollar volume, market cap and circulating
  supply for every asset in the panel.
* Gate.io - preferred independent exchange-venue price check for every listed
  asset.
* Binance - second exchange venue (reached through its official public data
  mirror, because api.binance.com is geo-blocked here and api.binance.us is a
  far thinner book).
* CoinPaprika - fallback adjudication when neither the second source nor
  CoinGecko can provide the tie-break vote. No validator ever rewrites a panel
  value.

The download fetches CoinGecko and CoinPaprika only when they are needed as a
tie-break; the build then lets every cached source vote (see
``atlas20.data.crosscheck.adjudicate_sources``).

CoinMarketCap is the only historical provider. Because price, volume and
market cap come from one snapshot, the price/market-cap ratio is internally
consistent and the point-in-time Top-N ranks are built from real supply data
instead of a price-scaled proxy.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from atlas20.config import ResearchConfig, SectorConfig
from atlas20.data.binance import BinanceClient
from atlas20.data.cache_merge import describe_conflicts, fetch_ordered, merge_by_fetch_order
from atlas20.data.catalog import asset_is_excluded, deduplicate_assets, metadata_is_excluded
from atlas20.data.coingecko import CoinGeckoClient, daily_closes_from_market_chart
from atlas20.data.coinmarketcap import CoinMarketCapClient
from atlas20.data.coinpaprika import CoinPaprikaClient
from atlas20.data.crosscheck import UNVERIFIED_REASONS, IndependentSource, adjudicate_sources, compare_daily_prices
from atlas20.data.gateio import GateIOClient
from atlas20.data.validation import summarize_market_history
from atlas20.logging_utils import ensure_dir, get_logger
from atlas20.sectors.mapping import resolve_sector_map

LOGGER = get_logger(__name__)


CANDIDATE_ASSETS_FILE = "candidate_assets.json"

# Venue stamps from providers that have been retired.  A cached candidate row
# is the only place an old stamp can hide, because every fresh screen re-writes
# the keys for the sources that are still read; without this, a coin that left
# the current listing would keep advertising a venue whose data is gone.
# Binance.US was replaced by Binance's public data mirror (`binance_pair`).
LEGACY_CANDIDATE_KEYS = ("binanceus_pair", "cryptocompare_pair")

# A feed that has not printed for this many days is over, not late: the asset
# was delisted or migrated (MATIC stops on 2025-03-24 when the token becomes
# POL). Venue windows are anchored to its last print and the cross-check
# verifies the overlap rather than demanding coverage of a print that will
# never arrive.
ENDED_FEED_GRACE_DAYS = 7


def _last_print_date(history: pd.DataFrame) -> pd.Timestamp | None:
    """Last day an asset's provider series prints, as a naive UTC date.

    Provider caches mix tz-aware and naive timestamps, and the research window
    is naive, so every comparison normalizes first.
    """
    if history is None or history.empty:
        return None
    last = pd.Timestamp(history["date"].max())
    if last.tzinfo is not None:
        last = last.tz_convert("UTC").tz_localize(None)
    return last.normalize()


def _pre_window_buffer_days(config: ResearchConfig) -> int:
    """Days of history the panel must carry before ``start_date``.

    Every configured lookback that reads pre-window data has to be warm on
    the first backtest day: universe eligibility counts ``min_history_days``
    of prints, the regime filter uses the BTC and tracked-market-cap moving
    averages and the alt-momentum change, and the momentum score reads its
    longest trailing return. The buffer used to be ``min_history_days`` alone
    (90) while the regime averages span 120 days, so regime_frame.csv showed
    bull=False on 2021-01-01..01-29 from moving-average warm-up alone - CMC's
    BTC closed above its 120-day average on every one of those days.
    """
    lookbacks = [
        config.universe.min_history_days,
        config.regime.btc_ma_window,
        config.regime.tracked_total_mcap_ma_window,
        config.regime.tracked_alt_mcap_momentum_window,
        *config.signals.momentum_weight_map().keys(),
    ]
    return max(int(value) for value in lookbacks)


def _feed_ended(history: pd.DataFrame, end: pd.Timestamp) -> bool:
    """True when an asset's provider series has stopped for good."""
    last = _last_print_date(history)
    if last is None:
        return False
    return bool(last < pd.Timestamp(end).normalize() - pd.Timedelta(days=ENDED_FEED_GRACE_DAYS))


def _candidate_assets_path(config: ResearchConfig) -> Path:
    return config.resolve_path(config.paths.raw_dir) / "coingecko" / CANDIDATE_ASSETS_FILE


def _load_onboarded_candidates(config: ResearchConfig) -> list[dict]:
    """Every coin that has already been onboarded, keyed by CoinGecko id.

    The pool is otherwise whatever CoinGecko's *current* listing returns, so a
    coin that slips down that listing - or off it entirely - would silently
    leave the pool.  Because the panel is rebuilt from the pool on every run,
    that retroactively rewrites the point-in-time universe the backtest ran
    on: a coin that sat in the Top-20 while it was hot would simply never have
    been held.  For a momentum strategy that is the worst possible bias,
    since the hottest names are exactly the ones that blow up and slide.

    Two on-disk records are consulted because neither is complete alone:

    * ``coin_metadata/`` - one CoinGecko document per coin ever screened.  It
      outlives a candidate that was accepted and only later dropped from the
      listing, which is how an already-paid-for history is recovered.
    * ``candidate_assets.json`` - last run's accepted candidates, carrying the
      CMC id and Gate.io pair that were resolved for them.
    """
    onboarded: dict[str, dict] = {}

    metadata_dir = _candidate_assets_path(config).parent / "coin_metadata"
    if metadata_dir.exists():
        for path in sorted(metadata_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError, ValueError):
                continue
            if not isinstance(payload, dict) or not payload.get("id"):
                continue
            onboarded[str(payload["id"]).lower()] = {
                "id": payload["id"],
                "symbol": payload.get("symbol"),
                "name": payload.get("name"),
                "market_cap_rank": payload.get("market_cap_rank"),
            }

    path = _candidate_assets_path(config)
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, ValueError):
            payload = None
        if isinstance(payload, list):
            for row in payload:
                if isinstance(row, dict) and row.get("id"):
                    onboarded[str(row["id"]).lower()] = {
                        key: value for key, value in row.items() if key not in LEGACY_CANDIDATE_KEYS
                    }

    return list(onboarded.values())


def _load_cached_id_map(raw_dir: Path) -> dict[str, int] | None:
    """The cached CMC symbol -> id map, read without touching the network."""
    path = raw_dir / "coinmarketcap" / "id_map.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    mapping: dict[str, int] = {}
    for symbol, cmc_id in payload.items():
        try:
            mapping[str(symbol).upper()] = int(cmc_id)
        except (TypeError, ValueError):
            continue
    return mapping


def _check_aliases_against_id_map(id_map: dict[str, int], aliases: dict[str, int]) -> None:
    """Refuse an alias that points at an id the id map gives another symbol.

    ``CEL: 5692`` was one: the id map assigns 5692 to COMP, so Celsius and
    Compound both read Compound's history, and Celsius surfaced as a steady
    ~988x "CMC outlier" against its venues instead of as the mapping error it
    was. An alias exists for a ticker CMC no longer lists; it can never be
    right to point it at an id another live ticker owns.
    """
    owners: dict[int, list[str]] = {}
    for symbol, cmc_id in id_map.items():
        owners.setdefault(int(cmc_id), []).append(str(symbol).upper())
    problems = []
    for symbol, cmc_id in sorted(aliases.items()):
        others = sorted(owner for owner in owners.get(int(cmc_id), []) if owner != str(symbol).upper())
        if others:
            problems.append(f"{str(symbol).upper()} -> {int(cmc_id)}, which the CMC id map assigns to {', '.join(others)}")
    if problems:
        raise ValueError(
            "universe.cmc_symbol_aliases contradict the CoinMarketCap id map: "
            + "; ".join(problems)
            + ". Verify the coin's own CMC id (symbol and name) or remove the alias."
        )


def _check_unique_cmc_ids(assignments: list[tuple[str, str, int]]) -> None:
    """Refuse two candidates that resolve to the same CMC series.

    ``assignments`` holds ``(coin_id, symbol, cmc_id)``. Two coins can never
    share one provider history; if they do, one of them is being fed the
    other's prices, market caps and Top-N rank.
    """
    by_id: dict[int, list[str]] = {}
    for coin_id, symbol, cmc_id in assignments:
        by_id.setdefault(int(cmc_id), []).append(f"{coin_id} ({str(symbol).upper()})")
    shared = {cmc_id: coins for cmc_id, coins in sorted(by_id.items()) if len(coins) > 1}
    if shared:
        raise ValueError(
            "Several candidates resolve to one CoinMarketCap series: "
            + "; ".join(f"cmc_id {cmc_id}: {', '.join(coins)}" for cmc_id, coins in shared.items())
            + ". Fix universe.cmc_symbol_aliases or the id map before building."
        )


def _resolve_candidate_cmc_ids(
    candidates: pd.DataFrame,
    id_map: dict[str, int] | None,
    aliases: dict[str, int],
) -> dict[str, int | None]:
    """CMC id per candidate, resolved the way the download resolves it.

    Config aliases win over the cached id map, exactly as in
    ``download_and_cache_raw_data``, so an alias fix takes effect on the next
    build instead of waiting for a download to rewrite the candidate cache.
    Without a cached id map (a cache that predates it) the candidate's stored
    id is used as before.
    """
    resolved: dict[str, int | None] = {}
    for _, asset in candidates.iterrows():
        coin_id = str(asset["id"])
        symbol = str(asset["symbol"]).upper()
        stored = asset.get("cmc_id")
        stored_id = None if stored is None or pd.isna(stored) else int(stored)
        if id_map is None:
            resolved[coin_id] = stored_id
            continue
        cmc_id = aliases.get(symbol, id_map.get(symbol))
        if cmc_id != stored_id:
            LOGGER.warning(
                "CoinMarketCap id for %s (%s) resolves to %s under the current aliases and id map "
                "(candidate cache says %s); using the resolved id",
                coin_id,
                symbol,
                cmc_id,
                stored_id,
            )
        resolved[coin_id] = cmc_id
    return resolved


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
    binance = BinanceClient(config.providers.binance, raw_dir)
    coinpaprika = CoinPaprikaClient(config.providers.coinpaprika, raw_dir)

    LOGGER.info("Fetching current top-%s candidate assets from CoinGecko", config.universe.current_top_n_candidates)
    current_top = coingecko.fetch_top_markets(
        config.universe.current_top_n_candidates, force=force or refresh_catalog
    ).to_dict(orient="records")
    legacy = coingecko.fetch_markets_by_ids(config.universe.legacy_candidate_ids, force=force).to_dict(orient="records")
    # Onboarded coins come first so a freshly fetched row for the same coin
    # still wins deduplication against its persisted copy.
    candidates = deduplicate_assets([*_load_onboarded_candidates(config), *current_top, *legacy])
    filtered_candidates = [asset for asset in candidates if not asset_is_excluded(asset, config.universe)]

    LOGGER.info("Fetching CoinMarketCap symbol->id map")
    id_map = cmc.fetch_id_map(force=force or refresh_catalog)
    aliases = {k.upper(): int(v) for k, v in config.universe.cmc_symbol_aliases.items()}
    _check_aliases_against_id_map({str(k).upper(): int(v) for k, v in id_map.items()}, aliases)
    # Curated aliases win: they cover tickers CMC no longer lists.
    id_map = {**id_map, **aliases}

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
            cached_history = cmc.cached_history(int(cmc_id))
            if cached_history.empty or not cmc.has_backfill(int(cmc_id), start=start.date()):
                screening_rows.append(
                    {"coin_id": coin_id, "symbol": symbol, "name": name, "status": "excluded", "details": f"coinmarketcap_history: {exc}"}
                )
                LOGGER.warning("CoinMarketCap unavailable for %s (%s): %s", coin_id, symbol, exc)
                continue
            # A transient provider failure must not delete an already
            # backfilled asset from the candidate cache. That would recreate
            # the exact survivorship hole this watchlist exists to prevent.
            history = cached_history
            details = f"coinmarketcap_history_cached_after_error: {exc}"
            LOGGER.warning(
                "Using cached CoinMarketCap history for %s (%s) after refresh failure: %s",
                coin_id,
                symbol,
                exc,
            )

        if history.empty:
            screening_rows.append(
                {"coin_id": coin_id, "symbol": symbol, "name": name, "status": "excluded", "details": "coinmarketcap_history_empty"}
            )
            LOGGER.warning("Skipping %s (%s): CoinMarketCap returned no usable history", coin_id, symbol)
            continue

        enriched_asset = {**asset, "cmc_id": int(cmc_id)}
        if details:
            enriched_asset["history_fetch_warning"] = details

        # Anchor both venue windows to the asset's own last print, not to today.
        # A delisted pair has no candles in the trailing 400 days, so a
        # today-anchored window reads as "no independent source" and the asset
        # is refused - which is how the missing MATIC would have been blocked
        # even after its history was recovered.
        history_latest = _last_print_date(history)
        feed_ended = _feed_ended(history, end)
        venue_end = min(end.normalize(), history_latest or end.normalize())
        if feed_ended:
            # An ended series has no current print to protect, and the part
            # that matters is the whole thing: the strategy could have held it
            # at any point. Verify the entire series against the venue instead
            # of only its last year.
            history_first = pd.Timestamp(history["date"].min())
            if history_first.tzinfo is not None:
                history_first = history_first.tz_convert("UTC").tz_localize(None)
            venue_start = min(venue_end, history_first.normalize())
        else:
            venue_start = venue_end - pd.Timedelta(days=config.providers.binance.history_days)

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
            gate_frame = gateio.fetch_daily_candles(
                symbol, start=venue_start, end=venue_end, force=force
            )
        except Exception as exc:  # noqa: BLE001
            details = f"{details} | gateio_history_missing: {exc}".lstrip(" |")
            LOGGER.warning("Gate.io history unavailable for %s (%s): %s", coin_id, symbol, exc)

        # A second exchange venue, reached through Binance's official public
        # data mirror (api.binance.com answers 451 from this host and
        # api.binance.us is a much thinner book). It carries no history for
        # delisted names (HT and CEL answer "Invalid symbol"), in which case
        # the frame is simply empty and the adjudicator falls through as
        # before; days below its dollar-volume floor are dropped for the same
        # reason.
        try:
            binance_frame = binance.fetch_daily_candles(
                symbol,
                start=venue_start.date(),
                end=venue_end.date(),
                force=force,
            )
        except Exception as exc:  # noqa: BLE001
            binance_frame = pd.DataFrame()
            LOGGER.warning("Binance history unavailable for %s (%s): %s", coin_id, symbol, exc)
        if not binance_frame.empty:
            enriched_asset["binance_pair"] = binance.resolve_pair(symbol)

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

        # The same tests the build applies (venue block test for Gate.io,
        # recent window for a live feed), so every dispute the build will see
        # has had its tie-break fetched here.
        secondary_result = compare_daily_prices(
            history.rename(columns={"close": "price"}),
            secondary,
            secondary_column=secondary_column,
            min_overlap_days=config.data_quality.cross_check_min_overlap_days,
            max_median_gap=config.data_quality.cross_check_max_median_gap,
            max_latest_gap=config.data_quality.cross_check_max_latest_gap,
            max_latest_staleness_days=config.data_quality.cross_check_max_latest_staleness_days,
            require_latest_coverage=not feed_ended,
            exchange_venue=secondary_source == "gateio",
            recent_days=None if feed_ended else config.data_quality.cross_check_recent_days,
        )

        if not secondary_result.passed:
            # CoinGecko cannot adjudicate its own disagreement.  It can only
            # act as the tertiary vote when Gate.io was the secondary source.
            coingecko_chart_ready = False
            if secondary_source == "gateio":
                # A Gate disagreement is rare.  Fetch CoinGecko only for that
                # adjudication, which keeps the normal refresh well below its
                # free-tier request ceiling.
                try:
                    chart = coingecko.fetch_daily_market_chart(
                        coin_id, config.data_quality.cross_check_recent_days, force=force
                    )
                    chart_result = compare_daily_prices(
                        history.rename(columns={"close": "price"}),
                        chart,
                        secondary_column="cg_price",
                        min_overlap_days=config.data_quality.cross_check_min_overlap_days,
                        max_median_gap=config.data_quality.cross_check_max_median_gap,
                        max_latest_gap=config.data_quality.cross_check_max_latest_gap,
                        max_latest_staleness_days=config.data_quality.cross_check_max_latest_staleness_days,
                        require_latest_coverage=not feed_ended,
                    )
                    coingecko_chart_ready = bool(
                        chart_result.latest_primary_covered
                        and chart_result.overlap_days >= config.data_quality.cross_check_min_overlap_days
                    )
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

    _check_unique_cmc_ids([(str(a["id"]), str(a["symbol"]), int(a["cmc_id"])) for a in valid_assets])
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
    """Load a cached CoinMarketCap history without independent evidence.

    Every row the level-corruption test flags is dropped, as no venue is
    consulted here; the panel build uses ``_read_cmc_history`` and
    ``_judge_level_corruption`` instead, which keep venue-confirmed moves.
    """
    loaded = _read_cmc_history(raw_dir, cmc_id)
    if loaded.frame is None:
        return None
    flagged = set(loaded.level_corruption_dates)
    return loaded.frame[~loaded.frame["date"].isin(flagged)].reset_index(drop=True)


# Every value a CMC row carries into the panel. Two cached fetches of the same
# day that differ in any of them are a provider revision, which is reported.
CMC_HISTORY_COLUMNS = ["date", "price", "volume_usd", "market_cap", "circulating_supply"]
CMC_VALUE_COLUMNS = CMC_HISTORY_COLUMNS[1:]


@dataclass(frozen=True, eq=False)
class CmcHistoryLoad:
    """A normalized CMC history plus the evidence of what loading resolved.

    ``duplicate_dates`` counts days cached by more than one fetch (the daily
    tail refresh re-requests overlapping windows, so most days are);
    ``conflicting_duplicate_dates`` counts the ones whose copies disagree,
    where the newest fetch was kept.
    """

    frame: pd.DataFrame | None
    duplicate_dates: int = 0
    conflicting_duplicate_dates: int = 0
    # Rows the level-corruption ring test flags (see ``_level_corruption_mask``).
    # They are still in ``frame``: whether they go depends on venue evidence
    # that only the build loop holds (``_judge_level_corruption``).
    level_corruption_dates: tuple[pd.Timestamp, ...] = ()


def _cmc_rows_from_payload(payload: list[object]) -> pd.DataFrame:
    """One cached CMC window, cleaned row by row.

    CMC stores 0 (not null) for assets it tracks without supply data, e.g.
    WhiteBIT Coin. A zero market cap is missing information, not a real value:
    keeping it would rank the asset inside the Top-N and displace a genuine
    constituent. A row without a positive close is not the fetch's answer for
    that day, so it is dropped *before* the merge and an older valid copy can
    stand in for it.
    """
    rows = []
    for row in payload:
        if not isinstance(row, dict):
            continue
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
    frame = pd.DataFrame(rows, columns=CMC_HISTORY_COLUMNS)
    for column in CMC_VALUE_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce").astype(float)
    frame.loc[frame["market_cap"] <= 0, "market_cap"] = np.nan
    frame = frame.dropna(subset=["price"])
    return frame[frame["price"] > 0].reset_index(drop=True)


def _read_cmc_history(raw_dir: Path, cmc_id: int) -> CmcHistoryLoad:
    """Load and normalize a cached CoinMarketCap history, with its evidence.

    Overlapping cache windows are merged so the newest *fetch* wins every
    duplicated date. The loader used to concatenate the files in name order
    and then call an unstable ``sort_values("date")``, so ``keep="last"`` kept
    whichever copy the sort left last - on a revised synthetic tail the new
    value survived on 209 dates and the stale one on 189. Name order is not
    fetch order either: a forced full re-download is the newest fetch, yet its
    name (the earliest start epoch) sorts first. The shared
    :mod:`atlas20.data.cache_merge` helpers order files by fetch time and
    describe every duplicate whose copies disagree.
    """
    directory = raw_dir / "coinmarketcap" / "history"
    if not directory.exists():
        return CmcHistoryLoad(None)

    frames: list[pd.DataFrame] = []
    for path in fetch_ordered(directory.glob(f"{cmc_id}_*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if not payload or not isinstance(payload, list):
            continue
        frame = _cmc_rows_from_payload(payload)
        if not frame.empty:
            frames.append(frame)

    if not frames:
        return CmcHistoryLoad(None)

    result = merge_by_fetch_order(frames, value_columns=CMC_VALUE_COLUMNS, columns=CMC_HISTORY_COLUMNS)
    if result.conflicting_dates:
        LOGGER.warning("CoinMarketCap id=%s: %s", cmc_id, describe_conflicts(result))
    merged = result.frame

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

    merged = merged.sort_values("date", kind="mergesort").reset_index(drop=True)
    flagged = merged.loc[_level_corruption_mask(merged), "date"]
    return CmcHistoryLoad(
        merged,
        duplicate_dates=result.duplicate_dates,
        conflicting_duplicate_dates=result.conflicting_dates,
        level_corruption_dates=tuple(pd.Timestamp(day) for day in flagged),
    )


def _level_corruption_mask(frame: pd.DataFrame, factor: float = 20.0) -> pd.Series:
    """Flag rows where the provider reports a wildly wrong price level.

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

    A genuine 20x round trip inside two months still looks exactly like this,
    which is why a flag is only a candidate: see ``_judge_level_corruption``.
    ``frame`` must be sorted by date; the mask is aligned with its index.
    """
    if frame.empty:
        return pd.Series(False, index=frame.index)
    price = frame["price"].astype(float)
    before = price.shift(31).rolling(30, min_periods=15).median()
    after = price.shift(-61).rolling(30, min_periods=15).median()
    rings_agree = (before / after).between(1.0 / 3.0, 3.0)
    baseline = (before * after) ** 0.5
    ratio = price / baseline
    corrupted = rings_agree & ((ratio > factor) | (ratio < 1.0 / factor))
    return corrupted.fillna(False).astype(bool)


def _drop_level_corruption(frame: pd.DataFrame, factor: float = 20.0) -> pd.DataFrame:
    """Drop every flagged row (the evidence-free rule; see the mask)."""
    if frame.empty:
        return frame
    ordered = frame.sort_values("date", kind="mergesort").reset_index(drop=True)
    return ordered.loc[~_level_corruption_mask(ordered, factor)].reset_index(drop=True)


def _judge_level_corruption(
    history: pd.DataFrame,
    flagged: tuple[pd.Timestamp, ...],
    sources: list[IndependentSource],
    *,
    tolerance: float,
) -> tuple[list[pd.Timestamp], list[pd.Timestamp]]:
    """Split flagged rows into (dropped, confirmed) using independent prints.

    The ring test cannot tell a provider level error from a genuine 20x round
    trip, and it used to delete both silently - a real move was erased and the
    asset then carried at a stale price. A flagged row is now *kept* only when
    an exchange venue prints within ``tolerance`` of CMC that day and no
    independent source is further than that: a real move trades on the order
    books. Every other flagged row is dropped - one a source disputes is proven
    corruption, and one no venue confirms keeps the old evidence-free rule
    (Huobi Token's 2025 block predates every cached venue window) - but the
    drop is now logged and counted in ``level_corruption_rows``.
    """
    if not flagged:
        return [], []
    closes = history.set_index("date")["price"].astype(float)
    confirmed_days: list[pd.Timestamp] = []
    dropped_days: list[pd.Timestamp] = []
    quotes = {source.name: _source_closes(source) for source in sources}
    for day in flagged:
        cmc_close = float(closes.get(day, np.nan))
        venue_confirms = False
        disputed = False
        for source in sources:
            quote = quotes[source.name].get(day)
            if quote is None or not np.isfinite(cmc_close) or quote <= 0:
                continue
            gap = max(cmc_close / quote, quote / cmc_close) - 1.0
            if gap > tolerance:
                disputed = True
            elif source.exchange_venue:
                venue_confirms = True
        if venue_confirms and not disputed:
            confirmed_days.append(day)
        else:
            dropped_days.append(day)
    return dropped_days, confirmed_days


def _source_closes(source: IndependentSource) -> dict[pd.Timestamp, float]:
    frame = source.frame
    if frame is None or frame.empty or source.column not in frame.columns:
        return {}
    dates = pd.to_datetime(frame["date"], errors="coerce", utc=True).dt.tz_convert(None).dt.normalize()
    values = pd.to_numeric(frame[source.column], errors="coerce")
    return {pd.Timestamp(day): float(value) for day, value in zip(dates, values, strict=True) if pd.notna(day) and pd.notna(value)}


def _date_ranges(days: list[pd.Timestamp]) -> str:
    """Compact ``first..last`` ranges of consecutive days, comma separated."""
    if not days:
        return ""
    ordered = sorted(pd.Timestamp(day) for day in days)
    ranges: list[str] = []
    start = previous = ordered[0]
    for day in ordered[1:]:
        if day - previous != pd.Timedelta(days=1):
            ranges.append(f"{start.date()}..{previous.date()}" if start != previous else f"{start.date()}")
            start = day
        previous = day
    ranges.append(f"{start.date()}..{previous.date()}" if start != previous else f"{start.date()}")
    return ", ".join(ranges)


def _load_coingecko_chart(path: Path) -> pd.DataFrame:
    """Normalize a cached CoinGecko market chart into a daily close series.

    Same parser as the live client, so the build and the download compare the
    same, correctly dated closes (00:00 UTC of D+1 is D's close).
    """
    if not path.exists():
        return pd.DataFrame(columns=["date", "cg_price"])
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return pd.DataFrame(columns=["date", "cg_price"])
    if not isinstance(payload, dict):
        return pd.DataFrame(columns=["date", "cg_price"])
    return daily_closes_from_market_chart(payload)[["date", "cg_price"]]


@dataclass(frozen=True, eq=False)
class PanelEnd:
    """Where the panel may end, and which live assets hold it there."""

    covered_end: pd.Timestamp
    panel_end: pd.Timestamp
    last_print: pd.Series
    holding: tuple[str, ...]


def _panel_end(panel: pd.DataFrame, ended: set[str], min_daily_coverage: float) -> PanelEnd:
    """Find the last date the panel can publish without dropping a live asset.

    Coverage is measured against the assets *live on each date*: an asset
    counts from its first print, and an ended feed (a delisting or migration,
    see ``_feed_ended``) only up to its last one. Counting ended feeds on every
    later date froze the panel end: with 2 of 10 feeds ended, every newer date
    sat at 8/10 < 90% and 41 fully covered dates were dropped.

    The coverage bar alone still let a *live* asset drop out of the newest
    dates - at 9/10 the largest coin's three-day CMC stall passed, it vanished
    from the point-in-time Top-N on the live-signal dates and the next coin
    was promoted. So the end is held at the last print of any live asset
    that stops early. Blocking that asset instead would delete its whole
    history (and trip the regression guard); holding the end keeps every
    published date complete, records the lag, and lets the live signal's
    freshness guard refuse a stale panel. ``_feed_ended`` bounds the hold: a
    feed silent for more than ``ENDED_FEED_GRACE_DAYS`` counts as ended.
    """
    spans = panel.groupby("coin_id")["date"].agg(["min", "max"])
    dates = pd.DatetimeIndex(sorted(panel["date"].unique()))
    expected = np.zeros(len(dates), dtype=int)
    for coin_id, first, last in spans.itertuples():
        live_on = dates >= first
        if coin_id in ended:
            live_on &= dates <= last
        expected += live_on.astype(int)
    present = panel.groupby("date")["coin_id"].nunique().reindex(dates, fill_value=0).to_numpy()
    required = np.maximum(1, np.ceil(expected * min_daily_coverage))
    covered = dates[present >= required]
    if covered.empty:
        raise ValueError("No panel date has sufficient provider coverage")
    covered_end = pd.Timestamp(covered.max())
    live_last = spans.loc[[coin_id for coin_id in spans.index if coin_id not in ended], "max"]
    holding = live_last[live_last < covered_end]
    panel_end = pd.Timestamp(min(covered_end, holding.min())) if not holding.empty else covered_end
    return PanelEnd(covered_end, panel_end, spans["max"], tuple(sorted(holding.index)))


def _guard_panel_regression(
    existing_path: Path,
    new_panel: pd.DataFrame,
    *,
    intended_exclusions: set[str] | frozenset[str] = frozenset(),
) -> None:
    """Refuse to replace a good panel with a provider-degraded smaller panel.

    A transient Gate/Binance/CoinGecko failure can make a live asset look
    "unverified" and cause the processor to omit it.  Writing that result
    would silently change the historical universe and could remove a coin that
    the strategy is actually holding.  The processed panel is cumulative:
    assets may be added, but a refresh must not delete one unless an operator
    excludes it by id in the config (``intended_exclusions``).  Only explicit
    ids count; a keyword or metadata change is provider-driven and still
    blocks the write.
    """
    if not existing_path.exists():
        return
    try:
        existing = pd.read_csv(existing_path, usecols=["date", "coin_id"])
    except (OSError, ValueError):
        return
    if existing.empty:
        return

    old_ids = set(existing["coin_id"].astype(str))
    new_ids = set(new_panel["coin_id"].astype(str))
    excluded = {str(value).lower() for value in intended_exclusions}
    missing = sorted(old_ids - new_ids)
    intended = [coin_id for coin_id in missing if coin_id.lower() in excluded]
    unexpected = [coin_id for coin_id in missing if coin_id.lower() not in excluded]
    if intended:
        LOGGER.warning(
            "Removing %s asset(s) from the processed panel because the config excludes them by id: %s",
            len(intended),
            ", ".join(intended),
        )
    if unexpected:
        preview = ", ".join(unexpected[:12])
        suffix = " ..." if len(unexpected) > 12 else ""
        raise RuntimeError(
            "Processed panel regression: refusing to overwrite an existing panel "
            f"because {len(unexpected)} asset(s) would disappear: {preview}{suffix}. "
            "Repair the independent provider cache, or, if the removal is intended, "
            "add the coin id to universe.excluded_ids (or universe.stablecoin_ids) "
            "before rerunning."
        )

    old_start = pd.to_datetime(existing["date"], errors="coerce").min()
    new_start = pd.to_datetime(new_panel["date"], errors="coerce").min()
    if pd.notna(old_start) and pd.notna(new_start) and pd.Timestamp(new_start) > pd.Timestamp(old_start):
        raise RuntimeError(
            "Processed panel regression: refusing to move the panel start date "
            f"forwards from {pd.Timestamp(old_start).date()} to {pd.Timestamp(new_start).date()}"
        )

    old_end = pd.to_datetime(existing["date"], errors="coerce").max()
    new_end = pd.to_datetime(new_panel["date"], errors="coerce").max()
    if pd.notna(old_end) and pd.notna(new_end) and pd.Timestamp(new_end) < pd.Timestamp(old_end):
        raise RuntimeError(
            "Processed panel regression: refusing to move the panel end date "
            f"backwards from {pd.Timestamp(old_end).date()} to {pd.Timestamp(new_end).date()}"
        )


def _write_csv_atomic(frame: pd.DataFrame, path: Path, *, index: bool = False) -> None:
    """Write a CSV through a sibling temp file, then replace atomically."""
    temp_path = path.with_name(f".{path.name}.tmp")
    frame.to_csv(temp_path, index=index)
    temp_path.replace(path)


def build_processed_datasets(
    config: ResearchConfig,
    sector_config: SectorConfig,
    *,
    persist: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
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
    binance = BinanceClient(config.providers.binance, raw_dir)
    coinpaprika = CoinPaprikaClient(config.providers.coinpaprika, raw_dir)

    id_map = _load_cached_id_map(raw_dir)
    aliases = {k.upper(): int(v) for k, v in config.universe.cmc_symbol_aliases.items()}
    if id_map is not None:
        _check_aliases_against_id_map(id_map, aliases)
    cmc_ids = _resolve_candidate_cmc_ids(candidates, id_map, aliases)
    assignments: list[tuple[str, str, int]] = []
    for _, asset in candidates.iterrows():
        resolved_id = cmc_ids.get(str(asset["id"]))
        if resolved_id is not None:
            assignments.append((str(asset["id"]), str(asset["symbol"]), resolved_id))
    _check_unique_cmc_ids(assignments)

    feed_ended_by_asset: dict[str, bool] = {}
    for _, asset in candidates.iterrows():
        coin_id = str(asset["id"])
        symbol = str(asset["symbol"]).upper()
        name = str(asset.get("name", coin_id))

        cmc_id = cmc_ids.get(coin_id)
        if cmc_id is None:
            LOGGER.warning("Missing CoinMarketCap id for %s (%s); skipping", coin_id, symbol)
            continue
        loaded = _read_cmc_history(raw_dir, int(cmc_id))
        history = loaded.frame
        if history is None or history.empty:
            LOGGER.warning("Missing CoinMarketCap cache for %s (%s); skipping", coin_id, symbol)
            continue

        metadata_path = raw_dir / "coingecko" / "coin_metadata" / f"{coin_id}.json"
        metadata_payload = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
        if metadata_payload and metadata_is_excluded(metadata_payload, config.universe):
            LOGGER.info("Skipping %s (%s) during processing because metadata marks it ineligible", coin_id, symbol)
            continue

        feed_ended = _feed_ended(history, config.end_timestamp)
        feed_ended_by_asset[coin_id] = feed_ended
        chart_path = raw_dir / "coingecko" / "market_chart" / f"{coin_id}_{config.data_quality.cross_check_recent_days}d.json"
        chart = _load_coingecko_chart(chart_path)
        gateio_pair = asset.get("gateio_pair")
        gate_frame = pd.DataFrame()
        if gateio_pair is not None and not pd.isna(gateio_pair):
            gate_frame = gateio.load_daily_candles(symbol)
        binance_frame = binance.load_daily_candles(symbol)

        # Independent sources.  Gate.io and Binance are exchange venues;
        # CoinGecko is an aggregator and carries the weakest evidence, but it
        # still counts as an independent vote when no order book covers a name.
        # CoinPaprika is the last-resort vote the download fetches when nothing
        # else can break a tie. CMC owns every value in the panel either way -
        # these only decide whether to trust it.
        pap_frame = pd.DataFrame()
        pap_id = asset.get("coinpaprika_id")
        if pap_id is not None and not pd.isna(pap_id):
            pap_frame = coinpaprika.load_daily_history(str(pap_id))
        sources = [
            IndependentSource("gateio", gate_frame, "gate_price"),
            IndependentSource("binance", binance_frame, "binance_price"),
            IndependentSource("coingecko", chart, "cg_price"),
            IndependentSource("coinpaprika", pap_frame, "pap_price"),
        ]

        corrupted_days, confirmed_days = _judge_level_corruption(
            history,
            loaded.level_corruption_dates,
            sources,
            tolerance=config.data_quality.cross_check_max_median_gap,
        )
        if corrupted_days:
            LOGGER.warning(
                "Dropping %s CMC row(s) of %s (%s) as price-level corruption: %s",
                len(corrupted_days),
                coin_id,
                symbol,
                _date_ranges(corrupted_days),
            )
            history = history[~history["date"].isin(set(corrupted_days))].reset_index(drop=True)
        if confirmed_days:
            LOGGER.warning(
                "Keeping %s flagged CMC row(s) of %s (%s): an exchange venue confirms the move on %s",
                len(confirmed_days),
                coin_id,
                symbol,
                _date_ranges(confirmed_days),
            )

        validation = summarize_market_history(
            coin_id=coin_id,
            symbol=symbol,
            name=name,
            history=history,
            quality_config=config.data_quality,
        )

        # Every source votes. Taking the first source that *passes* discarded
        # every other source's disagreement: CMC=250 against Gate=Binance=100
        # was admitted on CoinGecko's word, and a CMC block 13 months back was
        # "confirmed" by a CoinGecko chart that starts after it. A live feed's
        # level tests also run on the recent window, so the ever-growing venue
        # overlap cannot dilute a block; an ended feed is verified whole.
        cross = adjudicate_sources(
            validation.history,
            sources,
            min_overlap_days=config.data_quality.cross_check_min_overlap_days,
            max_median_gap=config.data_quality.cross_check_max_median_gap,
            max_latest_gap=config.data_quality.cross_check_max_latest_gap,
            max_latest_staleness_days=config.data_quality.cross_check_max_latest_staleness_days,
            require_latest_coverage=not feed_ended,
            recent_days=None if feed_ended else config.data_quality.cross_check_recent_days,
        )
        # "Disagrees" and "could not be checked" are different states. A proven
        # disagreement blocks the asset; a missing second source is recorded
        # and only blocks when the operator demands verification.
        unverified = cross.reason in UNVERIFIED_REASONS
        blocked_by_cross_check = not cross.passed and (
            (not unverified) or config.data_quality.require_cross_check
        )
        admitted = validation.passed and not (
            config.data_quality.exclude_on_cross_check_failure and blocked_by_cross_check
        )
        tertiary_result = cross.tertiary
        secondary_tertiary_result = cross.secondary_vs_tertiary
        tertiary_source = cross.tertiary_source
        confirmed_by = cross.confirmed_by or ""
        lags = [result.primary_lag_days for result in cross.verdicts.values() if result.primary_lag_days is not None]
        primary_lag_days = max(lags) if lags else 0
        # Each source's own verdict against CMC, so a disagreement is visible
        # even when another source settled it.
        source_verdicts: dict[str, object] = {}
        for source in sources:
            result = cross.verdicts.get(source.name)
            source_verdicts[f"crosscheck_{source.name}_reason"] = result.reason if result is not None else ""
            source_verdicts[f"crosscheck_{source.name}_overlap_days"] = (
                result.overlap_days if result is not None else pd.NA
            )
            source_verdicts[f"crosscheck_{source.name}_median_gap"] = (
                result.median_gap if result is not None else pd.NA
            )
        quality_rows.append(
            validation.summary
            | {
                "metadata_available": bool(metadata_payload),
                # Days cached by more than one fetch, and those whose copies
                # disagree (a provider revision; the newest fetch was kept).
                "cmc_duplicate_dates": loaded.duplicate_dates,
                "cmc_conflicting_duplicate_dates": loaded.conflicting_duplicate_dates,
                # Rows dropped as price-level corruption, and flagged rows kept
                # because an exchange venue confirmed the move.
                "level_corruption_rows": len(corrupted_days),
                "level_corruption_dates": _date_ranges(corrupted_days),
                "level_corruption_confirmed_rows": len(confirmed_days),
                # The API's data-quality alerts read these four. They describe
                # the comparison the decision rests on: the source that admitted
                # the asset, or the disagreement that refused it.
                "latest_overlap_date": cross.effective_result.latest_overlap_date,
                "latest_price_gap": cross.effective_result.latest_gap,
                "median_price_gap": cross.effective_result.median_gap,
                "price_correlation": cross.effective_result.price_correlation,
                "crosscheck_passed": cross.passed,
                "crosscheck_verified": not unverified,
                "crosscheck_reason": cross.reason,
                "crosscheck_confirmed_by": confirmed_by,
                "crosscheck_secondary_source": cross.secondary_source,
                "crosscheck_overlap_days": cross.overlap_days,
                "crosscheck_primary_latest_date": cross.latest_primary_date,
                "crosscheck_secondary_latest_date": cross.latest_secondary_date,
                "crosscheck_latest_staleness_days": cross.latest_staleness_days,
                "crosscheck_latest_primary_covered": cross.latest_primary_covered,
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
                # An ended feed cannot be corroborated to its final print: no
                # venue still quotes a delisted pair. Record how many trailing
                # days of the primary series rest on CMC alone so the audit can
                # price that in instead of hiding it.
                "crosscheck_primary_ended": bool(feed_ended),
                # CMC stopping before an independent source is the reverse of
                # a stale source: the venue proves the asset kept trading. A
                # live asset flagged here holds the panel end (``_panel_end``).
                "crosscheck_primary_lag_days": primary_lag_days,
                "crosscheck_primary_stale": bool(primary_lag_days and not feed_ended),
                "crosscheck_unverified_tail_days": (
                    max(
                        int(
                            (
                                pd.Timestamp(cross.latest_primary_date) - pd.Timestamp(cross.latest_secondary_date)
                            ).days
                        ),
                        0,
                    )
                    if feed_ended
                    and cross.latest_primary_date is not None
                    and cross.latest_secondary_date is not None
                    else 0
                ),
                "included_in_panel": bool(admitted),
            }
            | source_verdicts
        )
        if cross.passed and cross.reason != "ok":
            LOGGER.warning(
                "Admitted %s (%s) after %s disputed CMC: %s confirms CMC on every disputed day (%s)",
                coin_id,
                symbol,
                cross.secondary_source,
                cross.confirmed_by,
                cross.secondary.reason,
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
        # Include pre-window history so every trailing statistic is already
        # warm on start_timestamp (see ``_pre_window_buffer_days``). The end of
        # the window stays fixed because no data after the backtest end is
        # needed.
        data_start = config.start_timestamp - pd.Timedelta(days=_pre_window_buffer_days(config))
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
                "latest_price_gap": cross.effective_result.latest_gap,
                "median_price_gap": cross.effective_result.median_gap,
                "direct_market_cap_days": validation.summary["direct_market_cap_days"],
                "direct_price_days": validation.summary["direct_price_days"],
                "history_days": validation.summary["history_days"],
            }
        )

    if not panel_frames:
        raise ValueError("No processed panel rows could be built")

    panel = pd.concat(panel_frames, ignore_index=True)
    ended_ids = {coin_id for coin_id, ended in feed_ended_by_asset.items() if ended}
    tail = _panel_end(panel, ended_ids, config.data_quality.min_daily_coverage)
    panel_end = tail.panel_end
    if tail.holding:
        LOGGER.warning(
            "Holding the panel end at %s (data covers %s): live asset(s) whose CMC feed stops early: %s",
            panel_end.date(),
            tail.covered_end.date(),
            ", ".join(
                f"{coin_id} (last print {tail.last_print[coin_id].date()}, "
                f"{(tail.covered_end - tail.last_print[coin_id]).days}d behind)"
                for coin_id in tail.holding
            ),
        )
    dropped = panel[panel["date"] > panel_end]
    if not dropped.empty:
        dropped_dates = sorted(str(value.date()) for value in dropped["date"].unique())
        first_dropped = dropped["date"].min()
        missing = sorted(
            coin_id
            for coin_id, last in tail.last_print.items()
            if coin_id not in ended_ids and last < first_dropped
        )
        LOGGER.warning(
            "Dropping partial provider dates %s: live asset(s) without a CMC row on %s: %s",
            dropped_dates,
            first_dropped.date(),
            ", ".join(missing[:10]) + (" ..." if len(missing) > 10 else ""),
        )
    panel = panel[panel["date"] <= panel_end].copy()
    panel = panel.sort_values(["date", "market_cap"], ascending=[True, False]).reset_index(drop=True)
    metadata = pd.DataFrame(metadata_rows).drop_duplicates(subset=["coin_id"]).set_index("coin_id")
    quality = pd.DataFrame(quality_rows).drop_duplicates(subset=["coin_id"]).set_index("coin_id")
    # How far each admitted asset's last CMC print is behind the newest date
    # the rest of the universe covers (for an ended feed: how long ago it
    # ended), and whether it is what holds the panel end back.
    last_print = tail.last_print.reindex(quality.index)
    quality["cmc_lag_days"] = (tail.covered_end - last_print).dt.days
    quality["holds_panel_end"] = quality.index.isin(tail.holding)
    quality["panel_end_date"] = panel_end

    panel_path = processed_dir / "panel_daily.csv"
    if persist:
        _guard_panel_regression(
            panel_path,
            panel,
            intended_exclusions={
                *config.universe.excluded_ids,
                *config.universe.stablecoin_ids,
            },
        )
        _write_csv_atomic(panel, panel_path, index=False)
        _write_csv_atomic(metadata, processed_dir / "metadata.csv", index=True)
        _write_csv_atomic(quality, processed_dir / "data_quality.csv", index=True)
        LOGGER.info(
            "Processed dataset written: %s rows across %s assets (all market caps from CoinMarketCap)",
            len(panel),
            metadata.shape[0],
        )
    else:
        LOGGER.info(
            "Processed dataset built in memory: %s rows across %s assets "
            "(persist=False; canonical processed files untouched)",
            len(panel),
            metadata.shape[0],
        )
    return panel, metadata
