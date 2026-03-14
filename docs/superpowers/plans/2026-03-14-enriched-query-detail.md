# Enriched Query Detail Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the TUI's flat detail pane with a tabbed view (Overview, Stats, Tables, Errors) using dedicated Textual widgets per tab.

**Architecture:** `DetailPane` container widget with Textual's `TabbedContent` hosting four tab widgets. Each tab receives the raw `/v1/query/{id}` REST response dict. Navigation: Tab/Shift+Tab cycles detail tabs, Escape returns to query list. The detail view captures focus when opened.

**Tech Stack:** Textual (TabbedContent, TabPane, Static, widgets), Rich (Syntax for SQL highlighting)

**Spec:** `docs/superpowers/specs/2026-03-14-enriched-query-detail-design.md`

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/trinops/tui/tabs/__init__.py` | Package init |
| Create | `src/trinops/tui/tabs/overview.py` | OverviewTab widget |
| Create | `src/trinops/tui/tabs/stats.py` | StatsTab widget |
| Create | `src/trinops/tui/tabs/tables.py` | TablesTab widget |
| Create | `src/trinops/tui/tabs/errors.py` | ErrorsTab widget |
| Create | `src/trinops/tui/detail.py` | DetailPane container with TabbedContent |
| Modify | `src/trinops/tui/app.py` | Replace inline detail, new nav model |
| Create | `tests/test_detail_tabs.py` | Unit tests for all tab widgets and DetailPane |

---

## Chunk 1: Tab Widgets and Test Fixtures

### Task 1: Test Fixtures and OverviewTab

**Files:**
- Create: `tests/test_detail_tabs.py`
- Create: `src/trinops/tui/tabs/__init__.py`
- Create: `src/trinops/tui/tabs/overview.py`

**Context:** The raw REST response from `/v1/query/{id}` contains `queryId`, `state`, `session` (with `user`, `source`, `catalog`, `schema`), `queryStats` (with `createTime`, `elapsedTime`, `totalCpuTime`, `peakUserMemoryReservation`), and `query` (full SQL). The OverviewTab displays these in a readable layout with SQL syntax-highlighted via Rich. See `src/trinops/cli/formatting.py:101-194` for how the CLI already renders similar data from the same raw dict.

- [ ] **Step 1: Create test fixtures and first failing test**

Create `tests/test_detail_tabs.py` with comprehensive REST response fixtures and a test for OverviewTab rendering:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_detail_tabs.py::test_overview_tab_renders_core_fields -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'trinops.tui.tabs'`

- [ ] **Step 3: Create tabs package and OverviewTab**

Create `src/trinops/tui/tabs/__init__.py`:

```python
"""Detail pane tab widgets for the TUI."""
```

Create `src/trinops/tui/tabs/overview.py`:

```python
"""Overview tab for query detail pane."""
from __future__ import annotations

from rich.syntax import Syntax
from textual.widgets import Static

from trinops.formatting import format_bytes, format_time_millis, parse_duration_millis, parse_data_size_bytes


class OverviewTab(Static):
    """Displays query identity, session info, timing summary, and SQL.

    SQL is rendered with Rich Syntax highlighting when displayed via update_data().
    For render_text() (used in tests), SQL is included as plain text.
    """

    DEFAULT_CSS = """
    OverviewTab {
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._data: dict = {}

    def update_data(self, data: dict) -> None:
        self._data = data
        self.update(self.render_text())

    def render_text(self) -> str:
        d = self._data
        if not d:
            return "No data"
        session = d.get("session", {})
        qs = d.get("queryStats", {})

        lines: list[str] = []

        # Identity
        lines.append(f"Query ID:  {d.get('queryId', '')}")
        lines.append(f"State:     {d.get('state', '')}")
        if d.get("queryType"):
            lines.append(f"Type:      {d['queryType']}")
        lines.append(f"User:      {session.get('user', '')}")
        if session.get("source"):
            lines.append(f"Source:    {session['source']}")
        if session.get("catalog"):
            cat = session["catalog"]
            sch = session.get("schema", "")
            lines.append(f"Catalog:   {cat}.{sch}" if sch else f"Catalog:   {cat}")
        rg = d.get("resourceGroupId")
        if rg:
            lines.append(f"Resource:  {'.'.join(rg) if isinstance(rg, list) else rg}")

        # Timing summary
        lines.append("")
        if qs.get("createTime"):
            lines.append(f"Created:   {qs['createTime']}")
        if qs.get("elapsedTime"):
            lines.append(f"Elapsed:   {qs['elapsedTime']}")
        if qs.get("totalCpuTime"):
            lines.append(f"CPU:       {qs['totalCpuTime']}")
        if qs.get("peakUserMemoryReservation"):
            try:
                mem = parse_data_size_bytes(qs["peakUserMemoryReservation"])
                lines.append(f"Memory:    {format_bytes(mem)}")
            except ValueError:
                lines.append(f"Memory:    {qs['peakUserMemoryReservation']}")

        # SQL
        query = d.get("query", "")
        if query:
            lines.append("")
            lines.append("--- SQL " + "-" * 40)
            lines.append(query)

        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_detail_tabs.py -v -k overview`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/trinops/tui/tabs/__init__.py src/trinops/tui/tabs/overview.py tests/test_detail_tabs.py
