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
    execution_target = pd.Timestamp(
        datetime.combine(
            last_completed + timedelta(days=1),
            execution_utc,
            tzinfo=UTC,
        )
    )
    if moment >= execution_target:
        return execution_target - pd.Timedelta(hours=1, minutes=5)
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
        invalid_cap = ~np.isfinite(frame["market_cap"].to_numpy(dtype=float)) | (frame["market_cap"] < 0.0)
        _check(report, "panel.valid_price", not invalid_price.any(), f"{int(invalid_price.sum())} non-positive/non-finite price row(s)", hard=False)
        _check(report, "panel.valid_volume", not invalid_volume.any(), f"{int(invalid_volume.sum())} negative/non-finite volume row(s)", hard=False)
        _check(report, "panel.valid_market_cap", not invalid_cap.any(), f"{int(invalid_cap.sum())} negative/non-finite market-cap row(s)", hard=False)
        latest = frame["date"].max()
        latest_rows = frame.loc[frame["date"] == latest]
        latest_price = pd.to_numeric(latest_rows["price"], errors="coerce").to_numpy(dtype=float)
        latest_volume = pd.to_numeric(latest_rows["volume_usd"], errors="coerce").to_numpy(dtype=float)
        latest_cap = pd.to_numeric(latest_rows["market_cap"], errors="coerce").to_numpy(dtype=float)
        latest_price_bad = ~np.isfinite(latest_price) | (latest_price <= 0.0)
        latest_volume_bad = ~np.isfinite(latest_volume) | (latest_volume < 0.0)
        latest_cap_bad = ~np.isfinite(latest_cap) | (latest_cap < 0.0)
        _check(report, "panel.latest_price", not latest_price_bad.any(), f"{int(latest_price_bad.sum())} non-positive/non-finite latest price row(s)")
        _check(report, "panel.latest_volume", not latest_volume_bad.any(), f"{int(latest_volume_bad.sum())} negative/non-finite latest volume row(s)")
        _check(report, "panel.latest_market_cap", not latest_cap_bad.any(), f"{int(latest_cap_bad.sum())} negative/non-finite latest market-cap row(s)")
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


def _read_funding(
    raw_dir: Path,
    symbol_map: pd.DataFrame,
    report: DataAuditReport,
    *,
    required_short_assets: set[str],
    require_all_fresh: bool,
    stale_hours: float,
    now: datetime,
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
        valid_stamps = stamps.loc[valid].reset_index(drop=True)
        _check(
            report,
            f"funding.{asset}.monotonic",
            bool(valid_stamps.is_monotonic_increasing),
            "funding_time is not monotonic",
        )
        clean = pd.DataFrame({"funding_time": stamps[valid], "funding_rate": rates[valid]}).sort_values("funding_time")
        _check(report, f"funding.{asset}.unique_time", not clean["funding_time"].duplicated().any(), f"{int(clean['funding_time'].duplicated().sum())} duplicate timestamp(s)")
        last = clean["funding_time"].max() if not clean.empty else pd.NaT
        _check(
            report,
            f"funding.{asset}.no_future",
            bool(pd.isna(last) or _as_utc(last) <= _as_utc(now) + pd.Timedelta(hours=1)),
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
        stale = False
        if pd.isna(last):
            stale = True
        else:
            age = (_as_utc(now) - _as_utc(last)).total_seconds() / 3600.0
            stale = age > max(stale_hours, interval if np.isfinite(interval) else 0.0)
        if require_all_fresh:
            _check(
                report,
                f"funding.{asset}.fresh",
                not stale,
                "funding is stale for the live short sleeve" if stale else "fresh",
            )
        elif asset in required_short_assets:
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
    require_all_funding_fresh: bool = False,
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
    if panel is not None and symbol_map is not None:
        _check_panel_symbol_alignment(panel, symbol_map, report)
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
            valid_stamps = stamps.loc[valid].reset_index(drop=True)
            _check(
                report,
                f"marks.{asset}.monotonic",
                bool(valid_stamps.is_monotonic_increasing),
                "mark open_time is not monotonic",
            )
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
                # At/after the fill minute the live chain can only have the
                # last *completed* hourly bar; the 01:00 bar that starts at
                # the same minute is used later by the retrospective engine,
                # not by the live data refresh.  Requiring it here would make
                # every 09:05 Beijing run fail until 02:00 UTC.
                required_last = required_last_mark_time(
                    moment,
                    execution_utc=execution_utc,
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
            require_all_fresh=bool(require_all_funding_fresh),
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
