"""Adapter from API backtest config to engine research config."""

from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from atlas20.api.schemas import BacktestConfig
from atlas20.api.settings import Settings
from atlas20.config import ResearchConfig

_REBALANCE_FREQUENCIES = {
    "Weekly": {"weekly": "7D"},
    "Biweekly": {"biweekly": "14D"},
    "Monthly": {"monthly": "month_end"},
}


def to_research_config(api_config: BacktestConfig, preset: str, settings: Settings) -> ResearchConfig:
    preset_slug = _preset_slug(preset or api_config.preset)
    config_path = _config_path(settings.project_root, preset_slug)
    raw = _load_yaml(config_path)
    data = deepcopy(raw)

    stablecoin_ids = data["universe"].get("stablecoin_ids", [])
    data["universe"]["universe_size"] = api_config.universe.topN
    data["universe"]["stablecoin_ids"] = stablecoin_ids if api_config.universe.excludeStable else []
    data["universe"]["exclude_wrapped_assets"] = api_config.universe.excludeWrapped
    data["start_date"] = api_config.window.start.isoformat()
    data["end_date"] = api_config.window.end.isoformat()
    data["rebalancing"]["frequencies"] = _rebalance_frequencies(api_config.window.rebalance)
    # Note: positionPct is interpreted as percent -> decimal via /100, with no
    # rounding. For positionPct=33.33, max_weight_per_coin becomes 0.3333.
    # Downstream consumers should be precision-tolerant.
    data["frictions"]["max_weight_per_coin"] = api_config.allocation.positionPct / 100
    data["frictions"]["fee_bps"] = api_config.costs.feeBps
    data["frictions"]["slippage_bps"] = api_config.costs.slippageBps
    data["project_root"] = settings.project_root

    return ResearchConfig.model_validate(data)


def _preset_slug(preset: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", preset.lower()).strip("_")
    if not slug:
        raise ValueError("invalid preset slug")
    return slug


def _config_path(project_root: Path, preset_slug: str) -> Path:
    config_dir = project_root / "config"
    candidate = config_dir / f"{preset_slug}.yaml"
    if candidate.exists():
        return candidate
    base = config_dir / "base.yaml"
    if not base.exists():
        raise ValueError(f"base config 'config/base.yaml' not found at {project_root}")
    return base


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        raise ValueError(f"failed to parse config YAML: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"config YAML must be a mapping: {path}")
    return data


def _rebalance_frequencies(rebalance: str) -> dict[str, str]:
    frequencies = _REBALANCE_FREQUENCIES.get(rebalance)
    if frequencies is None:
        raise ValueError(f"inconsistent rebalance frequency mapping: {rebalance}")
    return dict(frequencies)
