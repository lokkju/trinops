# trino-progress Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone PyPI package that provides real-time query progress monitoring for Trino with pluggable display backends.

**Architecture:** Observer pattern with three layers: a `QueryPoller` that polls the Trino REST API in a background thread, a `Display` protocol with tqdm/web/stderr implementations, and a `TrinoProgress` user-facing class that wires them together. Supports both cursor-wrapping context manager and standalone query ID tracking modes.

**Tech Stack:** Python 3.10+, trino-python-client (peer dep), tqdm (optional), stdlib http.server/threading/dataclasses

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `src/trino_progress/__init__.py`
- Create: `src/trino_progress/stats.py` (empty placeholder)
- Create: `src/trino_progress/poller.py` (empty placeholder)
- Create: `src/trino_progress/progress.py` (empty placeholder)
- Create: `src/trino_progress/display/__init__.py` (empty placeholder)
- Create: `src/trino_progress/display/tqdm.py` (empty placeholder)
- Create: `src/trino_progress/display/web.py` (empty placeholder)
- Create: `src/trino_progress/display/stderr.py` (empty placeholder)
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "trino-progress"
version = "0.1.0"
description = "Real-time query progress monitoring for Trino"
readme = "README.md"
license = "Apache-2.0"
requires-python = ">=3.10"
dependencies = [
    "trino>=0.320",
]

[project.optional-dependencies]
tqdm = ["tqdm>=4.60"]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "tqdm>=4.60",
]

