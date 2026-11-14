"""Fail-closed reliability audit for the derivatives live data chain.

The audit deliberately separates hard failures from warnings.  A hard failure
means the live executor must not plan or place an order: the panel is missing
its last completed day, a mark file is duplicated/future/invalid, a contract is
not online/perpetual/2x-compatible, or a required short lacks fresh funding.
Historical or provider-window warnings remain visible without being silently
converted into zero-filled data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

UTC = timezone.utc
DEFAULT_EXECUTION_UTC = time(1, 5)
DEFAULT_FUNDING_STALE_HOURS = 12.0


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
    required = {"date", "coin_id", "price", "volume_usd", "market_cap"}
    missing = sorted(required.difference(frame.columns))
    _check(report, "panel.columns", not missing, f"missing columns {missing}" if missing else "all required columns present")
    if missing:
        return None
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True, format="mixed", errors="coerce").dt.normalize()
    frame["coin_id"] = frame["coin_id"].astype(str)
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
        invalid_cap = ~np.isfinite(frame["market_cap"].to_numpy(dtype=float)) | (frame["market_cap"] < 0.0)
        _check(report, "panel.valid_price", not invalid_price.any(), f"{int(invalid_price.sum())} non-positive/non-finite price row(s)", hard=False)
        _check(report, "panel.valid_volume", not invalid_volume.any(), f"{int(invalid_volume.sum())} negative/non-finite volume row(s)", hard=False)
        _check(report, "panel.valid_market_cap", not invalid_cap.any(), f"{int(invalid_cap.sum())} negative/non-finite market-cap row(s)", hard=False)
        latest = frame["date"].max()
        latest_rows = frame.loc[frame["date"] == latest]
        latest_price = pd.to_numeric(latest_rows["price"], errors="coerce")
        latest_volume = pd.to_numeric(latest_rows["volume_usd"], errors="coerce")
        latest_cap = pd.to_numeric(latest_rows["market_cap"], errors="coerce")
        _check(report, "panel.latest_price", bool((latest_price > 0.0).all()), f"{int((latest_price <= 0.0).sum())} non-positive latest price row(s)")
        _check(report, "panel.latest_volume", bool((latest_volume >= 0.0).all()), f"{int((latest_volume < 0.0).sum())} negative latest volume row(s)")
        _check(report, "panel.latest_market_cap", bool((latest_cap >= 0.0).all()), f"{int((latest_cap < 0.0).sum())} negative latest market-cap row(s)")
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
    required = {"coin_id", "bitget_symbol", "contract_status", "fund_interval", "min_trade_usdt", "size_multiplier"}
    missing = sorted(required.difference(frame.columns))
    _check(report, "symbol_map.columns", not missing, f"missing columns {missing}" if missing else "all required columns present")
    if missing:
        return None
    frame = frame.copy()
    frame["coin_id"] = frame["coin_id"].astype(str).str.strip()
    frame["bitget_symbol"] = frame["bitget_symbol"].fillna("").astype(str).str.strip()
    duplicate_coin = frame["coin_id"].duplicated(keep=False)
    _check(report, "symbol_map.unique_coin", not duplicate_coin.any(), f"{int(duplicate_coin.sum())} duplicate coin_id row(s)")
    normal = frame.loc[frame["contract_status"].astype(str).str.lower().eq("normal")].copy()
    missing_symbol = normal["bitget_symbol"].eq("")
    _check(report, "symbol_map.normal_symbol", not missing_symbol.any(), f"{int(missing_symbol.sum())} normal row(s) without Bitget symbol")
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
    return {str(row.get("symbol") or "").upper(): row for row in rows if row.get("symbol")}


def _read_funding(
    raw_dir: Path,
    symbol_map: pd.DataFrame,
    report: DataAuditReport,
    *,
    required_short_assets: set[str],
    stale_hours: float,
    now: datetime,
) -> dict[str, dict[str, Any]]:
    manifest_path = raw_dir / "funding_manifest.json"
    if manifest_path.is_file():
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            _check(
                report,
                "funding.manifest_object",
                isinstance(payload, dict),
                "funding manifest must be a JSON object",
            )
        except (OSError, json.JSONDecodeError) as exc:
            _check(report, "funding.manifest_readable", False, str(exc))
    else:
        _check(report, "funding.manifest_exists", False, f"missing {manifest_path}")
    normal = symbol_map.loc[symbol_map["contract_status"].astype(str).str.lower().eq("normal")]
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
        stamps = pd.to_datetime(frame["funding_time"], utc=True, format="mixed", errors="coerce")
        rates = pd.to_numeric(frame["funding_rate"], errors="coerce")
        valid = stamps.notna() & rates.notna() & np.isfinite(rates.to_numpy(dtype=float))
        _check(report, f"funding.{asset}.valid_rows", bool(valid.all()), f"{int((~valid).sum())} invalid row(s)")
        clean = pd.DataFrame({"funding_time": stamps[valid], "funding_rate": rates[valid]}).sort_values("funding_time")
        _check(report, f"funding.{asset}.unique_time", not clean["funding_time"].duplicated().any(), f"{int(clean['funding_time'].duplicated().sum())} duplicate timestamp(s)")
        last = clean["funding_time"].max() if not clean.empty else pd.NaT
        interval = float(pd.to_numeric(row.get("fund_interval"), errors="coerce")) if pd.notna(row.get("fund_interval")) else float("nan")
        stale = False
        if pd.isna(last):
            stale = True
        else:
            age = (_as_utc(now) - _as_utc(last)).total_seconds() / 3600.0
            stale = age > max(stale_hours, interval if np.isfinite(interval) else 0.0)
        if asset in required_short_assets:
            _check(report, f"funding.{asset}.fresh_for_short", not stale, "funding is stale for a required short" if stale else "fresh for required short")
        elif stale:
            _check(report, f"funding.{asset}.fresh", False, "funding is stale but no short is required", hard=False)
        summary[asset] = {
            "last": None if pd.isna(last) else str(last),
            "rows": int(len(clean)),
            "stale": bool(stale),
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
    min_panel_assets: int = 20,
    required_short_assets: Iterable[str] | None = None,
    execution_utc: time = DEFAULT_EXECUTION_UTC,
    funding_stale_hours: float = DEFAULT_FUNDING_STALE_HOURS,
) -> DataAuditReport:
    """Audit one live derivatives data snapshot without changing any file."""

    raw = Path(raw_dir)
    panel_file = Path(panel_path)
    symbol_file = Path(symbol_map_path) if symbol_map_path is not None else raw / "symbol_map.csv"
    moment = _as_utc(now or datetime.now(UTC))
    report = DataAuditReport(passed=False)
    report.summary["now"] = moment.isoformat()
    panel = _read_panel(panel_file, report, moment)
    symbol_map = _read_symbol_map(symbol_file, report)
    contracts = _read_contracts(raw / "contracts.json", report)
    if panel is not None and not panel.empty:
        last_completed = moment.date() - timedelta(days=1)
        latest = panel["date"].max().date()
        _check(
            report,
            "panel.last_completed_day",
            latest == last_completed,
            f"panel does not reach the last completed UTC day {last_completed} (latest {latest})"
            if latest != last_completed
            else f"panel reaches {last_completed}",
        )
        latest_assets = int(panel.loc[panel["date"] == pd.Timestamp(latest, tz="UTC"), "coin_id"].nunique())
        _check(report, "panel.min_assets", latest_assets >= int(min_panel_assets), f"{latest_assets} asset(s), require {min_panel_assets}")
        report.summary["panel_latest"] = str(latest)
        report.summary["panel_latest_assets"] = latest_assets

    marks: dict[str, pd.DataFrame] = {}
    mark_paths: list[Path] = []
    if symbol_map is not None:
        normal = symbol_map.loc[symbol_map["contract_status"].astype(str).str.lower().eq("normal")]
        for row in normal.to_dict("records"):
            asset = str(row["coin_id"])
            symbol = str(row["bitget_symbol"]).strip().upper()
            contract = contracts.get(symbol)
            _check(report, f"contracts.{asset}.exists", contract is not None, f"missing contract {symbol}")
            if contract is not None:
                status = str(contract.get("symbolStatus") or "").lower()
                kind = str(contract.get("symbolType") or "").lower()
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
                _check(report, f"contracts.{asset}.steps", all(np.isfinite(v) and v > 0.0 for v in (min_qty, min_usdt, step, interval)), "min quantity/notional, size step and funding interval must be positive")
                _check(report, f"contracts.{asset}.taker_fee", np.isfinite(taker) and taker >= 0.0, f"taker fee={taker:g}" if np.isfinite(taker) else "missing taker fee")
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
            missing = sorted({"open_time", "open", "high", "low", "close"}.difference(frame.columns))
            _check(report, f"marks.{asset}.columns", not missing, f"missing columns {missing}" if missing else "required OHLC columns present")
            if missing:
                continue
            stamps = pd.to_datetime(frame["open_time"], utc=True, format="mixed", errors="coerce")
            numeric = frame.loc[:, ["open", "high", "low", "close"]].apply(pd.to_numeric, errors="coerce")
            valid = stamps.notna() & numeric.notna().all(axis=1)
            _check(report, f"marks.{asset}.valid_rows", bool(valid.all()), f"{int((~valid).sum())} invalid row(s)")
            clean = numeric.loc[valid].copy()
            clean.index = pd.DatetimeIndex(stamps.loc[valid])
            clean = clean.sort_index()
            duplicate = clean.index.duplicated(keep=False)
            _check(report, f"marks.{asset}.unique_time", not duplicate.any(), f"{int(duplicate.sum())} duplicate mark timestamp(s)")
            future = clean.index > pd.Timestamp(moment)
            _check(report, f"marks.{asset}.no_future", not future.any(), f"{int(future.sum())} future mark timestamp(s)")
            invalid_price = (clean <= 0.0).any().any()
            invalid_ohlc = bool((clean["high"] < clean[["open", "close", "low"]].max(axis=1)).any() or (clean["low"] > clean[["open", "close", "high"]].min(axis=1)).any())
            _check(report, f"marks.{asset}.positive", not invalid_price, "non-positive OHLC value")
            _check(report, f"marks.{asset}.ohlc", not invalid_ohlc, "invalid OHLC relationship")
            if not clean.empty:
                last = pd.Timestamp(clean.index.max())
                last_completed = moment.date() - timedelta(days=1)
                execution_target = pd.Timestamp(datetime.combine(last_completed + timedelta(days=1), execution_utc, tzinfo=UTC))
                # At/after the fill minute the live chain can only have the
                # last *completed* hourly bar; the 01:00 bar that starts at
                # the same minute is used later by the retrospective engine,
                # not by the live data refresh.  Requiring it here would make
                # every 09:05 Beijing run fail until 02:00 UTC.
                required_last = (
                    execution_target - pd.Timedelta(hours=1, minutes=5)
                    if moment >= execution_target
                    else pd.Timestamp(last_completed, tz="UTC") + pd.Timedelta(hours=23)
                )
                _check(report, f"marks.{asset}.last_bar", last >= required_last, f"last mark {last} is before required {required_last}")
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
            stale_hours=float(funding_stale_hours),
            now=moment,
        )
    report.summary["funding"] = funding_summary

    files = [panel_file, symbol_file, raw / "contracts.json", raw / "coverage.json", raw / "funding_manifest.json", *mark_paths]
    provenance_paths = [path for path in files if path.is_file()]
    file_hashes = {str(path.relative_to(raw)) if path.is_relative_to(raw) else str(path): _file_sha256(path) for path in provenance_paths}
    report.provenance = {
        "raw_dir": str(raw),
        "panel_path": str(panel_file),
        "symbol_map_path": str(symbol_file),
        "files": file_hashes,
        "fingerprint": _tree_fingerprint(provenance_paths, root=raw),
    }
    if manifest_path is not None and Path(manifest_path).is_file():
        report.provenance["manifest_sha256"] = _file_sha256(Path(manifest_path))
    report.passed = not report.hard_failures
    report.summary["checks"] = len(report.checks)
    report.summary["hard_failures"] = len(report.hard_failures)
    report.summary["warnings"] = len(report.warnings)
    return report


__all__ = ["DataAuditReport", "audit_derivatives_data"]
