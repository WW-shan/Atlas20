"""Private Bitget UTA (v3) client for the live derivatives executor.

The research track deliberately runs on public data.  This module is the one
place that talks to a *private* Bitget account, because the daily rebalance
plan has to be sized from the real balance instead of the 1,000 USDT research
reference:

* ``GET  /api/v3/account/assets``          - equity / available margin
* ``GET  /api/v3/position/current-position`` - per-leg size and isolated margin
* ``POST /api/v3/account/set-leverage``    - isolated leverage per symbol
* ``POST /api/v3/account/set-margin``      - add/remove isolated margin
* ``POST /api/v3/trade/place-order``       - market open/reduce orders

Endpoint paths and payload fields were verified against the live API and the
official docs on 2026-10-10: ``/api/v2/mix/position/adjust-position-margin``
does not exist (HTTP 404); isolated-margin adjustment is the UTA v3
``/api/v3/account/set-margin`` endpoint with ``operation=add|remove``.

The client never trades on its own.  ``place_order`` is called only by the
execution script, which defaults to a dry run.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import requests

from atlas20.derivatives.bitget import BITGET_BASE_URL, BitgetAPIError

UTA_CATEGORY = "USDT-FUTURES"
_SUCCESS_CODES = {"0", "00000"}
_DEFAULT_TIMEOUT_SECONDS = 30.0
_RETRY_STATUS_CODES = {429, 500, 502, 503, 504}


class BitgetCredentialsError(RuntimeError):
    """Raised when live credentials are missing or incomplete."""


@dataclass(frozen=True)
class BitgetCredentials:
    """UTA API credentials plus the demo-trading switch."""

    api_key: str
    secret_key: str
    passphrase: str
    demo: bool = False

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "BitgetCredentials":
        env = os.environ if environ is None else environ
        api_key = str(env.get("ATLAS20_BITGET_API_KEY", "")).strip()
        secret_key = str(env.get("ATLAS20_BITGET_SECRET_KEY", "")).strip()
        passphrase = str(env.get("ATLAS20_BITGET_PASSPHRASE", "")).strip()
        missing = [
            name
            for name, value in (
                ("ATLAS20_BITGET_API_KEY", api_key),
                ("ATLAS20_BITGET_SECRET_KEY", secret_key),
                ("ATLAS20_BITGET_PASSPHRASE", passphrase),
            )
            if not value
        ]
        if missing:
            raise BitgetCredentialsError(
                "missing Bitget credentials: " + ", ".join(missing)
            )
        demo = str(env.get("ATLAS20_BITGET_DEMO", "")).strip().lower() in {
            "1",
            "true",
            "yes",
        }
        return cls(api_key=api_key, secret_key=secret_key, passphrase=passphrase, demo=demo)


def sign_request(
    secret_key: str,
    timestamp_ms: int,
    method: str,
    request_path: str,
    body: str = "",
) -> str:
    """Bitget v2/v3 signature: base64(HMAC-SHA256(secret, ts + METHOD + path + body))."""

    message = f"{timestamp_ms}{method.upper()}{request_path}{body}"
    digest = hmac.new(secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("ascii")


class BitgetPrivateClient:
    """Minimal signed client for the UTA endpoints the executor needs."""

    def __init__(
        self,
        credentials: BitgetCredentials,
        *,
        base_url: str = BITGET_BASE_URL,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = 3,
        retry_backoff_seconds: float = 1.0,
        session: requests.Session | None = None,
        now_seconds: float | None = None,
    ) -> None:
        self.credentials = credentials
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.session = session or requests.Session()
        headers = getattr(self.session, "headers", None)
        if headers is not None:
            headers.update({"User-Agent": "atlas20-live/0.1"})
        self._now_seconds = now_seconds

    def _timestamp_ms(self) -> int:
        now = time.time() if self._now_seconds is None else self._now_seconds
        return int(now * 1000)

    def _headers(self, method: str, request_path: str, body: str) -> dict[str, str]:
        timestamp = self._timestamp_ms()
        headers = {
            "ACCESS-KEY": self.credentials.api_key,
            "ACCESS-SIGN": sign_request(
                self.credentials.secret_key, timestamp, method, request_path, body
            ),
            "ACCESS-TIMESTAMP": str(timestamp),
            "ACCESS-PASSPHRASE": self.credentials.passphrase,
            "Content-Type": "application/json",
            "locale": "en-US",
        }
        if self.credentials.demo:
            headers["paptrading"] = "1"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        body: Mapping[str, Any] | None = None,
    ) -> Any:
        query = urlencode({k: v for k, v in (params or {}).items() if v is not None})
        request_path = f"{path}?{query}" if query else path
        body_text = (
            json.dumps(body, separators=(",", ":"), sort_keys=True) if body is not None else ""
        )
        url = f"{self.base_url}{request_path}"
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            headers = self._headers(method, request_path, body_text)
            try:
                response = self.session.request(
                    method.upper(),
                    url,
                    headers=headers,
                    data=body_text if body is not None else None,
                    timeout=self.timeout_seconds,
                )
            except requests.RequestException as exc:
                last_error = exc
                if attempt + 1 >= self.max_retries:
                    raise
                time.sleep(self.retry_backoff_seconds * (2**attempt))
                continue

            if response.ok:
                try:
                    payload = response.json()
                except ValueError as exc:
                    raise BitgetAPIError(f"Bitget {path} returned non-JSON payload") from exc
                if not isinstance(payload, dict):
                    raise BitgetAPIError(f"Bitget {path} returned an unexpected payload")
                code = str(payload.get("code", ""))
                if code not in _SUCCESS_CODES:
                    raise BitgetAPIError(
                        f"Bitget {path} error {code}: {payload.get('msg', '')}"
                    )
                return payload.get("data")

            if response.status_code in _RETRY_STATUS_CODES and attempt + 1 < self.max_retries:
                time.sleep(self.retry_backoff_seconds * (2**attempt))
                continue

            raise BitgetAPIError(
                f"Bitget {path} HTTP {response.status_code}: {response.text[:200]}"
            )

        if last_error is not None:
            raise last_error
        raise BitgetAPIError(f"Bitget {path} failed without a response")

    # -- account state -------------------------------------------------

    def account_assets(self) -> dict[str, Any]:
        """Unified-account equity and margin summary."""

        data = self._request("GET", "/api/v3/account/assets")
        if not isinstance(data, dict):
            raise BitgetAPIError("Bitget account assets payload is not an object")
        return dict(data)

    def current_positions(
        self,
        *,
        symbol: str | None = None,
        pos_side: str | None = None,
        category: str = UTA_CATEGORY,
    ) -> list[dict[str, Any]]:
        """Open positions for the category, optionally filtered to one symbol."""

        data = self._request(
            "GET",
            "/api/v3/position/current-position",
            params={"category": category, "symbol": symbol, "posSide": pos_side},
        )
        rows: Any
        if isinstance(data, dict):
            rows = data.get("list") or []
        elif isinstance(data, list):
            rows = data
        else:
            rows = []
        return [dict(row) for row in rows if isinstance(row, dict)]

    # -- account / position settings -----------------------------------

    def set_hold_mode(self, hold_mode: str = "one_way_mode") -> Any:
        return self._request(
            "POST",
            "/api/v3/account/set-hold-mode",
            body={"holdMode": hold_mode},
        )

    def set_leverage(
        self,
        symbol: str,
        leverage: int | float,
        *,
        pos_side: str = "long",
        margin_mode: str = "isolated",
        category: str = UTA_CATEGORY,
    ) -> Any:
        return self._request(
            "POST",
            "/api/v3/account/set-leverage",
            body={
                "category": category,
                "symbol": symbol,
                "leverage": str(leverage),
                "posSide": pos_side,
                "marginMode": margin_mode,
            },
        )

    def set_margin(
        self,
        symbol: str,
        amount: float,
        *,
        pos_side: str = "long",
        operation: str = "add",
        category: str = UTA_CATEGORY,
    ) -> Any:
        """Add or remove isolated margin. ``operation`` is ``add`` or ``remove``."""

        if operation not in {"add", "remove"}:
            raise ValueError("operation must be 'add' or 'remove'")
        if amount <= 0.0:
            raise ValueError("amount must be positive")
        return self._request(
            "POST",
            "/api/v3/account/set-margin",
            body={
                "category": category,
                "symbol": symbol,
                "posSide": pos_side,
                "operation": operation,
                "amount": f"{amount:.8f}".rstrip("0").rstrip("."),
            },
        )

    # -- orders ---------------------------------------------------------

    def place_order(
        self,
        *,
        symbol: str,
        qty: float,
        side: str,
        order_type: str = "market",
        pos_side: str = "long",
        reduce_only: bool = False,
        client_oid: str | None = None,
        margin_mode: str = "isolated",
        price: float | None = None,
        category: str = UTA_CATEGORY,
    ) -> dict[str, Any]:
        """Place one futures order.  Market orders omit ``price``."""

        if side not in {"buy", "sell"}:
            raise ValueError("side must be 'buy' or 'sell'")
        if order_type not in {"limit", "market"}:
            raise ValueError("order_type must be 'limit' or 'market'")
        if qty <= 0.0:
            raise ValueError("qty must be positive")
        body: dict[str, Any] = {
            "category": category,
            "symbol": symbol,
            "qty": f"{qty:.12f}".rstrip("0").rstrip("."),
            "side": side,
            "orderType": order_type,
            "posSide": pos_side,
            "marginMode": margin_mode,
        }
        if order_type == "limit":
            if price is None or price <= 0.0:
                raise ValueError("limit orders require a positive price")
            body["price"] = f"{price:.12f}".rstrip("0").rstrip(".")
        if reduce_only:
            body["reduceOnly"] = "yes"
        if client_oid:
            body["clientOid"] = client_oid
        data = self._request("POST", "/api/v3/trade/place-order", body=body)
        if isinstance(data, dict):
            return dict(data)
        return {"raw": data}


__all__ = [
    "BitgetCredentials",
    "BitgetCredentialsError",
    "BitgetPrivateClient",
    "UTA_CATEGORY",
    "sign_request",
]
