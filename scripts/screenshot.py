"""Generate TUI screenshots with mock data for documentation."""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone

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

MOCK_DETAIL_DATA = {
    "queryId": "20260311_091522_00142_abcde",
    "state": "RUNNING",
    "queryType": "SELECT",
    "query": "SELECT customer_id, SUM(order_total) AS revenue\nFROM warehouse.sales.orders\nWHERE order_date >= DATE '2026-01-01'\nGROUP BY customer_id\nORDER BY revenue DESC\nLIMIT 100",
    "session": {
        "user": "analytics",
        "source": "trinops",
        "catalog": "warehouse",
        "schema": "sales",
    },
    "resourceGroupId": ["global", "analytics"],
    "queryStats": {
        "createTime": "2026-03-11T09:15:22.000Z",
        "endTime": None,
        "elapsedTime": "12.87s",
        "queuedTime": "0.10s",
        "planningTime": "0.42s",
        "executionTime": "12.35s",
        "totalCpuTime": "34.21s",
        "physicalInputDataSize": "1073741824B",
        "physicalInputPositions": 48291053,
        "processedInputDataSize": "536870912B",
        "processedInputPositions": 24145526,
        "outputDataSize": "8388608B",
        "outputPositions": 100,
        "physicalWrittenDataSize": "0B",
        "spilledDataSize": "0B",
        "peakUserMemoryReservation": "268435456B",
        "peakTotalMemoryReservation": "536870912B",
        "cumulativeUserMemory": 500000000.0,
        "completedTasks": 38,
        "totalTasks": 42,
        "completedDrivers": 380,
        "totalDrivers": 420,
    },
    "inputs": [
        {
            "catalogName": "warehouse",
            "schema": "sales",
            "table": "orders",
            "columns": [
                {"name": "customer_id", "type": "BIGINT"},
                {"name": "order_total", "type": "DECIMAL(12,2)"},
                {"name": "order_date", "type": "DATE"},
            ],
        },
    ],
    "errorCode": None,
    "failureInfo": None,
    "warnings": [],
}

MOCK_FAILED_DETAIL = {
    "queryId": "20260311_090830_00051_efghi",
    "state": "FAILED",
    "queryType": "SELECT",
    "query": "SELECT * FROM hive.raw.events WHERE event_date = CURRENT_DATE AND payload.action = 'purchase'",
    "session": {"user": "analytics", "source": "trinops"},
    "queryStats": {
        "createTime": "2026-03-11T09:08:30.000Z",
        "endTime": "2026-03-11T09:08:32.300Z",
        "elapsedTime": "2.30s",
        "queuedTime": "0.10s",
        "totalCpuTime": "1.20s",
        "peakUserMemoryReservation": "67108864B",
        "peakTotalMemoryReservation": "134217728B",
        "cumulativeUserMemory": 100000000.0,
        "processedInputPositions": 0,
        "physicalInputDataSize": "0B",
        "completedTasks": 1,
        "totalTasks": 1,
        "completedDrivers": 2,
        "totalDrivers": 2,
    },
    "errorCode": {"code": 1, "name": "SYNTAX_ERROR", "type": "USER_ERROR"},
    "failureInfo": {"message": "line 1:72: Column 'payload.action' cannot be resolved"},
    "warnings": [],
}


class _FakeTimer:
    """Stands in for a Textual Timer so stop() calls don't raise."""

    def stop(self) -> None:
        pass


class MockTrinopsApp(TrinopsApp):
    """TrinopsApp subclass that uses mock data instead of a real Trino connection.

    The real TrinopsApp.on_mount runs first (via Textual's MRO dispatch) and sets
    up the DataTable columns, sort state, and carets.  We intercept the two
    scheduling methods so they load mock data synchronously instead of spawning
    workers, and we override set_interval so no background timers fire.
    """

    _mock_empty: bool = False
    _mock_detail_data: dict | None = None

    def set_interval(self, *args, **kwargs) -> _FakeTimer:  # type: ignore[override]
        return _FakeTimer()

    def _schedule_refresh(self) -> None:
        """Load mock data directly instead of spawning a Trino worker."""
        self._queries = [] if self._mock_empty else MOCK_QUERIES
        self._loaded = True
        self._refreshing = False
        self._last_refresh = time.monotonic()
        self._update_table()
        self._update_empty_message()
        self._update_status_bar()

    def _schedule_stats_refresh(self) -> None:
        pass  # No cluster to query.

    def _fetch_query_raw(self, query_id: str) -> dict | None:
        """Return mock detail data instead of hitting the Trino API."""
        if self._mock_detail_data is not None:
            return self._mock_detail_data
        return MOCK_DETAIL_DATA


