"""Tests for TUI detail tab widgets."""
from __future__ import annotations

import pytest

# Full REST response fixture — covers all tabs
FULL_QUERY_INFO = {
    "queryId": "20260314_071543_00002_wqrmk",
    "state": "RUNNING",
    "queryType": "SELECT",
    "query": "SELECT n.name AS nation_name, SUM(l.quantity) AS total_qty FROM tpch.sf1.lineitem l JOIN tpch.sf1.nation n ON l.suppkey = n.nationkey GROUP BY n.name ORDER BY total_qty DESC",
    "session": {
        "user": "alice",
        "source": "trinops",
        "catalog": "tpch",
        "schema": "sf1",
    },
    "resourceGroupId": ["global"],
    "queryStats": {
        "createTime": "2026-03-14T07:15:48.678Z",
        "endTime": None,
        "elapsedTime": "6.87s",
        "queuedTime": "0.10s",
        "planningTime": "1.23s",
        "executionTime": "5.54s",
        "totalCpuTime": "19.21s",
        "physicalInputDataSize": "474640412B",
        "physicalInputPositions": 100000000,
        "processedInputDataSize": "209715200B",
        "processedInputPositions": 34148040,
        "outputDataSize": "52428800B",
        "outputPositions": 1000,
        "physicalWrittenDataSize": "0B",
        "spilledDataSize": "0B",
        "peakUserMemoryReservation": "8650480B",
        "peakTotalMemoryReservation": "16777216B",
        "cumulativeUserMemory": 50000000.0,
        "completedTasks": 45,
        "totalTasks": 50,
        "completedDrivers": 450,
        "totalDrivers": 500,
    },
    "inputs": [
        {
            "catalogName": "tpch",
            "schema": "sf1",
            "table": "lineitem",
            "columns": [
                {"name": "suppkey", "type": "INTEGER"},
                {"name": "quantity", "type": "DOUBLE"},
            ],
        },
        {
            "catalogName": "tpch",
            "schema": "sf1",
            "table": "nation",
            "columns": [
                {"name": "nationkey", "type": "INTEGER"},
                {"name": "name", "type": "VARCHAR"},
            ],
        },
    ],
    "errorCode": None,
    "failureInfo": None,
    "warnings": [],
}

FAILED_QUERY_INFO = {
    "queryId": "20260314_000000_00001_xyz",
    "state": "FAILED",
    "query": "SELECT bad FROM t",
    "session": {"user": "admin"},
    "queryStats": {
        "createTime": "2026-03-14T14:00:00.000Z",
        "endTime": "2026-03-14T14:00:01.000Z",
        "elapsedTime": "1.00s",
        "queuedTime": "0.00ns",
        "totalCpuTime": "0.50s",
        "peakUserMemoryReservation": "0B",
        "peakTotalMemoryReservation": "0B",
        "processedInputPositions": 0,
        "physicalInputDataSize": "0B",
        "cumulativeUserMemory": 0.0,
        "completedTasks": 0,
        "totalTasks": 0,
        "completedDrivers": 0,
        "totalDrivers": 0,
    },
    "errorCode": {"code": 1, "name": "SYNTAX_ERROR", "type": "USER_ERROR"},
    "failureInfo": {"message": "line 1:8: Column 'bad' cannot be resolved"},
    "warnings": [],
}

MINIMAL_QUERY_INFO = {
    "queryId": "20260314_000000_00002_min",
    "state": "QUEUED",
    "query": "SELECT 1",
    "session": {"user": "bob"},
    "queryStats": {
        "createTime": "2026-03-14T12:00:00.000Z",
    },
}


def test_overview_tab_renders_core_fields():
    from trinops.tui.tabs.overview import OverviewTab

    tab = OverviewTab()
    tab._data = FULL_QUERY_INFO
    content = tab.render_text()
    assert "20260314_071543_00002_wqrmk" in content
    assert "RUNNING" in content
    assert "alice" in content
    assert "trinops" in content
    assert "tpch" in content
    assert "sf1" in content
    assert "SELECT" in content


def test_overview_tab_handles_minimal_data():
    from trinops.tui.tabs.overview import OverviewTab

    tab = OverviewTab()
    tab._data = MINIMAL_QUERY_INFO
    content = tab.render_text()
    assert "bob" in content
    assert "SELECT 1" in content


def test_stats_tab_renders_timing():
    from trinops.tui.tabs.stats import StatsTab

    tab = StatsTab()
    tab._data = FULL_QUERY_INFO
    content = tab.render_text()
    assert "Queued" in content
    assert "Planning" in content
    assert "Execution" in content
    assert "CPU" in content
    assert "Input" in content
    assert "Output" in content
    assert "45" in content  # completed tasks
    assert "50" in content  # total tasks


def test_stats_tab_handles_missing_fields():
    from trinops.tui.tabs.stats import StatsTab

    tab = StatsTab()
    tab._data = MINIMAL_QUERY_INFO
    content = tab.render_text()
    assert isinstance(content, str)


def test_tables_tab_renders_inputs():
    from trinops.tui.tabs.tables import TablesTab

    tab = TablesTab()
    tab._data = FULL_QUERY_INFO
    content = tab.render_text()
    assert "tpch.sf1.lineitem" in content
    assert "tpch.sf1.nation" in content
    assert "suppkey" in content
    assert "INTEGER" in content
    assert "name" in content
    assert "VARCHAR" in content


def test_tables_tab_no_inputs():
    from trinops.tui.tabs.tables import TablesTab

    tab = TablesTab()
    tab._data = MINIMAL_QUERY_INFO
    content = tab.render_text()
    assert "No table information" in content
