"""Adapter from API backtest config to engine research config."""

from __future__ import annotations

import logging
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from atlas20.api.schemas import BacktestConfig
from atlas20.api.settings import Settings
from atlas20.config import ResearchConfig
from atlas20.strategies.implementations import build_strategy_definitions

logger = logging.getLogger(__name__)

_REBALANCE_FREQUENCIES = {
    "Weekly": {"weekly": "7D"},
    "Biweekly": {"biweekly": "14D"},
    "Monthly": {"monthly": "month_end"},
}

# Complete lookup table preserved across user choice. Hardcoded benchmark and
# equal-weight strategies in strategies/implementations.py use
# `frequency="monthly"`; if the user picks Weekly the engine still has to be
# able to resolve "monthly" -> "month_end" or calendar.py crashes with
# "Unsupported rebalance frequency: monthly=monthly". The user choice still
# governs WHICH rotation strategies run (momentum_frequencies /
# sector_frequencies below).
_ALL_REBALANCE_FREQUENCIES: dict[str, str] = {
    key: value
    for freq_map in _REBALANCE_FREQUENCIES.values()
    for key, value in freq_map.items()
}

# Run kinds the worker executes as internal jobs (worker/run_one.py). A backtest
# with one of these as its preset would run as that job, e.g. a real external
# data refresh that skips /api/universe/refresh's rate limit and dedupe.
RESERVED_PRESETS = frozenset({"universe_refresh"})
_PRESET_SLUG_UNSAFE = re.compile(r"[^a-z0-9_]+")
# Shared config/*.yaml inputs that are not runnable presets.
NON_PRESET_CONFIGS = frozenset({"sectors"})
BASE_PRESET = "base"


def validate_preset(preset: str, settings: Settings) -> None:
    """Submission-time check: raise ValueError unless ``preset`` names one of known_presets()."""
    preset_slug = _preset_slug(preset)
    if preset_slug in RESERVED_PRESETS:
        raise ValueError(f"preset {_quoted(preset)} is reserved for internal runs")
    if preset_slug not in {_preset_slug(known) for known in known_presets(settings)}:
        raise ValueError(_unknown_preset_message(preset, settings.project_root))


def known_presets(settings: Settings) -> list[str]:
    """Presets a backtest may request: runnable config/*.yaml presets, then base.yaml strategy names."""
    presets = _config_presets(settings.project_root)
    base = settings.project_root / "config" / f"{BASE_PRESET}.yaml"
    if base.is_file():
        presets.extend(sorted(_strategy_names(_load_yaml(base), settings.project_root)))
    return presets


def to_research_config(api_config: BacktestConfig, preset: str, settings: Settings) -> ResearchConfig:
    """Build the engine config for a preset. Reserved presets always raise ValueError.

    Also used for runs already stored, which the old adapter accepted with any
    preset and ran on base.yaml, so an unknown preset still resolves to
    base.yaml here. New submissions must pass validate_preset first.
    """
    requested = preset or api_config.preset
    preset_slug = _preset_slug(requested)
    config_path = _config_path(settings.project_root, preset_slug, requested)
    raw = _load_yaml(config_path)
    strategy_slugs = {_preset_slug(name) for name in _strategy_names(raw, settings.project_root)}
    if config_path.stem != preset_slug and preset_slug not in strategy_slugs:
        logger.warning("Preset %r is not a known preset; resolving it to config/base.yaml", requested[:80])
    data = deepcopy(raw)

    stablecoin_ids = data["universe"].get("stablecoin_ids", [])
    data["universe"]["universe_size"] = api_config.universe.topN
    data["universe"]["stablecoin_ids"] = stablecoin_ids if api_config.universe.excludeStable else []
    data["universe"]["exclude_wrapped_assets"] = api_config.universe.excludeWrapped
    data["start_date"] = api_config.window.start.isoformat()
    data["end_date"] = api_config.window.end.isoformat()
    chosen_frequencies = _rebalance_frequencies(api_config.window.rebalance)
    # Keep the chosen cadence plus the benchmarks' hardcoded "monthly" sampling
    # so calendar.py never falls back to a bare key. We do NOT carry every
    # default cadence: pipeline.py iterates rebalancing.frequencies when
    # generating the union rebalance schedule, and the universe builder would
    # waste work materializing snapshots for cadences no live strategy uses.
    benchmark_frequencies = {"monthly": _ALL_REBALANCE_FREQUENCIES["monthly"]}
    data["rebalancing"]["frequencies"] = {**benchmark_frequencies, **chosen_frequencies}
    # The engine iterates strategies.momentum_frequencies / sector_frequencies
    # and creates one strategy variant per name. Constraining both lists to
    # the chosen cadence is what actually expresses the user's choice for
    # rotation strategies; benchmarks stay on their hardcoded "monthly"
    # cadence (sampling, not rebalancing).
    chosen_freq_key = next(iter(chosen_frequencies))
    data.setdefault("strategies", {})
    data["strategies"]["momentum_frequencies"] = [chosen_freq_key]
    data["strategies"]["sector_frequencies"] = [chosen_freq_key]
    # Note: positionPct is interpreted as percent -> decimal via /100, with no
    # rounding. For positionPct=33.33, max_weight_per_coin becomes 0.3333.
    # Downstream consumers should be precision-tolerant.
    data["frictions"]["max_weight_per_coin"] = api_config.allocation.positionPct / 100
    data["frictions"]["fee_bps"] = api_config.costs.feeBps
    data["frictions"]["slippage_bps"] = api_config.costs.slippageBps
    data["project_root"] = settings.project_root

    return ResearchConfig.model_validate(data)


