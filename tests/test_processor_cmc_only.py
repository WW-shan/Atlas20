"""The processed panel is built from a single provider: CoinMarketCap.

Price, volume and market cap must all come out of the same snapshot so the
price/market-cap ratio is internally consistent. Any leftover file from the
retired price sources must be ignored rather than silently merged in.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import pytest

from atlas20.config import load_config, load_sector_config
from atlas20.data import processor


def _write_candidates(raw_dir: Path, *assets: dict) -> None:
    path = raw_dir / "coingecko" / "candidate_assets.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(list(assets)), encoding="utf-8")


def _candidate(coin_id: str, symbol: str, cmc_id: int, coinpaprika_id: str | None = None) -> dict:
    asset = {
        "id": coin_id,
        "symbol": symbol,
        "name": coin_id.title(),
        "market_cap": 1_000_000.0,
        "market_cap_rank": 1,
        "current_price": 100.0,
        "total_volume": 10_000.0,
        "cmc_id": cmc_id,
    }
    if coinpaprika_id is not None:
        asset["coinpaprika_id"] = coinpaprika_id
    return asset


def _write_cmc(
    raw_dir: Path,
    cmc_id: int,
    days: list[str],
    *,
    price: float = 250.0,
    volume: float = 9_000_000.0,
    market_cap: float | None = 5_000_000.0,
) -> None:
    directory = raw_dir / "coinmarketcap" / "history"
    directory.mkdir(parents=True, exist_ok=True)
    start = int(pd.Timestamp(days[0]).timestamp())
    end = int(pd.Timestamp(days[-1]).timestamp())
    payload = [
        {
            "timeOpen": f"{d}T00:00:00.000Z",
            "quote": {
                "close": price,
                "volume": volume,
                "marketCap": market_cap,
                "circulatingSupply": 20_000.0,
            },
        }
        for d in days
    ]
    (directory / f"{cmc_id}_{start}_{end}.json").write_text(json.dumps(payload), encoding="utf-8")


def _config(tmp_path: Path, start: str = "2024-01-01", end: str = "2024-01-10"):
    config = load_config("config/base.yaml")
    config.project_root = tmp_path
    config.start_date = start
    config.end_date = end
    config.data_quality.min_price_days = 2
    config.data_quality.min_market_cap_days = 2
    # The fixtures only span a few days; the production floor is 30.
    config.data_quality.cross_check_min_overlap_days = 2
    # Most fixtures predate the independent-source cache. Keep them focused on
    # the behavior they exercise; tests for mandatory verification opt in.
    config.data_quality.require_cross_check = False
    return config


def _days() -> list[str]:
    return ["2024-01-01", "2024-01-02", "2024-01-03"]


def test_panel_uses_coinmarketcap_price_volume_and_market_cap(tmp_path):
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1))
    _write_cmc(raw_dir, 1, _days())

    panel, metadata = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert set(panel["price"]) == {250.0}
    assert set(panel["volume_usd"]) == {9_000_000.0}
    assert set(panel["market_cap"]) == {5_000_000.0}
    assert panel["price_source"].eq("coinmarketcap").all()
    assert panel["volume_source"].eq("coinmarketcap").all()
    assert panel["market_cap_source"].eq("coinmarketcap").all()
    assert metadata.loc["bitcoin", "sector"]


def test_retired_source_cache_is_ignored(tmp_path):
    """A stale CryptoCompare cache must not leak back into the panel."""
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1))
    _write_cmc(raw_dir, 1, _days())
    legacy = raw_dir / "cryptocompare" / "histoday" / "BTC.json"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text(
        json.dumps(
            {
                "Response": "Success",
                "Data": {
                    "Data": [
                        {"time": int(pd.Timestamp(d).timestamp()), "close": 1.0, "volumeto": 1.0}
                        for d in _days()
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert set(panel["price"]) == {250.0}, "legacy prices must not be spliced in"


def test_asset_without_coinmarketcap_history_is_skipped(tmp_path):
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1), _candidate("ghost", "GHOST", 2))
    _write_cmc(raw_dir, 1, _days())

    panel, metadata = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert set(panel["coin_id"]) == {"bitcoin"}
    assert "ghost" not in metadata.index


def test_zero_market_cap_asset_never_enters_the_panel(tmp_path):
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1), _candidate("whitebit", "WBT", 2))
    _write_cmc(raw_dir, 1, _days())
    _write_cmc(raw_dir, 2, _days(), market_cap=0.0)

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert set(panel["coin_id"]) == {"bitcoin"}
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    assert quality.loc["whitebit", "validation_reason"] == "insufficient_market_cap_history"
    assert not bool(quality.loc["whitebit", "validation_passed"])


def test_data_quality_keeps_the_api_contract_columns(tmp_path):
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1))
    _write_cmc(raw_dir, 1, _days())

    processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv")
    required = {
        "symbol",
        "validation_passed",
        "validation_reason",
        "latest_overlap_date",
        "latest_price_gap",
        "median_price_gap",
        "price_correlation",
        "included_in_panel",
    }
    assert required <= set(quality.columns)
    assert quality.loc[0, "symbol"] == "BTC"
    assert bool(quality.loc[0, "included_in_panel"]) is True


def test_partial_provider_tail_is_not_added_to_panel(tmp_path):
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1), _candidate("ethereum", "ETH", 2))
    _write_cmc(raw_dir, 1, _days())
    _write_cmc(raw_dir, 2, [*_days(), "2024-01-04"])

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert panel["date"].max() == pd.Timestamp("2024-01-03")
    assert set(panel[panel["date"] == panel["date"].max()]["coin_id"]) == {"bitcoin", "ethereum"}


def _ten_coin_universe(raw_dir: Path, days: list[str], *, last_day_by_coin: dict[int, str]) -> None:
    """coin0 is the largest; each coin's CMC series ends on its own last day."""
    _write_candidates(raw_dir, *[_candidate(f"coin{i}", f"C{i}", 100 + i) for i in range(10)])
    for i in range(10):
        last = last_day_by_coin.get(i, days[-1])
        _write_cmc(raw_dir, 100 + i, [d for d in days if d <= last], market_cap=1e9 * (10 - i))


def test_live_asset_behind_its_venue_holds_the_panel_end(tmp_path, caplog):
    """The largest coin's CMC feed stops three days before everyone else's
    while Gate.io keeps printing it. 9/10 coverage cleared the 90% bar, so the
    panel ran on to the last date without it: the largest coin vanished from
    the point-in-time Top-N on the three newest dates - the live signal dates -
    and the next coin was promoted in its place. Nothing named it.

    Blocking the asset would delete its whole history instead, so it is
    admitted and the panel end is held at its last print: every published
    date carries every live asset, the lag is recorded, and a stale panel is
    caught by the live signal's freshness guard instead of trading a wrong
    universe."""
    days = _span("2024-01-01", 70)
    config = _config(tmp_path, start=days[0], end=days[-1])
    raw_dir = tmp_path / "data" / "raw"
    _ten_coin_universe(raw_dir, days, last_day_by_coin={0: days[-4]})
    candidates = json.loads((raw_dir / "coingecko" / "candidate_assets.json").read_text(encoding="utf-8"))
    candidates[0]["gateio_pair"] = "C0_USDT"
    _write_candidates(raw_dir, *candidates)
    _write_gateio(raw_dir, "C0", days)

    with caplog.at_level("WARNING", logger="atlas20.data.processor"):
        panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert panel["date"].max() == pd.Timestamp(days[-4])
    per_date = panel.groupby("date")["coin_id"].nunique()
    assert (per_date == 10).all(), "no published date may silently drop a live asset"
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    row = quality.loc["coin0"]
    assert bool(row["crosscheck_primary_stale"]) is True
    assert row["crosscheck_primary_lag_days"] == 3
    assert row["cmc_lag_days"] == 3
    assert bool(row["holds_panel_end"]) is True
    assert quality.loc["coin1", "cmc_lag_days"] == 0
    assert bool(quality.loc["coin1", "holds_panel_end"]) is False
    assert str(quality.loc["coin1", "panel_end_date"])[:10] == days[-4]
    assert any("coin0" in message and "panel end" in message for message in caplog.messages)


