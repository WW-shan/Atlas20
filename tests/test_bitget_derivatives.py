from __future__ import annotations

import hashlib
import json
import pandas as pd
import pytest
from atlas20.derivatives.bitget import (
    BitgetAPIError,
    BitgetClient,
    candle_frame,
    funding_frame,
)
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


def test_candle_frame_collapses_identical_duplicate_timestamps() -> None:
    row = _row("2026-01-01T00:00:00Z")

    frame = candle_frame([row, list(row)])

    assert len(frame) == 1
    assert frame.iloc[0]["close"] == 100.0


def test_candle_frame_rejects_conflicting_duplicate_timestamps() -> None:
    with pytest.raises(ValueError, match="conflicting duplicate"):
        candle_frame(
            [
                _row("2026-01-01T00:00:00Z", 100.0),
                _row("2026-01-01T00:00:00Z", 101.0),
            ]
        )


def test_candle_frame_rejects_non_finite_values() -> None:
    row = _row("2026-01-01T00:00:00Z")
    row[4] = "inf"

    with pytest.raises(BitgetAPIError, match="non-finite"):
        candle_frame([row])


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


def test_funding_frame_collapses_identical_duplicate_timestamps() -> None:
    row = {
        "symbol": "BTCUSDT",
        "fundingRate": "0.0001",
        "fundingRateTimestamp": "1791504000000",
    }

    frame = funding_frame([row, dict(row)])

    assert len(frame) == 1
    assert frame.iloc[0]["funding_rate"] == pytest.approx(0.0001)


def test_funding_frame_rejects_conflicting_duplicate_timestamps() -> None:
    first = {
        "symbol": "BTCUSDT",
        "fundingRate": "0.0001",
        "fundingRateTimestamp": "1791504000000",
    }
    conflicting = {**first, "fundingRate": "0.0002"}

    with pytest.raises(ValueError, match="conflicting duplicate"):
        funding_frame([first, conflicting])


def test_funding_frame_rejects_non_finite_rates() -> None:
    row = {
        "symbol": "BTCUSDT",
        "fundingRate": "inf",
        "fundingRateTimestamp": "1791504000000",
    }

    with pytest.raises(BitgetAPIError, match="finite"):
        funding_frame([row])


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


def test_client_retries_a_transient_read_timeout() -> None:
    import requests

    calls = 0

    class _Session:
        def get(self, url, params, timeout):
            nonlocal calls
            del url, params, timeout
            calls += 1
            if calls == 1:
                raise requests.ReadTimeout("transient handshake/read timeout")
            return _FakeResponse({"code": "00000", "data": []})

    client = BitgetClient(
        session=_Session(),  # type: ignore[arg-type]
        rate_limit_seconds=0.0,
        retry_backoff_seconds=0.0,
        max_retries=2,
    )

    assert client.fetch_contracts() == []
    assert calls == 2


def test_client_does_not_retry_an_unrelated_programming_error() -> None:
    calls = 0

    class _Session:
        def get(self, url, params, timeout):
            nonlocal calls
            del url, params, timeout
            calls += 1
            raise ValueError("bad request construction")

    client = BitgetClient(
        session=_Session(),  # type: ignore[arg-type]
        rate_limit_seconds=0.0,
        retry_backoff_seconds=0.0,
        max_retries=3,
    )

    with pytest.raises(ValueError, match="bad request construction"):
        client.fetch_contracts()

    assert calls == 1


def test_client_retries_a_timeout_wrapped_by_a_generic_os_error() -> None:
    calls = 0

    class _Session:
        def get(self, url, params, timeout):
            nonlocal calls
            del url, params, timeout
            calls += 1
            if calls == 1:
                raise OSError(
                    "HTTPSConnectionPool(host='api.bitget.com', port=443): "
                    "Read timed out. (read timeout=30.0)"
                )
            return _FakeResponse({"code": "00000", "data": []})

    client = BitgetClient(
        session=_Session(),  # type: ignore[arg-type]
        rate_limit_seconds=0.0,
        retry_backoff_seconds=0.0,
        max_retries=2,
    )

    assert client.fetch_contracts() == []
    assert calls == 2


def test_fetch_history_candles_rejects_a_malformed_data_shape() -> None:
    class _Session:
        def get(self, url, params, timeout):
            del url, params, timeout
            return _FakeResponse({"code": "00000", "data": {"unexpected": []}})

    client = _client(_Session())

    with pytest.raises(BitgetAPIError, match="candle data"):
        client.fetch_history_candles(
            "BTCUSDT",
            "mark",
            "2026-01-01T00:00:00Z",
            "2026-01-01T02:00:00Z",
        )


def test_fetch_funding_history_rejects_a_malformed_data_shape() -> None:
    class _Session:
        def get(self, url, params, timeout):
            del url, params, timeout
            return _FakeResponse({"code": "00000", "data": "oops"})

    client = _client(_Session())

    with pytest.raises(BitgetAPIError, match="funding data"):
        client.fetch_funding_history("BTCUSDT")


def test_fetch_funding_history_exposes_the_server_request_time() -> None:
    request_time = int(pd.Timestamp("2026-11-14T01:05:00Z").timestamp() * 1000)

    class _Session:
        def get(self, url, params, timeout):
            del url, timeout
            page = int(params["pageNo"])
            return _FakeResponse(
                {
                    "code": "00000",
                    "requestTime": request_time + page,
                    "data": {
                        "resultList": (
                            [
                                {
                                    "symbol": "BTCUSDT",
                                    "fundingRate": "0.0001",
                                    "fundingRateTimestamp": "1791504000000",
                                }
                            ]
                            if page == 1
                            else []
                        )
                    },
                }
            )

    client = _client(_Session())
    frame = client.fetch_funding_history("BTCUSDT", page_size=1, max_pages=3)

    assert frame.attrs["request_time_ms"] == request_time + 2
    assert frame.attrs["request_times_ms"] == [request_time + 1, request_time + 2]


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


def test_build_symbol_map_uses_the_latest_panel_row_regardless_of_file_order() -> None:
    panel = pd.DataFrame(
        {
            "date": ["2026-11-13", "2026-11-12"],
            "coin_id": ["the-open-network", "the-open-network"],
            "symbol": ["GRAM", "TON"],
            "name": ["Gram (prev. Toncoin)", "Toncoin"],
        }
    )
    contracts = [
        {
            "symbol": "GRAMUSDT",
            "baseCoin": "GRAM",
            "quoteCoin": "USDT",
            "symbolType": "perpetual",
            "symbolStatus": "normal",
        }
    ]

    mapping = build_symbol_map(panel, contracts).set_index("coin_id")

    assert mapping.loc["the-open-network", "panel_symbol"] == "GRAM"
    assert mapping.loc["the-open-network", "bitget_symbol"] == "GRAMUSDT"
    assert mapping.loc["the-open-network", "reason"] == "direct"


