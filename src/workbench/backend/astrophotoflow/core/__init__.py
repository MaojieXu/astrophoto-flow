"""Shared controller primitives.

``contracts`` validates records, ``core`` owns configuration, files, Windows
permissions, the database and generic process management. Neither layer knows
about HTTP routes, MCP or ComfyUI.
"""

from .errors import WorkbenchError

__all__ = ["WorkbenchError"]
