"""The local service application: auth, lifecycle and node routes.

The service owns business data and lifecycle receipts. It reads the engine over
HTTP through its native API and never touches the engine's database or queue
objects directly.
"""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager
from typing import AsyncIterator

import httpx
from fastapi import Depends, FastAPI, Request, Security
from fastapi.responses import JSONResponse

from ...contracts.lifecycle import StartupContext
from ...core.auth import read_service_token
from ...core.database import check_database_ready, close_database, create_database_engine
from ...core.errors import WorkbenchError, http_status
from ...core.workspace import load_product_identity
from ...interfaces.native.engine import EngineGateway
from .lifecycle import health_router, internal_router, router as lifecycle_router
from .nodes import router as nodes_router
from .runtime import ServiceRuntime, authenticate, require_active

STOP_GRACE_SECONDS = 60.0


def create_app(
    settings: object | None = None, startup_context: StartupContext | None = None
) -> FastAPI:
    """Build the app; ``startup_context`` is set by the controller's service command."""

    version = startup_context.product.version if startup_context else load_product_identity().version
    app = FastAPI(title="AstroPhotoFlow Workbench", version=version, lifespan=_lifespan)
    app.state.settings = settings
    app.state.startup_context = startup_context
    app.state.runtime = None

    @app.exception_handler(WorkbenchError)
    async def workbench_error_handler(_: Request, error: WorkbenchError) -> JSONResponse:
        return JSONResponse(status_code=http_status(error.code), content=error.envelope().model_dump(mode="json"))

    app.include_router(health_router)
    app.include_router(lifecycle_router, dependencies=[Security(authenticate), Depends(require_active)])
    app.include_router(nodes_router, dependencies=[Security(authenticate), Depends(require_active)])
    app.include_router(internal_router, dependencies=[Security(authenticate)])
    return app


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    context: StartupContext | None = app.state.startup_context
    if context is None:
        raise RuntimeError("The service must be started by the workbench controller.")
    token = read_service_token(context.paths)
    client = httpx.AsyncClient(follow_redirects=False, trust_env=False)
    database_engine = create_database_engine(context.paths.database_file)
    try:
        revision = await asyncio.to_thread(check_database_ready, database_engine)
    except BaseException:
        await client.aclose()
        close_database(database_engine)
        raise
    app.state.runtime = ServiceRuntime(
        context=context,
        client=client,
        database_engine=database_engine,
        gateway=EngineGateway(context.engine_url, token, client),
        database_revision=revision,
        token=token,
        request_shutdown=getattr(app.state, "request_shutdown", None),
    )
    try:
        yield
    finally:
        stop_task = app.state.runtime.stop_task if app.state.runtime else None
        app.state.runtime = None
        if stop_task is not None:
            with contextlib.suppress(BaseException):
                await asyncio.wait_for(asyncio.shield(stop_task), timeout=STOP_GRACE_SECONDS)
        await client.aclose()
        close_database(database_engine)