def test_build_symbol_map_uses_the_known_gram_rebrand_alias() -> None:
    panel = pd.DataFrame(
        {
            "date": ["2026-11-12"],
            "coin_id": ["the-open-network"],
            "symbol": ["TON"],
            "name": ["Toncoin"],
        }
    )
    contracts = [
        {
            "symbol": "GRAMUSDT",
            "baseCoin": "GRAM",
            "quoteCoin": "USDT",
            "symbolType": "perpetual",
            "symbolStatus": "normal",
        }
    ]

    mapping = build_symbol_map(panel, contracts).set_index("coin_id")

    assert mapping.loc["the-open-network", "bitget_symbol"] == "GRAMUSDT"
    assert mapping.loc["the-open-network", "reason"] == "alias:GRAM"


def test_build_symbol_map_treats_blank_panel_symbol_as_unmapped() -> None:
    panel = pd.DataFrame(
        {
            "coin_id": ["tron"],
            "symbol": [None],
        }
    )
    contracts = [
        {
            "symbol": "TRXUSDT",
            "baseCoin": "TRX",
            "quoteCoin": "USDT",
            "symbolType": "perpetual",
            "symbolStatus": "normal",
        }
    ]

    mapping = build_symbol_map(panel, contracts).set_index("coin_id")

    assert mapping.loc["tron", "bitget_symbol"] == ""
    assert mapping.loc["tron", "contract_status"] == "missing"


@pytest.mark.parametrize(
    "contract",
    [
        {
            "symbol": "TRXUSDT_261225",
            "baseCoin": "TRX",
            "quoteCoin": "USDT",
            "symbolType": "delivery",
            "symbolStatus": "normal",
        },
        {
            "symbol": "TRXUSDC",
            "baseCoin": "TRX",
            "quoteCoin": "USDC",
            "symbolType": "perpetual",
            "symbolStatus": "normal",
        },
        {
            "symbol": "TRXUSDT",
            "baseCoin": "TRX",
            "quoteCoin": "USDT",
            "symbolType": "perpetual",
            "symbolStatus": "offline",
        },
    ],
)
def test_build_symbol_map_requires_a_normal_usdt_perpetual(contract) -> None:
    panel = pd.DataFrame({"coin_id": ["tron"], "symbol": ["TRX"]})

    mapping = build_symbol_map(panel, [contract]).set_index("coin_id")

    assert mapping.loc["tron", "bitget_symbol"] == ""
    assert mapping.loc["tron", "contract_status"] == "missing"
    assert mapping.loc["tron", "reason"] == "no Bitget USDT-M perpetual"


def test_build_symbol_map_skips_an_ineligible_direct_base_before_alias_fallback() -> None:
    panel = pd.DataFrame(
        {
            "date": ["2026-11-15"],
            "coin_id": ["matic-network"],
            "symbol": ["MATIC"],
        }
    )
    contracts = [
        {
            "symbol": "MATICUSDC",
            "baseCoin": "MATIC",
            "quoteCoin": "USDC",
            "symbolType": "perpetual",
            "symbolStatus": "normal",
            "openTime": "1700000000000",
        },
        {
            "symbol": "POLUSDT",
            "baseCoin": "POL",
            "quoteCoin": "USDT",
            "symbolType": "perpetual",
            "symbolStatus": "normal",
            "openTime": "1690000000000",
        },
    ]

    mapping = build_symbol_map(panel, contracts).set_index("coin_id")

    assert mapping.loc["matic-network", "bitget_symbol"] == "POLUSDT"
    assert mapping.loc["matic-network", "contract_status"] == "normal"
    assert mapping.loc["matic-network", "reason"] == "alias:POL"


def test_build_symbol_map_uses_a_normal_alias_when_the_direct_contract_is_offline() -> None:
    panel = pd.DataFrame(
        {
            "date": ["2026-11-15"],
            "coin_id": ["matic-network"],
            "symbol": ["MATIC"],
        }
    )
    contracts = [
        {
            "symbol": "MATICUSDT",
            "baseCoin": "MATIC",
            "quoteCoin": "USDT",
            "symbolType": "perpetual",
            "symbolStatus": "offline",
        },
        {
            "symbol": "POLUSDT",
            "baseCoin": "POL",
            "quoteCoin": "USDT",
            "symbolType": "perpetual",
            "symbolStatus": "normal",
        },
    ]

    mapping = build_symbol_map(panel, contracts).set_index("coin_id")

    assert mapping.loc["matic-network", "bitget_symbol"] == "POLUSDT"
    assert mapping.loc["matic-network", "contract_status"] == "normal"
    assert mapping.loc["matic-network", "reason"] == "alias:POL"


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


def test_candle_merge_rejects_conflicting_duplicate_values() -> None:
    from scripts.download_bitget_derivatives_data import _merge_candles

    existing = candle_frame([_row("2026-01-01T00:00:00Z", 100.0)])
    refreshed = candle_frame([_row("2026-01-01T00:00:00Z", 101.0)])

    with pytest.raises(ValueError, match="conflicting duplicate"):
        _merge_candles(existing, refreshed)


def test_candle_merge_accepts_a_decimal_equivalent_float_round_trip() -> None:
    from scripts.download_bitget_derivatives_data import _merge_candles

    cached = _row("2025-10-10T22:00:00Z")
    cached[6] = "10168712.597007012"
    refreshed = list(cached)
    refreshed[6] = "10168712.597007013"

    merged = _merge_candles(candle_frame([cached]), candle_frame([refreshed]))

    assert len(merged) == 1
    assert merged.iloc[0]["quote_volume"] == pytest.approx(10168712.597007013)


def test_candle_merge_collapses_identical_duplicate_values() -> None:
    from scripts.download_bitget_derivatives_data import _merge_candles

    first = candle_frame([_row("2026-01-01T00:00:00Z", 100.0)])
    duplicate = first.copy()

    merged = _merge_candles(first, duplicate)

    assert len(merged) == 1


