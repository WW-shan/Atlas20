from __future__ import annotations

import json

import pandas as pd
import pytest

from atlas20.derivatives.execution import ContractSpec
from atlas20.derivatives.live_journal import (
    JournalEntry,
    latest_short_quantities,
    protected_short_stops,
    protected_short_symbols,
)
from scripts.audit_live_track import (
    _active_event_state_issues,
    _event_quantity_issues,
    _execution_floor_issue,
    _ledger_expected_equity,
    _orphan_strategy_order_issues,
    _pnl_chain_errors,
    _position_data_issues,
    _position_signed_notional,
    _position_side_issues,
    _position_short_stop_expectations,
    _short_stop_duplicate_issues,
    _short_stop_liquidation_issues,
    _position_target_issues,
    _short_stop_gaps,
    _strategy_stop_history_issues,
    _short_stop_expectation_gaps,
    _state_track_issue,
    _target_hash_audit,
    _trade_mismatch,
    _unfilled_order_issues,
)


def test_state_track_guard_rejects_missing_and_cross_track_keys() -> None:
    spec = "PR2026-11-LS104-H5-LS23-PROFITLOCK-STRONGER21-S050-G175-M090"

    assert _state_track_issue({}, spec) is not None
    assert "last_key" in str(_state_track_issue({"last_status": "ok"}, spec))
    cross_track = {
        "last_key": "PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21|old"
    }
    issue = _state_track_issue(cross_track, spec)
    assert issue is not None
    assert "other track" in issue or "其他 track" in issue
    valid_key = f"{spec}|2026-11-13|target|2026-11-15"
    assert _state_track_issue(
        {"last_key": valid_key, "runs": [{"key": valid_key}]},
        spec,
    ) is None


def test_state_track_guard_rejects_cross_track_run_history() -> None:
    spec = "PR2026-11-LS104-H5-LS23-PROFITLOCK-STRONGER21-S050-G175-M090"
    current = f"{spec}|2026-11-13|target-a|2026-11-15"

    issue = _state_track_issue(
        {
            "last_key": current,
            "runs": [
                {"key": current},
                {
                    "key": (
                        "PR2026-11-LS45-H5-LS23-PROFITLOCK-STRONGER21"
                        "|2026-11-13|target-b|2026-11-15"
                    )
                },
            ],
        },
        spec,
    )

    assert issue is not None
    assert "runs[1]" in issue


def test_target_hash_audit_is_hard_when_the_manifest_omits_the_hash(tmp_path) -> None:
    targets = tmp_path / "oos_targets.csv"
    targets.write_text("asset,target_weight\nnear,-0.1\n", encoding="utf-8")

    ok, detail, hard = _target_hash_audit(
        {"targets_file": targets.name},
        targets,
    )

    assert ok is False
    assert hard is True
    assert "targets_sha256" in detail


def test_execution_floor_issue_rejects_equity_below_the_live_minimum() -> None:
    assert _execution_floor_issue(20.0, floor_usdt=20.0) is None
    assert "执行下限" in str(_execution_floor_issue(19.99, floor_usdt=20.0))


def _hyperliquid_spec() -> ContractSpec:
    return ContractSpec(
        symbol="HYPEUSDT",
        min_order_qty=0.01,
        quantity_multiplier=0.01,
        min_order_usdt=5.0,
        quantity_precision=2,
        price_multiplier=0.001,
        price_precision=3,
    )


def test_target_drift_is_allowed_when_the_minimum_order_would_move_further_away() -> None:
    equity = 503.59357169
    price = 66.089
    issues = _position_target_issues(
        targets={"hyperliquid": -31.47 / equity},
        signed_notional_by_asset={"hyperliquid": -30.37},
        equity=equity,
        lot_notional_by_asset={"hyperliquid": 0.01 * price},
        prices_by_asset={"hyperliquid": price},
        contract_specs_by_asset={"hyperliquid": _hyperliquid_spec()},
    )

    assert issues == []


def test_target_drift_still_fails_when_a_tradeable_order_would_reduce_the_gap() -> None:
    equity = 503.59357169
    price = 66.089
    issues = _position_target_issues(
        targets={"hyperliquid": -31.47 / equity},
        signed_notional_by_asset={"hyperliquid": -20.0},
        equity=equity,
        lot_notional_by_asset={"hyperliquid": 0.01 * price},
        prices_by_asset={"hyperliquid": price},
        contract_specs_by_asset={"hyperliquid": _hyperliquid_spec()},
    )

    assert issues
    assert "HYPERLIQUID" in issues[0]


def test_short_stop_expectation_is_independent_of_the_journal_value() -> None:
    expectations = _position_short_stop_expectations(
        [
            {
                "symbol": "HYPEUSDT",
                "total": "0.46",
                "posSide": "short",
                "avgPrice": "67.308",
            }
        ],
        specs_by_symbol={"HYPEUSDT": _hyperliquid_spec()},
        short_stop_loss_pct=0.20,
    )

    assert expectations == {"HYPEUSDT": pytest.approx(80.77)}


def test_position_audit_requires_entry_price_for_short_stop_recomputation() -> None:
    issues = _position_data_issues(
        [
            {
                "symbol": "HYPEUSDT",
                "total": "0.46",
                "posSide": "short",
                "markPrice": "66.04",
            }
        ]
    )

    assert issues
    assert "avgPrice" in issues[0]


def test_short_stop_audit_rejects_a_missing_live_contract_spec() -> None:
    gaps = _short_stop_expectation_gaps(
        [
            {
                "symbol": "HYPEUSDT",
                "total": "0.46",
                "posSide": "short",
                "avgPrice": "67.308",
            }
        ],
        expected_stops={},
    )

    assert gaps == ["HYPEUSDT"]


def _entry(
    *,
    date: str,
    equity: float,
    capital_flow: float,
    day_pnl: float,
) -> JournalEntry:
    return JournalEntry(
        date=date,
        run_at_utc=f"{date}T03:06:00+00:00",
        signal_date=date,
        equity=equity,
        position_value=0.0,
        cash=equity,
        day_pnl=day_pnl,
        day_return=0.0,
        fees_today=0.0,
        funding_total=0.0,
        unrealised_pnl=0.0,
        capital_flow=capital_flow,
    )


