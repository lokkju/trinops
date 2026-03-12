"""Trino client abstraction for trinops."""

from __future__ import annotations

from typing import Optional

from trinops.backend import HttpQueryBackend
from trinops.config import ConnectionProfile
from trinops.formatting import parse_duration_millis
from trinops.models import ClusterStats, QueryInfo


class TrinopsClient:
    def __init__(self, backend: HttpQueryBackend, profile: Optional[ConnectionProfile] = None) -> None:
        self._backend = backend
        self._profile = profile

    @classmethod
    def from_profile(cls, profile: ConnectionProfile) -> TrinopsClient:
        return cls(backend=HttpQueryBackend(profile), profile=profile)

    def check_connection(self) -> None:
        """Verify connectivity and auth via HTTP health check."""
        self._backend.check_connection()

    def list_queries(self, state: Optional[str] = None, limit: int = 0, query_user: Optional[str] = None) -> list[QueryInfo]:
        return self._backend.list_queries(state=state, limit=limit, query_user=query_user)

    def get_query(self, query_id: str) -> Optional[QueryInfo]:
        return self._backend.get_query(query_id)

    def get_query_raw(self, query_id: str) -> Optional[dict]:
        """Return raw REST API response for a single query."""
        return self._backend.get_query_raw(query_id)

    def kill_query(self, query_id: str) -> bool:
        """Kill a query. Returns True on success, False if already gone."""
        return self._backend.kill_query(query_id)

    def build_cluster_stats(self, queries: list[QueryInfo]) -> ClusterStats:
        """Build cluster stats from queries and optional REST endpoints."""
        stats = ClusterStats.from_queries(queries)

        info = self._backend.get_info()
        if info is not None:
            version_obj = info.get("nodeVersion")
            if isinstance(version_obj, dict):
                stats.trino_version = version_obj.get("version")
            uptime_str = info.get("uptime")
            if uptime_str:
                try:
                    stats.uptime_millis = parse_duration_millis(uptime_str)
                except ValueError:
                    pass
            stats.starting = info.get("starting")

        cluster = self._backend.get_cluster()
        if cluster is not None:
            workers = cluster.get("activeWorkers")
            if workers is not None:
                stats.active_workers = int(workers)

        return stats

    def close(self) -> None:
        self._backend.close()
