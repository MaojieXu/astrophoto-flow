"""Launch parameters and HTTP access for the native ComfyUI engine.

The engine owns graphs, the prompt queue and execution. This module only starts
it with pinned arguments and reads its own native endpoints back.
"""

from __future__ import annotations

import socket
import sys
from pathlib import Path
from typing import Any

import httpx

from ...contracts.lifecycle import EngineLifecycleStatus, ProcessLaunchSpec, WorkspacePaths
from ...core.auth import authorization_header
from ...core.errors import WorkbenchError

ENGINE_LIFECYCLE_PATH = "/astrophotoflow/lifecycle"
WEB_PAGE_MARKER = 'id="splash-loader"'
REQUEST_TIMEOUT = 60.0


def find_free_port(host: str) -> int:
    """Ask the platform for an unused loopback port."""

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        return int(probe.getsockname()[1])


def build_engine_launch_spec(
    backend_root: Path,
    paths: WorkspacePaths,
    port: int,
    web_root: Path,
) -> ProcessLaunchSpec:
    """Fixed engine command: loopback, CPU torch, only our custom node folder."""

    command = [
        sys.executable,
        "-m",
        "main",
        "--listen",
        "127.0.0.1",
        "--port",
        str(port),
        "--cpu",
        "--disable-auto-launch",
        "--disable-all-custom-nodes",
        "--whitelist-custom-nodes",
        "astrophotoflow",
        "--front-end-root",
        str(web_root),
        "--user-directory",
        str(paths.user_directory),
        "--input-directory",
        str(paths.input_directory),
        "--output-directory",
        str(paths.output_directory),
        "--temp-directory",
        str(paths.temp_directory),
    ]
    return ProcessLaunchSpec(
        role="engine",
        command=command,
        cwd=Path(backend_root),
        log_path=paths.engine_log,
        env={"ASTROPHOTOFLOW_WORKSPACE": str(paths.workspace)},
    )


class EngineGateway:
    """Typed reads over the engine's native HTTP API."""

    def __init__(self, base_url: str, token: str, client: httpx.AsyncClient) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._client = client

    async def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> httpx.Response:
        try:
            response = await self._client.request(
                method,
                f"{self.base_url}{path}",
                headers=authorization_header(self._token),
                json=payload,
                timeout=REQUEST_TIMEOUT,
            )
        except httpx.HTTPError as error:
            raise WorkbenchError(
                "ENGINE_UNAVAILABLE", "The native engine is not reachable.", reason=type(error).__name__
            ) from error
        if response.status_code == 401:
            raise WorkbenchError("UNAUTHORIZED", "The native engine rejected the service token.")
        if response.status_code == 409:
            detail = _error_detail(response)
            raise WorkbenchError("ENGINE_BUSY", detail or "The native engine is draining or busy.")
        if response.status_code >= 400:
            raise WorkbenchError(
                "ENGINE_UNAVAILABLE",
                _error_detail(response) or "The native engine rejected the request.",
                status=response.status_code,
            )
        return response

    async def is_ready(self) -> bool:
        """The engine answers ``/system_stats`` only after its queue exists."""

        try:
            await self._request("GET", "/system_stats")
        except WorkbenchError:
            return False
        return True

    async def node_catalog(self) -> dict[str, Any]:
        response = await self._request("GET", "/object_info")
        return response.json()

    async def node_definition(self, node_type: str) -> dict[str, Any]:
        response = await self._request("GET", f"/object_info/{node_type}")
        return response.json()

    async def lifecycle_status(self) -> EngineLifecycleStatus:
        response = await self._request("GET", f"{ENGINE_LIFECYCLE_PATH}/status")
        return EngineLifecycleStatus.model_validate(response.json())

    async def prepare_stop(self, operation_id: str) -> EngineLifecycleStatus:
        response = await self._request(
            "POST", f"{ENGINE_LIFECYCLE_PATH}/prepare-stop", {"operation_id": operation_id}
        )
        return EngineLifecycleStatus.model_validate(response.json())

    async def cancel_stop(self, operation_id: str) -> EngineLifecycleStatus:
        response = await self._request(
            "POST", f"{ENGINE_LIFECYCLE_PATH}/cancel-stop", {"operation_id": operation_id}
        )
        return EngineLifecycleStatus.model_validate(response.json())

    async def web_page(self) -> str:
        """Fetch the served frontend root and prove it is the real editor page."""

        try:
            response = await self._client.get(f"{self.base_url}/", timeout=30.0)
        except httpx.HTTPError as error:
            raise WorkbenchError(
                "WORKBENCH_NOT_READY", "The engine web page is not reachable.", reason=type(error).__name__
            ) from error
        content_type = response.headers.get("content-type", "")
        if response.status_code != 200 or "text/html" not in content_type:
            raise WorkbenchError(
                "WORKBENCH_NOT_READY", "The engine did not serve an HTML editor page.", status=response.status_code
            )
        body = response.text
        if WEB_PAGE_MARKER not in body:
            raise WorkbenchError("WORKBENCH_NOT_READY", "The served page is not the frontend entry document.")
        return body


def _error_detail(response: httpx.Response) -> str | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict) and isinstance(error.get("message"), str):
        return error["message"]
    return None
