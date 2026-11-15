"""Records and OpenAPI helpers for the local service surface."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from fastapi import FastAPI


class ServiceHealth(BaseModel):
    """The service health document; it is public only on loopback."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"] = "ok"
    version: str
    workspace: str
    service_url: str
    web_url: str
    database: str


class DrainResult(BaseModel):
    """Answer to a drain request, before the service leaves."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["draining"] = "draining"


class ShutdownResult(BaseModel):
    """Answer to the last authenticated request before the service exits."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["shutting-down"] = "shutting-down"


def openapi_document(app: FastAPI) -> dict[str, Any]:
    """The OpenAPI document the MCP client generator reads."""

    return app.openapi()


def write_openapi_snapshot(app: FastAPI, path: Path) -> Path:
    """Write the snapshot used to generate and diff the TypeScript client."""

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(openapi_document(app), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