def test_ledger_expected_equity_includes_flow_after_the_latest_snapshot() -> None:
    last = {
        "equity": 99.68,
        "positions": json.dumps([]),
    }

    expected, mismatches = _ledger_expected_equity(
        last,
        current_positions=[],
        capital_flow=400.0,
    )

    assert expected == pytest.approx(499.68)
    assert mismatches == []


def test_pnl_chain_excludes_capital_flow_from_strategy_performance() -> None:
    journal = pd.DataFrame(
        [
            _entry(date="2026-11-03", equity=99.68, capital_flow=0.0, day_pnl=0.0).as_row(),
            _entry(date="2026-11-04", equity=499.68, capital_flow=400.0, day_pnl=0.0).as_row(),
        ]
    )

    assert _pnl_chain_errors(journal) == []


def test_ledger_expected_equity_marks_a_short_in_the_adverse_direction() -> None:
    last = {
        "equity": 100.0,
        "positions": json.dumps(
            [{"symbol": "NEARUSDT", "side": "short", "mark_price": 5.0}]
        ),
    }

    expected, mismatches = _ledger_expected_equity(
        last,
        current_positions=[
            {"symbol": "NEARUSDT", "total": "20", "posSide": "short", "markPrice": "5.5"}
        ],
        capital_flow=0.0,
    )

    assert expected == pytest.approx(90.0)
    assert mismatches == []


def test_ledger_expected_equity_rejects_a_side_flip_since_the_snapshot() -> None:
    last = {
        "equity": 100.0,
        "positions": json.dumps(
            [{"symbol": "NEARUSDT", "side": "long", "mark_price": 5.0}]
        ),
    }

    _, mismatches = _ledger_expected_equity(
        last,
        current_positions=[
            {"symbol": "NEARUSDT", "total": "20", "posSide": "short", "markPrice": "5.0"}
        ],
        capital_flow=0.0,
    )

    assert any("方向" in item for item in mismatches)


def test_ledger_expected_equity_reports_malformed_position_json() -> None:
    expected, mismatches = _ledger_expected_equity(
        {"equity": 100.0, "positions": "not-json"},
        current_positions=[],
        capital_flow=0.0,
    )

    assert expected == pytest.approx(100.0)
    assert any("positions" in item for item in mismatches)


def test_position_signed_notional_preserves_hedge_and_one_way_shorts() -> None:
    assert _position_signed_notional(
        {"total": "20", "posSide": "short", "markPrice": "5"}
    ) == pytest.approx(-100.0)
    assert _position_signed_notional(
        {"total": "-20", "posSide": "net", "markPrice": "5"}
    ) == pytest.approx(-100.0)
    assert _position_signed_notional(
        {"total": "20", "posSide": "long", "markPrice": "5"}
    ) == pytest.approx(100.0)


def test_protected_short_symbols_requires_a_recorded_stop() -> None:
    journal = pd.DataFrame(
        [
            {
                "trades": json.dumps(
                    [
                        {"symbol": "NEARUSDT", "side": "sell", "stop_loss": 6.0},
                        {"symbol": "SOLUSDT", "side": "sell", "stop_loss": None},
                    ]
                )
            }
        ]
    )

    assert protected_short_symbols(journal) == {"NEARUSDT"}
    assert protected_short_stops(journal) == {"NEARUSDT": 6.0}


def test_protected_short_stops_prefers_the_normalized_venue_stop() -> None:
    journal = pd.DataFrame(
        [
            {
                "trades": json.dumps(
                    [
                        {
                            "symbol": "NEARUSDT",
                            "position_side": "short",
                            "action": "OPEN",
                            "side": "sell",
                            "qty": 10.0,
                            "stop_loss": 6.0,
                            "requested_stop_loss": 6.0,
                            "normalized_stop_loss": 6.6,
                            "stop_trigger_by": "mark",
                            "stop_order_type": "market",
                        }
                    ]
                )
            }
        ]
    )

    assert protected_short_stops(journal) == {"NEARUSDT": 6.6}


def test_protected_short_stops_refreshes_from_a_quiet_position_snapshot() -> None:
    journal = pd.DataFrame(
        [
            {
                "trades": json.dumps(
                    [
                        {
                            "symbol": "NEARUSDT",
                            "position_side": "short",
                            "action": "OPEN",
                            "side": "sell",
                            "qty": 10.0,
                            "stop_loss": 6.0,
                            "requested_stop_loss": 6.0,
                            "normalized_stop_loss": 6.6,
                            "stop_trigger_by": "mark",
                            "stop_order_type": "market",
                        }
                    ]
                ),
                "positions": json.dumps(
                    [
                        {
                            "symbol": "NEARUSDT",
                            "side": "short",
                            "qty": 10.0,
                            "normalized_stop_loss": 6.6,
                        }
                    ]
                ),
            },
            {
                "trades": json.dumps([]),
                "positions": json.dumps(
                    [
                        {
                            "symbol": "NEARUSDT",
                            "side": "short",
                            "qty": 10.0,
                            "normalized_stop_loss": 6.7,
                        }
                    ]
                ),
            },
        ]
    )

    assert protected_short_stops(journal) == {"NEARUSDT": 6.7}


def test_external_close_ends_the_old_short_cycle_before_a_reopen() -> None:
    journal = pd.DataFrame(
        [
            {
                "trades": json.dumps(
                    [
                        {
                            "symbol": "NEARUSDT",
                            "position_side": "short",
                            "action": "OPEN",
                            "side": "sell",
                            "qty": 10.0,
                            "stop_loss": 6.0,
                            "requested_stop_loss": 6.0,
                            "stop_trigger_by": "mark",
                            "stop_order_type": "market",
                        },
                        {
                            "symbol": "NEARUSDT",
                            "position_side": "short",
                            "action": "EXTERNAL_CLOSE",
                            "side": "buy",
                            "qty": 10.0,
                        },
                    ]
                )
            },
            {
                "trades": json.dumps(
                    [
                        {
                            "symbol": "NEARUSDT",
                            "position_side": "short",
                            "action": "OPEN",
                            "side": "sell",
                            "qty": 10.0,
                            "stop_loss": 7.0,
                            "requested_stop_loss": 7.0,
                            "stop_trigger_by": "mark",
                            "stop_order_type": "market",
                        }
                    ]
                )
            },
        ]
    )

    assert protected_short_stops(journal) == {"NEARUSDT": 7.0}


