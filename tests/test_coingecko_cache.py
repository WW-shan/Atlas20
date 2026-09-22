"""CoinGecko fallback caches must not go stale indefinitely."""

from __future__ import annotations

import json
import os
import time

from atlas20.config import CoinGeckoConfig
from atlas20.data.coingecko import MARKET_CHART_CACHE_MAX_AGE_SECONDS, CoinGeckoClient


def test_stale_market_chart_cache_is_refreshed(tmp_path, monkeypatch) -> None:
    config = CoinGeckoConfig(
        rate_limit_seconds=0.0,
        max_retries=1,
        retry_backoff_seconds=0.0,
    )
    client = CoinGeckoClient(config, tmp_path)
    cache = client._cache_path("market_chart", "monero_365d.json")
    cache.write_text(
        json.dumps(
            {
                "prices": [[1_700_000_000_000, 100.0]],
                "market_caps": [[1_700_000_000_000, 1_000_000.0]],
                "total_volumes": [[1_700_000_000_000, 10_000.0]],
            }
        ),
        encoding="utf-8",
    )
    stale_mtime = time.time() - MARKET_CHART_CACHE_MAX_AGE_SECONDS - 60
    os.utime(cache, (stale_mtime, stale_mtime))

    class FakeResponse:
        ok = True

        @staticmethod
        def json():
            return {
                "prices": [[1_800_000_000_000, 200.0]],
                "market_caps": [[1_800_000_000_000, 2_000_000.0]],
                "total_volumes": [[1_800_000_000_000, 20_000.0]],
            }

    calls: list[str] = []

    def fake_get(url, params, timeout):
        calls.append(url)
        return FakeResponse()

    monkeypatch.setattr(client.session, "get", fake_get)

    frame = client.fetch_daily_market_chart("monero", 365)

    assert calls
    assert frame.iloc[-1]["cg_price"] == 200.0
    assert cache.stat().st_mtime > stale_mtime
