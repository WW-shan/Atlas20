"""Read-only proof that every mapped asset can be planned on Bitget.

This audit closes the gap between a symbol appearing in a CSV and the venue
actually being able to trade it.  For every mapped asset it verifies the live
v3 contract identity, 2x leverage support, quote freshness, and synthetic
long, short-with-stop, and long-to-short flip plans.  It never places or
cancels an order and never reads private account credentials.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from math import isfinite
from pathlib import Path
import sys
from typing import Any

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.execution import (  # noqa: E402
    AccountState,
    ContractSpec,
    PositionState,
    build_execution_plan,
)
from atlas20.derivatives.mapping import LiveSymbolMap  # noqa: E402
from atlas20.derivatives.quotes import ExecutionQuote, fetch_execution_quotes  # noqa: E402
from atlas20.logging_utils import atomic_write_text, ensure_dir  # noqa: E402

from scripts.plan_live_execution import (  # noqa: E402
    DEFAULT_SYMBOL_MAP,
    fetch_public_instruments,
    load_symbol_map,
    specs_from_instruments,
)

DEFAULT_OUT = Path("reports/ls45_live_g125_live/venue_symbol_audit.json")


def _number(value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return parsed if isfinite(parsed) else float("nan")


def _first_number(*values: object) -> float:
    for value in values:
        parsed = _number(value)
        if isfinite(parsed):
            return parsed
    return float("nan")


def _json_number(value: float) -> float | None:
    return float(value) if isfinite(value) else None


def _contract_issues(contract: dict[str, Any], symbol: str) -> list[str]:
    issues: list[str] = []
    contract_symbol = str(contract.get("symbol") or "").strip().upper()
    base = str(contract.get("baseCoin") or "").strip().upper()
    quote = str(contract.get("quoteCoin") or "").strip().upper()
    if contract_symbol != symbol:
        issues.append(f"{symbol}: v3 symbol={contract_symbol or '<missing>'}")
    if base and quote and contract_symbol != f"{base}{quote}":
        issues.append(
            f"{symbol}: baseCoin={base} quoteCoin={quote} do not compose the symbol"
        )
    if quote != "USDT":
        issues.append(f"{symbol}: quoteCoin={quote or '<missing>'}, require USDT")
    if str(contract.get("category") or "").strip().upper() != "USDT-FUTURES":
        issues.append(f"{symbol}: category is not USDT-FUTURES")
    if str(contract.get("status") or "").strip().lower() != "online":
        issues.append(f"{symbol}: status={contract.get('status')!r}")
    if str(contract.get("type") or "").strip().lower() != "perpetual":
        issues.append(f"{symbol}: type={contract.get('type')!r}")
    min_leverage = _first_number(contract.get("minLeverage"), contract.get("minLever"))
    max_leverage = _first_number(contract.get("maxLeverage"), contract.get("maxLever"))
    if not (isfinite(min_leverage) and isfinite(max_leverage)):
        issues.append(f"{symbol}: leverage range is missing or invalid")
    elif not (min_leverage <= 2.0 <= max_leverage):
        issues.append(f"{symbol}: 2x outside leverage range {min_leverage:g}..{max_leverage:g}")
    return issues


def _plan_issue(
    plan: Any,
    *,
    side: str,
    symbol: str,
    spec: ContractSpec,
) -> str | None:
    if len(plan.orders) != 1:
        return f"expected one {side} open order, got {len(plan.orders)}"
    order = plan.orders[0]
    if order.action != "OPEN" or order.pos_side != side or order.symbol != symbol:
        return (
            f"unexpected {side} order action={order.action} posSide={order.pos_side} "
            f"symbol={order.symbol}"
        )
    if order.size < spec.min_order_qty or order.notional + 1e-9 < spec.min_order_usdt:
        return f"{side} order is below the venue minimum"
    if side == "short":
        if order.side != "sell" or order.stop_loss is None:
            return "short order has no sell/mark-price stop"
        if order.stop_loss <= order.price:
            return "short stop is not above entry"
    elif order.side != "buy" or order.stop_loss is not None:
        return "long order has the wrong side or an attached stop"
    return None


def build_venue_symbol_audit(
    *,
    symbol_map: LiveSymbolMap,
    instruments: list[dict[str, Any]],
    quotes: dict[str, ExecutionQuote],
    now: datetime | None = None,
    equity_reference: float = 500.0,
    max_quote_age_seconds: float = 120.0,
) -> dict[str, Any]:
    """Build a deterministic, read-only venue-symbol capability report."""

    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    else:
        moment = moment.astimezone(timezone.utc)
    by_symbol = {
        str(row.get("symbol") or "").strip().upper(): row
        for row in instruments
        if isinstance(row, dict) and row.get("symbol")
    }
    unique_symbols = sorted({str(symbol).strip().upper() for symbol in symbol_map.values()})
    issues: list[str] = []
    missing_instruments: list[str] = []
    missing_prices: list[str] = []
    long_depth_warnings: list[str] = []
    short_depth_warnings: list[str] = []
    assets: list[dict[str, Any]] = []

    for asset, raw_symbol in sorted(symbol_map.items()):
        symbol = str(raw_symbol).strip().upper()
        contract = by_symbol.get(symbol)
        quote = quotes.get(symbol)
        row: dict[str, Any] = {"asset": asset, "symbol": symbol}
        if contract is None:
            missing_instruments.append(symbol)
            issues.append(f"{asset}: no live v3 instrument for {symbol}")
            assets.append(row)
            continue
        asset_issues = _contract_issues(contract, symbol)
        issues.extend(f"{asset}: {item}" for item in asset_issues)
        spec = specs_from_instruments([contract], {asset: symbol}).get(asset)
        if spec is None:
            issues.append(f"{asset}: v3 contract has no complete perpetual spec")
            assets.append(row)
            continue
        row.update(
            {
                "contract_status": contract.get("status"),
                "contract_type": contract.get("type"),
                "category": contract.get("category"),
                "base_coin": contract.get("baseCoin"),
                "quote_coin": contract.get("quoteCoin"),
                "min_leverage": _json_number(
                    _first_number(contract.get("minLeverage"), contract.get("minLever"))
                ),
                "max_leverage": _json_number(
                    _first_number(contract.get("maxLeverage"), contract.get("maxLever"))
                ),
                "min_order_qty": spec.min_order_qty,
                "quantity_multiplier": spec.quantity_multiplier,
                "min_order_usdt": spec.min_order_usdt,
            }
        )
        if quote is None:
            missing_prices.append(symbol)
            issues.append(f"{asset}: no valid live ticker quote for {symbol}")
            assets.append(row)
            continue
        price = quote.mark_price
        row["price"] = price
        row["quote"] = quote.as_dict()
        account = AccountState(equity=float(equity_reference), available_margin=float(equity_reference))
        specs = {asset: spec}
        prices = {asset: price}
        long_plan = build_execution_plan(
            account,
            {asset: 1.0},
            specs,
            prices,
            leverage=2.0,
            long_buffer=0.50,
            short_buffer=0.50,
            short_stop_loss_pct=0.20,
            max_gross_exposure=float(equity_reference),
            min_rebalance_usdt=0.0,
        )
        short_plan = build_execution_plan(
            account,
            {asset: -1.0},
            specs,
            prices,
            leverage=2.0,
            long_buffer=0.50,
            short_buffer=0.50,
            short_stop_loss_pct=0.20,
            max_gross_exposure=float(equity_reference),
            min_rebalance_usdt=0.0,
        )
        long_issue = _plan_issue(long_plan, side="long", symbol=symbol, spec=spec)
        short_issue = _plan_issue(short_plan, side="short", symbol=symbol, spec=spec)

        leg_notional = 100.0
        flip_size = max(spec.round_down_qty(leg_notional / price), spec.min_order_qty)
        flip_margin = flip_size * price * 0.515
        flip_account = AccountState(
            equity=float(equity_reference),
            available_margin=max(0.0, float(equity_reference) - flip_margin),
            positions={
                asset: PositionState(
                    asset=asset,
                    symbol=symbol,
                    side="long",
                    size=flip_size,
                    entry_price=price,
                    mark_price=price,
                    margin=flip_margin,
                )
            },
        )
        flip_plan = build_execution_plan(
            flip_account,
            {asset: -1.0},
            specs,
            prices,
            leverage=2.0,
            long_buffer=0.50,
            short_buffer=0.50,
            short_stop_loss_pct=0.20,
            max_gross_exposure=float(equity_reference) * 1.25,
            min_rebalance_usdt=0.0,
        )
        flip_actions = [order.action for order in flip_plan.orders]
        flip_ok = (
            "CLOSE" in flip_actions
            and "OPEN" in flip_actions
            and any(
                order.action == "OPEN"
                and order.pos_side == "short"
                and order.stop_loss is not None
                for order in flip_plan.orders
            )
        )
        if not flip_ok:
            issues.append(f"{asset}: long-to-short flip plan failed: {flip_actions}")
        if long_issue:
            issues.append(f"{asset}: {long_issue}")
        if short_issue:
            issues.append(f"{asset}: {short_issue}")

        long_order = long_plan.orders[0] if long_plan.orders else None
        short_order = short_plan.orders[0] if short_plan.orders else None
        max_market_qty = _number(contract.get("maxMarketOrderQty"))
        long_qty_ok = bool(long_order is not None and (not isfinite(max_market_qty) or long_order.size <= max_market_qty))
        short_qty_ok = bool(short_order is not None and (not isfinite(max_market_qty) or short_order.size <= max_market_qty))
        long_depth_ok = bool(long_order is not None and quote.ask_size * quote.ask_price >= long_order.notional)
        short_depth_ok = bool(short_order is not None and quote.bid_size * quote.bid_price >= short_order.notional)
        if not long_depth_ok:
            long_depth_warnings.append(symbol)
        if not short_depth_ok:
            short_depth_warnings.append(symbol)
        row.update(
            {
                "long_ok": long_issue is None,
                "short_ok": short_issue is None,
                "flip_ok": flip_ok,
                "long_orders": [order.as_dict() for order in long_plan.orders],
                "short_orders": [order.as_dict() for order in short_plan.orders],
                "flip_actions": flip_actions,
                "long_under_market_qty_cap": long_qty_ok,
                "short_under_market_qty_cap": short_qty_ok,
                "long_visible_depth_covers_plan": long_depth_ok,
                "short_visible_depth_covers_plan": short_depth_ok,
            }
        )
        assets.append(row)

    fresh_quotes = all(
        quotes.get(symbol) is not None
        and quotes[symbol].age_seconds <= float(max_quote_age_seconds)
        for symbol in unique_symbols
    )
    if not fresh_quotes:
        issues.append(f"not every mapped symbol has a quote within {max_quote_age_seconds:g}s")
    max_age = max((quotes[symbol].age_seconds for symbol in unique_symbols if symbol in quotes), default=None)
    report = {
        "generated_at": moment.isoformat(),
        "equity_reference": float(equity_reference),
        "max_quote_age_seconds": float(max_quote_age_seconds),
        "mapped_assets": len(symbol_map),
        "unique_symbols": len(unique_symbols),
        "v3_instruments": len(instruments),
        "mapped_specs": sum(bool(row.get("long_orders")) for row in assets),
        "mapped_online": len([row for row in assets if row.get("contract_status") == "online"]),
        "long_ok": sum(bool(row.get("long_ok")) for row in assets),
        "short_ok": sum(bool(row.get("short_ok")) for row in assets),
        "flip_ok": sum(bool(row.get("flip_ok")) for row in assets),
        "two_x_supported": sum(
            bool(
                isfinite(_number(row.get("min_leverage")))
                and isfinite(_number(row.get("max_leverage")))
                and _number(row.get("min_leverage")) <= 2.0 <= _number(row.get("max_leverage"))
            )
            for row in assets
        ),
        "all_quotes_fresh": fresh_quotes,
        "max_observed_quote_age_seconds": max_age,
        "missing_instruments": sorted(set(missing_instruments)),
        "missing_prices": sorted(set(missing_prices)),
        "long_visible_depth_warnings": long_depth_warnings,
        "short_visible_depth_warnings": short_depth_warnings,
        "issues": issues,
        "passed": not issues,
        "assets": assets,
    }
    return report


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--symbol-map", type=Path, default=DEFAULT_SYMBOL_MAP)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--equity", type=float, default=500.0)
    parser.add_argument("--max-quote-age-seconds", type=float, default=120.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.equity <= 0.0 or args.max_quote_age_seconds <= 0.0:
        raise SystemExit("equity and quote age must be positive")
    symbol_map = load_symbol_map(args.symbol_map)
    session = requests.Session()
    instruments = fetch_public_instruments(session)
    symbols = sorted({str(symbol).upper() for symbol in symbol_map.values()})
    quotes = fetch_execution_quotes(session, symbols)
    report = build_venue_symbol_audit(
        symbol_map=symbol_map,
        instruments=instruments,
        quotes=quotes,
        equity_reference=float(args.equity),
        max_quote_age_seconds=float(args.max_quote_age_seconds),
    )
    ensure_dir(args.out.parent)
    atomic_write_text(args.out, json.dumps(report, indent=2, sort_keys=True, default=str))
    summary = {
        key: report[key]
        for key in (
            "passed",
            "mapped_assets",
            "unique_symbols",
            "mapped_specs",
            "mapped_online",
            "two_x_supported",
            "long_ok",
            "short_ok",
            "flip_ok",
            "all_quotes_fresh",
            "missing_instruments",
            "missing_prices",
            "issues",
        )
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"wrote {args.out}")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
