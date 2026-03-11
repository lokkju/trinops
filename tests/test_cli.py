import os
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
@patch("trinops.cli.commands._build_profile")
def test_queries_table_output(mock_profile, mock_build):
    from rich.console import Console
    from trinops.config import ConnectionProfile
    mock_profile.return_value = ConnectionProfile(server="localhost:8080", user="loki")
    client = MagicMock()
    client.list_queries.return_value = SAMPLE_QUERIES
    mock_build.return_value = client

    with patch("trinops.cli.formatting.console", Console(width=200)):
        result = runner.invoke(app, ["queries", "--server", "localhost:8080"])
    assert result.exit_code == 0
    assert "20260310_143549" in result.output
    assert "RUNNING" in result.output
    assert "loki" in result.output


@patch("trinops.cli.commands._build_client")
@patch("trinops.cli.commands._build_profile")
def test_queries_json_output(mock_profile, mock_build):
    from trinops.config import ConnectionProfile
    mock_profile.return_value = ConnectionProfile(server="localhost:8080", user="loki")
    client = MagicMock()
    client.list_queries.return_value = SAMPLE_QUERIES
    mock_build.return_value = client

    result = runner.invoke(app, ["queries", "--server", "localhost:8080", "--json"])
    assert result.exit_code == 0
    import json
    data = json.loads(result.output.strip())
    assert len(data) == 2
    assert data[0]["query_id"] == "20260310_143549_08022_abc"


@patch("trinops.cli.commands._build_client")
@patch("trinops.cli.commands._build_profile")
def test_queries_filter_state(mock_profile, mock_build):
    from trinops.config import ConnectionProfile
    mock_profile.return_value = ConnectionProfile(server="localhost:8080", user="loki")
    client = MagicMock()
    client.list_queries.return_value = [SAMPLE_QUERIES[0]]
    mock_build.return_value = client

    result = runner.invoke(app, ["queries", "--server", "localhost:8080", "--state", "RUNNING"])
    assert result.exit_code == 0
    client.list_queries.assert_called_once_with(state="RUNNING", limit=25, query_user="loki")


SAMPLE_RAW = {
    "queryId": "20260310_143549_08022_abc",
    "state": "RUNNING",
    "query": "SELECT * FROM big_table WHERE id > 100",
    "queryType": "SELECT",
    "resourceGroupId": ["global"],
    "session": {"user": "loki", "source": "trinops", "catalog": "hive", "schema": "default"},
    "queryStats": {
        "createTime": "2026-03-10T14:35:49Z",
        "elapsedTime": "6.87s",
        "queuedTime": "1.00ms",
        "planningTime": "120.00ms",
        "executionTime": "6.75s",
        "totalCpuTime": "19.21s",
        "peakUserMemoryReservation": "8650480B",
        "peakTotalMemoryReservation": "8650480B",
        "physicalInputDataSize": "474640412B",
        "physicalInputPositions": 34148040,
        "processedInputDataSize": "474640412B",
        "processedInputPositions": 34148040,
        "outputDataSize": "0B",
        "outputPositions": 0,
        "totalTasks": 10,
        "completedTasks": 5,
        "totalDrivers": 40,
        "completedDrivers": 20,
    },
    "inputs": [],
    "warnings": [],
}


@patch("trinops.cli.commands._build_client")
def test_query_detail(mock_build):
    client = MagicMock()
    client.get_query_raw.return_value = SAMPLE_RAW
    mock_build.return_value = client

    result = runner.invoke(app, ["query", "20260310_143549_08022_abc", "--server", "localhost:8080"])
    assert result.exit_code == 0
    assert "20260310_143549_08022_abc" in result.output
    assert "SELECT * FROM big_table" in result.output


@patch("trinops.cli.commands._build_client")
def test_query_detail_json(mock_build):
    client = MagicMock()
    client.get_query_raw.return_value = SAMPLE_RAW
    mock_build.return_value = client

    result = runner.invoke(app, ["query", "20260310_143549_08022_abc", "--server", "localhost:8080", "--json"])
    assert result.exit_code == 0
    import json
    data = json.loads(result.output.strip())
    assert data["queryId"] == "20260310_143549_08022_abc"


@patch("trinops.cli.commands._build_client")
def test_query_not_found(mock_build):
    client = MagicMock()
    client.get_query_raw.return_value = None
    mock_build.return_value = client

    result = runner.invoke(app, ["query", "nonexistent", "--server", "localhost:8080"])
    assert result.exit_code != 0 or "not found" in result.output.lower()


@patch("trinops.cli.commands.load_config")
def test_no_server_configured_shows_error(mock_config):
    from trinops.config import TrinopsConfig
    mock_config.return_value = TrinopsConfig()

    env = os.environ.copy()
    env.pop("TRINOPS_SERVER", None)
    with patch.dict(os.environ, env, clear=True):
        result = runner.invoke(app, ["queries"])
    assert result.exit_code != 0
    assert "No Trino server configured" in result.output
