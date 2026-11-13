from __future__ import annotations

import json

import pandas as pd
import pytest

from atlas20.derivatives.live_journal import JournalEntry, protected_short_symbols
from scripts.audit_live_track import (
    _ledger_expected_equity,
    _pnl_chain_errors,
    _position_signed_notional,
    _short_stop_gaps,
    _trade_mismatch,
)


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
                            "stop_trigger_by": "mark_price",
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
                            "stop_trigger_by": "mark_price",
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
                            "stop_trigger_by": "mark_price",
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
                            "stop_trigger_by": "mark_price",
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
        "slTriggerBy": "mark_price",
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
            "stopLoss": "6",
            "slTriggerBy": "mark_price",
            "slOrderType": "market",
        }
    ]

    assert _venue_short_stop_gaps(positions, strategy_orders) == ["SOLUSDT"]

    strategy_orders.append(
        {
            "symbol": "SOLUSDT",
            "posSide": "short",
            "stopLoss": "6",
            "slTriggerBy": "last_price",
            "slOrderType": "market",
        }
    )
    assert _venue_short_stop_gaps(positions, strategy_orders) == ["SOLUSDT"]


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