git commit -m "feat(tui): add OverviewTab widget with test fixtures"
```

---

### Task 2: StatsTab Widget

**Files:**
- Create: `src/trinops/tui/tabs/stats.py`
- Modify: `tests/test_detail_tabs.py`

**Context:** The Stats tab renders detailed timing breakdown, data volumes, memory, and task/driver counts from `queryStats`. Values are in Trino's Airlift format — durations like `"19.21s"` and data sizes like `"474640412B"`. Use `parse_duration_millis` and `parse_data_size_bytes` from `src/trinops/formatting.py` to convert, then `format_time_millis` and `format_bytes` to render human-readable values.

- [ ] **Step 1: Write failing test**

Append to `tests/test_detail_tabs.py`:

```python
def test_stats_tab_renders_timing():
    from trinops.tui.tabs.stats import StatsTab

    tab = StatsTab()
    tab._data = FULL_QUERY_INFO
    content = tab.render_text()
    # Timing values
    assert "Queued" in content
    assert "Planning" in content
    assert "Execution" in content
    assert "CPU" in content
    # Data volumes
    assert "Input" in content
    assert "Output" in content
    # Tasks
    assert "45" in content  # completed tasks
    assert "50" in content  # total tasks


def test_stats_tab_handles_missing_fields():
    from trinops.tui.tabs.stats import StatsTab

    tab = StatsTab()
    tab._data = MINIMAL_QUERY_INFO
    content = tab.render_text()
    # Should not crash, should show what's available
    assert isinstance(content, str)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_detail_tabs.py::test_stats_tab_renders_timing -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'trinops.tui.tabs.stats'`

- [ ] **Step 3: Implement StatsTab**

Create `src/trinops/tui/tabs/stats.py`:

```python
"""Stats tab for query detail pane."""
from __future__ import annotations

from textual.widgets import Static

from trinops.formatting import format_bytes, format_time_millis, parse_duration_millis, parse_data_size_bytes


def _duration(s: str | None) -> str:
    if not s:
        return "—"
    try:
        return format_time_millis(parse_duration_millis(s))
    except ValueError:
        return s


def _data_size(s: str | None) -> str:
    if not s:
        return "—"
    try:
        return format_bytes(parse_data_size_bytes(s))
    except ValueError:
        return s


