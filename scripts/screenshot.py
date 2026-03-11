"""Generate a TUI screenshot with mock data for the README."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from trinops.config import ConnectionProfile
from trinops.models import QueryInfo, QueryState
from trinops.tui.app import TrinopsApp

MOCK_QUERIES = [
    QueryInfo(
        query_id="20260311_091522_00142_abcde",
        state=QueryState.RUNNING,
        query="SELECT customer_id, SUM(order_total) AS revenue FROM warehouse.sales.orders WHERE order_date >= DATE '2026-01-01' GROUP BY customer_id ORDER BY revenue DESC LIMIT 100",
        user="analytics",
        source="trinops",
        created=datetime(2026, 3, 11, 9, 15, 22, tzinfo=timezone.utc),
        cpu_time_millis=34210,
        elapsed_time_millis=12870,
        queued_time_millis=100,
        peak_memory_bytes=268435456,
        cumulative_memory_bytes=500000000,
        processed_rows=48291053,
        processed_bytes=1073741824,
    ),
    QueryInfo(
        query_id="20260311_091801_00287_fghij",
        state=QueryState.RUNNING,
        query="INSERT INTO iceberg.reporting.daily_metrics SELECT date_trunc('day', event_time), count(*), avg(latency_ms) FROM kafka.events.api_calls GROUP BY 1",
        user="etl_service",
        source="airflow",
        created=datetime(2026, 3, 11, 9, 18, 1, tzinfo=timezone.utc),
        cpu_time_millis=89430,
        elapsed_time_millis=45200,
        queued_time_millis=2100,
        peak_memory_bytes=536870912,
        cumulative_memory_bytes=1200000000,
        processed_rows=127849201,
        processed_bytes=4294967296,
    ),
    QueryInfo(
        query_id="20260311_092034_00391_klmno",
        state=QueryState.PLANNING,
        query="WITH ranked AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY created_at DESC) AS rn FROM hive.app.sessions) SELECT * FROM ranked WHERE rn = 1",
        user="backend_svc",
        source="jdbc",
        created=datetime(2026, 3, 11, 9, 20, 34, tzinfo=timezone.utc),
        cpu_time_millis=0,
        elapsed_time_millis=1200,
        queued_time_millis=1200,
        peak_memory_bytes=0,
        cumulative_memory_bytes=0,
        processed_rows=0,
        processed_bytes=0,
    ),
    QueryInfo(
        query_id="20260311_092112_00445_pqrst",
        state=QueryState.RUNNING,
        query="SELECT u.email, count(o.id) AS order_count FROM postgres.public.users u JOIN warehouse.sales.orders o ON u.id = o.user_id GROUP BY u.email HAVING count(o.id) > 10",
        user="analytics",
        source="superset",
        created=datetime(2026, 3, 11, 9, 21, 12, tzinfo=timezone.utc),
        cpu_time_millis=5670,
        elapsed_time_millis=3400,
        queued_time_millis=50,
        peak_memory_bytes=134217728,
        cumulative_memory_bytes=200000000,
        processed_rows=2841092,
        processed_bytes=536870912,
    ),
    QueryInfo(
        query_id="20260311_091105_00098_uvwxy",
        state=QueryState.FINISHING,
        query="CREATE TABLE iceberg.staging.user_segments AS SELECT user_id, segment FROM ml.predictions.latest WHERE confidence > 0.85",
        user="ml_pipeline",
        source="spark",
        created=datetime(2026, 3, 11, 9, 11, 5, tzinfo=timezone.utc),
        cpu_time_millis=142300,
        elapsed_time_millis=98700,
        queued_time_millis=500,
        peak_memory_bytes=1073741824,
        cumulative_memory_bytes=3000000000,
        processed_rows=52019384,
        processed_bytes=8589934592,
    ),
    QueryInfo(
        query_id="20260311_092200_00512_zabcd",
        state=QueryState.QUEUED,
        query="ANALYZE iceberg.warehouse.fact_events",
        user="dba_admin",
        source="cli",
        created=datetime(2026, 3, 11, 9, 22, 0, tzinfo=timezone.utc),
        cpu_time_millis=0,
        elapsed_time_millis=500,
        queued_time_millis=500,
        peak_memory_bytes=0,
        cumulative_memory_bytes=0,
        processed_rows=0,
        processed_bytes=0,
    ),
    QueryInfo(
        query_id="20260311_090830_00051_efghi",
        state=QueryState.FAILED,
        query="SELECT * FROM hive.raw.events WHERE event_date = CURRENT_DATE AND payload.action = 'purchase'",
        user="analytics",
        source="trinops",
        created=datetime(2026, 3, 11, 9, 8, 30, tzinfo=timezone.utc),
        cpu_time_millis=1200,
        elapsed_time_millis=2300,
        queued_time_millis=100,
        peak_memory_bytes=67108864,
        cumulative_memory_bytes=100000000,
        processed_rows=0,
        processed_bytes=0,
        error_code="SYNTAX_ERROR",
        error_message="Column 'payload.action' cannot be resolved",
    ),
]


class MockTrinopsApp(TrinopsApp):
    """TrinopsApp subclass that uses mock data instead of a real Trino connection."""

    def on_mount(self) -> None:
        table = self.query_one("#query-table")
        table.add_columns("Query ID", "State", "User", "Elapsed", "Rows", "Memory", "SQL")
        table.cursor_type = "row"
        # Load mock data directly
        self._queries = MOCK_QUERIES
        self._loaded = True
        self._last_refresh = time.monotonic()
        self._update_table()
        self._update_status_bar()
        # Don't start any timers or workers


async def take_screenshot():
    profile = ConnectionProfile(
        server="trino.example.com:443",
        user="analytics",
    )
    app = MockTrinopsApp(profile=profile, interval=30.0)
    async with app.run_test(size=(120, 24)) as pilot:
        # Let the app render
        await pilot.pause()
        app.save_screenshot("docs/tui-screenshot.svg")


if __name__ == "__main__":
    asyncio.run(take_screenshot())
