"""Atomic JSON and text files.

A reader never observes a half-written record. The temporary file lives in the
target directory so ``os.replace`` stays on one volume.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .errors import WorkbenchError


def atomic_write_text(path: Path, text: str) -> None:
    """Replace ``path`` with ``text`` and make the rename durable."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, prefix=f".{path.name}.", delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, value: Any) -> None:
    """Write ``value`` as UTF-8 JSON with a stable key order."""

    atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def read_json(path: Path) -> Any:
    """Read a JSON document, reporting a broken record instead of returning None."""

    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise WorkbenchError("STATE_FILE_INVALID", f"Missing state file {Path(path).name}.", file=str(path)) from None
    except json.JSONDecodeError as error:
        raise WorkbenchError(
            "STATE_FILE_INVALID", f"State file {Path(path).name} is not valid JSON.", file=str(path)
        ) from error
