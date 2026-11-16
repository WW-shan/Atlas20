"""Prove every unrankable panel market cap against raw CoinMarketCap data.

The processed panel intentionally keeps short historical CMC zero-supply
omissions visible as rows with no market cap.  The universe builder refuses to
rank those rows and never forward-fills them.  This audit records the exact
provider values behind each omission so a future real data-loss bug cannot be
confused with a historical provider fact.
"""

from __future__ import annotations

import argparse
from collections import Counter
import json
from math import isfinite
from pathlib import Path
import sys
from typing import Any, Mapping

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.config import load_config  # noqa: E402
from atlas20.logging_utils import atomic_write_text, ensure_dir  # noqa: E402


def _normalise_date(value: object) -> pd.Timestamp | None:
    stamp = pd.to_datetime(value, utc=True, errors="coerce")
    return None if pd.isna(stamp) else pd.Timestamp(stamp).normalize()


def _number(value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return float("nan")
    return parsed if isfinite(parsed) else float("nan")


def _raw_rows_by_date(
    history_dir: Path,
    cmc_id: int,
    wanted_dates: set[pd.Timestamp],
) -> dict[pd.Timestamp, tuple[dict[str, Any], Path]]:
    """Return the newest cached CMC row for each date of one coin id."""

    by_date: dict[pd.Timestamp, tuple[dict[str, Any], Path]] = {}
    requested_start = min(wanted_dates)
    requested_end = max(wanted_dates)
    for path in sorted(Path(history_dir).glob(f"{int(cmc_id)}_*.json")):
        try:
            _, start_text, end_text = path.stem.split("_", 2)
            file_start = pd.Timestamp(int(start_text), unit="s", tz="UTC")
            file_end = pd.Timestamp(int(end_text), unit="s", tz="UTC")
        except (ValueError, TypeError):
            file_start = file_end = None
        if (
            file_start is not None
            and file_end is not None
            and (
                file_end <= requested_start
                or file_start > requested_end + pd.Timedelta(days=1)
            )
        ):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, list):
            continue
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            stamp = _normalise_date(raw.get("timeOpen") or raw.get("timeClose"))
            quote = raw.get("quote")
            if stamp not in wanted_dates or not isinstance(quote, dict):
                continue
            by_date[stamp] = (quote, path)
    return by_date