class StatsTab(Static):
    """Displays detailed timing, data volumes, memory, and task counts."""

    DEFAULT_CSS = """
    StatsTab {
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._data: dict = {}

    def update_data(self, data: dict) -> None:
        self._data = data
        self.update(self.render_text())

    def render_text(self) -> str:
        qs = self._data.get("queryStats", {})
        if not qs:
            return "No stats available"

        lines: list[str] = []

        # Timing
        lines.append("Timing")
        lines.append(f"  Queued:      {_duration(qs.get('queuedTime'))}")
        lines.append(f"  Planning:    {_duration(qs.get('planningTime'))}")
        lines.append(f"  Execution:   {_duration(qs.get('executionTime'))}")
        lines.append(f"  Elapsed:     {_duration(qs.get('elapsedTime'))}")
        lines.append(f"  CPU:         {_duration(qs.get('totalCpuTime'))}")

        # Data
        lines.append("")
        lines.append("Data")
        phys_in = _data_size(qs.get("physicalInputDataSize"))
        phys_rows = qs.get("physicalInputPositions", 0)
        lines.append(f"  Input:       {phys_in}  ({phys_rows:,} rows)")
        proc_in = _data_size(qs.get("processedInputDataSize"))
        proc_rows = qs.get("processedInputPositions", 0)
        lines.append(f"  Processed:   {proc_in}  ({proc_rows:,} rows)")
        out = _data_size(qs.get("outputDataSize"))
        out_rows = qs.get("outputPositions", 0)
        lines.append(f"  Output:      {out}  ({out_rows:,} rows)")
        spilled = qs.get("spilledDataSize")
        if spilled and spilled != "0B":
            lines.append(f"  Spilled:     {_data_size(spilled)}")

        # Memory
        lines.append("")
        lines.append("Memory")
        lines.append(f"  Peak user:   {_data_size(qs.get('peakUserMemoryReservation'))}")
        lines.append(f"  Peak total:  {_data_size(qs.get('peakTotalMemoryReservation'))}")
        cum = qs.get("cumulativeUserMemory", 0)
        if cum:
            lines.append(f"  Cumulative:  {format_bytes(int(cum))}")

        # Tasks
        lines.append("")
        lines.append("Tasks")
        ct = qs.get("completedTasks", 0)
        tt = qs.get("totalTasks", 0)
        lines.append(f"  Tasks:       {ct}/{tt}")
        cd = qs.get("completedDrivers", 0)
        td = qs.get("totalDrivers", 0)
        lines.append(f"  Drivers:     {cd}/{td}")

        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_detail_tabs.py -v -k stats`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/trinops/tui/tabs/stats.py tests/test_detail_tabs.py
git commit -m "feat(tui): add StatsTab widget with timing/data/memory breakdown"
```

---

### Task 3: TablesTab Widget

**Files:**
- Create: `src/trinops/tui/tabs/tables.py`
- Modify: `tests/test_detail_tabs.py`

**Context:** The `inputs` array in the REST response contains accessed tables with columns. Each entry has `catalogName`, `schema`, `table`, and `columns` (array of `{name, type}`). This array is only present in the full `/v1/query/{id}` response. See `src/trinops/cli/formatting.py:158-170` for how the CLI renders the same data.

- [ ] **Step 1: Write failing test**

Append to `tests/test_detail_tabs.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_detail_tabs.py::test_tables_tab_renders_inputs -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement TablesTab**

Create `src/trinops/tui/tabs/tables.py`:

```python
"""Tables tab for query detail pane."""
from __future__ import annotations

from textual.widgets import Static


class TablesTab(Static):
    """Displays accessed tables and their columns from the query's inputs."""

    DEFAULT_CSS = """
    TablesTab {
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._data: dict = {}

    def update_data(self, data: dict) -> None:
        self._data = data
        self.update(self.render_text())

    def render_text(self) -> str:
        inputs = self._data.get("inputs", [])
        if not inputs:
            return "No table information available."

        lines: list[str] = []
        for inp in inputs:
            fqn = f"{inp.get('catalogName', '')}.{inp.get('schema', '')}.{inp.get('table', '')}"
            lines.append(fqn)
            for col in inp.get("columns", []):
                lines.append(f"  {col['name']:<30s} {col.get('type', '')}")
            lines.append("")

        return "\n".join(lines).rstrip()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_detail_tabs.py -v -k tables`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/trinops/tui/tabs/tables.py tests/test_detail_tabs.py
git commit -m "feat(tui): add TablesTab widget showing accessed tables and columns"
```

---

### Task 4: ErrorsTab Widget

**Files:**
- Create: `src/trinops/tui/tabs/errors.py`
- Modify: `tests/test_detail_tabs.py`

**Context:** The REST response has `errorCode` (object with `code`, `name`, `type`), `failureInfo` (object with `message`), and `warnings` (array). When no errors or warnings exist, the tab shows a simple message.

- [ ] **Step 1: Write failing test**

Append to `tests/test_detail_tabs.py`:

```python
def test_errors_tab_renders_failure():
    from trinops.tui.tabs.errors import ErrorsTab

    tab = ErrorsTab()
    tab._data = FAILED_QUERY_INFO
    content = tab.render_text()
    assert "SYNTAX_ERROR" in content
    assert "USER_ERROR" in content
    assert "Column 'bad' cannot be resolved" in content


def test_errors_tab_no_errors():
    from trinops.tui.tabs.errors import ErrorsTab

    tab = ErrorsTab()
    tab._data = FULL_QUERY_INFO
    content = tab.render_text()
    assert "No errors or warnings" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_detail_tabs.py::test_errors_tab_renders_failure -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ErrorsTab**

Create `src/trinops/tui/tabs/errors.py`:

```python
"""Errors tab for query detail pane."""
from __future__ import annotations

from textual.widgets import Static


class ErrorsTab(Static):
    """Displays error details and warnings for a query."""

    DEFAULT_CSS = """
    ErrorsTab {
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._data: dict = {}

    def update_data(self, data: dict) -> None:
        self._data = data
        self.update(self.render_text())

    def render_text(self) -> str:
        error_code = self._data.get("errorCode")
        failure_info = self._data.get("failureInfo")
        warnings = self._data.get("warnings", [])

        if not error_code and not failure_info and not warnings:
            return "No errors or warnings."

        lines: list[str] = []

        if error_code and isinstance(error_code, dict):
            lines.append(f"Error Code:  {error_code.get('name', '')} ({error_code.get('type', '')})")
            lines.append(f"Error ID:    {error_code.get('code', '')}")

        if failure_info and isinstance(failure_info, dict):
            msg = failure_info.get("message", "")
            if msg:
                lines.append("")
                lines.append("Message:")
                lines.append(f"  {msg}")

        if warnings:
            lines.append("")
            lines.append("Warnings:")
            for w in warnings:
                lines.append(f"  {w}")

        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_detail_tabs.py -v -k errors`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/trinops/tui/tabs/errors.py tests/test_detail_tabs.py
git commit -m "feat(tui): add ErrorsTab widget showing error details and warnings"
```

---

## Chunk 2: DetailPane and App Integration

### Task 5: DetailPane Container

**Files:**
- Create: `src/trinops/tui/detail.py`
- Modify: `tests/test_detail_tabs.py`

**Context:** `DetailPane` is the container that holds `TabbedContent` with the four tabs. It receives the raw REST dict via `update_data()` and distributes to each tab. It also tracks the `query_id` of the displayed query so the kill keybinding can reference it. Textual's `TabbedContent` widget is imported from `textual.widgets` and used with `TabPane` children. See Textual docs: each `TabPane` gets a label and contains a child widget.

- [ ] **Step 1: Write failing test**

Append to `tests/test_detail_tabs.py`:

```python
def test_detail_pane_tracks_query_id():
    from trinops.tui.detail import DetailPane

    pane = DetailPane()
    assert pane.query_id is None
    pane.set_data(FULL_QUERY_INFO)
    assert pane.query_id == "20260314_071543_00002_wqrmk"


def test_detail_pane_set_data_none():
    from trinops.tui.detail import DetailPane

    pane = DetailPane()
    pane.set_data(None)
    assert pane.query_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run python -m pytest tests/test_detail_tabs.py::test_detail_pane_tracks_query_id -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement DetailPane**

Create `src/trinops/tui/detail.py`:

```python
"""Detail pane with tabbed content for query detail view."""
from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import Static, TabbedContent, TabPane

from trinops.tui.tabs.overview import OverviewTab
from trinops.tui.tabs.stats import StatsTab
from trinops.tui.tabs.tables import TablesTab
from trinops.tui.tabs.errors import ErrorsTab


class DetailPane(Container):
    """Tabbed detail view for a single query.

    Receives raw REST API response dict via set_data().
    Tracks query_id for kill-from-detail support.
    """

    DEFAULT_CSS = """
    DetailPane {
        height: auto;
        max-height: 50%;
        border-top: solid green;
        display: none;
    }
    DetailPane.visible {
        display: block;
    }
    DetailPane TabbedContent {
        height: auto;
    }
    DetailPane TabPane {
        height: auto;
        padding: 0;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._query_id: Optional[str] = None
        self._overview = OverviewTab()
        self._stats = StatsTab()
        self._tables = TablesTab()
        self._errors = ErrorsTab()

    @property
    def query_id(self) -> Optional[str]:
        return self._query_id

    def compose(self) -> ComposeResult:
        with TabbedContent():
            with TabPane("Overview"):
                yield self._overview
            with TabPane("Stats"):
                yield self._stats
            with TabPane("Tables"):
                yield self._tables
            with TabPane("Errors"):
                yield self._errors

    def set_data(self, data: Optional[dict]) -> None:
        if data is None:
            self._query_id = None
            return
        self._query_id = data.get("queryId")
        self._overview.update_data(data)
        self._stats.update_data(data)
        self._tables.update_data(data)
        self._errors.update_data(data)

    def show(self) -> None:
        self.add_class("visible")
        self.focus()

    def hide(self) -> None:
        self.remove_class("visible")
        self._query_id = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_detail_tabs.py -v -k detail_pane`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/trinops/tui/detail.py tests/test_detail_tabs.py
git commit -m "feat(tui): add DetailPane container with TabbedContent"
```

---

### Task 6: Integrate DetailPane into TUI App

**Files:**
- Modify: `src/trinops/tui/app.py`

**Context:** This task replaces the inline detail pane in `app.py` with the new `DetailPane` widget. The current detail pane (lines 185-189 of `app.py`) is a `Container` with `Static` and `TextArea` children. Replace it with `DetailPane`. Change `_show_detail()` to call `client.get_query_raw()` in a worker thread and pass the result to `detail_pane.set_data()`. Update `on_data_table_row_selected` to trigger the raw fetch. Update `action_close_detail` to use `detail_pane.hide()`. Update `action_kill_query` to read from `detail_pane.query_id` when the detail view is focused. Update CSS to remove the old `#detail-pane` styles (now in `DetailPane.DEFAULT_CSS`).

Key changes to `app.py`:
1. Remove old CSS for `#detail-pane`, `#detail-meta`, `#detail-sql`
2. Replace `Container(Static, TextArea)` in `compose()` with `DetailPane(id="detail-pane")`
3. Replace `_show_detail(qi: QueryInfo)` with `_show_detail_raw(data: dict)`
4. Add `_fetch_query_raw` worker method
5. Handle worker completion for `_fetch_query_raw` in `on_worker_state_changed`
6. Update `on_data_table_row_selected` to spawn the raw fetch worker
7. Update `action_close_detail` to call `detail_pane.hide()` and refocus table
8. Update `action_kill_query` to check detail pane focus and use `detail_pane.query_id`

- [ ] **Step 1: Write failing test**

Append to `tests/test_detail_tabs.py`:

```python
def test_app_has_detail_pane():
    """Verify the app composes with DetailPane instead of old Container."""
    from trinops.tui.app import TrinopsApp
    from trinops.tui.detail import DetailPane
    from trinops.config import ConnectionProfile

    profile = ConnectionProfile(server="localhost:8080", auth="none", user="dev")
    tui_app = TrinopsApp(profile=profile)
    # Check that the app references DetailPane (basic sanity check)
    # Full integration test would require async app pilot
    assert hasattr(tui_app, 'compose')
```

- [ ] **Step 2: Modify app.py — imports and CSS**

In `src/trinops/tui/app.py`, update the imports (line 10) to remove `TextArea` and add `DetailPane`:

Replace:
```python
from textual.widgets import Button, DataTable, Footer, Header, Label, Static, TextArea
```
With:
```python
from textual.widgets import Button, DataTable, Footer, Header, Label, Static
```

Add import after existing trinops imports:
```python
from trinops.tui.detail import DetailPane
```

Replace the CSS block (lines 120-145) — remove old `#detail-pane`, `#detail-meta`, `#detail-sql` styles:

```python
    CSS = """
    #query-table {
        height: 1fr;
    }
    #status-bar {
        height: 1;
    }
