import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from unittest.mock import MagicMock, PropertyMock, patch

from trino_progress.progress import TrinoProgress
from trino_progress.stats import QueryStats


RUNNING_STATS_RESPONSE = {
    "stats": {
        "state": "RUNNING",
        "queued": False,
        "scheduled": True,
        "nodes": 4,
        "totalSplits": 100,
        "queuedSplits": 10,
        "runningSplits": 30,
        "completedSplits": 60,
        "cpuTimeMillis": 5000,
        "wallTimeMillis": 8000,
        "queuedTimeMillis": 100,
        "elapsedTimeMillis": 3000,
        "processedRows": 5000000,
        "processedBytes": 100000000,
        "physicalInputBytes": 100000000,
        "peakMemoryBytes": 4000000,
        "spilledBytes": 0,
    }
}

FINISHED_STATS_RESPONSE = {
    "stats": {
        **RUNNING_STATS_RESPONSE["stats"],
        "state": "FINISHED",
        "completedSplits": 100,
        "runningSplits": 0,
        "queuedSplits": 0,
    }
}


class FakeTrinoHandler(BaseHTTPRequestHandler):
    responses = []
    call_count = 0
    lock = threading.Lock()

    def do_GET(self):
        with self.__class__.lock:
            idx = min(self.__class__.call_count, len(self.__class__.responses) - 1)
            self.__class__.call_count += 1
        body = json.dumps(self.__class__.responses[idx]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def _make_server(responses):
    handler = type(
        "Handler",
        (FakeTrinoHandler,),
        {"responses": responses, "call_count": 0, "lock": threading.Lock()},
    )
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _make_mock_cursor(server_port, query_id="test_query"):
    cursor = MagicMock()
    cursor.query_id = query_id
    cursor.stats = {"queryId": query_id}
    cursor.connection = MagicMock()
    cursor.connection.host = "127.0.0.1"
    cursor.connection.port = server_port
    cursor.connection.http_scheme = "http"
    cursor.connection.auth = None
    return cursor


def test_context_manager_basic():
    server = _make_server([RUNNING_STATS_RESPONSE, FINISHED_STATS_RESPONSE])
    port = server.server_address[1]
    cursor = _make_mock_cursor(port)

    with TrinoProgress(cursor, display="stderr", interval=0.1) as tp:
        tp.execute("SELECT 1")
        tp.fetchall()

    server.shutdown()
    cursor.execute.assert_called_once_with("SELECT 1")
    cursor.fetchall.assert_called_once()


def _make_mock_connection(port):
    conn = MagicMock(spec=["host", "port", "http_scheme", "auth"])
    conn.host = "127.0.0.1"
    conn.port = port
    conn.http_scheme = "http"
    conn.auth = None
    return conn


def test_standalone_mode():
    server = _make_server([RUNNING_STATS_RESPONSE, FINISHED_STATS_RESPONSE])
    port = server.server_address[1]

    conn = _make_mock_connection(port)

    tp = TrinoProgress(conn, query_id="test_standalone", display="stderr", interval=0.1)
    tp.start()
    tp.wait(timeout=5)
    server.shutdown()


def test_display_auto_fallback():
    server = _make_server([FINISHED_STATS_RESPONSE])
    port = server.server_address[1]

    conn = _make_mock_connection(port)

    tp = TrinoProgress(conn, query_id="test_auto", display="auto", interval=0.1)
    tp.start()
    tp.wait(timeout=5)
    server.shutdown()


def test_multiple_displays():
    server = _make_server([FINISHED_STATS_RESPONSE])
    port = server.server_address[1]

    conn = _make_mock_connection(port)

    mock_display = MagicMock()
    tp = TrinoProgress(conn, query_id="test_multi", display=[mock_display], interval=0.1)
    tp.start()
    tp.wait(timeout=5)
    server.shutdown()

    assert mock_display.on_stats.called
    assert mock_display.close.called


def test_cursor_proxy_methods():
    server = _make_server([FINISHED_STATS_RESPONSE])
    port = server.server_address[1]
    cursor = _make_mock_cursor(port)
    cursor.fetchone.return_value = (1,)
    cursor.fetchmany.return_value = [(1,), (2,)]
    cursor.description = [("col1", "varchar")]

    with TrinoProgress(cursor, display="stderr", interval=0.1) as tp:
        tp.execute("SELECT 1")
        assert tp.fetchone() == (1,)
        assert tp.fetchmany(2) == [(1,), (2,)]
        assert tp.description == [("col1", "varchar")]

    server.shutdown()
