"""Integration test: full flow with fake Trino server."""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from unittest.mock import MagicMock

from trinops import TrinoProgress, QueryStats


RESPONSES = [
    {
        "stats": {
            "state": "QUEUED",
            "queued": True, "scheduled": False, "nodes": 0,
            "totalSplits": 0, "queuedSplits": 0, "runningSplits": 0, "completedSplits": 0,
            "cpuTimeMillis": 0, "wallTimeMillis": 0, "queuedTimeMillis": 0, "elapsedTimeMillis": 0,
            "processedRows": 0, "processedBytes": 0, "physicalInputBytes": 0,
            "peakMemoryBytes": 0, "spilledBytes": 0,
        }
    },
    {
        "stats": {
            "state": "RUNNING",
            "queued": False, "scheduled": True, "nodes": 4,
            "totalSplits": 200, "queuedSplits": 50, "runningSplits": 50, "completedSplits": 100,
            "cpuTimeMillis": 3000, "wallTimeMillis": 5000, "queuedTimeMillis": 500, "elapsedTimeMillis": 2000,
            "processedRows": 2000000, "processedBytes": 80000000, "physicalInputBytes": 80000000,
            "peakMemoryBytes": 5000000, "spilledBytes": 0,
        }
    },
    {
        "stats": {
            "state": "FINISHED",
            "queued": False, "scheduled": True, "nodes": 4,
            "totalSplits": 200, "queuedSplits": 0, "runningSplits": 0, "completedSplits": 200,
            "cpuTimeMillis": 8000, "wallTimeMillis": 12000, "queuedTimeMillis": 500, "elapsedTimeMillis": 5000,
            "processedRows": 10000000, "processedBytes": 300000000, "physicalInputBytes": 300000000,
            "peakMemoryBytes": 8000000, "spilledBytes": 0,
        }
    },
]


def _make_server():
    class Handler(BaseHTTPRequestHandler):
        call_count = 0
        lock = threading.Lock()

        def do_GET(self):
            with self.__class__.lock:
                idx = min(self.__class__.call_count, len(RESPONSES) - 1)
                self.__class__.call_count += 1
            body = json.dumps(RESPONSES[idx]).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_full_context_manager_flow():
    server = _make_server()
    port = server.server_address[1]

    cursor = MagicMock()
    cursor.query_id = "integration_test_1"
    cursor.connection = MagicMock(spec=["host", "port", "http_scheme", "auth"])
    cursor.connection.host = "127.0.0.1"
    cursor.connection.port = port
    cursor.connection.http_scheme = "http"
    cursor.connection.auth = None
    cursor.fetchall.return_value = [(1, "hello"), (2, "world")]

    with TrinoProgress(cursor, display="stderr", interval=0.1) as tp:
        tp.execute("SELECT id, name FROM test_table")
        rows = tp.fetchall()

    assert rows == [(1, "hello"), (2, "world")]
    assert tp.last_stats is not None
    assert tp.last_stats.state == "FINISHED"
    server.shutdown()


def test_full_standalone_flow():
    server = _make_server()
    port = server.server_address[1]

    conn = MagicMock(spec=["host", "port", "http_scheme", "auth"])
    conn.host = "127.0.0.1"
    conn.port = port
    conn.http_scheme = "http"
    conn.auth = None

    collected = []
    mock_display = MagicMock()
    mock_display.on_stats = lambda s: collected.append(s)

    tp = TrinoProgress(conn, query_id="integration_test_2", display=[mock_display], interval=0.1)
    tp.start()
    tp.wait(timeout=10)

    assert len(collected) >= 2
    assert collected[-1].state == "FINISHED"
    assert collected[-1].processed_rows == 10000000
    server.shutdown()
