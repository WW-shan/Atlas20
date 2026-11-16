from __future__ import annotations

import pandas as pd
import pytest

from scripts.audit_signal_equivalence import (
    _compare_target_ledgers,
    _latest_action_execution_issues,
    _manifest_execution_model_issues,
)


def _ledger(weight: float = -0.25) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "signal_date": "2026-11-06 00:00:00+00:00",
                "execution_hint": "2026-11-07 03:00:00+00:00",
                "asset": "ethereum",
                "side": "short",
                "target_weight": weight,
                "change_weight": weight,
                "action": "OPEN",
            }
        ]
    )


def test_manifest_execution_model_requires_market_fills() -> None:
    manifest = {
        "live_parity": True,
        "execution_price_model": "market_1h_open_floor",
        "fill_price_source": "bitget_market_1h_open",
        "fill_downgrade_count": 0,
        "market_fill_fingerprint": "sha256:market",
    }

    assert _manifest_execution_model_issues(manifest) == []

    manifest["fill_price_source"] = "bitget_mark_1h_open"
    manifest["execution_price_model"] = "mark_1h_open_floor"
    issues = _manifest_execution_model_issues(manifest)

    assert any("fill_price_source" in issue for issue in issues)
    assert any("execution_price_model" in issue for issue in issues)


def test_signal_equivalence_accepts_an_identical_signed_ledger() -> None:
    result = _compare_target_ledgers(_ledger(), _ledger())

    assert result["passed"] is True
    assert result["differing_rows"] == 0
    assert result["events_only_in_frozen"] == []
    assert result["events_only_in_replay"] == []


def test_signal_equivalence_rejects_a_changed_short_weight() -> None:
    result = _compare_target_ledgers(_ledger(), _ledger(-0.20))

    assert result["passed"] is False
    assert result["differing_rows"] == 1
    assert result["differences"][0]["asset"] == "ethereum"
    assert result["differences"][0]["max_weight_delta"] == pytest.approx(0.05)


def test_latest_signal_actions_must_reach_the_replay_trade_ledger() -> None:
    targets = _ledger()
    trades = pd.DataFrame(
        [
            {
                "timestamp": "2026-11-07 02:00:00+00:00",
                "asset": "ethereum",
                "side": "short",
                "action": "open",
            }
        ]
    )
    positions = pd.DataFrame(
        [
            {
                "timestamp": "2026-11-07 02:00:00+00:00",
                "asset": "ethereum",
                "side": "short",
            }
        ]
    )

    assert _latest_action_execution_issues(targets, trades, positions=positions) == []

    missing = _latest_action_execution_issues(
        targets,
        pd.DataFrame(columns=["timestamp", "asset", "side", "action"]),
        positions=pd.DataFrame(),
    )

    assert missing
    assert "ethereum" in missing[0]


def test_latest_signal_action_can_be_an_explicit_venue_minimum_skip() -> None:
    targets = _ledger()
    skips = pd.DataFrame(
        [
            {
                "timestamp": "2026-11-07 02:00:00+00:00",
                "asset": "ethereum",
                "action": "open",
                "reason": "below_venue_minimum",
            }
        ]
    )

    assert (
        _latest_action_execution_issues(
            targets,
            pd.DataFrame(columns=["timestamp", "asset", "side", "action"]),
            positions=pd.DataFrame(),
            order_skips=skips,
        )
        == []
    )


def test_latest_action_execution_matches_the_0100_floor_bar() -> None:
    targets = _ledger()
    targets.loc[0, "execution_hint"] = "2026-11-07 01:05:00+00:00"
    trades = pd.DataFrame(
        [
            {
                "timestamp": "2026-11-07 01:00:00+00:00",
                "asset": "ethereum",
                "side": "short",
                "action": "open",
            }
        ]
    )
    positions = pd.DataFrame(
        [
            {
                "timestamp": "2026-11-07 01:00:00+00:00",
                "asset": "ethereum",
                "side": "short",
            }
        ]
    )

    assert _latest_action_execution_issues(targets, trades, positions) == []


def test_latest_action_execution_rejects_a_previous_hour_trade() -> None:
    targets = _ledger()
    targets.loc[0, "execution_hint"] = "2026-11-07 01:05:00+00:00"
    trades = pd.DataFrame(
        [
            {
                "timestamp": "2026-11-07 00:00:00+00:00",
                "asset": "ethereum",
                "side": "short",
                "action": "open",
            }
        ]
    )
    positions = pd.DataFrame(
        [
            {
                "timestamp": "2026-11-07 00:00:00+00:00",
                "asset": "ethereum",
                "side": "short",
            }
        ]
    )

    issues = _latest_action_execution_issues(targets, trades, positions)

    assert issues
    assert "no replay trade" in issues[0]


def test_latest_action_execution_rejects_a_later_trade() -> None:
    targets = _ledger()
    targets.loc[0, "execution_hint"] = "2026-11-07 01:05:00+00:00"
    trades = pd.DataFrame(
        [
            {
                "timestamp": "2026-11-07 02:00:00+00:00",
                "asset": "ethereum",
                "side": "short",
                "action": "open",
            }
        ]
    )
    positions = pd.DataFrame(
        [
            {
                "timestamp": "2026-11-07 02:00:00+00:00",
                "asset": "ethereum",
                "side": "short",
            }
        ]
    )

    issues = _latest_action_execution_issues(targets, trades, positions)

    assert issues
    assert "no replay trade" in issues[0]
