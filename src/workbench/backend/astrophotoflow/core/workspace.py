"""Workspace layout, persisted settings and product identity.

``config.toml`` belongs to the user: initialization keeps a valid existing file
and refuses to adopt a directory that holds anything it does not recognize.
"""

from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any

from ..contracts.lifecycle import ProductIdentity, WorkspacePaths, WorkspaceSettings
from .auth import ensure_service_token
from .errors import WorkbenchError
from .files import atomic_write_text
from .windows import restrict_private_directory

BACKEND_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_ENTRIES = frozenset({"config.toml", "data", "run", "logs"})

DEFAULT_CONFIG = """\
# AstroPhotoFlow workspace configuration. Initialization keeps this file once it exists.
schema_version = 1
service_host = "127.0.0.1"
service_port = 0
engine_host = "127.0.0.1"
engine_port = 0
"""


def resolve_workspace(path: str | Path) -> Path:
    """Require an absolute workspace path; a relative one depends on the caller's cwd."""

    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        raise WorkbenchError(
            "WORKSPACE_PATH_INVALID", "Supply an absolute workspace path.", workspace=str(path)
        )
    return candidate.resolve()


def _read_config(config_file: Path) -> dict[str, Any]:
    try:
        with config_file.open("rb") as handle:
            return tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise WorkbenchError(
            "STATE_FILE_INVALID", "config.toml is not a readable TOML document.", file=str(config_file)
        ) from error


def load_settings(workspace: Path) -> WorkspaceSettings:
    """Load the settings initialization wrote, validating every key."""

    resolved = resolve_workspace(workspace)
    config_file = resolved / "config.toml"
    if not config_file.is_file():
        raise WorkbenchError(
            "WORKSPACE_NOT_INITIALIZED",
            "The workspace has no config.toml; run workbench_init first.",
            workspace=str(resolved),
        )
    raw = _read_config(config_file)
    try:
        return WorkspaceSettings.model_validate({**raw, "workspace": resolved})
    except ValueError as error:
        raise WorkbenchError(
            "STATE_FILE_INVALID", "config.toml does not match the settings contract.", file=str(config_file)
        ) from error


def build_paths(settings: WorkspaceSettings) -> WorkspacePaths:
    """Derive every owned path from the configured workspace."""

    workspace = settings.workspace
    data_dir = workspace / "data"
    run_dir = workspace / "run"
    logs_dir = workspace / "logs"
    engine_dir = data_dir / "engine"
    return WorkspacePaths(
        workspace=workspace,
        config_file=workspace / "config.toml",
        data_dir=data_dir,
        database_file=data_dir / "workbench.sqlite3",
        token_file=data_dir / "service.token",
        run_dir=run_dir,
        lock_file=run_dir / "workbench.lock",
        process_record_file=run_dir / "processes.json",
        operations_dir=run_dir / "operations",
        logs_dir=logs_dir,
        service_log=logs_dir / "service.log",
        engine_log=logs_dir / "engine.log",
        engine_dir=engine_dir,
        user_directory=engine_dir / "user",
        input_directory=engine_dir / "input",
        output_directory=engine_dir / "output",
        temp_directory=engine_dir / "temp",
    )


def initialize_workspace(workspace: str | Path) -> tuple[WorkspacePaths, bool]:
    """Create or adopt a workspace; return its paths and whether it already existed.

    A non-empty directory without ``config.toml`` is somebody else's data and is
    refused. An existing valid configuration is never rewritten.
    """

    resolved = resolve_workspace(workspace)
    if resolved.exists() and not resolved.is_dir():
        raise WorkbenchError("WORKSPACE_PATH_INVALID", "The workspace path is not a directory.")
    if resolved.is_dir():
        unexpected = sorted(entry.name for entry in resolved.iterdir() if entry.name not in WORKSPACE_ENTRIES)
        if unexpected and not (resolved / "config.toml").is_file():
            raise WorkbenchError(
                "WORKSPACE_NOT_EMPTY",
                "The workspace directory holds files this workbench does not own.",
                entries=unexpected[:10],
            )
    created = not (resolved / "config.toml").is_file()
    resolved.mkdir(parents=True, exist_ok=True)
    if created:
        atomic_write_text(resolved / "config.toml", DEFAULT_CONFIG)
    settings = load_settings(resolved)
    paths = build_paths(settings)
    for directory in (
        paths.data_dir,
        paths.run_dir,
        paths.operations_dir,
        paths.logs_dir,
        paths.engine_dir,
        paths.user_directory,
        paths.input_directory,
        paths.output_directory,
        paths.temp_directory,
    ):
        restrict_private_directory(directory)
    ensure_service_token(paths)
    return paths, created


def load_product_identity(backend_root: Path = BACKEND_ROOT) -> ProductIdentity:
    """Read the installed release identity, or the checkout identity during development."""

    resolved_root = Path(backend_root).resolve()
    installed = resolved_root / "release-version.json"
    if installed.is_file():
        try:
            data = json.loads(installed.read_text(encoding="utf-8"))
            return ProductIdentity(
                version=str(data["version"]),
                commit=str(data.get("commit") or "") or None,
                source="installed",
                root=resolved_root,
            )
        except (OSError, ValueError, KeyError) as error:
            raise WorkbenchError(
                "STATE_FILE_INVALID", "release-version.json is not a usable product identity.", file=str(installed)
            ) from error
    repository = resolved_root.parents[2]
    package = repository / "package.json"
    try:
        version = str(json.loads(package.read_text(encoding="utf-8"))["version"])
    except (OSError, ValueError, KeyError) as error:
        raise WorkbenchError(
            "STATE_FILE_INVALID", "Neither an installed nor a checkout product version was found."
        ) from error
    return ProductIdentity(version=version, commit=_git_commit(repository), source="development", root=repository)


def _git_commit(repository: Path) -> str | None:
    completed = subprocess.run(
        ["git", "-C", str(repository), "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    )
    commit = completed.stdout.strip()
    return commit if completed.returncode == 0 and len(commit) == 40 else None


def frontend_web_root(backend_root: Path = BACKEND_ROOT) -> Path:
    """The packaged web directory, or the frontend build output during development."""

    packaged = Path(backend_root).resolve() / "web"
    if (packaged / "index.html").is_file():
        return packaged
    development = Path(backend_root).resolve().parents[0] / "frontend" / "dist"
    if (development / "index.html").is_file():
        return development
    raise WorkbenchError(
        "SERVICE_UNAVAILABLE", "The packaged frontend is missing; build the frontend or reinstall the release."
    )
