"""Shared controller capabilities exposed over local HTTP.

``native`` is the only package allowed to import ComfyUI modules;
``application`` orchestrates lifecycle work and ``http`` is the transport the
MCP server and other local clients speak.
"""
