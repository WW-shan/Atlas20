"""Download Bitget USDT-M derivative research data for the PIT Top20.

The script is deliberately resumable.  It stores one CSV per
``<symbol>_<candle_type>.csv`` and a small ``state.json`` keyed by 89-day
window.  A completed or known-missing window is never fetched twice unless
``--force`` is passed.  ``--max-requests`` provides a bounded run for CI or an
initial coverage audit without hammering the public endpoint.

Usage::

    .venv/bin/python scripts/download_bitget_derivatives_data.py \
        --sample-windows 4 --max-requests 600

    .venv/bin/python scripts/download_bitget_derivatives_data.py \
        --start 2022-01-01 --end 2026-09-21
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.derivatives.bitget import BitgetClient, CANDLE_COLUMNS  # noqa: E402
from atlas20.derivatives.mapping import build_symbol_map  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir, get_logger  # noqa: E402

LOGGER = get_logger(__name__)
DEFAULT_TYPES = ("mark", "index", "market")
_WINDOW_DAYS = 89


def _read_panel(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, usecols=["coin_id", "symbol"])
    frame["coin_id"] = frame["coin_id"].astype(str)
    frame["symbol"] = frame["symbol"].astype(str)
    return frame


def _iter_windows(start: pd.Timestamp, end: pd.Timestamp) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    windows: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    cursor = start
    while cursor < end:
        stop = min(cursor + pd.Timedelta(days=_WINDOW_DAYS), end)
        windows.append((cursor, stop))
        cursor = stop
    return windows


def _sample_windows(
    start: pd.Timestamp,
    end: pd.Timestamp,
    count: int,
) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Return ``count`` evenly spaced 7-day windows inside [start, end)."""
    if count <= 0:
        return _iter_windows(start, end)
    total_days = max((end - start).days, 1)
    window_days = min(7, max(total_days // max(count, 1), 1))
    offsets = [round(index * (total_days - window_days) / max(count - 1, 1)) for index in range(count)]
    return [
        (start + pd.Timedelta(days=offset), min(start + pd.Timedelta(days=offset + window_days), end))
        for offset in sorted(set(offsets))
    ]


def _load_state(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_state(path: Path, state: dict[str, dict[str, Any]]) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _merge_candles(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    frames = [frame for frame in (existing, new) if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame(columns=CANDLE_COLUMNS)
    combined = pd.concat(frames, ignore_index=True)
    combined["open_time"] = pd.to_datetime(combined["open_time"], utc=True)
    for column in CANDLE_COLUMNS[1:]:
        combined[column] = pd.to_numeric(combined[column], errors="coerce")
    combined = combined.drop_duplicates("open_time", keep="last").sort_values("open_time")
    return combined.reset_index(drop=True)


def _max_gap_hours(frame: pd.DataFrame) -> float:
    if len(frame) < 2:
        return 0.0
    times = pd.to_datetime(frame["open_time"], utc=True).sort_values()
    gaps = times.diff().dropna().dt.total_seconds() / 3600.0
    return float(gaps.max()) if not gaps.empty else 0.0


def _max_gap_hours_within_windows(
    frame: pd.DataFrame,
    windows: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> float:
    if frame.empty:
        return 0.0
    max_gap = 0.0
    times = pd.to_datetime(frame["open_time"], utc=True)
    for start, end in windows:
        subset = frame.loc[(times >= start) & (times < end)]
        max_gap = max(max_gap, _max_gap_hours(subset))
    return max_gap


def _coverage_row(
    coin_id: str,
    symbol: str,
    candle_type: str,
    frame: pd.DataFrame,
    window_state: dict[str, Any],
    windows: list[tuple[pd.Timestamp, pd.Timestamp]],
) -> dict[str, Any]:
    complete = sum(1 for value in window_state.values() if value.get("status") == "complete")
    missing = sum(1 for value in window_state.values() if value.get("status") == "missing")
    return {
        "coin_id": coin_id,
        "bitget_symbol": symbol,
        "candle_type": candle_type,
        "rows": int(len(frame)),
        "first": frame["open_time"].min() if not frame.empty else pd.NaT,
        "last": frame["open_time"].max() if not frame.empty else pd.NaT,
        "complete_windows": complete,
        "missing_windows": missing,
        "window_coverage": complete / (complete + missing) if complete + missing else 0.0,
        "max_gap_hours": _max_gap_hours_within_windows(frame, windows),
    }


def _download_funding(
    client: BitgetClient,
    symbol_map: pd.DataFrame,
    output_dir: Path,
    *,
    force: bool,
) -> dict[str, Any]:
    funding_dir = ensure_dir(output_dir / "funding")
    manifest: dict[str, Any] = {}
    for record in symbol_map.to_dict("records"):
        if not record.get("bitget_symbol"):
            continue
        coin_id = str(record["coin_id"])
        symbol = str(record["bitget_symbol"])
        path = funding_dir / f"{coin_id}.csv"
        if path.exists() and not force:
            frame = pd.read_csv(path)
            if not frame.empty:
                manifest[coin_id] = {
                    "symbol": symbol,
                    "rows": int(len(frame)),
                    "first": str(pd.to_datetime(frame["funding_time"], utc=True).min()),
                    "last": str(pd.to_datetime(frame["funding_time"], utc=True).max()),
                    "cached": True,
                }
                continue
        try:
            frame = client.fetch_funding_history(symbol)
        except Exception as exc:  # noqa: BLE001 - one bad contract must not abort the audit
            LOGGER.warning("funding %s (%s) failed: %s", coin_id, symbol, exc)
            manifest[coin_id] = {"symbol": symbol, "available": False, "error": str(exc)}
            continue
        if frame.empty:
            manifest[coin_id] = {"symbol": symbol, "available": False, "reason": "no funding rows"}
            continue
        frame.to_csv(path, index=False)
        manifest[coin_id] = {
            "symbol": symbol,
            "rows": int(len(frame)),
            "first": str(frame["funding_time"].min()),
            "last": str(frame["funding_time"].max()),
            "cached": False,
        }
    (output_dir / "funding_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--panel", type=Path, default=Path("data/processed/panel_daily.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/bitget_derivatives"))
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--end", default="2026-09-21")
    parser.add_argument("--types", default=",".join(DEFAULT_TYPES))
    parser.add_argument("--symbols", default="", help="Comma-separated coin ids or Bitget symbols")
    parser.add_argument("--max-symbols", type=int, default=0)
    parser.add_argument("--sample-windows", type=int, default=0, help="0 downloads the full range")
    parser.add_argument("--max-requests", type=int, default=0, help="0 means unlimited")
    parser.add_argument("--rate-limit-seconds", type=float, default=0.05)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--funding-only", action="store_true")
    parser.add_argument("--skip-funding", action="store_true")
    args = parser.parse_args()
    configure_logging("INFO")

    start = pd.Timestamp(args.start, tz="UTC")
    end = pd.Timestamp(args.end, tz="UTC")
    if end <= start:
        raise SystemExit("--end must be after --start")
    types = [item.strip() for item in args.types.split(",") if item.strip()]
    output_dir = ensure_dir(args.output_dir)
    candle_dir = ensure_dir(output_dir / "candles")
    state_path = output_dir / "state.json"
    state = _load_state(state_path)

    panel = _read_panel(args.panel)
    client = BitgetClient(rate_limit_seconds=args.rate_limit_seconds)
    contracts = client.fetch_contracts()
    symbol_map = build_symbol_map(panel, contracts)
    symbol_map.to_csv(output_dir / "symbol_map.csv", index=False)
    (output_dir / "contracts.json").write_text(
        json.dumps(contracts, indent=2, sort_keys=True), encoding="utf-8"
    )
    LOGGER.info("Bitget contracts: %s; mapped coins: %s", len(contracts), int(symbol_map["bitget_symbol"].ne("").sum()))

    selected = symbol_map[symbol_map["bitget_symbol"].ne("")].copy()
    if args.symbols:
        wanted = {item.strip().lower() for item in args.symbols.split(",") if item.strip()}
        selected = selected[
            selected["coin_id"].str.lower().isin(wanted)
            | selected["bitget_symbol"].str.lower().isin(wanted)
        ]
    if args.max_symbols > 0:
        selected = selected.head(args.max_symbols)
    if selected.empty:
        raise SystemExit("no Bitget contracts selected")

    if not args.skip_funding:
        _download_funding(client, selected, output_dir, force=args.force)
    if args.funding_only:
        print(f"wrote {output_dir} (funding only)")
        return

    windows = (
        _sample_windows(start, end, args.sample_windows)
        if args.sample_windows > 0
        else _iter_windows(start, end)
    )
    LOGGER.info("candle windows: %s x %s symbols x %s types", len(windows), len(selected), len(types))

    coverage_rows: list[dict[str, Any]] = []
    for record in selected.to_dict("records"):
        coin_id = str(record["coin_id"])
        symbol = str(record["bitget_symbol"])
        for candle_type in types:
            state_key = f"{symbol}_{candle_type}"
            window_state: dict[str, Any] = state.setdefault(state_key, {})
            path = candle_dir / f"{symbol}_{candle_type}.csv"
            existing = pd.read_csv(path) if path.exists() and not args.force else pd.DataFrame(columns=CANDLE_COLUMNS)
            for window_start, window_end in windows:
                key = window_start.isoformat()
                if not args.force and window_state.get(key, {}).get("status") in {"complete", "missing"}:
                    continue
                if args.max_requests > 0 and client.request_count >= args.max_requests:
                    LOGGER.warning("request budget reached at %s %s", symbol, candle_type)
                    break
                try:
                    frame = client.fetch_history_candles(symbol, candle_type, window_start, window_end)
                except Exception as exc:  # noqa: BLE001 - keep the audit moving across contracts
                    LOGGER.warning("%s %s %s failed: %s", coin_id, symbol, candle_type, exc)
                    window_state[key] = {"status": "error", "error": str(exc)}
                    _save_state(state_path, state)
                    continue
                existing = _merge_candles(existing, frame)
                window_state[key] = {
                    "status": "complete" if not frame.empty else "missing",
                    "rows": int(len(frame)),
                }
                _save_state(state_path, state)
            existing.to_csv(path, index=False)
            coverage_rows.append(_coverage_row(coin_id, symbol, candle_type, existing, window_state, windows))
            LOGGER.info(
                "%s %s: %s rows, %s complete windows, %s missing",
                symbol,
                candle_type,
                len(existing),
                window_state and sum(1 for value in window_state.values() if value.get("status") == "complete"),
                sum(1 for value in window_state.values() if value.get("status") == "missing"),
            )

    coverage = pd.DataFrame(coverage_rows)
    coverage.to_csv(output_dir / "coverage.csv", index=False)
    (output_dir / "coverage.json").write_text(
        json.dumps(coverage_rows, indent=2, sort_keys=True, default=str), encoding="utf-8"
    )
    print(f"wrote {output_dir} ({len(selected)} symbols, {client.request_count} requests)")


if __name__ == "__main__":
    main()
