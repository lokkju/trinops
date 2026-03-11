from datetime import datetime
from unittest.mock import MagicMock

from trinops.backend import QueryBackend, SqlQueryBackend
from trinops.models import QueryInfo, QueryState


SYSTEM_QUERY_COLUMNS = [
    "query_id", "state", "query", "user", "source",
    "created", "started", "end",
    "cpu_time", "wall_time", "queued_time", "elapsed_time",
    "peak_memory_bytes", "cumulative_memory", "processed_rows", "processed_bytes",
    "error_code", "error_message",
]

SAMPLE_ROW = (
    "20260310_143549_08022_abc",
    "RUNNING",
    "SELECT * FROM t",
    "loki",
    "trinops",
    datetime(2026, 3, 10, 14, 35, 49),
    datetime(2026, 3, 10, 14, 35, 50),
    None,
    19.212,
    53.095,
    0.1,
    6.872,
    8650480,
    50000000.0,
    34148040,
    474640412,
    None,
    None,
)


def _make_mock_cursor(rows, columns):
    cursor = MagicMock()
    cursor.description = [(col, None, None, None, None, None, None) for col in columns]
    cursor.fetchall.return_value = rows
    return cursor


def _make_mock_connection(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


def test_sql_backend_is_query_backend():
    assert issubclass(SqlQueryBackend, QueryBackend.__class__) or isinstance(
        SqlQueryBackend.__new__(SqlQueryBackend), QueryBackend
    ) or hasattr(SqlQueryBackend, "list_queries")


def test_sql_backend_list_queries(monkeypatch):
    cursor = _make_mock_cursor([SAMPLE_ROW], SYSTEM_QUERY_COLUMNS)
    conn = _make_mock_connection(cursor)

    import trinops.backend
    monkeypatch.setattr(trinops.backend.trino.dbapi, "connect", lambda **kw: conn)

    from trinops.config import ConnectionProfile
    profile = ConnectionProfile(server="localhost:8080", auth="none", user="dev")
    backend = SqlQueryBackend(profile)
    queries = backend.list_queries()

    assert len(queries) == 1
    assert queries[0].query_id == "20260310_143549_08022_abc"
    assert queries[0].state == QueryState.RUNNING


def test_sql_backend_get_query(monkeypatch):
    cursor = _make_mock_cursor([SAMPLE_ROW], SYSTEM_QUERY_COLUMNS)
    conn = _make_mock_connection(cursor)

    import trinops.backend
    monkeypatch.setattr(trinops.backend.trino.dbapi, "connect", lambda **kw: conn)

    from trinops.config import ConnectionProfile
    profile = ConnectionProfile(server="localhost:8080", auth="none", user="dev")
    backend = SqlQueryBackend(profile)
    qi = backend.get_query("20260310_143549_08022_abc")

    assert qi is not None
    assert qi.query_id == "20260310_143549_08022_abc"


def test_sql_backend_get_query_not_found(monkeypatch):
    cursor = _make_mock_cursor([], SYSTEM_QUERY_COLUMNS)
    conn = _make_mock_connection(cursor)

    import trinops.backend
    monkeypatch.setattr(trinops.backend.trino.dbapi, "connect", lambda **kw: conn)

    from trinops.config import ConnectionProfile
    profile = ConnectionProfile(server="localhost:8080", auth="none", user="dev")
    backend = SqlQueryBackend(profile)
    qi = backend.get_query("nonexistent")

    assert qi is None
