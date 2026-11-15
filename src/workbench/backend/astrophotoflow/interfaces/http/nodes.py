"""Node catalog routes over the engine's native ``/object_info``.

The catalog is the engine's own schema. These routes page and look it up; they
never re-declare node inputs, widgets or output types.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from ...contracts.nodes import NodeDefinition, NodePage, NodeSummary
from ...core.errors import WorkbenchError
from .runtime import ServiceRuntime, get_runtime

router = APIRouter()
MAX_PAGE = 200
DEFAULT_PAGE = 50


def summarize_node(node_type: str, definition: dict[str, Any]) -> NodeSummary:
    """One stable summary per native node type."""

    description = definition.get("description")
    return NodeSummary(
        node_type=node_type,
        display_name=str(definition.get("display_name") or node_type),
        category=str(definition.get("category") or ""),
        output_node=bool(definition.get("output_node")),
        description=str(description) if description else None,
    )


def summarize_catalog(catalog: dict[str, Any]) -> list[NodeSummary]:
    """Sort by node type so paging stays stable between calls."""

    return [summarize_node(node_type, catalog.get(node_type) or {}) for node_type in sorted(catalog)]


def matches(summary: NodeSummary, query: str | None) -> bool:
    if not query:
        return True
    needle = query.strip().lower()
    if not needle:
        return True
    return needle in summary.node_type.lower() or needle in summary.display_name.lower() or needle in summary.category.lower()


@router.get("/api/v1/nodes", response_model=NodePage, operation_id="findNodes")
async def find_nodes(
    query: str | None = Query(default=None, description="Case-insensitive node type, display name or category filter."),
    cursor: str | None = Query(default=None, description="Opaque offset returned by the previous page."),
    limit: int = Query(default=DEFAULT_PAGE, ge=1, le=MAX_PAGE),
    runtime: ServiceRuntime = Depends(get_runtime),
) -> NodePage:
    """Page through the native node catalog, filtered by a single query."""

    offset = _parse_cursor(cursor)
    catalog = await runtime.gateway.node_catalog()
    items = [summary for summary in summarize_catalog(catalog) if matches(summary, query)]
    window = items[offset : offset + limit]
    next_cursor = str(offset + limit) if offset + limit < len(items) else None
    return NodePage(items=window, total=len(items), next_cursor=next_cursor)


@router.get("/api/v1/nodes/{node_type}", response_model=NodeDefinition, operation_id="getNode")
async def get_node(node_type: str, runtime: ServiceRuntime = Depends(get_runtime)) -> NodeDefinition:
    """Return the engine's definition for exactly one node type."""

    catalog = await runtime.gateway.node_definition(node_type)
    definition = catalog.get(node_type)
    if not definition:
        raise WorkbenchError("NODE_NOT_FOUND", "The engine has no node of that type.", node_type=node_type)
    return NodeDefinition(node_type=node_type, definition=definition)


def _parse_cursor(cursor: str | None) -> int:
    if cursor is None or cursor == "":
        return 0
    if not cursor.isdigit():
        raise WorkbenchError("WORKSPACE_PATH_INVALID", "The node cursor must be a page offset.")
    return int(cursor)
