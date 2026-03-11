from datetime import datetime
from trinops.models import QueryInfo, QueryState


def test_query_info_creation():
    qi = QueryInfo(
        query_id="20260310_143549_08022_abc",
        state=QueryState.RUNNING,
        query="SELECT * FROM big_table",
        user="loki",
        source="trinops",
        created=datetime(2026, 3, 10, 14, 35, 49),
        started=datetime(2026, 3, 10, 14, 35, 50),
        ended=None,
        cpu_time_millis=19212,
        wall_time_millis=53095,
        queued_time_millis=100,
        elapsed_time_millis=6872,
        peak_memory_bytes=8650480,
        cumulative_memory_bytes=50000000,
        processed_rows=34148040,
        processed_bytes=474640412,
        error_code=None,
        error_message=None,
    )
    assert qi.query_id == "20260310_143549_08022_abc"
    assert qi.state == QueryState.RUNNING
    assert qi.is_terminal is False


def test_query_state_terminal():
    assert QueryState.FINISHED.is_terminal is True
    assert QueryState.FAILED.is_terminal is True
    assert QueryState.RUNNING.is_terminal is False
    assert QueryState.QUEUED.is_terminal is False


def test_query_info_from_system_row():
    row = {
        "query_id": "20260310_143549_08022_abc",
        "state": "RUNNING",
        "query": "SELECT 1",
        "user": "loki",
        "source": "trino-cli",
        "created": datetime(2026, 3, 10, 14, 35, 49),
        "started": datetime(2026, 3, 10, 14, 35, 50),
        "end": None,
        "cumulative_memory": 50000000.0,
        "peak_memory_bytes": 8650480,
        "cpu_time": 19.212,
        "wall_time": 53.095,
        "queued_time": 0.1,
        "elapsed_time": 6.872,
        "processed_rows": 34148040,
        "processed_bytes": 474640412,
        "error_code": None,
        "error_message": None,
    }
    qi = QueryInfo.from_system_row(row)
    assert qi.query_id == "20260310_143549_08022_abc"
    assert qi.state == QueryState.RUNNING
    assert qi.cpu_time_millis == 19212
    assert qi.wall_time_millis == 53095
    assert qi.elapsed_time_millis == 6872


def test_query_info_truncated_sql():
    qi = QueryInfo(
        query_id="test",
        state=QueryState.RUNNING,
        query="SELECT " + "x, " * 1000 + "y FROM t",
        user="loki",
        source="test",
        created=datetime.now(),
    )
    assert qi.truncated_sql(80).endswith("...")
    assert len(qi.truncated_sql(80)) <= 80
