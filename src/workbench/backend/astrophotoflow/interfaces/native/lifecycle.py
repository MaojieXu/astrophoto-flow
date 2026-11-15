"""The only module that touches ComfyUI internals.

It adds an admission gate in front of the native prompt route, exposes private
lifecycle routes the controller authorizes with the workspace token, and reads
the engine's own queue counters. Graph saving, history and execution stay in
ComfyUI; nothing here re-implements them.
"""

from __future__ import annotations

import asyncio
import functools
from typing import TYPE_CHECKING, Any

from aiohttp import web

from ...contracts.lifecycle import EngineLifecycleStatus, WorkspacePaths
from ...core.auth import read_service_token, verify_bearer
from ...core.errors import WorkbenchError
from ...core.workspace import build_paths, load_settings

if TYPE_CHECKING:  # pragma: no cover - typing only, the engine imports us
    from server import PromptServer

ADMISSION_PATHS = frozenset({"/prompt", "/api/prompt"})
LIFECYCLE_PREFIX = "/astrophotoflow/lifecycle"
DRAIN_TIMEOUT = 10.0
WORKSPACE_ENV = "ASTROPHOTOFLOW_WORKSPACE"


class EngineAdmission:
    """Closed admission rejects new prompts while an operator stops the engine."""

    def __init__(self) -> None:
        self._open = True
        self._in_flight = 0
        self._idle = asyncio.Event()
        self._idle.set()
        self.operation_id: str | None = None

    @property
    def is_open(self) -> bool:
        return self._open

    @property
    def in_flight(self) -> int:
        return self._in_flight

    def enter(self) -> None:
        self._in_flight += 1
        self._idle.clear()

    def leave(self) -> None:
        self._in_flight = max(0, self._in_flight - 1)
        if self._in_flight == 0:
            self._idle.set()

    def close(self, operation_id: str) -> None:
        self._open = False
        self.operation_id = operation_id

    def open(self) -> None:
        self._open = True
        self.operation_id = None

    async def wait_idle(self, timeout: float) -> bool:
        try:
            await asyncio.wait_for(self._idle.wait(), timeout=timeout)
        except (TimeoutError, asyncio.TimeoutError):
            return False
        return True


_STATE = EngineAdmission()
_registered = False


def create_admission_middleware(state: EngineAdmission):
    """Wrap only prompt submission: every other native route keeps its behaviour."""

    @web.middleware
    async def admission_middleware(request: web.Request, handler):
        if request.method == "POST" and request.path in ADMISSION_PATHS:
            if not state.is_open:
                return _error(503, "ENGINE_DRAINING", "The workbench is stopping and accepts no new prompts.")
            state.enter()
            try:
                return await handler(request)
            finally:
                state.leave()
        return await handler(request)

    return admission_middleware


@functools.lru_cache(maxsize=1)
def _workspace_paths() -> WorkspacePaths:
    import os

    workspace = os.environ.get(WORKSPACE_ENV)
    if not workspace:
        raise WorkbenchError("ENGINE_LIFECYCLE_UNAVAILABLE", "The engine was started without a workspace.")
    return build_paths(load_settings(workspace))


def _authorize(request: web.Request) -> None:
    token = read_service_token(_workspace_paths())
    if not verify_bearer(request.headers.get("Authorization"), token):
        raise WorkbenchError("UNAUTHORIZED", "The native lifecycle route requires the workspace token.")


def _error(status: int, code: str, message: str) -> web.Response:
    return web.json_response({"error": {"code": code, "message": message, "fields": {}}}, status=status)


def _error_response(error: WorkbenchError) -> web.Response:
    from ...core.errors import http_status

    return _error(http_status(error.code), error.code, error.message)


def _counters(server: PromptServer) -> tuple[int, int]:
    queue = server.prompt_queue
    pending = int(queue.get_tasks_remaining())
    running = len(queue.get_current_queue_volatile()[0])
    return pending, running


def _status_payload(state: EngineAdmission, server: PromptServer) -> dict[str, Any]:
    pending, running = _counters(server)
    return EngineLifecycleStatus(
        admission="open" if state.is_open else "closed",
        in_flight=state.in_flight,
        pending_tasks=pending,
        running_tasks=running,
    ).model_dump(mode="json")


def register_native_lifecycle(server: PromptServer) -> EngineAdmission:
    """Install the admission gate and private routes once per engine process."""

    global _registered
    if _registered:
        return _STATE
    _registered = True
    server.app.middlewares.append(create_admission_middleware(_STATE))
    routes = server.routes

    async def status(request: web.Request) -> web.Response:
        try:
            _authorize(request)
        except WorkbenchError as error:
            return _error_response(error)
        return web.json_response(_status_payload(_STATE, server))

    async def prepare_stop(request: web.Request) -> web.Response:
        try:
            _authorize(request)
            body = await request.json()
            operation_id = str(body.get("operation_id", ""))[:64]
            if not operation_id:
                return _error(400, "WORKSPACE_PATH_INVALID", "operation_id is required.")
            _STATE.close(operation_id)
            if not await _STATE.wait_idle(DRAIN_TIMEOUT):
                _STATE.open()
                return _error(409, "ENGINE_BUSY", "A prompt submission is still in flight.")
            payload = _status_payload(_STATE, server)
            if payload["pending_tasks"] or payload["running_tasks"]:
                _STATE.open()
                return web.json_response(
                    {
                        "error": {
                            "code": "ENGINE_BUSY",
                            "message": "The engine still has queued or running work.",
                            "fields": {
                                "pending_tasks": payload["pending_tasks"],
                                "running_tasks": payload["running_tasks"],
                            },
                        }
                    },
                    status=409,
                )
            return web.json_response(payload, status=202)
        except WorkbenchError as error:
            return _error_response(error)
        except (ValueError, TypeError):
            return _error(400, "WORKSPACE_PATH_INVALID", "The stop request body is not valid JSON.")

    async def cancel_stop(request: web.Request) -> web.Response:
        try:
            _authorize(request)
        except WorkbenchError as error:
            return _error_response(error)
        _STATE.open()
        return web.json_response(_status_payload(_STATE, server))

    routes.get(f"{LIFECYCLE_PREFIX}/status")(status)
    routes.post(f"{LIFECYCLE_PREFIX}/prepare-stop")(prepare_stop)
    routes.post(f"{LIFECYCLE_PREFIX}/cancel-stop")(cancel_stop)
    return _STATE
