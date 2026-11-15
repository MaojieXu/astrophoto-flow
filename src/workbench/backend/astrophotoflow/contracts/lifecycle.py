"""Records exchanged by the CLI, the local service and the native adapter.

Every model forbids unknown keys so a stale controller cannot silently accept a
field another component already renamed. Models serialize with
``model_dump(mode="json")``; the CLI and HTTP boundary print exactly that.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

LOOPBACK_HOSTS = ("127.0.0.1", "::1")

ProcessRole = Literal["service", "engine"]
ProcessPhase = Literal["starting", "ready", "stopping", "stopped", "failed", "unknown"]
OperationAction = Literal["init", "start", "stop"]
OperationStatus = Literal["accepted", "running", "succeeded", "failed", "unknown"]
RuntimeState = Literal["installing", "stopped", "starting", "ready", "stopping", "unknown"]


class ContractModel(BaseModel):
    """Base class for records that cross the controller boundary."""

    model_config = ConfigDict(extra="forbid")


class WorkspaceSettings(ContractModel):
    """The persisted part of ``config.toml`` plus the resolved workspace path."""

    workspace: Path
    schema_version: int = Field(default=1, ge=1)
    service_host: str = "127.0.0.1"
    service_port: int = Field(default=0, ge=0, le=65535)
    engine_host: str = "127.0.0.1"
    engine_port: int = Field(default=0, ge=0, le=65535)

    @field_validator("service_host", "engine_host")
    @classmethod
    def require_loopback(cls, value: str) -> str:
        if value not in LOOPBACK_HOSTS:
            raise ValueError("the workbench binds loopback addresses only")
        return value


class WorkspacePaths(ContractModel):
    """Every path the controller, service and native engine may touch."""

    workspace: Path
    config_file: Path
    data_dir: Path
    database_file: Path
    token_file: Path
    run_dir: Path
    lock_file: Path
    process_record_file: Path
    operations_dir: Path
    logs_dir: Path
    service_log: Path
    engine_log: Path
    engine_dir: Path
    user_directory: Path
    input_directory: Path
    output_directory: Path
    temp_directory: Path


class ProductIdentity(ContractModel):
    """The product version the controller announces, never the engine version."""

    version: str = Field(pattern=r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
    commit: str | None = Field(default=None, pattern=r"^[a-f0-9]{40}$")
    source: Literal["installed", "development"]
    root: Path


class StartupContext(ContractModel):
    """Identity and endpoints a running service was started with."""

    workspace: Path
    settings: WorkspaceSettings
    paths: WorkspacePaths
    product: ProductIdentity
    service_url: str
    engine_url: str
    web_url: str


class ProcessLaunchSpec(ContractModel):
    """A fixed command an owned process is started with."""

    role: ProcessRole
    command: list[str] = Field(min_length=1)
    cwd: Path
    log_path: Path
    env: dict[str, str] = Field(default_factory=dict)


class ProcessIdentity(ContractModel):
    """What psutil observed for a process this workspace owns."""

    pid: int = Field(gt=0)
    create_time: float
    exe: str | None = None
    cmdline: list[str] = Field(min_length=1)
    cwd: str | None = None


class ReadyResult(ContractModel):
    """The startup result MCP already understands; the six fields are stable."""

    status: Literal["ready"] = "ready"
    version: str
    workspace: str
    service_url: str
    web_url: str
    reused: bool = False


class ProcessRecord(ContractModel):
    """The single writer of ``run/processes.json`` is the controller."""

    schema_version: int = 1
    workspace: str
    version: str
    operation_id: str
    phase: ProcessPhase
    started_at: str
    service: ProcessIdentity | None = None
    engine: ProcessIdentity | None = None
    client: ReadyResult | None = None
    message: str | None = None


class RuntimeStatus(ContractModel):
    """Installation and run state combined for ``workbench_status``."""

    status: RuntimeState
    version: str
    workspace: str
    initialized: bool
    operation_id: str | None = None
    service_url: str | None = None
    web_url: str | None = None
    message: str | None = None


class InitResult(ContractModel):
    """Workspace initialization outcome; ``reused`` means existing content won."""

    status: Literal["initialized", "reused"]
    version: str
    workspace: str
    database_revision: str | None = None


class StopResult(ContractModel):
    """Stop outcome after both owned processes were confirmed gone."""

    status: Literal["stopped", "not_running"]
    version: str
    workspace: str
    operation_id: str | None = None
    service_stopped: bool = False
    engine_stopped: bool = False
    message: str | None = None


class OperationReceipt(ContractModel):
    """Lifecycle result persisted under ``run/operations``."""

    operation_id: str
    action: OperationAction
    status: OperationStatus
    phase: str
    workspace: str
    created_at: str
    updated_at: str
    message: str | None = None
    result: dict[str, Any] | None = None


class EngineLifecycleStatus(ContractModel):
    """Native admission and queue counters the controller inspects before stop."""

    admission: Literal["open", "closed"]
    in_flight: int = Field(ge=0)
    pending_tasks: int = Field(ge=0)
    running_tasks: int = Field(ge=0)


class EngineStopRequest(ContractModel):
    """The only body a native prepare/cancel-stop call accepts."""

    operation_id: str = Field(min_length=1, max_length=64)


class ErrorDetail(ContractModel):
    """Stable error code plus optional structured fields."""

    code: str
    message: str
    fields: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(ContractModel):
    """The error shape shared by the CLI, the API and the MCP adapter."""

    error: ErrorDetail
