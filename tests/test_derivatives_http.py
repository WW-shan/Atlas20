from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import requests

from atlas20.derivatives.http import get_json_with_retries


class _Response:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self._payload = dict(payload)
        self.ok = True
        self.status_code = 200
        self.text = ""

    def json(self) -> dict[str, Any]:
        return self._payload


class _FlakySession:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        self.payload = payload
        self.calls = 0

    def get(self, url: str, *, params: Mapping[str, Any], timeout: float) -> _Response:
        self.calls += 1
        if self.calls == 1:
            raise requests.ConnectionError("transient SSL EOF")
        return _Response(self.payload)


def test_get_json_retries_a_transient_connection_error() -> None:
    session = _FlakySession({"code": "00000", "data": []})

    payload = get_json_with_retries(
        session,  # type: ignore[arg-type]
        "https://api.bitget.com/api/v3/market/instruments",
        params={"category": "USDT-FUTURES"},
        timeout_seconds=1.0,
        max_retries=3,
        retry_backoff_seconds=0.0,
    )

    assert payload == {"code": "00000", "data": []}
    assert session.calls == 2