def test_ended_feeds_do_not_count_against_daily_coverage(tmp_path):
    """Two of ten feeds ended 41 days before the window end (a migration or a
    delisting). Counting them in the coverage denominator put every later
    date at 8/10 < 90%, so the panel end froze on their last print and 41
    fully covered dates were dropped."""
    days = _span("2024-04-01", 90)
    config = _config(tmp_path, start=days[0], end=days[-1])
    raw_dir = tmp_path / "data" / "raw"
    _ten_coin_universe(raw_dir, days, last_day_by_coin={8: days[-42], 9: days[-42]})

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert panel["date"].max() == pd.Timestamp(days[-1])
    ended = panel[panel["coin_id"].isin({"coin8", "coin9"})]
    assert ended["date"].max() == pd.Timestamp(days[-42]), "ended feeds keep their history"
    assert panel[panel["date"] == pd.Timestamp(days[-1])]["coin_id"].nunique() == 8


def _write_cmc_presupply(
    raw_dir: Path,
    cmc_id: int,
    days: list[str],
    *,
    price_by_day: dict[str, float],
    supply_from: str,
) -> None:
    """Write a CMC history whose early rows carry no circulating supply."""
    directory = raw_dir / "coinmarketcap" / "history"
    directory.mkdir(parents=True, exist_ok=True)
    start = int(pd.Timestamp(days[0]).timestamp())
    end = int(pd.Timestamp(days[-1]).timestamp())
    payload = []
    for d in days:
        has_supply = d >= supply_from
        payload.append(
            {
                "timeOpen": f"{d}T00:00:00.000Z",
                "quote": {
                    "close": price_by_day[d],
                    "volume": 9_000_000.0,
                    # CMC reports 0 (not null) when it has no supply data.
                    "marketCap": 5_000_000.0 if has_supply else 0.0,
                    "circulatingSupply": 20_000.0 if has_supply else 0.0,
                },
            }
        )
    (directory / f"{cmc_id}_{start}_{end}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_rows_before_first_circulating_supply_are_dropped(tmp_path):
    """A coin cannot be ranked before its supply exists, so its price rows from
    that period are uninvestable - and it is exactly where CMC's data is worst.

    TAO is the motivating case: its first print is $0.126 against a $79.79
    next-week median, a 696x artificial jump. SHIB's first print is 4x its
    neighbours. Both sit before the provider reports any supply.
    """
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("tao", "TAO", 7))
    days = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]
    prices = {"2024-01-01": 0.126, "2024-01-02": 79.0, "2024-01-03": 80.0, "2024-01-04": 81.0}
    _write_cmc_presupply(raw_dir, 7, days, price_by_day=prices, supply_from="2024-01-03")

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert list(panel["date"].dt.strftime("%Y-%m-%d")) == ["2024-01-03", "2024-01-04"]
    assert panel["price"].min() == 80.0, "the broken placeholder print must be gone"


def test_launch_rally_is_kept_when_supply_exists_from_day_one(tmp_path):
    """A low first price is not automatically an error: PEPE really did start
    around 1.87e-10 and rally ~375x in five days."""
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("pepe", "PEPE", 9))
    days = ["2024-01-01", "2024-01-02", "2024-01-03"]
    prices = {"2024-01-01": 1.87e-10, "2024-01-02": 7.0e-08, "2024-01-03": 2.0e-07}
    _write_cmc(raw_dir, 9, days)
    # rewrite with an explicit launch price curve
    _write_cmc_presupply(raw_dir, 9, days, price_by_day=prices, supply_from="2024-01-01")

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert len(panel) == 3
    assert panel["price"].iloc[0] == 1.87e-10


def test_price_level_corruption_block_is_dropped(tmp_path):
    """Huobi Token was served at ~$0.000002 instead of ~$0.5 for 34 straight
    days in early 2025, then snapped back. Each row is internally consistent
    (market_cap == price x supply), so only the level shift reveals it."""
    days = pd.date_range("2024-06-01", periods=200, freq="D")
    config = _config(tmp_path, start="2024-06-01", end=days[-1].strftime("%Y-%m-%d"))
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("huobi-token", "HT", 3))
    prices = {d.strftime("%Y-%m-%d"): 0.5 for d in days}
    for d in days[100:130]:
        prices[d.strftime("%Y-%m-%d")] = 0.000002
    _write_cmc_presupply(
        raw_dir, 3, [d.strftime("%Y-%m-%d") for d in days], price_by_day=prices, supply_from="2024-06-01"
    )

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert (panel["price"] >= 0.1).all(), "the corrupted block must be gone"
    assert len(panel) < len(days), "corrupted rows are dropped, not repaired"


def _round_trip(days: pd.DatetimeIndex, *, level: float, block_level: float) -> dict[str, float]:
    """A 30-day block at ``block_level`` in the middle of a flat series."""
    prices = {d.strftime("%Y-%m-%d"): level for d in days}
    for d in days[100:130]:
        prices[d.strftime("%Y-%m-%d")] = block_level
    return prices


def test_level_corruption_drop_is_reported(tmp_path, caplog):
    """The drop used to be silent: 34 Huobi Token rows vanished with no log
    line and no data-quality field. With no independent print for those days
    the rule still drops them, but visibly."""
    days = pd.date_range("2024-06-01", periods=200, freq="D")
    config = _config(tmp_path, start="2024-06-01", end=days[-1].strftime("%Y-%m-%d"))
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("huobi-token", "HT", 3))
    prices = _round_trip(days, level=0.5, block_level=0.000002)
    _write_cmc_presupply(raw_dir, 3, list(prices), price_by_day=prices, supply_from="2024-06-01")

    with caplog.at_level("WARNING", logger="atlas20.data.processor"):
        panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert len(panel) == len(days) - 30
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    assert quality.loc["huobi-token", "level_corruption_rows"] == 30
    assert quality.loc["huobi-token", "level_corruption_dates"] == "2024-09-09..2024-10-08"
    block = f"{days[100].date()}..{days[129].date()}"
    assert any("huobi-token" in message and block in message for message in caplog.messages)


def test_genuine_twenty_x_round_trip_confirmed_by_a_venue_is_kept(tmp_path):
    """A real 25x round trip looks exactly like a level corruption to the
    ring test. Deleting it would erase the move and leave the asset carried at
    a stale price, so rows an exchange venue confirms are kept."""
    days = pd.date_range("2024-06-01", periods=200, freq="D")
    config = _config(tmp_path, start="2024-06-01", end=days[-1].strftime("%Y-%m-%d"))
    raw_dir = tmp_path / "data" / "raw"
    candidate = _candidate("squeeze", "SQZ", 9)
    candidate["gateio_pair"] = "SQZ_USDT"
    _write_candidates(raw_dir, candidate)
    prices = _round_trip(days, level=0.5, block_level=12.5)
    _write_cmc_presupply(raw_dir, 9, list(prices), price_by_day=prices, supply_from="2024-06-01")
    _write_gateio(raw_dir, "SQZ", list(prices), price_by_day=prices)

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert len(panel) == len(days), "a venue-confirmed move is data, not corruption"
    assert panel["price"].max() == 12.5
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    assert quality.loc["squeeze", "level_corruption_rows"] == 0
    assert quality.loc["squeeze", "level_corruption_confirmed_rows"] == 30


def test_level_corruption_a_venue_disputes_is_dropped(tmp_path):
    days = pd.date_range("2024-06-01", periods=200, freq="D")
    config = _config(tmp_path, start="2024-06-01", end=days[-1].strftime("%Y-%m-%d"))
    raw_dir = tmp_path / "data" / "raw"
    candidate = _candidate("huobi-token", "HT", 3)
    candidate["gateio_pair"] = "HT_USDT"
    _write_candidates(raw_dir, candidate)
    prices = _round_trip(days, level=0.5, block_level=0.000002)
    _write_cmc_presupply(raw_dir, 3, list(prices), price_by_day=prices, supply_from="2024-06-01")
    _write_gateio(raw_dir, "HT", list(prices), price=0.5)

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert len(panel) == len(days) - 30
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    assert quality.loc["huobi-token", "level_corruption_rows"] == 30
    assert quality.loc["huobi-token", "level_corruption_confirmed_rows"] == 0


