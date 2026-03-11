"""Trino client abstraction for trinops."""

from __future__ import annotations

from typing import Optional

from trinops.backend import QueryBackend, SqlQueryBackend
from trinops.config import ConnectionProfile
from trinops.models import QueryInfo


class TrinopsClient:
    def __init__(self, backend: QueryBackend) -> None:
        self._backend = backend

    @classmethod
    def from_profile(cls, profile: ConnectionProfile) -> TrinopsClient:
        backend = SqlQueryBackend(profile)
        return cls(backend=backend)

    def list_queries(self, state: Optional[str] = None) -> list[QueryInfo]:
        return self._backend.list_queries(state=state)

    def get_query(self, query_id: str) -> Optional[QueryInfo]:
        return self._backend.get_query(query_id)

    def close(self) -> None:
        self._backend.close()
