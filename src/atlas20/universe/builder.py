"""Historical universe construction from processed market data."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from atlas20.config import ResearchConfig
from atlas20.data.catalog import metadata_is_excluded
from atlas20.logging_utils import get_logger

LOGGER = get_logger(__name__)

# A provider value missing for up to this many days is carried from the last
# print for ranking and signals; a longer gap leaves the cell missing.
CARRY_LIMIT_DAYS = 3
CARRIED_COLUMNS = ["date", "coin_id", "price", "market_cap", "volume"]
GAP_COLUMNS = ["date", "coin_id", "last_print", "next_print"]


def _text(value: object) -> str:
    return "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value)


def _category_list(listed: object, joined: object) -> list[str]:
    """One asset's categories from ``category_list``, else the joined ``categories``.

    metadata.csv stores ``category_list`` as the repr of a Python list, so read
    back it is the string "['Stablecoins', ...]". Compared as one string it
    never matched a keyword and the category backstop was dead.
    """
    if isinstance(listed, (list, tuple)):
        return [str(category) for category in listed]
    if isinstance(listed, str) and listed.strip().startswith("["):
        try:
            parsed = ast.literal_eval(listed.strip())
        except (SyntaxError, ValueError):
            parsed = None
        if isinstance(parsed, (list, tuple)):
            return [str(category) for category in parsed]
    for text in (joined, listed):
        if isinstance(text, str) and text.strip() and not text.strip().startswith("["):
            return [category.strip() for category in text.split(" | ") if category.strip()]
    return []


def _apply_universe_exclusions(snapshot: pd.DataFrame, config: ResearchConfig) -> pd.DataFrame:
    """Apply configured final eligibility exclusions to one snapshot.

    Candidate discovery already filters these names, but the processed panel
    can contain assets admitted by an older catalog. Re-applying the same gates
    here keeps the strategy universe fail-closed and prevents a legacy
    candidate such as Rain from re-entering through cached data. The rule is
    the catalog's own :func:`atlas20.data.catalog.metadata_is_excluded`, so the
    backstop cannot drift from discovery.
    """
    if snapshot.empty:
        return snapshot

    def column(name: str) -> list[object]:
        return snapshot[name].tolist() if name in snapshot.columns else [None] * len(snapshot)

    excluded = [
        metadata_is_excluded(
            {
                "id": _text(coin_id),
                "symbol": _text(symbol),
                "name": _text(name),
                "categories": _category_list(listed, joined),
            },
            config.universe,
        )
        for coin_id, symbol, name, listed, joined in zip(
            column("coin_id"), column("symbol"), column("name"), column("category_list"), column("categories")
        )
    ]
    return snapshot.loc[~pd.Series(excluded, index=snapshot.index, dtype=bool)].copy()


@dataclass
class MarketDataBundle:
    """Wide daily matrices used by the backtest engine."""

    raw_price: pd.DataFrame
    price: pd.DataFrame
    returns: pd.DataFrame
    market_cap: pd.DataFrame
    volume: pd.DataFrame
    history_count: pd.DataFrame
    metadata: pd.DataFrame
    # One row per (date, coin_id) where the provider had no value and the
    # previous print was carried (at most CARRY_LIMIT_DAYS); boolean columns
    # price / market_cap / volume say which fields were carried.
    carried_cells: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=CARRIED_COLUMNS))
    # One row per (date, coin_id) with no price inside a live series (after the
    # first print, before the last). The return there is NaN, and the next
    # print's return spans the gap from last_print.
    return_gaps: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=GAP_COLUMNS))



def prepare_market_data(panel: pd.DataFrame, metadata: pd.DataFrame, config: ResearchConfig) -> MarketDataBundle:
    """Transform the long panel into aligned wide matrices."""
    panel = panel.copy()
    panel["date"] = pd.to_datetime(panel["date"]).dt.normalize()
    panel = panel.sort_values(["date", "coin_id"])

    raw_price = panel.pivot(index="date", columns="coin_id", values="price").sort_index()
    market_cap = panel.pivot(index="date", columns="coin_id", values="market_cap").sort_index()
    volume = panel.pivot(index="date", columns="coin_id", values="volume_usd").sort_index()

    full_index = pd.date_range(raw_price.index.min(), raw_price.index.max(), freq="D")
    raw_price = raw_price.reindex(full_index)
    raw_market_cap = market_cap.reindex(full_index)
    raw_volume = volume.reindex(full_index)

    history_count = raw_price.notna().cumsum()
    price = raw_price.ffill(limit=CARRY_LIMIT_DAYS)
    market_cap = raw_market_cap.ffill(limit=CARRY_LIMIT_DAYS)
    # Volume is carried with the same limit. It used to become 0 on a day the
    # provider had no row while price and market cap were carried, so the coin
    # failed the liquidity gate and the #21 coin was promoted (2022-07-31, a
    # month-end: chainlink at rank 18 dropped for monero). Past the limit the
    # price is missing too, so the 0 there keeps the coin out either way.
    volume = raw_volume.ffill(limit=CARRY_LIMIT_DAYS).fillna(0.0)
    carried_cells = _carried_cells(
        {
            "price": raw_price.isna() & price.notna(),
            "market_cap": raw_market_cap.isna() & market_cap.notna(),
            "volume": raw_volume.isna() & raw_volume.ffill(limit=CARRY_LIMIT_DAYS).notna(),
        }
    )

    # Each print's return is measured from the previous print, so the day
    # after a provider gap applies the whole move since the last print, and
    # every day without a print - a gap day, or any day after the feed ends -
    # has no return. Carrying the price through the gap without a limit used
    # to book exactly 0.0 on each gap day (while ``price`` went NaN from day 4),
    # a silent zero fill (AGENTS.md). A held coin over a gap now makes the
    # engine fail closed under its default missing_return_policy.
    previous_print = raw_price.ffill().shift(1)
    returns = (raw_price / previous_print - 1.0).replace([float("inf"), float("-inf")], float("nan"))
    return_gaps = _return_gaps(raw_price)
    _log_data_gaps(carried_cells, return_gaps)

    return MarketDataBundle(
        raw_price=raw_price,
        price=price,
        returns=returns,
        market_cap=market_cap,
        volume=volume,
        history_count=history_count,
        metadata=metadata,
        carried_cells=carried_cells,
        return_gaps=return_gaps,
    )


def _carried_cells(carried: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """List each (date, coin_id) where any field was carried from an earlier print."""
    stacked = {name: mask.stack() for name, mask in carried.items()}
    frame = pd.DataFrame(stacked).fillna(False).astype(bool)
    frame = frame[frame.any(axis=1)]
    frame.index = frame.index.set_names(["date", "coin_id"])
    return frame.reset_index().reindex(columns=CARRIED_COLUMNS).sort_values(["date", "coin_id"], ignore_index=True)


def _return_gaps(raw_price: pd.DataFrame) -> pd.DataFrame:
    """List each coin-day without a price between a coin's first and last print."""
    printed = raw_price.notna()
    inside = printed.cummax() & printed.iloc[::-1].cummax().iloc[::-1]
    gap = (~printed & inside).stack()
    gap = gap[gap]
    if gap.empty:
        return pd.DataFrame(columns=GAP_COLUMNS)
    print_dates = pd.DataFrame(
        {column: raw_price.index for column in raw_price.columns}, index=raw_price.index
    ).where(printed)
    frame = gap.index.to_frame(index=False, name=["date", "coin_id"])
    last_print = print_dates.ffill().stack()
    next_print = print_dates.bfill().stack()
    frame["last_print"] = last_print.reindex(gap.index).to_numpy()
    frame["next_print"] = next_print.reindex(gap.index).to_numpy()
    return frame.reindex(columns=GAP_COLUMNS).sort_values(["date", "coin_id"], ignore_index=True)