def test_protected_short_symbols_survives_a_quiet_hold_day() -> None:
    journal = pd.DataFrame(
        [
            {
                "date": "2026-11-13",
                "trades": json.dumps(
                    [
                        {
                            "symbol": "NEARUSDT",
                            "position_side": "short",
                            "action": "OPEN",
                            "side": "sell",
                            "qty": 10.0,
                            "stop_loss": 6.0,
                            "stop_trigger_by": "mark",
                            "stop_order_type": "market",
                        }
                    ]
                ),
                "positions": json.dumps(
                    [{"symbol": "NEARUSDT", "side": "short"}]
                ),
            },
            {
                "date": "2026-11-14",
                "trades": "[]",
                "positions": json.dumps(
                    [{"symbol": "NEARUSDT", "side": "short"}]
                ),
            },
        ]
    )

    assert protected_short_symbols(journal) == {"NEARUSDT"}


def test_old_stop_does_not_mask_an_unprotected_reopened_short() -> None:
    journal = pd.DataFrame(
        [
            {
                "date": "2026-11-10",
                "trades": json.dumps(
                    [
                        {
                            "symbol": "NEARUSDT",
                            "position_side": "short",
                            "action": "OPEN",
                            "side": "sell",
                            "qty": 10.0,
                            "stop_loss": 6.0,
                            "stop_trigger_by": "mark",
                            "stop_order_type": "market",
                        }
                    ]
                ),
                "positions": json.dumps(
                    [{"symbol": "NEARUSDT", "side": "short"}]
                ),
            },
            {
                "date": "2026-11-11",
                "trades": json.dumps(
                    [
                        {
                            "symbol": "NEARUSDT",
                            "position_side": "short",
                            "action": "CLOSE",
                            "side": "buy",
                            "qty": 10.0,
                            "stop_loss": None,
                        }
                    ]
                ),
                "positions": "[]",
            },
            {
                "date": "2026-11-12",
                "trades": "[]",
                "positions": json.dumps(
                    [{"symbol": "NEARUSDT", "side": "short"}]
                ),
            },
        ]
    )

    assert protected_short_symbols(journal) == set()


def test_reopened_short_with_a_bad_new_stop_metadata_is_not_protected() -> None:
    journal = pd.DataFrame(
        [
            {
                "date": "2026-11-13",
                "trades": json.dumps(
                    [
                        {
                            "symbol": "NEARUSDT",
                            "position_side": "short",
                            "action": "OPEN",
                            "side": "sell",
                            "qty": 10.0,
                            "stop_loss": 6.0,
                            "stop_trigger_by": "last_price",
                            "stop_order_type": "market",
                        }
                    ]
                ),
                "positions": json.dumps(
                    [{"symbol": "NEARUSDT", "side": "short"}]
                ),
            }
        ]
    )

    assert protected_short_symbols(journal) == set()


def test_short_stop_must_match_the_requested_stop_price() -> None:
    journal = pd.DataFrame(
        [
            {
                "date": "2026-11-13",
                "trades": json.dumps(
                    [
                        {
                            "symbol": "NEARUSDT",
                            "position_side": "short",
                            "action": "OPEN",
                            "side": "sell",
                            "qty": 10.0,
                            "requested_stop_loss": 5.5,
                            "stop_loss": 6.0,
                            "stop_trigger_by": "mark",
                            "stop_order_type": "market",
                        }
                    ]
                ),
                "positions": json.dumps(
                    [{"symbol": "NEARUSDT", "side": "short"}]
                ),
            }
        ]
    )

    assert protected_short_symbols(journal) == set()


def test_unfilled_short_order_does_not_create_stop_protection() -> None:
    journal = pd.DataFrame(
        [
            {
                "date": "2026-11-13",
                "trades": json.dumps(
                    [
                        {
                            "symbol": "NEARUSDT",
                            "position_side": "short",
                            "action": "OPEN",
                            "side": "sell",
                            "qty": 0.0,
                            "status": "live",
                            "stop_loss": 6.0,
                            "stop_trigger_by": "mark",
                            "stop_order_type": "market",
                        }
                    ]
                ),
            }
        ]
    )

    assert protected_short_symbols(journal) == set()


def test_trade_mismatch_checks_the_attached_short_stop() -> None:
    trade = {
        "qty": 10.0,
        "avg_price": 5.0,
        "fee": 0.03,
        "stop_loss": 6.0,
    }
    venue = {
        "cumExecQty": "10",
        "avgPrice": "5",
        "feeDetail": [{"fee": "0.03"}],
        "stopLoss": "6",
        "slTriggerBy": "mark",
        "slOrderType": "market",
    }
    assert _trade_mismatch(trade, venue) is None

    venue["stopLoss"] = "5.8"
    mismatch = _trade_mismatch(trade, venue)
    assert mismatch is not None
    assert "止损" in mismatch


def test_trade_mismatch_allows_order_info_price_rounding_only_within_half_tick() -> None:
    trade = {
        "qty": 0.32,
        "avg_price": 208.15,
        "fee": 0.03996486,
    }
    venue = {
        "cumExecQty": "0.32",
        "avgPrice": "208.1503125",
        "feeDetail": [{"fee": "0.03996486"}],
    }

    assert _trade_mismatch(trade, venue, price_multiplier=0.01) is None
    assert _trade_mismatch(
        {**trade, "avg_price": 208.14},
        venue,
        price_multiplier=0.01,
    ) is not None


def test_open_short_requires_a_recorded_stop_trade() -> None:
    journal = pd.DataFrame(
        [
            {
                "date": "2026-11-13",
                "trades": json.dumps(
                    [
                        {
                            "symbol": "NEARUSDT",
                            "side": "sell",
                            "stop_loss": 6.0,
                        }
                    ]
                ),
            }
        ]
    )
    positions = [
        {"symbol": "NEARUSDT", "total": "10", "posSide": "short", "markPrice": "5"}
    ]

    assert _short_stop_gaps(journal, positions) == []

    journal.loc[0, "trades"] = json.dumps(
        [{"symbol": "NEARUSDT", "side": "sell", "stop_loss": None}]
    )
    assert _short_stop_gaps(journal, positions) == ["NEARUSDT"]


