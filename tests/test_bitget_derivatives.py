from __future__ import annotations

import json
import pandas as pd
import pytest
from atlas20.derivatives.bitget import BitgetClient, candle_frame, funding_frame
from atlas20.derivatives.mapping import build_symbol_map
from scripts.audit_bitget_derivatives_data import funding_overlap


class _FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.text = json.dumps(payload)

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self) -> object:
        return self._payload


def _client(session: object) -> BitgetClient:
    return BitgetClient(
        session=session,  # type: ignore[arg-type]
        rate_limit_seconds=0.0,
        retry_backoff_seconds=0.0,
        max_retries=1,
    )


def _row(stamp: str, close: float = 100.0) -> list[object]:
    millis = int(pd.Timestamp(stamp, tz="UTC").timestamp() * 1000)
    return [millis, "99", "101", "98", str(close), "1", "100"]


def test_candle_frame_parses_positional_payload() -> None:
    frame = candle_frame([_row("2026-01-01T00:00:00Z"), _row("2026-01-01T01:00:00Z", 101.0)])

    assert list(frame.columns) == ["open_time", "open", "high", "low", "close", "volume", "quote_volume"]
    assert frame["close"].tolist() == [100.0, 101.0]
    assert frame["open_time"].dt.tz is not None


def test_funding_frame_parses_v3_result_list() -> None:
    frame = funding_frame(
        [
            {"symbol": "BTCUSDT", "fundingRate": "0.0001", "fundingRateTimestamp": "1791504000000"},
            {"symbol": "BTCUSDT", "fundingRate": "-0.0002", "fundingRateTimestamp": "1791475200000"},
        ]
    )

    assert len(frame) == 2
    assert frame["funding_rate"].tolist() == [-0.0002, 0.0001]
    assert frame["funding_time"].is_monotonic_increasing


def test_fetch_history_candles_pages_backwards_from_end_time() -> None:
    calls: list[dict[str, object]] = []

    class _Session:
        def get(self, url, params, timeout):
            del url, timeout
            calls.append(dict(params))
            if len(calls) == 1:
                return _FakeResponse({"code": "00000", "data": [_row("2026-01-01T01:00:00Z")]})
            return _FakeResponse({"code": "00000", "data": []})

    client = _client(_Session())
    frame = client.fetch_history_candles(
        "BTCUSDT",
        "mark",
        "2026-01-01T00:00:00Z",
        "2026-01-01T02:00:00Z",
    )

    assert len(frame) == 1
    assert len(calls) == 2
    assert calls[0]["startTime"] == int(pd.Timestamp("2026-01-01T00:00:00Z").timestamp() * 1000)
    assert calls[0]["endTime"] == int(pd.Timestamp("2026-01-01T02:00:00Z").timestamp() * 1000)
    assert calls[1]["endTime"] == int(pd.Timestamp("2026-01-01T01:00:00Z").timestamp() * 1000)


def test_fetch_funding_history_paginates() -> None:
    calls: list[int] = []

    class _Session:
        def get(self, url, params, timeout):
            del url, timeout
            page = int(params["pageNo"])
            calls.append(page)
            if page == 1:
                return _FakeResponse(
                    {
                        "code": "00000",
                        "data": {
                            "resultList": [
                                {"symbol": "BTCUSDT", "fundingRate": "0.0001", "fundingRateTimestamp": "1791504000000"},
                                {"symbol": "BTCUSDT", "fundingRate": "0.0001", "fundingRateTimestamp": "1791475200000"},
                            ]
                        },
                    }
                )
            if page == 2:
                return _FakeResponse(
                    {
                        "code": "00000",
                        "data": {
                            "resultList": [
                                {"symbol": "BTCUSDT", "fundingRate": "0.0002", "fundingRateTimestamp": "1791446400000"}
                            ]
                        },
                    }
                )
            return _FakeResponse({"code": "00000", "data": {"resultList": []}})

    client = _client(_Session())
    frame = client.fetch_funding_history("BTCUSDT", page_size=2, max_pages=5)

    assert len(frame) == 3
    assert calls == [1, 2, 3]


def test_build_symbol_map_handles_rebrand_and_missing_contract() -> None:
    panel = pd.DataFrame(
        {
            "coin_id": ["matic-network", "okb", "bitcoin"],
            "symbol": ["MATIC", "OKB", "BTC"],
        }
    )
    contracts = [
        {"symbol": "POLUSDT", "baseCoin": "POL", "quoteCoin": "USDT", "symbolType": "perpetual", "symbolStatus": "normal"},
        {"symbol": "BTCUSDT", "baseCoin": "BTC", "quoteCoin": "USDT", "symbolType": "perpetual", "symbolStatus": "normal"},
    ]

    mapping = build_symbol_map(panel, contracts).set_index("coin_id")

    assert mapping.loc["matic-network", "bitget_symbol"] == "POLUSDT"
    assert mapping.loc["matic-network", "reason"] == "alias:POL"
    assert mapping.loc["bitcoin", "bitget_symbol"] == "BTCUSDT"
    assert mapping.loc["okb", "contract_status"] == "missing"


