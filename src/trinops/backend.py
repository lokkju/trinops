"""HTTP query backend for trinops."""

from __future__ import annotations

import base64
import gzip
import json
import logging
import time
from enum import Enum
from typing import Optional
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class EndpointState(Enum):
    """Tri-state availability for optional REST endpoints."""
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


# HTTP status codes that permanently mark an endpoint as unavailable
_PERMANENT_FAIL_CODES = {404, 405, 501}

try:
    import orjson as _json
except ImportError:
    _json = json  # type: ignore[assignment]

_QUERY_PREVIEW_LEN = 300

_log = logging.getLogger(__name__)

from trinops.auth import build_auth, resolve_password
from trinops.config import ConnectionProfile
from trinops.models import QueryInfo


class HttpQueryBackend:
    """Queries Trino REST API directly via /v1/query endpoints."""

    def __init__(self, profile: ConnectionProfile) -> None:
        self._profile = profile
        host, _, port_str = profile.server.partition(":")
        port = int(port_str) if port_str else (443 if profile.scheme == "https" else 8080)
        self._base_url = f"{profile.scheme}://{host}:{port}"
        self._session = None  # requests.Session, used for oauth2/kerberos
        self._headers = self._build_auth(profile)
        self._info_state = EndpointState.UNKNOWN
        self._cluster_state = EndpointState.UNKNOWN

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

    def _delete(self, path: str) -> int:
        """Send a DELETE request. Returns the HTTP status code."""
        url = f"{self._base_url}{path}"
        if self._session is not None:
            response = self._session.delete(url, timeout=30)
            return response.status_code
        request = Request(url, method="DELETE", headers=self._headers)
        try:
            with urlopen(request, timeout=30) as response:
                return response.status
        except HTTPError as e:
            return e.code

    def kill_query(self, query_id: str) -> bool:
        """Kill a query via DELETE /v1/query/{id}. Returns True on success, False if gone."""
        status = self._delete(f"/v1/query/{query_id}")
        if status in (200, 204):
            return True
        if status in (404, 410):
            return False
        raise HTTPError(
            f"{self._base_url}/v1/query/{query_id}",
            status, f"Kill query failed (HTTP {status})", {}, None,
        )

    def _try_optional_endpoint(self, path: str, state_attr: str) -> Optional[dict]:
        """Fetch an optional endpoint with tri-state availability tracking.

        Returns the parsed JSON on success, or None on failure/unavailability.
        Updates the availability flag stored in *state_attr*.
        """
        current = getattr(self, state_attr)
        if current == EndpointState.UNAVAILABLE:
            return None
        try:
            data = self._get_json(path)
            setattr(self, state_attr, EndpointState.AVAILABLE)
            return data
        except HTTPError as e:
            if e.code in _PERMANENT_FAIL_CODES:
                setattr(self, state_attr, EndpointState.UNAVAILABLE)
            _log.debug("Optional endpoint %s failed: %s", path, e)
            return None
        except Exception as e:
            # Handle requests-style exceptions (session path)
            status = None
            if hasattr(e, "response") and e.response is not None:
                status = e.response.status_code
            if status in _PERMANENT_FAIL_CODES:
                setattr(self, state_attr, EndpointState.UNAVAILABLE)
            _log.debug("Optional endpoint %s failed: %s", path, e)
            return None

    def get_info(self) -> Optional[dict]:
        """Fetch /v1/info. Returns None if unavailable."""
        return self._try_optional_endpoint("/v1/info", "_info_state")

    def get_cluster(self) -> Optional[dict]:
        """Fetch /v1/cluster. Returns None if unavailable."""
        return self._try_optional_endpoint("/v1/cluster", "_cluster_state")

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
