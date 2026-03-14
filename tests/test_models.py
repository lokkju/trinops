from datetime import datetime
from trinops.models import QueryInfo, QueryState, ClusterStats


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


def test_query_state_dispatching():
    assert QueryState("DISPATCHING") == QueryState.DISPATCHING
    assert not QueryState.DISPATCHING.is_terminal


def test_query_state_waiting_for_resources():
    assert QueryState("WAITING_FOR_RESOURCES") == QueryState.WAITING_FOR_RESOURCES
    assert not QueryState.WAITING_FOR_RESOURCES.is_terminal


def test_query_info_from_rest_response():
    data = {
        "queryId": "20260310_143549_08022_abc",
        "state": "RUNNING",
        "query": "SELECT * FROM t",
        "session": {
            "user": "loki",
            "source": "trinops",
        },
        "queryStats": {
            "createTime": "2026-03-10T14:35:49.000Z",
            "endTime": None,
            "totalCpuTime": "19.21s",
            "elapsedTime": "6.87s",
            "queuedTime": "0.10s",
            "peakUserMemoryReservation": "8650480B",
            "processedInputPositions": 34148040,
            "physicalInputDataSize": "474640412B",
            "cumulativeUserMemory": 50000000.0,
        },
        "errorCode": None,
    }
    qi = QueryInfo.from_rest_response(data)
    assert qi.query_id == "20260310_143549_08022_abc"
    assert qi.state == QueryState.RUNNING
    assert qi.query == "SELECT * FROM t"
    assert qi.user == "loki"
    assert qi.source == "trinops"
    assert qi.cpu_time_millis == 19210
    assert qi.elapsed_time_millis == 6870
    assert qi.peak_memory_bytes == 8650480
    assert qi.processed_rows == 34148040
    assert qi.processed_bytes == 474640412


def test_query_info_from_rest_response_with_error():
    data = {
        "queryId": "20260310_000000_00001_xyz",
        "state": "FAILED",
        "query": "SELECT bad",
        "session": {"user": "admin"},
        "queryStats": {
            "createTime": "2026-03-10T14:00:00.000Z",
            "endTime": "2026-03-10T14:00:01.000Z",
            "totalCpuTime": "0.50s",
            "elapsedTime": "1.00s",
            "queuedTime": "0.00ns",
            "peakUserMemoryReservation": "0B",
            "processedInputPositions": 0,
            "physicalInputDataSize": "0B",
            "cumulativeUserMemory": 0.0,
        },
        "errorCode": {"code": 1, "name": "SYNTAX_ERROR", "type": "USER_ERROR"},
        "failureInfo": {"message": "line 1:8: Column 'bad' cannot be resolved"},
    }
    qi = QueryInfo.from_rest_response(data)
    assert qi.state == QueryState.FAILED
    assert qi.error_code == "SYNTAX_ERROR"
    assert qi.error_message == "line 1:8: Column 'bad' cannot be resolved"


# ClusterStats tests


def _make_queries():
    return [
        QueryInfo(
            query_id="q1", state=QueryState.RUNNING, query="SELECT 1", user="a",
            cpu_time_millis=5000, peak_memory_bytes=100_000,
            processed_rows=1_000_000, processed_bytes=500_000,
        ),
        QueryInfo(
            query_id="q2", state=QueryState.RUNNING, query="SELECT 2", user="b",
            cpu_time_millis=3000, peak_memory_bytes=200_000,
            processed_rows=2_000_000, processed_bytes=300_000,
        ),
        QueryInfo(
            query_id="q3", state=QueryState.QUEUED, query="SELECT 3", user="a",
            cpu_time_millis=0, peak_memory_bytes=0,
            processed_rows=0, processed_bytes=0,
        ),
        QueryInfo(
            query_id="q4", state=QueryState.FINISHED, query="SELECT 4", user="c",
            cpu_time_millis=10000, peak_memory_bytes=500_000,
            processed_rows=5_000_000, processed_bytes=1_000_000,
        ),
        QueryInfo(
            query_id="q5", state=QueryState.FAILED, query="SELECT bad", user="a",
            cpu_time_millis=100, peak_memory_bytes=1000,
            processed_rows=0, processed_bytes=0,
            error_code="SYNTAX_ERROR",
        ),
    ]


def test_cluster_stats_from_queries():
    queries = _make_queries()
    stats = ClusterStats.from_queries(queries)
    assert stats.total_queries == 5
    assert stats.running == 2
    assert stats.queued == 1
    assert stats.finished == 1
    assert stats.failed == 1
    assert stats.total_cpu_millis == 18100
    assert stats.total_peak_memory_bytes == 801_000
    assert stats.total_processed_rows == 8_000_000
    assert stats.total_processed_bytes == 1_800_000


def test_cluster_stats_from_empty_queries():
    stats = ClusterStats.from_queries([])
    assert stats.total_queries == 0
    assert stats.running == 0
    assert stats.total_cpu_millis == 0


def test_cluster_stats_format_line_full():
    stats = ClusterStats(
        trino_version="449",
        uptime_millis=266_400_000,
        total_queries=47, running=12, queued=3, finished=32, failed=0,
        total_cpu_millis=2_712_000,
        total_peak_memory_bytes=133_743_869_952,
        total_processed_rows=1_200_000_000,
        total_processed_bytes=365_072_220_160,
    )
    line = stats.format_line(width=200)
    assert "trino 449" in line
    assert "12 run" in line
    assert "3 queued" in line
    assert "32 done" in line
    assert "0 failed" not in line  # zero states omitted
    assert "up 3d2h" in line


def test_cluster_stats_format_line_degraded():
    stats = ClusterStats(
        total_queries=5, running=2, queued=1, finished=1, failed=1,
        total_cpu_millis=18100,
        total_peak_memory_bytes=801_000,
        total_processed_rows=8_000_000,
        total_processed_bytes=1_800_000,
    )
    line = stats.format_line(width=200)
    assert "trino" not in line
    assert "up " not in line
    assert "2 run" in line
    assert "1 failed" in line


def test_cluster_stats_format_line_wraps():
    stats = ClusterStats(
        trino_version="449",
        uptime_millis=266_400_000,
        total_queries=47, running=12, queued=3, finished=32, failed=0,
        total_cpu_millis=2_712_000,
        total_peak_memory_bytes=133_743_869_952,
        total_processed_rows=1_200_000_000,
        total_processed_bytes=365_072_220_160,
    )
    line = stats.format_line(width=40)
    assert "\n" in line
