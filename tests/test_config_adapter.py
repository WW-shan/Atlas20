from pathlib import Path

import pytest

from atlas20.api.config_adapter import to_research_config
from atlas20.api.schemas import BacktestConfig
from atlas20.api.settings import Settings
from atlas20.config import ResearchConfig


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def valid_config(**overrides) -> BacktestConfig:
    data = {
        "preset": "ATLAS Adaptive v3",
        "universe": {"topN": 20, "excludeStable": True, "excludeWrapped": True},
        "window": {"start": "2024-01-01", "end": "2026-05-18", "rebalance": "Weekly"},
        "allocation": {"positionPct": 5.0, "slots": 10},
        "costs": {"feeBps": 10, "slippageBps": 5},
    }
    for section, values in overrides.items():
        if isinstance(values, dict) and isinstance(data.get(section), dict):
            data[section] = {**data[section], **values}
        else:
            data[section] = values
    return BacktestConfig.model_validate(data)


def settings(project_root: Path = PROJECT_ROOT) -> Settings:
    return Settings(project_root=project_root)


def test_to_research_config_maps_api_fields_to_engine_config():
    api_config = valid_config(
        universe={"topN": 12, "excludeStable": False, "excludeWrapped": False},
        window={"start": "2022-01-01", "end": "2024-12-31", "rebalance": "Weekly"},
        costs={"feeBps": 12.5, "slippageBps": 3.5},
    )

    config = to_research_config(api_config, api_config.preset, settings())

    assert isinstance(config, ResearchConfig)
    assert config.universe.universe_size == 12
    assert config.universe.stablecoin_ids == []
    assert config.universe.exclude_wrapped_assets is False
    assert config.start_date == "2022-01-01"
    assert config.end_date == "2024-12-31"
    assert config.rebalancing.frequencies == {"weekly": "7D"}
    assert config.frictions.fee_bps == 12.5
    assert config.frictions.slippage_bps == 3.5
    assert config.project_root == PROJECT_ROOT


def test_to_research_config_keeps_base_stablecoin_ids_when_exclude_stable_true():
    api_config = valid_config(universe={"excludeStable": True})

    config = to_research_config(api_config, api_config.preset, settings())

    assert "tether" in config.universe.stablecoin_ids


def test_to_research_config_missing_preset_yaml_falls_back_to_base():
    api_config = valid_config(preset="does not exist")

    config = to_research_config(api_config, api_config.preset, settings())

    assert config.project_name == "Atlas20 Rotation"
    assert config.paths.processed_dir == "data/processed"


def test_config_adapter_raises_when_base_yaml_missing(tmp_path: Path):
    api_config = valid_config(preset="does not exist")

    with pytest.raises(ValueError, match="base.yaml"):
        to_research_config(api_config, api_config.preset, settings(tmp_path))


def test_to_research_config_loads_slugged_preset_file():
    api_config = valid_config(preset="Five Year 2020 2024")

    config = to_research_config(api_config, api_config.preset, settings())

    assert config.project_name == "Atlas20 Rotation - Five Year Window (2020-2024)"
    assert config.paths.processed_dir == "data/processed/five_year_2020_2024"


def test_to_research_config_position_pct_maps_to_decimal_weight():
    api_config = valid_config(allocation={"positionPct": 35.0})

    config = to_research_config(api_config, api_config.preset, settings())

    assert config.frictions.max_weight_per_coin == 0.35


def test_to_research_config_biweekly_rebalance_uses_single_frequency_entry():
    api_config = valid_config(window={"rebalance": "Biweekly"})

    config = to_research_config(api_config, api_config.preset, settings())

    assert config.rebalancing.frequencies == {"biweekly": "14D"}


def test_to_research_config_constrains_strategy_frequencies_to_chosen_cadence():
    """Engine iterates strategies.momentum_frequencies and looks each up in
    rebalancing.frequencies. If a strategies list still has 'biweekly' while
    the chosen cadence dict only contains 'monthly', the unmatched lookup
    falls through to the bare key and crashes calendar.py with
    int('biweekly'). Adapter must constrain both strategy lists.
    """
    for rebalance, expected_key in [("Weekly", "weekly"), ("Biweekly", "biweekly"), ("Monthly", "monthly")]:
        api_config = valid_config(window={"rebalance": rebalance})

        config = to_research_config(api_config, api_config.preset, settings())

        assert config.strategies.momentum_frequencies == [expected_key], rebalance
        assert config.strategies.sector_frequencies == [expected_key], rebalance
        assert expected_key in config.rebalancing.frequencies, rebalance


def test_to_research_config_rejects_empty_preset_slug():
    api_config = valid_config()

    with pytest.raises(ValueError, match="invalid preset slug"):
        to_research_config(api_config, "!!!", settings())


def test_to_research_config_wraps_yaml_parse_errors(tmp_path: Path):
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "base.yaml").write_text("project_name: [unterminated\n", encoding="utf-8")
    api_config = valid_config(preset="missing")

    with pytest.raises(ValueError, match="failed to parse config YAML"):
        to_research_config(api_config, api_config.preset, settings(tmp_path))
