"""Windows platform checks and private-directory ACLs.

Only Windows x64 is a supported product platform. The ACL calls deliberately use
``icacls.exe`` with fixed argument lists instead of a generated PowerShell
string; ``os.chmod`` does not manage Windows DACLs and would fake isolation.
"""

from __future__ import annotations

import os
import platform
import subprocess
from pathlib import Path

import psutil

from .errors import WorkbenchError

SUPPORTED_MACHINES = ("amd64", "x86_64")
PLATFORM_OVERRIDE_ENV = "ASTROPHOTOFLOW_ALLOW_UNSUPPORTED_PLATFORM"


def platform_supported() -> bool:
    return os.name == "nt" and platform.machine().lower() in SUPPORTED_MACHINES


def allow_unsupported_platform() -> None:
    """Development escape hatch; inherited by the controller children it spawns."""

    os.environ[PLATFORM_OVERRIDE_ENV] = "1"


def _platform_override() -> bool:
    return os.environ.get(PLATFORM_OVERRIDE_ENV) == "1"


def require_windows_x64() -> None:
    """Refuse controller work on any platform the release does not test."""

    if not platform_supported() and not _platform_override():
        raise WorkbenchError(
            "PLATFORM_UNSUPPORTED",
            "The workbench lifecycle controller runs on Windows x64 only.",
            platform=os.name,
            machine=platform.machine(),
        )


def _require_owned_path(path: Path) -> Path:
    resolved = Path(path).resolve()
    if resolved.parent == resolved:
        raise WorkbenchError("WORKSPACE_PATH_INVALID", "Refusing to change permissions of a filesystem root.")
    return resolved


def _current_account() -> str:
    return psutil.Process().username()


def _apply_acl(path: Path, inheritance_flag: str) -> None:
    account = _current_account()
    command = [
        "icacls.exe",
        str(path),
        "/inheritance:r",
        "/grant:r",
        f"{account}:{inheritance_flag}",
        "/grant:r",
        f"SYSTEM:{inheritance_flag}",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, shell=False, check=False)
    if completed.returncode != 0:
        raise WorkbenchError(
            "WORKSPACE_PATH_INVALID",
            f"Could not restrict permissions of {path.name}.",
            exit_code=completed.returncode,
        )


def restrict_private_directory(path: Path) -> None:
    """Create ``path`` if needed and grant it to this account and SYSTEM only."""

    resolved = _require_owned_path(path)
    resolved.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        _apply_acl(resolved, "(OI)(CI)F")


def restrict_private_file(path: Path) -> None:
    """Grant an existing private file to this account and SYSTEM only."""

    resolved = _require_owned_path(path)
    if not resolved.is_file():
        raise WorkbenchError("STATE_FILE_INVALID", f"Missing private file {resolved.name}.", file=str(resolved))
    if os.name == "nt":
        _apply_acl(resolved, "F")
