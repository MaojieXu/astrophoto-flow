"""The workspace service token.

One responsibility owner: this module creates, reads and verifies the bearer
token that the controller, the local API and the native private routes share.
The token never appears in a URL, a tool result or a log line.
"""

from __future__ import annotations

import hmac
import re
import secrets
from pathlib import Path

from ..contracts.lifecycle import WorkspacePaths
from .errors import WorkbenchError
from .files import atomic_write_text
from .windows import restrict_private_directory, restrict_private_file

TOKEN_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def ensure_service_token(paths: WorkspacePaths) -> str:
    """Return the workspace token, creating it once with private permissions."""

    if paths.token_file.is_file():
        return read_service_token(paths)
    restrict_private_directory(paths.data_dir)
    token = secrets.token_hex(32)
    atomic_write_text(paths.token_file, token + "\n")
    restrict_private_file(paths.token_file)
    return token


def read_service_token(paths: WorkspacePaths) -> str:
    """Read the token and reject a truncated or edited file."""

    try:
        token = paths.token_file.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        raise WorkbenchError(
            "WORKSPACE_NOT_INITIALIZED", "The workspace has no service token; run workbench_init first."
        ) from None
    if not TOKEN_PATTERN.match(token):
        raise WorkbenchError("STATE_FILE_INVALID", "The service token file is not a 32-byte hex token.")
    return token


def verify_token(provided: str | None, token: str) -> bool:
    """Compare a raw token value in constant time."""

    if not provided or not TOKEN_PATTERN.match(provided):
        return False
    return hmac.compare_digest(provided, token)


def verify_bearer(header: str | None, token: str) -> bool:
    """Compare a bearer header in constant time."""

    if not header:
        return False
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value:
        return False
    return verify_token(value.strip(), token)


def authorization_header(token: str) -> dict[str, str]:
    """The only place that formats the header, so callers cannot leak variants."""

    return {"Authorization": f"Bearer {token}"}


def token_path(paths: WorkspacePaths) -> Path:
    return paths.token_file
