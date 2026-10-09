"""Audit downloaded Bitget derivative data against the project gates.

Outputs:

* ``coverage_audit.csv`` - per contract/candle-type window coverage;
* ``funding_overlap.csv`` - Bitget 90-day funding vs Binance archive proxy;
* ``missing_contracts.csv`` - PIT Top20 coins without a Bitget USDT-M contract;
* ``report.md`` - human-readable summary.

The script never downloads data.  Run
``scripts/download_bitget_derivatives_data.py`` first.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.logging_utils import configure_logging, ensure_dir, get_logger  # noqa: E402

LOGGER = get_logger(__name__)
_FUNDING_TOLERANCE = pd.Timedelta(hours=1)


def _funding_frame(path: Path, time_column: str, rate_column: str) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["funding_time", "funding_rate"])
    frame = pd.read_csv(path)
    if time_column not in frame.columns or rate_column not in frame.columns:
        return pd.DataFrame(columns=["funding_time", "funding_rate"])
    numeric_time = pd.to_numeric(frame[time_column], errors="coerce")
    if numeric_time.notna().any():
        funding_time = pd.to_datetime(numeric_time, unit="ms", utc=True, errors="coerce")
    else:
        funding_time = pd.to_datetime(frame[time_column], utc=True, errors="coerce")
    result = pd.DataFrame(
        {
            "funding_time": pd.to_datetime(funding_time, utc=True).astype("datetime64[ns, UTC]"),
            "funding_rate": pd.to_numeric(frame[rate_column], errors="coerce"),
        }
    )
    return result.dropna().sort_values("funding_time").reset_index(drop=True)


def funding_overlap(bitget: pd.DataFrame, binance: pd.DataFrame) -> dict[str, float | int | bool]:
    """Compare two funding series on their overlap window."""
    if bitget.empty or binance.empty:
        return {
            "overlap_rows": 0,
            "sign_agreement": np.nan,
            "pearson": np.nan,
            "median_abs_error_bps": np.nan,
            "p95_abs_error_bps": np.nan,
            "first_overlap": pd.NaT,
            "last_overlap": pd.NaT,
            "passed": False,
        }
    left = bitget.sort_values("funding_time").rename(columns={"funding_rate": "bitget_rate"})
    right = binance.sort_values("funding_time").rename(columns={"funding_rate": "binance_rate"})
    left["funding_time"] = pd.to_datetime(left["funding_time"], utc=True).astype("datetime64[ns, UTC]")
    right["funding_time"] = pd.to_datetime(right["funding_time"], utc=True).astype("datetime64[ns, UTC]")
    merged = pd.merge_asof(
        left,
        right,
        on="funding_time",
        direction="nearest",
        tolerance=_FUNDING_TOLERANCE,
    ).dropna(subset=["bitget_rate", "binance_rate"])
    if merged.empty:
        return {
            "overlap_rows": 0,
            "sign_agreement": np.nan,
            "pearson": np.nan,
            "median_abs_error_bps": np.nan,
            "p95_abs_error_bps": np.nan,
            "first_overlap": pd.NaT,
            "last_overlap": pd.NaT,
            "passed": False,
        }
    bitget_rate = merged["bitget_rate"].astype(float)
    binance_rate = merged["binance_rate"].astype(float)
    same_sign = ((bitget_rate > 0) & (binance_rate > 0)) | (
        (bitget_rate < 0) & (binance_rate < 0)
    ) | ((bitget_rate == 0) & (binance_rate == 0))
    abs_error_bps = (bitget_rate - binance_rate).abs() * 10_000.0
    if len(merged) >= 2 and bitget_rate.nunique() > 1 and binance_rate.nunique() > 1:
        pearson = float(bitget_rate.corr(binance_rate))
    elif bitget_rate.nunique() == 1 and binance_rate.nunique() == 1:
        pearson = 1.0 if float(bitget_rate.iloc[0]) == float(binance_rate.iloc[0]) else np.nan
    else:
        pearson = np.nan
    sign_agreement = float(same_sign.mean())
    median_error = float(abs_error_bps.median())
    p95_error = float(abs_error_bps.quantile(0.95))
    passed = bool(
        len(merged) >= 30
        and sign_agreement >= 0.95
        and np.isfinite(pearson)
        and pearson >= 0.95
        and median_error <= 1.0
        and p95_error <= 5.0
    )
    return {
        "overlap_rows": int(len(merged)),
        "sign_agreement": sign_agreement,
        "pearson": pearson,
        "median_abs_error_bps": median_error,
        "p95_abs_error_bps": p95_error,
        "first_overlap": merged["funding_time"].min(),
        "last_overlap": merged["funding_time"].max(),
        "passed": passed,
    }


def _load_symbol_map(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise SystemExit(f"missing symbol map: {path}")
    frame = pd.read_csv(path)
    frame["coin_id"] = frame["coin_id"].astype(str)
    frame["bitget_symbol"] = frame["bitget_symbol"].fillna("").astype(str)
    return frame


def _coverage_summary(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    if frame.empty:
        return frame
    frame["window_coverage"] = pd.to_numeric(frame["window_coverage"], errors="coerce")
    frame["max_gap_hours"] = pd.to_numeric(frame["max_gap_hours"], errors="coerce")
    return frame


def _funding_audit(
    bitget_dir: Path,
    binance_dir: Path,
    symbol_map: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for record in symbol_map.to_dict("records"):
        coin_id = str(record["coin_id"])
        symbol = str(record.get("bitget_symbol", ""))
        if not symbol:
            continue
        bitget_path = bitget_dir / f"{coin_id}.csv"
        bitget = _funding_frame(bitget_path, "funding_time", "funding_rate")
        binance = _funding_frame(binance_dir / f"{coin_id}.csv", "calc_time", "last_funding_rate")
        metrics = funding_overlap(bitget, binance)
        rows.append(
            {
                "coin_id": coin_id,
                "bitget_symbol": symbol,
                "available": bitget_path.exists() and not bitget.empty,
                **metrics,
            }
        )
    return pd.DataFrame(rows)


def _write_report(
    path: Path,
    symbol_map: pd.DataFrame,
    coverage: pd.DataFrame,
    funding: pd.DataFrame,
) -> None:
    mapped = symbol_map[symbol_map["bitget_symbol"].ne("")]
    missing = symbol_map[symbol_map["bitget_symbol"].eq("")]
    lines = [
        "# Bitget Derivatives Data Audit",
        "",
        f"- PIT Top20 coin ids in symbol map: {len(symbol_map)}",
        f"- Mapped to Bitget USDT-M: {len(mapped)}",
        f"- Missing Bitget contracts: {len(missing)}",
        "",
        "## Missing contracts",
        "",
    ]
    if missing.empty:
        lines.append("None.")
    else:
        lines.append("| coin_id | panel_symbol | reason |")
        lines.append("|---|---|---|")
        for record in missing.to_dict("records"):
            lines.append(f"| {record['coin_id']} | {record['panel_symbol']} | {record['reason']} |")
    lines.extend(["", "## Candle coverage", ""])
    if coverage.empty:
        lines.append("No coverage file found.")
    else:
        for candle_type, group in coverage.groupby("candle_type", sort=True):
            complete = int(group["complete_windows"].sum())
            missing_windows = int(group["missing_windows"].sum())
            total = complete + missing_windows
            ratio = complete / total if total else 0.0
            max_gap = float(group["max_gap_hours"].max()) if not group.empty else 0.0
            lines.append(
                f"- `{candle_type}`: {complete}/{total} windows complete "
                f"({ratio:.1%}), max observed gap {max_gap:.0f}h"
            )
    lines.extend(["", "## Funding overlap", ""])
    if funding.empty:
        lines.append("No funding overlap file found.")
    else:
        available = int(funding["available"].fillna(False).sum())
        passed = int(funding["passed"].fillna(False).sum())
        lines.append(f"- Bitget funding files present: {available}/{len(funding)}")
        lines.append(f"- Contracts with overlap rows: {int((funding['overlap_rows'] > 0).sum())}")
        lines.append(f"- Contracts passing all overlap gates: {passed}/{available}")
        failed = funding[funding["available"].fillna(False) & ~funding["passed"].fillna(False)].sort_values(
            "overlap_rows", ascending=False
        )
        if not failed.empty:
            lines.append("")
            lines.append("| coin_id | bitget_symbol | overlap | sign | pearson | median bps | p95 bps |")
            lines.append("|---|---|---:|---:|---:|---:|---:|")
            for record in failed.head(30).to_dict("records"):
                lines.append(
                    f"| {record['coin_id']} | {record['bitget_symbol']} | {record['overlap_rows']} | "
                    f"{record['sign_agreement']:.3f} | {record['pearson']:.3f} | "
                    f"{record['median_abs_error_bps']:.3f} | {record['p95_abs_error_bps']:.3f} |"
                )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/bitget_derivatives"))
    parser.add_argument("--binance-funding-dir", type=Path, default=Path("data/raw/binance_funding"))
    parser.add_argument("--report-dir", type=Path, default=Path("reports/derivatives_track_data_audit"))
    args = parser.parse_args()
    configure_logging("INFO")

    raw_dir = args.raw_dir
    report_dir = ensure_dir(args.report_dir)
    symbol_map = _load_symbol_map(raw_dir / "symbol_map.csv")
    coverage = _coverage_summary(raw_dir / "coverage.csv")
    funding = _funding_audit(raw_dir / "funding", args.binance_funding_dir, symbol_map)

    missing = symbol_map[symbol_map["bitget_symbol"].eq("")].copy()
    missing.to_csv(report_dir / "missing_contracts.csv", index=False)
    coverage.to_csv(report_dir / "coverage_audit.csv", index=False)
    funding.to_csv(report_dir / "funding_overlap.csv", index=False)
    _write_report(report_dir / "report.md", symbol_map, coverage, funding)

    summary = {
        "mapped_contracts": int(symbol_map["bitget_symbol"].ne("").sum()),
        "missing_contracts": int(len(missing)),
        "coverage_rows": int(len(coverage)),
        "funding_rows": int(len(funding)),
        "funding_available": int(funding["available"].fillna(False).sum()) if not funding.empty else 0,
        "funding_passed": int(funding["passed"].fillna(False).sum()) if not funding.empty else 0,
    }
    (report_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    LOGGER.info("audit complete: %s", summary)
    print(f"wrote {report_dir} ({summary})")


if __name__ == "__main__":
    main()
