"""R-API-1: loopback binds are open; anything else needs the static bearer token."""

import hmac
import ipaddress

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.orchestrator import PipelineOrchestrator

TOKEN_COOKIE = "mr_token"  # noqa: S105 (cookie name, not a secret)
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
    supplied = creds.credentials if creds else request.cookies.get(TOKEN_COOKIE)
    if supplied is None or not token_matches(supplied, settings.API_TOKEN):
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