def test_genuine_launch_rally_is_not_flagged(tmp_path):
    """A coin with no prior history cannot be judged against a surrounding
    level, so an explosive first week must survive."""
    days = pd.date_range("2023-04-14", periods=40, freq="D")
    config = _config(tmp_path, start="2023-04-14", end=days[-1].strftime("%Y-%m-%d"))
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("pepe", "PEPE", 5))
    prices = {d.strftime("%Y-%m-%d"): 1.87e-10 * (1.35 ** i) for i, d in enumerate(days)}
    _write_cmc_presupply(
        raw_dir, 5, [d.strftime("%Y-%m-%d") for d in days], price_by_day=prices, supply_from="2023-04-14"
    )

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert len(panel) == len(days)
    assert panel["price"].iloc[0] == 1.87e-10


def _write_cmc_window(
    raw_dir: Path,
    cmc_id: int,
    name: str,
    closes: dict[str, float],
    *,
    fetched_at: float,
) -> Path:
    """Write one cached CMC window whose file time records when it was fetched."""
    directory = raw_dir / "coinmarketcap" / "history"
    directory.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "timeOpen": f"{day}T00:00:00.000Z",
            "quote": {
                "close": close,
                "volume": 9_000_000.0,
                "marketCap": close * 20_000.0,
                "circulatingSupply": 20_000.0,
            },
        }
        for day, close in closes.items()
    ]
    path = directory / f"{cmc_id}_{name}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    os.utime(path, (fetched_at, fetched_at))
    return path


def test_newest_cmc_fetch_wins_every_duplicated_date(tmp_path, caplog):
    """Overlapping cache windows must resolve to the newest fetch.

    The loader concatenated the files in name order and then called an
    unstable ``sort_values("date")``, so ``keep="last")`` kept whichever copy
    the sort happened to leave last: on this revised history the new value
    survived on some dates and the stale one on the rest. A forced full
    re-download is the newest fetch although its name (the earliest start
    epoch) sorts first, so name order is not fetch order either. A copy that
    disagrees with a newer fetch of the same day is a provider revision and
    has to be reported, not silently resolved.
    """
    days = [d.strftime("%Y-%m-%d") for d in pd.date_range("2024-01-01", periods=398, freq="D")]
    config = _config(tmp_path, start=days[0], end=days[-1])
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1))
    _write_cmc_window(raw_dir, 1, "1704153600_1738368000", {d: 100.0 for d in days}, fetched_at=1_700_000_000)
    _write_cmc_window(raw_dir, 1, "1577836800_1738368000", {d: 200.0 for d in days}, fetched_at=1_800_000_000)

    with caplog.at_level("WARNING", logger="atlas20.data.processor"):
        panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert set(panel["price"]) == {200.0}, "the newest fetch must win on every duplicated date"
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    assert quality.loc["bitcoin", "cmc_duplicate_dates"] == len(days)
    assert quality.loc["bitcoin", "cmc_conflicting_duplicate_dates"] == len(days)
    assert any("conflict between cached fetches" in message for message in caplog.messages)


def test_agreeing_cmc_duplicates_are_counted_but_not_conflicts(tmp_path):
    days = [d.strftime("%Y-%m-%d") for d in pd.date_range("2024-01-01", periods=10, freq="D")]
    config = _config(tmp_path, start=days[0], end=days[-1])
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1))
    _write_cmc_window(raw_dir, 1, "a", {d: 100.0 for d in days}, fetched_at=1_700_000_000)
    _write_cmc_window(raw_dir, 1, "b", {d: 100.0 for d in days[-3:]}, fetched_at=1_800_000_000)

    processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    assert quality.loc["bitcoin", "cmc_duplicate_dates"] == 3
    assert quality.loc["bitcoin", "cmc_conflicting_duplicate_dates"] == 0


def _write_paprika(
    raw_dir: Path,
    coinpaprika_id: str,
    days: list[str],
    *,
    price: float = 250.0,
    price_by_day: dict[str, float] | None = None,
) -> None:
    directory = raw_dir / "coinpaprika" / "history"
    directory.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "timestamp": f"{day}T00:00:00Z",
            "price": (price_by_day or {}).get(day, price),
            "volume_24h": 9_000_000.0,
            "market_cap": 5_000_000.0,
        }
        for day in days
    ]
    (directory / f"{coinpaprika_id}_2024-01-01_2024-01-03.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )



def _write_gateio(
    raw_dir: Path,
    symbol: str,
    days: list[str],
    *,
    price: float = 250.0,
    price_by_day: dict[str, float] | None = None,
) -> None:
    directory = raw_dir / "gateio" / "candles"
    directory.mkdir(parents=True, exist_ok=True)
    payload = [
        [
            int(pd.Timestamp(day).timestamp()),
            9_000_000.0,
            (price_by_day or {}).get(day, price),
            (price_by_day or {}).get(day, price),
            (price_by_day or {}).get(day, price),
            (price_by_day or {}).get(day, price),
            20_000.0,
            "true",
        ]
        for day in days
    ]
    (directory / f"{symbol.upper()}_USDT_400.json").write_text(json.dumps(payload), encoding="utf-8")


def _write_binance(
    raw_dir: Path,
    symbol: str,
    days: list[str],
    *,
    price: float = 250.0,
    price_by_day: dict[str, float] | None = None,
) -> None:
    """Write a cached Binance kline window (quote volume above the floor)."""
    directory = raw_dir / "binance" / "candles"
    directory.mkdir(parents=True, exist_ok=True)
    rows = []
    for day in days:
        close = (price_by_day or {}).get(day, price)
        opened = int(pd.Timestamp(day).timestamp() * 1000)
        rows.append([opened, close, close, close, close, 1_000.0, opened + 86_399_999, 5_000_000.0, 100])
    (directory / f"{symbol.upper()}USDT_{days[0]}_{days[-1]}.json").write_text(json.dumps(rows), encoding="utf-8")


def test_one_passing_source_does_not_discard_the_others_disagreement(tmp_path):
    """CMC=250, Gate=Binance=100, CoinGecko=250 used to be admitted with
    CoinGecko as the confirming source and no tie-break: the first passing
    source won and both venues' disagreement was thrown away."""
    days = _span("2024-01-01", 40)
    config = _config(tmp_path, start=days[0], end=days[-1])
    raw_dir = tmp_path / "data" / "raw"
    bitcoin = _candidate("bitcoin", "BTC", 1)
    bitcoin["gateio_pair"] = "BTC_USDT"
    token = _candidate("sometoken", "SOME", 77)
    token["gateio_pair"] = "SOME_USDT"
    _write_candidates(raw_dir, bitcoin, token)
    _write_cmc(raw_dir, 1, days)
    _write_gateio(raw_dir, "BTC", days)
    _write_cmc(raw_dir, 77, days, price=250.0)
    _write_gateio(raw_dir, "SOME", days, price=100.0)
    _write_binance(raw_dir, "SOME", days, price=100.0)
    _write_chart(raw_dir, "sometoken", days, scale=1.0)

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert "sometoken" not in set(panel["coin_id"])
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    row = quality.loc["sometoken"]
    assert row["crosscheck_reason"] == "cmc_isolated"
    assert bool(row["crosscheck_third_source_checked"]) is True
    assert row["crosscheck_gateio_reason"] == "median_price_gap"
    assert row["crosscheck_binance_reason"] == "median_price_gap"
    assert row["crosscheck_coingecko_reason"] == "ok"
    assert pd.isna(row["crosscheck_coinpaprika_reason"])


def test_old_cmc_block_outside_the_coingecko_window_is_not_confirmed(tmp_path):
    """A 25-day 3.5x CMC block ~13 months back. Gate.io's 404-day window sees
    it; CoinGecko's 365-day chart starts after it and so passes. A pass from a
    source that never saw the disputed days is not a confirmation."""
    days = _span("2024-01-01", 404)
    config = _config(tmp_path, start=days[0], end=days[-1])
    config.data_quality.cross_check_min_overlap_days = 30
    raw_dir = tmp_path / "data" / "raw"
    bitcoin = _candidate("bitcoin", "BTC", 1)
    bitcoin["gateio_pair"] = "BTC_USDT"
    token = _candidate("sometoken", "SOME", 77)
    token["gateio_pair"] = "SOME_USDT"
    _write_candidates(raw_dir, bitcoin, token)
    _write_cmc(raw_dir, 1, days)
    _write_gateio(raw_dir, "BTC", days)
    closes = {day: (3.5 if 10 <= i < 35 else 1.0) for i, day in enumerate(days)}
    _write_cmc_presupply(raw_dir, 77, days, price_by_day=closes, supply_from=days[0])
    _write_gateio(raw_dir, "SOME", days, price=1.0)
    _write_chart_closes(raw_dir, "sometoken", {day: 1.0 for day in days[-365:]})

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert "sometoken" not in set(panel["coin_id"]), "the corrupted rows must not be admitted"
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    row = quality.loc["sometoken"]
    assert row["crosscheck_coingecko_reason"] == "ok"
    assert row["crosscheck_reason"] == "secondary_disagreement_unresolved"


def test_disagreement_is_blocked_even_when_verification_is_optional(tmp_path):
    """Gate.io proves a 2x level error on the last ten days; the only other
    source (CoinGecko) stopped before them. That used to be reported as an
    *unverified* reason, so ``require_cross_check=False`` admitted the asset.
    A proven disagreement blocks regardless of that switch."""
    days = _span("2024-01-01", 60)
    config = _config(tmp_path, start=days[0], end=days[-1])
    assert config.data_quality.require_cross_check is False
    raw_dir = tmp_path / "data" / "raw"
    bitcoin = _candidate("bitcoin", "BTC", 1)
    bitcoin["gateio_pair"] = "BTC_USDT"
    token = _candidate("sometoken", "SOME", 77)
    token["gateio_pair"] = "SOME_USDT"
    _write_candidates(raw_dir, bitcoin, token)
    _write_cmc(raw_dir, 1, days)
    _write_gateio(raw_dir, "BTC", days)
    closes = {day: (2.0 if i >= 50 else 1.0) for i, day in enumerate(days)}
    _write_cmc_presupply(raw_dir, 77, days, price_by_day=closes, supply_from=days[0])
    _write_gateio(raw_dir, "SOME", days, price=1.0)
    _write_chart_closes(raw_dir, "sometoken", {day: 1.0 for day in days[:45]})

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert "sometoken" not in set(panel["coin_id"])
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    row = quality.loc["sometoken"]
    assert bool(row["crosscheck_verified"]) is True
    assert row["crosscheck_reason"] == "secondary_disagreement_unresolved"

def _write_chart_closes(
    raw_dir: Path,
    coin_id: str,
    closes: dict[str, float],
    *,
    now_price: float | None = None,
    days_arg: int = 365,
) -> None:
    """Write a CoinGecko market chart the way the API really serves it.

    CoinGecko's daily point for day D is stamped 00:00 UTC of D+1 - it is the
    snapshot at the moment D closes - and the payload ends with an intraday
    "now" point. ``closes`` maps each day to its close; ``now_price`` adds the
    intraday point six and a half hours into the day after the last close.
    """
    path = raw_dir / "coingecko" / "market_chart" / f"{coin_id}_{days_arg}d.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    prices = [
        [int((pd.Timestamp(day) + pd.Timedelta(days=1)).timestamp() * 1000), value]
        for day, value in closes.items()
    ]
    if now_price is not None:
        last = max(pd.Timestamp(day) for day in closes)
        prices.append([int((last + pd.Timedelta(days=1, hours=6, minutes=30)).timestamp() * 1000), now_price])
    path.write_text(json.dumps({"prices": prices}), encoding="utf-8")


