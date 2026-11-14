from __future__ import annotations

import json

import pandas as pd
import pytest

from atlas20.derivatives.execution import ContractSpec
from atlas20.derivatives.live_journal import (
    JournalEntry,
    protected_short_stops,
    protected_short_symbols,
)
from scripts.audit_live_track import (
    _execution_floor_issue,
    _ledger_expected_equity,
    _orphan_strategy_order_issues,
    _pnl_chain_errors,
    _position_data_issues,
    _position_signed_notional,
    _position_side_issues,
    _position_short_stop_expectations,
    _position_target_issues,
    _short_stop_gaps,
    _short_stop_expectation_gaps,
    _trade_mismatch,
    _unfilled_order_issues,
)


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
        {"orderId": "1", "clientOid": "a20one", "orderStatus": "filled", "cumExecQty": "2"},
        {"orderId": "2", "clientOid": "a20two", "orderStatus": "filled", "cumExecQty": "3"},
        {"orderId": "3", "clientOid": "manual", "orderStatus": "filled", "cumExecQty": "4"},
        {"orderId": "4", "clientOid": "a20zero", "orderStatus": "cancelled", "cumExecQty": "0"},
    ]

    assert _unjournaled_order_ids(history, journal) == ["2"]
