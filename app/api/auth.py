"""R-API-1: loopback binds are open; anything else needs the static bearer token."""

import hashlib
import hmac
import ipaddress
import time

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.orchestrator import PipelineOrchestrator

TOKEN_COOKIE = "mr_token"  # noqa: S105 (cookie name, not a secret)
SESSION_MAX_AGE = 7 * 24 * 3600
_bearer = HTTPBearer(auto_error=False)


def is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def token_matches(supplied: str, expected: str) -> bool:
    """Constant-time compare on bytes: str compare_digest raises TypeError on non-ASCII."""
    return bool(expected) and hmac.compare_digest(supplied.encode(), expected.encode())


def _sign(issued: str) -> str:
    return hmac.new(
        settings.API_TOKEN.encode(), issued.encode(), hashlib.sha256
    ).hexdigest()


def make_session() -> str:
    """UI cookie value: `<issued-at>.<hmac>`; the raw token never leaves the login POST."""
    issued = str(int(time.time()))
    return f"{issued}.{_sign(issued)}"


def session_valid(value: str) -> bool:
    """Signed with the API token (rotating it logs everyone out) and expires after SESSION_MAX_AGE."""
    issued, _, sig = value.partition(".")
    if not (settings.API_TOKEN and issued.isdigit() and len(issued) < 15):
        return False
    age = time.time() - int(issued)
    return 0 <= age <= SESSION_MAX_AGE and token_matches(sig, _sign(issued))


def check_bind_security(host: str, token: str) -> None:
    """R-API-1 at startup: an exposed bind without a token would 401 every secured route."""
    if not is_loopback(host) and not token:
        raise RuntimeError(
            f"API_HOST={host} is not loopback: set MR_API_TOKEN (or bind 127.0.0.1)"
        )


def require_token(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    if is_loopback(settings.API_HOST):
        return
    # No token configured on a non-loopback bind fails closed: nobody gets in.
    # Browsers can't set headers on navigation, so the web UI login stores the token in a cookie.
    cookie = request.cookies.get(TOKEN_COOKIE)
    ok = (
        token_matches(creds.credentials, settings.API_TOKEN)
        if creds
        else cookie is not None and session_valid(cookie)
    )
    if not ok:
        raise HTTPException(
            401,
            "Invalid or missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def json_only(request: Request) -> None:
    """CSRF guard: a cross-site form cannot send application/json without a preflight."""
    if (
        request.headers.get("content-type", "").split(";")[0].strip()
        != "application/json"
    ):
        raise HTTPException(415, "Content-Type must be application/json")


def get_orchestrator(request: Request) -> PipelineOrchestrator:
    orchestrator = getattr(request.app.state, "orchestrator", None)
    if orchestrator is None:
        raise HTTPException(503, "Pipeline is not running")
    return orchestrator
