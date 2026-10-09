"""Loading helpers for Bitget mark candles and historical funding proxies."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

import pandas as pd

_MARK_COLUMNS = ["open", "high", "low", "close"]


def _as_utc_index(values: Iterable[object]) -> pd.DatetimeIndex:
    index = pd.DatetimeIndex([pd.Timestamp(value) for value in values])
    if index.tz is None:
        index = index.tz_localize("UTC")
    else:
        index = index.tz_convert("UTC")
    return index


def _selected_map(symbol_map: pd.DataFrame, coins: Iterable[str] | None) -> pd.DataFrame:
    required = {"coin_id", "bitget_symbol"}
    missing = required.difference(symbol_map.columns)
    if missing:
        raise ValueError(f"symbol_map is missing columns {sorted(missing)}")
    frame = symbol_map.loc[:, ["coin_id", "bitget_symbol"]].copy()
    frame["coin_id"] = frame["coin_id"].astype(str)
    frame["bitget_symbol"] = frame["bitget_symbol"].fillna("").astype(str)
    frame = frame[frame["bitget_symbol"].ne("")].drop_duplicates("coin_id", keep="last")
    if coins is not None:
        wanted = {str(coin) for coin in coins}
        frame = frame[frame["coin_id"].isin(wanted)]
    return frame.sort_values("coin_id").reset_index(drop=True)


def load_mark_candles(
    raw_dir: Path,
    symbol_map: pd.DataFrame,
    *,
    coins: Iterable[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Load ``<symbol>_mark.csv`` files keyed by point-in-time coin id.

    A contract without a downloaded mark file is omitted rather than replaced
    with another asset.  Callers can compare the returned keys with the
    symbol map to report unavailable weights.
    """
    raw_dir = Path(raw_dir)
    selected = _selected_map(symbol_map, coins)
    loaded: dict[str, pd.DataFrame] = {}
    for record in selected.to_dict("records"):
        coin_id = str(record["coin_id"])
        symbol = str(record["bitget_symbol"])
        path = raw_dir / "candles" / f"{symbol}_mark.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        if frame.empty or "open_time" not in frame.columns:
            continue
        missing = set(_MARK_COLUMNS).difference(frame.columns)
        if missing:
            raise ValueError(f"{path}: missing mark columns {sorted(missing)}")
        frame = frame.copy()
        frame.index = _as_utc_index(frame["open_time"])
        frame = frame.loc[:, _MARK_COLUMNS].apply(pd.to_numeric, errors="coerce")
        frame = frame[~frame.index.duplicated(keep="last")].sort_index()
        if frame.empty:
            continue
        loaded[coin_id] = frame
    return loaded


def load_binance_funding(
    funding_dir: Path,
    *,
    coins: Iterable[str],
) -> pd.DataFrame:
    """Load Binance monthly-archive funding as a wide point-in-time proxy.

    The caller is responsible for labelling this as a proxy; the Phase 1
    overlap audit does not permit it to be treated as exact Bitget history.
    """
    funding_dir = Path(funding_dir)
    series: dict[str, pd.Series] = {}
    for coin_id in sorted({str(coin) for coin in coins}):
        path = funding_dir / f"{coin_id}.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        if frame.empty or not {"calc_time", "last_funding_rate"}.issubset(frame.columns):
            continue
        stamp = pd.to_numeric(frame["calc_time"], errors="coerce")
        rate = pd.to_numeric(frame["last_funding_rate"], errors="coerce")
        index = pd.to_datetime(stamp, unit="ms", utc=True, errors="coerce")
        values = pd.Series(rate.to_numpy(dtype=float), index=index, name=coin_id).dropna()
        values = values[~values.index.duplicated(keep="last")].sort_index()
        if not values.empty:
            series[coin_id] = values
    if not series:
        return pd.DataFrame()
    return pd.DataFrame(series).sort_index()


def load_bitget_funding(
    raw_dir: Path,
    symbol_map: pd.DataFrame,
    *,
    coins: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Load the exact recent Bitget funding files, keyed by coin id."""
    raw_dir = Path(raw_dir)
    selected = _selected_map(symbol_map, coins)
    series: dict[str, pd.Series] = {}
    for coin_id in selected["coin_id"].astype(str):
        path = raw_dir / "funding" / f"{coin_id}.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        if frame.empty or not {"funding_time", "funding_rate"}.issubset(frame.columns):
            continue
        index = pd.to_datetime(frame["funding_time"], utc=True, errors="coerce")
        rate = pd.to_numeric(frame["funding_rate"], errors="coerce")
        values = pd.Series(rate.to_numpy(dtype=float), index=index, name=coin_id).dropna()
        values = values[~values.index.duplicated(keep="last")].sort_index()
        if not values.empty:
            series[coin_id] = values
    if not series:
        return pd.DataFrame()
    return pd.DataFrame(series).sort_index()


__all__ = ["load_binance_funding", "load_bitget_funding", "load_mark_candles"]
