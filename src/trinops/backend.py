"""Query backend protocol and SQL implementation for trinops."""

from __future__ import annotations

import base64
import json
from typing import Optional, Protocol, runtime_checkable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import trino.dbapi

from trinops.auth import build_auth, resolve_password
from trinops.config import ConnectionProfile
from trinops.models import QueryInfo


@runtime_checkable
class QueryBackend(Protocol):
    def list_queries(self, state: Optional[str] = None) -> list[QueryInfo]: ...
    def get_query(self, query_id: str) -> Optional[QueryInfo]: ...
    def close(self) -> None: ...


_SYSTEM_QUERY_SQL = """\
SELECT
    query_id, state, query, "user", source,
    created, started, "end",
    cpu_time, wall_time, queued_time, elapsed_time,
    peak_memory_bytes, cumulative_memory, processed_rows, processed_bytes,
    error_code, error_message
FROM system.runtime.queries
"""


class SqlQueryBackend:
    """Queries system.runtime.queries via SQL. Current default backend."""

    def __init__(self, profile: ConnectionProfile) -> None:
        self._profile = profile
        self._conn = None

    def _get_connection(self):
        if self._conn is None:
            host, _, port_str = self._profile.server.partition(":")
            port = int(port_str) if port_str else 8080
            auth = build_auth(self._profile)
            self._conn = trino.dbapi.connect(
                host=host,
                port=port,
                user=self._profile.user,
                catalog=self._profile.catalog or "system",
                schema=self._profile.schema or "runtime",
                http_scheme=self._profile.scheme,
                auth=auth,
            )
        return self._conn

    def _query_to_dicts(self, cursor, rows) -> list[dict]:
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def list_queries(self, state: Optional[str] = None) -> list[QueryInfo]:
        conn = self._get_connection()
        cursor = conn.cursor()

        sql = _SYSTEM_QUERY_SQL
        params = []
        if state is not None:
            sql += " WHERE state = ?"
            params.append(state)
        sql += " ORDER BY created DESC"

        cursor.execute(sql, params if params else None)
        rows = cursor.fetchall()
        dicts = self._query_to_dicts(cursor, rows)
        return [QueryInfo.from_system_row(row) for row in dicts]

    def get_query(self, query_id: str) -> Optional[QueryInfo]:
        conn = self._get_connection()
        cursor = conn.cursor()

        sql = _SYSTEM_QUERY_SQL + " WHERE query_id = ?"
        cursor.execute(sql, [query_id])
        rows = cursor.fetchall()
        if not rows:
            return None
        dicts = self._query_to_dicts(cursor, rows)
        return QueryInfo.from_system_row(dicts[0])

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


class HttpQueryBackend:
    """Queries Trino REST API directly via /v1/query endpoints."""

    def __init__(self, profile: ConnectionProfile) -> None:
        self._profile = profile
        host, _, port_str = profile.server.partition(":")
        port = int(port_str) if port_str else 8080
        self._base_url = f"{profile.scheme}://{host}:{port}"
        self._headers = self._build_headers(profile)

    @staticmethod
    def _build_headers(profile: ConnectionProfile) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if profile.user:
            headers["X-Trino-User"] = profile.user

        method = profile.auth
        if method == "none" or method is None:
            pass
        elif method == "basic":
            password = resolve_password(profile)
            if password is None:
                raise ValueError("basic auth requires password or password_cmd")
            creds = base64.b64encode(f"{profile.user}:{password}".encode()).decode()
            headers["Authorization"] = f"Basic {creds}"
        elif method == "jwt":
            token = profile.jwt_token
            if token is None:
                raise ValueError("jwt auth requires jwt_token")
            headers["Authorization"] = f"Bearer {token}"
        elif method in ("oauth2", "kerberos"):
            raise ValueError(
                f"{method} auth is not supported with the HTTP backend; "
                f"use --backend sql instead"
            )
        else:
            raise ValueError(f"Unknown auth method: {method!r}")

        return headers

    def _get_json(self, path: str):
        url = f"{self._base_url}{path}"
        request = Request(url, headers=self._headers)
        with urlopen(request, timeout=10) as response:
            return json.loads(response.read())

    def list_queries(self, state: Optional[str] = None) -> list[QueryInfo]:
        path = "/v1/query"
        if state:
            path += f"?state={state}"
        data = self._get_json(path)
        return [QueryInfo.from_rest_response(item) for item in data]

    def get_query(self, query_id: str) -> Optional[QueryInfo]:
        try:
            data = self._get_json(f"/v1/query/{query_id}")
            return QueryInfo.from_rest_response(data)
        except HTTPError as e:
            if e.code in (404, 410):
                return None
            raise

    def check_connection(self) -> None:
        """Verify server reachability and auth. Raises on failure."""
        # Step 1: reachability (no auth needed for /v1/info)
        url = f"{self._base_url}/v1/info"
        request = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(request, timeout=5) as response:
                json.loads(response.read())
        except Exception as e:
            raise ConnectionError(
                f"Cannot reach Trino server at {self._base_url}: {e}"
            ) from e

        # Step 2: auth check (uses configured credentials)
        try:
            self._get_json("/v1/query")
        except HTTPError as e:
            if e.code in (401, 403):
                raise ConnectionError(
                    f"Authentication failed (HTTP {e.code}). "
                    f"Check your auth configuration (current: {self._profile.auth})."
                ) from e
            raise

    def close(self) -> None:
        pass