def test_journal_trade_rows_must_be_valid_objects() -> None:
    from scripts.audit_live_track import _journal_trade_rows

    assert _journal_trade_rows('[{"order_id": "1"}]') == [{"order_id": "1"}]
    with pytest.raises(ValueError, match="invalid JSON"):
        _journal_trade_rows("not-json")
    with pytest.raises(ValueError, match="array of objects"):
        _journal_trade_rows('["not-an-object"]')


def test_position_risk_checks_require_isolated_two_x_and_the_margin_buffer() -> None:
    from scripts.audit_live_track import _position_risk_issues

    positions = [
        {
            "symbol": "NEARUSDT",
            "total": "20",
            "posSide": "long",
            "markPrice": "5",
            "marginMode": "isolated",
            "leverage": "2",
            "positionBalance": "51.5",
        }
    ]
    assert _position_risk_issues(positions) == []

    positions[0]["marginMode"] = "crossed"
    positions[0]["leverage"] = "3"
    positions[0]["positionBalance"] = "40"
    issues = _position_risk_issues(positions)
    assert any("marginMode" in issue for issue in issues)
    assert any("leverage" in issue for issue in issues)
    assert any("margin" in issue for issue in issues)


def test_unknown_position_symbols_cannot_be_silently_dropped() -> None:
    from scripts.audit_live_track import _unknown_position_symbols

    assert _unknown_position_symbols(
        [{"symbol": "NEARUSDT"}, {"symbol": "MYSTERYUSDT"}],
        {"near": "NEARUSDT"},
    ) == ["MYSTERYUSDT"]


def test_account_audit_rejects_missing_or_non_numeric_core_fields() -> None:
    from scripts.audit_live_track import _account_data_issues

    issues = _account_data_issues(
        {
            "usdtEquity": "bad",
            "assets": [{"coin": "USDT", "balance": None}],
        }
    )

    assert any("usdtEquity" in issue for issue in issues)
    assert any("balance" in issue for issue in issues)


def test_account_audit_rejects_invalid_non_usdt_asset_value() -> None:
    from scripts.audit_live_track import _account_data_issues

    issues = _account_data_issues(
        {
            "usdtEquity": "100",
            "usdtUnrealisedPnl": "0",
            "positionValue": "0",
            "assets": [
                {"coin": "USDT", "balance": "100", "available": "100"},
                {"coin": "BGB", "balance": "1", "usdValue": "bad"},
            ],
        }
    )

    assert any("BGB" in issue and "usdValue" in issue for issue in issues)


def test_usdt_equivalent_balance_includes_non_usdt_collateral() -> None:
    from scripts.audit_live_track import _usdt_equivalent_balance

    balance = _usdt_equivalent_balance(
        {
            "assets": [
                {"coin": "USDT", "equity": "499.45972246", "usdValue": "498.97250755"},
                {"coin": "BGB", "equity": "0.10349572", "usdValue": "0.16973777"},
            ]
        }
    )

    assert balance == pytest.approx(499.62946023)


def test_account_identity_includes_isolated_position_margin() -> None:
    from scripts.audit_live_track import _account_identity_components

    assets = {
        "usdtEquity": "499.59468426",
        "usdtUnrealisedPnl": "0.0413",
        "assets": [
            {"coin": "USDT", "equity": "436.54408782"},
            {"coin": "BGB", "usdValue": "0.16642705"},
        ],
    }
    positions = [
        {
            "symbol": "ZECUSDT",
            "total": "0.035",
            "posSide": "short",
            "positionBalance": "16.00555047",
        },
        {
            "symbol": "HYPEUSDT",
            "total": "0.46",
            "posSide": "short",
            "positionBalance": "16.02101533",
        },
        {
            "symbol": "NEARUSDT",
            "total": "9",
            "posSide": "short",
            "positionBalance": "15.23275542",
        },
        {
            "symbol": "BCHUSDT",
            "total": "0.14",
            "posSide": "short",
            "positionBalance": "15.58343122",
        },
    ]

    equity, collateral, isolated, unrealised = _account_identity_components(
        assets, positions
    )

    assert equity == pytest.approx(499.59468426)
    assert collateral == pytest.approx(436.71051487)
    assert isolated == pytest.approx(62.84275244)
    assert unrealised == pytest.approx(0.0413)
    assert collateral + isolated + unrealised == pytest.approx(equity, abs=0.001)


def test_position_value_accepts_zero_assets_field_for_isolated_legs() -> None:
    from scripts.audit_live_track import _position_value_reconciliation

    positions = [
        {
            "symbol": "NEARUSDT",
            "total": "9",
            "posSide": "short",
            "markPrice": "3.2706",
            "marginMode": "isolated",
            "positionBalance": "15.23275542",
        }
    ]

    ok, detail = _position_value_reconciliation(0.0, 29.4354, positions)

    assert ok
    assert "positionValue=0" in detail
    assert "current-position" in detail


def test_ledger_equity_tolerance_allows_snapshot_noise_but_stays_bounded() -> None:
    from scripts.audit_live_track import _ledger_equity_tolerance

    assert _ledger_equity_tolerance(499.6) == pytest.approx(0.10)
    assert _ledger_equity_tolerance(1_000_000.0) == pytest.approx(200.0)


def test_position_audit_rejects_an_invalid_total_and_mark_price() -> None:
    from scripts.audit_live_track import _position_data_issues

    issues = _position_data_issues(
        [
            {"symbol": "NEARUSDT", "total": "bad", "markPrice": "5"},
            {"symbol": "TRXUSDT", "total": "10", "markPrice": "nan"},
            {"symbol": "SOLUSDT", "total": "10", "posSide": "side_typo", "markPrice": "5"},
        ]
    )

    assert any("NEARUSDT" in issue and "total" in issue for issue in issues)
    assert any("TRXUSDT" in issue and "markPrice" in issue for issue in issues)
    assert any("SOLUSDT" in issue and "posSide" in issue for issue in issues)


