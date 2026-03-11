from __future__ import annotations

import dataclasses
import json
import sys
from typing import Any, Optional

from trinops.client import TrinopsClient
from trinops.models import QueryInfo


_TOOLS = [
    {
        "name": "list_queries",
        "description": "List running and recent Trino queries",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "description": "Filter by query state (QUEUED, RUNNING, FINISHED, FAILED)",
                },
            },
        },
    },
    {
        "name": "get_query",
        "description": "Get details for a specific Trino query by ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query_id": {
                    "type": "string",
                    "description": "The Trino query ID",
                },
            },
            "required": ["query_id"],
        },
    },
    {
        "name": "get_cluster_stats",
        "description": "Get aggregate cluster statistics from running queries",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def list_tools() -> list[dict]:
    return _TOOLS


def _query_to_dict(qi: QueryInfo) -> dict:
    return dataclasses.asdict(qi)


def handle_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
    client: TrinopsClient,
) -> Any:
    if tool_name == "list_queries":
        state = arguments.get("state")
        queries = client.list_queries(state=state)
        return [_query_to_dict(q) for q in queries]

    if tool_name == "get_query":
        query_id = arguments["query_id"]
        qi = client.get_query(query_id)
        if qi is None:
            return {"error": f"Query not found: {query_id}"}
        return _query_to_dict(qi)

    if tool_name == "get_cluster_stats":
        queries = client.list_queries()
        running = [q for q in queries if q.state.value == "RUNNING"]
        queued = [q for q in queries if q.state.value == "QUEUED"]
        return {
            "total_queries": len(queries),
            "running_queries": len(running),
            "queued_queries": len(queued),
            "total_rows_processed": sum(q.processed_rows for q in running),
            "total_peak_memory": sum(q.peak_memory_bytes for q in running),
        }

    return {"error": f"Unknown tool: {tool_name}"}


def run_stdio_server(client: TrinopsClient) -> None:
    """Run a simple JSON-RPC stdio MCP server."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = request.get("method")
        req_id = request.get("id")

        if method == "initialize":
            response = {"jsonrpc": "2.0", "id": req_id, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "trinops", "version": "0.1.0"},
            }}
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            response = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": list_tools()}}
        elif method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = handle_tool_call(tool_name, arguments, client)
            content = json.dumps(result, default=str)
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": content}]},
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()