def test_candle_merge_rejects_an_invalid_cached_timestamp() -> None:
    from scripts.download_bitget_derivatives_data import _merge_candles

    invalid = pd.DataFrame(
        [
            {
                "open_time": "not-a-timestamp",
                "open": 100.0,
                "high": 101.0,
                "low": 99.0,
                "close": 100.5,
                "volume": 1.0,
                "quote_volume": 100.0,
            }
        ]
    )

    with pytest.raises(ValueError, match="open_time"):
        _merge_candles(invalid, pd.DataFrame())


def test_cached_page_boundary_gap_is_refetched_not_treated_as_final() -> None:
    from scripts.download_bitget_derivatives_data import _cached_window_needs_refetch

    assert _cached_window_needs_refetch("complete", "partial") is True
    assert _cached_window_needs_refetch("partial", "partial") is True
    assert _cached_window_needs_refetch("complete", "missing") is True
    assert _cached_window_needs_refetch("complete", "complete") is False
    assert _cached_window_needs_refetch("missing", "missing") is False


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


def test_partial_funding_refresh_preserves_other_manifest_entries(tmp_path) -> None:
    from scripts.download_bitget_derivatives_data import _download_funding

    class _FundingClient:
        def fetch_funding_history(self, symbol: str) -> pd.DataFrame:
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
    (output_dir / "funding_manifest.json").write_text(
        json.dumps(
            {
                "bitcoin": {"symbol": "BTCUSDT", "last": "2026-11-10T00:00:00Z"},
                "ethereum": {"symbol": "ETHUSDT", "last": "2026-11-10T00:00:00Z"},
            }
        ),
        encoding="utf-8",
    )
    symbol_map = pd.DataFrame(
        [{"coin_id": "bitcoin", "bitget_symbol": "BTCUSDT", "fund_interval": 8}]
    )

    manifest = _download_funding(  # type: ignore[arg-type]
        _FundingClient(),
        symbol_map,
        output_dir,
        force=True,
        now=pd.Timestamp("2026-11-14T01:05:00Z"),
    )

    persisted = json.loads((output_dir / "funding_manifest.json").read_text())
    assert manifest["bitcoin"]["last"] == "2026-11-14 00:00:00+00:00"
    assert persisted["bitcoin"]["last"] == "2026-11-14 00:00:00+00:00"
    assert persisted["ethereum"]["last"] == "2026-11-10T00:00:00Z"


def test_partial_candle_refresh_preserves_other_coverage_rows() -> None:
    from scripts.download_bitget_derivatives_data import _merge_coverage_rows

    merged = _merge_coverage_rows(
        [
            {"coin_id": "bitcoin", "bitget_symbol": "BTCUSDT", "candle_type": "mark", "rows": 1},
            {"coin_id": "ethereum", "bitget_symbol": "ETHUSDT", "candle_type": "mark", "rows": 2},
        ],
        [
            {"coin_id": "bitcoin", "bitget_symbol": "BTCUSDT", "candle_type": "market", "rows": 3},
        ],
    )

    assert merged == [
        {"coin_id": "bitcoin", "bitget_symbol": "BTCUSDT", "candle_type": "mark", "rows": 1},
        {"coin_id": "bitcoin", "bitget_symbol": "BTCUSDT", "candle_type": "market", "rows": 3},
        {"coin_id": "ethereum", "bitget_symbol": "ETHUSDT", "candle_type": "mark", "rows": 2},
    ]


def test_candle_coverage_keeps_distinct_coin_aliases_for_one_contract() -> None:
    from scripts.download_bitget_derivatives_data import _merge_coverage_rows

    merged = _merge_coverage_rows(
        [
            {
                "coin_id": "bitcoin",
                "bitget_symbol": "BTCUSDT",
                "candle_type": "market",
                "rows": 2,
            },
            {
                "coin_id": "wrapped-bitcoin",
                "bitget_symbol": "BTCUSDT",
                "candle_type": "market",
                "rows": 2,
            },
        ],
        [
            {
                "coin_id": "wrapped-bitcoin",
                "bitget_symbol": "BTCUSDT",
                "candle_type": "market",
                "rows": 3,
            }
        ],
    )

    assert {row["coin_id"]: row["rows"] for row in merged} == {
        "bitcoin": 2,
        "wrapped-bitcoin": 3,
    }


def test_live_mark_tail_retry_merges_the_new_completed_hour(tmp_path) -> None:
    from scripts import download_bitget_derivatives_data as downloader

    candle_dir = tmp_path / "candles"
    candle_dir.mkdir()
    pd.DataFrame(
        {
            "open_time": [pd.Timestamp("2026-11-13T23:00:00Z")],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.0],
            "volume": [1.0],
            "quote_volume": [100.0],
        }
    ).to_csv(candle_dir / "BTCUSDT_mark.csv", index=False)
    symbol_map = pd.DataFrame(
        [
            {
                "coin_id": "bitcoin",
                "bitget_symbol": "BTCUSDT",
                "contract_status": "normal",
            }
        ]
    )

    class _TailClient:
        def __init__(self) -> None:
            self.calls = 0

        def fetch_history_candles(
            self,
            symbol: str,
            candle_type: str,
            start: pd.Timestamp,
            end: pd.Timestamp,
        ) -> pd.DataFrame:
            self.calls += 1
            assert symbol == "BTCUSDT"
            assert candle_type == "mark"
            assert start == pd.Timestamp("2026-11-13T22:00:00Z")
            assert end == pd.Timestamp("2026-11-14T01:00:00Z")
            return candle_frame([_row("2026-11-14T00:00:00Z")])

    client = _TailClient()
    stale = downloader._wait_for_live_mark_tail(  # type: ignore[attr-defined,arg-type]
        client,
        symbol_map,
        tmp_path,
        required_last=pd.Timestamp("2026-11-14T00:00:00Z"),
        max_wait_seconds=120.0,
        poll_seconds=30.0,
        sleep_fn=lambda _: None,
    )

    assert stale == []
    assert client.calls == 1
    merged = pd.read_csv(candle_dir / "BTCUSDT_mark.csv")
    assert pd.to_datetime(merged["open_time"], utc=True).max() == pd.Timestamp(
        "2026-11-14T00:00:00Z"
    )


