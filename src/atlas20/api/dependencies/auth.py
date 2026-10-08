"""API key and JWT authentication dependency."""

import base64
import binascii
import hashlib
import hmac
import json
import re
import time
from typing import Any, cast

from fastapi import Header, HTTPException

from atlas20.api.settings import Settings, get_settings


class JwtAuthError(Exception):
    """Raised when a bearer token cannot be accepted."""


_BASE64URL_SEGMENT = re.compile(r"[A-Za-z0-9_-]*")


def _base64url_decode(value: str) -> bytes:
    # JWS segments are unpadded base64url (RFC 7515 section 2). The stdlib
    # decoder silently drops foreign characters and ignores trailing bits, so
    # only accept the canonical spelling: one token, one string.
    if _BASE64URL_SEGMENT.fullmatch(value) is None:
        raise JwtAuthError
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except binascii.Error as exc:
        raise JwtAuthError from exc
    if base64.urlsafe_b64encode(decoded).rstrip(b"=").decode("ascii") != value:
        raise JwtAuthError
    return decoded


def _json_part(value: str) -> dict[str, Any]:
    try:
        parsed = json.loads(_base64url_decode(value).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, JwtAuthError) as exc:
        raise JwtAuthError from exc
    if not isinstance(parsed, dict):
        raise JwtAuthError
    return cast(dict[str, Any], parsed)


def _numeric_claim(claims: dict[str, Any], name: str) -> float | None:
    value = claims.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise JwtAuthError
    return float(value)


def _secrets_equal(left: str, right: str) -> bool:
    # compare_digest raises TypeError for non-ASCII str (a 500); bytes compare fine.
    return hmac.compare_digest(left.encode("utf-8", "surrogatepass"), right.encode("utf-8", "surrogatepass"))


def _audience_matches(value: Any, expected: str) -> bool:
    if isinstance(value, str):
        return _secrets_equal(value, expected)
    if isinstance(value, list):
        return any(isinstance(item, str) and _secrets_equal(item, expected) for item in value)
    return False


def _validate_claims(claims: dict[str, Any], settings: Settings) -> None:
    now = time.time()
    leeway = settings.jwt_leeway_seconds
    exp = _numeric_claim(claims, "exp")
    if exp is None or exp + leeway < now:
        raise JwtAuthError
    nbf = _numeric_claim(claims, "nbf")
    if nbf is not None and nbf - leeway > now:
        raise JwtAuthError
    iat = _numeric_claim(claims, "iat")
    if iat is not None and iat - leeway > now:
        raise JwtAuthError
    if settings.jwt_issuer is not None and claims.get("iss") != settings.jwt_issuer:
        raise JwtAuthError
    if settings.jwt_audience is not None and not _audience_matches(claims.get("aud"), settings.jwt_audience):
        raise JwtAuthError


def _verify_hs256_jwt(token: str, settings: Settings) -> dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3 or any(part == "" for part in parts):
        raise JwtAuthError
    header = _json_part(parts[0])
    if header.get("alg") != "HS256":
        raise JwtAuthError
    try:
        signing_input = f"{parts[0]}.{parts[1]}".encode("ascii")
    except UnicodeEncodeError as exc:
        raise JwtAuthError from exc
    signing_key = settings.jwt_signing_key()
    if not signing_key.strip():
        # An empty HMAC key lets anyone mint valid tokens; never accept one.
        raise JwtAuthError
    expected_signature = hmac.new(signing_key.encode(), signing_input, hashlib.sha256).digest()
    if not hmac.compare_digest(_base64url_decode(parts[2]), expected_signature):
        raise JwtAuthError
    claims = _json_part(parts[1])
    _validate_claims(claims, settings)
    return claims


def _jwt_principal(claims: dict[str, Any]) -> str:
    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        subject = "anonymous"
    issuer = claims.get("iss")
    issuer_text = issuer if isinstance(issuer, str) else ""
    fingerprint = hashlib.sha256(f"{issuer_text}:{subject}".encode()).hexdigest()[:8]
    return "jwt-" + fingerprint


def _verify_bearer(authorization: str, settings: Settings) -> str:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise JwtAuthError
    return _jwt_principal(_verify_hs256_jwt(token.strip(), settings))


def _missing_auth_message(settings: Settings) -> str:
    if settings.api_keys and settings.jwt_auth_enabled:
        return "X-API-Key or Bearer token required"
    if settings.jwt_auth_enabled:
        return "Bearer token required"
    return "X-API-Key header required"


def verify_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    return _authenticate(x_api_key, authorization, get_settings())


def authenticated_principal(x_api_key: str | None, authorization: str | None) -> str | None:
    """Non-secret principal the credentials verify as; None when auth is off or they fail."""
    settings = get_settings()
    if not settings.api_keys and not settings.jwt_auth_enabled:
        return None
    try:
        return _authenticate(x_api_key, authorization, settings)
    except HTTPException:
        return None


def _authenticate(x_api_key: str | None, authorization: str | None, settings: Settings) -> str:
    if not settings.api_keys and not settings.jwt_auth_enabled:
        return "anonymous"
    if x_api_key is None:
        api_key_error = None
    else:
        api_key_error = HTTPException(status_code=401, detail="invalid API key")
        for api_key in settings.api_keys:
            if _secrets_equal(x_api_key, api_key.get_secret_value()):
                return "client-" + hashlib.sha256(x_api_key.encode()).hexdigest()[:8]
    if settings.jwt_auth_enabled and authorization is not None:
        try:
            return _verify_bearer(authorization, settings)
        except JwtAuthError as exc:
            if x_api_key is None:
                raise HTTPException(status_code=401, detail="invalid bearer token") from exc
    if api_key_error is not None:
        raise api_key_error
    raise HTTPException(status_code=401, detail=_missing_auth_message(settings))
