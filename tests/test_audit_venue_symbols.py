from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from atlas20.derivatives.mapping import LiveSymbolMap
from atlas20.derivatives.quotes import ExecutionQuote
from scripts.audit_venue_symbols import build_venue_symbol_audit


def _instrument(**overrides):
    row = {
        "symbol": "TRXUSDT",
        "baseCoin": "TRX",
        "quoteCoin": "USDT",
        "category": "USDT-FUTURES",
        "status": "online",
        "type": "perpetual",
        "minLeverage": "1",
        "maxLeverage": "75",
        "minOrderQty": "0.1",
        "quantityMultiplier": "0.1",
        "minOrderAmount": "5",
        "quantityPrecision": "1",
        "priceMultiplier": "0.0001",
        "pricePrecision": "4",
        "maxMarketOrderQty": "100000",
    }
    row.update(overrides)
    return row


def _quote() -> ExecutionQuote:
    observed = pd.Timestamp("2026-11-14T12:00:00Z")
    return ExecutionQuote(
        symbol="TRXUSDT",
        last_price=0.30,
        mark_price=0.30,
        bid_price=0.2999,
        ask_price=0.3001,
        bid_size=100_000,
        ask_size=100_000,
        observed_at=observed,
        received_at=observed + pd.Timedelta(milliseconds=500),
    )


def _symbol_map() -> LiveSymbolMap:
    return LiveSymbolMap({"tron": "TRXUSDT"}, {"TRXUSDT": "tron"})


def test_venue_symbol_audit_proves_long_short_and_flip_for_tron() -> None:
    report = build_venue_symbol_audit(
        symbol_map=_symbol_map(),
        instruments=[_instrument()],
        quotes={"TRXUSDT": _quote()},
        now=datetime(2026, 11, 14, 12, 0, 1, tzinfo=timezone.utc),
    )

    assert report["passed"] is True
    assert report["mapped_assets"] == 1
    assert report["unique_symbols"] == 1
    assert report["long_ok"] == 1
    assert report["short_ok"] == 1
    assert report["flip_ok"] == 1
    assert report["issues"] == []


def test_venue_symbol_audit_rejects_a_contract_base_mismatch() -> None:
    report = build_venue_symbol_audit(
        symbol_map=_symbol_map(),
        instruments=[_instrument(baseCoin="TRON")],
        quotes={"TRXUSDT": _quote()},
        now=datetime(2026, 11, 14, 12, 0, 1, tzinfo=timezone.utc),
    )

    assert report["passed"] is False
    assert any("baseCoin" in issue for issue in report["issues"])
