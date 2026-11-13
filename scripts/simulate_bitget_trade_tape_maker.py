"""Simulate LS57 maker-first execution against Bitget historical trade tapes.

The script downloads official Bitget transaction history and Level1 depth
snapshots into a local cache, then evaluates hypothetical passive orders. It
never sends orders and never reads private credentials. Results are execution
research only; queue position and real fills remain unproven.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys
import time
from typing import Any

import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.trade_tape import (  # noqa: E402
    MakerOrderOutcome,
    TopOfBook,
    TradePrint,
    TradeTapeError,
    parse_depth_xlsx,
    parse_trade_csv,
    simulate_maker_order,
)

DOWNLOAD_URL = "https://www.bitget.com/v1/statistics/public/download/getPublicDataV2"
DEFAULT_SYMBOL_MAP = Path("data/raw/bitget_derivatives/merged_oos_20261009/symbol_map.csv")
DEFAULT_TRADES = Path(
    "reports/derivatives_track_h5_ls23_profitlock_skip7dneg_ma21_stable1d_redistribute/"
    "PR2026-11-LS57-H5-LS23-PROFITLOCK-SKIP7DNEG-MA21-STABLE1D-REDISTRIBUTE/trades.csv"
)
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Origin": "https://www.bitget.com",
    "Referer": "https://www.bitget.com/data-download",
    "Content-Type": "application/json",
}
MAKER_FEE_BPS = 2.0
TAKER_FEE_BPS = 20.0
BASE_TAKER_COST_BPS = 20.0


def execution_side(position_side: str, action: str) -> str:
    """Map a signed position action to the exchange order direction."""
    side = str(position_side).lower()
    verb = str(action).lower()
    if side == "long":
        return "buy" if verb in {"open", "increase"} else "sell"
    if side == "short":
        return "sell" if verb in {"open", "increase"} else "buy"
    raise ValueError(f"unsupported position side {position_side!r}")


def _post_file_list(
    session: requests.Session,
    *,
    symbol: str,
    business_type: int,
    date: str,
    dept_type: int = 1,
    timeout_seconds: float = 30.0,
    retries: int = 5,
) -> list[dict[str, Any]]:
    if retries < 1:
        raise ValueError("retries must be positive")
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = session.post(
                DOWNLOAD_URL,
                json={
                    "displaySymbol": symbol,
                    "businessLine": 2,
                    "businessType": business_type,
                    "dateType": 1,
                    "beginTimeStr": date,
                    "endTimeStr": date,
                    "deptType": dept_type,
                },
                headers=HEADERS,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            if str(payload.get("code")) not in {"0", "200", "00000"}:
                raise TradeTapeError(f"Bitget history error for {symbol} {date}: {payload.get('code')}")
            files = payload.get("data") or []
            if not isinstance(files, list):
                raise TradeTapeError(f"Bitget history data is not a list for {symbol} {date}")
            return [
                record
                for record in files
                if isinstance(record, dict) and record.get("fileUrl")
            ]
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(min(2.0**attempt, 8.0))
    raise TradeTapeError(
        f"failed to list Bitget history for {symbol} {date} after {retries} attempts: {last_error}"
    )


def _history_date(timestamp: pd.Timestamp) -> str:
    """Return Bitget's UTC+8 exchange day for one event timestamp."""
    return (pd.Timestamp(timestamp) + pd.Timedelta(hours=8)).date().isoformat()


def _history_dates(start: pd.Timestamp, end: pd.Timestamp) -> tuple[str, ...]:
    """Return every UTC+8 exchange day touched by a time window."""
    first = (pd.Timestamp(start) + pd.Timedelta(hours=8)).date()
    last = (pd.Timestamp(end) + pd.Timedelta(hours=8)).date()
    return tuple(day.date().isoformat() for day in pd.date_range(first, last, freq="1D"))


def _history_cache_path(
    cache_dir: Path,
    *,
    kind: str,
    symbol: str,
    date: str,
    url: str,
) -> Path:
    """Return a symbol/date-isolated cache path for one public history file."""
    name = Path(url.split("?", 1)[0]).name
    if not name:
        raise TradeTapeError(f"history URL has no filename: {url}")
    return cache_dir / kind / symbol.upper() / date / name


def _download_cached(
    session: requests.Session,
    url: str,
    cache_dir: Path,
    *,
    timeout_seconds: float,
    retries: int = 3,
) -> bytes:
    cache_dir.mkdir(parents=True, exist_ok=True)
    name = Path(url.split("?", 1)[0]).name
    path = cache_dir / name
    if path.is_file() and path.stat().st_size > 0:
        return path.read_bytes()
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = session.get(url, timeout=timeout_seconds)
            response.raise_for_status()
            if not response.content:
                raise TradeTapeError(f"empty history download {url}")
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_bytes(response.content)
            temporary.replace(path)
            return response.content
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(1.0 + attempt)
    raise TradeTapeError(f"failed to download {url}: {last_error}")


