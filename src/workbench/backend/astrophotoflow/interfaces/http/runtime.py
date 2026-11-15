"""Request-scoped runtime objects and the auth dependencies.

Keeping these here (rather than in ``app``) lets route modules depend on the
runtime without importing the application factory and creating a cycle.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import httpx
from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ...contracts.lifecycle import StartupContext, WorkspacePaths
from ...core.auth import verify_token
from ...core.errors import WorkbenchError
from ...interfaces.native.engine import EngineGateway

# Declared as a scheme so the exported OpenAPI document states the auth requirement.
bearer_scheme = HTTPBearer(auto_error=False, scheme_name="WorkbenchBearer")


@dataclass
class ServiceRuntime:
    """The objects a request may use; built once by the lifespan handler."""

    context: StartupContext
    client: httpx.AsyncClient
    database_engine: object
    gateway: EngineGateway
    database_revision: str
    token: str = field(repr=False)
    draining: bool = False
    stop_task: object | None = None
    request_shutdown: Callable[[], None] | None = None

    def paths(self) -> WorkspacePaths:
        return self.context.paths


def get_runtime(request: Request) -> ServiceRuntime:
    runtime = getattr(request.app.state, "runtime", None)
    if runtime is None:
        raise WorkbenchError("SERVICE_UNAVAILABLE", "The service is not ready.")
    return runtime


async def authenticate(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    runtime: ServiceRuntime = Depends(get_runtime),
) -> None:
    """Require the workspace token on every route that is not the health check."""

    provided = credentials.credentials if credentials is not None else None
    if not verify_token(provided, runtime.token):
        raise WorkbenchError("UNAUTHORIZED", "A valid workspace bearer token is required.")


async def require_active(runtime: ServiceRuntime = Depends(get_runtime)) -> None:
    """Reject new lifecycle work once a stop is draining the service."""

    if runtime.draining:
        raise WorkbenchError("SERVICE_DRAINING", "The workbench is stopping.")