def test_mark_tail_only_updates_coverage_metadata(tmp_path) -> None:
    from scripts import download_bitget_derivatives_data as downloader

    candle_dir = tmp_path / "candles"
    candle_dir.mkdir()
    pd.DataFrame(
        {
            "open_time": [
                pd.Timestamp("2026-11-13T23:00:00Z"),
                pd.Timestamp("2026-11-14T00:00:00Z"),
            ],
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.0, 101.0],
            "volume": [1.0, 1.0],
            "quote_volume": [100.0, 100.0],
        }
    ).to_csv(candle_dir / "BTCUSDT_mark.csv", index=False)
    (tmp_path / "coverage.json").write_text(
        json.dumps(
            [
                {
                    "coin_id": "bitcoin",
                    "bitget_symbol": "BTCUSDT",
                    "candle_type": "mark",
                    "last": "2026-11-13 23:00:00+00:00",
                }
            ]
        ),
        encoding="utf-8",
    )
    selected = pd.DataFrame(
        [
            {
                "coin_id": "bitcoin",
                "bitget_symbol": "BTCUSDT",
                "contract_status": "normal",
            }
        ]
    )

    downloader._update_mark_tail_coverage(  # type: ignore[attr-defined]
        tmp_path,
        selected,
        required_last=pd.Timestamp("2026-11-14T00:00:00Z"),
    )

    row = json.loads((tmp_path / "coverage.json").read_text(encoding="utf-8"))[0]
    assert row["rows"] == 2
    assert pd.Timestamp(row["last"]) == pd.Timestamp("2026-11-14T00:00:00Z")
    assert row["tail_required_through"] == "2026-11-14 00:00:00+00:00"


def test_mark_tail_only_reuses_cached_symbol_map_without_fetching_contracts(
    tmp_path,
    monkeypatch,
) -> None:
    from scripts import download_bitget_derivatives_data as downloader

    output_dir = tmp_path / "raw"
    output_dir.mkdir()
    pd.DataFrame(
        [
            {
                "coin_id": "bitcoin",
                "bitget_symbol": "BTCUSDT",
                "contract_status": "normal",
            },
            {
                "coin_id": "offline",
                "bitget_symbol": "OFFLINEUSDT",
                "contract_status": "offline",
            }
        ]
    ).to_csv(output_dir / "symbol_map.csv", index=False)
    panel = tmp_path / "panel.csv"
    pd.DataFrame([{"coin_id": "bitcoin", "symbol": "BTC"}]).to_csv(panel, index=False)
    selected_symbols: list[str] = []

    class _TailClient:
        def __init__(self, **_kwargs) -> None:
            pass

        def fetch_contracts(self) -> list[dict[str, object]]:
            raise AssertionError("mark-tail finalize must not refetch contracts")

    def fake_wait(client, selected, output, **kwargs):
        del client, output, kwargs
        selected_symbols.extend(selected["bitget_symbol"].tolist())
        return []

    monkeypatch.setattr(downloader, "BitgetClient", _TailClient)
    monkeypatch.setattr(
        downloader,
        "_read_panel",
        lambda _path: (_ for _ in ()).throw(
            AssertionError("mark-tail finalize must not rebuild the symbol map")
        ),
    )
    monkeypatch.setattr(downloader, "_wait_for_live_mark_tail", fake_wait)
    monkeypatch.setattr(
        downloader,
        "_update_mark_tail_coverage",
        lambda *_args, **_kwargs: None,
    )
    monkeypatch.setattr(
        downloader.sys,
        "argv",
        [
            "download_bitget_derivatives_data.py",
            "--panel",
            str(panel),
            "--output-dir",
            str(output_dir),
            "--mark-tail-only",
            "--required-mark-time",
            "2026-11-14T00:00:00Z",
            "--wait-for-live-mark-seconds",
            "1",
            "--skip-funding",
        ],
    )

    downloader.main()

    assert selected_symbols == ["BTCUSDT"]


def test_live_mark_tail_retry_does_not_refetch_a_deep_gap(tmp_path) -> None:
    from scripts import download_bitget_derivatives_data as downloader

    candle_dir = tmp_path / "candles"
    candle_dir.mkdir()
    pd.DataFrame(
        {
            "open_time": [pd.Timestamp("2026-11-13T12:00:00Z")],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.0],
            "volume": [1.0],
            "quote_volume": [100.0],
        }
    ).to_csv(candle_dir / "BTCUSDT_mark.csv", index=False)
    symbol_map = pd.DataFrame(
        [
            {
                "coin_id": "bitcoin",
                "bitget_symbol": "BTCUSDT",
                "contract_status": "normal",
            }
        ]
    )

    class _TailClient:
        def fetch_history_candles(self, *args, **kwargs) -> pd.DataFrame:
            raise AssertionError("a deep gap needs a full data refresh, not a tail retry")

    stale = downloader._wait_for_live_mark_tail(  # type: ignore[attr-defined,arg-type]
        _TailClient(),
        symbol_map,
        tmp_path,
        required_last=pd.Timestamp("2026-11-14T00:00:00Z"),
        max_wait_seconds=120.0,
        poll_seconds=30.0,
        sleep_fn=lambda _: None,
    )

    assert stale == ["BTCUSDT"]


def test_live_mark_tail_retry_stops_at_the_wait_budget(tmp_path) -> None:
    from scripts import download_bitget_derivatives_data as downloader

    candle_dir = tmp_path / "candles"
    candle_dir.mkdir()
    pd.DataFrame(
        {
            "open_time": [pd.Timestamp("2026-11-13T23:00:00Z")],
            "open": [100.0],
            "high": [101.0],
            "low": [99.0],
            "close": [100.0],
            "volume": [1.0],
            "quote_volume": [100.0],
        }
    ).to_csv(candle_dir / "BTCUSDT_mark.csv", index=False)
    symbol_map = pd.DataFrame(
        [
            {
                "coin_id": "bitcoin",
                "bitget_symbol": "BTCUSDT",
                "contract_status": "normal",
            }
        ]
    )

    class _EmptyTailClient:
        def __init__(self) -> None:
            self.calls = 0

        def fetch_history_candles(self, *args, **kwargs) -> pd.DataFrame:
            self.calls += 1
            return pd.DataFrame()

    class _Clock:
        def __init__(self) -> None:
            self.elapsed = 0.0

        def monotonic(self) -> float:
            return self.elapsed

        def sleep(self, seconds: float) -> None:
            self.elapsed += seconds

    clock = _Clock()
    client = _EmptyTailClient()
    stale = downloader._wait_for_live_mark_tail(  # type: ignore[attr-defined,arg-type]
        client,
        symbol_map,
        tmp_path,
        required_last=pd.Timestamp("2026-11-14T00:00:00Z"),
        max_wait_seconds=75.0,
        poll_seconds=30.0,
        sleep_fn=clock.sleep,
        clock_fn=clock.monotonic,
    )

    assert stale == ["BTCUSDT"]
    assert clock.elapsed == 75.0
    assert client.calls == 3


