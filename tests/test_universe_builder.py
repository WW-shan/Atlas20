"""Universe construction from the processed panel in ``atlas20.universe.builder``."""

from __future__ import annotations

import pandas as pd
import pytest

from atlas20.backtest.engine import run_backtest
from atlas20.config import FrictionConfig, load_config
from atlas20.universe.builder import (
    MarketDataBundle,
    _apply_universe_exclusions,
    build_rebalance_universe,
    prepare_market_data,
)


def _bundle_with_metadata(metadata: pd.DataFrame) -> MarketDataBundle:
    coins = list(metadata.index)
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    price = pd.DataFrame({coin: [100.0] * 3 for coin in coins}, index=idx)
    return MarketDataBundle(
        raw_price=price,
        price=price,
        returns=price.pct_change(),
        market_cap=pd.DataFrame({coin: [5e9] * 3 for coin in coins}, index=idx),
        volume=pd.DataFrame({coin: [1e9] * 3 for coin in coins}, index=idx),
        history_count=pd.DataFrame({coin: [365] * 3 for coin in coins}, index=idx),
        metadata=metadata,
    )


def test_category_backstop_parses_the_stringified_list_read_back_from_metadata_csv(tmp_path) -> None:
    """metadata.csv stores category_list as the repr of a list.

    Read back, "['Stablecoins', 'USD Stablecoin']" was compared as one string
    and never matched a keyword, so the category backstop was dead.
    """
    metadata = pd.DataFrame(
        {
            "coin_id": ["good", "pegged", "wrapped"],
            "symbol": ["GOOD", "PEG", "WRP"],
            "name": ["Alpha", "Beta", "Gamma"],
            "sector": ["Other"] * 3,
            "categories": [
                "Smart Contract Platform",
                "Stablecoins | USD Stablecoin",
                "Wrapped-Tokens | Ethereum Ecosystem",
            ],
            "category_list": [
                ["Smart Contract Platform"],
                ["Stablecoins", "USD Stablecoin"],
                ["Wrapped-Tokens", "Ethereum Ecosystem"],
            ],
        }
    )
    metadata.to_csv(tmp_path / "metadata.csv", index=False)
    read_back = pd.read_csv(tmp_path / "metadata.csv").set_index("coin_id")
    assert read_back.loc["pegged", "category_list"] == "['Stablecoins', 'USD Stablecoin']"

    universe = build_rebalance_universe(
        _bundle_with_metadata(read_back), [pd.Timestamp("2024-01-01")], load_config("config/base.yaml")
    )

    assert set(universe["coin_id"]) == {"good"}


def test_category_backstop_falls_back_to_the_joined_categories_column() -> None:
    snapshot = pd.DataFrame(
        {
            "coin_id": ["good", "staked"],
            "symbol": ["GOOD", "STK"],
            "name": ["Alpha", "Beta"],
            "categories": ["Layer 1 (L1)", "Liquid Staking Tokens | Ethereum Ecosystem"],
            "category_list": [float("nan"), "not a list"],
        }
    )

    kept = _apply_universe_exclusions(snapshot, load_config("config/base.yaml"))

    assert kept["coin_id"].tolist() == ["good"]


def test_category_backstop_uses_the_catalog_matching_rule() -> None:
    """A keyword must match a whole category or its leading words, as in the catalog.

    "USD Stablecoin" is not "Stablecoins", and "Treasury" as the first word of
    "Treasury-backed Tokens" is a match while "DAO Treasury Tools" is not.
    """
    snapshot = pd.DataFrame(
        {
            "coin_id": ["usd_only", "treasury_first", "treasury_later"],
            "symbol": ["AA", "BB", "CC"],
            "name": ["Alpha", "Beta", "Gamma"],
            "category_list": [
                "['USD Stablecoin']",
                "['Treasury-backed Tokens']",
                "['DAO Treasury Tools']",
            ],
        }
    )
    kept = _apply_universe_exclusions(snapshot, load_config("config/base.yaml"))

    assert kept["coin_id"].tolist() == ["usd_only", "treasury_later"]


def _panel(prices: dict[str, list[float]], market_caps: dict[str, float], missing: set[tuple[str, int]]) -> pd.DataFrame:
    """A long provider panel with no row at all for each ``(coin, day)`` in ``missing``."""
    dates = pd.date_range("2022-07-27", periods=len(next(iter(prices.values()))), freq="D")
    rows = [
        {
            "date": date,
            "coin_id": coin,
            "price": series[position],
            "market_cap": market_caps[coin] * series[position] / series[0],
            "volume_usd": 1e9,
        }
        for coin, series in prices.items()
        for position, date in enumerate(dates)
        if (coin, position) not in missing
    ]
    return pd.DataFrame(rows)


def _metadata(coins: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {"symbol": [coin.upper() for coin in coins], "name": coins, "sector": ["Other"] * len(coins)},
        index=pd.Index(coins, name="coin_id"),
    )