def test_position_audit_rejects_a_non_positive_mark_price() -> None:
    from scripts.audit_live_track import _position_data_issues

    issues = _position_data_issues(
        [{"symbol": "NEARUSDT", "total": "10", "markPrice": "0"}]
    )

    assert any("NEARUSDT" in issue and "positive" in issue for issue in issues)


def test_position_audit_rejects_duplicate_or_opposite_hedge_legs() -> None:
    issues = _position_side_issues(
        [
            {"symbol": "NEARUSDT", "total": "10", "posSide": "long", "markPrice": "5"},
            {"symbol": "NEARUSDT", "total": "2", "posSide": "short", "markPrice": "5"},
            {"symbol": "SOLUSDT", "total": "3", "posSide": "long", "markPrice": "100"},
            {"symbol": "SOLUSDT", "total": "4", "posSide": "long", "markPrice": "100"},
        ]
    )

    assert "NEARUSDT:long+short" in issues
    assert "SOLUSDT:duplicate-long" in issues


def test_venue_stop_coverage_requires_a_live_mark_market_stop_per_short() -> None:
    from scripts.audit_live_track import _venue_short_stop_gaps

    positions = [
        {"symbol": "NEARUSDT", "total": "10", "posSide": "short", "markPrice": "5"},
        {"symbol": "SOLUSDT", "total": "10", "posSide": "short", "markPrice": "5"},
    ]
    strategy_orders = [
        {
            "symbol": "NEARUSDT",
            "posSide": "short",
            "side": "buy",
            "qty": "10",
            "stopLoss": "6",
            "slTriggerBy": "mark",
            "slOrderType": "market",
        }
    ]

    assert _venue_short_stop_gaps(positions, strategy_orders) == ["SOLUSDT"]

    strategy_orders.append(
        {
            "symbol": "SOLUSDT",
            "posSide": "short",
            "side": "buy",
            "qty": "10",
            "stopLoss": "6",
            "slTriggerBy": "last_price",
            "slOrderType": "market",
        }
    )
    assert _venue_short_stop_gaps(positions, strategy_orders) == ["SOLUSDT"]


def test_venue_stop_coverage_rejects_a_modified_stop_price() -> None:
    from scripts.audit_live_track import _venue_short_stop_gaps

    positions = [
        {"symbol": "NEARUSDT", "total": "10", "posSide": "short", "markPrice": "5"}
    ]
    strategy_orders = [
        {
            "symbol": "NEARUSDT",
            "posSide": "short",
            "side": "buy",
            "qty": "10",
            "stopLoss": "5.5",
            "slTriggerBy": "mark",
            "slOrderType": "market",
            "status": "pending",
        }
    ]

    assert _venue_short_stop_gaps(
        positions,
        strategy_orders,
        expected_stops={"NEARUSDT": 6.0},
    ) == ["NEARUSDT"]


def test_venue_stop_coverage_rejects_a_stop_that_is_too_wide() -> None:
    from scripts.audit_live_track import _venue_short_stop_gaps

    positions = [
        {"symbol": "NEARUSDT", "total": "10", "posSide": "short", "markPrice": "5"}
    ]
    strategy_orders = [
        {
            "symbol": "NEARUSDT",
            "posSide": "short",
            "side": "buy",
            "qty": "10",
            "stopLoss": "8",
            "slTriggerBy": "mark",
            "slOrderType": "market",
            "status": "pending",
        }
    ]

    assert _venue_short_stop_gaps(
        positions,
        strategy_orders,
        expected_stops={"NEARUSDT": 6.0},
    ) == ["NEARUSDT"]


def test_venue_stop_coverage_accepts_one_way_net_position_side() -> None:
    from scripts.audit_live_track import _venue_short_stop_gaps

    positions = [
        {"symbol": "NEARUSDT", "total": "-10", "posSide": "net", "markPrice": "5"}
    ]
    strategy_orders = [
        {
            "symbol": "NEARUSDT",
            "posSide": "net",
            "side": "buy",
            "qty": "10",
            "stopLoss": "6",
            "slTriggerBy": "mark",
            "slOrderType": "market",
            "status": "pending",
        }
    ]

    assert _venue_short_stop_gaps(
        positions,
        strategy_orders,
        expected_stops={"NEARUSDT": 6.0},
    ) == []


def test_multiple_exchange_stops_must_collectively_cover_the_short() -> None:
    from scripts.audit_live_track import _venue_short_stop_gaps

    positions = [
        {"symbol": "NEARUSDT", "total": "4", "posSide": "short", "markPrice": "3.545"}
    ]
    full = [
        {
            "symbol": "NEARUSDT",
            "posSide": "short",
            "side": "buy",
            "qty": "2",
            "stopLoss": "4.2538",
            "slTriggerBy": "mark",
            "slOrderType": "market",
            "status": "pending",
        },
        {
            "symbol": "NEARUSDT",
            "posSide": "short",
            "side": "buy",
            "qty": "2",
            "stopLoss": "4.2542",
            "slTriggerBy": "mark",
            "slOrderType": "market",
            "status": "pending",
        },
    ]

    assert _venue_short_stop_gaps(
        positions,
        full,
        expected_stops={"NEARUSDT": 4.2542},
    ) == []
    assert _venue_short_stop_gaps(
        positions,
        full[:1],
        expected_stops={"NEARUSDT": 4.2542},
    ) == ["NEARUSDT"]
    assert _venue_short_stop_gaps(
        positions,
        [{**full[0], "stopLoss": "4.2542"}],
        expected_stops={"NEARUSDT": 4.2542},
    ) == ["NEARUSDT"]


def test_short_stop_audit_rejects_multiple_active_stops_for_one_short() -> None:
    positions = [
        {"symbol": "NEARUSDT", "total": "4", "posSide": "short", "markPrice": "3.545"}
    ]
    strategy_orders = [
        {
            "symbol": "NEARUSDT",
            "posSide": "short",
            "side": "buy",
            "qty": "2",
            "stopLoss": "4.2538",
            "slTriggerBy": "mark",
            "slOrderType": "market",
            "status": "pending",
        },
        {
            "symbol": "NEARUSDT",
            "posSide": "short",
            "side": "buy",
            "qty": "2",
            "stopLoss": "4.2542",
            "slTriggerBy": "mark",
            "slOrderType": "market",
            "status": "pending",
        },
    ]

    assert _short_stop_duplicate_issues(positions, strategy_orders) == ["NEARUSDT"]


