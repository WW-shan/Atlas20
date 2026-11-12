from __future__ import annotations

import pandas as pd
import pytest

from atlas20.derivatives.quotes import ExecutionQuote, QuoteError
from scripts.record_execution_shadow import _execution_side, _summary, build_shadow_rows


def _quote(symbol: str = "BTCUSDT") -> ExecutionQuote:
    observed = pd.Timestamp("2026-01-02 01:05:00+00:00")
    return ExecutionQuote(
        symbol=symbol,
        last_price=100.0,
        mark_price=100.1,
        bid_price=99.9,
        ask_price=100.1,
        bid_size=5.0,
        ask_size=4.0,
        observed_at=observed,
        received_at=observed,
    )


def _book() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "asset": "bitcoin",
                "target_weight": 0.5,
                "change_weight": 0.1,
                "action": "BUY",
            },
            {
                "asset": "ethereum",
                "target_weight": 0.25,
                "change_weight": -0.05,
                "action": "SELL",
            },
        ]
    )


def test_execution_side_from_change_weight() -> None:
    assert _execution_side(0.1) == "buy"
    assert _execution_side(-0.1) == "sell"
    assert _execution_side(0.0) == "hold"


def test_build_shadow_rows_uses_the_relevant_top_of_book_side() -> None:
    quotes = {"BTCUSDT": _quote(), "ETHUSDT": _quote("ETHUSDT")}
    rows = build_shadow_rows(
        _book(),
        quotes,
        {"bitcoin": "BTCUSDT", "ethereum": "ETHUSDT"},
        signal_date=pd.Timestamp("2026-01-01T00:00:00Z"),
        execution_hint=pd.Timestamp("2026-01-02T01:05:00Z"),
        observation_index=0,
    )
    assert rows[0]["side"] == "buy"
    assert rows[0]["top_of_book_notional"] == pytest.approx(400.4)
    assert rows[0]["top_of_book_to_target_ratio"] == pytest.approx(0.8008)
    assert rows[1]["side"] == "sell"
    assert rows[1]["top_of_book_notional"] == pytest.approx(499.5)


def test_build_shadow_rows_fails_closed_on_missing_quote() -> None:
    with pytest.raises(QuoteError, match="no fresh quote"):
        build_shadow_rows(
            _book().iloc[[0]],
            {},
            {"bitcoin": "BTCUSDT"},
            signal_date=pd.Timestamp("2026-01-01T00:00:00Z"),
            execution_hint=pd.Timestamp("2026-01-02T01:05:00Z"),
            observation_index=0,
        )


def test_summary_groups_by_asset() -> None:
    frame = pd.DataFrame(
        [
            {
                "asset": "bitcoin",
                "spread_bps": 20.0,
                "top_of_book_notional": 400.0,
                "top_of_book_to_target_ratio": 0.8,
            },
            {
                "asset": "bitcoin",
                "spread_bps": 10.0,
                "top_of_book_notional": 600.0,
                "top_of_book_to_target_ratio": 1.2,
            },
        ]
    )
    summary = _summary(frame)
    assert summary.loc[0, "observations"] == 2
    assert summary.loc[0, "mean_spread_bps"] == pytest.approx(15.0)
    assert summary.loc[0, "median_top_of_book_notional"] == pytest.approx(500.0)
