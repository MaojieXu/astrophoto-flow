"""Lifecycle orchestration shared by the CLI and the local service.

Only this module decides when to spawn, reuse or stop the two owned processes.
It never trusts a pid from outside: every stop path re-verifies the recorded
identity first, so an MCP caller cannot stop an unrelated process.
"""

from __future__ import annotations

import asyncio
import contextlib
import re
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import AsyncIterator

import httpx

from ...contracts.lifecycle import (
    InitResult,
    OperationAction,
    OperationReceipt,
    OperationStatus,
    ProcessIdentity,
    ProcessLaunchSpec,
    ProcessPhase,
    ProcessRecord,
    ProductIdentity,
    ReadyResult,
    RuntimeStatus,
    StopResult,
    WorkspacePaths,
    WorkspaceSettings,
)
from ...core.auth import authorization_header, read_service_token
from ...core.database import check_database_ready, close_database, create_database_engine, upgrade_database
from ...core.errors import WorkbenchError
from ...core.files import atomic_write_json, read_json
from ...core.processes import (
    WorkspaceLock,
    identity_matches,
    identity_state,
    load_process_record,
    save_process_record,
    clear_process_record,
    spawn_detached,
    terminate_owned,
    utc_now,
    wait_for_exit,
)
from ...core.workspace import (
    BACKEND_ROOT,
    build_paths,
    frontend_web_root,
    initialize_workspace,
    load_product_identity,
    load_settings,
    resolve_workspace,
)
from ...interfaces.native.engine import EngineGateway, build_engine_launch_spec, find_free_port

SERVICE_START_TIMEOUT = 90.0
ENGINE_START_TIMEOUT = 240.0
STOP_TIMEOUT = 30.0
OPERATION_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
LOG_TAIL_LINES = 20


@dataclass(frozen=True)
class WorkspaceContext:
    """The three validated facts every lifecycle operation needs."""

    settings: WorkspaceSettings
    paths: WorkspacePaths
    product: ProductIdentity


def load_workspace(workspace: str | Path) -> WorkspaceContext:
    resolved = resolve_workspace(workspace)
    settings = load_settings(resolved)
    return WorkspaceContext(settings=settings, paths=build_paths(settings), product=load_product_identity())


async def initialize_workbench(workspace: str | Path) -> InitResult:
    """Create the workspace, its token and the database baseline exactly once."""

    resolved = resolve_workspace(workspace)
    paths, created = await asyncio.to_thread(initialize_workspace, resolved)
    engine = await asyncio.to_thread(create_database_engine, paths.database_file)
    try:
        revision = await asyncio.to_thread(upgrade_database, engine)
    finally:
        await asyncio.to_thread(close_database, engine)
    product = await asyncio.to_thread(load_product_identity)
    return InitResult(
        status="initialized" if created else "reused",
        version=product.version,
        workspace=str(resolved),
        database_revision=revision,
    )


async def start_workbench(workspace: str | Path, http_client: httpx.AsyncClient | None = None) -> ReadyResult:
    """Start the pair, or reuse the pair that is already confirmed ready."""

    context = await asyncio.to_thread(load_workspace, workspace)
    token = await asyncio.to_thread(read_service_token, context.paths)
    async with _client(http_client) as client:
        lock = WorkspaceLock(context.paths, timeout=120.0)
        await asyncio.to_thread(lock.acquire)
        try:
            existing = await _probe_ready(context, client, token)
            if existing is not None:
                return existing
            await _clear_stale(context, client, token)
            return await _start_processes(context, client, token)
        finally:
            lock.release()


