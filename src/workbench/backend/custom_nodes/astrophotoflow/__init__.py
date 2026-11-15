"""ComfyUI custom node that installs the workbench lifecycle adapter.

The engine imports this folder only because the controller starts it with
``--disable-all-custom-nodes --whitelist-custom-nodes astrophotoflow``. It
registers private routes and an admission gate before ``PromptServer`` adds its
route table to the aiohttp application.
"""

from __future__ import annotations

from server import PromptServer

from astrophotoflow.interfaces.native.lifecycle import register_native_lifecycle

NODE_CLASS_MAPPINGS: dict[str, object] = {}
NODE_DISPLAY_NAME_MAPPINGS: dict[str, str] = {}

if PromptServer.instance is not None:
    register_native_lifecycle(PromptServer.instance)
