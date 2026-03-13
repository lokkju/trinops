"""Version compatibility tests using VCR cassettes.

These tests replay recorded HTTP responses from real Trino versions
to verify that HttpQueryBackend parses all supported versions correctly.

To record cassettes: make record-all
"""
from __future__ import annotations

import pytest

from trinops.backend import HttpQueryBackend
from trinops.client import TrinopsClient
from trinops.config import ConnectionProfile
from trinops.models import QueryState


def _make_profile() -> ConnectionProfile:
    """Create a profile pointing at the recorded server."""
    return ConnectionProfile(
        server="127.0.0.1:8080",
        scheme="http",
        auth="none",
        user="trinops-recorder",
    )


def test_list_queries(trino_version):
    """list_queries returns QueryInfo objects with valid core fields."""
    version, use_cassette, _metadata = trino_version
    profile = _make_profile()
    backend = HttpQueryBackend(profile)

    with use_cassette():
        queries = backend.list_queries()

    assert len(queries) > 0, f"No queries returned for Trino {version}"
    for qi in queries:
        assert qi.query_id, "query_id must not be empty"
        assert isinstance(qi.state, QueryState), f"state must be QueryState, got {type(qi.state)}"
        assert qi.user, "user must not be empty"
        assert qi.created is not None, "created must not be None"
        assert qi.query, "query SQL must not be empty"


def test_get_query(trino_version):
    """get_query returns a QueryInfo with detail fields populated."""
    version, use_cassette, metadata = trino_version
    profile = _make_profile()
    backend = HttpQueryBackend(profile)

    # Use the exact query ID recorded in the cassette
    query_id = metadata["detail_query_id"]

    with use_cassette():
        qi = backend.get_query(query_id)

    assert qi is not None, f"get_query returned None for {query_id}"
    assert qi.query_id == query_id
    assert isinstance(qi.state, QueryState)
    assert qi.user
    assert qi.query


def test_get_info(trino_version):
    """get_info returns version and uptime from /v1/info."""
    version, use_cassette, _metadata = trino_version
    profile = _make_profile()
    backend = HttpQueryBackend(profile)

    with use_cassette():
        info = backend.get_info()

    if info is None:
        pytest.skip(f"Trino {version} does not expose /v1/info")

    assert "nodeVersion" in info
    assert isinstance(info["nodeVersion"], dict)
    assert "version" in info["nodeVersion"]
    assert isinstance(info["nodeVersion"]["version"], str)
    assert "uptime" in info
    assert isinstance(info["uptime"], str)


def test_get_cluster(trino_version):
    """get_cluster returns worker count from /v1/cluster."""
    version, use_cassette, _metadata = trino_version
    profile = _make_profile()
    backend = HttpQueryBackend(profile)

    with use_cassette():
        cluster = backend.get_cluster()

    if cluster is None:
        pytest.skip(f"Trino {version} does not expose /v1/cluster")

    assert "activeWorkers" in cluster
    assert isinstance(cluster["activeWorkers"], int)


def test_kill_query(trino_version):
    """kill_query returns True for a recorded DELETE response."""
    version, use_cassette, metadata = trino_version
    profile = _make_profile()
    backend = HttpQueryBackend(profile)

    # Use the exact query ID that the recording script killed
    query_id = metadata["kill_query_id"]

    with use_cassette():
        result = backend.kill_query(query_id)

    assert result is True, f"kill_query should return True for recorded 204 response"


def test_build_cluster_stats(trino_version):
    """build_cluster_stats populates ClusterStats from recorded data."""
    version, use_cassette, _metadata = trino_version
    profile = _make_profile()
    client = TrinopsClient.from_profile(profile)

    with use_cassette():
        queries = client.list_queries()
        stats = client.build_cluster_stats(queries)

    assert stats.total_queries > 0
    # trino_version should be populated since all supported versions expose /v1/info
    if stats.trino_version is not None:
        assert isinstance(stats.trino_version, str)
        assert len(stats.trino_version) > 0