async def get_workbench_status(
    workspace: str | Path, http_client: httpx.AsyncClient | None = None
) -> RuntimeStatus:
    """Report installation plus run state without starting anything."""

    resolved = resolve_workspace(workspace)
    product = await asyncio.to_thread(load_product_identity)
    try:
        context = await asyncio.to_thread(load_workspace, resolved)
    except WorkbenchError:
        return RuntimeStatus(
            status="stopped", version=product.version, workspace=str(resolved), initialized=False
        )
    try:
        record = await asyncio.to_thread(load_process_record, context.paths)
    except WorkbenchError as error:
        return RuntimeStatus(
            status="unknown",
            version=product.version,
            workspace=str(resolved),
            initialized=True,
            message=error.message,
        )
    if record is None:
        return RuntimeStatus(
            status="stopped", version=product.version, workspace=str(resolved), initialized=True
        )
    async with _client(http_client) as client:
        token = await asyncio.to_thread(read_service_token, context.paths)
        alive = identity_matches(record.service) or identity_matches(record.engine)
        if not alive:
            state = "stopped" if record.phase in ("ready", "stopped", "failed") else "unknown"
            return RuntimeStatus(
                status=state,
                version=record.version,
                workspace=str(resolved),
                initialized=True,
                operation_id=record.operation_id,
                message=None if state == "stopped" else "The recorded processes are gone.",
            )
        ready = await _probe_ready(context, client, token)
        if ready is not None:
            return RuntimeStatus(
                status="ready",
                version=ready.version,
                workspace=str(resolved),
                initialized=True,
                operation_id=record.operation_id,
                service_url=ready.service_url,
                web_url=ready.web_url,
            )
        state = "starting" if record.phase == "starting" else ("stopping" if record.phase == "stopping" else "unknown")
        return RuntimeStatus(
            status=state,
            version=record.version,
            workspace=str(resolved),
            initialized=True,
            operation_id=record.operation_id,
            message=record.message or "The owned processes did not answer their health checks.",
        )


async def stop_workbench(
    workspace: str | Path,
    http_client: httpx.AsyncClient | None = None,
    operation_id: str | None = None,
) -> StopResult:
    """Drain the engine, stop both owned processes and keep every file."""

    context = await asyncio.to_thread(load_workspace, workspace)
    token = await asyncio.to_thread(read_service_token, context.paths)
    lock = WorkspaceLock(context.paths, timeout=120.0)
    await asyncio.to_thread(lock.acquire)
    try:
        record = await asyncio.to_thread(load_process_record, context.paths)
        if record is None:
            result = StopResult(
                status="not_running",
                version=context.product.version,
                workspace=str(context.paths.workspace),
                operation_id=operation_id,
            )
            if operation_id:
                await asyncio.to_thread(
                    _write_receipt,
                    context.paths,
                    operation_id,
                    "stop",
                    "succeeded",
                    "not-running",
                    None,
                    result.model_dump(mode="json"),
                )
            return result
        operation = operation_id or f"stop-{uuid.uuid4().hex}"
        _require_operation_id(operation)
        if _require_ownership(record):
            await asyncio.to_thread(clear_process_record, context.paths)
            result = StopResult(
                status="not_running",
                version=context.product.version,
                workspace=str(context.paths.workspace),
                operation_id=operation,
            )
            await asyncio.to_thread(
                _write_receipt,
                context.paths,
                operation,
                "stop",
                "succeeded",
                "not-running",
                None,
                result.model_dump(mode="json"),
            )
            return result
        await _set_phase(context.paths, record, "stopping", operation)
        await asyncio.to_thread(
            _write_receipt, context.paths, operation, "stop", "running", "stopping"
        )
        async with _client(http_client) as client:
            try:
                await _drain_and_stop(context, client, token, record, operation)
            except WorkbenchError as error:
                await _set_phase(context.paths, record, "ready", record.operation_id, message=error.message)
                await asyncio.to_thread(
                    _write_receipt, context.paths, operation, "stop", "failed", "refused", error.message
                )
                raise
        await asyncio.to_thread(clear_process_record, context.paths)
        result = StopResult(
            status="stopped",
            version=context.product.version,
            workspace=str(context.paths.workspace),
            operation_id=operation,
            service_stopped=True,
            engine_stopped=True,
        )
        await asyncio.to_thread(
            _write_receipt, context.paths, operation, "stop", "succeeded", "stopped", None, result.model_dump(mode="json")
        )
        return result
    finally:
        lock.release()


async def begin_stop(workspace: str | Path) -> OperationReceipt:
    """Record an accepted stop; the caller owns running it and recording the end."""

    context = await asyncio.to_thread(load_workspace, workspace)
    operation = f"stop-{uuid.uuid4().hex}"
    return await asyncio.to_thread(
        _write_receipt, context.paths, operation, "stop", "accepted", "queued"
    )


