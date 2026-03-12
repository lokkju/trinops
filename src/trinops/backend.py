"""Query backend protocol and SQL implementation for trinops."""

from __future__ import annotations

import base64
import gzip
import json
import logging
import time
from typing import Optional, Protocol, runtime_checkable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

try:
    import orjson as _json
except ImportError:
    _json = json  # type: ignore[assignment]

_QUERY_PREVIEW_LEN = 300

_log = logging.getLogger(__name__)

import trino.dbapi

from trinops.auth import build_auth, resolve_password
from trinops.config import ConnectionProfile
from trinops.models import QueryInfo


@runtime_checkable
class QueryBackend(Protocol):
    def list_queries(self, state: Optional[str] = None, limit: int = 0, query_user: Optional[str] = None) -> list[QueryInfo]: ...
    def get_query(self, query_id: str) -> Optional[QueryInfo]: ...
    def close(self) -> None: ...


# Required columns (must exist in all Trino versions)
_REQUIRED_COLS = ["query_id", "state", "query", '"user"', "source", "created"]

# Optional columns — we try each candidate and use whichever exists.
# Maps our internal name -> list of candidate column names to try.
# Time columns: some clusters use seconds (cpu_time), others use millis (queued_time_ms).
_OPTIONAL_COL_CANDIDATES = {
    "started": ["started"],
    "end": ['"end"'],
    "cpu_time": ["cpu_time", "total_cpu_time"],
    "wall_time": ["wall_time"],
    "queued_time": ["queued_time"],
    "queued_time_ms": ["queued_time_ms"],
    "elapsed_time": ["elapsed_time"],
    "analysis_time_ms": ["analysis_time_ms"],
    "planning_time_ms": ["planning_time_ms"],
    "peak_memory_bytes": ["peak_memory_bytes"],
    "cumulative_memory": ["cumulative_memory"],
    "processed_rows": ["processed_rows"],
    "processed_bytes": ["processed_bytes"],
    "error_code": ["error_code"],
    "error_message": ["error_message"],
    "error_type": ["error_type"],
    "resource_group_id": ["resource_group_id"],
}


