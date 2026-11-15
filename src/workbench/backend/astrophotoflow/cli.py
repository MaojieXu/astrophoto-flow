"""Controller CLI used only by the fixed lifecycle bootstrap.

One JSON object goes to stdout; diagnostics and error envelopes go to stderr so
a caller can parse a single stream without guessing. No command accepts an
arbitrary executable, url or pid.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Sequence

import httpx
from pydantic import BaseModel

from .contracts.lifecycle import ErrorEnvelope
from .core.errors import WorkbenchError
from .core.windows import allow_unsupported_platform, require_windows_x64
from .interfaces.application import workbench as application

EXIT_OK = 0
EXIT_FAILURE = 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="astrophotoflow",
        description="AstroPhotoFlow workbench lifecycle controller.",
    )
    parser.add_argument(
        "--allow-unsupported-platform",
        action="store_true",
        help="Development only: run the controller on a non-Windows host. The installer never passes this.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("init", "Create or adopt the workspace and its database baseline."),
        ("start", "Start the workbench, or reuse the instance that is already ready."),
        ("status", "Report installation and run state."),
        ("stop", "Stop the owned processes and keep every file."),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--workspace", required=True, type=Path, help="Absolute workspace path.")
        command.add_argument("--json", action="store_true", help="Emit the result as one JSON object (always on).")
        if name == "stop":
            command.add_argument("--operation-id", default=None, help="Receipt id this stop reports under.")
    return parser


async def run_command(args: argparse.Namespace) -> BaseModel:
    async with httpx.AsyncClient(follow_redirects=False, trust_env=False) as client:
        if args.command == "init":
            return await application.initialize_workbench(args.workspace)
        if args.command == "start":
            return await application.start_workbench(args.workspace, client)
        if args.command == "status":
            return await application.get_workbench_status(args.workspace, client)
        if args.command == "stop":
            return await application.stop_workbench(args.workspace, client, args.operation_id)
    raise WorkbenchError("WORKSPACE_PATH_INVALID", "Unknown controller command.")


def emit(result: BaseModel) -> None:
    sys.stdout.write(result.model_dump_json(exclude_none=False) + "\n")
    sys.stdout.flush()


def emit_error(error: WorkbenchError) -> None:
    envelope: ErrorEnvelope = error.envelope()
    sys.stderr.write(envelope.model_dump_json() + "\n")
    sys.stderr.flush()


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.allow_unsupported_platform:
            allow_unsupported_platform()
        require_windows_x64()
        emit(asyncio.run(run_command(args)))
    except WorkbenchError as error:
        emit_error(error)
        return EXIT_FAILURE
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
