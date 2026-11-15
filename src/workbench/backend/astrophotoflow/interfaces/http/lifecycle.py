"""Lifecycle routes: init, start, stop, status and operation receipts.

Every mutating route delegates to ``interfaces.application.workbench``; this
module only validates input, selecting response contracts and status codes.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Request

from ...contracts.lifecycle import (
    InitResult,
    OperationReceipt,
    ReadyResult,
    RuntimeStatus,
)
from ...core.errors import WorkbenchError
from ...interfaces.application import workbench as application
from .runtime import ServiceRuntime, get_runtime, require_active
from .schema import DrainResult, ServiceHealth, ShutdownResult

health_router = APIRouter()
router = APIRouter()
internal_router = APIRouter()


@health_router.get("/health", response_model=ServiceHealth, operation_id="getServiceHealth")
async def get_service_health(runtime: ServiceRuntime = Depends(get_runtime)) -> ServiceHealth:
    """Prove the service can serve this workspace; the controller polls it."""

    return ServiceHealth(
        version=runtime.context.product.version,
        workspace=str(runtime.context.paths.workspace),
        service_url=runtime.context.service_url,
        web_url=runtime.context.web_url,
        database=runtime.database_revision,
    )


@router.post("/api/v1/workbench/init", response_model=InitResult, operation_id="initializeWorkbench")
async def initialize_workbench(runtime: ServiceRuntime = Depends(get_runtime)) -> InitResult:
    """Re-run initialization on an existing workspace without losing data."""

    return await application.initialize_workbench(runtime.context.paths.workspace)


@router.post("/api/v1/workbench/start", response_model=ReadyResult, operation_id="startWorkbench")
async def start_workbench(runtime: ServiceRuntime = Depends(get_runtime)) -> ReadyResult:
    """Reuse or restart the pair for this workspace."""

    return await application.start_workbench(runtime.context.paths.workspace, runtime.client)


@router.get("/api/v1/workbench/status", response_model=RuntimeStatus, operation_id="getWorkbenchStatus")
async def get_workbench_status(runtime: ServiceRuntime = Depends(get_runtime)) -> RuntimeStatus:
    return await application.get_workbench_status(runtime.context.paths.workspace, runtime.client)


@router.post("/api/v1/workbench/stop", response_model=OperationReceipt, operation_id="stopWorkbench")
async def stop_workbench(runtime: ServiceRuntime = Depends(get_runtime)) -> OperationReceipt:
    """Accept the stop; this service stops the engine, records it, then exits."""

    if runtime.stop_task is not None:
        raise WorkbenchError("WORKBENCH_ALREADY_STOPPING", "A stop is already in progress for this workbench.")
    receipt = await application.begin_stop(runtime.context.paths.workspace)
    runtime.stop_task = asyncio.create_task(_finish_stop(runtime, receipt.operation_id))
    return receipt


@router.get(
    "/api/v1/workbench/operations/{operation_id}",
    response_model=OperationReceipt,
    operation_id="getWorkbenchOperation",
)
async def get_workbench_operation(
    operation_id: str, runtime: ServiceRuntime = Depends(get_runtime)
) -> OperationReceipt:
    return await application.get_operation(runtime.context.paths.workspace, operation_id)


async def _finish_stop(runtime: ServiceRuntime, operation_id: str) -> None:
    """Run inside the service: stop the engine, then ask uvicorn to exit."""

    try:
        await application.stop_engine(
            runtime.context.paths.workspace, runtime.client, runtime.gateway, operation_id
        )
    except WorkbenchError:
        runtime.stop_task = None
        return
    runtime.draining = True
    stop = runtime.request_shutdown
    if stop is not None:
        asyncio.get_running_loop().call_later(0.2, stop)


@internal_router.post(
    "/internal/drain", response_model=DrainResult, operation_id="drainService", include_in_schema=False
)
async def drain_service(runtime: ServiceRuntime = Depends(get_runtime)) -> DrainResult:
    runtime.draining = True
    return DrainResult()


@internal_router.post(
    "/internal/shutdown",
    response_model=ShutdownResult,
    operation_id="shutdownService",
    include_in_schema=False,
)
async def shutdown_service(request: Request, _: ServiceRuntime = Depends(require_active)) -> ShutdownResult:
    """Answer first, then let uvicorn exit so the controller sees a clean stop."""

    stop = getattr(request.app.state, "request_shutdown", None)
    if stop is None:
        from ...core.errors import WorkbenchError

        raise WorkbenchError("SERVICE_UNAVAILABLE", "The service cannot schedule its own shutdown.")
    asyncio.get_running_loop().call_later(0.2, stop)
    return ShutdownResult()
