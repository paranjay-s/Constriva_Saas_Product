"""Short-lived signed tokens for requests that cannot carry an Authorization header.

A browser cannot attach the session's Bearer token to an <iframe>, an <img> or a file
download. Such a request is authorised by a token placed in its URL instead:

    token = sign({"sub": user_id, "job": job_id}, audience="plan3d-embed", secret=..., ttl_s=3600)
    claims = verify(token, audience="plan3d-embed", secret=...)      # raises TokenError

The token is `payload.signature`: the claims as base64url JSON, and an HMAC-SHA256 of that
text. It says who it was issued to, what for (`aud`) and until when (`exp`). It cannot be
altered or extended without the server's secret, and a token issued for one purpose is
refused for another. Keep the lifetime short: a URL can end up in a log.
"""

import base64
import hashlib
import hmac
import json
import time
from typing import Any


class TokenError(ValueError):
    """The token is malformed, forged, for another purpose, or expired."""


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _signature(payload: str, secret: bytes) -> str:
    return _b64(hmac.new(secret, payload.encode("ascii"), hashlib.sha256).digest())


def sign(
    claims: dict[str, Any], *, audience: str, secret: bytes, ttl_s: int, now: float | None = None
) -> str:
    if not secret:
        raise ValueError("a signing secret is required")
    issued = int(now if now is not None else time.time())
    body = {**claims, "aud": audience, "exp": issued + int(ttl_s)}
    payload = _b64(json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return f"{payload}.{_signature(payload, secret)}"


def verify(token: str, *, audience: str, secret: bytes, now: float | None = None) -> dict[str, Any]:
    """The claims of a valid token. Raises TokenError otherwise."""
    payload, dot, signature = str(token or "").partition(".")
    if not dot or not payload or not signature:
        raise TokenError("malformed token")
    if not secret or not hmac.compare_digest(signature, _signature(payload, secret)):
        raise TokenError("bad signature")
    try:
        claims = json.loads(_unb64(payload))
    except (ValueError, UnicodeDecodeError) as e:
        raise TokenError("unreadable token") from e
    if not isinstance(claims, dict) or claims.get("aud") != audience:
        raise TokenError("token is for another purpose")
    expires = claims.get("exp")
    if not isinstance(expires, int) or expires <= (now if now is not None else time.time()):
        raise TokenError("token has expired")
    return claims