def _write_chart(raw_dir: Path, coin_id: str, days: list[str], scale: float = 1.0, days_arg: int = 365) -> None:
    """Write a CoinGecko validation chart whose closes are ``scale`` x the CMC price."""
    _write_chart_closes(raw_dir, coin_id, {d: 250.0 * scale for d in days}, days_arg=days_arg)


def test_second_source_disagreement_blocks_the_asset(tmp_path):
    """A proven disagreement with an independent provider is fatal."""
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(
        raw_dir,
        _candidate("bitcoin", "BTC", 1),
        _candidate("celsius-degree-token", "CEL", 4),
    )
    days = _days()
    _write_cmc(raw_dir, 1, days)
    _write_cmc(raw_dir, 4, days)
    _write_chart(raw_dir, "bitcoin", days, scale=1.0)
    _write_chart(raw_dir, "celsius-degree-token", days, scale=0.001)  # 1000x apart

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert set(panel["coin_id"]) == {"bitcoin"}, "the 1000x disagreement must be refused"
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    assert bool(quality.loc["celsius-degree-token", "crosscheck_passed"]) is False
    assert bool(quality.loc["celsius-degree-token", "included_in_panel"]) is False


def test_missing_second_source_is_unverified_not_rejected(tmp_path):
    """A CoinGecko outage must degrade to 'unverified', not an empty pipeline."""
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1))
    _write_cmc(raw_dir, 1, _days())

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert len(panel) == 3
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    assert len(quality) == 1
    assert bool(quality.loc["bitcoin", "included_in_panel"]) is True


def test_require_cross_check_refuses_unverified_assets(tmp_path):
    config = _config(tmp_path)
    config.data_quality.require_cross_check = True
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1))
    _write_cmc(raw_dir, 1, _days())

    try:
        processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))
    except ValueError:
        pass
    else:
        raise AssertionError("require_cross_check must refuse an unverified asset")


def test_coingecko_midnight_snapshot_is_compared_with_the_previous_cmc_close(tmp_path):
    """CoinGecko's 00:00 UTC point for day D is D-1's close.

    Labelled as D it was compared with CMC's close for D, so every CMC-vs-
    CoinGecko check ran one day out of phase: on real data the median gap was
    2.61% as coded and 0.079% once shifted back a day. A market that moves
    20% a day makes the one-day slip a 20% "disagreement" that blocks a
    perfectly healthy asset. The trailing intraday "now" point is a partial
    day and must not become a close either.
    """
    days = [d.strftime("%Y-%m-%d") for d in pd.date_range("2024-01-01", periods=40, freq="D")]
    config = _config(tmp_path, start=days[0], end=days[-1])
    config.data_quality.require_cross_check = True
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("monero", "XMR", 328))
    closes = {day: 100.0 * (1.2 ** i) for i, day in enumerate(days)}
    _write_cmc_presupply(raw_dir, 328, days, price_by_day=closes, supply_from=days[0])
    _write_chart_closes(raw_dir, "monero", closes, now_price=1e-6)

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert set(panel["coin_id"]) == {"monero"}
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    row = quality.loc["monero"]
    assert row["crosscheck_reason"] == "ok"
    assert row["crosscheck_confirmed_by"] == "coingecko"
    assert row["crosscheck_median_gap"] < 1e-9
    assert str(row["crosscheck_secondary_latest_date"])[:10] == days[-1]


def test_agreeing_second_source_admits_the_asset(tmp_path):
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1))
    days = _days()
    _write_cmc(raw_dir, 1, days)
    _write_chart(raw_dir, "bitcoin", days, scale=1.0)

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert len(panel) == 3
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    assert bool(quality.loc["bitcoin", "crosscheck_passed"]) is True


def test_third_source_can_confirm_cmc_when_second_source_is_outlier(tmp_path):
    """CoinGecko disagrees by 1000x, but CoinPaprika fully agrees with CMC.
    The third provider breaks the tie in CMC's favour."""
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(
        raw_dir,
        _candidate("bitcoin", "BTC", 1),
        _candidate("celsius-degree-token", "CEL", 4, "cel-celsius"),
    )
    days = _days()
    _write_cmc(raw_dir, 1, days)
    _write_cmc(raw_dir, 4, days)
    _write_chart(raw_dir, "bitcoin", days, scale=1.0)
    _write_chart(raw_dir, "celsius-degree-token", days, scale=0.001)
    _write_paprika(raw_dir, "cel-celsius", days)

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert set(panel["coin_id"]) == {"bitcoin", "celsius-degree-token"}
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    row = quality.loc["celsius-degree-token"]
    assert bool(row["crosscheck_passed"]) is True
    assert row["crosscheck_reason"] == "third_source_confirms_cmc"
    assert row["crosscheck_confirmed_by"] == "coinpaprika"


def test_two_providers_agree_against_cmc_and_block_it(tmp_path):
    """CEL-like case where both independent providers agree with each other
    and CMC is the isolated 1000x outlier."""
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(
        raw_dir,
        _candidate("bitcoin", "BTC", 1),
        _candidate("celsius-degree-token", "CEL", 4, "cel-celsius"),
    )
    days = _days()
    _write_cmc(raw_dir, 1, days)
    _write_cmc(raw_dir, 4, days)
    _write_chart(raw_dir, "bitcoin", days, scale=1.0)
    _write_chart(raw_dir, "celsius-degree-token", days, scale=0.001)
    _write_paprika(raw_dir, "cel-celsius", days, price=0.25)

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert set(panel["coin_id"]) == {"bitcoin"}
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    row = quality.loc["celsius-degree-token"]
    assert bool(row["crosscheck_passed"]) is False
    assert row["crosscheck_reason"] == "cmc_isolated"
    assert bool(row["included_in_panel"]) is False


