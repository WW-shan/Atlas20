"""Tests for the independent finalist selection / universe audit."""

from __future__ import annotations

import json

import pandas as pd
import pytest

import scripts.audit_finalist_selections as audit
from atlas20.config import load_config


def test_cmc_id_map_reads_cache_and_aliases(tmp_path) -> None:
    """The symbol -> CMC id map must mirror the processor, aliases included."""
    raw = tmp_path / "raw" / "coinmarketcap"
    raw.mkdir(parents=True)
    (raw / "id_map.json").write_text(json.dumps({"BTC": 1, "ETH": 1027}), encoding="utf-8")

    config = load_config("config/base.yaml")
    config = config.model_copy(deep=True)
    config.paths.raw_dir = str(tmp_path / "raw")

    mapping = audit._cmc_id_map(config)

    assert mapping["BTC"] == 1
    assert mapping["ETH"] == 1027


def test_raw_market_caps_reads_provider_payload(tmp_path) -> None:
    """Market caps come from the raw payload, keyed on the tz-naive close date."""
    history = tmp_path / "raw" / "coinmarketcap" / "history"
    history.mkdir(parents=True)
    (tmp_path / "raw" / "coinmarketcap" / "id_map.json").write_text(
        json.dumps({"BTC": 1}), encoding="utf-8"
    )
    (history / "1_0_0.json").write_text(
        json.dumps(
            [
                {
                    "timeClose": "2024-01-02T23:59:59.999Z",
                    "quote": {"marketCap": 1000.0},
                },
                {
                    "timeClose": "2024-01-03T23:59:59.999Z",
                    "quote": {"marketCap": 2000.0},
                },
            ]
        ),
        encoding="utf-8",
    )

    config = load_config("config/base.yaml")
    config = config.model_copy(deep=True)
    config.paths.raw_dir = str(tmp_path / "raw")

    frame = audit._raw_market_caps(config, {"bitcoin": "BTC"})

    assert list(frame.columns) == ["bitcoin"]
    # The provider stamps closes in UTC; the index must be a naive date or every
    # lookup against the panel silently misses.
    assert frame.index.tz is None
    assert frame.loc[pd.Timestamp("2024-01-03"), "bitcoin"] == pytest.approx(2000.0)


def test_raw_market_caps_skips_unknown_symbols(tmp_path, capsys) -> None:
    history = tmp_path / "raw" / "coinmarketcap" / "history"
    history.mkdir(parents=True)
    (tmp_path / "raw" / "coinmarketcap" / "id_map.json").write_text(
        json.dumps({"BTC": 1}), encoding="utf-8"
    )
    (history / "1_0_0.json").write_text(
        json.dumps([{"timeClose": "2024-01-02T00:00:00.000Z", "quote": {"marketCap": 5.0}}]),
        encoding="utf-8",
    )
    config = load_config("config/base.yaml")
    config = config.model_copy(deep=True)
    config.paths.raw_dir = str(tmp_path / "raw")

    frame = audit._raw_market_caps(config, {"bitcoin": "BTC", "mystery": "NOPE"})

    assert list(frame.columns) == ["bitcoin"]
    assert "mystery" in capsys.readouterr().out


def test_default_output_dir_isolates_custom_windows(tmp_path) -> None:
    """A custom audit window must not overwrite the canonical 2021 report."""
    config = load_config("config/base.yaml")
    config = config.model_copy(deep=True)
    config.paths.reports_dir = str(tmp_path / "reports" / "latest")

    assert audit._default_output_dir(config, None, None) == (
        tmp_path / "reports" / "bull_offense_finalist"
    )
    assert audit._default_output_dir(config, "2022-01-01", None) == (
        tmp_path / "reports" / "bull_offense_finalist_2022"
    )
    assert audit._default_output_dir(config, "2022-03-15", "2022-06-30") == (
        tmp_path / "reports" / "bull_offense_finalist_2022-03-15_to_2022-06-30"
    )

