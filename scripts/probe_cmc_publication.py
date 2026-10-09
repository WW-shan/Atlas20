"""Measure when CoinMarketCap has finished publishing a day's rows.

Why this exists
---------------
The frozen phase-momentum champion is filled about three hours after the
00:00 UTC close because the daily refresh is scheduled for 02:00 UTC. The
literature review (``docs/research/literature_review_2026-09.md``, section 4,
H1) records a compliant operational alternative: keep the signal at the close
and shorten the data pipeline so the fill lands about one hour after it. That
lever is worth real money with no rule change and no new trial - the existing
hourly-fill backtest (``reports/phase_momentum_execution_lag_2022/fill_timing.csv``)
gives 21.22x at 20 bps with a +1h fill against 19.56x at +3h.

Whether +1h is achievable depends on one provider fact this repository does not
yet measure: when CoinMarketCap has finished writing day D-1's rows. CMC
publishes asset by asset after 00:00 UTC, so the panel's >=90% coverage gate
(``data_quality.min_daily_coverage``) cannot append the day until enough assets
have landed. This script measures that curve.

It is a measurement tool. It never writes ``data/processed/panel_daily.csv``,
never changes the strategy, and adds no trial. Run it from cron every 10-15
minutes from about 00:05 UTC to 03:00 UTC for a week; the earliest time at which
>=90% of a fixed sample carries the target date, across days, sets the refresh
time (see ``docs/operations/execution_latency.md``).

Its CMC fetches are cached **outside** the production raw cache
(``data/raw/cmc_publication_probe`` by default). Writing them into
``data/raw/coinmarketcap/history`` used to poison the shared cache: the probe
advances the probed coins to the newest CMC print, but it does not refresh the
Binance/Gate venue windows, so the next ``build_processed_datasets`` run finds
CMC one day ahead of every venue and excludes the affected assets as
unverified. Those are exactly the largest coins, so the panel silently lost its
top of book. ``--cache-dir`` exists to keep the two caches separate.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.config import (  # noqa: E402
    ResearchConfig,
    current_utc_day,
    latest_completed_utc_day,
    load_config,
)
from atlas20.data.coinmarketcap import CoinMarketCapClient  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402

CANDIDATE_ASSETS_FILE = "candidate_assets.json"
DEFAULT_OUTPUT = "reports/provider_publication/cmc_publication_probe.csv"
# Deliberately not the production ``data/raw`` cache: see the module docstring.
DEFAULT_CACHE_DIR = "data/raw/cmc_publication_probe"


def select_sample_ids(candidates: list[dict], sample_size: int) -> list[int]:
    """The ``sample_size`` largest cached candidates by market cap.

    Deterministic on purpose: ties break on the CMC id, so every probe measures
    the same basket and the coverage series stays comparable across runs. A
    candidate without a ``cmc_id`` cannot be ranked by CMC and is skipped.
    """
    if sample_size < 1:
        raise ValueError("sample_size must be at least 1")
    rows = [
        candidate
        for candidate in candidates
        if isinstance(candidate, dict) and candidate.get("cmc_id") is not None
    ]
    rows.sort(key=lambda candidate: (-float(candidate.get("market_cap") or 0.0), int(candidate["cmc_id"])))
    ids: list[int] = []
    seen: set[int] = set()
    for candidate in rows:
        coin_id = int(candidate["cmc_id"])
        if coin_id in seen:
            continue
        seen.add(coin_id)
        ids.append(coin_id)
        if len(ids) >= sample_size:
            break
    return ids


def _last_row_date(frame: pd.DataFrame | None) -> pd.Timestamp | None:
    """The newest date a history frame carries, as a naive UTC midnight."""
    if frame is None or frame.empty or "date" not in frame:
        return None
    last = pd.Timestamp(frame["date"].max())
    if last.tzinfo is not None:
        last = last.tz_convert("UTC").tz_localize(None)
    return last.normalize()


def coverage_of_target(
    histories: dict[int, pd.DataFrame],
    target: pd.Timestamp | str,
) -> tuple[int, int]:
    """``(assets whose newest row reaches target, assets probed)``."""
    target_ts = pd.Timestamp(target).normalize()
    reached = 0
    for frame in histories.values():
        last = _last_row_date(frame)
        if last is not None and last >= target_ts:
            reached += 1
    return reached, len(histories)


def resolve_probe_cache_dir(config: ResearchConfig, cache_dir: str | Path) -> Path:
    """The probe's isolated CMC cache directory, never the production one.

    The probe advances CMC history without refreshing the Binance/Gate venue
    windows. Sharing the production cache therefore leaves CMC one day ahead of
    every venue, and the next panel build excludes the probed assets - the
    largest coins - as unverified. Refuse that path instead of poisoning it.
    """
    raw_dir = config.resolve_path(config.paths.raw_dir)
    candidate = Path(cache_dir)
    if not candidate.is_absolute():
        candidate = config.resolve_path(candidate)
    if candidate.resolve() == raw_dir.resolve():
        raise ValueError(
            "the probe cache must not be the production raw cache; the probe would poison "
            "the shared CMC history and make the next panel build drop every probed asset"
        )
    return candidate


def load_candidates(config: ResearchConfig) -> list[dict]:
    path = config.resolve_path(config.paths.raw_dir) / "coingecko" / CANDIDATE_ASSETS_FILE
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} is not a candidate list")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--sample-size", type=int, default=20, help="assets probed per run")
    parser.add_argument("--lookback-days", type=int, default=3, help="days of tail requested per asset")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help="summary CSV, appended to")
    parser.add_argument(
        "--cache-dir",
        default=DEFAULT_CACHE_DIR,
        help="isolated CMC cache for the probe (never the production data/raw cache)",
    )
    parser.add_argument("--now", default=None, help="ISO timestamp; defaults to the wall clock")
    parser.add_argument(
        "--from-cache",
        action="store_true",
        help="read the cache instead of spending one CMC request per asset",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    configure_logging(config.logging.level)

    now = pd.Timestamp(args.now) if args.now else pd.Timestamp.now(tz="UTC")
    if now.tzinfo is None:
        now = now.tz_localize("UTC")
    now = now.tz_convert("UTC")
    target = latest_completed_utc_day(now)
    today = current_utc_day(now)

    sample = select_sample_ids(load_candidates(config), args.sample_size)
    if not sample:
        raise ValueError("no cached candidate carried a cmc_id")

    probe_raw_dir = resolve_probe_cache_dir(config, args.cache_dir)
    client = CoinMarketCapClient(config.providers.coinmarketcap, probe_raw_dir)
    start = (target - pd.Timedelta(days=args.lookback_days)).date()

    histories: dict[int, pd.DataFrame] = {}
    for coin_id in sample:
        if args.from_cache:
            histories[coin_id] = client.cached_history(coin_id)
        else:
            histories[coin_id] = client.fetch_history(
                coin_id, start=start, end=today.date(), force=True
            )

    reached, probed = coverage_of_target(histories, target)
    ratio = reached / probed if probed else float("nan")

    output = Path(args.output)
    ensure_dir(output.parent)
    row = {
        "probed_at_utc": now.isoformat(),
        "target_date": target.date().isoformat(),
        "sample_size": probed,
        "assets_with_target": reached,
        "coverage_ratio": round(ratio, 4),
        "source": "cache" if args.from_cache else "fetch",
    }
    frame = pd.DataFrame([row])
    frame.to_csv(output, mode="a", header=not output.exists(), index=False)
    print(frame.to_string(index=False))
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
