"""R-API-1: loopback binds are open; anything else needs the static bearer token."""

import hmac

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.orchestrator import PipelineOrchestrator

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
TOKEN_COOKIE = "mr_token"  # noqa: S105 (cookie name, not a secret)
_bearer = HTTPBearer(auto_error=False)


def require_token(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    if settings.API_HOST in LOOPBACK_HOSTS:
        return
    # No token configured on a non-loopback bind fails closed: nobody gets in.
    # Browsers can't set headers on navigation, so the web UI login stores the token in a cookie.
    supplied = creds.credentials if creds else request.cookies.get(TOKEN_COOKIE)
    if (
        not settings.API_TOKEN
        or supplied is None
        or not hmac.compare_digest(supplied, settings.API_TOKEN)
    ):
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