def test_huobi_like_third_source_disagreement_keeps_asset_blocked(tmp_path):
    """A similar median is not enough: the third provider's latest print must
    also pass the full test before it can overrule the second provider."""
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(
        raw_dir,
        _candidate("bitcoin", "BTC", 1),
        _candidate("huobi-token", "HT", 3, "ht-huobi-token"),
    )
    days = _days()
    _write_cmc(raw_dir, 1, days)
    _write_cmc(raw_dir, 3, days)
    _write_chart(raw_dir, "bitcoin", days, scale=1.0)
    _write_chart(raw_dir, "huobi-token", days, scale=1.3)
    _write_paprika(
        raw_dir,
        "ht-huobi-token",
        days,
        price_by_day={days[-1]: 25.0},
    )

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert "huobi-token" not in set(panel["coin_id"])
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    assert quality.loc["huobi-token", "crosscheck_reason"] == "two_providers_disagree"
    assert bool(quality.loc["huobi-token", "included_in_panel"]) is False


def test_gateio_confirms_cmc_and_admits_asset(tmp_path):
    """CoinGecko is 1000x off and Gate.io agrees with CMC. CoinGecko's
    disagreement is no longer discarded because Gate.io passed first: it is
    adjudicated, and Gate.io settles it on every disputed day."""
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    candidate = _candidate("bitcoin", "BTC", 1)
    candidate["gateio_pair"] = "BTC_USDT"
    _write_candidates(raw_dir, candidate)
    days = _days()
    _write_cmc(raw_dir, 1, days)
    _write_chart(raw_dir, "bitcoin", days, scale=0.001)
    _write_gateio(raw_dir, "BTC", days)

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert "bitcoin" in set(panel["coin_id"])
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    assert quality.loc["bitcoin", "crosscheck_reason"] == "third_source_confirms_cmc"
    assert quality.loc["bitcoin", "crosscheck_secondary_source"] == "coingecko"
    assert quality.loc["bitcoin", "crosscheck_third_source"] == "gateio"
    assert quality.loc["bitcoin", "crosscheck_confirmed_by"] == "gateio"
    assert quality.loc["bitcoin", "crosscheck_coingecko_reason"] == "median_price_gap"


def test_gateio_is_primary_crosscheck_source_when_it_agrees(tmp_path):
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    candidate = _candidate("bitcoin", "BTC", 1)
    candidate["gateio_pair"] = "BTC_USDT"
    _write_candidates(raw_dir, candidate)
    days = _days()
    _write_cmc(raw_dir, 1, days)
    _write_gateio(raw_dir, "BTC", days)

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert "bitcoin" in set(panel["coin_id"])
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    row = quality.loc["bitcoin"]
    assert bool(row["crosscheck_passed"]) is True
    assert row["crosscheck_reason"] == "ok"
    assert row["crosscheck_confirmed_by"] == "gateio"
    assert bool(row["crosscheck_third_source_checked"]) is False


def test_gateio_disagreement_uses_coinpaprika_as_tertiary_vote(tmp_path):
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    candidate = _candidate("celsius-degree-token", "CEL", 4, "cel-celsius")
    candidate["gateio_pair"] = "CEL_USDT"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1), candidate)
    days = _days()
    _write_cmc(raw_dir, 1, days)
    _write_gateio(raw_dir, "BTC", days)
    _write_cmc(raw_dir, 4, days)
    _write_gateio(raw_dir, "CEL", days, price=0.25)
    _write_paprika(raw_dir, "cel-celsius", days, price=0.25)

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert set(panel["coin_id"]) == {"bitcoin"}
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    row = quality.loc["celsius-degree-token"]
    assert bool(row["crosscheck_passed"]) is False
    assert row["crosscheck_reason"] == "cmc_isolated"
    assert row["crosscheck_third_source"] == "coinpaprika"
    assert bool(row["included_in_panel"]) is False


def test_gateio_latest_disagreement_keeps_huobi_like_asset_blocked(tmp_path):
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    candidate = _candidate("huobi-token", "HT", 3)
    candidate["gateio_pair"] = "HT_USDT"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1), candidate)
    days = _days()
    _write_cmc(raw_dir, 1, days)
    _write_cmc(raw_dir, 3, days)
    _write_chart(raw_dir, "bitcoin", days, scale=1.0)
    _write_chart(raw_dir, "huobi-token", days, scale=1.3)
    _write_gateio(raw_dir, "HT", days, price_by_day={days[-1]: 25.0})

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert "huobi-token" not in set(panel["coin_id"])
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    assert quality.loc["huobi-token", "crosscheck_reason"] == "two_providers_disagree"
    assert bool(quality.loc["huobi-token", "included_in_panel"]) is False


def _span(start: str, periods: int) -> list[str]:
    return [d.strftime("%Y-%m-%d") for d in pd.date_range(start, periods=periods, freq="D")]


def test_venue_block_below_the_aggregator_gaps_blocks_the_asset(tmp_path):
    """A 16-day 2.9x CMC block passed every aggregator tolerance (3x share,
    5x catastrophic) against a correctly aligned exchange venue, so the asset
    was admitted with the bad rows. Gate.io is a venue: the block is a proven
    disagreement and nothing else covers those days, so it stays blocked."""
    days = _span("2024-01-01", 120)
    config = _config(tmp_path, start=days[0], end=days[-1])
    config.data_quality.cross_check_min_overlap_days = 30
    raw_dir = tmp_path / "data" / "raw"
    bitcoin = _candidate("bitcoin", "BTC", 1)
    bitcoin["gateio_pair"] = "BTC_USDT"
    kaspa = _candidate("kaspa", "KAS", 20396)
    kaspa["gateio_pair"] = "KAS_USDT"
    _write_candidates(raw_dir, bitcoin, kaspa)
    _write_cmc(raw_dir, 1, days)
    _write_gateio(raw_dir, "BTC", days)
    closes = {day: (2.9 if 60 <= i < 76 else 1.0) for i, day in enumerate(days)}
    _write_cmc_presupply(raw_dir, 20396, days, price_by_day=closes, supply_from=days[0])
    _write_gateio(raw_dir, "KAS", days, price=1.0)

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert set(panel["coin_id"]) == {"bitcoin"}
    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    row = quality.loc["kaspa"]
    assert bool(row["included_in_panel"]) is False
    assert bool(row["crosscheck_verified"]) is True, "a proven disagreement, not a missing source"
    assert row["crosscheck_gateio_reason"] == "venue_sustained_disagreement"


def test_download_prefers_gateio_and_avoids_coingecko_chart_when_listed(tmp_path, monkeypatch):
    config = _config(tmp_path)
    calls = {"gate": 0, "chart": 0}

    class _FakeCoinGecko:
        def __init__(self, *_args, **_kwargs):
            pass

        def fetch_top_markets(self, per_page, force=False):
            return pd.DataFrame(
                [
                    {
                        "id": "bitcoin",
                        "symbol": "btc",
                        "name": "Bitcoin",
                        "market_cap": 1_000_000.0,
                        "market_cap_rank": 1,
                        "current_price": 250.0,
                        "total_volume": 9_000_000.0,
                    }
                ]
            )

        def fetch_markets_by_ids(self, coin_ids, force=False):
            return pd.DataFrame()

        def fetch_coin_metadata(self, coin_id, force=False):
            return {}

        def fetch_daily_market_chart(self, coin_id, days, force=False):
            calls["chart"] += 1
            raise AssertionError("CoinGecko chart must not be requested when Gate.io lists the asset")

    class _FakeCMC:
        def __init__(self, *_args, **_kwargs):
            pass

        def fetch_id_map(self, *, force=False, max_pages=6):
            return {"BTC": 1}

        def ensure_history(self, coin_id, *, start, end, force=False):
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(_days()),
                    "close": [250.0] * 3,
                    "volume_usd": [9_000_000.0] * 3,
                    "market_cap": [5_000_000.0] * 3,
                    "circulating_supply": [20_000.0] * 3,
                }
            )

    class _FakeGateIO:
        def __init__(self, *_args, **_kwargs):
            pass

        def fetch_daily_candles(self, symbol, force=False, start=None, end=None):
            # The venue window is anchored to the asset's own last print, so
            # the client is always asked for an explicit window.
            assert start is not None and end is not None
            calls["gate"] += 1
            return pd.DataFrame(
                {
                    "date": pd.to_datetime(_days()),
                    "gate_price": [250.0] * 3,
                    "gate_volume_usd": [9_000_000.0] * 3,
                }
            )

        def resolve_pair(self, symbol):
            return f"{symbol.upper()}_USDT"

    class _FakeCoinPaprika:
        def __init__(self, *_args, **_kwargs):
            pass

    monkeypatch.setattr(processor, "CoinGeckoClient", _FakeCoinGecko)
    monkeypatch.setattr(processor, "CoinPaprikaClient", _FakeCoinPaprika)
    monkeypatch.setattr(processor, "CoinMarketCapClient", _FakeCMC)
    monkeypatch.setattr(processor, "GateIOClient", _FakeGateIO)
    monkeypatch.setattr(processor, "CoinPaprikaClient", _FakeCoinPaprika)

    processor.download_and_cache_raw_data(config)

    assert calls == {"gate": 1, "chart": 0}
    candidates = json.loads(
        (tmp_path / "data" / "raw" / "coingecko" / "candidate_assets.json").read_text(encoding="utf-8")
    )
    assert candidates[0]["gateio_pair"] == "BTC_USDT"


