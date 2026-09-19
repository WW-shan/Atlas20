"""Download orchestration and processed dataset builders."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from atlas20.config import ResearchConfig, SectorConfig
from atlas20.data.catalog import asset_is_excluded, deduplicate_assets, metadata_is_excluded
from atlas20.data.coingecko import CoinGeckoClient
from atlas20.data.binanceus import BinanceUSClient
from atlas20.data.cryptocompare import CryptoCompareClient
from atlas20.data.splice import splice_histories
from atlas20.data.validation import EMPTY_CG_HISTORY, validate_and_blend_history
from atlas20.logging_utils import ensure_dir, get_logger
from atlas20.sectors.mapping import resolve_sector_map

LOGGER = get_logger(__name__)


CANDIDATE_ASSETS_FILE = "candidate_assets.json"



def _candidate_assets_path(config: ResearchConfig) -> Path:
    return config.resolve_path(config.paths.raw_dir) / "coingecko" / CANDIDATE_ASSETS_FILE



def download_and_cache_raw_data(config: ResearchConfig, force: bool = False) -> pd.DataFrame:
    """Fetch raw candidate, metadata, and historical files into the local cache."""
    raw_dir = ensure_dir(config.resolve_path(config.paths.raw_dir))
    coingecko = CoinGeckoClient(config.providers.coingecko, raw_dir)
    cryptocompare = CryptoCompareClient(config.providers.cryptocompare, raw_dir)
    binance_us = BinanceUSClient(config.providers.binance_us, raw_dir)

    LOGGER.info("Fetching current top-%s candidate assets from CoinGecko", config.universe.current_top_n_candidates)
    current_top = coingecko.fetch_top_markets(config.universe.current_top_n_candidates, force=force).to_dict(orient="records")
    legacy = coingecko.fetch_markets_by_ids(config.universe.legacy_candidate_ids, force=force).to_dict(orient="records")
    candidates = deduplicate_assets([*current_top, *legacy])
    filtered_candidates = [asset for asset in candidates if not asset_is_excluded(asset, config.universe)]

    candidate_path = _candidate_assets_path(config)
    candidate_path.parent.mkdir(parents=True, exist_ok=True)
    candidate_path.write_text(json.dumps(filtered_candidates, indent=2), encoding="utf-8")
    LOGGER.info("Prepared %s candidate assets", len(filtered_candidates))

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

        history_ok = False
        try:
            cryptocompare.fetch_daily_history(symbol, force=force)
            history_ok = True
        except Exception as exc:  # noqa: BLE001
            details = f"cryptocompare_history: {exc}"
            LOGGER.warning("CryptoCompare unavailable for %s (%s): %s", coin_id, symbol, exc)

        # Always refresh the current-source cache. A stale-but-readable
        # CryptoCompare cache would otherwise short-circuit this and the
        # series would never advance past its last successful pull.
        try:
            current = binance_us.fetch_daily_history(symbol, force=True)
        except Exception as fallback_exc:  # noqa: BLE001
            details = f"{details} | binanceus_history: {fallback_exc}".lstrip(" |")
            LOGGER.warning("Binance.US unavailable for %s (%s): %s", coin_id, symbol, fallback_exc)
            current = None
        if current is not None and not current.empty:
            history_ok = True
            if "cryptocompare_history" in details:
                details = f"{details} | used_binanceus_fallback"

        if not history_ok:
            status = "excluded"
            screening_rows.append({"coin_id": coin_id, "symbol": symbol, "name": name, "status": status, "details": details})
            LOGGER.warning("Skipping %s (%s): %s", coin_id, symbol, details)
            continue

        try:
            metadata_payload = coingecko.fetch_coin_metadata(coin_id, force=force)
        except Exception as exc:  # noqa: BLE001
            details = f"metadata_missing: {exc}"
            if config.data_quality.require_metadata:
                status = "excluded"
                screening_rows.append({"coin_id": coin_id, "symbol": symbol, "name": name, "status": status, "details": details})
                LOGGER.warning("Skipping %s (%s) because metadata is required: %s", coin_id, symbol, exc)
                continue
            LOGGER.warning("Metadata unavailable for %s (%s): %s", coin_id, symbol, exc)

        if metadata_payload and metadata_is_excluded(metadata_payload, config.universe):
            status = "excluded"
            details = "metadata_exclusion_rules"
            screening_rows.append({"coin_id": coin_id, "symbol": symbol, "name": name, "status": status, "details": details})
            LOGGER.info("Excluded %s (%s) using metadata filters", coin_id, symbol)
            continue

        if config.data_quality.use_coingecko_recent_history:
            try:
                coingecko.fetch_daily_market_chart(coin_id, config.data_quality.coingecko_recent_days, force=force)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("Recent CoinGecko history unavailable for %s (%s): %s", coin_id, symbol, exc)
                if details:
                    details = f"{details} | market_chart_missing: {exc}"
                else:
                    details = f"market_chart_missing: {exc}"

        screening_rows.append({"coin_id": coin_id, "symbol": symbol, "name": name, "status": status, "details": details})
        valid_assets.append(asset)

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



def _legacy_history_frame(history: pd.DataFrame) -> pd.DataFrame:
    """Normalize a raw CryptoCompare histoday frame into date/close/volume."""
    empty = pd.DataFrame(columns=["date", "close", "volume_usd"])
    if history is None or history.empty or "time" not in history.columns:
        return empty
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(history["time"], unit="s").dt.normalize(),
            "close": pd.to_numeric(history["close"], errors="coerce"),
            "volume_usd": pd.to_numeric(history.get("volumeto"), errors="coerce"),
        }
    )
    frame = frame[frame["close"] > 0]
    return frame.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def _load_binanceus_history(raw_dir: Path, symbol: str) -> pd.DataFrame | None:
    """Load a cached Binance.US kline frame if one exists."""
    path = raw_dir / "binanceus" / "klines" / f"{symbol.upper()}.json"
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not payload:
        return None
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime([int(row[0]) for row in payload], unit="ms").normalize(),
            "close": [float(row[4]) for row in payload],
            "volume_usd": [float(row[7]) for row in payload],
        }
    )
    frame = frame[frame["close"] > 0]
    return frame.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


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

    for _, asset in candidates.iterrows():
        coin_id = str(asset["id"])
        symbol = str(asset["symbol"]).upper()
        name = str(asset.get("name", coin_id))
        history_path = raw_dir / "cryptocompare" / "histoday" / f"{symbol}.json"
        metadata_path = raw_dir / "coingecko" / "coin_metadata" / f"{coin_id}.json"
        market_chart_path = raw_dir / "coingecko" / "market_chart" / f"{coin_id}_{config.data_quality.coingecko_recent_days}d.json"
        binanceus_path = raw_dir / "binanceus" / "klines" / f"{symbol}.json"
        if not history_path.exists() and not binanceus_path.exists():
            LOGGER.warning("Missing cache for %s (%s); skipping from processed dataset", coin_id, symbol)
            continue

        metadata_payload = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
        if metadata_payload and metadata_is_excluded(metadata_payload, config.universe):
            LOGGER.info("Skipping %s (%s) during processing because metadata marks it ineligible", coin_id, symbol)
            continue

        # Assets listed after the CryptoCompare shutdown have no legacy
        # cache at all; Binance.US is then the only price source.
        if history_path.exists():
            history_payload = json.loads(history_path.read_text(encoding="utf-8"))
            history = pd.DataFrame(history_payload["Data"]["Data"])
        else:
            history = pd.DataFrame()

        # The CryptoCompare free tier shut down in mid-2026, so the legacy
        # cache stops at its last successful pull. Continue the series from
        # Binance.US and keep both sources aligned over their overlap window.
        legacy_frame = _legacy_history_frame(history)
        new_frame = _load_binanceus_history(raw_dir, symbol)
        if legacy_frame.empty and (new_frame is None or new_frame.empty):
            LOGGER.warning("No usable history for %s (%s); skipping", coin_id, symbol)
            continue
        if new_frame is not None and not new_frame.empty:
            spliced = splice_histories(legacy_frame, new_frame)
            # Price is spliced, but volume must stay on the legacy (aggregate
            # market) scale. Binance.US reports a single low-liquidity venue,
            # so its quote volume is orders of magnitude below the aggregate
            # figure the liquidity filter expects. Dates beyond the legacy
            # cache fall back to CoinGecko's aggregate volume downstream.
            legacy_volume = legacy_frame.set_index("date")["volume_usd"]
            history = pd.DataFrame(
                {
                    "date": spliced.frame["date"],
                    "close": spliced.frame["price"],
                }
            )
            history["volumeto"] = history["date"].map(legacy_volume)
        else:
            history = legacy_frame.rename(columns={"volume_usd": "volumeto"})
        if history.empty:
            continue

        cg_history = EMPTY_CG_HISTORY.copy()
        if market_chart_path.exists() and config.data_quality.use_coingecko_recent_history:
            market_chart_payload = json.loads(market_chart_path.read_text(encoding="utf-8"))
            cg_history = pd.DataFrame(
                {
                    "date": [pd.to_datetime(row[0], unit="ms").normalize() for row in market_chart_payload.get("prices", [])],
                    "cg_price": [row[1] for row in market_chart_payload.get("prices", [])],
                    "cg_market_cap": [row[1] for row in market_chart_payload.get("market_caps", [])],
                    "cg_volume_usd": [row[1] for row in market_chart_payload.get("total_volumes", [])],
                }
            )
            if not cg_history.empty:
                cg_history = cg_history.groupby("date", as_index=False).last()

        validation = validate_and_blend_history(
            coin_id=coin_id,
            symbol=symbol,
            name=name,
            cc_history=history,
            cg_history=cg_history,
            current_market_cap=float(asset.get("market_cap") or 0.0),
            quality_config=config.data_quality,
            use_proxy_market_caps=config.universe.use_proxy_market_caps,
        )
        quality_summary = validation.summary | {
            "metadata_available": bool(metadata_payload),
            "included_in_panel": bool(validation.passed or not config.data_quality.exclude_on_validation_failure),
        }
        quality_rows.append(quality_summary)

        if not validation.passed and config.data_quality.exclude_on_validation_failure:
            LOGGER.warning(
                "Excluding %s (%s) after source validation failure: %s",
                coin_id,
                symbol,
                validation.summary["validation_reason"],
            )
            continue

        blended = validation.blended_history.copy()
        # Include pre-window history so universe eligibility (history_days) can
        # be satisfied at start_timestamp. Without this, history_count begins at
        # 0 on the backtest start date and the universe builder rejects every
        # coin until min_history_days has accumulated -- which for short
        # windows means no eligible assets at any rebalance, raising
        # "No rebalance universes could be built". The end of the window stays
        # fixed because no data after the backtest end is needed.
        history_buffer = pd.Timedelta(days=config.universe.min_history_days)
        data_start = config.start_timestamp - history_buffer
        blended = blended[(blended["date"] >= data_start) & (blended["date"] <= config.end_timestamp)].copy()
        if blended.empty:
            continue

        blended["coin_id"] = coin_id
        blended["symbol"] = symbol
        blended["name"] = name
        blended["current_market_cap"] = float(asset.get("market_cap") or 0.0)
        blended["current_rank"] = asset.get("market_cap_rank")
        panel_frames.append(
            blended[
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
        "Processed dataset written: %s rows across %s assets (%s with direct CoinGecko overlap)",
        len(panel),
        metadata.shape[0],
        int((quality["direct_price_days"] > 0).sum()) if not quality.empty else 0,
    )
    return panel, metadata
