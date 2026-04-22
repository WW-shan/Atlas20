"""Download orchestration and processed dataset builders."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from atlas20.config import ResearchConfig, SectorConfig
from atlas20.data.catalog import asset_is_excluded, deduplicate_assets, metadata_is_excluded
from atlas20.data.coingecko import CoinGeckoClient
from atlas20.data.cryptocompare import CryptoCompareClient
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

        try:
            cryptocompare.fetch_daily_history(symbol, force=force)
        except Exception as exc:  # noqa: BLE001
            status = "excluded"
            details = f"cryptocompare_history: {exc}"
            screening_rows.append({"coin_id": coin_id, "symbol": symbol, "name": name, "status": status, "details": details})
            LOGGER.warning("Skipping %s (%s): %s", coin_id, symbol, exc)
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
        if not history_path.exists():
            LOGGER.warning("Missing cache for %s (%s); skipping from processed dataset", coin_id, symbol)
            continue

        metadata_payload = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else {}
        if metadata_payload and metadata_is_excluded(metadata_payload, config.universe):
            LOGGER.info("Skipping %s (%s) during processing because metadata marks it ineligible", coin_id, symbol)
            continue

        history_payload = json.loads(history_path.read_text(encoding="utf-8"))
        history = pd.DataFrame(history_payload["Data"]["Data"])
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
        blended = blended[(blended["date"] >= config.start_timestamp) & (blended["date"] <= config.end_timestamp)].copy()
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