def test_short_stop_must_fire_before_the_isolated_liquidation_price() -> None:
    positions = [
        {
            "symbol": "NEARUSDT",
            "total": "4",
            "posSide": "short",
            "avgPrice": "3.545",
            "liquidationPrice": "5.5",
        }
    ]

    assert _short_stop_liquidation_issues(
        positions,
        expected_stops={"NEARUSDT": 6.0},
    ) == ["NEARUSDT"]


def test_orphan_strategy_orders_are_not_silently_accepted() -> None:
    positions = [
        {"symbol": "NEARUSDT", "total": "10", "posSide": "short", "markPrice": "5"}
    ]
    strategy_orders = [
        {
            "orderId": "expected",
            "symbol": "NEARUSDT",
            "posSide": "short",
            "side": "buy",
            "qty": "10",
            "stopLoss": "6",
            "slTriggerBy": "mark",
            "slOrderType": "market",
            "status": "pending",
        },
        {
            "orderId": "orphan",
            "symbol": "SOLUSDT",
            "posSide": "short",
            "side": "buy",
            "qty": "10",
            "stopLoss": "100",
            "slTriggerBy": "mark",
            "slOrderType": "market",
            "status": "pending",
        },
    ]

    issues = _orphan_strategy_order_issues(
        positions,
        strategy_orders,
    )

    assert issues == ["SOLUSDT:orphan"]


def test_any_pending_regular_order_fails_the_full_chain_audit() -> None:
    assert _unfilled_order_issues([]) == []
    assert _unfilled_order_issues(
        [
            {
                "symbol": "NEARUSDT",
                "orderId": "123",
                "clientOid": "manual",
                "side": "buy",
                "qty": "2",
                "cumExecQty": "0",
            }
        ]
    ) == ["NEARUSDT:123:manual:buy:0/2"]

def test_funding_delta_check_rejects_repeating_a_cumulative_snapshot() -> None:
    from scripts.audit_live_track import _funding_delta_errors

    positions_before = [
        {
            "symbol": "NEARUSDT",
            "side": "long",
            "qty": 20.0,
            "funding_cumulative": -0.10,
        }
    ]
    positions_after = [
        {
            "symbol": "NEARUSDT",
            "side": "long",
            "qty": 20.0,
            "funding_cumulative": -0.13,
        }
    ]
    journal = pd.DataFrame(
        [
            {"date": "2026-11-03", "positions": json.dumps(positions_before), "funding_total": 0.0},
            {"date": "2026-11-04", "positions": json.dumps(positions_after), "funding_total": -0.13},
        ]
    )

    errors = _funding_delta_errors(journal)

    assert len(errors) == 1
    assert "资金费" in errors[0]

    journal.loc[1, "funding_total"] = -0.03
    assert _funding_delta_errors(journal) == []


