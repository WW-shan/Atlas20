"""Idempotency key repository."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from typing import Any, Literal

from sqlalchemy import delete, insert, text, update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col

from atlas20.api import _time
from atlas20.api.db.models import IdempotencyKey

# A claim whose request never finished (crashed process, dropped connection)
# must not lock its key for the whole replay window. After this long the key
# can be claimed again.
PENDING_CLAIM_TTL_SECONDS = 60
_ENVELOPE_VERSION = 1

ClaimStatus = Literal["claimed", "replay", "in_progress", "mismatch"]


@dataclass(frozen=True)
class IdempotencyClaim:
    """Outcome of trying to reserve an Idempotency-Key for one request."""

    status: ClaimStatus
    response_json: str | None = None


def request_fingerprint(*, principal: str, method: str, path: str, body: Any) -> str:
    """Hash who sent a request and what it asked for.

    A stored response may only be replayed for the same principal, endpoint and
    payload. Anything else reusing the key is a client error and must never be
    answered with another request's response.
    """
    canonical = json.dumps(
        {"principal": principal, "method": method.upper(), "path": path, "body": body},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class IdempotencyRepo:
    def __init__(self, session: Session):
        self._s = session

    def get(self, key: str) -> IdempotencyKey | None:
        row = self._s.get(IdempotencyKey, key)
        if row is None or self._is_expired(row):
            return None
        return row

    def store(self, key: str, method: str, path: str, response_json: str, ttl_seconds: int = 86400) -> None:
        """Write a raw response without binding it to a request.

        Kept for callers that manage replay themselves; request handlers use
        claim/complete/release so a key is tied to one request payload.
        """
        now = _time.utc_now()
        row = self._s.get(IdempotencyKey, key)
        if row is None:
            row = IdempotencyKey(
                key=key,
                method=method,
                path=path,
                response_json=response_json,
                created_at=now,
                expires_at=now + timedelta(seconds=ttl_seconds),
            )
        else:
            row.method = method
            row.path = path
            row.response_json = response_json
            row.created_at = now
            row.expires_at = now + timedelta(seconds=ttl_seconds)
        self._s.add(row)
        self._s.flush()

    def claim(
        self,
        key: str,
        *,
        method: str,
        path: str,
        request_hash: str,
        pending_ttl_seconds: int = PENDING_CLAIM_TTL_SECONDS,
    ) -> IdempotencyClaim:
        """Reserve ``key`` for this request, or report why it is unavailable.

        The reservation is committed before this returns so concurrent requests
        with the same key see it at once. Call it before any other write in the
        session: it ends the session's current transaction.
        """
        now = _time.utc_now()
        self._begin_immediate_for_sqlite()
        # An expired row (replay window over, or a claim whose request never
        # finished) no longer owns the key.
        self._s.exec(
            delete(IdempotencyKey)
            .where(col(IdempotencyKey.key) == key, col(IdempotencyKey.expires_at) <= now)
            .execution_options(synchronize_session=False)
        )
        try:
            self._s.exec(
                insert(IdempotencyKey).values(
                    key=key,
                    method=method,
                    path=path,
                    response_json=_envelope(request_hash, None),
                    created_at=now,
                    expires_at=now + timedelta(seconds=pending_ttl_seconds),
                )
            )
            self._s.commit()
        except IntegrityError:
            self._s.rollback()
        else:
            return IdempotencyClaim("claimed")

        existing = self._s.get(IdempotencyKey, key, populate_existing=True)
        if existing is None:
            # The holder released the key between our insert and this read.
            return IdempotencyClaim("in_progress")
        return _classify(existing, request_hash)

    def complete(self, key: str, *, request_hash: str, response_json: str, ttl_seconds: int = 86400) -> bool:
        """Store the response for a claim this request holds.

        Returns False when the claim is no longer ours (it expired and another
        request took the key), in which case nothing is overwritten.
        """
        now = _time.utc_now()
        result = self._s.exec(
            update(IdempotencyKey)
            .where(
                col(IdempotencyKey.key) == key,
                col(IdempotencyKey.response_json) == _envelope(request_hash, None),
            )
            .values(
                response_json=_envelope(request_hash, response_json),
                expires_at=now + timedelta(seconds=ttl_seconds),
            )
            .execution_options(synchronize_session=False)
        )
        self._s.flush()
        return bool(result.rowcount)

    def release(self, key: str, *, request_hash: str) -> None:
        """Drop this request's pending claim so the client can retry the key."""
        self._s.exec(
            delete(IdempotencyKey)
            .where(
                col(IdempotencyKey.key) == key,
                col(IdempotencyKey.response_json) == _envelope(request_hash, None),
            )
            .execution_options(synchronize_session=False)
        )
        self._s.flush()

    def purge_expired(self) -> int:
        stmt = delete(IdempotencyKey).where(col(IdempotencyKey.expires_at) <= _time.utc_now())
        result = self._s.exec(stmt)
        self._s.flush()
        return result.rowcount or 0

    def _is_expired(self, row: IdempotencyKey) -> bool:
        return _aware(row.expires_at) <= _time.utc_now()

    def _begin_immediate_for_sqlite(self) -> None:
        # Take SQLite's write lock up front so two claims for one key are
        # serialized instead of both reading "free" and one failing on upgrade.
        if self._s.in_transaction():
            return
        if self._s.get_bind().dialect.name == "sqlite":
            self._s.execute(text("BEGIN IMMEDIATE"))


def _envelope(request_hash: str, response_json: str | None) -> str:
    # The table has no request-hash column; the hash travels with the stored
    # response so a replay can be checked against the incoming request.
    return json.dumps(
        {"v": _ENVELOPE_VERSION, "request_hash": request_hash, "response_json": response_json},
        sort_keys=True,
        separators=(",", ":"),
    )


def _classify(row: IdempotencyKey, request_hash: str) -> IdempotencyClaim:
    try:
        payload = json.loads(row.response_json)
    except ValueError:
        payload = None
    if not isinstance(payload, dict) or payload.get("v") != _ENVELOPE_VERSION:
        # Written by store() or before requests were fingerprinted: nothing to
        # compare against, so keep the historical replay behaviour.
        return IdempotencyClaim("replay", row.response_json)
    stored_hash = payload.get("request_hash")
    if not isinstance(stored_hash, str) or not hmac.compare_digest(stored_hash, request_hash):
        return IdempotencyClaim("mismatch")
    response_json = payload.get("response_json")
    if not isinstance(response_json, str):
        return IdempotencyClaim("in_progress")
    return IdempotencyClaim("replay", response_json)


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