async def stop_engine(
    workspace: str | Path,
    http_client: httpx.AsyncClient,
    gateway: EngineGateway,
    operation_id: str,
) -> StopResult:
    """Stop only the engine so a service can then shut itself down without a deadlock."""

    context = await asyncio.to_thread(load_workspace, workspace)
    record = await asyncio.to_thread(load_process_record, context.paths)
    token = await asyncio.to_thread(read_service_token, context.paths)
    _require_operation_id(operation_id)
    if record is None:
        result = StopResult(
            status="not_running",
            version=context.product.version,
            workspace=str(context.paths.workspace),
            operation_id=operation_id,
        )
        await asyncio.to_thread(
            _write_receipt,
            context.paths,
            operation_id,
            "stop",
            "succeeded",
            "not-running",
            None,
            result.model_dump(mode="json"),
        )
        return result
    await _set_phase(context.paths, record, "stopping", operation_id)
    if _require_ownership(record):
        await asyncio.to_thread(clear_process_record, context.paths)
        result = StopResult(
            status="not_running",
            version=context.product.version,
            workspace=str(context.paths.workspace),
            operation_id=operation_id,
        )
        await asyncio.to_thread(
            _write_receipt,
            context.paths,
            operation_id,
            "stop",
            "succeeded",
            "not-running",
            None,
            result.model_dump(mode="json"),
        )
        return result
    await asyncio.to_thread(_write_receipt, context.paths, operation_id, "stop", "running", "stopping")
    try:
        await _close_engine_admission(record, http_client, token, operation_id, gateway)
        await _terminate_engine(record)
    except WorkbenchError as error:
        await _set_phase(context.paths, record, "ready", record.operation_id, message=error.message)
        await asyncio.to_thread(
            _write_receipt, context.paths, operation_id, "stop", "failed", "refused", error.message
        )
        raise
    await asyncio.to_thread(clear_process_record, context.paths)
    result = StopResult(
        status="stopped",
        version=context.product.version,
        workspace=str(context.paths.workspace),
        operation_id=operation_id,
        service_stopped=False,
        engine_stopped=True,
    )
    await asyncio.to_thread(
        _write_receipt,
        context.paths,
        operation_id,
        "stop",
        "succeeded",
        "stopped",
        None,
        result.model_dump(mode="json"),
    )
    return result


async def get_operation(workspace: str | Path, operation_id: str) -> OperationReceipt:
    """Read a persisted lifecycle receipt; ids are validated before touching disk."""

    context = await asyncio.to_thread(load_workspace, workspace)
    _require_operation_id(operation_id)
    path = context.paths.operations_dir / f"{operation_id}.json"
    if not path.is_file():
        raise WorkbenchError("OPERATION_NOT_FOUND", "No lifecycle operation used that id.", operation_id=operation_id)
    return OperationReceipt.model_validate(await asyncio.to_thread(read_json, path))


def build_service_launch_spec(
    context: WorkspaceContext, port: int, engine_url: str, web_url: str
) -> ProcessLaunchSpec:
    """Fixed service command; the controller picks the port and both urls."""

    command = [
        sys.executable,
        "-m",
        "astrophotoflow.__main__",
        "--workspace",
        str(context.paths.workspace),
        "--port",
        str(port),
        "--engine-url",
        engine_url,
        "--web-url",
        web_url,
    ]
    return ProcessLaunchSpec(
        role="service",
        command=command,
        cwd=BACKEND_ROOT,
        log_path=context.paths.service_log,
        env={
            "ASTROPHOTOFLOW_WORKSPACE": str(context.paths.workspace),
            "PYTHONPATH": str(BACKEND_ROOT),
        },
    )


def _require_operation_id(operation: str) -> None:
    if not OPERATION_PATTERN.match(operation):
        raise WorkbenchError("OPERATION_NOT_FOUND", "Operation ids are lowercase hex prefixed by the action.")


@contextlib.asynccontextmanager
async def _client(existing: httpx.AsyncClient | None) -> AsyncIterator[httpx.AsyncClient]:
    if existing is not None:
        yield existing
        return
    async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as client:
        yield client


