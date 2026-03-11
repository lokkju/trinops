"""Query backend protocol and SQL implementation for trinops."""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

import trino.dbapi

from trinops.auth import build_auth
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