def _log_data_gaps(carried_cells: pd.DataFrame, return_gaps: pd.DataFrame) -> None:
    """Report carried and missing provider values instead of absorbing them silently."""
    if not carried_cells.empty:
        LOGGER.warning(
            "%d coin-day(s) carried from the previous print (limit %d days; price %d, market cap %d, "
            "volume %d): %s",
            len(carried_cells),
            CARRY_LIMIT_DAYS,
            int(carried_cells["price"].sum()),
            int(carried_cells["market_cap"].sum()),
            int(carried_cells["volume"].sum()),
            _cell_summary(carried_cells),
        )
    if not return_gaps.empty:
        LOGGER.warning(
            "%d coin-day(s) of provider gaps inside a live price series have no return; the next print "
            "spans the gap: %s",
            len(return_gaps),
            _cell_summary(return_gaps),
        )


def _cell_summary(cells: pd.DataFrame, limit: int = 10) -> str:
    """``coin first..last (n)`` per coin, for a log line."""
    parts = [
        f"{coin} {group['date'].min().date()}..{group['date'].max().date()} ({len(group)})"
        for coin, group in cells.groupby("coin_id", sort=True)
    ]
    more = f" and {len(parts) - limit} more coin(s)" if len(parts) > limit else ""
    return "; ".join(parts[:limit]) + more


