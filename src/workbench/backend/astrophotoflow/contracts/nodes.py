"""Native node catalog records.

The definition field keeps the engine's own JSON verbatim: rewriting ports or
widget protocols here would create a second, always-stale node schema.
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .lifecycle import ContractModel


class NodeSummary(ContractModel):
    """One searchable entry of the engine node catalog."""

    node_type: str
    display_name: str
    category: str
    output_node: bool
    description: str | None = None


class NodePage(ContractModel):
    """A bounded page of node summaries in stable node_type order."""

    items: list[NodeSummary]
    total: int = Field(ge=0)
    next_cursor: str | None = None


class NodeDefinition(ContractModel):
    """The full native definition of one node type."""

    node_type: str
    definition: dict[str, Any]
