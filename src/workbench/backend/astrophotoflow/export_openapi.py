"""Write the OpenAPI snapshot the TypeScript client is generated from.

Run it through ``scripts/export-openapi.ts``; the snapshot is a build input, not
a hand-maintained document.
"""

from __future__ import annotations

import sys
from pathlib import Path

from .interfaces.http.app import create_app
from .interfaces.http.schema import write_openapi_snapshot


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        sys.stderr.write("usage: python -m astrophotoflow.export_openapi <output.json>\n")
        return 2
    path = write_openapi_snapshot(create_app(), Path(args[0]))
    sys.stdout.write(f"{path}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
