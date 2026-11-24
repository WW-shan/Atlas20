"""Fail-closed reliability audit for the derivatives live data chain.

The audit deliberately separates hard failures from warnings.  A hard failure
means the live executor must not plan or place an order: the panel is missing
its last completed day, a mark file is duplicated/future/invalid, a contract is
not online/perpetual at the profile's required leverage, or a required short
lacks fresh funding.
Historical or provider-window warnings remain visible without being silently
converted into zero-filled data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

UTC = timezone.utc
DEFAULT_EXECUTION_UTC = time(1, 5)
DEFAULT_FUNDING_STALE_HOURS = 12.0


def _normalise_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "<na>"} else text


@dataclass
class DataAuditReport:
    """One auditable data snapshot and its typed pass/fail evidence."""

    passed: bool
    checks: list[dict[str, Any]] = field(default_factory=list)
    hard_failures: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "checks": self.checks,
            "hard_failures": self.hard_failures,
            "warnings": self.warnings,
            "provenance": self.provenance,
            "summary": self.summary,
        }


def _as_utc(value: object) -> datetime:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        stamp = stamp.tz_localize("UTC")
    else:
        stamp = stamp.tz_convert("UTC")
    return stamp.to_pydatetime()


def required_last_mark_time(
    now: datetime | pd.Timestamp,
    *,
    execution_utc: time = DEFAULT_EXECUTION_UTC,
) -> pd.Timestamp:
    """Return the newest mark bar the live chain must have before trading."""

    moment = pd.Timestamp(_as_utc(now))
    last_completed = moment.date() - timedelta(days=1)
    # The signal is a completed-daily-bar strategy.  The 01:05 clock is the
    # execution time, not the signal-data boundary: a 00:00 hourly mark bar is
    # neither a return observation nor a fill input for the daily decision.
    # Requiring it would force the entire data/signal build into the execution
    # window.  Demand only the completed daily close (23:00 open of D-1, whose
    # covering close is D-1 23:59), while market candles separately prove the
    # 01:00 open fill anchor.
    del execution_utc
    return pd.Timestamp(last_completed, tz=UTC) + pd.Timedelta(hours=23)


def _file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_fingerprint(paths: Iterable[Path], *, root: Path | None = None) -> str | None:
    entries: list[tuple[str, str]] = []
    for path in sorted({Path(item) for item in paths if Path(item).is_file()}, key=str):
        name = str(path.relative_to(root)) if root is not None and path.is_relative_to(root) else str(path)
        digest = _file_sha256(path)
        if digest is not None:
            entries.append((name, digest))
    if not entries:
        return None
    payload = "\n".join(f"{name}\0{digest}" for name, digest in entries).encode()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _provenance_name(path: Path, raw: Path) -> str:
    """Return a path spelling that is stable across equivalent invocations.

    The finalize job passes an absolute raw directory while the executor uses
    the CLI's relative default.  Hashing the caller's spelling made the same
    bytes produce two identities and blocked live execution.  Prefer the
    raw-relative name, then a cwd-relative name, and only fall back to the
    resolved path for inputs outside both roots.
    """

    resolved = Path(path).expanduser().resolve()
    raw_resolved = Path(raw).expanduser().resolve()
    if resolved.is_relative_to(raw_resolved):
        return str(resolved.relative_to(raw_resolved))
    cwd = Path.cwd().resolve()
    if resolved.is_relative_to(cwd):
        return str(resolved.relative_to(cwd))
    return str(resolved)


def _funding_publication_data_identity(path: Path) -> str:
    """Stable identity of funding evidence, excluding observation timestamps.

    ``funding_publication.json`` is both proof and a query log.  A repeated
    audit may refresh request/observation times without changing the funding
    rows it proves.  Hashing those timestamps as market data made the
    manifest's ``data_fingerprint`` move on a read-only re-audit, blocking the
    executor immediately after a successful finalize.  Keep the funding-file
    byte hash and rate/settlement identity in provenance, but do not let the
    observation clock become data identity.
    """

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "unreadable"
    if not isinstance(payload, dict):
        return "not-object"
    assets = payload.get("assets")
    if not isinstance(assets, dict):
        return "missing-assets"
    stable_assets: dict[str, dict[str, object]] = {}
    for raw_asset, raw_entry in assets.items():
        if not isinstance(raw_entry, dict):
            stable_assets[str(raw_asset)] = {"invalid": True}
            continue
        stable_assets[str(raw_asset)] = {
            key: raw_entry.get(key)
            for key in (
                "symbol",
                "funding_sha256",
                "funding_last",
                "funding_rate",
                "history_last",
                "current_settlement_time",
                "current_funding_rate",
                "api_interval_hours",
                "contract_interval_hours",
                "interval_matches_contract",
                "history_rate_at_current_settlement",
                "rate_relation",
                "latest_source",
            )
        }
    encoded = json.dumps(stable_assets, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _check(
    report: DataAuditReport,
    name: str,
    passed: bool,
    detail: str,
    *,
    hard: bool = True,
) -> None:
    report.checks.append({"name": name, "passed": bool(passed), "detail": detail})
    if not passed:
        if hard:
            report.hard_failures.append(f"{name}: {detail}")
        else:
            report.warnings.append(f"{name}: {detail}")


def _read_panel(path: Path, report: DataAuditReport, now: datetime) -> pd.DataFrame | None:
    if not path.is_file():
        _check(report, "panel.exists", False, f"missing panel {path}")
        return None
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        _check(report, "panel.readable", False, str(exc))
        return None
    required = {"date", "coin_id", "symbol", "price", "volume_usd", "market_cap"}
    missing = sorted(required.difference(frame.columns))
    _check(report, "panel.columns", not missing, f"missing columns {missing}" if missing else "all required columns present")
    if missing:
        return None
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True, format="mixed", errors="coerce").dt.normalize()
    frame["coin_id"] = [_normalise_text(value) for value in frame["coin_id"]]
    frame["symbol"] = [_normalise_text(value).upper() for value in frame["symbol"]]
    invalid_coin_id = frame["coin_id"].eq("")
    invalid_symbol = frame["symbol"].eq("")
    _check(
        report,
        "panel.valid_coin_ids",
        not invalid_coin_id.any(),
        f"{int(invalid_coin_id.sum())} missing/non-finite coin id row(s)",
    )
    _check(
        report,
        "panel.valid_symbols",
        not invalid_symbol.any(),
        f"{int(invalid_symbol.sum())} missing/non-finite symbol row(s)",
    )
    for column in ("price", "volume_usd", "market_cap"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    invalid_date = frame["date"].isna()
    _check(report, "panel.valid_dates", not invalid_date.any(), f"{int(invalid_date.sum())} invalid date row(s)")
    frame = frame.loc[~invalid_date]
    duplicate = frame.duplicated(["date", "coin_id"], keep=False)
    _check(report, "panel.unique_date_asset", not duplicate.any(), f"{int(duplicate.sum())} duplicate (date, coin_id) row(s)")
    if not frame.empty:
        future = frame["date"] > pd.Timestamp(now).normalize()
        _check(report, "panel.no_future_dates", not future.any(), f"{int(future.sum())} future row(s)")
        invalid_price = ~np.isfinite(frame["price"].to_numpy(dtype=float)) | (frame["price"] <= 0.0)
        invalid_volume = ~np.isfinite(frame["volume_usd"].to_numpy(dtype=float)) | (frame["volume_usd"] < 0.0)
        invalid_cap = ~np.isfinite(frame["market_cap"].to_numpy(dtype=float)) | (frame["market_cap"] <= 0.0)
        latest = frame["date"].max()
        latest_rows = frame.loc[frame["date"] == latest]
        latest_cap = pd.to_numeric(latest_rows["market_cap"], errors="coerce").to_numpy(dtype=float)
        latest_cap_bad = ~np.isfinite(latest_cap) | (latest_cap <= 0.0)
        historical_invalid_cap = invalid_cap & ~frame["date"].eq(latest).to_numpy()
        valid_cap_coins = set(frame.loc[~invalid_cap, "coin_id"])
        historical_invalid_coins = set(frame.loc[historical_invalid_cap, "coin_id"])
        unbacked_cap_coins = historical_invalid_coins.difference(valid_cap_coins)
        _check(report, "panel.valid_price", not invalid_price.any(), f"{int(invalid_price.sum())} non-positive/non-finite price row(s)", hard=False)
        _check(report, "panel.valid_volume", not invalid_volume.any(), f"{int(invalid_volume.sum())} negative/non-finite volume row(s)", hard=False)
        market_cap_ok = not latest_cap_bad.any() and not unbacked_cap_coins
        if latest_cap_bad.any():
            market_cap_detail = f"{int(latest_cap_bad.sum())} invalid latest market-cap row(s)"
        elif invalid_cap.any():
            market_cap_detail = (
                f"{int(invalid_cap.sum())} historical market-cap row(s) are unrankable; "
                "all latest rows and affected assets retain a real positive cap"
            )
        else:
            market_cap_detail = "all market-cap rows are positive and finite"
        _check(report, "panel.valid_market_cap", market_cap_ok, market_cap_detail, hard=False)
        latest_price = pd.to_numeric(latest_rows["price"], errors="coerce").to_numpy(dtype=float)
        latest_volume = pd.to_numeric(latest_rows["volume_usd"], errors="coerce").to_numpy(dtype=float)
        latest_price_bad = ~np.isfinite(latest_price) | (latest_price <= 0.0)
        latest_volume_bad = ~np.isfinite(latest_volume) | (latest_volume < 0.0)
        _check(report, "panel.latest_price", not latest_price_bad.any(), f"{int(latest_price_bad.sum())} non-positive/non-finite latest price row(s)")
        _check(report, "panel.latest_volume", not latest_volume_bad.any(), f"{int(latest_volume_bad.sum())} negative/non-finite latest volume row(s)")
        _check(report, "panel.latest_market_cap", not latest_cap_bad.any(), f"{int(latest_cap_bad.sum())} non-positive/non-finite latest market-cap row(s)")
    return frame


def _read_symbol_map(path: Path, report: DataAuditReport) -> pd.DataFrame | None:
    if not path.is_file():
        _check(report, "symbol_map.exists", False, f"missing symbol map {path}")
        return None
    try:
        frame = pd.read_csv(path)
    except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
        _check(report, "symbol_map.readable", False, str(exc))
        return None
    required = {
        "coin_id",
        "panel_symbol",
        "bitget_symbol",
        "base_coin",
        "contract_status",
        "reason",
        "fund_interval",
        "min_trade_usdt",
        "size_multiplier",
    }
    missing = sorted(required.difference(frame.columns))
    _check(report, "symbol_map.columns", not missing, f"missing columns {missing}" if missing else "all required columns present")
    if missing:
        return None
    frame = frame.copy()
    for column in (
        "coin_id",
        "panel_symbol",
        "bitget_symbol",
        "base_coin",
        "contract_status",
        "reason",
    ):
        frame[column] = (
            frame[column]
            .fillna("")
            .astype(str)
            .str.strip()
            .replace({"nan": "", "NaN": "", "NAN": "", "None": ""})
        )
    duplicate_coin = frame["coin_id"].duplicated(keep=False)
    _check(report, "symbol_map.unique_coin", not duplicate_coin.any(), f"{int(duplicate_coin.sum())} duplicate coin_id row(s)")
    normal = frame.loc[frame["contract_status"].astype(str).str.lower().eq("normal")].copy()
    missing_symbol = normal["bitget_symbol"].eq("")
    _check(report, "symbol_map.normal_symbol", not missing_symbol.any(), f"{int(missing_symbol.sum())} normal row(s) without Bitget symbol")
    missing_panel_symbol = normal["panel_symbol"].eq("")
    _check(
        report,
        "symbol_map.normal_panel_symbol",
        not missing_panel_symbol.any(),
        f"{int(missing_panel_symbol.sum())} normal row(s) without the source panel symbol",
    )
    missing_base = normal["base_coin"].eq("")
    _check(
        report,
        "symbol_map.normal_base_coin",
        not missing_base.any(),
        f"{int(missing_base.sum())} normal row(s) without a base coin",
    )
    unusable_with_symbol = frame.loc[
        ~frame["contract_status"].str.lower().eq("normal")
        & frame["bitget_symbol"].ne("")
    ]
    _check(
        report,
        "symbol_map.unusable_has_no_symbol",
        unusable_with_symbol.empty,
        (
            f"{len(unusable_with_symbol)} non-normal row(s) still carry a tradeable symbol"
            if not unusable_with_symbol.empty
            else "non-normal rows carry no venue symbol"
        ),
    )
    symbol_dupes = normal.loc[normal["bitget_symbol"].ne("") & normal["bitget_symbol"].duplicated(keep=False)]
    if not symbol_dupes.empty:
        alias_only = symbol_dupes.groupby("bitget_symbol", dropna=False).apply(
            lambda group: len(group) == 2
            and set(group["reason"].astype(str).str.lower()) >= {"direct"}
            and group["reason"].astype(str).str.lower().str.contains("alias").any()
        )
        ambiguous = [str(symbol) for symbol, allowed in alias_only.items() if not bool(allowed)]
        _check(report, "symbol_map.unambiguous_symbol", not ambiguous, f"ambiguous Bitget symbol(s): {ambiguous}" if ambiguous else "explicit alias/direct pairs only")
    for column in ("fund_interval", "min_trade_usdt", "size_multiplier"):
        numeric = pd.to_numeric(normal[column], errors="coerce")
        invalid = numeric.isna() | ~np.isfinite(numeric.to_numpy(dtype=float)) | (numeric <= 0.0)
        _check(report, f"symbol_map.valid_{column}", not invalid.any(), f"{int(invalid.sum())} invalid normal row(s)")
    return frame


def _check_panel_symbol_alignment(
    panel: pd.DataFrame,
    symbol_map: pd.DataFrame,
    report: DataAuditReport,
) -> None:
    """Prove the cached map was built from the current per-asset symbols."""

    latest = (
        panel.sort_values(["date", "coin_id"], kind="stable")
        .drop_duplicates("coin_id", keep="last")
        .set_index("coin_id")
    )
    latest_symbols = {
        str(coin_id): _normalise_text(value).upper()
        for coin_id, value in latest["symbol"].items()
    }
    mapped = symbol_map.drop_duplicates("coin_id", keep="last").set_index("coin_id", drop=False)
    missing = sorted(set(latest_symbols).difference(mapped.index.astype(str)))
    _check(
        report,
        "symbol_map.latest_panel_coverage",
        not missing,
        f"latest panel asset(s) absent from symbol map: {missing}" if missing else "all latest panel assets mapped",
    )

    drift: list[str] = []
    for coin_id, panel_symbol in latest_symbols.items():
        if coin_id not in mapped.index:
            continue
        row = mapped.loc[coin_id]
        mapped_symbol = str(row.get("panel_symbol") or "").strip().upper()
        if panel_symbol != mapped_symbol:
            drift.append(f"{coin_id}:{mapped_symbol or '<missing>'}->{panel_symbol or '<missing>'}")
    _check(
        report,
        "symbol_map.latest_panel_symbols",
        not drift,
        "panel symbol drift: " + ", ".join(sorted(drift)) if drift else "panel symbols current",
    )


def _read_contracts(path: Path, report: DataAuditReport) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        _check(report, "contracts.exists", False, f"missing contracts file {path}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _check(report, "contracts.readable", False, str(exc))
        return {}
    if not isinstance(payload, list):
        _check(report, "contracts.list", False, "contracts.json must contain a list")
        return {}
    rows = [item for item in payload if isinstance(item, dict)]
    _check(report, "contracts.list", bool(rows), f"{len(rows)} contract row(s)")
    symbols = [str(row.get("symbol") or "").upper() for row in rows if row.get("symbol")]
    duplicates = sorted(
        {symbol for symbol in symbols if symbols.count(symbol) > 1}
    )
    _check(
        report,
        "contracts.unique_symbol",
        not duplicates,
        f"duplicate contract symbol(s): {duplicates}" if duplicates else "symbols unique",
    )
    return {str(row.get("symbol") or "").upper(): row for row in rows if row.get("symbol")}


def _check_funding_publication(
    report: DataAuditReport,
    *,
    asset: str,
    funding_path: Path,
    entry: object,
    actual_last: pd.Timestamp,
    actual_rate: float,
    declared_interval: float,
    now: datetime,
) -> None:
    """Verify that this funding snapshot was observed after its last print."""

    if not isinstance(entry, dict):
        _check(
            report,
            f"funding.{asset}.publication_evidence",
            False,
            "required funding has no matching publication observation",
        )
        return

    expected_hash = _file_sha256(funding_path)
    observed_hash = str(entry.get("funding_sha256") or "")
    _check(
        report,
        f"funding.{asset}.publication_hash",
        bool(expected_hash) and observed_hash == expected_hash,
        "publication evidence is not bound to the current funding file bytes",
    )

    try:
        evidence_last = pd.Timestamp(entry.get("funding_last"))
    except (TypeError, ValueError):
        evidence_last = pd.NaT
    try:
        verified_at = pd.Timestamp(entry.get("verified_at"))
    except (TypeError, ValueError):
        verified_at = pd.NaT
    evidence_identity_ok = bool(
        not pd.isna(evidence_last)
        and _as_utc(evidence_last) == _as_utc(actual_last)
        and not pd.isna(verified_at)
    )
    _check(
        report,
        f"funding.{asset}.publication_evidence",
        evidence_identity_ok,
        (
            "publication evidence covers the current funding tail"
            if evidence_identity_ok
            else f"publication last={entry.get('funding_last')!r}, actual={actual_last}"
        ),
    )

    try:
        reported_lag = float(entry.get("publication_lag_seconds"))
    except (TypeError, ValueError):
        reported_lag = float("nan")
    actual_lag = (
        (_as_utc(verified_at) - _as_utc(actual_last)).total_seconds()
        if not pd.isna(verified_at)
        else float("nan")
    )
    time_ok = bool(
        not pd.isna(verified_at)
        and np.isfinite(actual_lag)
        and np.isfinite(reported_lag)
        and actual_lag >= 0.0
        and abs(actual_lag - reported_lag) <= 1.0
        and _as_utc(verified_at) <= _as_utc(now) + pd.Timedelta(minutes=5)
    )
    _check(
        report,
        f"funding.{asset}.publication_time",
        time_ok,
        (
            f"verified at {verified_at} after settlement {actual_last} "
            f"(lag {actual_lag:.0f}s)"
            if time_ok
            else f"verified_at={verified_at}, last={actual_last}, "
            f"reported_lag={reported_lag}, actual_lag={actual_lag}"
        ),
    )

    try:
        evidence_rate = float(entry.get("funding_rate"))
    except (TypeError, ValueError):
        evidence_rate = float("nan")
    relation = str(entry.get("rate_relation") or "").strip().lower()
    current_settlement: pd.Timestamp | pd.NaT
    try:
        current_settlement = pd.Timestamp(entry.get("current_settlement_time"))
    except (TypeError, ValueError):
        current_settlement = pd.NaT
    try:
        current_rate = float(entry.get("current_funding_rate"))
    except (TypeError, ValueError):
        current_rate = float("nan")
    current_rate_ok = True
    if (
        not pd.isna(current_settlement)
        and _as_utc(current_settlement) == _as_utc(actual_last)
        and np.isfinite(current_rate)
    ):
        current_rate_ok = bool(
            math.isclose(current_rate, actual_rate, rel_tol=1e-12, abs_tol=1e-12)
        )
    rate_ok = bool(
        np.isfinite(evidence_rate)
        and math.isclose(evidence_rate, actual_rate, rel_tol=1e-12, abs_tol=1e-12)
        and relation != "conflict"
        and current_rate_ok
    )
    _check(
        report,
        f"funding.{asset}.publication_rate",
        rate_ok,
        (
            f"rate {actual_rate:.12g} matches history/current evidence ({relation})"
            if rate_ok
            else f"history rate={actual_rate:.12g}, evidence rate={evidence_rate:.12g}, "
            f"current rate={current_rate:.12g}, relation={relation or '<missing>'}"
        ),
    )

    try:
        api_interval = float(entry.get("api_interval_hours"))
    except (TypeError, ValueError):
        api_interval = float("nan")
    interval_ok = bool(
        np.isfinite(declared_interval)
        and np.isfinite(api_interval)
        and math.isclose(api_interval, declared_interval, abs_tol=1e-9)
        and entry.get("interval_matches_contract") is True
    )
    _check(
        report,
        f"funding.{asset}.publication_interval",
        interval_ok,
        (
            f"venue current-fund-rate interval {api_interval:g}h matches contract {declared_interval:g}h"
            if interval_ok
            else f"venue interval={api_interval}, contract interval={declared_interval}, "
            f"flag={entry.get('interval_matches_contract')!r}"
        ),
    )


def _read_funding(
    raw_dir: Path,
    symbol_map: pd.DataFrame,
    report: DataAuditReport,
    *,
    required_short_assets: set[str],
    required_assets: set[str] | None,
    require_all_fresh: bool,
    stale_hours: float,
    now: datetime,
    publication_now: datetime,
    historical: bool = False,
) -> dict[str, dict[str, Any]]:
    manifest_path = raw_dir / "funding_manifest.json"
    manifest_payload: object = None
    if manifest_path.is_file():
        try:
            manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            _check(
                report,
                "funding.manifest_object",
                isinstance(manifest_payload, dict),
                "funding manifest must be a JSON object",
            )
        except (OSError, json.JSONDecodeError) as exc:
            _check(report, "funding.manifest_readable", False, str(exc))
    else:
        _check(report, "funding.manifest_exists", False, f"missing {manifest_path}")
    publication_path = raw_dir / "funding_publication.json"
    publication_assets: dict[str, Any] = {}
    if publication_path.is_file():
        try:
            publication_payload = json.loads(
                publication_path.read_text(encoding="utf-8")
            )
            if isinstance(publication_payload, dict) and isinstance(
                publication_payload.get("assets"), dict
            ):
                publication_assets = publication_payload["assets"]
        except (OSError, json.JSONDecodeError):
            publication_assets = {}
    normal = symbol_map.loc[symbol_map["contract_status"].astype(str).str.lower().eq("normal")]
    required_funding_assets = {
        str(asset).strip().lower()
        for asset in (required_assets if required_assets is not None else required_short_assets)
    }
    if require_all_fresh:
        required_funding_assets = {
            str(asset).strip().lower() for asset in normal["coin_id"].astype(str)
        }
    summary: dict[str, dict[str, Any]] = {}
    for row in normal.to_dict("records"):
        asset = str(row["coin_id"])
        path = raw_dir / "funding" / f"{asset}.csv"
        if not path.is_file():
            _check(report, f"funding.{asset}.exists", False, f"missing {path}")
            continue
        try:
            frame = pd.read_csv(path)
        except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
            _check(report, f"funding.{asset}.readable", False, str(exc))
            continue
        if not {"funding_time", "funding_rate"}.issubset(frame.columns):
            _check(report, f"funding.{asset}.columns", False, "missing funding_time/funding_rate")
            continue
        if "symbol" not in frame.columns:
            _check(
                report,
                f"funding.{asset}.symbol",
                False,
                "funding file has no symbol column; venue identity is unproven",
                hard=asset.lower() in required_funding_assets,
            )
        else:
            expected_symbol = str(row.get("bitget_symbol") or "").strip().upper()
            observed_symbols = {
                str(value).strip().upper()
                for value in frame["symbol"].dropna().unique()
                if str(value).strip()
            }
            _check(
                report,
                f"funding.{asset}.symbol",
                bool(expected_symbol)
                and observed_symbols == {expected_symbol},
                (
                    f"symbol mismatch: file={sorted(observed_symbols)} "
                    f"map={expected_symbol or '<missing>'}"
                ),
            )
        stamps = pd.to_datetime(frame["funding_time"], utc=True, format="mixed", errors="coerce")
        rates = pd.to_numeric(frame["funding_rate"], errors="coerce")
        valid = stamps.notna() & rates.notna() & np.isfinite(rates.to_numpy(dtype=float))
        _check(report, f"funding.{asset}.valid_rows", bool(valid.all()), f"{int((~valid).sum())} invalid row(s)")
        valid_stamps = stamps.loc[valid].reset_index(drop=True)
        _check(
            report,
            f"funding.{asset}.monotonic",
            bool(valid_stamps.is_monotonic_increasing),
            "funding_time is not monotonic",
        )
        clean = pd.DataFrame({"funding_time": stamps[valid], "funding_rate": rates[valid]}).sort_values("funding_time")
        _check(report, f"funding.{asset}.unique_time", not clean["funding_time"].duplicated().any(), f"{int(clean['funding_time'].duplicated().sum())} duplicate timestamp(s)")
        if not clean.empty:
            max_abs_rate = float(clean["funding_rate"].abs().max())
            _check(
                report,
                f"funding.{asset}.rate_sanity",
                np.isfinite(max_abs_rate) and max_abs_rate <= 0.10,
                f"max |funding_rate|={max_abs_rate:.6g} exceeds 10% per settlement",
            )
        last = clean["funding_time"].max() if not clean.empty else pd.NaT
        _check(
            report,
            f"funding.{asset}.no_future",
            # A historical replay audits against its frozen boundary, while
            # the cumulative funding cache legitimately contains later rows.
            # Treat those rows as archived history in that mode; a live audit
            # still rejects a timestamp materially ahead of its own clock.
            bool(
                pd.isna(last)
                or _as_utc(last) <= _as_utc(now) + pd.Timedelta(hours=1)
                # Archived replay uses a cumulative file: rows after the
                # frozen day are later history, not an impossible print.
                # Wall-clock future detection remains active for live audits.
                or historical
            ),
            f"latest funding timestamp {last} is materially in the future",
        )
        if isinstance(manifest_payload, dict):
            entry = manifest_payload.get(asset)
            manifest_last = entry.get("last") if isinstance(entry, dict) else None
            try:
                manifest_last_ts = pd.Timestamp(manifest_last) if manifest_last else pd.NaT
            except (TypeError, ValueError):
                manifest_last_ts = pd.NaT
            _check(
                report,
                f"funding.{asset}.manifest_matches",
                (pd.isna(last) and pd.isna(manifest_last_ts))
                or (not pd.isna(last) and not pd.isna(manifest_last_ts) and _as_utc(last) == _as_utc(manifest_last_ts)),
                f"manifest last={manifest_last!r} actual last={last}",
            )
        interval = float(pd.to_numeric(row.get("fund_interval"), errors="coerce")) if pd.notna(row.get("fund_interval")) else float("nan")
        if asset.lower() in required_funding_assets:
            actual_rate = (
                float(clean.sort_values("funding_time")["funding_rate"].iloc[-1])
                if not clean.empty
                else float("nan")
            )
            _check_funding_publication(
                report,
                asset=asset,
                funding_path=path,
                entry=publication_assets.get(asset),
                actual_last=pd.Timestamp(last) if not pd.isna(last) else pd.NaT,
                actual_rate=actual_rate,
                declared_interval=interval,
                now=publication_now,
            )
        observed_interval: float | None = None
        interval_history_matches = False
        if np.isfinite(interval) and interval > 0.0 and len(clean) >= 2:
            # The contract snapshot only proves the *current* interval.  The
            # funding timestamps are the authoritative historical cadence:
            # every adjacent gap must equal the declared interval.  Requiring
            # an exact cadence catches both directions of an interval change
            # (8h->4h and 4h->8h) and a missing settlement, instead of treating
            # the current contract value as if it had always applied.
            all_gaps = (
                clean["funding_time"].diff().dropna().dt.total_seconds().div(3600.0)
            )
            off_grid = [
                float(gap)
                for gap in all_gaps
                if abs(float(gap) / interval - round(float(gap) / interval)) > 1e-9
            ]
            _check(
                report,
                f"funding.{asset}.observed_gap_grid",
                not off_grid,
                (
                    f"observed gap(s) {off_grid[:5]} are not multiples of declared "
                    f"{interval:g}h; interval may have changed"
                    if off_grid
                    else f"all {len(all_gaps)} observed gaps are multiples of {interval:g}h"
                ),
            )
            gap_minutes = [
                int(round(float(gap) * 60.0))
                for gap in all_gaps
                if np.isfinite(float(gap)) and float(gap) > 0.0
            ]
            positive_gaps = [
                float(gap)
                for gap in all_gaps
                if np.isfinite(float(gap)) and float(gap) > 0.0
            ]
            if gap_minutes:
                observed_minutes = 0
                for minutes in gap_minutes:
                    observed_minutes = math.gcd(observed_minutes, abs(minutes))
                if observed_minutes > 0:
                    observed_interval = observed_minutes / 60.0
            off_cadence = [
                gap for gap in positive_gaps if not math.isclose(gap, interval, abs_tol=0.25)
            ]
            interval_history_matches = bool(
                observed_interval is not None
                and math.isclose(observed_interval, interval, abs_tol=0.01)
                and not off_cadence
            )
            _check(
                report,
                f"funding.{asset}.interval_history",
                interval_history_matches,
                (
                    f"observed cadence {observed_interval if observed_interval is not None else 'unknown'}h "
                    f"does not match declared {interval:g}h; "
                    f"{len(off_cadence)} gap(s) differ, e.g. {off_cadence[:5]}"
                    if not interval_history_matches
                    else f"all {len(positive_gaps)} gaps match the declared {interval:g}h cadence"
                ),
            )
            recent_cutoff = pd.Timestamp(_as_utc(now)) - pd.Timedelta(days=30)
            recent_times = clean.loc[
                clean["funding_time"] >= recent_cutoff, "funding_time"
            ].sort_values()
            if len(recent_times) >= 2:
                recent_gaps = (
                    recent_times.diff().dropna().dt.total_seconds().div(3600.0)
                )
                largest_gap = float(recent_gaps.max())
                _check(
                    report,
                    f"funding.{asset}.recent_gap",
                    largest_gap <= interval + 0.01,
                    f"funding gap {largest_gap:.2f}h exceeds interval {interval:.2f}h",
                )

            # A last-row freshness check alone cannot prove that every
            # settlement was present: an old tail can look "fresh enough" for a
            # slow interval while a settlement inside the live window is
            # missing.  Build the expected schedule from the first observed
            # leg through the last settlement that should already be published
            # and prove every timestamp exists.  This is applied to the legs
            # that can actually be held, not to the whole watchlist.
            if asset.lower() in required_funding_assets and not clean.empty:
                first = pd.Timestamp(clean["funding_time"].min())
                # Allow one hour for provider publication after the nominal
                # settlement minute.  A live caller must not accept a stale
                # 00:00 print at 01:05 merely because it is less than 12h old.
                cutoff = _as_utc(now) - pd.Timedelta(hours=1.0)
                if cutoff >= first:
                    elapsed_hours = (cutoff - first).total_seconds() / 3600.0
                    periods = int(np.floor(elapsed_hours / interval + 1e-9))
                    if periods >= 0:
                        expected_last = first + pd.Timedelta(
                            hours=float(periods) * interval
                        )
                        expected = pd.date_range(
                            start=first,
                            end=expected_last,
                            freq=pd.Timedelta(hours=interval),
                        )
                        observed = set(pd.DatetimeIndex(clean["funding_time"]))
                        missing = [
                            stamp for stamp in expected if pd.Timestamp(stamp) not in observed
                        ]
                        _check(
                            report,
                            f"funding.{asset}.settlement_coverage",
                            not missing,
                            (
                                f"missing {len(missing)} expected settlement(s) through "
                                f"{expected_last}, e.g. {missing[:3]}"
                                if missing
                                else f"all {len(expected)} expected settlements present through {expected_last}"
                            ),
                        )
        # Freshness is a same-snapshot property, not a wall-clock-only
        # property.  A panel and funding tree fetched just before the next
        # settlement are internally consistent; the execution gate separately
        # proves that the snapshot was captured recently enough for this run.
        # Otherwise every 01:05 run with a 00:00 settlement would fail the
        # freshness bound while settlement coverage correctly demands the row.
        stale = False
        if pd.isna(last):
            stale = True
        else:
            age = (_as_utc(now) - _as_utc(last)).total_seconds() / 3600.0
            stale = age > max(
                stale_hours, interval if np.isfinite(interval) else 0.0
            )
        if asset.lower() in required_funding_assets:
            # The required-leg settlement schedule above is the hard proof.
            # An informational freshness warning can diagnose an old cache,
            # but must not duplicate or contradict a complete settlement
            # calendar at the current execution instant.
            _check(
                report,
                f"funding.{asset}.fresh",
                not stale,
                (
                    "funding is stale for the live short sleeve"
                    if stale and require_all_fresh
                    else "funding is stale for a required live leg"
                    if stale
                    else "fresh"
                ),
                hard=False,
            )
        elif asset.lower() in required_short_assets:
            _check(report, f"funding.{asset}.fresh_for_short", not stale, "funding is stale for a required short" if stale else "fresh for required short", hard=False)
        elif stale:
            _check(report, f"funding.{asset}.fresh", False, "funding is stale but no short is required", hard=False)
        publication_entry = publication_assets.get(asset)
        summary[asset] = {
            "last": None if pd.isna(last) else str(last),
            "rows": int(len(clean)),
            "stale": bool(stale),
            "observed_interval_hours": observed_interval,
            "interval_matches_contract": interval_history_matches,
            "publication": (
                {
                    key: publication_entry.get(key)
                    for key in (
                        "verified_at",
                        "publication_lag_seconds",
                        "latest_source",
                        "rate_relation",
                        "api_interval_hours",
                    )
                }
                if isinstance(publication_entry, dict)
                else None
            ),
        }
    report.summary["funding_assets"] = len(summary)
    return summary


def audit_derivatives_data(
    raw_dir: str | Path,
    panel_path: str | Path,
    symbol_map_path: str | Path | None = None,
    manifest_path: str | Path | None = None,
    *,
    now: datetime | None = None,
    required_through: datetime | None = None,
    expected_panel_day: date | None = None,
    historical_panel_day: date | None = None,
    min_panel_assets: int = 20,
    required_short_assets: Iterable[str] | None = None,
    required_leverage_assets: Iterable[str] | None = None,
    required_leverage: float = 2.0,
    required_funding_assets: Iterable[str] | None = None,
    require_all_funding_fresh: bool = False,
    execution_utc: time = DEFAULT_EXECUTION_UTC,
    funding_stale_hours: float = DEFAULT_FUNDING_STALE_HOURS,
    publication_now: datetime | None = None,
) -> DataAuditReport:
    """Audit one live derivatives data snapshot without changing any file."""

    raw = Path(raw_dir)
    panel_file = Path(panel_path)
    symbol_file = Path(symbol_map_path) if symbol_map_path is not None else raw / "symbol_map.csv"
    moment = _as_utc(now or datetime.now(UTC))
    required_moment = _as_utc(required_through) if required_through is not None else moment
    publication_moment = _as_utc(publication_now or datetime.now(UTC))
    if not np.isfinite(float(required_leverage)) or float(required_leverage) <= 0.0:
        raise ValueError("required_leverage must be positive and finite")
    required_short_set = {
        str(asset).strip().lower() for asset in (required_short_assets or ())
    }
    required_funding_set = (
        None
        if required_funding_assets is None
        else {
            str(asset).strip().lower()
            for asset in required_funding_assets
            if str(asset).strip()
        }
    )
    required_leverage_set = {
        str(asset).strip().lower()
        for asset in (
            required_short_set
            if required_leverage_assets is None
            else required_leverage_assets
        )
    }
    report = DataAuditReport(passed=False)
    report.summary["now"] = moment.isoformat()
    report.summary["publication_now"] = publication_moment.isoformat()
    report.summary["required_leverage"] = float(required_leverage)
    report.summary["required_leverage_assets"] = sorted(required_leverage_set)
    if historical_panel_day is not None and required_through is None:
        required_moment = datetime.combine(
            historical_panel_day + timedelta(days=1),
            time(0, 0),
            tzinfo=UTC,
        )
    report.summary["required_through"] = required_moment.isoformat()
    panel = _read_panel(panel_file, report, moment)
    symbol_map = _read_symbol_map(symbol_file, report)
    contracts = _read_contracts(raw / "contracts.json", report)
    if panel is not None and symbol_map is not None:
        _check_panel_symbol_alignment(panel, symbol_map, report)
    if panel is not None and not panel.empty:
        if expected_panel_day is not None and historical_panel_day is not None:
            raise ValueError(
                "expected_panel_day and historical_panel_day are mutually exclusive"
            )
        latest = panel["date"].max().date()
        if historical_panel_day is not None:
            # A historical replay only needs the requested completed day to be
            # present in the current, cumulative panel.  It must not reject a
            # newer panel: that would make every archived-date audit fail once
            # the daily refresh advances.  The live exact-day gate below stays
            # unchanged.
            audited_day = historical_panel_day
            present = bool(
                (panel["date"] == pd.Timestamp(audited_day, tz="UTC")).any()
            )
            _check(
                report,
                "panel.historical_day_present",
                present,
                f"panel does not contain historical day {audited_day}",
            )
        else:
            audited_day = (
                expected_panel_day
                if expected_panel_day is not None
                else moment.date() - timedelta(days=1)
            )
            _check(
                report,
                "panel.last_completed_day",
                latest == audited_day,
                f"panel does not reach the last completed UTC day {audited_day} (latest {latest})"
                if latest != audited_day
                else f"panel reaches {audited_day}",
            )
        audited = panel.loc[
            panel["date"] == pd.Timestamp(audited_day, tz="UTC")
        ]
        audited_assets = int(audited["coin_id"].nunique())
        _check(
            report,
            "panel.min_assets",
            audited_assets >= int(min_panel_assets),
            f"{audited_assets} asset(s) on {audited_day}, require {min_panel_assets}",
        )
        report.summary["panel_latest"] = str(latest)
        report.summary["panel_latest_assets"] = int(
            panel.loc[panel["date"] == pd.Timestamp(latest, tz="UTC"), "coin_id"].nunique()
        )
        report.summary["panel_audited_day"] = str(audited_day)
        report.summary["panel_audited_day_assets"] = audited_assets

    marks: dict[str, pd.DataFrame] = {}
    mark_paths: list[Path] = []
    if symbol_map is not None:
        normal = symbol_map.loc[symbol_map["contract_status"].astype(str).str.lower().eq("normal")]
        normal_assets = {
            str(asset).strip().lower() for asset in normal["coin_id"].astype(str)
        }
        missing_required_leverage = sorted(
            required_leverage_set.difference(normal_assets)
        )
        _check(
            report,
            "contracts.required_leverage_mappings",
            not missing_required_leverage,
            (
                "missing normal Bitget mapping for required leverage asset(s): "
                + ", ".join(missing_required_leverage)
                if missing_required_leverage
                else "all required leverage assets have a normal Bitget mapping"
            ),
        )
        for row in normal.to_dict("records"):
            asset = str(row["coin_id"])
            symbol = str(row["bitget_symbol"]).strip().upper()
            contract = contracts.get(symbol)
            _check(report, f"contracts.{asset}.exists", contract is not None, f"missing contract {symbol}")
            if contract is not None:
                status = str(contract.get("symbolStatus") or "").lower()
                kind = str(contract.get("symbolType") or "").lower()
                contract_symbol = str(contract.get("symbol") or "").strip().upper()
                contract_base = str(contract.get("baseCoin") or "").strip().upper()
                contract_quote = str(contract.get("quoteCoin") or "").strip().upper()
                mapped_base = str(row.get("base_coin") or "").strip().upper()
                _check(
                    report,
                    f"contracts.{asset}.base_coin",
                    bool(mapped_base) and contract_base == mapped_base,
                    f"base coin mismatch: contract baseCoin={contract_base or 'missing'} vs map base_coin={mapped_base or 'missing'}",
                )
                _check(
                    report,
                    f"contracts.{asset}.quote_coin",
                    contract_quote == "USDT",
                    f"quoteCoin={contract_quote or 'missing'}",
                )
                _check(
                    report,
                    f"contracts.{asset}.symbol_identity",
                    bool(contract_base and contract_quote)
                    and contract_symbol == f"{contract_base}{contract_quote}",
                    f"symbol={contract_symbol or 'missing'} vs baseCoin+quoteCoin={contract_base or '?'}+{contract_quote or '?'}",
                )
                try:
                    min_lever = float(contract.get("minLever"))
                    max_lever = float(contract.get("maxLever"))
                    min_qty = float(contract.get("minTradeNum"))
                    min_usdt = float(contract.get("minTradeUSDT"))
                    step = float(contract.get("sizeMultiplier"))
                    taker = float(contract.get("takerFeeRate"))
                    interval = float(contract.get("fundInterval"))
                except (TypeError, ValueError):
                    min_lever = max_lever = min_qty = min_usdt = step = taker = interval = float("nan")
                _check(report, f"contracts.{asset}.normal", status == "normal", f"status={status or 'missing'}")
                _check(report, f"contracts.{asset}.perpetual", kind == "perpetual", f"type={kind or 'missing'}")
                _check(report, f"contracts.{asset}.two_x", np.isfinite(min_lever) and np.isfinite(max_lever) and min_lever <= 2.0 <= max_lever, f"leverage range {min_lever:g}..{max_lever:g}" if np.isfinite(min_lever) and np.isfinite(max_lever) else "missing leverage")
                if str(asset).strip().lower() in required_leverage_set:
                    _check(
                        report,
                        f"contracts.{asset}.required_leverage",
                        np.isfinite(min_lever)
                        and np.isfinite(max_lever)
                        and min_lever <= float(required_leverage) <= max_lever,
                        (
                            f"leverage range {min_lever:g}..{max_lever:g}, "
                            f"require {float(required_leverage):g}"
                            if np.isfinite(min_lever) and np.isfinite(max_lever)
                            else "missing leverage"
                        ),
                    )
                _check(report, f"contracts.{asset}.steps", all(np.isfinite(v) and v > 0.0 for v in (min_qty, min_usdt, step, interval)), "min quantity/notional, size step and funding interval must be positive")
                _check(report, f"contracts.{asset}.taker_fee", np.isfinite(taker) and taker >= 0.0, f"taker fee={taker:g}" if np.isfinite(taker) else "missing taker fee")
                # The symbol map drives the offline engine's quantity rounding
                # and funding calendar.  If those fields drift from the venue
                # contract snapshot, a backtest can be quantized against one
                # exchange rule while the live executor uses another.
                for map_key, contract_key, contract_value in (
                    ("fund_interval", "fundInterval", interval),
                    ("min_trade_usdt", "minTradeUSDT", min_usdt),
                    ("size_multiplier", "sizeMultiplier", step),
                ):
                    try:
                        mapped_value = float(row.get(map_key))
                    except (TypeError, ValueError):
                        mapped_value = float("nan")
                    _check(
                        report,
                        f"contracts.{asset}.{map_key}_matches",
                        np.isfinite(mapped_value)
                        and np.isfinite(contract_value)
                        and abs(mapped_value - contract_value)
                        <= 1e-9 * max(1.0, abs(mapped_value), abs(contract_value)),
                        (
                            f"symbol_map {map_key}={mapped_value:g} vs "
                            f"contract {contract_key}={contract_value:g}"
                            if np.isfinite(mapped_value) and np.isfinite(contract_value)
                            else f"invalid {map_key}"
                        ),
                    )
            mark_path = raw / "candles" / f"{symbol}_mark.csv"
            mark_paths.append(mark_path)
            if not mark_path.is_file():
                _check(report, f"marks.{asset}.exists", False, f"missing {mark_path}")
                continue
            try:
                frame = pd.read_csv(mark_path)
            except (OSError, ValueError, pd.errors.ParserError, pd.errors.EmptyDataError) as exc:
                _check(report, f"marks.{asset}.readable", False, str(exc))
                continue
            missing = sorted(
                {
                    "open_time",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "quote_volume",
                }.difference(frame.columns)
            )
            _check(report, f"marks.{asset}.columns", not missing, f"missing columns {missing}" if missing else "required OHLCV columns present")
            if missing:
                continue
            stamps = pd.to_datetime(frame["open_time"], utc=True, format="mixed", errors="coerce")
            numeric = frame.loc[:, ["open", "high", "low", "close", "volume", "quote_volume"]].apply(pd.to_numeric, errors="coerce")
            valid = stamps.notna() & np.isfinite(
                numeric.to_numpy(dtype=float)
            ).all(axis=1)
            _check(report, f"marks.{asset}.valid_rows", bool(valid.all()), f"{int((~valid).sum())} invalid row(s)")
            valid_stamps = stamps.loc[valid].reset_index(drop=True)
            _check(
                report,
                f"marks.{asset}.monotonic",
                bool(valid_stamps.is_monotonic_increasing),
                "mark open_time is not monotonic",
            )
            non_hourly = valid_stamps[valid_stamps != valid_stamps.dt.floor("h")]
            _check(
                report,
                f"marks.{asset}.hour_grid",
                non_hourly.empty,
                (
                    f"{len(non_hourly)} non-hourly mark open_time row(s), "
                    f"first {non_hourly.iloc[0]}"
                    if not non_hourly.empty
                    else "all mark timestamps are on the UTC hour"
                ),
            )
            clean = numeric.loc[valid].copy()
            clean.index = pd.DatetimeIndex(stamps.loc[valid])
            clean = clean.sort_index()
            duplicate = clean.index.duplicated(keep=False)
            _check(report, f"marks.{asset}.unique_time", not duplicate.any(), f"{int(duplicate.sum())} duplicate mark timestamp(s)")
            future = clean.index > pd.Timestamp(moment)
            _check(report, f"marks.{asset}.no_future", not future.any(), f"{int(future.sum())} future mark timestamp(s)")
            invalid_price = (
                clean.loc[:, ["open", "high", "low", "close"]] <= 0.0
            ).any().any()
            invalid_ohlc = bool((clean["high"] < clean[["open", "close", "low"]].max(axis=1)).any() or (clean["low"] > clean[["open", "close", "high"]].min(axis=1)).any())
            _check(report, f"marks.{asset}.positive", not invalid_price, "non-positive OHLC value")
            _check(report, f"marks.{asset}.ohlc", not invalid_ohlc, "invalid OHLC relationship")
            invalid_volume = (clean.loc[:, ["volume", "quote_volume"]] < 0.0).any(axis=1)
            _check(
                report,
                f"marks.{asset}.volume",
                not invalid_volume.any(),
                f"{int(invalid_volume.sum())} invalid mark volume row(s)",
            )
            if not clean.empty:
                last = pd.Timestamp(clean.index.max())
                # At/after the fill minute the live chain can only have the
                # last *completed* hourly bar; the 01:00 bar that starts at
                # the same minute is used later by the retrospective engine,
                # not by the live data refresh.  Requiring it here would make
                # every 09:05 Beijing run fail until 02:00 UTC.
                required_last = (
                    pd.Timestamp(historical_panel_day, tz="UTC")
                    + pd.Timedelta(hours=23)
                    if historical_panel_day is not None
                    else required_last_mark_time(
                        moment,
                        execution_utc=execution_utc,
                    )
                )
                _check(report, f"marks.{asset}.last_bar", last >= required_last, f"last mark {last} is before required {required_last}")
                required_bar_present = required_last in clean.index
                _check(
                    report,
                    f"marks.{asset}.required_bar",
                    required_bar_present,
                    f"required mark bar {required_last} "
                    + ("present" if required_bar_present else "is missing"),
                )
                recent = clean.loc[clean.index >= last - pd.Timedelta(days=1)]
                gaps = recent.index.to_series().diff().dropna().dt.total_seconds().div(3600.0)
                max_gap = float(gaps.max()) if not gaps.empty else 1.0
                _check(report, f"marks.{asset}.recent_gap", max_gap <= 1.01, f"max recent gap {max_gap:.2f}h")
                marks[asset] = clean
    if mark_paths:
        report.summary["mark_assets"] = len(marks)
        if marks:
            report.summary["last_mark"] = str(max(frame.index.max() for frame in marks.values()))

    funding_summary: dict[str, dict[str, Any]] = {}
    if symbol_map is not None:
        funding_summary = _read_funding(
            raw,
            symbol_map,
            report,
            required_short_assets={str(asset) for asset in (required_short_assets or ())},
            required_assets=required_funding_set,
            require_all_fresh=bool(require_all_funding_fresh),
            stale_hours=float(funding_stale_hours),
            now=required_moment,
            publication_now=publication_moment,
            historical=historical_panel_day is not None,
        )
    report.summary["funding"] = funding_summary

    funding_paths = sorted((raw / "funding").glob("*.csv"))
    files = [
        panel_file,
        symbol_file,
        raw / "contracts.json",
        raw / "coverage.json",
        raw / "funding_manifest.json",
        raw / "funding_publication.json",
        *mark_paths,
        *funding_paths,
    ]
    provenance_paths = [path for path in files if path.is_file()]
    file_hashes = {
        _provenance_name(path, raw): _file_sha256(path)
        for path in provenance_paths
    }
    fingerprint_paths = [
        path
        for path in provenance_paths
        if path.name != "funding_publication.json"
    ]
    publication_path = raw / "funding_publication.json"
    fingerprint_payload = "\n".join(
        f"{_provenance_name(path, raw)}\0{_file_sha256(path)}"
        for path in sorted(fingerprint_paths, key=lambda item: _provenance_name(item, raw))
    ).encode()
    if publication_path.is_file():
        fingerprint_payload += (
            f"\nfunding_publication.json\0{_funding_publication_data_identity(publication_path)}"
        ).encode()
    report.provenance = {
        "raw_dir": str(raw),
        "panel_path": str(panel_file),
        "symbol_map_path": str(symbol_file),
        "files": file_hashes,
        "fingerprint": (
            "sha256:" + hashlib.sha256(fingerprint_payload).hexdigest()
            if fingerprint_payload
            else None
        ),
    }
    if manifest_path is not None and Path(manifest_path).is_file():
        report.provenance["manifest_sha256"] = _file_sha256(Path(manifest_path))
    report.passed = not report.hard_failures
    report.summary["checks"] = len(report.checks)
    report.summary["hard_failures"] = len(report.hard_failures)
    report.summary["warnings"] = len(report.warnings)
    return report


__all__ = ["DataAuditReport", "audit_derivatives_data"]
