"""Local service entry point.

Only the controller's fixed service command starts this module; it refuses
relative workspaces and binds loopback addresses from ``config.toml``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

import uvicorn

from .contracts.lifecycle import StartupContext, WorkspaceSettings
from .core.workspace import (
    build_paths,
    load_product_identity,
    load_settings,
    resolve_workspace,
)
from .interfaces.http.app import create_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="astrophotoflow.__main__", description="AstroPhotoFlow workbench local service."
    )
    parser.add_argument("--workspace", required=True, type=Path, help="Absolute workspace path.")
    parser.add_argument("--port", required=True, type=int, help="Loopback port the controller reserved.")
    parser.add_argument("--engine-url", required=True, help="Native engine base url.")
    parser.add_argument("--web-url", required=True, help="Frontend url the controller publishes.")
    return parser


def build_startup_context(
    workspace: Path, port: int, engine_url: str, web_url: str
) -> StartupContext:
    """Validate the persisted workspace and the endpoints passed by the controller."""

    resolved = resolve_workspace(workspace)
    settings: WorkspaceSettings = load_settings(resolved).model_copy(update={"service_port": port})
    return StartupContext(
        workspace=resolved,
        settings=settings,
        paths=build_paths(settings),
        product=load_product_identity(),
        service_url=f"http://{settings.service_host}:{port}",
        engine_url=engine_url.rstrip("/"),
        web_url=web_url,
    )


def create_http_server(app, settings: WorkspaceSettings) -> uvicorn.Server:
    """Build the uvicorn server with headers and access logs that leak nothing."""

    config = uvicorn.Config(
        app,
        host=settings.service_host,
        port=settings.service_port,
        log_level="info",
        access_log=False,
        server_header=False,
        lifespan="on",
    )
    return uvicorn.Server(config)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    context = build_startup_context(args.workspace, args.port, args.engine_url, args.web_url)
    app = create_app(settings=context.settings, startup_context=context)
    server = create_http_server(app, context.settings)

    def request_shutdown() -> None:
        server.should_exit = True

    app.state.request_shutdown = request_shutdown
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