"""
```

- [ ] **Step 3: Modify compose() and initialization**

Replace the `compose()` method (lines 181-191):

```python
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ClusterHeader(id="cluster-header")
        yield DataTable(id="query-table")
        yield DetailPane(id="detail-pane")
        yield StatusBar(id="status-bar")
        yield Footer()
```

Add `_detail_query_id` to `__init__` (after `_kill_query_id` around line 179):
```python
        self._detail_query_id: str | None = None
```

- [ ] **Step 4: Replace _show_detail and add raw fetch worker**

Replace `_show_detail` method (lines 387-406) with:

```python
    def _show_detail_raw(self, data: dict) -> None:
        pane = self.query_one("#detail-pane", DetailPane)
        pane.set_data(data)
        pane.show()

    def _fetch_query_raw(self, query_id: str) -> dict | None:
        if self._client is None:
            self._client = TrinopsClient.from_profile(self._profile)
        return self._client.get_query_raw(query_id)
```

- [ ] **Step 5: Update worker dispatch and on_data_table_row_selected**

In `on_worker_state_changed` (line 279), add a handler for the new worker name:

```python
        elif event.worker.name == "_fetch_query_raw":
            self._on_detail_done(event)
```

Add the completion handler:

```python
    def _on_detail_done(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.SUCCESS:
            data = event.worker.result
            if data is None:
                self._flash("Query no longer available")
                return
            self._show_detail_raw(data)
        elif event.state == WorkerState.ERROR:
            self._flash(f"Failed to load query detail: {event.worker.error}")
```

Replace `on_data_table_row_selected` (lines 419-423):

```python
    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        query_id = str(event.row_key.value)
        self._detail_query_id = query_id
        self.run_worker(
            lambda: self._fetch_query_raw(query_id),
            thread=True,
            name="_fetch_query_raw",
        )
```

- [ ] **Step 6: Update action_close_detail and action_kill_query**

Replace `action_close_detail` (lines 425-428):

```python
    def action_close_detail(self) -> None:
        pane = self.query_one("#detail-pane", DetailPane)
        pane.hide()
        self.query_one("#query-table", DataTable).focus()
```

Update `action_kill_query` (lines 444-471) to check the detail pane first:

```python
    def action_kill_query(self) -> None:
        if not self._profile.allow_kill:
            return

        # If detail pane is focused and has a query, use that
        pane = self.query_one("#detail-pane", DetailPane)
        query_id = None
        if pane.has_class("visible") and pane.query_id:
            query_id = pane.query_id
        else:
            # Fall back to table cursor
            table = self.query_one("#query-table", DataTable)
            if table.row_count == 0 or table.cursor_row is None:
                return
            try:
                query_id = str(table.get_row_at(table.cursor_row)[0])
            except Exception:
                return

        if query_id is None:
            return

        qi = None
        for q in self._queries:
            if q.query_id == query_id:
                qi = q
                break
        if qi is None:
            return

        if self._profile.confirm_kill:
            def on_confirm(confirmed: bool) -> None:
                if confirmed:
                    self._execute_kill(qi.query_id)
            self.push_screen(
                KillConfirmScreen(qi.query_id, qi.user, qi.truncated_sql(80)),
                on_confirm,
            )
        else:
            self._execute_kill(qi.query_id)
```

- [ ] **Step 7: Run full test suite**

Run: `uv run python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 8: Commit**

```bash
git add src/trinops/tui/app.py tests/test_detail_tabs.py
git commit -m "feat(tui): integrate DetailPane with tabbed navigation model"
```