def test_funding_overlap_passes_on_close_series() -> None:
    times = pd.date_range("2026-07-01", periods=40, freq="8h", tz="UTC")
    bitget = pd.DataFrame({"funding_time": times, "funding_rate": [0.0001] * 40})
    binance = pd.DataFrame({"funding_time": times, "funding_rate": [0.0001] * 40})

    result = funding_overlap(bitget, binance)

    assert result["passed"] is True
    assert result["overlap_rows"] == 40
    assert result["sign_agreement"] == pytest.approx(1.0)
    assert result["median_abs_error_bps"] == pytest.approx(0.0)


def test_funding_overlap_fails_on_sign_disagreement() -> None:
    times = pd.date_range("2026-07-01", periods=40, freq="8h", tz="UTC")
    bitget = pd.DataFrame({"funding_time": times, "funding_rate": [-0.0001] * 40})
    binance = pd.DataFrame({"funding_time": times, "funding_rate": [0.0001] * 40})

    result = funding_overlap(bitget, binance)

    assert result["passed"] is False
    assert result["sign_agreement"] == pytest.approx(0.0)


def test_fetch_history_candles_does_not_drop_the_page_boundary_hour() -> None:
    class _Session:
        def get(self, url, params, timeout):
            del url, timeout
            start = pd.to_datetime(params["startTime"], unit="ms", utc=True)
            end = pd.to_datetime(params["endTime"], unit="ms", utc=True)
            hours = pd.date_range(start, end, freq="h", inclusive="left")
            page = hours[-100:]
            return _FakeResponse(
                {
                    "code": "00000",
                    "data": [_row(str(stamp)) for stamp in page],
                }
            )

    client = _client(_Session())
    start = pd.Timestamp("2026-01-01T00:00:00Z")
    end = start + pd.Timedelta(hours=101)

    frame = client.fetch_history_candles("BTCUSDT", "mark", start, end)

    assert len(frame) == 101
    assert frame["open_time"].iloc[0] == start
    assert frame["open_time"].iloc[-1] == end - pd.Timedelta(hours=1)


def test_window_status_marks_page_gaps_as_partial() -> None:
    from scripts.download_bitget_derivatives_data import _window_status

    start = pd.Timestamp("2026-01-01T00:00:00Z")
    end = start + pd.Timedelta(hours=4)
    full = candle_frame([_row(str(start + pd.Timedelta(hours=i))) for i in range(4)])
    gapped = full.drop(full.index[2])

    assert _window_status(full, start, end) == ("complete", 4)
    assert _window_status(gapped, start, end) == ("partial", 4)
    assert _window_status(pd.DataFrame(), start, end) == ("missing", 4)


def test_window_status_requires_the_exact_hourly_grid_not_only_row_count() -> None:
    from scripts.download_bitget_derivatives_data import _window_status

    start = pd.Timestamp("2026-01-01T00:00:00Z")
    end = start + pd.Timedelta(hours=4)
    wrong_times = candle_frame(
        [
            _row(str(start)),
            _row(str(start + pd.Timedelta(hours=1))),
            _row(str(start + pd.Timedelta(hours=2))),
            _row(str(start + pd.Timedelta(hours=4))),
        ]
    )

    assert _window_status(wrong_times, start, end) == ("partial", 4)


def test_open_live_window_is_never_treated_as_cached_complete() -> None:
    from scripts.download_bitget_derivatives_data import _window_needs_refresh

    now = pd.Timestamp("2026-11-14T01:07:00Z")

    assert _window_needs_refresh(pd.Timestamp("2026-11-15T00:00:00Z"), now) is True
    assert _window_needs_refresh(pd.Timestamp("2026-11-14T00:00:00Z"), now) is False


def test_stale_cached_funding_is_refetched_and_history_is_merged(tmp_path) -> None:
    from scripts.download_bitget_derivatives_data import _download_funding

    class _FundingClient:
        def __init__(self) -> None:
            self.calls = 0

        def fetch_funding_history(self, symbol: str) -> pd.DataFrame:
            self.calls += 1
            assert symbol == "BTCUSDT"
            return pd.DataFrame(
                {
                    "symbol": [symbol],
                    "funding_time": [pd.Timestamp("2026-11-14T00:00:00Z")],
                    "funding_rate": [0.0002],
                }
            )

    output_dir = tmp_path
    funding_dir = output_dir / "funding"
    funding_dir.mkdir()
    pd.DataFrame(
        {
            "symbol": ["BTCUSDT"],
            "funding_time": [pd.Timestamp("2026-11-10T00:00:00Z")],
            "funding_rate": [0.0001],
        }
    ).to_csv(funding_dir / "bitcoin.csv", index=False)
    symbol_map = pd.DataFrame(
        [{"coin_id": "bitcoin", "bitget_symbol": "BTCUSDT", "fund_interval": 8}]
    )
    client = _FundingClient()

    manifest = _download_funding(  # type: ignore[arg-type]
        client,
        symbol_map,
        output_dir,
        force=False,
        now=pd.Timestamp("2026-11-14T01:05:00Z"),
    )

    assert client.calls == 1
    merged = pd.read_csv(funding_dir / "bitcoin.csv")
    assert len(merged) == 2
    assert merged["funding_time"].tolist() == [
        "2026-11-10 00:00:00+00:00",
        "2026-11-14 00:00:00+00:00",
    ]
    assert manifest["bitcoin"]["last"] == "2026-11-14 00:00:00+00:00"