def build_rebalance_universe(
    market: MarketDataBundle,
    rebalance_dates: list[pd.Timestamp],
    config: ResearchConfig,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Build the top-20 eligible universe at each rebalance date using point-in-time data."""
    metadata = market.metadata.copy()
    rows: list[pd.DataFrame] = []
    metadata_columns = [
        column
        for column in ("symbol", "name", "sector", "category_list")
        if column in metadata.columns
    ]
    # Exclusions depend only on a coin's metadata, so they are decided once per
    # coin, not per date: the catalog rule costs ~4 ms per 100 coins, which is
    # ~9 s over a daily universe. ``categories`` is read only as the fallback.
    exclusion_columns = [
        column for column in ("symbol", "name", "category_list", "categories") if column in metadata.columns
    ]
    coins = pd.DataFrame(index=pd.Index(market.price.columns, name="coin_id"))
    coins = coins.join(metadata[exclusion_columns], how="left").reset_index()
    eligible_coins = set(_apply_universe_exclusions(coins, config)["coin_id"])
    # CMC is the ranking authority. On a day it has no market cap for a coin
    # the builder carries the last one (so prices and signals stay defined),
    # but ranking on it would rank on stale data: AGENTS.md makes an asset
    # absent from CMC ineligible, and the data-chain audit checks that no rank
    # leans on a carried cap. The coin sits out that day and is ranked again
    # as soon as CMC prints (2022-07-31: chainlink, then back on 08-01).
    carried_caps: dict[pd.Timestamp, set[str]] = {}
    cells = market.carried_cells
    if not cells.empty:
        capped = cells[cells["market_cap"].astype(bool)]
        for date, coin in zip(pd.to_datetime(capped["date"]), capped["coin_id"].astype(str)):
            carried_caps.setdefault(pd.Timestamp(date), set()).add(coin)

    for rebalance_date in rebalance_dates:
        snapshot = pd.DataFrame(
            {
                "price": market.price.loc[rebalance_date],
                "market_cap": market.market_cap.loc[rebalance_date],
                "volume_usd": market.volume.loc[rebalance_date],
                "history_days": market.history_count.loc[rebalance_date],
            }
        )
        snapshot.index.name = "coin_id"
        snapshot = snapshot.join(metadata[metadata_columns], how="left")
        snapshot = snapshot.reset_index()
        snapshot = snapshot[snapshot["coin_id"].isin(eligible_coins)]
        stale = carried_caps.get(pd.Timestamp(rebalance_date), set()) & set(snapshot["coin_id"])
        if stale:
            LOGGER.warning(
                "Not ranking %s on %s: no same-day market cap from CMC (carried from an earlier print)",
                ", ".join(sorted(stale)),
                pd.Timestamp(rebalance_date).date(),
            )
            snapshot = snapshot[~snapshot["coin_id"].isin(stale)]
        snapshot = snapshot[
            snapshot["price"].notna()
            & (snapshot["price"] > 0)
            # A zero or negative market cap means the provider has no supply
            # data for that asset (CMC returns marketCap: 0 for e.g. WhiteBIT).
            # Treating it as valid would let the asset rank inside the Top-N
            # and displace a genuine constituent.
            & snapshot["market_cap"].notna()
            & (snapshot["market_cap"] > 0)
            & (snapshot["price"] >= config.universe.min_price)
            & (snapshot["volume_usd"] >= config.universe.min_daily_dollar_volume)
            & (snapshot["history_days"] >= config.universe.min_history_days)
        ].copy()

        if snapshot.empty:
            LOGGER.warning("No eligible assets on rebalance date %s", rebalance_date.date())
            continue

        # Liquidity gate: an inflated-supply / thin-float asset can rank highly
        # on market cap while being untradeable in size. Require either a
        # meaningful turnover ratio or a large absolute dollar volume.
        if config.universe.min_turnover_ratio > 0:
            turnover = snapshot["volume_usd"] / snapshot["market_cap"]
            liquid = (turnover >= config.universe.min_turnover_ratio) | (
                snapshot["volume_usd"] >= config.universe.min_turnover_volume_usd
            )
            snapshot = snapshot[liquid].copy()
            if snapshot.empty:
                LOGGER.warning("No liquid assets on rebalance date %s", rebalance_date.date())
                continue

        snapshot = snapshot.sort_values("market_cap", ascending=False).head(config.universe.universe_size).copy()
        snapshot["rebalance_date"] = rebalance_date
        snapshot["universe_rank"] = range(1, len(snapshot) + 1)
        rows.append(snapshot)

    if not rows:
        raise ValueError("No rebalance universes could be built")

    universe = pd.concat(rows, ignore_index=True)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        universe.to_csv(output_path, index=False)
    return universe
