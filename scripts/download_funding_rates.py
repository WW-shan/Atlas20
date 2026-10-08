"""Download Binance USDT-perpetual funding rates for every coin that has been Top20.

The daily panel the strategy trades on carries price, dollar volume and market
cap only.  Derivatives positioning - how much leverage longs are paying to hold
- is a different information set, and ``data.binance.vision`` publishes the
complete funding-rate history of every Binance USDT perpetual as one small
monthly archive per symbol (``.../monthly/fundingRate/<SYMBOL>/<SYMBOL>-fundingRate-<YYYY-MM>.zip``).
``fapi.binance.com`` is not reachable from every network, and the public
archive is the same data with no API key, so the archives are the source.

A coin is mapped to its perpetual symbol by the pair already recorded in
``data/raw/binance_1h/coverage.json``; tokens that Binance quotes in units of
1,000 get an explicit override (SHIB -> 1000SHIBUSDT, PEPE -> 1000PEPEUSDT,
LUNC -> 1000LUNCUSDT) and a few coins have no Binance perpetual at all (their
funding state is simply missing for the months they are in the Top20, which the
screen reports).

Usage::

    .venv/bin/python scripts/download_funding_rates.py
    .venv/bin/python scripts/download_funding_rates.py --start-month 2020-09 --end-month 2026-09
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import concurrent.futures as futures
import io
import json
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request
import zipfile

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.logging_utils import configure_logging, ensure_dir, get_logger  # noqa: E402

LOGGER = get_logger(__name__)
ARCHIVE_URL = (
    "https://data.binance.vision/data/futures/um/monthly/fundingRate/"
    "{symbol}/{symbol}-fundingRate-{month}.zip"
)
FUNDING_COLUMNS = ["calc_time", "funding_interval_hours", "last_funding_rate"]
# Binance quotes these tokens in units of 1,000 on the perpetual venue.
SYMBOL_OVERRIDES = {
    "shiba-inu": "1000SHIBUSDT",
    "pepe": "1000PEPEUSDT",
    "terra-luna": "1000LUNCUSDT",
}
# Gate-only pairs (underscore tickers) have no Binance perpetual.
NO_PERPETUAL = {"crypto-com-chain", "okb", "mantle", "leo-token"}


def _months(start_month: str, end_month: str) -> list[str]:
    periods = pd.period_range(start_month, end_month, freq="M")
    return [str(period) for period in periods]


def _perp_symbol(coin: str, spot_pair: str) -> str:
    if coin in SYMBOL_OVERRIDES:
        return SYMBOL_OVERRIDES[coin]
    if coin in NO_PERPETUAL:
        raise KeyError(coin)
    return str(spot_pair).replace("_USDT", "USDT").replace("_", "")


def _fetch_month(symbol: str, month: str, *, retries: int = 3) -> pd.DataFrame | None:
    """One month of funding rates, or None when the symbol has no file for it."""
    url = ARCHIVE_URL.format(symbol=symbol, month=month)
    last_error: Exception | None = None
    for attempt in range(retries):
        request = urllib.request.Request(url, headers={"User-Agent": "atlas20-research"})
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            last_error = exc
            time.sleep(1.0 + attempt)
            continue
        except Exception as exc:  # noqa: BLE001 - retry any transport failure
            last_error = exc
            time.sleep(1.0 + attempt)
            continue
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            name = archive.namelist()[0]
            frame = pd.read_csv(archive.open(name))
        # Older archives ship without a header row.
        if list(frame.columns) != FUNDING_COLUMNS:
            frame = pd.read_csv(io.BytesIO(payload), compression="zip", header=None, names=FUNDING_COLUMNS)
        return frame
    raise RuntimeError(f"{symbol} {month}: {last_error}")


def _download_coin(coin: str, symbol: str, months: list[str]) -> tuple[str, pd.DataFrame | None, list[str]]:
    frames: list[pd.DataFrame] = []
    missing: list[str] = []
    for month in months:
        frame = _fetch_month(symbol, month)
        if frame is None or frame.empty:
            missing.append(month)
            continue
        frames.append(frame)
    if not frames:
        return coin, None, missing
    combined = pd.concat(frames, ignore_index=True)
    combined["calc_time"] = pd.to_numeric(combined["calc_time"], errors="coerce")
    combined = combined.dropna(subset=["calc_time"]).drop_duplicates(subset=["calc_time"])
    combined = combined.sort_values("calc_time").reset_index(drop=True)
    return coin, combined, missing


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--coverage", type=Path, default=Path("data/raw/binance_1h/coverage.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/binance_funding"))
    parser.add_argument("--start-month", default="2020-09")
    parser.add_argument("--end-month", default=None, help="Defaults to the current month")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    configure_logging("INFO")

    coverage = json.loads(args.coverage.read_text(encoding="utf-8"))
    months = _months(args.start_month, args.end_month or str(pd.Timestamp.utcnow().to_period("M")))
    output_dir = ensure_dir(args.output_dir)

    targets: list[tuple[str, str]] = []
    skipped: dict[str, str] = {}
    for coin, info in sorted(coverage.items()):
        if coin in NO_PERPETUAL:
            skipped[coin] = "no Binance perpetual"
            continue
        if not info.get("available"):
            skipped[coin] = "no spot pair"
            continue
        targets.append((coin, _perp_symbol(coin, str(info.get("pair")))))
    LOGGER.info("funding download: %s coins x %s months", len(targets), len(months))

    manifest: dict[str, dict[str, object]] = {}
    failures: list[str] = []
    with futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        pending = {
            pool.submit(_download_coin, coin, symbol, months): (coin, symbol)
            for coin, symbol in targets
        }
        for done, future in enumerate(futures.as_completed(pending), start=1):
            coin, symbol = pending[future]
            try:
                _, frame, missing = future.result()
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning("%s (%s) failed: %s", coin, symbol, exc)
                failures.append(coin)
                continue
            if frame is None or frame.empty:
                skipped[coin] = "no funding archive"
                continue
            frame.to_csv(output_dir / f"{coin}.csv", index=False)
            first = pd.to_datetime(int(frame["calc_time"].iloc[0]), unit="ms", utc=True)
            last = pd.to_datetime(int(frame["calc_time"].iloc[-1]), unit="ms", utc=True)
            manifest[coin] = {
                "symbol": symbol,
                "rows": int(len(frame)),
                "first": first.isoformat(),
                "last": last.isoformat(),
                "missing_months": missing,
            }
            if done % 10 == 0:
                LOGGER.info("downloaded %s/%s", done, len(pending))

    for coin, reason in skipped.items():
        manifest[coin] = {"available": False, "reason": reason}
    (output_dir / "coverage.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    available = sum(1 for value in manifest.values() if value.get("rows"))
    LOGGER.info("funding download complete: %s coins with data, %s skipped, %s failed", available, len(skipped), len(failures))
    print(f"wrote {output_dir} ({available} coins with funding history)")


if __name__ == "__main__":
    main()