def test_a_missing_provider_row_carries_volume_like_price_and_market_cap(caplog) -> None:
    """A coin without a provider row is carried and reported, but not ranked that day.

    Volume used to become 0 while price and market cap were carried, which
    only kept the coin out of the Top-N by accident (the $25M liquidity gate).
    Volume is carried now, and the coin is kept out on purpose: CMC is the
    ranking authority and has no market cap for it that day, so ranking it on
    the carried one would rank on stale data (AGENTS.md: an asset absent from
    CMC is not eligible for ranking). 2022-07-31 is the real case: chainlink,
    rank 18 the day before, sits out the July month-end and monero enters.
    """
    prices = {"alpha": [100.0] * 5, "chainlink": [7.8] * 5, "monero": [150.0] * 5}
    caps = {"alpha": 10e9, "chainlink": 8e9, "monero": 5e9}
    panel = _panel(prices, caps, missing={("chainlink", 4)})
    config = load_config("config/base.yaml")
    config.universe.universe_size = 2
    config.universe.min_history_days = 1
    rebalance = pd.Timestamp("2022-07-31")

    with caplog.at_level("WARNING", logger="atlas20.universe.builder"):
        market = prepare_market_data(panel, _metadata(list(prices)), config)
    universe = build_rebalance_universe(market, [rebalance], config)

    assert set(universe["coin_id"]) == {"alpha", "monero"}
    assert market.volume.loc[rebalance, "chainlink"] == 1e9
    carried = market.carried_cells.set_index(["date", "coin_id"])
    assert carried.index.tolist() == [(rebalance, "chainlink")]
    assert carried.loc[(rebalance, "chainlink")].tolist() == [True, True, True]
    assert "carried" in caplog.text and "chainlink" in caplog.text


def test_volume_is_not_carried_past_the_price_carry_limit() -> None:
    prices = {"alpha": [100.0] * 6}
    panel = _panel(prices, {"alpha": 10e9}, missing={("alpha", 1), ("alpha", 2), ("alpha", 3), ("alpha", 4)})

    market = prepare_market_data(panel, _metadata(["alpha"]), load_config("config/base.yaml"))

    assert market.volume["alpha"].tolist() == [1e9, 1e9, 1e9, 1e9, 0.0, 1e9]
    assert market.price["alpha"].isna().tolist() == [False, False, False, False, True, False]


def test_a_provider_gap_inside_a_live_series_is_a_missing_return_not_a_flat_day(caplog) -> None:
    """Gap days have no return; the next print is measured from the last print.

    The gap used to be carried at the last price without a limit, booking
    exactly 0.0 returns on every gap day (while ``price`` went NaN from day 4),
    and the whole move on the resume day. AGENTS.md: never silently fill
    missing returns with zero or stale prices.
    """
    prices = {"curve": [1.00, 1.10, 1.20, 1.30, 1.40, 1.50, 1.65]}
    panel = _panel(prices, {"curve": 1e9}, missing={("curve", 1), ("curve", 2), ("curve", 3), ("curve", 4)})

    with caplog.at_level("WARNING", logger="atlas20.universe.builder"):
        market = prepare_market_data(panel, _metadata(["curve"]), load_config("config/base.yaml"))

    returns = market.returns["curve"]
    assert returns.iloc[1:5].isna().all()
    assert returns.iloc[5] == pytest.approx(1.50 / 1.00 - 1.0)
    assert returns.iloc[6] == pytest.approx(1.65 / 1.50 - 1.0)
    gaps = market.return_gaps
    assert gaps["coin_id"].tolist() == ["curve"] * 4
    assert gaps["date"].tolist() == list(pd.date_range("2022-07-28", "2022-07-31", freq="D"))
    assert "gap" in caplog.text and "curve" in caplog.text


def test_a_held_coin_over_a_provider_gap_fails_closed_in_the_engine() -> None:
    """The engine's default policy refuses to invent the gap-day returns."""
    prices = {"curve": [1.00, 1.10, 1.20, 1.30]}
    panel = _panel(prices, {"curve": 1e9}, missing={("curve", 2)})
    market = prepare_market_data(panel, _metadata(["curve"]), load_config("config/base.yaml"))
    index = market.returns.index

    with pytest.raises(ValueError, match="Missing returns for held assets on 2022-07-29: curve"):
        run_backtest(
            "gap_check",
            market.returns,
            {index[0]: pd.Series({"curve": 1.0})},
            pd.Series({"curve": "Other"}),
            FrictionConfig(max_weight_per_coin=1.0),
            initial_capital=1.0,
        )


def test_a_coin_is_ranked_again_once_its_market_cap_prints(caplog) -> None:
    prices = {"alpha": [100.0] * 5, "chainlink": [7.8] * 5, "monero": [150.0] * 5}
    caps = {"alpha": 10e9, "chainlink": 8e9, "monero": 5e9}
    panel = _panel(prices, caps, missing={("chainlink", 3)})
    config = load_config("config/base.yaml")
    config.universe.universe_size = 2
    config.universe.min_history_days = 1
    gap_day, next_day = pd.Timestamp("2022-07-30"), pd.Timestamp("2022-07-31")

    market = prepare_market_data(panel, _metadata(list(prices)), config)
    with caplog.at_level("WARNING", logger="atlas20.universe.builder"):
        universe = build_rebalance_universe(market, [gap_day, next_day], config)

    members = universe.groupby("rebalance_date")["coin_id"].apply(set)
    assert members.loc[gap_day] == {"alpha", "monero"}
    assert members.loc[next_day] == {"alpha", "chainlink"}
    assert "no same-day market cap" in caplog.text and "chainlink" in caplog.text
