"""Candidate asset catalog helpers."""

from __future__ import annotations

from collections.abc import Iterable

from atlas20.config import UniverseConfig


def _normalize_text(value: str) -> str:
    return " ".join(str(value).lower().replace("/", " ").replace("-", " ").split())


def deduplicate_assets(assets: Iterable[dict]) -> list[dict]:
    """Deduplicate asset payloads by CoinGecko id."""
    merged: dict[str, dict] = {}
    for asset in assets:
        asset_id = str(asset["id"]).lower()
        merged[asset_id] = asset
    return list(merged.values())


def asset_is_excluded(asset: dict, universe_config: UniverseConfig) -> bool:
    """Return True when an asset should be excluded from the tradable universe seed."""
    asset_id = str(asset.get("id", "")).lower()
    symbol = str(asset.get("symbol", "")).lower()
    name = str(asset.get("name", "")).lower()

    if asset_id in {value.lower() for value in universe_config.stablecoin_ids}:
        return True
    if asset_id in {value.lower() for value in universe_config.excluded_ids}:
        return True
    if any(keyword.lower() in symbol for keyword in universe_config.symbol_exclusion_keywords):
        return True
    if any(keyword.lower() in name for keyword in universe_config.name_exclusion_keywords):
        return True
    return False


def metadata_is_excluded(metadata: dict, universe_config: UniverseConfig) -> bool:
    """Return True when metadata indicates the asset is ineligible."""
    name = str(metadata.get("name", "")).lower()
    asset_id = str(metadata.get("id", "")).lower()
    symbol = str(metadata.get("symbol", "")).lower()
    categories = [_normalize_text(value) for value in (metadata.get("categories") or [])]

    if asset_id in {value.lower() for value in universe_config.stablecoin_ids}:
        return True
    if asset_id in {value.lower() for value in universe_config.excluded_ids}:
        return True
    if any(keyword.lower() in name for keyword in universe_config.name_exclusion_keywords):
        return True
    if any(keyword.lower() in symbol for keyword in universe_config.symbol_exclusion_keywords):
        return True
    category_keywords = {_normalize_text(value) for value in universe_config.category_exclusion_keywords}
    if any(
        category == keyword or category.startswith(f"{keyword} ")
        for category in categories
        for keyword in category_keywords
    ):
        return True
    return False