def test_stale_second_source_blocks_asset_when_crosscheck_is_required(tmp_path):
    config = _config(tmp_path)
    config.data_quality.require_cross_check = True
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1))
    days = _days()
    _write_cmc(raw_dir, 1, days)
    # Two days overlap and agree, but the independent source stops before the
    # latest primary print. That is an unverified current price, not a pass.
    _write_chart(raw_dir, "bitcoin", days[:-1], scale=1.0)

    with pytest.raises(ValueError, match="No processed panel rows"):
        processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))


def test_transient_cmc_tail_error_keeps_backfilled_candidate(tmp_path, monkeypatch):
    """A provider 500 on a tail refresh must not delete a usable history.

    This is the IMX failure mode: CMC had a complete cached series, the tail
    request failed once, and the old code rewrote candidate_assets.json without
    IMX. The next panel then silently lost a real point-in-time Top-20 member.
    """
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    days = _days()
    _write_candidates(raw_dir, _candidate("immutable-x", "IMX", 10603))
    _write_cmc(raw_dir, 10603, days)

    class _FakeCoinGecko:
        def __init__(self, *_args, **_kwargs): pass
        def fetch_top_markets(self, per_page, force=False): return pd.DataFrame()
        def fetch_markets_by_ids(self, coin_ids, force=False): return pd.DataFrame()
        def fetch_coin_metadata(self, coin_id, force=False): return {}
        def fetch_daily_market_chart(self, coin_id, days, force=False):
            return pd.DataFrame(columns=["date", "cg_price"])

    class _FakeCMC:
        def __init__(self, *_args, **_kwargs): pass
        def fetch_id_map(self, *, force=False, max_pages=6): return {"IMX": 10603}
        def ensure_history(self, coin_id, *, start, end, force=False):
            raise RuntimeError("temporary 500")
        def cached_history(self, coin_id):
            return pd.DataFrame({
                "date": pd.to_datetime(days),
                "close": [250.0] * 3,
                "volume_usd": [9_000_000.0] * 3,
                "market_cap": [5_000_000.0] * 3,
                "circulating_supply": [20_000.0] * 3,
            })
        def has_backfill(self, coin_id, *, start): return True

    class _FakeGate:
        def __init__(self, *_args, **_kwargs): pass
        def resolve_pair(self, symbol): return f"{symbol.upper()}_USDT"
        def fetch_daily_candles(self, symbol, *, start=None, end=None, force=False):
            return pd.DataFrame({
                "date": pd.to_datetime(days),
                "gate_price": [250.0] * 3,
                "gate_volume_usd": [9_000_000.0] * 3,
            })

    class _FakeBinance:
        def __init__(self, *_args, **_kwargs): pass
        def resolve_pair(self, symbol): return f"{symbol.upper()}USDT"
        def fetch_daily_candles(self, symbol, *, start=None, end=None, force=False):
            return pd.DataFrame(columns=["date", "binance_price", "binance_volume_usd"])

    class _FakeCoinPaprika:
        def __init__(self, *_args, **_kwargs): pass

    monkeypatch.setattr(processor, "CoinGeckoClient", _FakeCoinGecko)
    monkeypatch.setattr(processor, "CoinMarketCapClient", _FakeCMC)
    monkeypatch.setattr(processor, "GateIOClient", _FakeGate)
    monkeypatch.setattr(processor, "BinanceClient", _FakeBinance)
    monkeypatch.setattr(processor, "CoinPaprikaClient", _FakeCoinPaprika)

    assets = processor.download_and_cache_raw_data(config)

    assert len(assets) == 1
    assert assets.iloc[0]["id"] == "immutable-x"
    assert "history_fetch_warning" in assets.columns
    candidates = json.loads(
        (raw_dir / "coingecko" / "candidate_assets.json").read_text(encoding="utf-8")
    )
    assert [row["id"] for row in candidates] == ["immutable-x"]


def test_quality_records_latest_primary_verification(tmp_path):
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1))
    days = _days()
    _write_cmc(raw_dir, 1, days)
    _write_chart(raw_dir, "bitcoin", days, scale=1.0)

    processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    row = quality.loc["bitcoin"]
    assert bool(row["crosscheck_latest_primary_covered"]) is True
    assert str(row["crosscheck_primary_latest_date"])[:10] == days[-1]


def test_ended_feed_anchors_the_venue_window_to_its_own_series(tmp_path, monkeypatch):
    """A delisted pair has no candles in the trailing 400 days.

    MATIC's provider series stops on 2025-03-24, when the token migrated to
    POL. Asking a venue for "the last 400 days from today" returns nothing, so
    the asset would be refused as unverified - the venue window has to follow
    the asset's own series instead, and the cross-check has to verify the
    overlap rather than a print that will never arrive.
    """
    config = _config(tmp_path, start="2024-01-01", end="2026-09-21")
    config.data_quality.require_cross_check = True
    config.universe.min_history_days = 2
    raw_dir = tmp_path / "data" / "raw"
    days = pd.date_range("2024-01-01", "2025-03-24", freq="D")
    _write_cmc(raw_dir, 3890, [d.strftime("%Y-%m-%d") for d in days])
    _write_candidates(raw_dir, _candidate("matic-network", "MATIC", 3890))

    seen: dict[str, object] = {}

    class _FakeCoinGecko:
        def __init__(self, *_args, **_kwargs): pass
        def fetch_top_markets(self, per_page, force=False): return pd.DataFrame()
        def fetch_markets_by_ids(self, coin_ids, force=False): return pd.DataFrame()
        def fetch_coin_metadata(self, coin_id, force=False): return {}

    class _FakeCoinPaprika:
        def __init__(self, *_args, **_kwargs): pass

    class _FakeCMC:
        def __init__(self, *_args, **_kwargs): pass
        def fetch_id_map(self, *, force=False, max_pages=6): return {}
        def ensure_history(self, coin_id, *, start, end, force=False):
            return pd.DataFrame({
                "date": days,
                "close": [0.5] * len(days),
                "volume_usd": [9_000_000.0] * len(days),
                "market_cap": [5_000_000_000.0] * len(days),
                "circulating_supply": [1e10] * len(days),
            })

    class _FakeGate:
        def __init__(self, *_args, **_kwargs): pass
        def resolve_pair(self, symbol): return f"{symbol.upper()}_USDT"
        def fetch_daily_candles(self, symbol, *, limit=400, start=None, end=None, force=False):
            seen["gate_window"] = (start, end)
            return pd.DataFrame(columns=["date", "gate_price", "gate_volume_usd"])

    class _FakeBinance:
        def __init__(self, *_args, **_kwargs): pass
        def resolve_pair(self, symbol): return f"{symbol.upper()}USDT"
        def fetch_daily_candles(self, symbol, *, start=None, end=None, force=False):
            seen["binance_window"] = (start, end)
            # The venue delisted the pair before the provider stopped printing.
            venue_days = pd.date_range(start, min(pd.Timestamp(end), pd.Timestamp("2024-09-10")), freq="D")
            return pd.DataFrame({
                "date": venue_days,
                "binance_price": [0.5] * len(venue_days),
                "binance_volume_usd": [5_000_000.0] * len(venue_days),
            })

    monkeypatch.setattr(processor, "CoinGeckoClient", _FakeCoinGecko)
    monkeypatch.setattr(processor, "CoinPaprikaClient", _FakeCoinPaprika)
    monkeypatch.setattr(processor, "CoinMarketCapClient", _FakeCMC)
    monkeypatch.setattr(processor, "GateIOClient", _FakeGate)
    monkeypatch.setattr(processor, "BinanceClient", _FakeBinance)

    assets = processor.download_and_cache_raw_data(config)

    assert len(assets) == 1, "an ended feed must not be dropped for lack of a venue window"
    start, end = seen["binance_window"]
    assert pd.Timestamp(end) == pd.Timestamp("2025-03-24"), "the venue window must end at the last print"
    assert pd.Timestamp(start) == days[0], "an ended series is verified over its whole length"


