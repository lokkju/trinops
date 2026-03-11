from unittest.mock import MagicMock
from datetime import datetime

from trinops.client import TrinopsClient
from trinops.models import QueryInfo, QueryState


SAMPLE_QUERY = QueryInfo(
    query_id="20260310_143549_08022_abc",
    state=QueryState.RUNNING,
    query="SELECT * FROM t",
    user="loki",
    created=datetime(2026, 3, 10, 14, 35, 49),
)


def test_client_delegates_to_backend():
    backend = MagicMock()
    backend.list_queries.return_value = [SAMPLE_QUERY]

    client = TrinopsClient(backend=backend)
    queries = client.list_queries()

    assert len(queries) == 1
    assert queries[0].query_id == "20260310_143549_08022_abc"
    backend.list_queries.assert_called_once_with(state=None)


def test_client_passes_state_filter():
    backend = MagicMock()
    backend.list_queries.return_value = [SAMPLE_QUERY]

    client = TrinopsClient(backend=backend)
    client.list_queries(state="RUNNING")
    backend.list_queries.assert_called_once_with(state="RUNNING")


def test_client_get_query():
    backend = MagicMock()
    backend.get_query.return_value = SAMPLE_QUERY

    client = TrinopsClient(backend=backend)
    qi = client.get_query("20260310_143549_08022_abc")
    assert qi.query_id == "20260310_143549_08022_abc"


def test_client_from_profile():
    from trinops.config import ConnectionProfile
    from trinops.backend import HttpQueryBackend

    profile = ConnectionProfile(server="localhost:8080", auth="none", user="dev")
    client = TrinopsClient.from_profile(profile)
    assert isinstance(client._backend, HttpQueryBackend)


def test_client_from_profile_http():
    from trinops.config import ConnectionProfile
    from trinops.backend import HttpQueryBackend

    profile = ConnectionProfile(server="localhost:8080", auth="none", user="dev")
    client = TrinopsClient.from_profile(profile, backend="http")
    assert isinstance(client._backend, HttpQueryBackend)


def test_client_from_profile_sql():
    from trinops.config import ConnectionProfile
    from trinops.backend import SqlQueryBackend

    profile = ConnectionProfile(server="localhost:8080", auth="none", user="dev")
    client = TrinopsClient.from_profile(profile, backend="sql")
    assert isinstance(client._backend, SqlQueryBackend)