OUTPUT_DIR = "docs/screenshots"


async def capture_all() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    profile = ConnectionProfile(
        server="trino.example.com:443",
        user="analytics",
        allow_kill=True,
        confirm_kill=True,
    )

    # 1. Query list (default view with sort caret)
    app = MockTrinopsApp(profile=profile, interval=30.0)
    async with app.run_test(size=(140, 42)) as pilot:
        await pilot.pause()
        app.save_screenshot(f"{OUTPUT_DIR}/query-list.svg")

    # 2. Detail pane — Overview tab
    app = MockTrinopsApp(profile=profile, interval=30.0)
    async with app.run_test(size=(140, 42)) as pilot:
        await pilot.pause()
        app._show_detail_raw(MOCK_DETAIL_DATA)
        await pilot.pause()
        app.save_screenshot(f"{OUTPUT_DIR}/detail-overview.svg")

    # 3. Detail pane — Stats tab
    app = MockTrinopsApp(profile=profile, interval=30.0)
    async with app.run_test(size=(140, 42)) as pilot:
        await pilot.pause()
        app._show_detail_raw(MOCK_DETAIL_DATA)
        await pilot.pause()
        await pilot.press("right")  # Switch to Stats tab
        await pilot.pause()
        app.save_screenshot(f"{OUTPUT_DIR}/detail-stats.svg")

    # 4. Detail pane — Tables tab
    app = MockTrinopsApp(profile=profile, interval=30.0)
    async with app.run_test(size=(140, 42)) as pilot:
        await pilot.pause()
        app._show_detail_raw(MOCK_DETAIL_DATA)
        await pilot.pause()
        await pilot.press("right")  # Stats
        await pilot.press("right")  # Tables
        await pilot.pause()
        app.save_screenshot(f"{OUTPUT_DIR}/detail-tables.svg")

    # 5. Detail pane — Errors tab (failed query)
    app = MockTrinopsApp(profile=profile, interval=30.0)
    async with app.run_test(size=(140, 42)) as pilot:
        await pilot.pause()
        app._show_detail_raw(MOCK_FAILED_DETAIL)
        await pilot.pause()
        await pilot.press("right")  # Stats
        await pilot.press("right")  # Tables
        await pilot.press("right")  # Errors
        await pilot.pause()
        app.save_screenshot(f"{OUTPUT_DIR}/detail-errors.svg")

    # 6. Kill confirmation dialog
    app = MockTrinopsApp(profile=profile, interval=30.0)
    async with app.run_test(size=(140, 42)) as pilot:
        await pilot.pause()
        await pilot.press("k")  # Trigger kill dialog on first row
        await pilot.pause()
        app.save_screenshot(f"{OUTPUT_DIR}/kill-confirm.svg")

    # 7. Empty state
    app = MockTrinopsApp(profile=profile, interval=30.0)
    app._mock_empty = True
    async with app.run_test(size=(140, 42)) as pilot:
        await pilot.pause()
        app.save_screenshot(f"{OUTPUT_DIR}/empty-state.svg")

    # Hero PNG (for OG image / social cards)
    svg_to_png(f"{OUTPUT_DIR}/query-list.svg", f"{OUTPUT_DIR}/hero.png")

    # Hero GIF — sequence: list → detail → tabs → back to list
    gif_frames = [
        f"{OUTPUT_DIR}/query-list.svg",
        f"{OUTPUT_DIR}/detail-overview.svg",
        f"{OUTPUT_DIR}/detail-stats.svg",
        f"{OUTPUT_DIR}/detail-tables.svg",
        f"{OUTPUT_DIR}/query-list.svg",
    ]
    import tempfile
    import shutil
    tmpdir = tempfile.mkdtemp(prefix="trinops-hero-")
    temp_pngs = []
    for i, svg in enumerate(gif_frames):
        tmp = os.path.join(tmpdir, f"frame_{i}.png")
        svg_to_png(svg, tmp, scale=1.5)
        temp_pngs.append(tmp)
    assemble_gif(temp_pngs, f"{OUTPUT_DIR}/hero.gif", duration_ms=2000)
    shutil.rmtree(tmpdir)


def svg_to_png(svg_path: str, png_path: str, scale: float = 2.0) -> None:
    """Convert an SVG file to PNG at the given scale factor."""
    import cairosvg
    cairosvg.svg2png(url=svg_path, write_to=png_path, scale=scale)


def assemble_gif(png_paths: list[str], gif_path: str, duration_ms: int = 1500) -> None:
    """Combine multiple PNGs into an animated GIF."""
    from PIL import Image
    frames = [Image.open(p) for p in png_paths]
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
    )


if __name__ == "__main__":
    asyncio.run(capture_all())
