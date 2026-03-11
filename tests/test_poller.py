import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from unittest.mock import MagicMock, PropertyMock

from trinops.progress.poller import QueryPoller
from trinops.progress.stats import QueryStats


FINISHED_RESPONSE = {
    "stats": {
        "state": "FINISHED",
        "queued": False,
        "scheduled": True,
        "nodes": 4,
        "totalSplits": 100,
        "queuedSplits": 0,
        "runningSplits": 0,
        "completedSplits": 100,
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

RUNNING_RESPONSE = {
    "stats": {
        **FINISHED_RESPONSE["stats"],
        "state": "RUNNING",
        "completedSplits": 50,
        "runningSplits": 30,
        "queuedSplits": 20,
    }
}


class FakeTrinoHandler(BaseHTTPRequestHandler):
    responses = []
    call_count = 0

    def do_GET(self):
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
    handler = type("Handler", (FakeTrinoHandler,), {"responses": responses, "call_count": 0})
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_poller_delivers_stats():
    server = _make_server([RUNNING_RESPONSE, FINISHED_RESPONSE])
    port = server.server_address[1]

    received = []
    callback = lambda stats: received.append(stats)

    poller = QueryPoller(
        host="127.0.0.1",
        port=port,
        http_scheme="http",
        query_id="test_query_1",
        interval=0.1,
    )
    poller.add_callback(callback)
    poller.start()
    poller.wait(timeout=5)
    server.shutdown()

    assert len(received) >= 2
    assert all(isinstance(s, QueryStats) for s in received)
    assert received[-1].state == "FINISHED"


def test_poller_stops_on_terminal_state():
    server = _make_server([FINISHED_RESPONSE])
    port = server.server_address[1]

    poller = QueryPoller(
        host="127.0.0.1",
        port=port,
        http_scheme="http",
        query_id="test_query_2",
        interval=0.1,
    )
    poller.start()
    poller.wait(timeout=5)
    server.shutdown()

    assert not poller.is_alive()


def test_poller_survives_transient_errors():
    server = _make_server([RUNNING_RESPONSE, FINISHED_RESPONSE])
    port = server.server_address[1]
    server.shutdown()

    received = []
    poller = QueryPoller(
        host="127.0.0.1",
        port=port,
        http_scheme="http",
        query_id="test_query_3",
        interval=0.1,
        max_failures=2,
    )
    poller.add_callback(lambda s: received.append(s))
    poller.start()
    poller.wait(timeout=3)

    assert not poller.is_alive()


def test_poller_from_connection():
    server = _make_server([FINISHED_RESPONSE])
    port = server.server_address[1]

    conn = MagicMock()
    conn.host = "127.0.0.1"
    conn.port = port
    conn.http_scheme = "http"
    conn.auth = None

    poller = QueryPoller.from_connection(conn, query_id="test_query_4", interval=0.1)
    poller.start()
    poller.wait(timeout=5)
    server.shutdown()

    assert not poller.is_alive()


def test_cursor_poller_delivers_stats():
    """Poller can poll stats from a cursor's stats property."""
    from trinops.progress.poller import CursorPoller
    from trinops.progress.stats import QueryStats

    mock_cursor = MagicMock()
    stats_sequence = [
        {
            "state": "RUNNING", "queued": False, "scheduled": True, "nodes": 4,
            "totalSplits": 100, "queuedSplits": 20, "runningSplits": 30,
            "completedSplits": 50, "cpuTimeMillis": 3000, "wallTimeMillis": 5000,
            "queuedTimeMillis": 100, "elapsedTimeMillis": 2000,
            "processedRows": 2000000, "processedBytes": 80000000,
            "physicalInputBytes": 80000000, "peakMemoryBytes": 5000000,
            "spilledBytes": 0,
        },
        {
            "state": "FINISHED", "queued": False, "scheduled": True, "nodes": 4,
            "totalSplits": 100, "queuedSplits": 0, "runningSplits": 0,
            "completedSplits": 100, "cpuTimeMillis": 5000, "wallTimeMillis": 8000,
            "queuedTimeMillis": 100, "elapsedTimeMillis": 3000,
            "processedRows": 5000000, "processedBytes": 100000000,
            "physicalInputBytes": 100000000, "peakMemoryBytes": 4000000,
            "spilledBytes": 0,
        },
    ]
    call_count = [0]
    def get_stats():
        idx = min(call_count[0], len(stats_sequence) - 1)
        call_count[0] += 1
        return stats_sequence[idx]

    type(mock_cursor).stats = PropertyMock(side_effect=get_stats)

    received = []
    poller = CursorPoller(cursor=mock_cursor, interval=0.1)
    poller.add_callback(lambda s: received.append(s))
    poller.start()
    poller.wait(timeout=5)

    assert len(received) >= 2
    assert received[-1].state == "FINISHED"
    assert not poller.is_alive()
