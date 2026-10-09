"""Splice Binance proxy marks into a copy of the pre-2022 Bitget mark tree.

The 2020-10 → 2022-01 stress window is limited by Bitget contract history:
only 32 contracts have mark data there, so the §12.8.9 run dropped 199
target rows to cash and could not claim "no liquidation" for the rest of the
universe.  This script builds a **labelled proxy tree**: for every coin whose
Bitget mark is missing, the Binance 1-hour spot candles (already downloaded
for the execution-lag work) are used as a proxy mark path.  Bitget mark rows
are never overwritten — proxy rows are only prepended before a contract's
first Bitget mark hour, or used alone when Bitget has no row at all.  The
seam basis (last proxy close before the seam vs first Bitget mark open) is
recorded so a splice artefact cannot silently masquerade as a drawdown.

The output tree exists to re-check the kill criterion ("no liquidation in
2020-10 → 2021-12") on a wider asset set.  It must never be used for
headline performance: the price source is a competitor's spot tape, not the
venue that would have liquidated the position.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.logging_utils import configure_logging, ensure_dir, get_logger  # noqa: E402

CANDLE_COLUMNS = ["open_time", "open", "high", "low", "close", "volume", "quote_volume"]
LOGGER = get_logger(__name__)


def _read_candles(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    frame = pd.read_csv(path)
    if frame.empty or "open_time" not in frame.columns:
        return None
    missing = [column for column in CANDLE_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"{path}: missing candle columns {missing}")
    frame = frame.loc[:, CANDLE_COLUMNS].copy()
    frame["open_time"] = pd.to_datetime(frame["open_time"], utc=True, format="mixed")
    frame = frame.dropna(subset=["open_time"])
    frame = frame[~frame["open_time"].duplicated(keep="last")].sort_values("open_time")
    return frame.reset_index(drop=True)


def _format_time(frame: pd.DataFrame) -> pd.Series:
    return frame["open_time"].dt.strftime("%Y-%m-%d %H:%M:%S+00:00")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bitget-dir", type=Path, default=Path("data/raw/bitget_derivatives/merged_pre2022_20261009"))
    parser.add_argument("--proxy-dir", type=Path, default=Path("data/raw/binance_1h_pre2022"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/bitget_derivatives/merged_pre2022_proxy_20261009"))
    parser.add_argument("--start", default="2020-10-01")
    args = parser.parse_args()

    configure_logging()
    symbol_map = pd.read_csv(args.bitget_dir / "symbol_map.csv")
    coverage_path = args.proxy_dir / "coverage.json"
    coverage = json.loads(coverage_path.read_text()) if coverage_path.exists() else {}

    output = ensure_dir(args.output_dir)
    candles_dir = ensure_dir(output / "candles")
    for name in ("symbol_map.csv", "contracts.json"):
        source = args.bitget_dir / name
        if source.exists():
            shutil.copyfile(source, output / name)

    start = pd.Timestamp(args.start, tz="UTC")
    manifest: list[dict[str, object]] = []
    counts = {"bitget_only": 0, "proxy_only": 0, "spliced": 0, "no_data": 0}
    for record in symbol_map.to_dict("records"):
        coin = str(record["coin_id"])
        symbol = str(record["bitget_symbol"])
        bitget = _read_candles(args.bitget_dir / "candles" / f"{symbol}_mark.csv")
        if bitget is not None:
            bitget = bitget.loc[bitget["open_time"] >= start]
        proxy_info = coverage.get(coin) or {}
        proxy = None
        if proxy_info.get("available"):
            pair = str(proxy_info.get("pair"))
            proxy = _read_candles(args.proxy_dir / f"{pair}.csv")
            if proxy is not None:
                proxy = proxy.loc[proxy["open_time"] >= start]

        merged: pd.DataFrame | None = None
        source = "no_data"
        seam_basis = None
        if bitget is not None and not bitget.empty:
            if proxy is not None and not proxy.empty:
                first_bitget = bitget["open_time"].min()
                before = proxy.loc[proxy["open_time"] < first_bitget]
                if not before.empty:
                    seam_basis = float(before["close"].iloc[-1]) / float(bitget["open"].iloc[0]) - 1.0
                    merged = pd.concat([before, bitget], ignore_index=True)
                    source = "spliced"
                else:
                    merged = bitget
                    source = "bitget_only"
            else:
                merged = bitget
                source = "bitget_only"
        elif proxy is not None and not proxy.empty:
            merged = proxy
            source = "proxy_only"

        counts[source] += 1
        entry = {
            "coin_id": coin,
            "bitget_symbol": symbol,
            "source": source,
            "bitget_rows": 0 if bitget is None else int(len(bitget)),
            "proxy_rows": 0 if proxy is None else int(len(proxy)),
            "rows": 0 if merged is None else int(len(merged)),
            "first": None if merged is None else str(merged["open_time"].min()),
            "last": None if merged is None else str(merged["open_time"].max()),
            "seam_basis": seam_basis,
        }
        manifest.append(entry)
        if merged is None:
            continue
        out = merged.copy()
        out["open_time"] = _format_time(out)
        out.to_csv(candles_dir / f"{symbol}_mark.csv", index=False)

    (output / "proxy_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    seam_frame = pd.DataFrame(
        [row for row in manifest if row["seam_basis"] is not None]
    )
    LOGGER.info("coin sources: %s", counts)
    if not seam_frame.empty:
        worst = seam_frame.reindex(seam_frame["seam_basis"].abs().sort_values(ascending=False).index).head(5)
        LOGGER.info(
            "splice seams (proxy close before seam vs Bitget mark open): %d seams, median |basis| %.4f%%, worst:",
            int(len(seam_frame)),
            100 * float(seam_frame["seam_basis"].abs().median()),
        )
        for row in worst.to_dict("records"):
            LOGGER.info("  %-24s %+8.3f%%", row["coin_id"], 100 * float(row["seam_basis"]))
    print(f"Wrote proxy-augmented pre-2022 tree to {output}")


if __name__ == "__main__":
    main()
