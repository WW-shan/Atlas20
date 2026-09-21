"""A coin that newly enters the Top-N must be fully onboarded in one run.

The candidate catalog is re-read on every refresh, but a newly discovered coin
has no cached history. It has to be backfilled to the full depth the momentum
signal needs before it can be scored - and an already-onboarded coin must not
be re-downloaded in full every single day.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from atlas20.config import CoinMarketCapConfig, load_config
from atlas20.data.coinmarketcap import CoinMarketCapClient


def _write_window(
    raw_dir: Path,
    cmc_id: int,
    start: str,
    end: str,
    days: int = 400,
    data_end: str | None = None,
) -> Path:
    """Write a cached window.

    ``end`` is what the filename records (the *requested* end); ``data_end``
    is the last date actually present in the payload. The two differ when a
    run fires before the provider has published the newest close.
    """
    directory = raw_dir / "coinmarketcap" / "history"
    directory.mkdir(parents=True, exist_ok=True)
    start_ts = int(pd.Timestamp(start).timestamp())
    end_ts = int(pd.Timestamp(end).timestamp())
    # A window payload runs *up to* its last available day, not forward
    # from it; a forward range would silently place rows in the future.
    dates = pd.date_range(end=pd.Timestamp(data_end or end), periods=days, freq="D")
    payload = [
        {
            "timeOpen": f"{d.date().isoformat()}T00:00:00.000Z",
            "quote": {"close": 10.0, "volume": 1000.0, "marketCap": 5000.0, "circulatingSupply": 500.0},
        }
        for d in dates
    ]
    path = directory / f"{cmc_id}_{start_ts}_{end_ts}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _client(raw_dir: Path) -> CoinMarketCapClient:
    return CoinMarketCapClient(CoinMarketCapConfig(), raw_dir)


def test_cached_coin_triggers_no_network_call(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    _write_window(raw_dir, 1, "2020-01-01", "2026-09-20")
    client = _client(raw_dir)

    def _boom(*args, **kwargs):
        raise AssertionError("a fully cached coin must not hit the network")

    monkeypatch.setattr(client, "fetch_history", _boom)

    frame = client.ensure_history(1, start="2020-01-01", end="2026-09-20")

    assert not frame.empty


def test_stale_cache_pulls_only_the_tail(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    _write_window(raw_dir, 1, "2020-01-01", "2026-09-10")
    client = _client(raw_dir)
    captured: dict[str, object] = {}

    def _fake_fetch(coin_id, *, start, end, force=False):
        captured["start"] = pd.Timestamp(start)
        captured["end"] = pd.Timestamp(end)
        return pd.DataFrame()

    monkeypatch.setattr(client, "fetch_history", _fake_fetch)

    client.ensure_history(1, start="2020-01-01", end="2026-09-20")

    assert captured["start"] > pd.Timestamp("2026-09-01"), "only the tail should be re-pulled"
    assert captured["start"] <= pd.Timestamp("2026-09-20")
    assert captured["end"] == pd.Timestamp("2026-09-20")


def test_window_marker_ahead_of_payload_is_re_pulled(tmp_path, monkeypatch):
    """A window filename records the *requested* end (today's midnight), but a
    run that fires before the provider publishes the newest close stores data
    only through the previous day. Coverage has to be judged on the payload,
    not the filename, or the cache silently freezes one day behind and every
    coin but the newly-onboarded ones goes stale."""
    raw_dir = tmp_path / "raw"
    _write_window(raw_dir, 1, "2020-01-01", "2026-09-21", data_end="2026-09-19")
    client = _client(raw_dir)
    captured: dict[str, object] = {}

    def _fake_fetch(coin_id, *, start, end, force=False):
        captured["start"] = pd.Timestamp(start)
        captured["end"] = pd.Timestamp(end)
        captured["force"] = force
        return pd.DataFrame()

    monkeypatch.setattr(client, "fetch_history", _fake_fetch)

    client.ensure_history(1, start="2020-01-01", end="2026-09-21")

    assert captured, "a payload lagging the last completed day must be re-pulled"
    assert captured["force"] is True, "the same-named tail window must be re-fetched, not read"
    assert captured["end"] == pd.Timestamp("2026-09-21")
    assert captured["start"] > pd.Timestamp("2026-09-01"), "only the tail should be re-pulled"


def test_new_entrant_is_backfilled_to_the_full_requested_depth(tmp_path, monkeypatch):
    """No cache at all: the coin must be pulled from the configured start."""
    raw_dir = tmp_path / "raw"
    client = _client(raw_dir)
    captured: dict[str, object] = {}

    def _fake_fetch(coin_id, *, start, end, force=False):
        captured["start"] = pd.Timestamp(start)
        captured["end"] = pd.Timestamp(end)
        return pd.DataFrame()

    monkeypatch.setattr(client, "fetch_history", _fake_fetch)

    client.ensure_history(42, start="2020-01-01", end="2026-09-20")

    assert captured["start"] == pd.Timestamp("2020-01-01")
    assert captured["end"] == pd.Timestamp("2026-09-20")


def test_shallow_cache_is_re_backfilled(tmp_path, monkeypatch):
    """A tail-only cache (e.g. one short window) must not masquerade as full
    coverage - the momentum lookback would silently be truncated."""
    raw_dir = tmp_path / "raw"
    _write_window(raw_dir, 7, "2026-08-01", "2026-09-20", days=50)
    client = _client(raw_dir)
    captured: dict[str, object] = {}

    def _fake_fetch(coin_id, *, start, end, force=False):
        captured["start"] = pd.Timestamp(start)
        return pd.DataFrame()

    monkeypatch.setattr(client, "fetch_history", _fake_fetch)

    client.ensure_history(7, start="2020-01-01", end="2026-09-20")

    assert captured["start"] == pd.Timestamp("2020-01-01")


def test_catalog_refresh_is_on_by_default(monkeypatch, tmp_path):
    """A change to the Top-N listing must be picked up without passing
    --refresh-raw; otherwise a coin entering the Top-20 is never discovered."""
    from atlas20.data import processor

    config = load_config("config/base.yaml")
    config.project_root = tmp_path
    calls: dict[str, object] = {}

    class _FakeCoinGecko:
        def __init__(self, *_a, **_k):
            pass

        def fetch_top_markets(self, per_page, force=False):
            calls["top_force"] = force
            return pd.DataFrame()

        def fetch_markets_by_ids(self, ids, force=False):
            return pd.DataFrame()

        def fetch_coin_metadata(self, coin_id, force=False):
            return {}

    class _FakeCMC:
        def __init__(self, *_a, **_k):
            pass

        def fetch_id_map(self, *, force=False, max_pages=6):
            calls["idmap_force"] = force
            return {}

    monkeypatch.setattr(processor, "CoinGeckoClient", _FakeCoinGecko)
    monkeypatch.setattr(processor, "CoinMarketCapClient", _FakeCMC)

    processor.download_and_cache_raw_data(config)

    assert calls["top_force"] is True, "top-N listing must be re-read on every refresh"
    assert calls["idmap_force"] is True, "the CMC id map must be re-read too"


def test_onboarded_candidates_never_leave_the_pool(monkeypatch, tmp_path):
    """A coin that slips out of CoinGecko's current listing must stay a
    candidate.

    The pool is otherwise rebuilt from the live listing on every refresh, so a
    coin that was inside the Top-20 while it was hot and has since fallen down
    the listing would leave the panel and take its historical rows with it.
    Because the panel is rebuilt from scratch each run, that retroactively
    rewrites the universe the backtest ran on.
    """
    from atlas20.data import processor

    config = load_config("config/base.yaml")
    config.project_root = tmp_path
    raw = tmp_path / "data" / "raw"
    (raw / "coingecko").mkdir(parents=True)
    (raw / "coingecko" / "candidate_assets.json").write_text(
        json.dumps([{"id": "retired-coin", "symbol": "OLD", "name": "Retired Coin", "cmc_id": 111}]),
        encoding="utf-8",
    )

    captured: dict[str, object] = {}

    def _capture(assets):
        captured["ids"] = [str(a["id"]) for a in assets]
        return []  # stop before screening so no provider fakes are needed

    class _FakeCoinGecko:
        def __init__(self, *_a, **_k):
            pass

        def fetch_top_markets(self, per_page, force=False):
            return pd.DataFrame([{"id": "fresh-coin", "symbol": "NEW", "name": "Fresh Coin"}])

        def fetch_markets_by_ids(self, ids, force=False):
            return pd.DataFrame()

    class _FakeCMC:
        def __init__(self, *_a, **_k):
            pass

        def fetch_id_map(self, *, force=False, max_pages=6):
            return {}

    monkeypatch.setattr(processor, "deduplicate_assets", _capture)
    monkeypatch.setattr(processor, "CoinGeckoClient", _FakeCoinGecko)
    monkeypatch.setattr(processor, "CoinMarketCapClient", _FakeCMC)

    processor.download_and_cache_raw_data(config)

    assert "retired-coin" in captured["ids"], "an onboarded coin must not be dropped from the pool"
    assert "fresh-coin" in captured["ids"]


def test_onboarded_candidates_are_recovered_from_metadata(tmp_path):
    """The metadata cache outlives a candidate list that was already
    overwritten, so a coin whose history we paid for is still recoverable."""
    from atlas20.data import processor

    config = load_config("config/base.yaml")
    config.project_root = tmp_path
    metadata_dir = tmp_path / "data" / "raw" / "coingecko" / "coin_metadata"
    metadata_dir.mkdir(parents=True)
    (metadata_dir / "retired-coin.json").write_text(
        json.dumps({"id": "retired-coin", "symbol": "old", "name": "Retired Coin", "market_cap_rank": 31}),
        encoding="utf-8",
    )
    (metadata_dir / "broken.json").write_text("{not json", encoding="utf-8")

    onboarded = processor._load_onboarded_candidates(config)

    assert [row["id"] for row in onboarded] == ["retired-coin"]


def test_id_map_refresh_is_additive(tmp_path, monkeypatch):
    """Rebranded coins fall off the current listing. A refresh must merge into
    the cached map rather than replace it, or EOS/MKR/FTM silently vanish."""
    raw_dir = tmp_path / "raw"
    path = raw_dir / "coinmarketcap" / "id_map.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"EOS": 1765, "MKR": 1518, "BTC": 1}), encoding="utf-8")
    client = _client(raw_dir)

    def _fake_listing(*, force=False, max_pages=6):
        # The live listing no longer carries the retired symbols.
        return {"BTC": 1, "ETH": 1027}

    monkeypatch.setattr(client, "_fetch_listing_pages", _fake_listing, raising=False)

    # Simulate the refresh by exercising the merge path directly.
    merged = client._merge_id_map({"EOS": 1765, "MKR": 1518, "BTC": 1}, {"BTC": 1, "ETH": 1027})

    assert merged["EOS"] == 1765
    assert merged["MKR"] == 1518
    assert merged["ETH"] == 1027
    assert merged["BTC"] == 1