def _preset_slug(preset: str) -> str:
    slug = _PRESET_SLUG_UNSAFE.sub("_", preset.lower()).strip("_")
    if not slug:
        raise ValueError("invalid preset slug")
    return slug


def _config_presets(project_root: Path) -> list[str]:
    # Only slug-named files: _config_path looks presets up as config/<slug>.yaml.
    config_dir = project_root / "config"
    if not config_dir.is_dir():
        return []
    return [
        path.stem
        for path in sorted(config_dir.glob("*.yaml"))
        if path.is_file()
        and _PRESET_SLUG_UNSAFE.sub("_", path.stem.lower()).strip("_") == path.stem
        and path.stem not in NON_PRESET_CONFIGS
        and path.stem not in RESERVED_PRESETS
    ]


def _config_path(project_root: Path, preset_slug: str, requested: str) -> Path:
    if preset_slug in RESERVED_PRESETS:
        raise ValueError(f"preset {_quoted(requested)} is reserved for internal runs")
    if preset_slug in NON_PRESET_CONFIGS:
        # Loading a shared config as a preset used to crash with KeyError (a 500).
        raise ValueError(_unknown_preset_message(requested, project_root))
    config_dir = project_root / "config"
    candidate = config_dir / f"{preset_slug}.yaml"
    if candidate.is_file():
        return candidate
    base = config_dir / f"{BASE_PRESET}.yaml"
    if not base.exists():
        raise ValueError(f"base config 'config/base.yaml' not found at {project_root}")
    # Strategy-name presets run base.yaml; callers check the name against the
    # strategies base.yaml defines.
    return base


def _strategy_names(raw: dict[str, Any], project_root: Path) -> set[str]:
    # /api/options offers report strategy names as presets. They run base.yaml
    # and select that strategy's metrics, so a name is known when this config
    # defines it under any cadence the API offers. Being static, the set does
    # not move with reports/latest, so queued runs stay valid for the worker.
    data = deepcopy(raw)
    cadences = list(_ALL_REBALANCE_FREQUENCIES)
    data.setdefault("strategies", {})
    data["strategies"]["momentum_frequencies"] = cadences
    data["strategies"]["sector_frequencies"] = cadences
    data.setdefault("rebalancing", {})
    data["rebalancing"]["frequencies"] = dict(_ALL_REBALANCE_FREQUENCIES)
    data["project_root"] = project_root
    return {definition.name for definition in build_strategy_definitions(ResearchConfig.model_validate(data))}


def _unknown_preset_message(requested: str, project_root: Path) -> str:
    config_presets = ", ".join(_config_presets(project_root)) or "none"
    return (
        f"unknown preset {_quoted(requested)}: use a config preset ({config_presets}) "
        "or a strategy name defined by config/base.yaml"
    )


def _quoted(value: str, limit: int = 80) -> str:
    return repr(value if len(value) <= limit else value[:limit] + "...")


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
