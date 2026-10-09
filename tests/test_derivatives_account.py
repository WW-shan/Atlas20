from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest

from atlas20.derivatives.account import (
    BitgetCredentials,
    BitgetCredentialsError,
    BitgetPrivateClient,
    sign_request,
)
from atlas20.derivatives.bitget import BitgetAPIError


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.ok = status_code < 400
        self.text = json.dumps(payload)

    def json(self) -> dict:
        return self._payload


class _FakeSession:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []
        self.headers: dict[str, str] = {}

    def request(self, method: str, url: str, *, headers: dict, data=None, timeout=30.0):
        self.calls.append(
            {"method": method, "url": url, "headers": dict(headers), "data": data, "timeout": timeout}
        )
        if not self.responses:
            raise AssertionError("no fake responses left")
        return self.responses.pop(0)


def _client(session: _FakeSession, *, demo: bool = False, **kwargs) -> BitgetPrivateClient:
    credentials = BitgetCredentials(
        api_key="key-1", secret_key="secret-1", passphrase="pass-1", demo=demo
    )
    return BitgetPrivateClient(
        credentials, session=session, max_retries=1, retry_backoff_seconds=0.0, **kwargs
    )


def test_signature_matches_the_documented_hmac_construction() -> None:
    timestamp = 1659076670000
    method = "POST"
    path = "/api/v3/trade/place-order"
    body = '{"symbol":"BTCUSDT"}'
    message = f"{timestamp}{method}{path}{body}"
    expected = base64.b64encode(
        hmac.new(b"secret-1", message.encode(), hashlib.sha256).digest()
    ).decode()

    assert sign_request("secret-1", timestamp, method, path, body) == expected


def test_headers_carry_credentials_and_the_demo_flag() -> None:
    session = _FakeSession([_FakeResponse({"code": "00000", "data": {}})])
    client = _client(session, demo=True, now_seconds=1_700_000_000.0)

    client.account_assets()

    headers = session.calls[0]["headers"]
    assert headers["ACCESS-KEY"] == "key-1"
    assert headers["ACCESS-PASSPHRASE"] == "pass-1"
    assert headers["ACCESS-TIMESTAMP"] == "1700000000000"
    assert headers["paptrading"] == "1"
    assert headers["locale"] == "en-US"
    assert (
        headers["ACCESS-SIGN"]
        == sign_request("secret-1", 1700000000000, "GET", "/api/v3/account/assets", "")
    )


def test_non_demo_requests_omit_the_paper_header() -> None:
    session = _FakeSession([_FakeResponse({"code": "00000", "data": {}})])
    client = _client(session, now_seconds=1_700_000_000.0)

    client.account_assets()

    assert "paptrading" not in session.calls[0]["headers"]


def test_query_parameters_are_signed_as_part_of_the_path() -> None:
    session = _FakeSession([_FakeResponse({"code": "00000", "data": {"list": []}})])
    client = _client(session, now_seconds=1_700_000_000.0)

    client.current_positions(symbol="NEARUSDT")

    call = session.calls[0]
    assert "category=USDT-FUTURES" in call["url"]
    assert "symbol=NEARUSDT" in call["url"]
    path = call["url"].split("api.bitget.com", 1)[1]
    assert (
        call["headers"]["ACCESS-SIGN"]
        == sign_request("secret-1", 1700000000000, "GET", path, "")
    )


def test_body_is_signed_and_sent_for_orders() -> None:
    session = _FakeSession([_FakeResponse({"code": "00000", "data": {"orderId": "1"}})])
    client = _client(session, now_seconds=1_700_000_000.0)

    client.place_order(symbol="NEARUSDT", qty=12.5, side="buy")

    call = session.calls[0]
    body = call["data"]
    assert body is not None and "NEARUSDT" in body
    assert (
        call["headers"]["ACCESS-SIGN"]
        == sign_request("secret-1", 1700000000000, "POST", "/api/v3/trade/place-order", body)
    )


def test_api_error_code_raises() -> None:
    session = _FakeSession([_FakeResponse({"code": "40006", "msg": "Invalid ACCESS_KEY"})])
    client = _client(session)

    with pytest.raises(BitgetAPIError, match="40006"):
        client.account_assets()


def test_server_errors_are_retried() -> None:
    session = _FakeSession(
        [
            _FakeResponse({"code": "50000", "msg": "oops"}, status_code=500),
            _FakeResponse({"code": "00000", "data": {"accountEquity": "100"}}),
        ]
    )
    credentials = BitgetCredentials("k", "s", "p")
    client = BitgetPrivateClient(
        credentials, session=session, max_retries=2, retry_backoff_seconds=0.0
    )

    assert client.account_assets()["accountEquity"] == "100"
    assert len(session.calls) == 2


def test_market_order_omits_price_and_formats_qty() -> None:
    session = _FakeSession([_FakeResponse({"code": "00000", "data": {}})])
    client = _client(session)

    client.place_order(symbol="NEARUSDT", qty=12.5000, side="sell", reduce_only=True)

    body = json.loads(session.calls[0]["data"])
    assert body["qty"] == "12.5"
    assert body["side"] == "sell"
    assert body["reduceOnly"] == "yes"
    assert "price" not in body


def test_limit_order_requires_a_price() -> None:
    session = _FakeSession([])
    client = _client(session)

    with pytest.raises(ValueError, match="limit orders require"):
        client.place_order(symbol="NEARUSDT", qty=1.0, side="buy", order_type="limit")


def test_set_margin_validates_and_formats_the_amount() -> None:
    session = _FakeSession([_FakeResponse({"code": "00000", "data": "success"})])
    client = _client(session)

    client.set_margin("NEARUSDT", 7.50, operation="add")

    body = json.loads(session.calls[0]["data"])
    assert body == {
        "category": "USDT-FUTURES",
        "symbol": "NEARUSDT",
        "posSide": "long",
        "operation": "add",
        "amount": "7.5",
    }

    with pytest.raises(ValueError, match="operation"):
        client.set_margin("NEARUSDT", 1.0, operation="replace")
    with pytest.raises(ValueError, match="positive"):
        client.set_margin("NEARUSDT", 0.0)


def test_set_leverage_sends_isolated_mode() -> None:
    session = _FakeSession([_FakeResponse({"code": "00000", "data": {}})])
    client = _client(session)

    client.set_leverage("NEARUSDT", 2)

    body = json.loads(session.calls[0]["data"])
    assert body["leverage"] == "2"
    assert body["marginMode"] == "isolated"
    assert body["posSide"] == "long"


def test_credentials_from_env_reports_missing_names() -> None:
    with pytest.raises(BitgetCredentialsError, match="ATLAS20_BITGET_SECRET_KEY"):
        BitgetCredentials.from_env({"ATLAS20_BITGET_API_KEY": "k"})

    credentials = BitgetCredentials.from_env(
        {
            "ATLAS20_BITGET_API_KEY": "k",
            "ATLAS20_BITGET_SECRET_KEY": "s",
            "ATLAS20_BITGET_PASSPHRASE": "p",
            "ATLAS20_BITGET_DEMO": "yes",
        }
    )
    assert credentials.demo is True