class SqlQueryBackend:
    """Queries system.runtime.queries via SQL. Current default backend."""

    def __init__(self, profile: ConnectionProfile) -> None:
        self._profile = profile
        self._conn = None
        self._select_sql: Optional[str] = None
        self._available_cols: Optional[set[str]] = None

    def _get_connection(self):
        if self._conn is None:
            host, _, port_str = self._profile.server.partition(":")
            port = int(port_str) if port_str else (443 if self._profile.scheme == "https" else 8080)
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

    def _discover_columns(self) -> None:
        """Query SHOW COLUMNS once to learn what this cluster has."""
        conn = self._get_connection()
        cursor = conn.cursor()
        t0 = time.monotonic()
        cursor.execute("SHOW COLUMNS FROM system.runtime.queries")
        rows = cursor.fetchall()
        self._available_cols = {row[0] for row in rows}
        _log.debug("Column discovery took %.3fs, found %d columns: %s",
                   time.monotonic() - t0, len(self._available_cols),
                   sorted(self._available_cols))

        # Build SELECT clause: required + whichever optional cols exist
        cols = list(_REQUIRED_COLS)
        for internal_name, candidates in _OPTIONAL_COL_CANDIDATES.items():
            for candidate in candidates:
                # Strip quotes for comparison with SHOW COLUMNS output
                bare = candidate.strip('"')
                if bare in self._available_cols:
                    if candidate != internal_name and bare != internal_name:
                        cols.append(f'{candidate} AS "{internal_name}"')
                    else:
                        cols.append(candidate)
                    break
        self._select_sql = f"SELECT {', '.join(cols)} FROM system.runtime.queries"

    def _get_select_sql(self) -> str:
        if self._select_sql is None:
            self._discover_columns()
        return self._select_sql

    def _query_to_dicts(self, cursor, rows) -> list[dict]:
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def list_queries(self, state: Optional[str] = None, limit: int = 0, query_user: Optional[str] = None) -> list[QueryInfo]:
        conn = self._get_connection()
        cursor = conn.cursor()

        sql = self._get_select_sql()
        params = []
        conditions = []
        if state is not None:
            conditions.append("state = ?")
            params.append(state)
        if query_user is not None:
            conditions.append('"user" = ?')
            params.append(query_user)
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY created DESC"
        if limit > 0:
            sql += f" LIMIT {int(limit)}"

        t0 = time.monotonic()
        cursor.execute(sql, params if params else None)
        rows = cursor.fetchall()
        t_fetch = time.monotonic()
        dicts = self._query_to_dicts(cursor, rows)
        result = [QueryInfo.from_system_row(row) for row in dicts]
        t_parse = time.monotonic()
        _log.debug("SQL list_queries: fetch=%.3fs parse(%d rows)=%.3fs total=%.3fs",
                   t_fetch - t0, len(result), t_parse - t_fetch, t_parse - t0)
        return result

    def get_query(self, query_id: str) -> Optional[QueryInfo]:
        conn = self._get_connection()
        cursor = conn.cursor()

        sql = self._get_select_sql() + " WHERE query_id = ?"
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
        port = int(port_str) if port_str else (443 if profile.scheme == "https" else 8080)
        self._base_url = f"{profile.scheme}://{host}:{port}"
        self._session = None  # requests.Session, used for oauth2/kerberos
        self._headers = self._build_auth(profile)

    def _build_auth(self, profile: ConnectionProfile) -> dict[str, str]:
        """Build auth headers, or configure a requests.Session for complex auth."""
        headers = {"Accept": "application/json", "Accept-Encoding": "gzip"}
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
            import requests as req
            from urllib3.util.retry import Retry
            from requests.adapters import HTTPAdapter
            self._session = req.Session()
            retries = Retry(total=3, backoff_factor=0.5,
                            status_forcelist=[502, 503, 504])
            adapter = HTTPAdapter(max_retries=retries)
            self._session.mount("http://", adapter)
            self._session.mount("https://", adapter)
            self._session.headers.update(headers)
            trino_auth = build_auth(profile)
            trino_auth.set_http_session(self._session)
            if method == "oauth2":
                try:
                    import keyring  # noqa: F401
                except ImportError:
                    import logging
                    logging.getLogger(__name__).warning(
                        "keyring is not installed; OAuth2 tokens will not be cached "
                        "across sessions. Install keyring to avoid re-authenticating: "
                        "pip install keyring"
                    )
        else:
            raise ValueError(f"Unknown auth method: {method!r}")

        return headers

    def _get_json(self, path: str):
        url = f"{self._base_url}{path}"
        t0 = time.monotonic()
        if self._session is not None:
            response = self._session.get(url, timeout=30)
            response.raise_for_status()
            wire = len(response.content)
            t_net = time.monotonic()
            data = _json.loads(response.content)
            t_parse = time.monotonic()
            _log.debug("GET %s: network=%.3fs json_parse=%.3fs wire=%d bytes",
                       path, t_net - t0, t_parse - t_net, wire)
            return data
        request = Request(url, headers=self._headers)
        with urlopen(request, timeout=30) as response:
            raw = response.read()
            t_net = time.monotonic()
            encoding = response.headers.get("Content-Encoding", "")
            if encoding == "gzip":
                raw = gzip.decompress(raw)
            data = _json.loads(raw)
            t_parse = time.monotonic()
            _log.debug("GET %s: network=%.3fs json_parse=%.3fs wire=%d bytes encoding=%s",
                       path, t_net - t0, t_parse - t_net, len(raw), encoding or "identity")
            return data

    def _get_all_queries_raw(self, state: Optional[str] = None) -> list:
        """Fetch /v1/query."""
        path = "/v1/query"
        if state is not None:
            from urllib.parse import quote
            path += f"?state={quote(state)}"
        return self._get_json_light(path)

    def _get_json_light(self, path: str):
        """Fetch JSON for list view. Full query text is preserved so detail
        views can display it without a second round-trip."""
        return self._get_json(path)

    def list_queries(self, state: Optional[str] = None, limit: int = 0, query_user: Optional[str] = None) -> list[QueryInfo]:
        t0 = time.monotonic()
        data = self._get_all_queries_raw(state=state)
        t_fetch = time.monotonic()
        if query_user is not None:
            data = [item for item in data if item.get("session", {}).get("user") == query_user]
        t_filter = time.monotonic()
        result = [QueryInfo.from_rest_response(item) for item in data]
        result.sort(key=lambda qi: qi.created, reverse=True)
        if limit > 0:
            result = result[:limit]
        t_parse = time.monotonic()
        _log.debug("list_queries: fetch=%.3fs filter=%.3fs parse(%d items)=%.3fs total=%.3fs",
                   t_fetch - t0, t_filter - t_fetch, len(result), t_parse - t_filter, t_parse - t0)
        return result

    def get_query(self, query_id: str) -> Optional[QueryInfo]:
        raw = self.get_query_raw(query_id)
        if raw is None:
            return None
        return QueryInfo.from_rest_response(raw)

    def get_query_raw(self, query_id: str) -> Optional[dict]:
        """Return raw REST API response for a single query."""
        try:
            return self._get_json(f"/v1/query/{query_id}")
        except HTTPError as e:
            if e.code in (404, 410):
                return None
            raise
        except Exception as e:
            if self._session is not None and hasattr(e, "response"):
                if e.response is not None and e.response.status_code in (404, 410):
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
        except Exception as e:
            if self._session is not None and hasattr(e, "response"):
                if e.response is not None and e.response.status_code in (401, 403):
                    raise ConnectionError(
                        f"Authentication failed (HTTP {e.response.status_code}). "
                        f"Check your auth configuration (current: {self._profile.auth})."
                    ) from e
            raise

    def close(self) -> None:
        if self._session is not None:
            self._session.close()