def test_live_mark_tail_retry_fills_a_hole_before_a_newer_bar(tmp_path) -> None:
    from scripts import download_bitget_derivatives_data as downloader

    candle_dir = tmp_path / "candles"
    candle_dir.mkdir()
    pd.DataFrame(
        {
            "open_time": [
                pd.Timestamp("2026-11-13T23:00:00Z"),
                pd.Timestamp("2026-11-14T01:00:00Z"),
            ],
            "open": [100.0, 101.0],
            "high": [101.0, 102.0],
            "low": [99.0, 100.0],
            "close": [100.0, 101.0],
            "volume": [1.0, 1.0],
            "quote_volume": [100.0, 100.0],
        }
    ).to_csv(candle_dir / "BTCUSDT_mark.csv", index=False)
    symbol_map = pd.DataFrame(
        [
            {
                "coin_id": "bitcoin",
                "bitget_symbol": "BTCUSDT",
                "contract_status": "normal",
            }
        ]
    )

    class _HoleClient:
        def __init__(self) -> None:
            self.calls = 0

        def fetch_history_candles(self, *args, **kwargs) -> pd.DataFrame:
            self.calls += 1
            return candle_frame([_row("2026-11-14T00:00:00Z")])

    client = _HoleClient()
    stale = downloader._wait_for_live_mark_tail(  # type: ignore[attr-defined,arg-type]
        client,
        symbol_map,
        tmp_path,
        required_last=pd.Timestamp("2026-11-14T00:00:00Z"),
        max_wait_seconds=120.0,
        poll_seconds=30.0,
        sleep_fn=lambda _: None,
    )

    assert stale == []
    assert client.calls == 1
    merged = pd.read_csv(candle_dir / "BTCUSDT_mark.csv")
    assert pd.Timestamp("2026-11-14T00:00:00Z") in set(
        pd.to_datetime(merged["open_time"], utc=True)
    )


def test_four_hour_funding_cache_is_refetched_before_twelve_hours(tmp_path) -> None:
    """A 4h settlement clock cannot rely on the old 12h refresh threshold."""

    from scripts.download_bitget_derivatives_data import _download_funding

    class _FundingClient:
        def __init__(self) -> None:
            self.calls = 0

        def fetch_funding_history(self, symbol: str) -> pd.DataFrame:
            self.calls += 1
            return pd.DataFrame(
                {
                    "symbol": [symbol],
                    "funding_time": [pd.Timestamp("2026-11-14T08:00:00Z")],
                    "funding_rate": [0.0002],
                }
            )

    output_dir = tmp_path
    funding_dir = output_dir / "funding"
    funding_dir.mkdir()
    pd.DataFrame(
        {
            "symbol": ["BTCUSDT"],
            "funding_time": [pd.Timestamp("2026-11-13T22:00:00Z")],
            "funding_rate": [0.0001],
        }
    ).to_csv(funding_dir / "bitcoin.csv", index=False)
    symbol_map = pd.DataFrame(
        [{"coin_id": "bitcoin", "bitget_symbol": "BTCUSDT", "fund_interval": 4}]
    )
    client = _FundingClient()

    manifest = _download_funding(  # type: ignore[arg-type]
        client,
        symbol_map,
        output_dir,
        force=False,
        now=pd.Timestamp("2026-11-14T08:05:00Z"),
    )

    assert client.calls == 1
    assert manifest["bitcoin"]["last"] == "2026-11-14 08:00:00+00:00"


@pytest.mark.parametrize(
    ("interval_hours", "last_settlement"),
    [(8, "2026-11-18T16:00:00Z"), (4, "2026-11-18T20:00:00Z")],
)
def test_due_funding_settlement_is_fetched_within_provider_delivery_window(
    tmp_path,
    interval_hours: int,
    last_settlement: str,
) -> None:
    """A settlement becoming due must trigger a request, even 40s later."""

    from scripts.download_bitget_derivatives_data import _download_funding

    settlement = pd.Timestamp("2026-11-19T00:00:00Z")
    next_settlement = settlement + pd.Timedelta(hours=interval_hours)
    request_time = settlement + pd.Timedelta(seconds=40)

    class _FundingClient:
        def __init__(self) -> None:
            self.history_calls = 0
            self.current_calls = 0
            self.last_request_time_ms = int(request_time.timestamp() * 1000)

        def fetch_funding_history(self, symbol: str) -> pd.DataFrame:
            self.history_calls += 1
            return pd.DataFrame(
                {
                    "symbol": [symbol],
                    "funding_time": [settlement],
                    "funding_rate": [0.0002],
                }
            )

        def fetch_current_funding(self, symbol: str) -> dict[str, object]:
            self.current_calls += 1
            return {
                "symbol": symbol,
                "fundingRateInterval": str(interval_hours),
                "nextUpdate": str(int(next_settlement.timestamp() * 1000)),
                "lastFundingRate": "0.0002",
            }

    output_dir = tmp_path
    funding_dir = output_dir / "funding"
    funding_dir.mkdir()
    pd.DataFrame(
        {
            "symbol": ["BTCUSDT"],
            "funding_time": [pd.Timestamp(last_settlement)],
            "funding_rate": [0.0001],
        }
    ).to_csv(funding_dir / "bitcoin.csv", index=False)
    symbol_map = pd.DataFrame(
        [{"coin_id": "bitcoin", "bitget_symbol": "BTCUSDT", "fund_interval": interval_hours}]
    )
    client = _FundingClient()

    manifest = _download_funding(  # type: ignore[arg-type]
        client,
        symbol_map,
        output_dir,
        force=False,
        now=request_time,
    )

    assert client.history_calls == 1
    assert client.current_calls == 1
    assert manifest["bitcoin"]["last"] == "2026-11-19 00:00:00+00:00"


