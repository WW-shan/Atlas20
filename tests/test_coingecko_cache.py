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
    # Daily points sit on 00:00 UTC; an off-midnight point is the intraday
    # "now" print and is not a close (see daily_closes_from_market_chart).
    cache = client._cache_path("market_chart", "monero_365d.json")
    cache.write_text(
        json.dumps(
            {
                "prices": [[1_699_920_000_000, 100.0]],
                "market_caps": [[1_699_920_000_000, 1_000_000.0]],
                "total_volumes": [[1_699_920_000_000, 10_000.0]],
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
                "prices": [[1_799_971_200_000, 200.0]],
                "market_caps": [[1_799_971_200_000, 2_000_000.0]],
                "total_volumes": [[1_799_971_200_000, 20_000.0]],
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


# 00:00 UTC on 2026-09-22/23/24 and CoinGecko's intraday "now" point.
_MIDNIGHT_22 = 1_790_035_200_000
_MIDNIGHT_23 = _MIDNIGHT_22 + 86_400_000
_MIDNIGHT_24 = _MIDNIGHT_23 + 86_400_000
_NOW_24 = _MIDNIGHT_24 + (6 * 3600 + 30 * 60 + 50) * 1000


def _xmr_payload() -> dict:
    """Real XMR prints: CoinGecko's 2026-09-22T00:00 point is 590.79, while
    CMC closes 2026-09-21 at 589.42 and 2026-09-22 at 573.51 - the midnight
    snapshot is the *previous* day's close."""
    prices = [[_MIDNIGHT_22, 590.79], [_MIDNIGHT_23, 573.95], [_MIDNIGHT_24, 553.38], [_NOW_24, 560.22]]
    return {
        "prices": prices,
        "market_caps": [[ts, value * 18e6] for ts, value in prices],
        "total_volumes": [[ts, 1e8] for ts, _ in prices],
    }


def test_market_chart_midnight_point_is_the_previous_day_close(tmp_path) -> None:
    import pandas as pd

    client = CoinGeckoClient(CoinGeckoConfig(rate_limit_seconds=0.0, max_retries=1), tmp_path)
    cache = client._cache_path("market_chart", "monero_365d.json")
    cache.write_text(json.dumps(_xmr_payload()), encoding="utf-8")

    frame = client.fetch_daily_market_chart("monero", 365)

    assert frame["date"].tolist() == list(pd.to_datetime(["2026-09-21", "2026-09-22", "2026-09-23"]))
    assert frame["cg_price"].tolist() == [590.79, 573.95, 553.38]
    # The intraday "now" point is a partial day, not a close: it never
    # overwrites or extends the daily series.
    assert 560.22 not in frame["cg_price"].tolist()
