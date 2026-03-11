from datetime import datetime
from unittest.mock import MagicMock, patch

from trinops.mcp.server import list_tools, handle_tool_call
from trinops.models import QueryInfo, QueryState


SAMPLE_QUERIES = [
    QueryInfo(
        query_id="20260310_143549_08022_abc",
        state=QueryState.RUNNING,
        query="SELECT * FROM big_table",
        user="loki",
        source="trinops",
        created=datetime(2026, 3, 10, 14, 35, 49),
        cpu_time_millis=19212,
        elapsed_time_millis=6872,
        processed_rows=34148040,
        processed_bytes=474640412,
        peak_memory_bytes=8650480,
    ),
]


def test_list_tools():
    tools = list_tools()
    names = [t["name"] for t in tools]
    assert "list_queries" in names
    assert "get_query" in names
    assert "get_cluster_stats" in names


def test_handle_list_queries():
    client = MagicMock()
    client.list_queries.return_value = SAMPLE_QUERIES

    result = handle_tool_call("list_queries", {}, client)
    assert len(result) == 1
    assert result[0]["query_id"] == "20260310_143549_08022_abc"


def test_handle_list_queries_with_state():
    client = MagicMock()
    client.list_queries.return_value = SAMPLE_QUERIES

    handle_tool_call("list_queries", {"state": "RUNNING"}, client)
    client.list_queries.assert_called_once_with(state="RUNNING")


def test_handle_get_query():
    client = MagicMock()
    client.get_query.return_value = SAMPLE_QUERIES[0]

    result = handle_tool_call("get_query", {"query_id": "20260310_143549_08022_abc"}, client)
    assert result["query_id"] == "20260310_143549_08022_abc"


def test_handle_get_query_not_found():
    client = MagicMock()
    client.get_query.return_value = None

    result = handle_tool_call("get_query", {"query_id": "nonexistent"}, client)
    assert "error" in result


def test_handle_unknown_tool():
    client = MagicMock()
    result = handle_tool_call("unknown_tool", {}, client)
    assert "error" in result