def _normalise_depth_scale(
    book: TopOfBook,
    *,
    trade_prices: tuple[float, ...] | list[float],
) -> tuple[TopOfBook, float]:
    """Align a depth workbook's contract price units to the trade tape.

    Bitget occasionally publishes Level1 depth in a contract unit that differs
    from the trade tape by a power of ten (for example SHIB depth x1000). Only
    accept an exact power-of-ten correction that brings the midpoint within 2%
    of the contemporaneous median trade price; anything else fails closed.
    """
    prices = [float(price) for price in trade_prices if math.isfinite(float(price)) and float(price) > 0.0]
    if not prices:
        raise TradeTapeError("depth/trade price scale calibration has no trades")
    trade_median = float(np.median(prices))
    ratio = book.mid_price / trade_median
    if not math.isfinite(ratio) or ratio <= 0.0:
        raise TradeTapeError("depth/trade price scale mismatch")
    factor = 10.0 ** round(math.log10(ratio))
    adjusted_ratio = ratio / factor
    if not 0.98 <= adjusted_ratio <= 1.02:
        raise TradeTapeError(
            "depth/trade price scale mismatch: "
            f"depth_mid={book.mid_price:.12g}, trade_median={trade_median:.12g}, ratio={ratio:.12g}"
        )
    adjusted = TopOfBook(
        timestamp=book.timestamp,
        ask_price=book.ask_price / factor,
        bid_price=book.bid_price / factor,
        ask_volume=book.ask_volume,
        bid_volume=book.bid_volume,
    )
    if adjusted.bid_price >= adjusted.ask_price:
        raise TradeTapeError("scaled depth workbook has crossed top of book")
    return adjusted, factor


def _reference_book(
    books: tuple[TopOfBook, ...],
    entry_time: pd.Timestamp,
    *,
    max_age_minutes: float,
) -> TopOfBook | None:
    prior = [book for book in books if book.timestamp <= entry_time]
    if not prior:
        return None
    book = prior[-1]
    age_minutes = (entry_time - book.timestamp).total_seconds() / 60.0
    if age_minutes > max_age_minutes:
        return None
    return book


def _load_trade_window(
    session: requests.Session,
    files: list[dict[str, Any]],
    *,
    symbol: str,
    date: str,
    entry_time: pd.Timestamp,
    end_time: pd.Timestamp,
    cache_dir: Path,
    timeout_seconds: float,
) -> tuple[TradePrint, ...]:
    rows: dict[str, TradePrint] = {}
    for record in files:
        url = str(record["fileUrl"])
        data = _download_cached(
            session,
            url,
            _history_cache_path(
                cache_dir,
                kind="trades",
                symbol=symbol,
                date=date,
                url=url,
            ).parent,
            timeout_seconds=timeout_seconds,
        )
        parsed = parse_trade_csv(data)
        if not parsed:
            continue
        first = parsed[0].timestamp
        last = parsed[-1].timestamp
        if last < entry_time:
            continue
        if first > end_time:
            break
        for trade in parsed:
            if entry_time <= trade.timestamp <= end_time:
                previous = rows.get(trade.trade_id)
                if previous is not None and previous != trade:
                    raise TradeTapeError(f"conflicting duplicate trade_id {trade.trade_id}")
                rows[trade.trade_id] = trade
    return tuple(sorted(rows.values(), key=lambda row: (row.timestamp, row.trade_id)))


def _haircut_tag(haircut: float) -> str:
    percent = int(round(float(haircut) * 100.0))
    if not math.isclose(percent / 100.0, float(haircut), abs_tol=1e-12):
        raise ValueError("fill haircut must be a whole percentage")
    return f"{percent:03d}"


def _parse_haircuts(value: str) -> tuple[float, ...]:
    if not value.strip():
        return ()
    haircuts: list[float] = []
    for item in value.split(","):
        haircut = float(item.strip())
        if not 0.0 < haircut <= 1.0:
            raise ValueError("fill haircut must be in (0, 1]")
        _haircut_tag(haircut)
        if haircut not in haircuts:
            haircuts.append(haircut)
    return tuple(sorted(haircuts))


def _outcome_fields(prefix: str, outcome: MakerOrderOutcome) -> dict[str, Any]:
    return {
        f"{prefix}_limit_price": outcome.limit_price,
        f"{prefix}_maker_filled_notional": outcome.maker_filled_notional,
        f"{prefix}_taker_filled_notional": outcome.taker_filled_notional,
        f"{prefix}_maker_fill_ratio": outcome.maker_fill_ratio,
        f"{prefix}_vwap": outcome.vwap,
        f"{prefix}_effective_cost_bps": outcome.effective_cost_bps,
        f"{prefix}_improvement_bps": outcome.improvement_bps,
        f"{prefix}_guard_triggered": outcome.guard_triggered,
        f"{prefix}_timed_out": outcome.timed_out,
        f"{prefix}_status": outcome.status,
    }