[tool.hatch.build.targets.wheel]
packages = ["src/trino_progress"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Step 2: Create package files**

`src/trino_progress/__init__.py`:
```python
from trino_progress.stats import QueryStats, StageStats
from trino_progress.progress import TrinoProgress

__all__ = ["TrinoProgress", "QueryStats", "StageStats"]
```

All other files: empty or just a docstring placeholder.

`tests/__init__.py`: empty.

`tests/conftest.py`:
```python
"""Shared fixtures for trino-progress tests."""
```

**Step 3: Verify the package installs**

Run: `uv pip install -e ".[dev]"`
Expected: Installs successfully with trino and tqdm.

**Step 4: Commit**

```bash
git add pyproject.toml src/ tests/
git commit -m "chore: scaffold trino-progress package"
```

---

### Task 2: QueryStats Dataclass

**Files:**
- Create: `src/trino_progress/stats.py`
- Create: `tests/test_stats.py`

**Step 1: Write the failing test**

`tests/test_stats.py`:
```python
from trino_progress.stats import QueryStats, StageStats, parse_stats


SAMPLE_STATS = {
    "state": "RUNNING",
    "queued": False,
    "scheduled": True,
    "progressPercentage": 45.2,
    "nodes": 12,
    "totalSplits": 988,
    "queuedSplits": 100,
    "runningSplits": 200,
    "completedSplits": 688,
    "cpuTimeMillis": 19212,
    "wallTimeMillis": 53095,
    "queuedTimeMillis": 1,
    "elapsedTimeMillis": 6872,
    "planningTimeMillis": 50,
    "analysisTimeMillis": 30,
    "finishingTimeMillis": 0,
    "processedRows": 34148040,
    "processedBytes": 474640412,
    "physicalInputBytes": 474640412,
    "physicalWrittenBytes": 0,
    "peakMemoryBytes": 8650480,
    "spilledBytes": 0,
    "rootStage": {
        "stageId": "0",
        "state": "RUNNING",
        "done": False,
        "nodes": 1,
        "totalSplits": 100,
        "queuedSplits": 10,
        "runningSplits": 40,
        "completedSplits": 50,
        "cpuTimeMillis": 5000,
        "wallTimeMillis": 10000,
        "processedRows": 1000000,
        "processedBytes": 50000000,
        "failedTasks": 0,
        "subStages": [
            {
                "stageId": "1",
                "state": "FINISHED",
                "done": True,
                "nodes": 11,
                "totalSplits": 888,
                "queuedSplits": 0,
                "runningSplits": 0,
                "completedSplits": 888,
                "cpuTimeMillis": 14000,
                "wallTimeMillis": 43000,
                "processedRows": 33148040,
                "processedBytes": 424640412,
                "failedTasks": 0,
                "subStages": [],
            }
        ],
    },
}


def test_parse_stats_basic_fields():
    stats = parse_stats(SAMPLE_STATS)
    assert isinstance(stats, QueryStats)
    assert stats.state == "RUNNING"
    assert stats.total_splits == 988
    assert stats.completed_splits == 688
    assert stats.running_splits == 200
    assert stats.queued_splits == 100
    assert stats.cpu_time_millis == 19212
    assert stats.elapsed_time_millis == 6872
    assert stats.processed_rows == 34148040
    assert stats.processed_bytes == 474640412
    assert stats.peak_memory_bytes == 8650480
    assert stats.progress_percentage == 45.2


def test_parse_stats_stages():
    stats = parse_stats(SAMPLE_STATS)
    assert stats.root_stage is not None
    assert stats.root_stage.stage_id == "0"
    assert stats.root_stage.state == "RUNNING"
    assert stats.root_stage.completed_splits == 50
    assert len(stats.root_stage.sub_stages) == 1
    assert stats.root_stage.sub_stages[0].stage_id == "1"
    assert stats.root_stage.sub_stages[0].done is True


def test_parse_stats_immutable():
    stats = parse_stats(SAMPLE_STATS)
    try:
        stats.state = "FINISHED"
        assert False, "Should have raised"
    except AttributeError:
        pass


def test_parse_stats_missing_optional_fields():
    minimal = {
        "state": "QUEUED",
        "queued": True,
        "scheduled": False,
        "nodes": 0,
        "totalSplits": 0,
        "queuedSplits": 0,
        "runningSplits": 0,
        "completedSplits": 0,
        "cpuTimeMillis": 0,
        "wallTimeMillis": 0,
        "queuedTimeMillis": 0,
        "elapsedTimeMillis": 0,
        "processedRows": 0,
        "processedBytes": 0,
        "physicalInputBytes": 0,
        "peakMemoryBytes": 0,
        "spilledBytes": 0,
    }
    stats = parse_stats(minimal)
    assert stats.state == "QUEUED"
    assert stats.root_stage is None
    assert stats.progress_percentage is None
    assert stats.planning_time_millis is None


def test_query_stats_is_terminal():
    for state in ("FINISHED", "FAILED"):
        stats = parse_stats({**SAMPLE_STATS, "state": state})
        assert stats.is_terminal is True
    for state in ("QUEUED", "PLANNING", "STARTING", "RUNNING", "FINISHING"):
        stats = parse_stats({**SAMPLE_STATS, "state": state})
        assert stats.is_terminal is False
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_stats.py -v`
Expected: ImportError — `parse_stats` not defined.

**Step 3: Implement stats.py**

`src/trino_progress/stats.py`:
```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


TERMINAL_STATES = frozenset({"FINISHED", "FAILED"})


@dataclass(frozen=True)
class StageStats:
    stage_id: str
    state: str
    done: bool
    nodes: int
    total_splits: int
    queued_splits: int
    running_splits: int
    completed_splits: int
    cpu_time_millis: int
    wall_time_millis: int
    processed_rows: int
    processed_bytes: int
    failed_tasks: int
    sub_stages: tuple[StageStats, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class QueryStats:
    state: str
    queued: bool
    scheduled: bool
    nodes: int
    total_splits: int
    queued_splits: int
    running_splits: int
    completed_splits: int
    cpu_time_millis: int
    wall_time_millis: int
    queued_time_millis: int
    elapsed_time_millis: int
    processed_rows: int
    processed_bytes: int
    physical_input_bytes: int
    peak_memory_bytes: int
    spilled_bytes: int
    progress_percentage: Optional[float] = None
    planning_time_millis: Optional[int] = None
    analysis_time_millis: Optional[int] = None
    finishing_time_millis: Optional[int] = None
    physical_written_bytes: Optional[int] = None
    root_stage: Optional[StageStats] = None
    error: Optional[dict] = None

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES


def _parse_stage(data: dict) -> StageStats:
    return StageStats(
        stage_id=data["stageId"],
        state=data["state"],
        done=data.get("done", False),
        nodes=data.get("nodes", 0),
        total_splits=data.get("totalSplits", 0),
        queued_splits=data.get("queuedSplits", 0),
        running_splits=data.get("runningSplits", 0),
        completed_splits=data.get("completedSplits", 0),
        cpu_time_millis=data.get("cpuTimeMillis", 0),
        wall_time_millis=data.get("wallTimeMillis", 0),
        processed_rows=data.get("processedRows", 0),
        processed_bytes=data.get("processedBytes", 0),
        failed_tasks=data.get("failedTasks", 0),
        sub_stages=tuple(_parse_stage(s) for s in data.get("subStages", [])),
    )


def parse_stats(data: dict) -> QueryStats:
    root_stage = None
    if "rootStage" in data and data["rootStage"] is not None:
        root_stage = _parse_stage(data["rootStage"])

    return QueryStats(
        state=data["state"],
        queued=data.get("queued", False),
        scheduled=data.get("scheduled", False),
        nodes=data.get("nodes", 0),
        total_splits=data.get("totalSplits", 0),
        queued_splits=data.get("queuedSplits", 0),
        running_splits=data.get("runningSplits", 0),
        completed_splits=data.get("completedSplits", 0),
        cpu_time_millis=data.get("cpuTimeMillis", 0),
        wall_time_millis=data.get("wallTimeMillis", 0),
        queued_time_millis=data.get("queuedTimeMillis", 0),
        elapsed_time_millis=data.get("elapsedTimeMillis", 0),
        processed_rows=data.get("processedRows", 0),
        processed_bytes=data.get("processedBytes", 0),
        physical_input_bytes=data.get("physicalInputBytes", 0),
        peak_memory_bytes=data.get("peakMemoryBytes", 0),
        spilled_bytes=data.get("spilledBytes", 0),
        progress_percentage=data.get("progressPercentage"),
        planning_time_millis=data.get("planningTimeMillis"),
        analysis_time_millis=data.get("analysisTimeMillis"),
        finishing_time_millis=data.get("finishingTimeMillis"),
        physical_written_bytes=data.get("physicalWrittenBytes"),
        root_stage=root_stage,
        error=data.get("error"),
    )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_stats.py -v`
Expected: All 5 tests PASS.

**Step 5: Commit**

```bash
git add src/trino_progress/stats.py tests/test_stats.py
git commit -m "feat: add QueryStats dataclass with Trino JSON parsing"
```

---

### Task 3: Display Protocol and StderrDisplay

**Files:**
- Create: `src/trino_progress/display/__init__.py`
- Create: `src/trino_progress/display/stderr.py`
- Create: `tests/test_display_stderr.py`

**Step 1: Write the failing test**

`tests/test_display_stderr.py`:
```python
import io
from unittest.mock import patch

from trino_progress.display.stderr import StderrDisplay
from trino_progress.stats import parse_stats


RUNNING_STATS = {
    "state": "RUNNING",
    "queued": False,
    "scheduled": True,
    "nodes": 4,
    "totalSplits": 100,
    "queuedSplits": 10,
    "runningSplits": 30,
    "completedSplits": 60,
    "cpuTimeMillis": 5000,
    "wallTimeMillis": 8000,
    "queuedTimeMillis": 100,
    "elapsedTimeMillis": 3000,
    "processedRows": 5000000,
    "processedBytes": 100000000,
    "physicalInputBytes": 100000000,
    "peakMemoryBytes": 4000000,
    "spilledBytes": 0,
}


def test_stderr_display_on_stats():
    buf = io.StringIO()
    display = StderrDisplay(file=buf)
    stats = parse_stats(RUNNING_STATS)
    display.on_stats(stats)
    output = buf.getvalue()
    assert "RUNNING" in output
    assert "60/100" in output


def test_stderr_display_close():
    buf = io.StringIO()
    display = StderrDisplay(file=buf)
    stats = parse_stats(RUNNING_STATS)
    display.on_stats(stats)
    display.close()
    output = buf.getvalue()
    # close should print a newline to avoid overwriting the last line
    assert output.endswith("\n")


def test_stderr_display_finished():
    buf = io.StringIO()
    display = StderrDisplay(file=buf)
    finished = {**RUNNING_STATS, "state": "FINISHED", "completedSplits": 100, "runningSplits": 0, "queuedSplits": 0}
    stats = parse_stats(finished)
    display.on_stats(stats)
    output = buf.getvalue()
    assert "FINISHED" in output
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_display_stderr.py -v`
Expected: ImportError.

**Step 3: Implement display protocol and stderr display**

`src/trino_progress/display/__init__.py`:
```python
from __future__ import annotations

from typing import Protocol, runtime_checkable

from trino_progress.stats import QueryStats


@runtime_checkable
class Display(Protocol):
    def on_stats(self, stats: QueryStats) -> None: ...
    def close(self) -> None: ...
```

`src/trino_progress/display/stderr.py`:
```python
from __future__ import annotations

import sys
from typing import TextIO

from trino_progress.stats import QueryStats


def _format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def _format_time(millis: int) -> str:
    seconds = millis / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"


class StderrDisplay:
    def __init__(self, file: TextIO | None = None) -> None:
        self._file = file or sys.stderr
        self._started = False

    def on_stats(self, stats: QueryStats) -> None:
        splits = f"{stats.completed_splits}/{stats.total_splits}"
        rows = f"{stats.processed_rows:,} rows"
        bytes_ = _format_bytes(stats.processed_bytes)
        elapsed = _format_time(stats.elapsed_time_millis)
        cpu = _format_time(stats.cpu_time_millis)

        line = f"\r{stats.state} | splits {splits} | {rows} | {bytes_} | elapsed {elapsed} | cpu {cpu}"
        self._file.write(line)
        self._file.flush()
        self._started = True

    def close(self) -> None:
        if self._started:
            self._file.write("\n")
            self._file.flush()
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_display_stderr.py -v`
Expected: All 3 tests PASS.

**Step 5: Commit**

```bash
git add src/trino_progress/display/ tests/test_display_stderr.py
git commit -m "feat: add Display protocol and StderrDisplay"
```

---

### Task 4: TqdmDisplay

**Files:**
- Create: `src/trino_progress/display/tqdm.py`
- Create: `tests/test_display_tqdm.py`

**Step 1: Write the failing test**

`tests/test_display_tqdm.py`:
```python
import pytest

from trino_progress.display.tqdm import TqdmDisplay
from trino_progress.stats import parse_stats


RUNNING_STATS = {
    "state": "RUNNING",
    "queued": False,
    "scheduled": True,
    "nodes": 4,
    "totalSplits": 100,
    "queuedSplits": 10,
    "runningSplits": 30,
    "completedSplits": 60,
    "cpuTimeMillis": 5000,
    "wallTimeMillis": 8000,
    "queuedTimeMillis": 100,
    "elapsedTimeMillis": 3000,
    "processedRows": 5000000,
    "processedBytes": 100000000,
    "physicalInputBytes": 100000000,
    "peakMemoryBytes": 4000000,
    "spilledBytes": 0,
}


def test_tqdm_display_updates_progress():
    display = TqdmDisplay()
    stats = parse_stats(RUNNING_STATS)
    display.on_stats(stats)
    assert display._pbar is not None
    assert display._pbar.total == 100
    assert display._pbar.n == 60
    display.close()


def test_tqdm_display_handles_total_change():
    display = TqdmDisplay()
    stats1 = parse_stats(RUNNING_STATS)
    display.on_stats(stats1)
    # Trino can revise total splits upward as it discovers more work
    revised = {**RUNNING_STATS, "totalSplits": 200}
    stats2 = parse_stats(revised)
    display.on_stats(stats2)
    assert display._pbar.total == 200
    display.close()


def test_tqdm_display_close_completes_bar():
    display = TqdmDisplay()
    stats = parse_stats(RUNNING_STATS)
    display.on_stats(stats)
    display.close()
    assert display._pbar.disable  # tqdm sets disable on close


def test_tqdm_not_installed():
    """Verify helpful error when tqdm is missing."""
    import unittest.mock
    import sys

    with unittest.mock.patch.dict(sys.modules, {"tqdm": None, "tqdm.auto": None}):
        # Force reimport
        import importlib
        from trino_progress.display import tqdm as tqdm_mod
        with pytest.raises(ImportError, match="tqdm"):
            importlib.reload(tqdm_mod)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_display_tqdm.py -v`
Expected: ImportError.

**Step 3: Implement TqdmDisplay**

`src/trino_progress/display/tqdm.py`:
```python
from __future__ import annotations

try:
    from tqdm.auto import tqdm
except ImportError:
    raise ImportError(
        "tqdm is required for TqdmDisplay. "
        "Install it with: pip install trino-progress[tqdm]"
    )

from trino_progress.stats import QueryStats


class TqdmDisplay:
    def __init__(self, **tqdm_kwargs) -> None:
        self._tqdm_kwargs = tqdm_kwargs
        self._pbar: tqdm | None = None

    def on_stats(self, stats: QueryStats) -> None:
        if self._pbar is None:
            self._pbar = tqdm(
                total=stats.total_splits,
                unit="splits",
                desc=stats.state,
                **self._tqdm_kwargs,
            )

        if self._pbar.total != stats.total_splits:
            self._pbar.total = stats.total_splits
            self._pbar.refresh()

        self._pbar.n = stats.completed_splits
        self._pbar.set_description(stats.state)
        self._pbar.set_postfix(
            rows=f"{stats.processed_rows:,}",
            cpu=f"{stats.cpu_time_millis / 1000:.1f}s",
            mem=f"{stats.peak_memory_bytes / 1024 / 1024:.0f}MB",
            refresh=False,
        )
        self._pbar.refresh()

    def close(self) -> None:
        if self._pbar is not None:
            self._pbar.close()
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_display_tqdm.py -v`
Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
git add src/trino_progress/display/tqdm.py tests/test_display_tqdm.py
git commit -m "feat: add TqdmDisplay with optional tqdm dependency"
```

---

### Task 5: QueryPoller

**Files:**
- Create: `src/trino_progress/poller.py`
- Create: `tests/test_poller.py`

**Step 1: Write the failing test**

`tests/test_poller.py`:
```python
import json
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from unittest.mock import MagicMock

from trino_progress.poller import QueryPoller
from trino_progress.stats import QueryStats


FINISHED_RESPONSE = {
    "stats": {
        "state": "FINISHED",
        "queued": False,
        "scheduled": True,
        "nodes": 4,
        "totalSplits": 100,
        "queuedSplits": 0,
        "runningSplits": 0,
        "completedSplits": 100,
        "cpuTimeMillis": 5000,
        "wallTimeMillis": 8000,
        "queuedTimeMillis": 100,
        "elapsedTimeMillis": 3000,
        "processedRows": 5000000,
        "processedBytes": 100000000,
        "physicalInputBytes": 100000000,
        "peakMemoryBytes": 4000000,
        "spilledBytes": 0,
    }
}

RUNNING_RESPONSE = {
    "stats": {
        **FINISHED_RESPONSE["stats"],
        "state": "RUNNING",
        "completedSplits": 50,
        "runningSplits": 30,
        "queuedSplits": 20,
    }
}


class FakeTrinoHandler(BaseHTTPRequestHandler):
    responses = []
    call_count = 0

    def do_GET(self):
        idx = min(self.__class__.call_count, len(self.__class__.responses) - 1)
        self.__class__.call_count += 1
        body = json.dumps(self.__class__.responses[idx]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass  # suppress logs


def _make_server(responses):
    handler = type("Handler", (FakeTrinoHandler,), {"responses": responses, "call_count": 0})
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_poller_delivers_stats():
    server = _make_server([RUNNING_RESPONSE, FINISHED_RESPONSE])
    port = server.server_address[1]

    received = []
    callback = lambda stats: received.append(stats)

    poller = QueryPoller(
        host="127.0.0.1",
        port=port,
        http_scheme="http",
        query_id="test_query_1",
        interval=0.1,
    )
    poller.add_callback(callback)
    poller.start()
    poller.wait(timeout=5)
    server.shutdown()

    assert len(received) >= 2
    assert all(isinstance(s, QueryStats) for s in received)
    assert received[-1].state == "FINISHED"


def test_poller_stops_on_terminal_state():
    server = _make_server([FINISHED_RESPONSE])
    port = server.server_address[1]

    poller = QueryPoller(
        host="127.0.0.1",
        port=port,
        http_scheme="http",
        query_id="test_query_2",
        interval=0.1,
    )
    poller.start()
    poller.wait(timeout=5)
    server.shutdown()

    assert not poller.is_alive()


def test_poller_survives_transient_errors():
    """Poller retries on connection errors without crashing."""
    server = _make_server([RUNNING_RESPONSE, FINISHED_RESPONSE])
    port = server.server_address[1]
    server.shutdown()  # kill server immediately to cause errors

    received = []
    poller = QueryPoller(
        host="127.0.0.1",
        port=port,
        http_scheme="http",
        query_id="test_query_3",
        interval=0.1,
        max_failures=2,
    )
    poller.add_callback(lambda s: received.append(s))
    poller.start()
    poller.wait(timeout=3)

    # Should have stopped after max_failures consecutive errors
    assert not poller.is_alive()


def test_poller_from_connection():
    """Poller can extract connection details from a trino Connection."""
    server = _make_server([FINISHED_RESPONSE])
    port = server.server_address[1]

    conn = MagicMock()
    conn.host = "127.0.0.1"
    conn.port = port
    conn.http_scheme = "http"
    conn.auth = None

    poller = QueryPoller.from_connection(conn, query_id="test_query_4", interval=0.1)
    poller.start()
    poller.wait(timeout=5)
    server.shutdown()

    assert not poller.is_alive()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_poller.py -v`
Expected: ImportError.

**Step 3: Implement QueryPoller**

`src/trino_progress/poller.py`:
```python
from __future__ import annotations

import logging
import sys
import threading
import time
from typing import Callable
from urllib.request import Request, urlopen
import json

from trino_progress.stats import QueryStats, parse_stats

logger = logging.getLogger(__name__)


class QueryPoller:
    def __init__(
        self,
        host: str,
        port: int,
        http_scheme: str = "http",
        query_id: str = "",
        interval: float = 1.0,
        max_failures: int = 5,
        auth: object | None = None,
    ) -> None:
        self._host = host
        self._port = port
        self._http_scheme = http_scheme
        self._query_id = query_id
        self._interval = interval
        self._max_failures = max_failures
        self._auth = auth
        self._callbacks: list[Callable[[QueryStats], None]] = []
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._done_event = threading.Event()
        self._session = None
        self._last_stats: QueryStats | None = None

    @classmethod
    def from_connection(
        cls,
        connection,
        query_id: str,
        interval: float = 1.0,
        max_failures: int = 5,
    ) -> QueryPoller:
        return cls(
            host=connection.host,
            port=connection.port,
            http_scheme=connection.http_scheme,
            query_id=query_id,
            interval=interval,
            max_failures=max_failures,
            auth=getattr(connection, "auth", None),
        )

    def add_callback(self, callback: Callable[[QueryStats], None]) -> None:
        self._callbacks.append(callback)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def wait(self, timeout: float | None = None) -> None:
        self._done_event.wait(timeout=timeout)

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def last_stats(self) -> QueryStats | None:
        return self._last_stats

    def _build_url(self) -> str:
        return f"{self._http_scheme}://{self._host}:{self._port}/v1/query/{self._query_id}"

    def _fetch_stats(self) -> QueryStats:
        url = self._build_url()
        request = Request(url, headers={"Accept": "application/json"})
        if self._auth is not None and self._session is None:
            import requests
            self._session = requests.Session()
            self._auth.set_http_session(self._session)

        if self._session is not None:
            response = self._session.get(url)
            response.raise_for_status()
            data = response.json()
        else:
            with urlopen(request, timeout=10) as response:
                data = json.loads(response.read())

        return parse_stats(data["stats"])

    def _poll_loop(self) -> None:
        consecutive_failures = 0

        try:
            while not self._stop_event.is_set():
                try:
                    stats = self._fetch_stats()
                    consecutive_failures = 0
                    self._last_stats = stats

                    for callback in self._callbacks:
                        try:
                            callback(stats)
                        except Exception:
                            logger.exception("Display callback error")

                    if stats.is_terminal:
                        return

                except Exception:
                    consecutive_failures += 1
                    logger.warning(
                        "Failed to poll Trino stats (attempt %d/%d)",
                        consecutive_failures,
                        self._max_failures,
                    )
                    if consecutive_failures >= self._max_failures:
                        logger.error("Max poll failures reached, stopping poller")
                        return

                self._stop_event.wait(timeout=self._interval)
        finally:
            self._done_event.set()
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_poller.py -v`
Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
git add src/trino_progress/poller.py tests/test_poller.py
git commit -m "feat: add QueryPoller with background thread and observer callbacks"
```

---

### Task 6: WebDisplay

**Files:**
- Create: `src/trino_progress/display/web.py`
- Create: `tests/test_display_web.py`

**Step 1: Write the failing test**

`tests/test_display_web.py`:
```python
import json
import time
import urllib.request

from trino_progress.display.web import WebDisplay
from trino_progress.stats import parse_stats


RUNNING_STATS = {
    "state": "RUNNING",
    "queued": False,
    "scheduled": True,
    "nodes": 4,
    "totalSplits": 100,
    "queuedSplits": 10,
    "runningSplits": 30,
    "completedSplits": 60,
    "cpuTimeMillis": 5000,
    "wallTimeMillis": 8000,
    "queuedTimeMillis": 100,
    "elapsedTimeMillis": 3000,
    "processedRows": 5000000,
    "processedBytes": 100000000,
    "physicalInputBytes": 100000000,
    "peakMemoryBytes": 4000000,
    "spilledBytes": 0,
}


def test_web_display_serves_stats_json():
    display = WebDisplay(port=0)
    stats = parse_stats(RUNNING_STATS)
    display.on_stats(stats)

    url = f"http://localhost:{display.port}/stats"
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.loads(resp.read())

    assert data["state"] == "RUNNING"
    assert data["completed_splits"] == 60
    display.close()


def test_web_display_serves_history():
    display = WebDisplay(port=0)
    stats1 = parse_stats(RUNNING_STATS)
    display.on_stats(stats1)
    stats2 = parse_stats({**RUNNING_STATS, "completedSplits": 80})
    display.on_stats(stats2)

    url = f"http://localhost:{display.port}/stats/history"
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.loads(resp.read())

    assert len(data) == 2
    assert data[0]["completed_splits"] == 60
    assert data[1]["completed_splits"] == 80
    display.close()


def test_web_display_serves_html():
    display = WebDisplay(port=0)
    stats = parse_stats(RUNNING_STATS)
    display.on_stats(stats)

    url = f"http://localhost:{display.port}/"
    with urllib.request.urlopen(url, timeout=5) as resp:
        html = resp.read().decode()

    assert "<html" in html.lower()
    assert "trino" in html.lower()
    display.close()


def test_web_display_close_stops_server():
    display = WebDisplay(port=0)
    port = display.port
    display.close()

    try:
        urllib.request.urlopen(f"http://localhost:{port}/stats", timeout=1)
        assert False, "Server should be stopped"
    except Exception:
        pass  # Expected: connection refused
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_display_web.py -v`
Expected: ImportError.

**Step 3: Implement WebDisplay**

`src/trino_progress/display/web.py`:
```python
from __future__ import annotations

import dataclasses
import json
import sys
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import TextIO

from trino_progress.stats import QueryStats


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Trino Query Progress</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 900px; margin: 2em auto; padding: 0 1em; background: #fafafa; color: #222; }
  h1 { font-size: 1.4em; }
  .state { font-size: 1.2em; font-weight: bold; padding: 0.3em 0.6em; border-radius: 4px; display: inline-block; }
  .state-RUNNING { background: #dbeafe; color: #1e40af; }
  .state-FINISHED { background: #dcfce7; color: #166534; }
  .state-FAILED { background: #fee2e2; color: #991b1b; }
  .state-QUEUED, .state-PLANNING, .state-STARTING { background: #fef3c7; color: #92400e; }
  .progress-bar { width: 100%%; height: 24px; background: #e5e7eb; border-radius: 4px; overflow: hidden; margin: 1em 0; }
  .progress-fill { height: 100%%; background: #3b82f6; transition: width 0.3s; }
  table { border-collapse: collapse; width: 100%%; margin: 1em 0; }
  th, td { text-align: left; padding: 0.4em 0.8em; border-bottom: 1px solid #e5e7eb; }
  th { background: #f3f4f6; font-weight: 600; }
  .stages { margin-top: 1.5em; }
  .stage { padding: 0.3em 0; border-left: 3px solid #3b82f6; padding-left: 0.8em; margin: 0.5em 0; }
</style>
</head>
<body>
<h1>Trino Query Progress</h1>
<div id="content"><p>Waiting for stats...</p></div>
<script>
function fmt(bytes) {
  const units = ['B','KB','MB','GB','TB'];
  let i = 0;
  let n = bytes;
  while (Math.abs(n) >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return n.toFixed(1) + ' ' + units[i];
}
function fmtTime(ms) {
  const s = ms / 1000;
  if (s < 60) return s.toFixed(1) + 's';
  const m = s / 60;
  if (m < 60) return m.toFixed(1) + 'm';
  return (m / 60).toFixed(1) + 'h';
}
function renderStage(stage) {
  let html = '<div class="stage">';
  html += '<strong>Stage ' + stage.stage_id + '</strong> — ' + stage.state;
  html += ' | splits ' + stage.completed_splits + '/' + stage.total_splits;
  html += ' | ' + stage.processed_rows.toLocaleString() + ' rows';
  if (stage.sub_stages && stage.sub_stages.length > 0) {
    stage.sub_stages.forEach(function(s) { html += renderStage(s); });
  }
  html += '</div>';
  return html;
}
function update() {
  fetch('/stats').then(r => r.json()).then(s => {
    const pct = s.total_splits > 0 ? (s.completed_splits / s.total_splits * 100) : 0;
    let html = '<span class="state state-' + s.state + '">' + s.state + '</span>';
    html += '<div class="progress-bar"><div class="progress-fill" style="width:' + pct.toFixed(1) + '%%"></div></div>';
    html += '<table><tr><th>Metric</th><th>Value</th></tr>';
    html += '<tr><td>Splits</td><td>' + s.completed_splits + ' / ' + s.total_splits + ' (queued: ' + s.queued_splits + ', running: ' + s.running_splits + ')</td></tr>';
    html += '<tr><td>Rows</td><td>' + s.processed_rows.toLocaleString() + '</td></tr>';
    html += '<tr><td>Data</td><td>' + fmt(s.processed_bytes) + '</td></tr>';
    html += '<tr><td>Elapsed</td><td>' + fmtTime(s.elapsed_time_millis) + '</td></tr>';
    html += '<tr><td>CPU</td><td>' + fmtTime(s.cpu_time_millis) + '</td></tr>';
    html += '<tr><td>Peak Memory</td><td>' + fmt(s.peak_memory_bytes) + '</td></tr>';
    html += '<tr><td>Spilled</td><td>' + fmt(s.spilled_bytes) + '</td></tr>';
    html += '<tr><td>Nodes</td><td>' + s.nodes + '</td></tr>';
    html += '</table>';
    if (s.root_stage) {
      html += '<div class="stages"><h3>Stages</h3>' + renderStage(s.root_stage) + '</div>';
    }
    document.getElementById('content').innerHTML = html;
    if (s.state !== 'FINISHED' && s.state !== 'FAILED') {
      setTimeout(update, 1000);
    }
  }).catch(() => setTimeout(update, 2000));
}
update();
</script>
</body>
</html>
"""


def _stats_to_dict(stats: QueryStats) -> dict:
    """Convert QueryStats to a JSON-serializable dict."""
    return dataclasses.asdict(stats)


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/stats":
            self._json_response(
                _stats_to_dict(self.server.latest_stats) if self.server.latest_stats else {}
            )
        elif self.path == "/stats/history":
            self._json_response(
                [_stats_to_dict(s) for s in self.server.stats_history]
            )
        elif self.path == "/":
            self._html_response(_HTML_TEMPLATE)
        else:
            self.send_error(404)

    def _json_response(self, data):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html_response(self, html: str):
        body = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


class WebDisplay:
    def __init__(self, port: int = 0, file: TextIO | None = None) -> None:
        self._file = file or sys.stderr
        self._server = HTTPServer(("127.0.0.1", port), _Handler)
        self._server.latest_stats = None
        self._server.stats_history = []
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        actual_port = self._server.server_address[1]
        self._port = actual_port
        self._file.write(f"Trino progress dashboard: http://localhost:{actual_port}/\n")
        self._file.flush()

    @property
    def port(self) -> int:
        return self._port

    def on_stats(self, stats: QueryStats) -> None:
        self._server.latest_stats = stats
        self._server.stats_history.append(stats)

    def close(self) -> None:
        self._server.shutdown()
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_display_web.py -v`
Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
git add src/trino_progress/display/web.py tests/test_display_web.py
git commit -m "feat: add WebDisplay with JSON API and HTML dashboard"
```

---

### Task 7: TrinoProgress (Context Manager + Standalone)

**Files:**
- Create: `src/trino_progress/progress.py`
- Create: `tests/test_progress.py`

**Step 1: Write the failing test**

`tests/test_progress.py`:
```python
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from unittest.mock import MagicMock, PropertyMock, patch

from trino_progress.progress import TrinoProgress
from trino_progress.stats import QueryStats


RUNNING_STATS_RESPONSE = {
    "stats": {
        "state": "RUNNING",
        "queued": False,
        "scheduled": True,
        "nodes": 4,
        "totalSplits": 100,
        "queuedSplits": 10,
        "runningSplits": 30,
        "completedSplits": 60,
        "cpuTimeMillis": 5000,
        "wallTimeMillis": 8000,
        "queuedTimeMillis": 100,
        "elapsedTimeMillis": 3000,
        "processedRows": 5000000,
        "processedBytes": 100000000,
        "physicalInputBytes": 100000000,
        "peakMemoryBytes": 4000000,
        "spilledBytes": 0,
    }
}

FINISHED_STATS_RESPONSE = {
    "stats": {
        **RUNNING_STATS_RESPONSE["stats"],
        "state": "FINISHED",
        "completedSplits": 100,
        "runningSplits": 0,
        "queuedSplits": 0,
    }
}


class FakeTrinoHandler(BaseHTTPRequestHandler):
    responses = []
    call_count = 0
    lock = threading.Lock()

    def do_GET(self):
        with self.__class__.lock:
            idx = min(self.__class__.call_count, len(self.__class__.responses) - 1)
            self.__class__.call_count += 1
        body = json.dumps(self.__class__.responses[idx]).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass


def _make_server(responses):
    handler = type(
        "Handler",
        (FakeTrinoHandler,),
        {"responses": responses, "call_count": 0, "lock": threading.Lock()},
    )
    server = HTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _make_mock_cursor(server_port, query_id="test_query"):
    cursor = MagicMock()
    cursor.query_id = query_id
    cursor.stats = {"queryId": query_id}
    # Mock the connection attributes needed by the poller
    cursor.connection = MagicMock()
    cursor.connection.host = "127.0.0.1"
    cursor.connection.port = server_port
    cursor.connection.http_scheme = "http"
    cursor.connection.auth = None
    return cursor


def test_context_manager_basic():
    server = _make_server([RUNNING_STATS_RESPONSE, FINISHED_STATS_RESPONSE])
    port = server.server_address[1]
    cursor = _make_mock_cursor(port)

    with TrinoProgress(cursor, display="stderr", interval=0.1) as tp:
        tp.execute("SELECT 1")
        tp.fetchall()

    server.shutdown()
    cursor.execute.assert_called_once_with("SELECT 1")
    cursor.fetchall.assert_called_once()


def test_standalone_mode():
    server = _make_server([RUNNING_STATS_RESPONSE, FINISHED_STATS_RESPONSE])
    port = server.server_address[1]

    conn = MagicMock()
    conn.host = "127.0.0.1"
    conn.port = port
    conn.http_scheme = "http"
    conn.auth = None

    tp = TrinoProgress(conn, query_id="test_standalone", display="stderr", interval=0.1)
    tp.start()
    tp.wait(timeout=5)
    server.shutdown()


def test_display_auto_fallback():
    """display='auto' falls back to stderr when tqdm is not available."""
    server = _make_server([FINISHED_STATS_RESPONSE])
    port = server.server_address[1]

    conn = MagicMock()
    conn.host = "127.0.0.1"
    conn.port = port
    conn.http_scheme = "http"
    conn.auth = None

    tp = TrinoProgress(conn, query_id="test_auto", display="auto", interval=0.1)
    tp.start()
    tp.wait(timeout=5)
    server.shutdown()


def test_multiple_displays():
    server = _make_server([FINISHED_STATS_RESPONSE])
    port = server.server_address[1]

    conn = MagicMock()
    conn.host = "127.0.0.1"
    conn.port = port
    conn.http_scheme = "http"
    conn.auth = None

    mock_display = MagicMock()
    tp = TrinoProgress(conn, query_id="test_multi", display=[mock_display], interval=0.1)
    tp.start()
    tp.wait(timeout=5)
    server.shutdown()

    assert mock_display.on_stats.called
    assert mock_display.close.called


def test_cursor_proxy_methods():
    server = _make_server([FINISHED_STATS_RESPONSE])
    port = server.server_address[1]
    cursor = _make_mock_cursor(port)
    cursor.fetchone.return_value = (1,)
    cursor.fetchmany.return_value = [(1,), (2,)]
    cursor.description = [("col1", "varchar")]

    with TrinoProgress(cursor, display="stderr", interval=0.1) as tp:
        tp.execute("SELECT 1")
        assert tp.fetchone() == (1,)
        assert tp.fetchmany(2) == [(1,), (2,)]
        assert tp.description == [("col1", "varchar")]

    server.shutdown()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_progress.py -v`
Expected: ImportError.

**Step 3: Implement TrinoProgress**

`src/trino_progress/progress.py`:
```python
from __future__ import annotations

import logging
import sys
from typing import Any, Sequence

from trino_progress.display import Display
from trino_progress.display.stderr import StderrDisplay
from trino_progress.poller import QueryPoller
from trino_progress.stats import QueryStats

logger = logging.getLogger(__name__)


def _resolve_displays(display) -> list[Display]:
    """Resolve display argument into a list of Display instances."""
    if isinstance(display, list):
        result = []
        for d in display:
            if isinstance(d, str):
                result.extend(_resolve_displays(d))
            else:
                result.append(d)
        return result

    if isinstance(display, str):
        if display == "stderr":
            return [StderrDisplay()]
        elif display == "tqdm":
            from trino_progress.display.tqdm import TqdmDisplay
            return [TqdmDisplay()]
        elif display == "web":
            from trino_progress.display.web import WebDisplay
            return [WebDisplay()]
        elif display == "auto":
            try:
                from trino_progress.display.tqdm import TqdmDisplay
                return [TqdmDisplay()]
            except ImportError:
                return [StderrDisplay()]
        else:
            raise ValueError(f"Unknown display type: {display!r}")

    # Assume it's a Display instance
    return [display]


def _is_cursor(obj) -> bool:
    """Check if obj looks like a DB-API cursor (has execute method)."""
    return hasattr(obj, "execute") and hasattr(obj, "fetchall")


class TrinoProgress:
    def __init__(
        self,
        cursor_or_connection,
        query_id: str | None = None,
        display: str | list | Display = "auto",
        interval: float = 1.0,
        max_failures: int = 5,
        web_port: int = 0,
    ) -> None:
        self._displays = _resolve_displays(display)
        self._interval = interval
        self._max_failures = max_failures
        self._poller: QueryPoller | None = None

        if _is_cursor(cursor_or_connection):
            self._cursor = cursor_or_connection
            self._connection = cursor_or_connection.connection
            self._query_id = query_id
            self._mode = "cursor"
        else:
            self._cursor = None
            self._connection = cursor_or_connection
            self._query_id = query_id
            self._mode = "standalone"

    # -- Context manager (cursor mode) --

    def __enter__(self) -> TrinoProgress:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._poller is not None:
            self._poller.wait(timeout=30)
            self._poller.stop()
        self._close_displays()
        return None

    # -- Standalone mode --

    def start(self) -> None:
        if self._query_id is None:
            raise ValueError("query_id is required for standalone mode")
        self._start_poller()

    def stop(self) -> None:
        if self._poller is not None:
            self._poller.stop()
        self._close_displays()

    def wait(self, timeout: float | None = None) -> None:
        if self._poller is not None:
            self._poller.wait(timeout=timeout)
        self._close_displays()

    # -- Cursor proxy methods --

    def execute(self, operation: str, parameters: Sequence | None = None) -> None:
        if self._cursor is None:
            raise RuntimeError("execute() requires cursor mode")
        if parameters is not None:
            self._cursor.execute(operation, parameters)
        else:
            self._cursor.execute(operation)
        self._query_id = self._cursor.query_id
        self._start_poller()

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> list:
        return self._cursor.fetchall()

    def fetchmany(self, size: int | None = None) -> list:
        if size is not None:
            return self._cursor.fetchmany(size)
        return self._cursor.fetchmany()

    def __iter__(self):
        return iter(self._cursor)

    @property
    def description(self):
        return self._cursor.description

    @property
    def query_id(self) -> str | None:
        return self._query_id

    @property
    def last_stats(self) -> QueryStats | None:
        if self._poller is not None:
            return self._poller.last_stats
        return None

    # -- Internal --

    def _start_poller(self) -> None:
        self._poller = QueryPoller.from_connection(
            self._connection,
            query_id=self._query_id,
            interval=self._interval,
            max_failures=self._max_failures,
        )
        for display in self._displays:
            self._poller.add_callback(display.on_stats)
        self._poller.start()

    def _close_displays(self) -> None:
        for display in self._displays:
            try:
                display.close()
            except Exception:
                logger.exception("Error closing display")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_progress.py -v`
Expected: All 5 tests PASS.

**Step 5: Commit**

```bash
git add src/trino_progress/progress.py tests/test_progress.py
git commit -m "feat: add TrinoProgress with context manager and standalone modes"
```

---

### Task 8: Update __init__.py Exports and Integration Test

**Files:**
- Modify: `src/trino_progress/__init__.py`
- Create: `tests/test_integration.py`

**Step 1: Update __init__.py with full public API**

`src/trino_progress/__init__.py`:
```python
from trino_progress.stats import QueryStats, StageStats
from trino_progress.progress import TrinoProgress
from trino_progress.display import Display
from trino_progress.display.stderr import StderrDisplay
from trino_progress.display.web import WebDisplay

__all__ = [
    "TrinoProgress",
    "QueryStats",
    "StageStats",
    "Display",
    "StderrDisplay",
    "WebDisplay",
]

__version__ = "0.1.0"
```

**Step 2: Write integration test**

`tests/test_integration.py`:
```python
"""Integration test: full flow with fake Trino server."""

import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from unittest.mock import MagicMock

from trino_progress import TrinoProgress, QueryStats


RESPONSES = [
    {
        "stats": {
            "state": "QUEUED",
            "queued": True, "scheduled": False, "nodes": 0,
            "totalSplits": 0, "queuedSplits": 0, "runningSplits": 0, "completedSplits": 0,
            "cpuTimeMillis": 0, "wallTimeMillis": 0, "queuedTimeMillis": 0, "elapsedTimeMillis": 0,
            "processedRows": 0, "processedBytes": 0, "physicalInputBytes": 0,
            "peakMemoryBytes": 0, "spilledBytes": 0,
        }
    },
    {
        "stats": {
            "state": "RUNNING",
            "queued": False, "scheduled": True, "nodes": 4,
            "totalSplits": 200, "queuedSplits": 50, "runningSplits": 50, "completedSplits": 100,
            "cpuTimeMillis": 3000, "wallTimeMillis": 5000, "queuedTimeMillis": 500, "elapsedTimeMillis": 2000,
            "processedRows": 2000000, "processedBytes": 80000000, "physicalInputBytes": 80000000,
            "peakMemoryBytes": 5000000, "spilledBytes": 0,
        }
    },
    {
        "stats": {
            "state": "FINISHED",
            "queued": False, "scheduled": True, "nodes": 4,
            "totalSplits": 200, "queuedSplits": 0, "runningSplits": 0, "completedSplits": 200,
            "cpuTimeMillis": 8000, "wallTimeMillis": 12000, "queuedTimeMillis": 500, "elapsedTimeMillis": 5000,
            "processedRows": 10000000, "processedBytes": 300000000, "physicalInputBytes": 300000000,
            "peakMemoryBytes": 8000000, "spilledBytes": 0,
        }
    },
]


def _make_server():
    handler_cls = type(
        "Handler",
        (BaseHTTPRequestHandler,),
        {
            "responses": RESPONSES,
            "call_count": 0,
            "lock": threading.Lock(),
            "do_GET": lambda self: self._respond(),
            "_respond": lambda self: (
                self.__class__.lock.__enter__(),
                setattr(self.__class__, "call_count", min(self.__class__.call_count + 1, len(self.__class__.responses))),
                self.__class__.lock.__exit__(None, None, None),
                self.send_response(200),
                self.send_header("Content-Type", "application/json"),
                self.end_headers(),
                self.wfile.write(json.dumps(self.__class__.responses[min(self.__class__.call_count - 1, len(self.__class__.responses) - 1)]).encode()),
            ),
            "log_message": lambda self, *a: None,
        },
    )
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def test_full_context_manager_flow():
    server = _make_server()
    port = server.server_address[1]

    cursor = MagicMock()
    cursor.query_id = "integration_test_1"
    cursor.connection = MagicMock()
    cursor.connection.host = "127.0.0.1"
    cursor.connection.port = port
    cursor.connection.http_scheme = "http"
    cursor.connection.auth = None
    cursor.fetchall.return_value = [(1, "hello"), (2, "world")]

    with TrinoProgress(cursor, display="stderr", interval=0.1) as tp:
        tp.execute("SELECT id, name FROM test_table")
        rows = tp.fetchall()

    assert rows == [(1, "hello"), (2, "world")]
    assert tp.last_stats is not None
    assert tp.last_stats.state == "FINISHED"
    server.shutdown()


def test_full_standalone_flow():
    server = _make_server()
    port = server.server_address[1]

    conn = MagicMock()
    conn.host = "127.0.0.1"
    conn.port = port
    conn.http_scheme = "http"
    conn.auth = None

    collected = []
    mock_display = MagicMock()
    mock_display.on_stats = lambda s: collected.append(s)

    tp = TrinoProgress(conn, query_id="integration_test_2", display=[mock_display], interval=0.1)
    tp.start()
    tp.wait(timeout=10)

    assert len(collected) >= 2
    assert collected[-1].state == "FINISHED"
    assert collected[-1].processed_rows == 10000000
    server.shutdown()
```

**Step 3: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS.

**Step 4: Commit**

```bash
git add src/trino_progress/__init__.py tests/test_integration.py
git commit -m "feat: finalize public API exports and add integration tests"
```

---

### Task 9: Final Cleanup and Verification

**Files:**
- Verify: all files

**Step 1: Run full test suite with coverage**

Run: `uv run pytest tests/ -v --cov=trino_progress --cov-report=term-missing`
Expected: All tests PASS, reasonable coverage.

**Step 2: Verify package builds**

Run: `uv build`
Expected: Produces a wheel and sdist in `dist/`.

**Step 3: Verify import works**

Run: `uv run python -c "from trino_progress import TrinoProgress, QueryStats; print('OK')"`
Expected: Prints "OK".

**Step 4: Commit any remaining fixes**

If any fixes were needed, commit them.

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore: final cleanup and verification"
```
