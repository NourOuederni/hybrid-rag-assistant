"""A8 - MCP server exposing the project's tools to any MCP client (Claude Desktop, MCP Inspector...).

Run:  python -m core.mcp_server            (stdio, for Claude Desktop)
      python -m core.mcp_server --http     (streamable HTTP on port 8765)
"""
from __future__ import annotations

import sys
from typing import Any

try:  # mcp >= 2.0
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

from contracts.schemas import ChatOptions

_core = None


def core():
    global _core
    if _core is None:
        from .service import Core
        _core = Core()
    return _core


mcp = _Server("hybrid-rag-assistant")


def _dump(records) -> list[dict[str, Any]]:
    return [r.model_dump(exclude_none=True) for r in records]


@mcp.tool()
def list_documents() -> list[str]:
    """List the ids of the documents currently indexed in the knowledge base."""
    return core().list_indexed_documents()


@mcp.tool()
def search_documents(query: str, k: int = 5) -> list[dict[str, Any]]:
    """Semantic search over the uploaded documents. Returns passages with file name and page."""
    return _dump(core().search_documents(query, k))


@mcp.tool()
def search_graph(query: str) -> list[dict[str, Any]]:
    """Search the knowledge graph (GraphRAG): finds entities in the query and returns related
    entities, relations and the passages that support them. Good for multi-hop questions."""
    return _dump(core().search_graph(query))


@mcp.tool()
def search_images(query: str, k: int = 3) -> list[dict[str, Any]]:
    """Find figures and diagrams in the documents that match a text description."""
    return _dump(core().search_images(query, k))


@mcp.tool()
def web_search(query: str) -> dict[str, Any]:
    """Search the web. Each result carries its URL, title and retrieval date."""
    results, err = core().web(query)
    return {"results": _dump(results), "error": err}


@mcp.tool()
def ask_agent(question: str, mode: str = "auto", web_search_enabled: bool = True) -> dict[str, Any]:
    """Ask the full agent (router, retrieval, optional web fallback, verification).
    Returns the cited answer, its sources and the route the agent took."""
    ans = core().ask(question, ChatOptions(mode=mode, web_search_enabled=web_search_enabled))
    return ans.model_dump(exclude_none=True)


def main() -> None:
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
