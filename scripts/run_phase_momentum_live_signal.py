"""Generate the latest target snapshot for the phase-momentum champion.

This is deliberately a signal-generation tool, not an order router.  It
reconstructs the point-in-time Top20 targets with the same production strategy
code used by the research report, then writes the most recent aggregate target
for the next T+1 execution window.
"""

# ruff: noqa: E402

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from atlas20.config import ResearchConfig  # noqa: E402
from atlas20.data.completeness import LastDayCompleteness, assess_last_day  # noqa: E402
from atlas20.logging_utils import configure_logging, ensure_dir  # noqa: E402
from atlas20.signals.risk import btc_above_moving_average  # noqa: E402
from atlas20.strategies.phase_momentum import (  # noqa: E402
    PhaseMomentumBuildResult,
    PhaseMomentumSpec,
    build_phase_momentum_targets,
)

from scripts.run_phase_momentum import _load_market, _production_result  # noqa: E402

# The frozen specification this tool emits signals for.  ``champion-defaults``
# is the pre-2026-10-08 single-book champion; ``PR2026-10-H3`` is the adopted
# Top20-breadth co-gate blend.  Override per run with ``--trial-id``.
FROZEN_TRIAL_ID = "PR2026-10-H3"


def _utc_now(now: datetime | None = None) -> datetime:
    """``now`` as an aware UTC datetime; a naive value is taken to be UTC."""
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now.astimezone(timezone.utc)


def _latest_completed_utc_day(now: datetime | None = None) -> date:
    """The newest daily close: the current UTC day is still in progress."""
    return _utc_now(now).date() - timedelta(days=1)


def _check_freshness(
    last_date: pd.Timestamp | date | str,
    *,
    max_staleness_days: int,
    now: datetime | None = None,
) -> None:
    """Refuse a snapshot whose evaluated range stops short of current data.

    The last evaluated date must be no older than the latest completed UTC
    day minus ``max_staleness_days``.  Dates are UTC calendar days, the same
    days the provider stamps its closes with, never the local calendar.
    """
    if max_staleness_days < 0:
        raise ValueError("max_staleness_days must be non-negative")
    last = pd.Timestamp(last_date)
    if pd.isna(last):
        raise ValueError("no evaluated date to check for freshness")
    latest_completed = _latest_completed_utc_day(now)
    oldest_allowed = latest_completed - timedelta(days=max_staleness_days)
    if last.date() < oldest_allowed:
        raise ValueError(
            f"stale market data: the evaluated range ends {last.date()}, but the "
            f"latest completed UTC day is {latest_completed} and "
            f"--max-staleness-days {max_staleness_days} requires {oldest_allowed} "
            "or later. Refresh the panel (or drop an old --end-date); pass "
            "--allow-stale only for a deliberate backfill."
        )


def _resolve_as_of(index: pd.DatetimeIndex, as_of: pd.Timestamp | str | None) -> pd.Timestamp:
    """Resolve ``as_of`` inside the evaluated range, never the whole panel.

    The panel can extend past ``--end-date``; the targets cannot.  Resolving
    against the panel would stamp the snapshot, and read the BTC gate, on a
    day the strategy was never evaluated for.
    """
    index = pd.DatetimeIndex(index)
    if index.empty:
        raise ValueError("evaluated index is empty")
    first = pd.Timestamp(index.min()).normalize()
    last = pd.Timestamp(index.max()).normalize()
    if as_of is None:
        return last
    requested = pd.Timestamp(as_of).normalize()
    if requested > last:
        raise ValueError(
            f"as-of {requested.date()} is after the evaluated range "
            f"{first.date()}..{last.date()}; extend --end-date instead"
        )
    eligible = index[index <= requested]
    if eligible.empty:
        raise ValueError(
            f"no evaluated date on or before {requested.date()} "
            f"(the evaluated range starts {first.date()})"
        )
    return pd.Timestamp(eligible[-1]).normalize()


