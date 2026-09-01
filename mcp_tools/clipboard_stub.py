"""
HELIX MCP OS Stub — one server, one tool.

Replaces the full OS middleware layer (Vedika's module — descoped per revised spec).
Exposes a single safe read-only operation: read_clipboard.

Wired as a LangGraph tool node in helix_graph.py.
HITL gate in hitl_check_node guards any write actions before they reach this server.

Usage (standalone test):
    python mcp_tools/clipboard_stub.py

Usage (from LangGraph tool node):
    result = call_clipboard_tool()

Ref: MCP Python SDK — https://github.com/modelcontextprotocol/python-sdk
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


# ── Synchronous helper — used by LangGraph tool node ─────────────────────────

def call_clipboard_tool() -> str:
    """
    Read the system clipboard and return its text content.

    Returns empty string if clipboard is empty or pyperclip is unavailable.
    This is a READ-ONLY operation — no write risk, HITL is not triggered.
    """
    try:
        import pyperclip
        content = pyperclip.paste()
        if content:
            logger.info("[MCP CLIPBOARD] Read %d chars from clipboard.", len(content))
        return content or ""
    except Exception as exc:
        logger.warning("[MCP CLIPBOARD] Could not read clipboard: %s", exc)
        return ""


# ── MCP Server (async) ───────────────────────────────────────────────────────
# Only used when running as a standalone MCP server process.
# LangGraph integration uses call_clipboard_tool() directly.

async def _run_mcp_server() -> None:
    """Run the MCP server. Called when this script is executed directly."""
    try:
        from mcp.server import Server
        from mcp.server.stdio import stdio_server
        from mcp.types import TextContent, Tool
    except ImportError:
        print("[MCP] 'mcp' package not installed. Run: pip install mcp")
        print("[MCP] Using direct clipboard call instead.\n")
        result = call_clipboard_tool()
        print(f"[MCP CLIPBOARD] Content: {result!r}")
        return

    server = Server("helix-os-stub")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="read_clipboard",
                description=(
                    "Read the current system clipboard text. "
                    "Read-only. No data is written. "
                    "HELIX uses this to paste content into queries."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            )
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        if name != "read_clipboard":
            return [TextContent(type="text", text=f"[MCP] Unknown tool: {name}")]

        content = call_clipboard_tool()
        return [TextContent(type="text", text=content or "(clipboard is empty)")]

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print("HELIX MCP OS Stub — read_clipboard tool")
    print("Testing clipboard read directly...\n")
    asyncio.run(_run_mcp_server())