def test_panel_refresh_refuses_to_drop_existing_asset(tmp_path):
    """A transient provider failure must not silently shrink the panel."""
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    path = processed / "panel_daily.csv"
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "coin_id": ["bitcoin", "ethereum"],
        }
    ).to_csv(path, index=False)

    degraded = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "coin_id": ["bitcoin", "bitcoin"],
        }
    )

    with pytest.raises(RuntimeError, match="refusing to overwrite"):
        processor._guard_panel_regression(path, degraded)


def test_panel_refresh_allows_config_excluded_asset_to_disappear(tmp_path):
    """An operator exclusion in the config is intended, not a provider failure."""
    path = tmp_path / "panel_daily.csv"
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-01"]),
            "coin_id": ["bitcoin", "rain"],
        }
    ).to_csv(path, index=False)
    refreshed = pd.DataFrame({"date": pd.to_datetime(["2024-01-01"]), "coin_id": ["bitcoin"]})

    processor._guard_panel_regression(path, refreshed, intended_exclusions={"rain"})


def test_panel_refresh_still_refuses_unexpected_drop_next_to_config_exclusion(tmp_path):
    path = tmp_path / "panel_daily.csv"
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01"] * 3),
            "coin_id": ["bitcoin", "ethereum", "rain"],
        }
    ).to_csv(path, index=False)
    refreshed = pd.DataFrame({"date": pd.to_datetime(["2024-01-01"]), "coin_id": ["bitcoin"]})

    with pytest.raises(RuntimeError, match="ethereum") as excinfo:
        processor._guard_panel_regression(path, refreshed, intended_exclusions={"rain"})
    assert "rain" not in str(excinfo.value)


def test_build_lets_config_excluded_asset_leave_existing_panel(tmp_path):
    """Adding an id to universe.excluded_ids must not wedge the daily refresh."""
    config = _config(tmp_path)
    config.universe.excluded_ids = [*config.universe.excluded_ids, "retired-coin"]
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1))
    _write_cmc(raw_dir, 1, _days())
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    pd.DataFrame(
        {
            "date": pd.to_datetime(_days() * 2),
            "coin_id": ["bitcoin"] * 3 + ["retired-coin"] * 3,
        }
    ).to_csv(processed / "panel_daily.csv", index=False)

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert set(panel["coin_id"]) == {"bitcoin"}
    assert set(pd.read_csv(processed / "panel_daily.csv")["coin_id"]) == {"bitcoin"}


def test_panel_refresh_refuses_to_move_end_date_backwards(tmp_path):
    path = tmp_path / "panel_daily.csv"
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-03"]),
            "coin_id": ["bitcoin", "bitcoin"],
        }
    ).to_csv(path, index=False)
    stale = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-02"]),
            "coin_id": ["bitcoin", "bitcoin"],
        }
    )

    with pytest.raises(RuntimeError, match="backwards"):
        processor._guard_panel_regression(path, stale)


def test_panel_refresh_refuses_to_truncate_history_start(tmp_path):
    path = tmp_path / "panel_daily.csv"
    pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01", "2024-01-03"]),
            "coin_id": ["bitcoin", "bitcoin"],
        }
    ).to_csv(path, index=False)
    truncated = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "coin_id": ["bitcoin", "bitcoin"],
        }
    )

    with pytest.raises(RuntimeError, match="start date"):
        processor._guard_panel_regression(path, truncated)


def test_persist_false_does_not_overwrite_canonical_panel(tmp_path):
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1))
    _write_cmc(raw_dir, 1, _days())
    processed = tmp_path / "data" / "processed"
    processed.mkdir(parents=True)
    path = processed / "panel_daily.csv"
    path.write_text("sentinel\n", encoding="utf-8")

    panel, _ = processor.build_processed_datasets(
        config,
        load_sector_config("config/sectors.yaml"),
        persist=False,
    )

    assert not panel.empty
    assert path.read_text(encoding="utf-8") == "sentinel\n"


def test_pre_window_buffer_covers_every_configured_lookback(tmp_path):
    """The buffer was ``min_history_days`` (90) while the regime uses
    120-day moving averages, so regime_frame.csv showed bull=False on
    2021-01-01..01-29 purely from MA warm-up - raw CMC BTC was above its
    120-day average on every one of those days."""
    config = _config(tmp_path, start="2021-01-01", end="2021-01-10")
    assert config.universe.min_history_days == 90
    assert config.regime.btc_ma_window == 120
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1))
    _write_cmc(raw_dir, 1, _span("2020-06-01", 224))

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert panel["date"].min() == pd.Timestamp("2021-01-01") - pd.Timedelta(days=120)


def test_pre_window_buffer_is_derived_from_config(tmp_path):
    config = _config(tmp_path, start="2021-01-01", end="2021-01-10")
    config.regime.btc_ma_window = 150
    config.signals.momentum_windows = {30: 0.5, 60: 0.3, 200: 0.2}
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1))
    _write_cmc(raw_dir, 1, _span("2020-01-01", 376))

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert panel["date"].min() == pd.Timestamp("2021-01-01") - pd.Timedelta(days=200)


def _write_id_map(raw_dir: Path, mapping: dict[str, int]) -> None:
    path = raw_dir / "coinmarketcap" / "id_map.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping), encoding="utf-8")


def test_alias_contradicting_the_id_map_fails_the_build(tmp_path):
    """``CEL: 5692`` pointed Celsius at Compound's CMC id: the id map assigns
    5692 to COMP, so both candidates read Compound's history and Celsius was
    reported as a steady ~988x "CMC outlier" instead of a mapping error."""
    config = _config(tmp_path)
    config.universe.cmc_symbol_aliases = {"CEL": 5692}
    raw_dir = tmp_path / "data" / "raw"
    _write_id_map(raw_dir, {"BTC": 1, "COMP": 5692})
    _write_candidates(
        raw_dir,
        _candidate("bitcoin", "BTC", 1),
        _candidate("compound-governance-token", "COMP", 5692),
        _candidate("celsius-degree-token", "CEL", 5692),
    )
    _write_cmc(raw_dir, 1, _days())
    _write_cmc(raw_dir, 5692, _days())

    with pytest.raises(ValueError, match=r"CEL.*5692.*COMP"):
        processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))


def test_two_candidates_on_one_cmc_id_fail_the_build(tmp_path):
    config = _config(tmp_path)
    raw_dir = tmp_path / "data" / "raw"
    _write_candidates(raw_dir, _candidate("bitcoin", "BTC", 1), _candidate("bitcoin-clone", "BTCC", 1))
    _write_cmc(raw_dir, 1, _days())

    with pytest.raises(ValueError, match=r"cmc_id 1.*bitcoin.*bitcoin-clone"):
        processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))


def test_candidate_whose_symbol_no_longer_resolves_is_skipped(tmp_path):
    """The build resolves CMC ids exactly like the download does - config
    aliases over the cached id map - so removing a bad alias takes effect
    without waiting for a download to rewrite the candidate cache."""
    config = _config(tmp_path)
    config.universe.cmc_symbol_aliases = {}
    raw_dir = tmp_path / "data" / "raw"
    _write_id_map(raw_dir, {"BTC": 1, "COMP": 5692})
    _write_candidates(
        raw_dir,
        _candidate("bitcoin", "BTC", 1),
        _candidate("compound-governance-token", "COMP", 5692),
        _candidate("celsius-degree-token", "CEL", 5692),
    )
    _write_cmc(raw_dir, 1, _days())
    _write_cmc(raw_dir, 5692, _days())

    panel, _ = processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    assert set(panel["coin_id"]) == {"bitcoin", "compound-governance-token"}