async def _probe_ready(
    context: WorkspaceContext, client: httpx.AsyncClient, token: str
) -> ReadyResult | None:
    """Reuse only a pair whose processes, health and editor page all still match."""

    try:
        record = await asyncio.to_thread(load_process_record, context.paths)
    except WorkbenchError:
        return None
    if record is None or record.client is None:
        return None
    if record.version != context.product.version:
        raise WorkbenchError(
            "WORKBENCH_BUSY",
            "A workbench of another version owns this workspace; stop it first.",
            running=record.version,
            installed=context.product.version,
        )
    if not identity_matches(record.service) or not identity_matches(record.engine):
        return None
    health = await _fetch_health(client, record.client.service_url)
    if health is None:
        return None
    if health["version"] != context.product.version or health["workspace"] != str(context.paths.workspace):
        raise WorkbenchError(
            "WORKBENCH_IDENTITY_MISMATCH", "The running service belongs to another workspace or version."
        )
    gateway = EngineGateway(record.client.web_url, token, client)
    try:
        await gateway.web_page()
    except WorkbenchError:
        return None
    return record.client.model_copy(update={"reused": True})


async def _clear_stale(context: WorkspaceContext, client: httpx.AsyncClient, token: str) -> None:
    """Terminate an owned pair that is alive but cannot serve, then start over."""

    record = await asyncio.to_thread(load_process_record, context.paths)
    if record is None:
        return
    owned = [identity for identity in (record.engine, record.service) if identity_matches(identity)]
    if not owned:
        await asyncio.to_thread(clear_process_record, context.paths)
        return
    for identity in owned:
        await asyncio.to_thread(terminate_owned, identity, STOP_TIMEOUT)
    await asyncio.to_thread(clear_process_record, context.paths)


async def _start_processes(
    context: WorkspaceContext, client: httpx.AsyncClient, token: str
) -> ReadyResult:
    paths = context.paths
    operation = f"start-{uuid.uuid4().hex}"
    record = ProcessRecord(
        workspace=str(paths.workspace),
        version=context.product.version,
        operation_id=operation,
        phase="starting",
        started_at=utc_now(),
    )
    await asyncio.to_thread(save_process_record, paths, record)
    await asyncio.to_thread(_write_receipt, paths, operation, "start", "running", "starting")
    host = context.settings.service_host
    service_port = await asyncio.to_thread(find_free_port, host)
    engine_port = await asyncio.to_thread(find_free_port, host)
    while engine_port == service_port:
        engine_port = await asyncio.to_thread(find_free_port, host)
    service_url = f"http://{host}:{service_port}"
    engine_url = f"http://{context.settings.engine_host}:{engine_port}"
    web_url = f"{engine_url}/"
    try:
        web_root = await asyncio.to_thread(frontend_web_root)
        record = record.model_copy(
            update={
                "service": await asyncio.to_thread(
                    spawn_detached, build_service_launch_spec(context, service_port, engine_url, web_url)
                )
            }
        )
        await asyncio.to_thread(save_process_record, paths, record)
        health = await _await_service(context, client, record.service, service_url)
        record = record.model_copy(
            update={
                "engine": await asyncio.to_thread(
                    spawn_detached, build_engine_launch_spec(BACKEND_ROOT, paths, engine_port, web_root)
                )
            }
        )
        await asyncio.to_thread(save_process_record, paths, record)
        gateway = EngineGateway(engine_url, token, client)
        await _await_engine(context, gateway, record.engine)
        ready = ReadyResult(
            version=health["version"],
            workspace=str(paths.workspace),
            service_url=service_url,
            web_url=web_url,
            reused=False,
        )
        record = record.model_copy(update={"phase": "ready", "client": ready})
        await asyncio.to_thread(save_process_record, paths, record)
        await asyncio.to_thread(
            _write_receipt, paths, operation, "start", "succeeded", "ready", None, ready.model_dump(mode="json")
        )
        return ready
    except BaseException as error:
        await _fail_start(context, record, operation, error)
        raise


