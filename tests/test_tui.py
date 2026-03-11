import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

from trinops.models import QueryInfo, QueryState


SAMPLE_QUERIES = [
    QueryInfo(
        query_id="20260310_143549_08022_abc",
        state=QueryState.RUNNING,
        query="SELECT * FROM big_table",
        user="loki",
        source="trinops",
        created=datetime(2026, 3, 10, 14, 35, 49),
        cpu_time_millis=19212,
        elapsed_time_millis=6872,
        processed_rows=34148040,
        processed_bytes=474640412,
        peak_memory_bytes=8650480,
    ),
]


def test_tui_app_creates():
    from trinops.tui.app import TrinopsApp
    from trinops.config import ConnectionProfile

    profile = ConnectionProfile(server="localhost:8080", auth="none", user="dev")
    app = TrinopsApp(profile=profile)
    assert app is not None
