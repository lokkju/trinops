"""Trino client abstraction for trinops."""

from __future__ import annotations

from typing import Optional

from trinops.backend import QueryBackend, HttpQueryBackend, SqlQueryBackend
from trinops.config import ConnectionProfile
from trinops.models import QueryInfo


class TrinopsClient:
    def __init__(self, backend: QueryBackend, profile: Optional[ConnectionProfile] = None) -> None:
        self._backend = backend
        self._profile = profile

    @classmethod
    def from_profile(cls, profile: ConnectionProfile, backend: str = "http") -> TrinopsClient:
        if backend == "sql":
            return cls(backend=SqlQueryBackend(profile), profile=profile)
        return cls(backend=HttpQueryBackend(profile), profile=profile)

    def check_connection(self) -> None:
        """Verify connectivity and auth via HTTP health check."""
        # Always use HTTP for connection checks — /v1/info is fast and
        # doesn't require a full SQL session.
        if isinstance(self._backend, HttpQueryBackend):
            self._backend.check_connection()
        elif self._profile is not None:
            http = HttpQueryBackend(self._profile)
            try:
                http.check_connection()
            finally:
                http.close()

    def list_queries(self, state: Optional[str] = None, limit: int = 0, query_user: Optional[str] = None) -> list[QueryInfo]:
        return self._backend.list_queries(state=state, limit=limit, query_user=query_user)

    def get_query(self, query_id: str) -> Optional[QueryInfo]:
        return self._backend.get_query(query_id)

    def close(self) -> None:
        self._backend.close()
