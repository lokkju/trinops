"""Tests for HttpQueryBackend (Tasks 4 and 5)."""

from __future__ import annotations

import base64
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from trinops.backend import HttpQueryBackend, QueryBackend
from trinops.config import ConnectionProfile
from trinops.models import QueryState


BASIC_QUERY_INFO = {
    "queryId": "20260310_143549_08022_abc",
    "state": "RUNNING",
    "query": "SELECT * FROM t",
    "session": {"user": "loki", "source": "trinops"},
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


class FakeTrinoAPI(BaseHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import urlparse

        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/v1/query":
            self._json([BASIC_QUERY_INFO])
        elif path.startswith("/v1/query/"):
            qid = path.split("/")[-1]
            if qid == BASIC_QUERY_INFO["queryId"]:
                self._json(BASIC_QUERY_INFO)
            else:
                self.send_error(410, "Gone")
        elif self.path == "/v1/info":
            self._json(
                {
                    "nodeVersion": {"version": "449"},
                    "uptime": "1.00h",
                    "starting": False,
                }
            )
        else:
            self.send_error(404)

    def _json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def _make_server(handler_cls=FakeTrinoAPI):
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_http_backend_is_query_backend():
    assert hasattr(HttpQueryBackend, "list_queries")
    assert hasattr(HttpQueryBackend, "get_query")
    assert hasattr(HttpQueryBackend, "close")


def test_http_backend_list_queries():
    server = _make_server()
    port = server.server_address[1]
    profile = ConnectionProfile(
        server=f"127.0.0.1:{port}", scheme="http", auth="none", user="dev"
    )
    backend = HttpQueryBackend(profile)
    try:
        queries = backend.list_queries()
        assert len(queries) == 1
        assert queries[0].query_id == "20260310_143549_08022_abc"
        assert queries[0].state == QueryState.RUNNING
        assert queries[0].user == "loki"
    finally:
        server.shutdown()


def test_http_backend_list_queries_with_state():
    server = _make_server()
    port = server.server_address[1]
    profile = ConnectionProfile(
        server=f"127.0.0.1:{port}", scheme="http", auth="none", user="dev"
    )
    backend = HttpQueryBackend(profile)
    try:
        queries = backend.list_queries(state="RUNNING")
        assert len(queries) == 1
    finally:
        server.shutdown()


def test_http_backend_get_query():
    server = _make_server()
    port = server.server_address[1]
    profile = ConnectionProfile(
        server=f"127.0.0.1:{port}", scheme="http", auth="none", user="dev"
    )
    backend = HttpQueryBackend(profile)
    try:
        qi = backend.get_query("20260310_143549_08022_abc")
        assert qi is not None
        assert qi.query_id == "20260310_143549_08022_abc"
    finally:
        server.shutdown()


def test_http_backend_get_query_not_found():
    server = _make_server()
    port = server.server_address[1]
    profile = ConnectionProfile(
        server=f"127.0.0.1:{port}", scheme="http", auth="none", user="dev"
    )
    backend = HttpQueryBackend(profile)
    try:
        qi = backend.get_query("nonexistent")
        assert qi is None
    finally:
        server.shutdown()


# Task 5: Connection check tests


def test_check_connection_success():
    server = _make_server()
    port = server.server_address[1]
    profile = ConnectionProfile(
        server=f"127.0.0.1:{port}", scheme="http", auth="none", user="dev"
    )
    backend = HttpQueryBackend(profile)
    try:
        backend.check_connection()  # should not raise
    finally:
        server.shutdown()


def test_check_connection_unreachable():
    profile = ConnectionProfile(
        server="127.0.0.1:1", scheme="http", auth="none", user="dev"
    )
    backend = HttpQueryBackend(profile)
    with pytest.raises(ConnectionError, match="Cannot reach Trino"):
        backend.check_connection()


class FakeAuthFailAPI(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/v1/info":
            body = json.dumps({"starting": False}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/v1/query":
            self.send_error(401, "Unauthorized")
        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        pass


def test_check_connection_auth_failure():
    server = _make_server(FakeAuthFailAPI)
    port = server.server_address[1]
    profile = ConnectionProfile(
        server=f"127.0.0.1:{port}", scheme="http", auth="none", user="dev"
    )
    backend = HttpQueryBackend(profile)
    try:
        with pytest.raises(ConnectionError, match="Authentication failed"):
            backend.check_connection()
    finally:
        server.shutdown()


# Basic auth header test


class FakeAuthCheckAPI(BaseHTTPRequestHandler):
    received_auth = None

    def do_GET(self):
        self.__class__.received_auth = self.headers.get("Authorization")
        self._json([BASIC_QUERY_INFO])

    def _json(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def test_http_backend_basic_auth_header():
    handler_cls = type("H", (FakeAuthCheckAPI,), {"received_auth": None})
    server = _make_server(handler_cls)
    port = server.server_address[1]
    profile = ConnectionProfile(
        server=f"127.0.0.1:{port}",
        scheme="http",
        auth="basic",
        user="testuser",
        password="testpass",
    )
    backend = HttpQueryBackend(profile)
    try:
        backend.list_queries()
        expected = "Basic " + base64.b64encode(b"testuser:testpass").decode()
        assert handler_cls.received_auth == expected
    finally:
        server.shutdown()