async def _fail_start(
    context: WorkspaceContext, record: ProcessRecord, operation: str, error: BaseException
) -> None:
    """Stop what this start spawned, keep the logs and record what is unknown."""

    message = error.message if isinstance(error, WorkbenchError) else f"{type(error).__name__}: {error}"
    leftover = False
    for identity in (record.engine, record.service):
        if not identity_matches(identity):
            continue
        try:
            if not await asyncio.to_thread(terminate_owned, identity, STOP_TIMEOUT):
                leftover = True
        except WorkbenchError:
            leftover = True
    phase: ProcessPhase = "unknown" if leftover else "failed"
    await asyncio.to_thread(
        save_process_record,
        context.paths,
        record.model_copy(update={"phase": phase, "message": message}),
    )
    await asyncio.to_thread(_write_receipt, context.paths, operation, "start", "failed", phase, message)


async def _await_service(
    context: WorkspaceContext, client: httpx.AsyncClient, identity: ProcessIdentity, service_url: str
) -> dict:
    """Wait for the service health document and verify it is this workspace."""

    deadline = time.monotonic() + SERVICE_START_TIMEOUT
    while time.monotonic() < deadline:
        if not identity_matches(identity):
            raise WorkbenchError(
                "WORKBENCH_START_FAILED",
                "The workbench service exited during startup.",
                log=_tail_log(context.paths.service_log),
            )
        health = await _fetch_health(client, service_url)
        if health is not None:
            if health["workspace"] != str(context.paths.workspace):
                raise WorkbenchError(
                    "WORKBENCH_IDENTITY_MISMATCH", "The service announced another workspace."
                )
            return health
        await asyncio.sleep(0.25)
    raise WorkbenchError(
        "WORKBENCH_START_FAILED",
        "The workbench service did not become healthy.",
        log=_tail_log(context.paths.service_log),
    )


async def _await_engine(context: WorkspaceContext, gateway: EngineGateway, identity: ProcessIdentity) -> None:
    """Require native readiness, a non-empty node catalog and the editor page."""

    deadline = time.monotonic() + ENGINE_START_TIMEOUT
    ready = False
    while time.monotonic() < deadline:
        if not identity_matches(identity):
            raise WorkbenchError(
                "WORKBENCH_START_FAILED",
                "The native engine exited during startup.",
                log=_tail_log(context.paths.engine_log),
            )
        if await gateway.is_ready():
            ready = True
            break
        await asyncio.sleep(0.5)
    if not ready:
        raise WorkbenchError(
            "WORKBENCH_START_FAILED",
            "The native engine did not become ready.",
            log=_tail_log(context.paths.engine_log),
        )
    catalog = await gateway.node_catalog()
    if not catalog:
        raise WorkbenchError("WORKBENCH_START_FAILED", "The native engine reported an empty node catalog.")
    await gateway.web_page()


def _require_ownership(record: ProcessRecord) -> bool:
    """Refuse a stop whose pid no longer belongs to this workspace.

    Returns ``True`` when both recorded processes are already gone, which lets
    the caller report ``not_running`` instead of pretending a stop happened.
    """

    states = (identity_state(record.service), identity_state(record.engine))
    if "foreign" in states:
        raise WorkbenchError(
            "PROCESS_IDENTITY_MISMATCH",
            "A recorded pid now belongs to another process, so the stop is refused.",
            operation_id=record.operation_id,
        )
    return all(state == "gone" for state in states)


async def _close_engine_admission(
    record: ProcessRecord,
    client: httpx.AsyncClient,
    token: str,
    operation: str,
    gateway: EngineGateway | None = None,
) -> None:
    """Refuse new prompts, then refuse the stop itself if work is still in flight."""

    if not identity_matches(record.engine):
        return
    if record.client is None:
        raise WorkbenchError(
            "WORKBENCH_BUSY",
            "The engine of an incomplete start cannot confirm a safe stop; inspect the logs.",
            operation_id=record.operation_id,
        )
    native = gateway or EngineGateway(record.client.web_url, token, client)
    try:
        status = await native.prepare_stop(operation)
    except WorkbenchError as error:
        if error.code == "ENGINE_BUSY":
            with contextlib.suppress(WorkbenchError):
                await native.cancel_stop(operation)
            raise
        status = None
    if status is not None and (status.pending_tasks or status.running_tasks):
        with contextlib.suppress(WorkbenchError):
            await native.cancel_stop(operation)
        raise WorkbenchError(
            "ENGINE_BUSY",
            "The engine still has queued or running work; stop refused.",
            pending_tasks=status.pending_tasks,
            running_tasks=status.running_tasks,
        )