def build_market_cap_gap_evidence(
    panel: pd.DataFrame,
    *,
    history_dir: Path,
    cmc_ids: Mapping[str, int],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Return one evidence row per panel row with no usable market cap."""

    required = {"date", "coin_id", "symbol", "market_cap"}
    missing = required.difference(panel.columns)
    if missing:
        raise ValueError(f"panel is missing columns: {sorted(missing)}")
    frame = panel.copy()
    frame["_date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce").dt.normalize()
    frame["_cap"] = pd.to_numeric(frame["market_cap"], errors="coerce")
    invalid = frame.loc[~frame["_cap"].gt(0.0)].copy()

    cache: dict[int, dict[pd.Timestamp, tuple[dict[str, Any], Path]]] = {}
    wanted_by_id: dict[int, set[pd.Timestamp]] = {}
    for record in invalid.to_dict("records"):
        cmc_id = cmc_ids.get(str(record.get("symbol") or "").strip().upper())
        date = record.get("_date")
        if cmc_id is not None and not pd.isna(date):
            wanted_by_id.setdefault(int(cmc_id), set()).add(pd.Timestamp(date))
    rows: list[dict[str, Any]] = []
    for record in invalid.to_dict("records"):
        symbol = str(record.get("symbol") or "").strip().upper()
        cmc_id = cmc_ids.get(symbol)
        date = record.get("_date")
        row: dict[str, Any] = {
            "date": None if pd.isna(date) else pd.Timestamp(date).date().isoformat(),
            "coin_id": str(record.get("coin_id") or ""),
            "symbol": symbol,
            "cmc_id": cmc_id,
            "panel_market_cap": None,
            "raw_market_cap": None,
            "raw_circulating_supply": None,
            "raw_close": None,
            "raw_file": None,
            "rankable": False,
            "status": "",
        }
        if cmc_id is None:
            row["status"] = "missing_cmc_id"
            rows.append(row)
            continue
        if pd.isna(date):
            row["status"] = "invalid_panel_date"
            rows.append(row)
            continue
        if int(cmc_id) not in cache:
            cache[int(cmc_id)] = _raw_rows_by_date(
                history_dir,
                int(cmc_id),
                wanted_by_id[int(cmc_id)],
            )
        raw = cache[int(cmc_id)].get(pd.Timestamp(date))
        if raw is None:
            row["status"] = "missing_raw_cmc_row"
            rows.append(row)
            continue
        quote, path = raw
        market_cap = _number(quote.get("marketCap"))
        supply = _number(quote.get("circulatingSupply"))
        close = _number(quote.get("close"))
        row.update(
            {
                "raw_market_cap": None if pd.isna(market_cap) else market_cap,
                "raw_circulating_supply": None if pd.isna(supply) else supply,
                "raw_close": None if pd.isna(close) else close,
                "raw_file": path.name,
            }
        )
        if market_cap > 0.0 and supply > 0.0:
            row["status"] = "unexpected_missing_cap"
        elif market_cap <= 0.0 and supply <= 0.0:
            row["status"] = "provider_zero_supply"
        else:
            row["status"] = "inconsistent_provider_values"
        rows.append(row)

    evidence = pd.DataFrame(
        rows,
        columns=[
            "date",
            "coin_id",
            "symbol",
            "cmc_id",
            "panel_market_cap",
            "raw_market_cap",
            "raw_circulating_supply",
            "raw_close",
            "raw_file",
            "rankable",
            "status",
        ],
    )
    latest = (
        frame.sort_values(["_date", "coin_id"], kind="stable")
        .drop_duplicates("coin_id", keep="last")
        .copy()
    )
    affected = set(invalid["coin_id"].astype(str))
    affected_latest = latest.loc[latest["coin_id"].astype(str).isin(affected)]
    latest_panel_date = frame["_date"].max()
    latest_panel_rows = frame.loc[frame["_date"] == latest_panel_date].copy()
    affected_current = latest_panel_rows.loc[
        latest_panel_rows["coin_id"].astype(str).isin(affected)
    ]
    status_counts = Counter(str(value) for value in evidence.get("status", []))
    failing_statuses = {
        "missing_cmc_id",
        "invalid_panel_date",
        "missing_raw_cmc_row",
        "unexpected_missing_cap",
        "inconsistent_provider_values",
    }
    unexplained_rows = int(evidence["status"].isin(failing_statuses).sum()) if not evidence.empty else 0
    summary = {
        "panel_rows": int(len(frame)),
        "panel_assets": int(frame["coin_id"].nunique()),
        "invalid_market_cap_rows": int(len(evidence)),
        "unexplained_rows": unexplained_rows,
        "status_counts": dict(sorted(status_counts.items())),
        "affected_assets": sorted(affected),
        "affected_asset_count": len(affected),
        "latest_panel_rows_valid": bool(
            len(latest_panel_rows) and latest_panel_rows["_cap"].gt(0.0).all()
        ),
        "latest_rows_valid": bool(
            len(latest_panel_rows) and latest_panel_rows["_cap"].gt(0.0).all()
        ),
        "affected_assets_current_valid": bool(affected_current["_cap"].gt(0.0).all()),
        "affected_assets_current_count": int(affected_current["coin_id"].nunique()),
        "affected_assets_last_observed_valid": bool(
            len(affected_latest) == len(affected) and affected_latest["_cap"].gt(0.0).all()
        ),
        "latest_panel_date": (
            pd.Timestamp(latest_panel_date).date().isoformat()
            if not pd.isna(latest_panel_date)
            else None
        ),
        "passed": unexplained_rows == 0,
    }
    return evidence, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--panel", type=Path, default=Path("data/processed/panel_daily.csv"))
    parser.add_argument("--history-dir", type=Path, default=None)
    parser.add_argument("--id-map", type=Path, default=None)
    parser.add_argument("--csv-out", type=Path, required=True)
    parser.add_argument("--json-out", type=Path, required=True)
    args = parser.parse_args(argv)

    config = load_config(args.config)
    raw_dir = config.resolve_path(config.paths.raw_dir)
    history_dir = args.history_dir or raw_dir / "coinmarketcap" / "history"
    id_map_path = args.id_map or raw_dir / "coinmarketcap" / "id_map.json"
    raw_ids = json.loads(id_map_path.read_text(encoding="utf-8"))
    cmc_ids = {str(symbol).upper(): int(cmc_id) for symbol, cmc_id in raw_ids.items()}
    cmc_ids.update(
        {
            str(symbol).upper(): int(cmc_id)
            for symbol, cmc_id in config.universe.cmc_symbol_aliases.items()
        }
    )
    panel = pd.read_csv(args.panel)
    evidence, summary = build_market_cap_gap_evidence(
        panel,
        history_dir=history_dir,
        cmc_ids=cmc_ids,
    )
    ensure_dir(args.csv_out.parent)
    ensure_dir(args.json_out.parent)
    evidence.to_csv(args.csv_out, index=False)
    atomic_write_text(args.json_out, json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"wrote {args.csv_out}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