def test_fresh_funding_cache_refetches_to_repair_incomplete_publication(
    tmp_path,
) -> None:
    """A cache must not be skipped until its audit evidence is complete."""

    from scripts.download_bitget_derivatives_data import _download_funding

    settlement = pd.Timestamp("2026-11-19T00:00:00Z")
    request_time = pd.Timestamp("2026-11-19T01:00:00Z")
    next_settlement = pd.Timestamp("2026-11-19T08:00:00Z")

    class _FundingClient:
        def __init__(self) -> None:
            self.history_calls = 0
            self.current_calls = 0
            self.last_request_time_ms = int(request_time.timestamp() * 1000)

        def fetch_funding_history(self, symbol: str) -> pd.DataFrame:
            self.history_calls += 1
            return pd.DataFrame(
                {
                    "symbol": [symbol],
                    "funding_time": [settlement],
                    "funding_rate": [0.0002],
                }
            )

        def fetch_current_funding(self, symbol: str) -> dict[str, object]:
            self.current_calls += 1
            return {
                "symbol": symbol,
                "fundingRateInterval": "8",
                "nextUpdate": str(int(next_settlement.timestamp() * 1000)),
                "lastFundingRate": "0.0002",
            }

    output_dir = tmp_path
    funding_dir = output_dir / "funding"
    funding_dir.mkdir()
    funding_path = funding_dir / "bitcoin.csv"
    pd.DataFrame(
        {
            "symbol": ["BTCUSDT"],
            "funding_time": [settlement],
            "funding_rate": [0.0002],
        }
    ).to_csv(funding_path, index=False)
    funding_hash = hashlib.sha256(funding_path.read_bytes()).hexdigest()
    (output_dir / "funding_publication.json").write_text(
        json.dumps(
            {
                "version": 1,
                "generated_at": "2026-11-19T00:40:00+00:00",
                "assets": {
                    "bitcoin": {
                        "symbol": "BTCUSDT",
                        "funding_sha256": funding_hash,
                        "funding_last": str(settlement),
                        "funding_rate": 0.0002,
                        "history_last": str(settlement),
                        "current_settlement_time": str(settlement),
                        "current_funding_rate": None,
                        "api_interval_hours": None,
                        "contract_interval_hours": 8,
                        "interval_matches_contract": False,
                        "rate_relation": "unavailable",
                        "latest_source": "history",
                        "verified_at": "2026-11-19T00:40:00+00:00",
                        "publication_lag_seconds": 2400.0,
                        "current_funding_error": "temporary current endpoint failure",
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    symbol_map = pd.DataFrame(
        [{"coin_id": "bitcoin", "bitget_symbol": "BTCUSDT", "fund_interval": 8}]
    )
    client = _FundingClient()

    manifest = _download_funding(  # type: ignore[arg-type]
        client,
        symbol_map,
        output_dir,
        force=False,
        now=request_time,
    )

    assert manifest["bitcoin"]["last"] == str(settlement)
    assert client.history_calls == 1
    assert client.current_calls == 1
    publication = json.loads(
        (output_dir / "funding_publication.json").read_text(encoding="utf-8")
    )
    entry = publication["assets"]["bitcoin"]
    assert entry["api_interval_hours"] == 8.0
    assert entry["interval_matches_contract"] is True
    assert entry["current_funding_error"] is None
    assert entry["rate_relation"] == "match"


def test_fresh_funding_cache_refetches_to_repair_conflicting_publication_rate(
    tmp_path,
) -> None:
    """Publication evidence that would fail the audit must be repaired."""

    from scripts.download_bitget_derivatives_data import _download_funding

    settlement = pd.Timestamp("2026-11-19T00:00:00Z")
    request_time = pd.Timestamp("2026-11-19T01:00:00Z")
    next_settlement = pd.Timestamp("2026-11-19T08:00:00Z")

    class _FundingClient:
        def __init__(self) -> None:
            self.history_calls = 0
            self.current_calls = 0
            self.last_request_time_ms = int(request_time.timestamp() * 1000)

        def fetch_funding_history(self, symbol: str) -> pd.DataFrame:
            self.history_calls += 1
            return pd.DataFrame(
                {
                    "symbol": [symbol],
                    "funding_time": [settlement],
                    "funding_rate": [0.0002],
                }
            )

        def fetch_current_funding(self, symbol: str) -> dict[str, object]:
            self.current_calls += 1
            return {
                "symbol": symbol,
                "fundingRateInterval": "8",
                "nextUpdate": str(int(next_settlement.timestamp() * 1000)),
                "lastFundingRate": "0.0002",
            }

    output_dir = tmp_path
    funding_dir = output_dir / "funding"
    funding_dir.mkdir()
    funding_path = funding_dir / "bitcoin.csv"
    pd.DataFrame(
        {
            "symbol": ["BTCUSDT"],
            "funding_time": [settlement],
            "funding_rate": [0.0002],
        }
    ).to_csv(funding_path, index=False)
    funding_hash = hashlib.sha256(funding_path.read_bytes()).hexdigest()
    (output_dir / "funding_publication.json").write_text(
        json.dumps(
            {
                "version": 1,
                "generated_at": "2026-11-19T00:40:00+00:00",
                "assets": {
                    "bitcoin": {
                        "symbol": "BTCUSDT",
                        "funding_sha256": funding_hash,
                        "funding_last": str(settlement),
                        "funding_rate": 0.0002,
                        "history_last": str(settlement),
                        "current_settlement_time": str(settlement),
                        "current_funding_rate": 0.0003,
                        "api_interval_hours": 8.0,
                        "contract_interval_hours": 8,
                        "interval_matches_contract": True,
                        "rate_relation": "match",
                        "latest_source": "history",
                        "verified_at": "2026-11-19T00:40:00+00:00",
                        "publication_lag_seconds": 2400.0,
                        "current_funding_error": None,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    symbol_map = pd.DataFrame(
        [{"coin_id": "bitcoin", "bitget_symbol": "BTCUSDT", "fund_interval": 8}]
    )
    client = _FundingClient()

    _download_funding(  # type: ignore[arg-type]
        client,
        symbol_map,
        output_dir,
        force=False,
        now=request_time,
    )

    assert client.history_calls == 1
    assert client.current_calls == 1
    publication = json.loads(
        (output_dir / "funding_publication.json").read_text(encoding="utf-8")
    )
    entry = publication["assets"]["bitcoin"]
    assert entry["current_funding_rate"] == 0.0002
    assert entry["rate_relation"] == "match"


def test_funding_fetch_failure_keeps_the_cached_manifest_identity(tmp_path) -> None:
    """A transient refresh error must not erase a valid cached funding row."""

    from scripts.download_bitget_derivatives_data import _download_funding

    class _FailingClient:
        def fetch_funding_history(self, symbol: str) -> pd.DataFrame:
            raise RuntimeError("temporary endpoint failure")

    output_dir = tmp_path
    funding_dir = output_dir / "funding"
    funding_dir.mkdir()
    pd.DataFrame(
        {
            "symbol": ["BTCUSDT"],
            "funding_time": [pd.Timestamp("2026-11-13T16:00:00Z")],
            "funding_rate": [0.0001],
        }
    ).to_csv(funding_dir / "bitcoin.csv", index=False)
    (output_dir / "funding_manifest.json").write_text(
        json.dumps(
            {
                "bitcoin": {
                    "symbol": "BTCUSDT",
                    "last": "2026-11-13T16:00:00Z",
                    "rows": 1,
                }
            }
        ),
        encoding="utf-8",
    )
    symbol_map = pd.DataFrame(
        [{"coin_id": "bitcoin", "bitget_symbol": "BTCUSDT", "fund_interval": 8}]
    )

    manifest = _download_funding(  # type: ignore[arg-type]
        _FailingClient(),
        symbol_map,
        output_dir,
        force=True,
        now=pd.Timestamp("2026-11-14T01:05:00Z"),
    )

    assert manifest["bitcoin"]["last"] == "2026-11-13 16:00:00+00:00"
    assert manifest["bitcoin"]["rows"] == 1
    assert "temporary endpoint failure" in manifest["bitcoin"]["refresh_error"]
    persisted = json.loads((output_dir / "funding_manifest.json").read_text())
    assert persisted["bitcoin"]["last"] == "2026-11-13 16:00:00+00:00"



def test_current_funding_rate_fills_a_late_history_settlement(tmp_path) -> None:
    from scripts.download_bitget_derivatives_data import _download_funding

    history_time = int(pd.Timestamp("2026-11-14T01:00:00Z").timestamp() * 1000)
    current_time = int(pd.Timestamp("2026-11-14T01:05:00Z").timestamp() * 1000)
    next_time = int(pd.Timestamp("2026-11-14T08:00:00Z").timestamp() * 1000)

    class _FundingClient:
        def __init__(self) -> None:
            self.last_request_time_ms = history_time

        def fetch_funding_history(self, symbol: str) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    "symbol": [symbol],
                    "funding_time": [pd.Timestamp("2026-11-13T16:00:00Z")],
                    "funding_rate": [0.0001],
                }
            )

        def fetch_current_funding(self, symbol: str) -> dict[str, object]:
            assert symbol == "BTCUSDT"
            self.last_request_time_ms = current_time
            return {
                "symbol": symbol,
                "fundingRateInterval": "8",
                "nextUpdate": str(next_time),
                "lastFundingRate": "0.0003",
            }

    output_dir = tmp_path
    funding_dir = output_dir / "funding"
    funding_dir.mkdir()
    pd.DataFrame(
        {
            "symbol": ["BTCUSDT"],
            "funding_time": [pd.Timestamp("2026-11-13T16:00:00Z")],
            "funding_rate": [0.0001],
        }
    ).to_csv(funding_dir / "bitcoin.csv", index=False)
    symbol_map = pd.DataFrame(
        [{"coin_id": "bitcoin", "bitget_symbol": "BTCUSDT", "fund_interval": 8}]
    )

    manifest = _download_funding(  # type: ignore[arg-type]
        _FundingClient(),
        symbol_map,
        output_dir,
        force=True,
        now=pd.Timestamp("2026-11-14T01:05:00Z"),
    )

    merged = pd.read_csv(funding_dir / "bitcoin.csv")
    assert manifest["bitcoin"]["last"] == "2026-11-14 00:00:00+00:00"
    assert merged["funding_time"].tolist() == [
        "2026-11-13 16:00:00+00:00",
        "2026-11-14 00:00:00+00:00",
    ]
    assert merged["funding_rate"].tolist() == [0.0001, 0.0003]
    publication = json.loads(
        (output_dir / "funding_publication.json").read_text(encoding="utf-8")
    )
    entry = publication["assets"]["bitcoin"]
    assert entry["rate_relation"] == "fallback"
    assert entry["latest_source"] == "current_fund_rate"
    assert entry["funding_last"] == "2026-11-14 00:00:00+00:00"
    assert entry["publication_lag_seconds"] == 3900.0


@pytest.mark.parametrize("history_failure", ["raises", "empty"])
def test_current_funding_rate_is_used_when_history_is_unavailable(
    tmp_path,
    history_failure: str,
) -> None:
    """The independent current endpoint must survive a history outage."""

    from scripts.download_bitget_derivatives_data import _download_funding

    settlement = pd.Timestamp("2026-11-19T00:00:00Z")
    request_time = pd.Timestamp("2026-11-19T00:35:00Z")
    next_settlement = pd.Timestamp("2026-11-19T08:00:00Z")

    class _FundingClient:
        def __init__(self) -> None:
            self.current_calls = 0
            self.last_request_time_ms = int(request_time.timestamp() * 1000)

        def fetch_funding_history(self, symbol: str) -> pd.DataFrame:
            if history_failure == "raises":
                raise RuntimeError("history endpoint unavailable")
            return pd.DataFrame(columns=["symbol", "funding_time", "funding_rate"])

        def fetch_current_funding(self, symbol: str) -> dict[str, object]:
            self.current_calls += 1
            assert symbol == "BTCUSDT"
            return {
                "symbol": symbol,
                "fundingRateInterval": "8",
                "nextUpdate": str(int(next_settlement.timestamp() * 1000)),
                "lastFundingRate": "0.0002",
            }

    output_dir = tmp_path
    funding_dir = output_dir / "funding"
    funding_dir.mkdir()
    pd.DataFrame(
        {
            "symbol": ["BTCUSDT"],
            "funding_time": [pd.Timestamp("2026-11-18T16:00:00Z")],
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
        force=True,
        now=request_time,
    )

    merged = pd.read_csv(funding_dir / "bitcoin.csv")
    assert client.current_calls == 1
    assert manifest["bitcoin"]["last"] == str(settlement)
    assert pd.to_datetime(merged["funding_time"], utc=True).tolist() == [
        pd.Timestamp("2026-11-18T16:00:00Z"),
        settlement,
    ]
    publication = json.loads(
        (output_dir / "funding_publication.json").read_text(encoding="utf-8")
    )
    entry = publication["assets"]["bitcoin"]
    assert entry["rate_relation"] == "fallback"
    assert entry["latest_source"] == "current_fund_rate"
    assert entry["funding_last"] == str(settlement)


def test_current_funding_rate_conflict_is_evidence_not_silently_overwritten(
    tmp_path,
) -> None:
    from scripts.download_bitget_derivatives_data import _download_funding

    history_time = int(pd.Timestamp("2026-11-14T01:00:00Z").timestamp() * 1000)
    current_time = int(pd.Timestamp("2026-11-14T01:05:00Z").timestamp() * 1000)
    next_time = int(pd.Timestamp("2026-11-14T08:00:00Z").timestamp() * 1000)

    class _FundingClient:
        def __init__(self) -> None:
            self.last_request_time_ms = history_time

        def fetch_funding_history(self, symbol: str) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    "symbol": [symbol],
                    "funding_time": [pd.Timestamp("2026-11-14T00:00:00Z")],
                    "funding_rate": [0.0002],
                }
            )

        def fetch_current_funding(self, symbol: str) -> dict[str, object]:
            self.last_request_time_ms = current_time
            return {
                "symbol": symbol,
                "fundingRateInterval": "8",
                "nextUpdate": str(next_time),
                "lastFundingRate": "0.0003",
            }

    output_dir = tmp_path
    funding_dir = output_dir / "funding"
    funding_dir.mkdir()
    pd.DataFrame(
        {
            "symbol": ["BTCUSDT"],
            "funding_time": [pd.Timestamp("2026-11-13T16:00:00Z")],
            "funding_rate": [0.0001],
        }
    ).to_csv(funding_dir / "bitcoin.csv", index=False)
    symbol_map = pd.DataFrame(
        [{"coin_id": "bitcoin", "bitget_symbol": "BTCUSDT", "fund_interval": 8}]
    )

    manifest = _download_funding(  # type: ignore[arg-type]
        _FundingClient(),
        symbol_map,
        output_dir,
        force=True,
        now=pd.Timestamp("2026-11-14T01:05:00Z"),
    )

    merged = pd.read_csv(funding_dir / "bitcoin.csv")
    assert manifest["bitcoin"]["last"] == "2026-11-14 00:00:00+00:00"
    assert merged["funding_rate"].tolist() == [0.0001, 0.0002]
    publication = json.loads(
        (output_dir / "funding_publication.json").read_text(encoding="utf-8")
    )
    assert publication["assets"]["bitcoin"]["rate_relation"] == "conflict"


def test_cached_funding_conflict_is_rejected_instead_of_overwritten(tmp_path) -> None:
    from scripts.download_bitget_derivatives_data import _download_funding

    class _FundingClient:
        def fetch_funding_history(self, symbol: str) -> pd.DataFrame:
            return pd.DataFrame(
                {
                    "symbol": [symbol],
                    "funding_time": [pd.Timestamp("2026-11-10T00:00:00Z")],
                    "funding_rate": [0.0002],
                }
            )

    funding_dir = tmp_path / "funding"
    funding_dir.mkdir()
    pd.DataFrame(
        {
            "symbol": ["BTCUSDT"],
            "funding_time": [pd.Timestamp("2026-11-10T00:00:00Z")],
            "funding_rate": [0.0001],
        }
    ).to_csv(funding_dir / "bitcoin.csv", index=False)
    before = (funding_dir / "bitcoin.csv").read_bytes()
    symbol_map = pd.DataFrame(
        [{"coin_id": "bitcoin", "bitget_symbol": "BTCUSDT", "fund_interval": 8}]
    )

    with pytest.raises(ValueError, match="conflicting duplicate"):
        _download_funding(  # type: ignore[arg-type]
            _FundingClient(),
            symbol_map,
            tmp_path,
            force=True,
            now=pd.Timestamp("2026-11-14T01:05:00Z"),
        )

    assert (funding_dir / "bitcoin.csv").read_bytes() == before


def test_cached_funding_symbol_mismatch_is_rejected() -> None:
    from scripts.download_bitget_derivatives_data import _normalise_funding_frame

    frame = pd.DataFrame(
        {
            "symbol": ["ETHUSDT"],
            "funding_time": [pd.Timestamp("2026-11-10T00:00:00Z")],
            "funding_rate": [0.0001],
        }
    )

    with pytest.raises(ValueError, match="symbol"):
        _normalise_funding_frame(frame, symbol="BTCUSDT", label="cached bitcoin")


def test_contract_snapshot_archive_records_change_points_not_duplicates(tmp_path) -> None:
    from scripts.download_bitget_derivatives_data import _archive_contract_snapshot

    first = _archive_contract_snapshot(
        tmp_path,
        [{"symbol": "BTCUSDT", "sizeMultiplier": "0.0001", "minTradeUSDT": "5"}],
        captured_at=pd.Timestamp("2026-11-16T13:00:00Z"),
        request_time_ms=int(pd.Timestamp("2026-11-16T13:00:01Z").timestamp() * 1000),
    )
    second = _archive_contract_snapshot(
        tmp_path,
        [{"symbol": "BTCUSDT", "sizeMultiplier": "0.0001", "minTradeUSDT": "5"}],
        captured_at=pd.Timestamp("2026-11-16T14:00:00Z"),
        request_time_ms=int(pd.Timestamp("2026-11-16T14:00:01Z").timestamp() * 1000),
    )
    changed = _archive_contract_snapshot(
        tmp_path,
        [{"symbol": "BTCUSDT", "sizeMultiplier": "0.001", "minTradeUSDT": "5"}],
        captured_at=pd.Timestamp("2026-11-16T15:00:00Z"),
        request_time_ms=int(pd.Timestamp("2026-11-16T15:00:01Z").timestamp() * 1000),
    )

    index = json.loads(
        (tmp_path / "contract_snapshots" / "index.json").read_text(encoding="utf-8")
    )
    assert len(index["snapshots"]) == 2
    assert first["sha256"] == second["sha256"]
    assert first["first_seen_at"] == "2026-11-16T13:00:00+00:00"
    assert second["last_seen_at"] == "2026-11-16T14:00:00+00:00"
    assert changed["sha256"] != first["sha256"]
    assert len(list((tmp_path / "contract_snapshots").glob("contracts_*.json"))) == 2


def test_funding_request_time_is_not_reused_when_a_response_omits_it() -> None:
    class _Session:
        def get(self, url, params, timeout):
            del url, timeout
            page = int(params["pageNo"])
            payload: dict[str, object] = {
                "code": "00000",
                "data": {
                    "resultList": (
                        [
                            {
                                "symbol": "BTCUSDT",
                                "fundingRate": "0.0001",
                                "fundingRateTimestamp": "1791504000000",
                            }
                        ]
                        if page == 1
                        else []
                    )
                },
            }
            if page == 1:
                payload["requestTime"] = 1791504005000
            return _FakeResponse(payload)

    client = _client(_Session())
    frame = client.fetch_funding_history("BTCUSDT", page_size=1, max_pages=2)

    assert frame.attrs["request_times_ms"] == [1791504005000]
