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


def _write_window(raw_dir: Path, cmc_id: int, start: str, end: str, days: int = 400) -> Path:
    directory = raw_dir / "coinmarketcap" / "history"
    directory.mkdir(parents=True, exist_ok=True)
    start_ts = int(pd.Timestamp(start).timestamp())
    end_ts = int(pd.Timestamp(end).timestamp())
    dates = pd.date_range(end, periods=days, freq="D")
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