def test_registered_venue_drill_orders_are_not_reported_as_missing_journal(tmp_path) -> None:
    from scripts.audit_live_track import _load_drill_order_ids, _unjournaled_order_ids

    registry = tmp_path / "drill.json"
    registry.write_text(
        json.dumps(
            {
                "orders": [
                    {
                        "order_id": "2",
                        "client_oid": "a20fixeddrill",
                        "purpose": "venue capability drill",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    history = [
        {"orderId": "2", "clientOid": "a20fixeddrill", "orderStatus": "filled", "cumExecQty": "3"},
    ]

    assert _load_drill_order_ids(registry) == {"2"}
    assert (
        _unjournaled_order_ids(history, pd.DataFrame(), ignored_order_ids={"2"})
        == []
    )


def test_prior_track_order_registry_must_exist_when_configured(tmp_path) -> None:
    from scripts.audit_live_track import _load_prior_track_order_ids

    missing = tmp_path / "missing-prior-orders.json"
    with pytest.raises(ValueError, match="prior-track order registry"):
        _load_prior_track_order_ids(missing)

    registry = tmp_path / "prior-orders.json"
    registry.write_text(
        json.dumps(
            {
                "orders": [
                    {
                        "order_id": "pre-migration-1",
                        "client_oid": "a20ls45",
                        "purpose": "LS45 production position carried into LS104 baseline",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    assert _load_prior_track_order_ids(registry) == {"pre-migration-1"}


def test_every_filled_strategy_order_must_appear_in_the_journal() -> None:
    from scripts.audit_live_track import _unjournaled_order_ids

    journal = pd.DataFrame(
        [
            {
                "date": "2026-11-13",
                "trades": json.dumps(
                    [
                        {
                            "order_id": "1",
                            "qty": 2.0,
                            "status": "filled",
                        }
                    ]
                ),
            }
        ]
    )
    history = [
        {"orderId": "1", "clientOid": "a20one", "symbol": "NEARUSDT", "orderStatus": "filled", "cumExecQty": "2"},
        {"orderId": "2", "clientOid": "a20two", "symbol": "NEARUSDT", "orderStatus": "filled", "cumExecQty": "3"},
        {"orderId": "3", "clientOid": "manual", "symbol": "NEARUSDT", "orderStatus": "filled", "cumExecQty": "4"},
        {"orderId": "4", "clientOid": "a20zero", "symbol": "NEARUSDT", "orderStatus": "cancelled", "cumExecQty": "0"},
        {"orderId": "5", "clientOid": "outside", "symbol": "BTCUSDT", "orderStatus": "filled", "cumExecQty": "1"},
    ]

    assert _unjournaled_order_ids(
        history,
        journal,
        tracked_symbols={"NEARUSDT"},
    ) == ["2", "3"]


def test_latest_journal_short_quantities_ignore_other_sides() -> None:
    entry = JournalEntry(
        date="2026-11-14",
        run_at_utc="2026-11-14T16:38:00+00:00",
        signal_date="2026-11-13",
        equity=500.0,
        position_value=50.0,
        cash=450.0,
        day_pnl=0.0,
        day_return=0.0,
        fees_today=0.0,
        funding_total=0.0,
        unrealised_pnl=0.0,
        positions=[
            {"symbol": "NEARUSDT", "side": "short", "qty": 9.0},
            {"symbol": "LINKUSDT", "side": "long", "qty": 2.0},
        ],
    )
    frame = pd.DataFrame([entry.as_row()])

    assert latest_short_quantities(frame) == {"NEARUSDT": pytest.approx(9.0)}


def test_event_quantity_target_allows_price_drift_without_daily_rebalance() -> None:
    issues = _event_quantity_issues(
        target_quantities={"NEARUSDT": 9.0},
        target_weights={"near": -0.0625},
        symbol_assets={"NEARUSDT": "near"},
        positions=[
            {
                "symbol": "NEARUSDT",
                "posSide": "short",
                "total": "9",
                "markPrice": "4.0",
            }
        ],
        specs_by_symbol={"NEARUSDT": ContractSpec("NEARUSDT", min_order_qty=1.0)},
        event_prices={"near": 5.0},
        stopped_symbols={},
    )

    assert issues == []


def test_event_quantity_target_fails_a_partial_leg() -> None:
    issues = _event_quantity_issues(
        target_quantities={"NEARUSDT": 9.0},
        target_weights={"near": -0.0625},
        symbol_assets={"NEARUSDT": "near"},
        positions=[
            {
                "symbol": "NEARUSDT",
                "posSide": "short",
                "total": "4",
                "markPrice": "5.0",
            }
        ],
        specs_by_symbol={"NEARUSDT": ContractSpec("NEARUSDT", min_order_qty=1.0)},
        event_prices={"near": 5.0},
        stopped_symbols={},
    )

    assert issues == ["NEARUSDT 目标数量 9 vs 实际 -4"]


def test_event_quantity_target_accepts_a_journaled_stop_closure() -> None:
    issues = _event_quantity_issues(
        target_quantities={"NEARUSDT": 9.0},
        target_weights={"near": -0.0625},
        symbol_assets={"NEARUSDT": "near"},
        positions=[],
        specs_by_symbol={"NEARUSDT": ContractSpec("NEARUSDT", min_order_qty=1.0)},
        event_prices={"near": 5.0},
        stopped_symbols={
            "NEARUSDT": {
                "order_id": "executed-stop-1",
                "strategy_order_id": "strategy-stop-1",
                "triggered_at": "2026-11-15T00:00:00+00:00",
                "quantity": 9.0,
            }
        },
    )

    assert issues == []


def _stop_journal() -> pd.DataFrame:
    entry = JournalEntry(
        date="2026-11-15",
        run_at_utc="2026-11-15T01:05:00+00:00",
        signal_date="2026-11-13",
        equity=500.0,
        position_value=0.0,
        cash=500.0,
        day_pnl=0.0,
        day_return=0.0,
        fees_today=0.0,
        funding_total=0.0,
        unrealised_pnl=0.0,
        trades=[
            {
                "order_id": "executed-stop-1",
                "symbol": "NEARUSDT",
                "action": "CLOSE",
                "side": "buy",
                "qty": 9.0,
                "status": "filled",
                "reason": "venue_strategy_stop",
                "strategy_order_id": "strategy-stop-1",
                "triggered_at": "2026-11-15T00:00:00+00:00",
            }
        ],
    )
    return pd.DataFrame([entry.as_row()])


def test_active_event_state_accepts_a_journaled_stop_closure() -> None:
    state = {
        "last_status": "ok",
        "active_event": {
            "signal_date": "2026-11-13",
            "targets_sha256": "sha256:target",
            "position_status": "ok",
            "stopped_symbols": {
                "NEARUSDT": {
                    "order_id": "executed-stop-1",
                    "strategy_order_id": "strategy-stop-1",
                    "triggered_at": "2026-11-15T00:00:00+00:00",
                    "quantity": 9.0,
                }
            },
        },
    }

    assert _active_event_state_issues(
        state,
        signal_date=pd.Timestamp("2026-11-13T00:00:00Z"),
        journal=_stop_journal(),
        expected_targets_sha256="sha256:target",
    ) == []


def test_active_event_state_rejects_an_incomplete_position_application() -> None:
    state = {
        "last_status": "partial",
        "active_event": {
            "signal_date": "2026-11-13",
            "targets_sha256": "sha256:target",
            "position_status": "partial",
            "stopped_symbols": {},
        },
    }

    issues = _active_event_state_issues(
        state,
        signal_date=pd.Timestamp("2026-11-13T00:00:00Z"),
        journal=_stop_journal(),
        expected_targets_sha256="sha256:target",
    )

    assert any("last_status" in issue for issue in issues)
    assert any("position application" in issue for issue in issues)


def test_strategy_stop_history_verifies_the_journaled_stop_trigger() -> None:
    stopped = {
        "NEARUSDT": {
            "order_id": "executed-stop-1",
            "strategy_order_id": "strategy-stop-1",
            "triggered_at": "2026-11-15T00:00:00+00:00",
            "quantity": 9.0,
            "stop_loss": 3.9248,
            "stop_trigger_by": "mark",
            "stop_order_type": "market",
        }
    }
    rows = [
        {
            "orderId": "strategy-stop-1",
            "symbol": "NEARUSDT",
            "posSide": "short",
            "side": "buy",
            "status": "success",
            "qty": "9",
            "stopLoss": "3.9248",
            "slTriggerBy": "mark",
            "slOrderType": "market",
            "updatedTime": "1794700800000",
        }
    ]

    assert _strategy_stop_history_issues(stopped, rows) == []


def test_event_quantity_target_allows_an_untradeable_minimum_order_residual() -> None:
    issues = _event_quantity_issues(
        target_quantities={"HYPEUSDT": 0.47637},
        target_weights={"hyperliquid": -0.0625},
        symbol_assets={"HYPEUSDT": "hyperliquid"},
        positions=[
            {
                "symbol": "HYPEUSDT",
                "posSide": "short",
                "total": "0.46",
                "markPrice": "66.0",
            }
        ],
        specs_by_symbol={
            "HYPEUSDT": ContractSpec(
                "HYPEUSDT",
                min_order_qty=0.01,
                quantity_multiplier=0.01,
                min_order_usdt=5.0,
            )
        },
        event_prices={"hyperliquid": 66.055},
        stopped_symbols={},
    )

    assert issues == []


def test_event_quantity_target_rejects_reopening_a_stopped_leg_before_a_new_event() -> None:
    issues = _event_quantity_issues(
        target_quantities={"NEARUSDT": 9.0},
        target_weights={"near": -0.0625},
        symbol_assets={"NEARUSDT": "near"},
        positions=[
            {
                "symbol": "NEARUSDT",
                "posSide": "short",
                "total": "9",
                "markPrice": "5.0",
            }
        ],
        specs_by_symbol={"NEARUSDT": ContractSpec("NEARUSDT", min_order_qty=1.0)},
        event_prices={"near": 5.0},
        stopped_symbols={
            "NEARUSDT": {
                "order_id": "executed-stop-1",
                "strategy_order_id": "strategy-stop-1",
                "triggered_at": "2026-11-15T00:00:00+00:00",
                "quantity": 9.0,
            }
        },
    )

    assert issues == ["NEARUSDT 已在旧事件中止损，下一目标事件前不得重开"]


def test_active_event_state_requires_stop_history_high_water_coverage() -> None:
    state = {
        "last_status": "ok",
        "active_event": {
            "signal_date": "2026-11-13",
            "targets_sha256": "sha256:target",
            "position_status": "ok",
            "applied_at": "2026-11-14T16:38:00+00:00",
            "stopped_symbols": {},
        },
        "stop_reconciliation_through": "2026-11-14T01:00:00+00:00",
    }

    issues = _active_event_state_issues(
        state,
        signal_date=pd.Timestamp("2026-11-13T00:00:00Z"),
        journal=_stop_journal(),
        expected_targets_sha256="sha256:target",
    )

    assert any("stop history high-water" in issue for issue in issues)


def test_generated_stop_close_is_matched_to_its_execution_order_without_attached_stop() -> None:
    trade = {
        "qty": 9.0,
        "avg_price": 3.95,
        "fee": 0.02,
        "stop_loss": 3.9248,
        "reason": "venue_strategy_stop",
        "strategy_order_id": "strategy-stop-1",
    }
    venue = {
        "cumExecQty": "9",
        "avgPrice": "3.95",
        "feeDetail": [{"fee": "0.02"}],
        "stopLoss": "",
        "slTriggerBy": "",
        "slOrderType": "",
    }

    assert _trade_mismatch(trade, venue) is None


def test_active_event_state_rejects_a_malformed_risk_overlay() -> None:
    state = {
        "last_status": "ok",
        "active_event": {
            "signal_date": "2026-11-13",
            "targets_sha256": "sha256:target",
            "position_status": "ok",
            "stopped_symbols": {},
            "risk_overlay": {
                "reason": "not-a-risk-cap",
                "applied_at": "invalid",
                "target_quantities": {"NEARUSDT": -4.0},
            },
        },
    }

    issues = _active_event_state_issues(
        state,
        signal_date=pd.Timestamp("2026-11-13T00:00:00Z"),
        journal=_stop_journal(),
        expected_targets_sha256="sha256:target",
    )

    assert any("risk_overlay" in issue for issue in issues)


def test_active_event_state_rejects_a_stop_trade_with_wrong_action() -> None:
    journal = _stop_journal()
    trades = json.loads(journal.iloc[0]["trades"])
    trades[0]["action"] = "OPEN"
    journal.loc[journal.index[0], "trades"] = json.dumps(trades)
    state = {
        "last_status": "ok",
        "active_event": {
            "signal_date": "2026-11-13",
            "targets_sha256": "sha256:target",
            "position_status": "ok",
            "stopped_symbols": {
                "NEARUSDT": {
                    "order_id": "executed-stop-1",
                    "strategy_order_id": "strategy-stop-1",
                    "triggered_at": "2026-11-15T00:00:00+00:00",
                    "quantity": 9.0,
                }
            },
        },
    }

    issues = _active_event_state_issues(
        state,
        signal_date=pd.Timestamp("2026-11-13T00:00:00Z"),
        journal=journal,
        expected_targets_sha256="sha256:target",
    )

    assert any("journal stop trade" in issue for issue in issues)


def test_strategy_stop_history_accepts_a_partial_execution_of_the_requested_stop() -> None:
    stopped = {
        "NEARUSDT": {
            "order_id": "executed-stop-1",
            "strategy_order_id": "strategy-stop-1",
            "triggered_at": "2026-11-15T00:00:00+00:00",
            "quantity": 4.0,
            "requested_quantity": 10.0,
            "stop_loss": 3.9248,
            "stop_trigger_by": "mark",
            "stop_order_type": "market",
        }
    }
    rows = [
        {
            "orderId": "strategy-stop-1",
            "symbol": "NEARUSDT",
            "posSide": "short",
            "side": "buy",
            "status": "success",
            "qty": "10",
            "stopLoss": "3.9248",
            "slTriggerBy": "mark",
            "slOrderType": "market",
            "updatedTime": "1794700800000",
        }
    ]

    assert _strategy_stop_history_issues(stopped, rows) == []


def test_strategy_stop_history_accepts_one_way_net_position_side() -> None:
    stopped = {
        "NEARUSDT": {
            "order_id": "executed-stop-1",
            "strategy_order_id": "strategy-stop-1",
            "triggered_at": "2026-11-15T00:00:00+00:00",
            "quantity": 9.0,
            "stop_loss": 3.9248,
            "stop_trigger_by": "mark",
            "stop_order_type": "market",
        }
    }
    rows = [
        {
            "orderId": "strategy-stop-1",
            "symbol": "NEARUSDT",
            "posSide": "net",
            "side": "buy",
            "status": "success",
            "qty": "9",
            "stopLoss": "3.9248",
            "slTriggerBy": "mark",
            "slOrderType": "market",
            "updatedTime": "1794700800000",
        }
    ]

    assert _strategy_stop_history_issues(stopped, rows) == []


def test_position_risk_checks_accept_the_ls104_four_x_profile() -> None:
    from scripts.audit_live_track import _position_risk_issues

    positions = [
        {
            "symbol": "NEARUSDT",
            "total": "-20",
            "posSide": "short",
            "markPrice": "5",
            "marginMode": "isolated",
            "leverage": "4",
            "positionBalance": "51.5",
        }
    ]

    assert _position_risk_issues(positions, expected_leverage=4.0) == []