async def _terminate_engine(record: ProcessRecord) -> None:
    """Terminate the engine only when the recorded identity still matches."""

    if not identity_matches(record.engine):
        return
    await asyncio.to_thread(terminate_owned, record.engine, STOP_TIMEOUT)
    if identity_matches(record.engine):
        raise WorkbenchError("WORKBENCH_BUSY", "The native engine did not exit.")


async def _drain_and_stop(
    context: WorkspaceContext,
    client: httpx.AsyncClient,
    token: str,
    record: ProcessRecord,
    operation: str,
) -> None:
    """Close engine admission, drain the queue, stop the service, then the engine."""

    await _close_engine_admission(record, client, token, operation)
    if identity_matches(record.service) and record.client is not None:
        await _request_service_shutdown(client, record.client.service_url, token)
        stopped = await asyncio.to_thread(wait_for_exit, record.service, STOP_TIMEOUT)
        if not stopped:
            await asyncio.to_thread(terminate_owned, record.service, STOP_TIMEOUT)
        if not await asyncio.to_thread(wait_for_exit, record.service, 5.0):
            raise WorkbenchError("WORKBENCH_BUSY", "The workbench service did not exit.")
    elif identity_matches(record.service):
        await asyncio.to_thread(terminate_owned, record.service, STOP_TIMEOUT)
    await _terminate_engine(record)


async def _fetch_health(client: httpx.AsyncClient, service_url: str) -> dict | None:
    try:
        response = await client.get(f"{service_url}/health", timeout=3.0)
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    if payload.get("status") != "ok":
        return None
    for key in ("version", "workspace", "service_url", "web_url"):
        if not isinstance(payload.get(key), str):
            return None
    return payload


async def _request_service_shutdown(client: httpx.AsyncClient, service_url: str, token: str) -> None:
    headers = authorization_header(token)
    with contextlib.suppress(httpx.HTTPError):
        await client.post(f"{service_url}/internal/drain", headers=headers, timeout=10.0)
    with contextlib.suppress(httpx.HTTPError):
        await client.post(f"{service_url}/internal/shutdown", headers=headers, timeout=10.0)


async def _set_phase(
    paths: WorkspacePaths,
    record: ProcessRecord,
    phase: ProcessPhase,
    operation: str | None = None,
    message: str | None = None,
) -> None:
    updated = record.model_copy(
        update={
            "phase": phase,
            "operation_id": operation or record.operation_id,
            "message": message,
        }
    )
    await asyncio.to_thread(save_process_record, paths, updated)


def _write_receipt(
    paths: WorkspacePaths,
    operation: str,
    action: OperationAction,
    status: OperationStatus,
    phase: str,
    message: str | None = None,
    result: dict | None = None,
) -> OperationReceipt:
    _require_operation_id(operation)
    now = utc_now()
    path = paths.operations_dir / f"{operation}.json"
    previous = None
    if path.is_file():
        with contextlib.suppress(WorkbenchError):
            previous = OperationReceipt.model_validate(read_json(path))
    receipt = OperationReceipt(
        operation_id=operation,
        action=action,
        status=status,
        phase=phase,
        workspace=str(paths.workspace),
        created_at=previous.created_at if previous else now,
        updated_at=now,
        message=message,
        result=result,
    )
    atomic_write_json(path, receipt.model_dump(mode="json"))
    return receipt


def _tail_log(path: Path) -> list[str]:
    """The last diagnostic lines, so a failed start is debuggable from its result."""

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return lines[-LOG_TAIL_LINES:]


def database_revision(paths: WorkspacePaths) -> str:
    """Health reports the schema revision it actually reached."""

    engine = create_database_engine(paths.database_file)
    try:
        return check_database_ready(engine)
    finally:
        close_database(engine)
