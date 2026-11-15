"""The stable error codes every boundary translates instead of inventing its own."""

from __future__ import annotations

from typing import Any

from ..contracts.lifecycle import ErrorDetail, ErrorEnvelope


class WorkbenchError(Exception):
    """A controller failure with a code a caller can branch on.

    Codes are part of the CLI/API/MCP contract. Messages never carry the service
    token or a whole child-process command line.
    """

    def __init__(self, code: str, message: str, **fields: Any) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.fields = fields

    def envelope(self) -> ErrorEnvelope:
        return ErrorEnvelope(error=ErrorDetail(code=self.code, message=self.message, fields=self.fields))


# HTTP status per controller code; the CLI ignores it and exits non-zero.
STATUS_CODES: dict[str, int] = {
    "UNAUTHORIZED": 401,
    "FORBIDDEN": 403,
    "WORKSPACE_NOT_FOUND": 404,
    "OPERATION_NOT_FOUND": 404,
    "NODE_NOT_FOUND": 404,
    "WORKSPACE_NOT_INITIALIZED": 409,
    "WORKSPACE_NOT_EMPTY": 409,
    "WORKBENCH_BUSY": 409,
    "ENGINE_BUSY": 409,
    "WORKBENCH_ALREADY_STOPPING": 409,
    "DATABASE_NOT_READY": 503,
    "ENGINE_UNAVAILABLE": 503,
    "SERVICE_UNAVAILABLE": 503,
    "SERVICE_DRAINING": 503,
    "PROCESS_IDENTITY_MISMATCH": 409,
    "PROCESS_NOT_FOUND": 409,
    "ENGINE_LIFECYCLE_UNAVAILABLE": 503,
    "PLATFORM_UNSUPPORTED": 501,
    "WORKSPACE_PATH_INVALID": 400,
    "STATE_FILE_INVALID": 500,
}


def http_status(code: str) -> int:
    return STATUS_CODES.get(code, 500)
