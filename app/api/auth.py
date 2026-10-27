"""R-API-1: loopback binds are open; anything else needs the static bearer token."""

import hmac

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.orchestrator import PipelineOrchestrator

LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_bearer = HTTPBearer(auto_error=False)


def require_token(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    if settings.API_HOST in LOOPBACK_HOSTS:
        return
    # No token configured on a non-loopback bind fails closed: nobody gets in.
    if (
        not settings.API_TOKEN
        or creds is None
        or not hmac.compare_digest(creds.credentials, settings.API_TOKEN)
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