def test_download_refuses_an_alias_that_contradicts_the_id_map(tmp_path, monkeypatch):
    config = _config(tmp_path)
    config.universe.cmc_symbol_aliases = {"CEL": 5692}

    class _FakeCoinGecko:
        def __init__(self, *_args, **_kwargs): pass
        def fetch_top_markets(self, per_page, force=False): return pd.DataFrame()
        def fetch_markets_by_ids(self, coin_ids, force=False): return pd.DataFrame()

    class _FakeCMC:
        def __init__(self, *_args, **_kwargs): pass
        def fetch_id_map(self, *, force=False, max_pages=6): return {"COMP": 5692}

    class _Unused:
        def __init__(self, *_args, **_kwargs): pass

    monkeypatch.setattr(processor, "CoinGeckoClient", _FakeCoinGecko)
    monkeypatch.setattr(processor, "CoinMarketCapClient", _FakeCMC)
    for client in ("GateIOClient", "BinanceClient", "CoinPaprikaClient"):
        monkeypatch.setattr(processor, client, _Unused)

    with pytest.raises(ValueError, match=r"CEL.*5692.*COMP"):
        processor.download_and_cache_raw_data(config)


def test_config_carries_no_celsius_alias_and_excuses_celsius():
    """The cached id map has no CEL entry and no cached CMC series is
    Celsius, so there is no verified id to alias: the name is recorded as
    un-onboardable instead of being fed Compound's prices."""
    config = load_config("config/base.yaml")

    assert "CEL" not in {symbol.upper() for symbol in config.universe.cmc_symbol_aliases}
    assert "celsius-degree-token" in config.universe.legacy_unavailable
    assert "5692" in config.universe.legacy_unavailable["celsius-degree-token"]


def test_quality_reports_the_comparison_that_admitted_the_asset(tmp_path):
    """latest_price_gap, median_price_gap and price_correlation were hard-coded
    NaN (0 of 102 rows populated) although the API's data-quality alerts read
    them, and latest_overlap_date was really the last market-cap date."""
    days = _span("2024-01-01", 40)
    config = _config(tmp_path, start=days[0], end=days[-1])
    raw_dir = tmp_path / "data" / "raw"
    bitcoin = _candidate("bitcoin", "BTC", 1)
    bitcoin["gateio_pair"] = "BTC_USDT"
    _write_candidates(raw_dir, bitcoin)
    closes = {day: 100.0 * 1.01**i for i, day in enumerate(days)}
    directory = raw_dir / "coinmarketcap" / "history"
    directory.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "timeOpen": f"{day}T00:00:00.000Z",
            "quote": {
                "close": close,
                "volume": 9_000_000.0,
                # No supply for the newest three days: the last market-cap date
                # is three days before the last shared print.
                "marketCap": None if i >= len(days) - 3 else close * 20_000.0,
                "circulatingSupply": 20_000.0,
            },
        }
        for i, (day, close) in enumerate(closes.items())
    ]
    (directory / "1_0_1.json").write_text(json.dumps(payload), encoding="utf-8")
    venue = {day: close * 1.002 for day, close in closes.items()}
    venue[days[-1]] = closes[days[-1]] * 1.01
    _write_gateio(raw_dir, "BTC", days, price_by_day=venue)

    processor.build_processed_datasets(config, load_sector_config("config/sectors.yaml"))

    quality = pd.read_csv(tmp_path / "data" / "processed" / "data_quality.csv").set_index("coin_id")
    row = quality.loc["bitcoin"]
    assert row["crosscheck_confirmed_by"] == "gateio"
    assert row["latest_price_gap"] == pytest.approx(0.01)
    assert row["median_price_gap"] == pytest.approx(0.002)
    assert row["price_correlation"] > 0.999
    assert str(row["latest_overlap_date"])[:10] == days[-1]
    assert str(row["latest_market_cap_date"])[:10] == days[-4]
    metadata = pd.read_csv(tmp_path / "data" / "processed" / "metadata.csv").set_index("coin_id")
    assert metadata.loc["bitcoin", "latest_price_gap"] == pytest.approx(0.01)


def test_download_fetches_a_tie_break_when_the_venue_test_fails(tmp_path, monkeypatch):
    """The build now fails Gate.io on the venue block test, so the download
    must apply the same test when it decides whether a tie-break chart is
    needed - otherwise the build has no vote to settle the dispute with."""
    days = _span("2024-01-01", 120)
    config = _config(tmp_path, start=days[0], end=days[-1])
    config.data_quality.cross_check_min_overlap_days = 30
    calls = {"chart": 0}
    closes = [2.9 if 60 <= i < 76 else 1.0 for i in range(len(days))]

    class _FakeCoinGecko:
        def __init__(self, *_args, **_kwargs): pass
        def fetch_top_markets(self, per_page, force=False):
            return pd.DataFrame([{"id": "kaspa", "symbol": "kas", "name": "Kaspa", "market_cap": 1e9, "market_cap_rank": 20}])
        def fetch_markets_by_ids(self, coin_ids, force=False): return pd.DataFrame()
        def fetch_coin_metadata(self, coin_id, force=False): return {}
        def fetch_daily_market_chart(self, coin_id, days_arg, force=False):
            calls["chart"] += 1
            return pd.DataFrame({"date": pd.to_datetime(days), "cg_price": [1.0] * len(days)})

    class _FakeCMC:
        def __init__(self, *_args, **_kwargs): pass
        def fetch_id_map(self, *, force=False, max_pages=6): return {"KAS": 20396}
        def ensure_history(self, coin_id, *, start, end, force=False):
            return pd.DataFrame({
                "date": pd.to_datetime(days), "close": closes, "volume_usd": [9e6] * len(days),
                "market_cap": [1e9] * len(days), "circulating_supply": [1e9] * len(days),
            })

    class _FakeGateIO:
        def __init__(self, *_args, **_kwargs): pass
        def resolve_pair(self, symbol): return f"{symbol.upper()}_USDT"
        def fetch_daily_candles(self, symbol, force=False, start=None, end=None):
            return pd.DataFrame({"date": pd.to_datetime(days), "gate_price": [1.0] * len(days), "gate_volume_usd": [9e6] * len(days)})

    class _FakeBinance:
        def __init__(self, *_args, **_kwargs): pass
        def fetch_daily_candles(self, symbol, *, start=None, end=None, force=False): return pd.DataFrame()

    class _FakeCoinPaprika:
        def __init__(self, *_args, **_kwargs): pass

    monkeypatch.setattr(processor, "CoinGeckoClient", _FakeCoinGecko)
    monkeypatch.setattr(processor, "CoinMarketCapClient", _FakeCMC)
    monkeypatch.setattr(processor, "GateIOClient", _FakeGateIO)
    monkeypatch.setattr(processor, "BinanceClient", _FakeBinance)
    monkeypatch.setattr(processor, "CoinPaprikaClient", _FakeCoinPaprika)

    processor.download_and_cache_raw_data(config)

    assert calls["chart"] == 1, "a venue-test failure needs the tie-break chart"


def test_market_cap_end_trims_the_price_only_tail() -> None:
    """EOS/MKR keep printing a legacy price after CMC stops publishing supply.

    Those rows can never be ranked, and comparing the legacy ticker with the
    migrated token makes the independent-source check fail. The feed is ended
    at its last real market cap instead.
    """
    days = pd.date_range("2025-05-01", periods=12, freq="D")
    history = pd.DataFrame(
        {
            "date": days,
            "price": [1.0] * len(days),
            "volume_usd": [10.0] * len(days),
            "market_cap": [100.0] * 4 + [float("nan")] * 8,
        }
    )

    trimmed, ended = processor._trim_market_cap_ended(history)

    assert ended is True
    assert trimmed["date"].max() == days[3]


def test_market_cap_short_tail_is_not_treated_as_ended() -> None:
    days = pd.date_range("2025-05-01", periods=8, freq="D")
    history = pd.DataFrame(
        {
            "date": days,
            "price": [1.0] * len(days),
            "volume_usd": [10.0] * len(days),
            "market_cap": [100.0] * 4 + [float("nan")] * 4,
        }
    )

    trimmed, ended = processor._trim_market_cap_ended(history)

    assert ended is False
    assert trimmed["date"].max() == days[-1]
