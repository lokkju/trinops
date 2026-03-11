from datetime import datetime
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from trinops.cli import app
from trinops.models import QueryInfo, QueryState


runner = CliRunner()

SAMPLE_QUERIES = [
    QueryInfo(
        query_id="20260310_143549_08022_abc",
        state=QueryState.RUNNING,
        query="SELECT * FROM big_table WHERE id > 100",
        user="loki",
        source="trinops",
        created=datetime(2026, 3, 10, 14, 35, 49),
        cpu_time_millis=19212,
        elapsed_time_millis=6872,
        processed_rows=34148040,
        processed_bytes=474640412,
        peak_memory_bytes=8650480,
    ),
    QueryInfo(
        query_id="20260310_142000_07000_def",
        state=QueryState.FINISHED,
        query="SELECT count(*) FROM users",
        user="admin",
        source="trino-cli",
        created=datetime(2026, 3, 10, 14, 20, 0),
        cpu_time_millis=500,
        elapsed_time_millis=1200,
        processed_rows=1,
        processed_bytes=8,
        peak_memory_bytes=100000,
    ),
]


@patch("trinops.cli.commands._build_client")
def test_queries_table_output(mock_build):
    client = MagicMock()
    client.list_queries.return_value = SAMPLE_QUERIES
    mock_build.return_value = client

    result = runner.invoke(app, ["queries", "--server", "localhost:8080"])
    assert result.exit_code == 0
    assert "20260310_143549" in result.output
    assert "RUNNING" in result.output
    assert "loki" in result.output


@patch("trinops.cli.commands._build_client")
def test_queries_json_output(mock_build):
    client = MagicMock()
    client.list_queries.return_value = SAMPLE_QUERIES
    mock_build.return_value = client

    result = runner.invoke(app, ["queries", "--server", "localhost:8080", "--json"])
    assert result.exit_code == 0
    import json
    lines = [l for l in result.output.strip().split("\n") if l]
    data = [json.loads(l) for l in lines]
    assert len(data) == 2
    assert data[0]["query_id"] == "20260310_143549_08022_abc"


@patch("trinops.cli.commands._build_client")
def test_queries_filter_state(mock_build):
    client = MagicMock()
    client.list_queries.return_value = [SAMPLE_QUERIES[0]]
    mock_build.return_value = client

    result = runner.invoke(app, ["queries", "--server", "localhost:8080", "--state", "RUNNING"])
    assert result.exit_code == 0
    client.list_queries.assert_called_once_with(state="RUNNING")


@patch("trinops.cli.commands._build_client")
def test_query_detail(mock_build):
    client = MagicMock()
    client.get_query.return_value = SAMPLE_QUERIES[0]
    mock_build.return_value = client

    result = runner.invoke(app, ["query", "20260310_143549_08022_abc", "--server", "localhost:8080"])
    assert result.exit_code == 0
    assert "20260310_143549_08022_abc" in result.output
    assert "SELECT * FROM big_table" in result.output


@patch("trinops.cli.commands._build_client")
def test_query_detail_json(mock_build):
    client = MagicMock()
    client.get_query.return_value = SAMPLE_QUERIES[0]
    mock_build.return_value = client

    result = runner.invoke(app, ["query", "20260310_143549_08022_abc", "--server", "localhost:8080", "--json"])
    assert result.exit_code == 0
    import json
    data = json.loads(result.output.strip())
    assert data["query_id"] == "20260310_143549_08022_abc"


@patch("trinops.cli.commands._build_client")
def test_query_not_found(mock_build):
    client = MagicMock()
    client.get_query.return_value = None
    mock_build.return_value = client

    result = runner.invoke(app, ["query", "nonexistent", "--server", "localhost:8080"])
    assert result.exit_code != 0 or "not found" in result.output.lower()
