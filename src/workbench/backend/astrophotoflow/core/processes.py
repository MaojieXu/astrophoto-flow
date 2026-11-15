"""Workspace locks, detached spawns and process identity.

A process record is evidence, not authority: nothing is terminated until the
live pid, creation time, executable and command line still match what the
controller observed when it started that process.
"""

from __future__ import annotations

import os
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal

import psutil

from ..contracts.lifecycle import ProcessIdentity, ProcessLaunchSpec, ProcessRecord
from .errors import WorkbenchError
from .files import atomic_write_json, read_json

CREATE_TIME_TOLERANCE = 1.0
LOCK_POLL_SECONDS = 0.2


def utc_now() -> str:
    return datetime.now(tz=timezone.utc).isoformat(timespec="seconds")


class WorkspaceLock:
    """One exclusive lock file per workspace.

    The lock file is created on first use; ``msvcrt.locking`` on Windows and
    ``flock`` elsewhere both release it when the owning process disappears.
    """

    def __init__(self, paths, timeout: float = 120.0) -> None:
        self.path = paths.lock_file
        self.timeout = timeout
        self._handle = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+b")
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        deadline = time.monotonic() + self.timeout
        while True:
            if self._try_lock(handle):
                self._handle = handle
                return
            if time.monotonic() >= deadline:
                handle.close()
                raise WorkbenchError(
                    "WORKBENCH_BUSY",
                    "Another workbench operation holds this workspace lock.",
                    workspace=str(self.path.parent.parent),
                )
            time.sleep(LOCK_POLL_SECONDS)

    @staticmethod
    def _try_lock(handle) -> bool:
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return False
        return True

    def release(self) -> None:
        handle, self._handle = self._handle, None
        if handle is None:
            return
        try:
            if os.name == "nt":
                import msvcrt

                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        finally:
            handle.close()


@contextmanager
def workspace_lock(paths, timeout: float = 120.0) -> Iterator[WorkspaceLock]:
    lock = WorkspaceLock(paths, timeout=timeout)
    lock.acquire()
    try:
        yield lock
    finally:
        lock.release()


def _normalize(value: str) -> str:
    return os.path.normcase(os.path.normpath(value))


def _command_identity(command: list[str]) -> tuple[str, ...]:
    return tuple(_normalize(part) if (os.sep in part or "/" in part) else part for part in command)


def capture_identity(pid: int) -> ProcessIdentity:
    """Observe a live process; retry briefly while Windows publishes its details."""

    deadline = time.monotonic() + 10.0
    while True:
        try:
            process = psutil.Process(pid)
            return ProcessIdentity(
                pid=pid,
                create_time=process.create_time(),
                exe=_safe(lambda: process.exe()),
                cmdline=_safe(lambda: process.cmdline()) or [str(pid)],
                cwd=_safe(lambda: process.cwd()),
            )
        except psutil.NoSuchProcess:
            raise WorkbenchError("PROCESS_NOT_FOUND", "The started process exited before it could be recorded.") from None
        except psutil.AccessDenied:
            raise WorkbenchError(
                "PROCESS_IDENTITY_MISMATCH", "The started process refused identity inspection."
            ) from None
        if time.monotonic() >= deadline:
            raise WorkbenchError("PROCESS_IDENTITY_MISMATCH", "The started process identity was not observable.")
        time.sleep(0.1)


def _safe(read):
    try:
        return read()
    except (psutil.AccessDenied, psutil.ZombieProcess, OSError):
        return None


def spawn_detached(spec: ProcessLaunchSpec) -> ProcessIdentity:
    """Start an owned process that survives the controller, and record its identity."""

    spec.log_path.parent.mkdir(parents=True, exist_ok=True)
    environment = {**os.environ, **spec.env, "PYTHONUTF8": "1"}
    options: dict = {
        "cwd": str(spec.cwd),
        "env": environment,
        "stdin": subprocess.DEVNULL,
        "stderr": subprocess.STDOUT,
        "close_fds": True,
    }
    if os.name == "nt":
        options["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    with spec.log_path.open("ab", buffering=0) as log:
        options["stdout"] = log
        process = subprocess.Popen(spec.command, **options)
    try:
        return capture_identity(process.pid)
    except WorkbenchError:
        raise


def identity_matches(identity: ProcessIdentity | None) -> bool:
    """True only while the live process still is the one that was recorded."""

    if identity is None:
        return False
    try:
        process = psutil.Process(identity.pid)
        if abs(process.create_time() - identity.create_time) > CREATE_TIME_TOLERANCE:
            return False
        if identity.exe:
            actual = _safe(lambda: process.exe())
            if not actual or _normalize(actual) != _normalize(identity.exe):
                return False
        actual_command = _safe(lambda: process.cmdline())
        if not actual_command or _command_identity(actual_command) != _command_identity(identity.cmdline):
            return False
        if identity.cwd:
            actual_cwd = _safe(lambda: process.cwd())
            if actual_cwd and _normalize(actual_cwd) != _normalize(identity.cwd):
                return False
    except psutil.NoSuchProcess:
        return False
    except psutil.AccessDenied:
        return False
    return True


def identity_state(identity: ProcessIdentity | None) -> Literal["owned", "gone", "foreign"]:
    """Classify a recorded process: still ours, already gone, or an unknown owner."""

    if identity is None:
        return "gone"
    if not psutil.pid_exists(identity.pid):
        return "gone"
    return "owned" if identity_matches(identity) else "foreign"


def wait_for_exit(identity: ProcessIdentity | None, timeout: float) -> bool:
    """Wait until the recorded process is gone; report whether it really is."""

    if identity is None:
        return True
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not identity_matches(identity):
            return True
        time.sleep(LOCK_POLL_SECONDS)
    return not identity_matches(identity)


def terminate_owned(identity: ProcessIdentity | None, timeout: float = 20.0) -> bool:
    """Terminate a verified process tree, never a process matched by name."""

    if identity is None:
        return True
    if not identity_matches(identity):
        raise WorkbenchError(
            "PROCESS_IDENTITY_MISMATCH",
            "The recorded process is no longer the process this workspace started.",
            pid=identity.pid,
        )
    process = psutil.Process(identity.pid)
    children = _safe(lambda: process.children(recursive=True)) or []
    for child in children:
        _safe(child.terminate)
    _safe(process.terminate)
    _, alive = psutil.wait_procs([process, *children], timeout=timeout)
    for leftover in alive:
        _safe(leftover.kill)
    if alive:
        psutil.wait_procs(alive, timeout=5.0)
    return not identity_matches(identity)


def load_process_record(paths) -> ProcessRecord | None:
    """Read the process record; a corrupt record is an error, not a stopped workspace."""

    if not paths.process_record_file.is_file():
        return None
    return ProcessRecord.model_validate(read_json(paths.process_record_file))


def save_process_record(paths, record: ProcessRecord) -> None:
    atomic_write_json(paths.process_record_file, record.model_dump(mode="json"))


def clear_process_record(paths) -> None:
    Path(paths.process_record_file).unlink(missing_ok=True)


def port_is_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """Check whether something still listens on a loopback port."""

    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(timeout)
        return probe.connect_ex((host, port)) == 0