def _book_labels(
    built: PhaseMomentumBuildResult,
    books: tuple[tuple[PhaseMomentumSpec, float], ...],
) -> list[int]:
    """Which book each sleeve belongs to, in build order.

    ``build_parameter_ensemble_targets`` appends sleeves book by book (spec by
    spec, then signal, then phase), so the first ``signals x phases`` sleeves
    are book 0 and so on.  ``build_phase_momentum_targets`` is the one-book
    case.  A synthetic build whose sleeve count does not match its spec falls
    back to equal contiguous blocks (display-only; the aggregate targets and
    engine book do not depend on this label).
    """
    n_books = len(books)
    n_sleeves = len(built.sleeve_targets)
    if n_books <= 1:
        return [0] * n_sleeves
    signal_count = len(_signal_names(built))
    expected = [signal_count * len(spec.phase_offsets) for spec, _ in books]
    if sum(expected) == n_sleeves:
        labels: list[int] = []
        for index, count in enumerate(expected):
            labels.extend([index] * count)
        return labels
    per_book = n_sleeves // n_books
    if per_book * n_books != n_sleeves:
        return [0] * n_sleeves
    return [index // per_book for index in range(n_sleeves)]


def _sleeve_snapshot(
    built: PhaseMomentumBuildResult,
    as_of: pd.Timestamp,
    books: tuple[tuple[PhaseMomentumSpec, float], ...],
) -> list[dict[str, object]]:
    labels = _book_labels(built, books)
    rows: list[dict[str, object]] = []
    for book, sleeve in zip(labels, built.sleeve_targets):
        history = sleeve.assets.loc[:as_of].dropna()
        if history.empty:
            continue
        target_date = pd.Timestamp(history.index[-1])
        asset = str(history.iloc[-1])
        weight = 0.0 if asset == "__cash__" else float(sleeve.weights.loc[target_date])
        rows.append(
            {
                "book": int(book),
                "signal_name": sleeve.signal_name,
                "phase_offset": int(sleeve.phase_offset),
                "asset": asset,
                "weight": weight,
                "target_date": target_date.date().isoformat(),
            }
        )
    return rows


def _signal_names(built: PhaseMomentumBuildResult) -> list[str]:
    """Signals the sleeves were actually built from, in build order."""
    return list(dict.fromkeys(str(sleeve.signal_name) for sleeve in built.sleeve_targets))


def _rule_text(spec: PhaseMomentumSpec, signal_names: list[str]) -> str:
    """Describe the rules from the spec that produced the targets."""
    parts = [
        "Strict point-in-time Top20",
        f"{len(signal_names)} trailing-return signals ({', '.join(signal_names)}) x "
        f"{len(spec.phase_offsets)} calendar phases of a {spec.rebalance_days}D rebalance cycle",
        f"hold while in Top{spec.hold_rank}",
    ]
    if spec.use_btc_gate:
        parts.append(f"BTC {spec.btc_ma_window}D MA + confirm{spec.btc_confirm_days}")
    else:
        parts.append("no BTC gate")
    if spec.use_volatility_target:
        parts.append(f"{spec.vol_window}D volatility target at {spec.target_volatility * 100:g}%")
    else:
        parts.append("no volatility target")
    if spec.stop_loss_kind != "none":
        parts.append(f"{spec.stop_loss_kind} stop at {spec.stop_loss_pct * 100:g}%")
    if spec.use_asset_trend_filter:
        parts.append(f"asset above its {spec.asset_ma_window}D MA")
    parts.extend(["long-only spot, no leverage", "T+1"])
    return "; ".join(parts)


def _book_summary(spec: PhaseMomentumSpec) -> str:
    """One book's rule knobs, for the multi-book rule text."""
    bits = [f"hold while in Top{spec.hold_rank}"]
    if spec.use_btc_gate:
        if spec.btc_ma_windows is not None:
            windows = "/".join(f"MA{window}" for window in spec.btc_ma_windows)
            bits.append(f"BTC gate ensemble {windows} + confirm{spec.btc_confirm_days}")
        else:
            bits.append(f"BTC {spec.btc_ma_window}D MA + confirm{spec.btc_confirm_days}")
    else:
        bits.append("no BTC gate")
    if spec.breadth_threshold is not None:
        bits.append(
            f"Top20 breadth >= {spec.breadth_threshold:.2f} above own "
            f"{spec.breadth_ma_window}D SMA"
        )
    if spec.holdings_per_sleeve > 1:
        bits.append(f"{spec.holdings_per_sleeve} coins per sleeve")
    if spec.use_volatility_target:
        bits.append(f"{spec.vol_window}D volatility target at {spec.target_volatility * 100:g}%")
    else:
        bits.append("no volatility target")
    if spec.stop_loss_kind != "none":
        bits.append(f"{spec.stop_loss_kind} stop at {spec.stop_loss_pct * 100:g}%")
    if spec.use_asset_trend_filter:
        bits.append(f"asset above its {spec.asset_ma_window}D MA")
    return ", ".join(bits)


def _multi_book_rule_text(
    books: tuple[tuple[PhaseMomentumSpec, float], ...],
    signal_names: list[str],
) -> str:
    """Describe a multi-book (registered ensemble) target build."""
    first = books[0][0]
    sleeve_count = sum(len(spec.phase_offsets) for spec, _ in books) * len(signal_names)
    weights = ", ".join(f"{weight:.2f}" for _, weight in books)
    parts = [
        "Strict point-in-time Top20",
        f"{sleeve_count} sleeves = {len(books)} books at [{weights}] x "
        f"{len(signal_names)} trailing-return signals ({', '.join(signal_names)}) x "
        f"{len(first.phase_offsets)} calendar phases of a {first.rebalance_days}D rebalance cycle",
    ]
    for index, (spec, _weight) in enumerate(books):
        parts.append(f"book {chr(ord('A') + index)}: {_book_summary(spec)}")
    parts.extend(["long-only spot, no leverage", "T+1"])
    return "; ".join(parts)


def _target_spec(
    books: tuple[tuple[PhaseMomentumSpec, float], ...],
) -> dict[str, object]:
    """The spec(s) behind the targets: one spec, or the registered book mix."""
    if len(books) == 1:
        spec = books[0][0]
        return {**asdict(spec), "phase_offsets": list(spec.phase_offsets)}
    return {
        "construction": "build_parameter_ensemble_targets (equal book weights)",
        "books": [
            {
                "weight": float(weight),
                "spec": {**asdict(spec), "phase_offsets": list(spec.phase_offsets)},
            }
            for spec, weight in books
        ],
    }


def _current_weights(engine_weights: pd.DataFrame, as_of: pd.Timestamp) -> pd.Series:
    """The book the engine holds at ``as_of``'s close, before trading its target.

    ``BacktestResult.weights`` are end-of-day weights after that day's drift.
    A target dated ``as_of`` is applied from the next day on, so this row is
    the pre-trade book on a trade day and the drifted book on any other day.
    """
    if as_of not in engine_weights.index:
        raise ValueError(f"engine weights do not cover {as_of.date()}")
    book = pd.to_numeric(engine_weights.loc[as_of], errors="coerce")
    return book[book > 0.0].sort_values(ascending=False)


def _last_day_line(check: object) -> str:
    if not isinstance(check, dict):
        return "- Last day complete: not checked (backfill)"
    reasons = check.get("reasons") or []
    suffix = f" ({'; '.join(str(reason) for reason in reasons)})" if reasons else ""
    return f"- Last day complete: {check.get('complete')}{suffix}"


def _assess_last_day(config: ResearchConfig, end: pd.Timestamp) -> LastDayCompleteness:
    """Is the last evaluated panel day a finished provider day?

    CMC finalizes a day asset by asset after 00:00 UTC. A day every asset has
    but only partially (volumes at 30-50%) passes the processor's coverage
    gate and can move the Top 20 through the liquidity filter, so the signal
    must not trade on it (see atlas20.data.completeness).
    """
    panel_path = config.resolve_path(config.paths.processed_dir) / "panel_daily.csv"
    panel = pd.read_csv(panel_path, usecols=["date", "coin_id", "volume_usd", "market_cap"])
    panel = panel[pd.to_datetime(panel["date"]) <= pd.Timestamp(end)]
    return assess_last_day(panel)


def _check_last_day(verdict: LastDayCompleteness) -> None:
    if verdict.complete:
        return
    day = verdict.date.date() if verdict.date is not None else "unknown"
    raise ValueError(
        f"the last panel day {day} looks partial: {'; '.join(verdict.reasons)}. Rerun after the "
        "provider has finalized it, or pass --allow-partial-day to trade on it deliberately."
    )


def _last_day_payload(verdict: LastDayCompleteness | None) -> dict[str, object] | None:
    if verdict is None:
        return None
    return {
        "date": verdict.date.date().isoformat() if verdict.date is not None else None,
        "complete": bool(verdict.complete),
        "median_volume_ratio": float(verdict.median_volume_ratio),
        "market_cap_coverage": float(verdict.market_cap_coverage),
        "volume_floor": float(verdict.volume_floor),
        "reasons": list(verdict.reasons),
    }


def _latest_signal_payload(
    market,
    built: PhaseMomentumBuildResult,
    spec: PhaseMomentumSpec,
    index: pd.DatetimeIndex,
    *,
    engine_weights: pd.DataFrame,
    cost_bps: float,
    as_of: pd.Timestamp | str | None = None,
    books: tuple[tuple[PhaseMomentumSpec, float], ...] | None = None,
    trial_id: str = "champion-defaults",
) -> dict[str, object]:
    """Latest target snapshot for the evaluated ``index`` (the backtest range).

    ``phase_offset`` labels count days from ``index[0]``, so the payload
    records the evaluated range next to the panel's own last date.
    ``engine_weights`` is the production engine's ``BacktestResult.weights``
    for the same build, run at ``cost_bps``.  ``books`` is the registered
    book mix behind the build (one book for the champion, two for H3); ``spec``
    is the first book's spec and drives the BTC gate reading.
    """
    books = books if books is not None else ((spec, 1.0),)
    resolved_as_of = _resolve_as_of(index, as_of)
    eligible_dates = sorted(
        pd.Timestamp(target_date)
        for target_date in built.targets
        if pd.Timestamp(target_date) <= resolved_as_of
    )
    if not eligible_dates:
        raise ValueError(f"strategy produced no targets on or before {resolved_as_of.date()}")
    target_date = eligible_dates[-1]
    target = built.targets[target_date]
    positive = target[target > 0.0].sort_values(ascending=False)
    current = _current_weights(engine_weights, resolved_as_of)
    signal_names = _signal_names(built)
    gate = btc_above_moving_average(
        market.price,
        ma_window=spec.btc_ma_window,
        confirm_days=spec.btc_confirm_days,
    )
    rule = (
        _rule_text(spec, signal_names)
        if len(books) == 1
        else _multi_book_rule_text(books, signal_names)
    )
    return {
        "as_of": resolved_as_of.date().isoformat(),
        "start_date": pd.Timestamp(index.min()).date().isoformat(),
        "end_date": pd.Timestamp(index.max()).date().isoformat(),
        "panel_last_date": pd.Timestamp(market.price.index.max()).date().isoformat(),
        "latest_target_date": target_date.date().isoformat(),
        # A target dated before as_of has already been traded; only a target
        # generated at as_of's close still has to be executed.
        "trade_required": bool(target_date == resolved_as_of),
        "btc_gate_open": bool(gate.get(resolved_as_of, False)),
        "targets": {str(asset): float(weight) for asset, weight in positive.items()},
        "gross_exposure": float(positive.sum()),
        "current_weights": {str(asset): float(weight) for asset, weight in current.items()},
        "current_gross_exposure": float(current.sum()),
        "cost_bps": float(cost_bps),
        "next_check_date": (resolved_as_of + pd.Timedelta(days=1)).date().isoformat(),
        "trial_id": trial_id,
        "rule": rule,
        "signal_names": signal_names,
        "target_spec": _target_spec(books),
        "sleeves": _sleeve_snapshot(built, resolved_as_of, books),
    }


def _weight_lines(weights: object) -> list[str]:
    assert isinstance(weights, dict)
    lines = ["| Asset | Weight |", "| --- | ---: |"]
    if weights:
        for asset, weight in weights.items():
            lines.append(f"| {asset} | {float(weight):.6f} |")
    else:
        lines.append("| _cash_ | 0.000000 |")
    return lines


def _write_markdown(path: Path, payload: dict[str, object]) -> None:
    sleeve_lines = [
        "| Book | Signal | Phase | Asset | Weight | Target date |",
        "| ---: | --- | ---: | --- | ---: | --- |",
    ]
    for sleeve in payload["sleeves"]:
        assert isinstance(sleeve, dict)
        sleeve_lines.append(
            "| {book} | {signal_name} | {phase_offset} | {asset} | {weight:.6f} | "
            "{target_date} |".format(
                book=sleeve["book"],
                signal_name=sleeve["signal_name"],
                phase_offset=sleeve["phase_offset"],
                asset=sleeve["asset"],
                weight=float(sleeve["weight"]),
                target_date=sleeve["target_date"],
            )
        )

    path.write_text(
        "\n".join(
            [
                "# Latest Phase-Momentum Signal",
                "",
                f"- As of: {payload['as_of']}",
                f"- Evaluated range: {payload['start_date']} .. {payload['end_date']} "
                f"(phase offsets count from {payload['start_date']})",
                f"- Panel last date: {payload['panel_last_date']}",
                f"- Trial: {payload['trial_id']}",
                f"- Latest target date: {payload['latest_target_date']}",
                f"- Trade required: {payload['trade_required']}",
                _last_day_line(payload.get("last_day_check")),
                f"- BTC gate open: {payload['btc_gate_open']}",
                f"- Gross exposure: {float(payload['gross_exposure']):.6f}",
                f"- Current gross exposure: {float(payload['current_gross_exposure']):.6f}",
                f"- Next check date: {payload['next_check_date']}",
                f"- Rule: {payload['rule']}",
                "",
                "## Aggregate Targets",
                "",
                "The target to trade toward. It is new only when trade required is True.",
                "",
                *_weight_lines(payload["targets"]),
                "",
                "## Current Book",
                "",
                "Production-engine weights at the as-of close, after drift and before",
                f"trading a target dated that day ({float(payload['cost_bps']):g} bps cost).",
                "",
                *_weight_lines(payload["current_weights"]),
                "",
                "## Current Sleeve Snapshot",
                "",
                *sleeve_lines,
                "",
                "This file is a signal snapshot only. It does not place orders.",
                "",
            ]
        ),
        encoding="utf-8",
    )


CHAMPION_TRIAL_ID = "champion-defaults"


def _resolve_build(
    market,
    universe: pd.DataFrame,
    index: pd.DatetimeIndex,
    trial_id: str | None,
) -> tuple[tuple[tuple[PhaseMomentumSpec, float], ...], PhaseMomentumSpec,
           PhaseMomentumBuildResult, str]:
    """Build the sleeve targets for the frozen spec or a registered trial.

    ``trial_id`` selects a pre-registered trial from
    ``scripts.run_phase_momentum_hypotheses`` (the runner refuses an
    unregistered or drifted spec).  ``None`` resolves to ``FROZEN_TRIAL_ID``;
    the sentinel ``champion-defaults`` builds the pre-switch single-book
    champion's ``PhaseMomentumSpec`` defaults directly.  Returns the book mix,
    the first book's spec (drives the BTC gate reading), the build, and the
    recorded trial id.
    """
    resolved = trial_id or FROZEN_TRIAL_ID
    if resolved == CHAMPION_TRIAL_ID:
        spec = PhaseMomentumSpec()
        built = build_phase_momentum_targets(market, universe, index, spec=spec)
        return ((spec, 1.0),), spec, built, CHAMPION_TRIAL_ID
    from scripts.run_phase_momentum_hypotheses import build_trial, trial_by_id

    trial = trial_by_id(resolved)
    built = build_trial(trial, market, universe, index)
    return trial.books, trial.books[0][0], built, resolved


def main(argv: list[str] | None = None, *, now: datetime | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument("--start-date", default="2022-01-01")
    parser.add_argument(
        "--end-date",
        default=None,
        help="last evaluated date (default: the latest completed UTC day)",
    )
    parser.add_argument("--as-of", default=None)
    parser.add_argument(
        "--trial-id",
        default=None,
        help=(
            "registered trial to build (default: the frozen spec, "
            f"{FROZEN_TRIAL_ID!r}). Pass 'champion-defaults' for the pre-switch "
            "single-book champion."
        ),
    )
    parser.add_argument(
        "--cost-bps",
        type=float,
        default=20.0,
        help="all-in cost for the production-engine run behind current_weights",
    )
    parser.add_argument(
        "--max-staleness-days",
        type=int,
        default=1,
        help="refuse a range ending more than this many days before the latest completed UTC day",
    )
    parser.add_argument(
        "--allow-stale",
        action="store_true",
        help="skip the freshness guard (backfills and tests only)",
    )
    parser.add_argument(
        "--allow-partial-day",
        action="store_true",
        help="signal even when the last panel day looks unfinished (recorded in the output)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/phase_momentum_live"),
    )
    args = parser.parse_args(argv)
    if args.max_staleness_days < 0:
        parser.error("--max-staleness-days must be non-negative")
    now = _utc_now(now)
    end_date = args.end_date or _latest_completed_utc_day(now).isoformat()

    configure_logging("ERROR")
    config, market, universe, index = _load_market(
        args.config,
        start_date=args.start_date,
        end_date=end_date,
    )
    last_day: LastDayCompleteness | None = None
    if not args.allow_stale:
        _check_freshness(index.max(), max_staleness_days=args.max_staleness_days, now=now)
        # Live mode only: a backfill evaluates days that finished long ago.
        last_day = _assess_last_day(config, index.max())
        if not args.allow_partial_day:
            _check_last_day(last_day)
    books, spec, built, trial_id = _resolve_build(market, universe, index, args.trial_id)
    result = _production_result(config, market, built, index, cost_bps=args.cost_bps)
    payload = _latest_signal_payload(
        market,
        built,
        spec,
        index,
        engine_weights=result.weights,
        cost_bps=args.cost_bps,
        as_of=args.as_of,
        books=books,
        trial_id=trial_id,
    )
    payload["last_day_check"] = _last_day_payload(last_day)
    output_dir = ensure_dir(args.output_dir)
    (output_dir / "latest_signal.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    _write_markdown(output_dir / "latest_signal.md", payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(f"Wrote latest signal to {output_dir}")


if __name__ == "__main__":
    main()