def _event_rows(
    *,
    trades: pd.DataFrame,
    symbol_map: pd.DataFrame,
    session: requests.Session,
    cache_dir: Path,
    equity: float,
    min_trade_usdt: float,
    timeout_hours: float,
    offset_bps: float,
    through_bps: float,
    guard_bps: float,
    max_depth_age_minutes: float,
    download_timeout_seconds: float,
    max_events: int | None,
    haircut_sensitivity: tuple[float, ...] = (),
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    mapping = {
        str(record["coin_id"]): (
            str(record["bitget_symbol"]).upper(),
            float(record.get("min_trade_usdt") or 0.0),
        )
        for record in symbol_map.to_dict("records")
    }
    candidates: list[dict[str, Any]] = []
    for record in trades.to_dict("records"):
        timestamp = pd.Timestamp(record["timestamp"])
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        asset = str(record["asset"])
        symbol, venue_min = mapping.get(asset, ("", 0.0))
        requested = abs(float(record["notional"])) * float(equity)
        if not symbol or requested < max(float(min_trade_usdt), venue_min):
            continue
        candidates.append(
            {
                "timestamp": timestamp,
                "asset": asset,
                "symbol": symbol,
                "position_side": str(record["side"]).lower(),
                "action": str(record["action"]).lower(),
                "exec_side": execution_side(str(record["side"]), str(record["action"])),
                "requested_notional": requested,
                "venue_min_trade_usdt": venue_min,
                "reason": str(record.get("reason", "")),
            }
        )
    if max_events is not None:
        candidates = candidates[: int(max_events)]

    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for index, event in enumerate(candidates, start=1):
        entry = pd.Timestamp(event["timestamp"])
        entry_date = _history_date(entry)
        try:
            depth_files = _post_file_list(
                session,
                symbol=str(event["symbol"]),
                business_type=3,
                date=entry_date,
                timeout_seconds=download_timeout_seconds,
            )
            if not depth_files:
                raise TradeTapeError("no depth file")
            depth_url = str(depth_files[0]["fileUrl"])
            depth_data = _download_cached(
                session,
                depth_url,
                _history_cache_path(
                    cache_dir,
                    kind="depth",
                    symbol=str(event["symbol"]),
                    date=entry_date,
                    url=depth_url,
                ).parent,
                timeout_seconds=download_timeout_seconds,
            )
            books = parse_depth_xlsx(depth_data)
            raw_book = _reference_book(books, entry, max_age_minutes=max_depth_age_minutes)
            if raw_book is None:
                raise TradeTapeError("no depth snapshot within max age")

            end = entry + pd.Timedelta(hours=float(timeout_hours))
            by_trade_id: dict[str, TradePrint] = {}
            for history_date in _history_dates(entry, end):
                trade_files = _post_file_list(
                    session,
                    symbol=str(event["symbol"]),
                    business_type=2,
                    date=history_date,
                    timeout_seconds=download_timeout_seconds,
                )
                if not trade_files:
                    raise TradeTapeError(f"no transaction files for {history_date}")
                for trade in _load_trade_window(
                    session,
                    trade_files,
                    symbol=str(event["symbol"]),
                    date=history_date,
                    entry_time=entry,
                    end_time=end,
                    cache_dir=cache_dir,
                    timeout_seconds=download_timeout_seconds,
                ):
                    previous_trade = by_trade_id.get(trade.trade_id)
                    if previous_trade is not None:
                        raise TradeTapeError(f"duplicate trade_id {trade.trade_id} across files")
                    by_trade_id[trade.trade_id] = trade
            trades_in_window = tuple(
                sorted(by_trade_id.values(), key=lambda row: (row.timestamp, row.trade_id))
            )
            if not trades_in_window:
                raise TradeTapeError("no trades in execution window")
            book, depth_scale = _normalise_depth_scale(
                raw_book,
                trade_prices=[trade.price for trade in trades_in_window[:100]],
            )

            strict = simulate_maker_order(
                trades_in_window,
                side=str(event["exec_side"]),
                reference_price=book.mid_price,
                order_notional=float(event["requested_notional"]),
                entry_time=entry,
                timeout_hours=timeout_hours,
                offset_bps=offset_bps,
                through_bps=through_bps,
                guard_bps=guard_bps,
                maker_fee_bps=MAKER_FEE_BPS,
                taker_fee_bps=TAKER_FEE_BPS,
            )
            touch = simulate_maker_order(
                trades_in_window,
                side=str(event["exec_side"]),
                reference_price=book.mid_price,
                order_notional=float(event["requested_notional"]),
                entry_time=entry,
                timeout_hours=timeout_hours,
                offset_bps=offset_bps,
                through_bps=0.0,
                guard_bps=guard_bps,
                maker_fee_bps=MAKER_FEE_BPS,
                taker_fee_bps=TAKER_FEE_BPS,
            )
            haircut_fields: dict[str, Any] = {}
            for haircut in haircut_sensitivity:
                outcome = simulate_maker_order(
                    trades_in_window,
                    side=str(event["exec_side"]),
                    reference_price=book.mid_price,
                    order_notional=float(event["requested_notional"]),
                    entry_time=entry,
                    timeout_hours=timeout_hours,
                    offset_bps=offset_bps,
                    through_bps=through_bps,
                    guard_bps=guard_bps,
                    maker_fee_bps=MAKER_FEE_BPS,
                    taker_fee_bps=TAKER_FEE_BPS,
                    fill_haircut=haircut,
                )
                haircut_fields.update(
                    _outcome_fields(f"haircut_{_haircut_tag(haircut)}", outcome)
                )
            rows.append(
                {
                    **event,
                    "date": entry_date,
                    "raw_reference_bid": raw_book.bid_price,
                    "raw_reference_ask": raw_book.ask_price,
                    "raw_reference_mid": raw_book.mid_price,
                    "depth_scale_adjustment": depth_scale,
                    "reference_bid": book.bid_price,
                    "reference_ask": book.ask_price,
                    "reference_mid": book.mid_price,
                    "reference_age_seconds": (entry - book.timestamp).total_seconds(),
                    "trade_count": len(trades_in_window),
                    "first_trade_time": trades_in_window[0].timestamp.isoformat(),
                    "last_trade_time": trades_in_window[-1].timestamp.isoformat(),
                    "base_taker_cost_bps": BASE_TAKER_COST_BPS,
                    **_outcome_fields("strict", strict),
                    **_outcome_fields("touch", touch),
                    **haircut_fields,
                }
            )
        except Exception as exc:  # noqa: BLE001
            errors.append(
                {
                    "event_index": index - 1,
                    **event,
                    "date": entry_date,
                    "error": str(exc),
                }
            )
        if index % 25 == 0:
            print(f"processed {index}/{len(candidates)} events; rows={len(rows)} errors={len(errors)}")
    return rows, errors


def _weighted_mean(frame: pd.DataFrame, column: str, weight: str = "requested_notional") -> float:
    valid = frame[[column, weight]].dropna()
    if valid.empty or float(valid[weight].sum()) <= 0.0:
        return float("nan")
    return float(np.average(valid[column], weights=valid[weight]))


def _summaries(events: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if events.empty:
        empty = pd.DataFrame()
        return {"monthly": empty, "side": empty, "asset": empty}

    def aggregate(group: pd.DataFrame) -> pd.Series:
        requested = group["requested_notional"].sum()
        return pd.Series(
            {
                "events": int(len(group)),
                "requested_notional": float(requested),
                "strict_maker_fill_rate": float(group["strict_maker_filled_notional"].sum() / requested),
                "touch_maker_fill_rate": float(group["touch_maker_filled_notional"].sum() / requested),
                "strict_effective_cost_bps": _weighted_mean(group, "strict_effective_cost_bps"),
                "touch_effective_cost_bps": _weighted_mean(group, "touch_effective_cost_bps"),
                "strict_improvement_bps": _weighted_mean(group, "strict_improvement_bps"),
                "touch_improvement_bps": _weighted_mean(group, "touch_improvement_bps"),
                "strict_guard_notional_share": float(group["strict_taker_filled_notional"].sum() / requested),
                "strict_guard_event_share": float(group["strict_guard_triggered"].mean()),
                "strict_full_fill_share": float((group["strict_status"] == "filled").mean()),
            }
        )

    events = events.copy()
    events["month"] = pd.to_datetime(events["date"], utc=True).dt.strftime("%Y-%m")
    return {
        "monthly": events.groupby("month", dropna=False).apply(aggregate, include_groups=False).reset_index(),
        "side": events.groupby("exec_side", dropna=False).apply(aggregate, include_groups=False).reset_index(),
        "asset": events.groupby("asset", dropna=False).apply(aggregate, include_groups=False).reset_index(),
    }


def _haircut_summary(
    events: pd.DataFrame,
    haircuts: tuple[float, ...],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for haircut in haircuts:
        prefix = f"haircut_{_haircut_tag(haircut)}"
        maker_col = f"{prefix}_maker_filled_notional"
        taker_col = f"{prefix}_taker_filled_notional"
        cost_col = f"{prefix}_effective_cost_bps"
        improvement_col = f"{prefix}_improvement_bps"
        guard_col = f"{prefix}_guard_triggered"
        status_col = f"{prefix}_status"
        if events.empty or maker_col not in events.columns:
            continue
        requested = float(events["requested_notional"].sum())
        improvement = _weighted_mean(events, improvement_col)
        rows.append(
            {
                "haircut": float(haircut),
                "events": int(len(events)),
                "requested_notional": requested,
                "strict_maker_fill_rate": float(events[maker_col].sum() / requested),
                "strict_effective_cost_bps": _weighted_mean(events, cost_col),
                "strict_improvement_bps": improvement,
                "strict_effective_cost_p05_bps": float(events[cost_col].quantile(0.05)),
                "strict_effective_cost_p95_bps": float(events[cost_col].quantile(0.95)),
                "strict_guard_notional_share": float(events[taker_col].sum() / requested),
                "strict_guard_event_share": float(events[guard_col].mean()),
                "strict_full_fill_share": float((events[status_col] == "filled").mean()),
                "strict_timeout_event_share": float((events[status_col] == "timeout").mean()),
                "passes_5bps_improvement": bool(np.isfinite(improvement) and improvement >= 5.0),
            }
        )
    return pd.DataFrame(rows)


def _haircut_breakdowns(
    events: pd.DataFrame,
    haircuts: tuple[float, ...],
) -> dict[str, pd.DataFrame]:
    if events.empty:
        empty = pd.DataFrame()
        return {"side": empty, "month": empty, "asset": empty}
    frame = events.copy()
    frame["month"] = pd.to_datetime(frame["date"], utc=True).dt.strftime("%Y-%m")
    dimensions = {"side": "exec_side", "month": "month", "asset": "asset"}
    result: dict[str, pd.DataFrame] = {}
    for name, column in dimensions.items():
        group_rows: list[dict[str, Any]] = []
        for haircut in haircuts:
            prefix = f"haircut_{_haircut_tag(haircut)}"
            maker_col = f"{prefix}_maker_filled_notional"
            taker_col = f"{prefix}_taker_filled_notional"
            cost_col = f"{prefix}_effective_cost_bps"
            improvement_col = f"{prefix}_improvement_bps"
            guard_col = f"{prefix}_guard_triggered"
            status_col = f"{prefix}_status"
            for group_value, group in frame.groupby(column, dropna=False):
                requested = float(group["requested_notional"].sum())
                group_rows.append(
                    {
                        "haircut": float(haircut),
                        "group": str(group_value),
                        "events": int(len(group)),
                        "requested_notional": requested,
                        "strict_maker_fill_rate": float(group[maker_col].sum() / requested),
                        "strict_effective_cost_bps": _weighted_mean(group, cost_col),
                        "strict_improvement_bps": _weighted_mean(group, improvement_col),
                        "strict_guard_notional_share": float(group[taker_col].sum() / requested),
                        "strict_guard_event_share": float(group[guard_col].mean()),
                        "strict_full_fill_share": float((group[status_col] == "filled").mean()),
                        "strict_timeout_event_share": float((group[status_col] == "timeout").mean()),
                    }
                )
        result[name] = pd.DataFrame(group_rows).sort_values(
            ["haircut", "group"], kind="stable"
        ).reset_index(drop=True)
    return result


def _haircut_acceptance(
    haircut_summary: pd.DataFrame,
    *,
    coverage_checks: dict[str, bool],
) -> dict[str, bool]:
    if haircut_summary.empty:
        return {
            **coverage_checks,
            "haircut_25_present": False,
            "haircut_25_improvement_ge_5bps": False,
            "improvement_monotonic_with_haircut": False,
        }
    ordered = haircut_summary.sort_values("haircut", kind="stable")
    row_25 = ordered.loc[np.isclose(ordered["haircut"], 0.25)]
    improvement = ordered["strict_improvement_bps"].astype(float).to_numpy()
    monotonic = bool(
        len(improvement) >= 2
        and np.all(np.diff(improvement) >= -1e-9)
    )
    checks = {
        **coverage_checks,
        "haircut_25_present": not row_25.empty,
        "haircut_25_improvement_ge_5bps": bool(
            not row_25.empty and float(row_25.iloc[0]["strict_improvement_bps"]) >= 5.0
        ),
        "improvement_monotonic_with_haircut": monotonic,
    }
    return {name: bool(passed) for name, passed in checks.items()}


def _robustness_metrics(events: pd.DataFrame) -> dict[str, Any]:
    """Summarize breadth and dependence of the cost improvement."""
    if events.empty:
        return {
            "weeks": 0,
            "positive_weeks": 0,
            "weeks_ge_5bps": 0,
            "top_savings_asset": None,
            "top_savings_share": float("nan"),
            "ex_top_savings_improvement_bps": float("nan"),
            "negative_assets": 0,
            "ex_negative_assets_improvement_bps": float("nan"),
        }
    frame = events.copy()
    timestamps = pd.to_datetime(frame["timestamp"], utc=True)
    frame["week"] = timestamps.dt.tz_localize(None).dt.to_period("W-MON").astype(str)
    weekly = frame.groupby("week", dropna=False).apply(
        lambda group: _weighted_mean(group, "strict_improvement_bps"),
        include_groups=False,
    )
    savings = (
        frame["requested_notional"]
        * (BASE_TAKER_COST_BPS - frame["strict_effective_cost_bps"])
        / 10_000.0
    )
    by_asset = savings.groupby(frame["asset"]).sum().sort_values(ascending=False)
    total_savings = float(savings.sum())
    top_asset = str(by_asset.index[0]) if not by_asset.empty else None
    top_share = float(by_asset.iloc[0] / total_savings) if total_savings > 0.0 else float("nan")
    ex_top = frame.loc[frame["asset"] != top_asset] if top_asset is not None else frame
    asset_improvement = frame.groupby("asset").apply(
        lambda group: _weighted_mean(group, "strict_improvement_bps"),
        include_groups=False,
    )
    negative_assets = int((asset_improvement < 0.0).sum())
    healthy = frame.loc[~frame["asset"].isin(asset_improvement[asset_improvement < 0.0].index)]
    return {
        "weeks": int(len(weekly)),
        "positive_weeks": int((weekly > 0.0).sum()),
        "weeks_ge_5bps": int((weekly >= 5.0).sum()),
        "top_savings_asset": top_asset,
        "top_savings_share": top_share,
        "ex_top_savings_improvement_bps": _weighted_mean(ex_top, "strict_improvement_bps"),
        "negative_assets": negative_assets,
        "ex_negative_assets_improvement_bps": _weighted_mean(
            healthy, "strict_improvement_bps"
        ),
    }


def _acceptance_checks(
    *,
    covered_events: int,
    event_coverage: float,
    notional_coverage: float,
    strict_fill_rate: float,
    weighted_improvement_bps: float,
) -> dict[str, bool]:
    return {
        "events_ge_200": covered_events >= 200,
        "event_coverage_ge_70pct": event_coverage >= 0.70,
        "notional_coverage_ge_70pct": notional_coverage >= 0.70,
        "strict_fill_ge_70pct": strict_fill_rate >= 0.70,
        "weighted_improvement_ge_5bps": weighted_improvement_bps >= 5.0,
    }


def _report(
    events: pd.DataFrame,
    errors: pd.DataFrame,
    summaries: dict[str, pd.DataFrame],
    *,
    equity: float,
    expected_events: int | None = None,
    expected_notional: float | None = None,
    haircut_summary: pd.DataFrame | None = None,
    haircut_breakdowns: dict[str, pd.DataFrame] | None = None,
) -> str:
    requested = float(events["requested_notional"].sum()) if not events.empty else 0.0
    strict_maker = float(events["strict_maker_filled_notional"].sum()) if not events.empty else 0.0
    strict_taker = float(events["strict_taker_filled_notional"].sum()) if not events.empty else 0.0
    strict_cost = _weighted_mean(events, "strict_effective_cost_bps") if not events.empty else float("nan")
    strict_improvement = _weighted_mean(events, "strict_improvement_bps") if not events.empty else float("nan")
    strict_cost_p95 = (
        float(events["strict_effective_cost_bps"].quantile(0.95)) if not events.empty else float("nan")
    )
    event_coverage = len(events) / expected_events if expected_events else float("nan")
    notional_coverage = requested / expected_notional if expected_notional else float("nan")
    omitted_notional = (
        max(0.0, expected_notional - requested) if expected_notional is not None else float("nan")
    )
    scale_adjustments = (
        int((events["depth_scale_adjustment"] != 1.0).sum()) if not events.empty else 0
    )
    max_reference_age = (
        float(events["reference_age_seconds"].max()) if not events.empty else float("nan")
    )
    median_trade_count = (
        float(events["trade_count"].median()) if not events.empty else float("nan")
    )
    robustness = _robustness_metrics(events)
    checks = _acceptance_checks(
        covered_events=len(events),
        event_coverage=event_coverage,
        notional_coverage=notional_coverage,
        strict_fill_rate=strict_maker / requested if requested else 0.0,
        weighted_improvement_bps=strict_improvement if np.isfinite(strict_improvement) else -float("inf"),
    )
    verdict = "PASS (shadow candidate only)" if all(checks.values()) else "FAIL"
    haircut_checks = _haircut_acceptance(
        haircut_summary if haircut_summary is not None else pd.DataFrame(),
        coverage_checks={
            "events_ge_200": checks["events_ge_200"],
            "notional_coverage_ge_70pct": checks["notional_coverage_ge_70pct"],
        },
    )
    haircut_verdict = (
        "PASS under 25% volume-capacity haircut (shadow only)"
        if haircut_checks and all(haircut_checks.values())
        else "FAIL"
    )
    haircut_robustness: dict[str, Any] | None = None
    minimum_haircut: float | None = None
    if haircut_summary is not None and not haircut_summary.empty and not events.empty:
        minimum_haircut = float(haircut_summary["haircut"].min())
        prefix = f"haircut_{_haircut_tag(minimum_haircut)}"
        scenario_events = events.copy()
        scenario_events["strict_improvement_bps"] = events[
            f"{prefix}_improvement_bps"
        ]
        scenario_events["strict_effective_cost_bps"] = events[
            f"{prefix}_effective_cost_bps"
        ]
        haircut_robustness = _robustness_metrics(scenario_events)
    lines = [
        "# Bitget trade-tape maker shadow",
        "",
        "- status: execution research only; orders sent: **no**",
        f"- equity reference: **{equity:.2f} USDT**",
        f"- expected sample events: **{expected_events if expected_events is not None else 'n/a'}**; covered: **{len(events)}**; errors: **{len(errors)}**",
        f"- event coverage: **{event_coverage:.4%}**",
        f"- expected sample notional: **{expected_notional:.2f} USDT**" if expected_notional is not None else "- expected sample notional: n/a",
        f"- covered requested notional: **{requested:.2f} USDT**",
        f"- omitted requested notional: **{omitted_notional:.2f} USDT**",
        f"- notional coverage: **{notional_coverage:.4%}**",
        f"- power-of-ten depth scale adjustments: **{scale_adjustments}** events",
        f"- max reference depth age: **{max_reference_age:.0f} seconds**",
        f"- median trades per event window: **{median_trade_count:.0f}**",
        f"- strict maker fill rate: **{strict_maker / requested:.4%}**" if requested else "- strict maker fill rate: n/a",
        f"- strict taker fallback notional: **{strict_taker:.2f} USDT**",
        f"- notional-weighted strict effective cost: **{strict_cost:.4f} bps**",
        f"- notional-weighted strict improvement vs 20bps taker: **{strict_improvement:.4f} bps**",
        f"- strict effective cost p95: **{strict_cost_p95:.4f} bps**",
        f"- acceptance verdict: **{verdict}**",
        "",
        "## Acceptance checks",
        "",
        *[f"- [{'x' if passed else ' '}] {name}" for name, passed in checks.items()],
        "",
        "## Robustness",
        "",
        f"- weeks with positive weighted improvement: **{robustness['positive_weeks']} / {robustness['weeks']}**",
        f"- weeks with at least 5bps improvement: **{robustness['weeks_ge_5bps']} / {robustness['weeks']}**",
        f"- largest savings contributor: **{robustness['top_savings_asset']}** at **{robustness['top_savings_share']:.2%}** of total savings",
        f"- weighted improvement excluding that asset: **{robustness['ex_top_savings_improvement_bps']:.4f} bps**",
        f"- negative assets: **{robustness['negative_assets']}**; weighted improvement excluding them: **{robustness['ex_negative_assets_improvement_bps']:.4f} bps**",
        "",
        "## Fill haircut sensitivity",
        "",
        haircut_summary.to_csv(index=False)
        if haircut_summary is not None and not haircut_summary.empty
        else "No haircut sensitivity requested.",
        "",
        f"- haircut acceptance verdict: **{haircut_verdict}**",
        "",
        *[f"- [{'x' if passed else ' '}] {name}" for name, passed in haircut_checks.items()],
        "",
        (
            f"- at {minimum_haircut:.0%} haircut: positive weeks "
            f"**{haircut_robustness['positive_weeks']} / {haircut_robustness['weeks']}**, "
            f">=5bps weeks **{haircut_robustness['weeks_ge_5bps']} / {haircut_robustness['weeks']}**, "
            f"improvement excluding **{haircut_robustness['top_savings_asset']}** "
            f"**{haircut_robustness['ex_top_savings_improvement_bps']:.4f}bps**"
            if haircut_robustness is not None and minimum_haircut is not None
            else "- haircut robustness: n/a"
        ),
        "",
        "### Fill haircut by side",
        "",
        haircut_breakdowns["side"].to_csv(index=False)
        if haircut_breakdowns is not None and not haircut_breakdowns["side"].empty
        else "No side breakdown.",
        "",
        "Full monthly and asset breakdowns are in `haircut_month.csv` and `haircut_asset.csv`.",
        "",
        "## By side",
        "",
        summaries["side"].to_csv(index=False) if not summaries["side"].empty else "No covered events.",
        "",
        "## By month",
        "",
        summaries["monthly"].to_csv(index=False) if not summaries["monthly"].empty else "No covered events.",
        "",
        "## By asset",
        "",
        summaries["asset"].to_csv(index=False) if not summaries["asset"].empty else "No covered events.",
        "",
        "## Interpretation guardrail",
        "",
        "Strict fill means an actual aggressor-side trade printed through the limit by 1bp; touch is the optimistic upper bound. Neither proves queue position, hidden liquidity, partial-fill priority or real order acceptance. This output cannot promote a strategy by itself.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--trades-path", type=Path, default=DEFAULT_TRADES)
    parser.add_argument("--symbol-map", type=Path, default=DEFAULT_SYMBOL_MAP)
    parser.add_argument("--cache-dir", type=Path, default=Path("data/raw/bitget_history"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--start-date", default="2026-01-01")
    parser.add_argument("--end-date", default="2026-09-21")
    parser.add_argument("--equity", type=float, default=500.0)
    parser.add_argument("--timeout-hours", type=float, default=2.0)
    parser.add_argument("--offset-bps", type=float, default=5.0)
    parser.add_argument("--through-bps", type=float, default=1.0)
    parser.add_argument("--guard-bps", type=float, default=30.0)
    parser.add_argument("--max-depth-age-minutes", type=float, default=10.0)
    parser.add_argument("--download-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--haircut-sensitivity", default="0.25,0.5,0.75")
    parser.add_argument("--max-events", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.equity <= 0.0:
        parser.error("--equity must be positive")
    if args.timeout_hours <= 0.0:
        parser.error("--timeout-hours must be positive")
    if args.start_date > args.end_date:
        parser.error("--start-date must be on or before --end-date")
    try:
        haircut_sensitivity = _parse_haircuts(str(args.haircut_sensitivity))
    except ValueError as exc:
        parser.error(str(exc))

    trades = pd.read_csv(args.trades_path, parse_dates=["timestamp"])
    trades["timestamp"] = pd.to_datetime(trades["timestamp"], utc=True)
    start = pd.Timestamp(args.start_date, tz="UTC")
    end = pd.Timestamp(args.end_date, tz="UTC") + pd.Timedelta(days=1)
    trades = trades.loc[(trades["timestamp"] >= start) & (trades["timestamp"] < end)].copy()
    if trades.empty:
        raise SystemExit("no trades in the requested window")
    symbol_map = pd.read_csv(args.symbol_map)
    expected_events = int(len(trades))
    expected_notional = float(abs(trades["notional"]).sum()) * float(args.equity)

    output_dir: Path = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "events": output_dir / "events.csv",
        "errors": output_dir / "errors.csv",
        "monthly": output_dir / "monthly.csv",
        "side": output_dir / "side.csv",
        "asset": output_dir / "asset.csv",
        "haircuts": output_dir / "haircuts.csv",
        "haircut_side": output_dir / "haircut_side.csv",
        "haircut_month": output_dir / "haircut_month.csv",
        "haircut_asset": output_dir / "haircut_asset.csv",
        "report": output_dir / "report.md",
        "manifest": output_dir / "manifest.json",
    }
    existing = [path for path in files.values() if path.exists()]
    if existing and not args.overwrite:
        raise SystemExit(f"output already exists: {existing[0]}; pass --overwrite")

    session = requests.Session()
    rows, errors = _event_rows(
        trades=trades,
        symbol_map=symbol_map,
        session=session,
        cache_dir=args.cache_dir,
        equity=float(args.equity),
        min_trade_usdt=0.0,
        timeout_hours=float(args.timeout_hours),
        offset_bps=float(args.offset_bps),
        through_bps=float(args.through_bps),
        guard_bps=float(args.guard_bps),
        max_depth_age_minutes=float(args.max_depth_age_minutes),
        download_timeout_seconds=float(args.download_timeout_seconds),
        max_events=args.max_events,
        haircut_sensitivity=haircut_sensitivity,
    )
    events = pd.DataFrame(rows)
    error_frame = pd.DataFrame(
        errors,
        columns=[
            "event_index",
            "timestamp",
            "asset",
            "symbol",
            "position_side",
            "action",
            "exec_side",
            "requested_notional",
            "venue_min_trade_usdt",
            "reason",
            "date",
            "error",
        ],
    )
    summaries = _summaries(events)
    haircut_summary = _haircut_summary(events, haircut_sensitivity)
    haircut_breakdowns = _haircut_breakdowns(events, haircut_sensitivity)
    events.to_csv(files["events"], index=False)
    error_frame.to_csv(files["errors"], index=False)
    summaries["monthly"].to_csv(files["monthly"], index=False)
    summaries["side"].to_csv(files["side"], index=False)
    summaries["asset"].to_csv(files["asset"], index=False)
    haircut_summary.to_csv(files["haircuts"], index=False)
    haircut_breakdowns["side"].to_csv(files["haircut_side"], index=False)
    haircut_breakdowns["month"].to_csv(files["haircut_month"], index=False)
    haircut_breakdowns["asset"].to_csv(files["haircut_asset"], index=False)
    files["report"].write_text(
        _report(
            events,
            error_frame,
            summaries,
            equity=float(args.equity),
            expected_events=expected_events,
            expected_notional=expected_notional,
            haircut_summary=haircut_summary,
            haircut_breakdowns=haircut_breakdowns,
        ),
        encoding="utf-8",
    )
    requested_covered = (
        float(events["requested_notional"].sum()) if not events.empty else 0.0
    )
    strict_maker_covered = (
        float(events["strict_maker_filled_notional"].sum()) if not events.empty else 0.0
    )
    strict_improvement = (
        _weighted_mean(events, "strict_improvement_bps") if not events.empty else 0.0
    )
    acceptance = _acceptance_checks(
        covered_events=int(len(events)),
        event_coverage=(
            float(len(events)) / expected_events if expected_events > 0 else 0.0
        ),
        notional_coverage=(
            requested_covered / expected_notional if expected_notional > 0.0 else 0.0
        ),
        strict_fill_rate=(
            strict_maker_covered / requested_covered if requested_covered > 0.0 else 0.0
        ),
        weighted_improvement_bps=strict_improvement,
    )
    haircut_checks = _haircut_acceptance(
        haircut_summary,
        coverage_checks={
            "events_ge_200": acceptance["events_ge_200"],
            "notional_coverage_ge_70pct": acceptance["notional_coverage_ge_70pct"],
        },
    )
    manifest = {
        "trades_path": str(args.trades_path),
        "symbol_map": str(args.symbol_map),
        "start_date": args.start_date,
        "end_date": args.end_date,
        "equity_reference": float(args.equity),
        "timeout_hours": float(args.timeout_hours),
        "offset_bps": float(args.offset_bps),
        "through_bps": float(args.through_bps),
        "guard_bps": float(args.guard_bps),
        "maker_fee_bps": MAKER_FEE_BPS,
        "taker_fee_bps": TAKER_FEE_BPS,
        "events_expected": expected_events,
        "events_covered": int(len(events)),
        "events_error": int(len(errors)),
        "notional_expected": expected_notional,
        "notional_covered": float(events["requested_notional"].sum()) if not events.empty else 0.0,
        "strict_maker_fill_rate": (
            strict_maker_covered / requested_covered if requested_covered > 0.0 else None
        ),
        "strict_weighted_improvement_bps": strict_improvement,
        "acceptance_checks": acceptance,
        "acceptance_verdict": "pass" if all(acceptance.values()) else "fail",
        "haircut_sensitivity": list(haircut_sensitivity),
        "haircut_acceptance_checks": haircut_checks,
        "haircut_acceptance_verdict": (
            "pass" if haircut_checks and all(haircut_checks.values()) else "fail"
        ),
        "cache_dir": str(args.cache_dir),
        "read_only": True,
        "orders_sent": False,
    }
    files["manifest"].write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output_dir} with {len(events)} covered events and {len(errors)} errors")


if __name__ == "__main__":
    main()
