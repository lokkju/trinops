# trino-progress Design

## Overview

A standalone PyPI package providing real-time query progress monitoring for Trino. One class, `TrinoProgress`, works as either a cursor-wrapping context manager or a standalone tracker given a connection + query ID. Pluggable display backends render progress via tqdm, a local web dashboard, or a basic stderr fallback.

## Public API

Two usage patterns, one class:

```python
# Context manager — wraps a trino cursor
from trino_progress import TrinoProgress

with TrinoProgress(cursor, display="tqdm") as tp:
    tp.execute("SELECT * FROM huge_table")
    rows = tp.fetchall()

# Standalone — given a connection + query ID
tp = TrinoProgress(connection, query_id="abc123", display="web")
tp.start()
tp.wait()
```

The `display` parameter accepts `"tqdm"`, `"web"`, `"auto"`, a list of display names, or a custom `Display` instance. Default is `"auto"` (tqdm if installed, stderr fallback otherwise).

In context manager mode, `TrinoProgress` proxies standard DB-API cursor methods (`execute`, `fetchone`, `fetchall`, `fetchmany`, `__iter__`). It intercepts `execute()` to extract the query ID, starts polling, and stops when the query reaches a terminal state or the context manager exits.

Web display binds to `localhost:0` by default (OS-assigned port). Configurable via `web_port` kwarg. URL printed to stderr on startup.

## Architecture

Three internal layers using an observer pattern:

### QueryPoller

The engine. Takes a Trino connection (or host/port/auth) and a query ID. Runs a background `threading.Thread` that hits `GET /v1/query/{queryId}` on a configurable interval (default 1s). Each response is parsed into a `QueryStats` dataclass. The poller maintains a list of registered callbacks and invokes each one with the new `QueryStats` snapshot on every tick.

### Display Protocol

A simple interface: `on_stats(stats: QueryStats)` and `close()`. Three implementations ship:

- **TqdmDisplay**: Renders a tqdm progress bar keyed on completed splits / total splits, with postfix showing state, rows, CPU time. Requires the `[tqdm]` optional extra.
- **WebDisplay**: Starts an `http.server` in a daemon thread. Serves `/stats` (JSON), `/stats/history` (JSON array of all snapshots), and `/` (HTML dashboard with inline JS that polls `/stats`). No external JS dependencies.
- **StderrDisplay**: Basic fallback. Prints state + splits + rows via `\r` overwrite on each tick. No dependencies.

### TrinoProgress

The user-facing class. Detects construction mode from arguments:

- If given a cursor: wraps it, intercepts `execute()`, extracts query ID from `cursor.stats['queryId']`, creates a `QueryPoller`, attaches displays, starts polling. Context manager handles cleanup.
- If given a connection + query ID: creates a `QueryPoller` directly. Exposes `start()` / `stop()` / `wait()`.

## QueryStats Dataclass

Frozen, immutable snapshot parsed from the Trino query stats API response:

- Query state: QUEUED, PLANNING, STARTING, RUNNING, FINISHING, FINISHED, FAILED
- Splits: completed, running, queued, total
- CPU time, wall time, elapsed time
- Rows and bytes processed
- Peak memory usage
- Per-stage breakdown (stage ID, state, splits, rows)
- Error info (populated on FAILED state)

## Web Display Endpoints

- `GET /` — HTML page with inline JS/CSS. Shows query state, visual progress bar, splits table, timing, memory, rows/bytes, per-stage breakdown. Auto-refreshes by polling `/stats`.
- `GET /stats` — JSON dump of the latest `QueryStats` snapshot.
- `GET /stats/history` — JSON array of all snapshots collected, for sparklines or time-series rendering.

Server binds to `localhost` only. Shuts down when the poller stops. No websockets, no SSE.

## Error Handling

- **Query finishes before polling starts**: First poll sees terminal state. Displays get one final `on_stats`, then close.
- **Query fails**: Poller detects FAILED state, delivers final stats (including error info), closes displays. Context manager does not swallow cursor exceptions.
- **Coordinator connection lost**: Poller catches the exception, logs a warning to stderr, retries next tick. After N consecutive failures (configurable, default 5), gives up and closes displays with last known stats. Does not kill the underlying query.
- **KeyboardInterrupt**: Context manager `__exit__` stops poller and closes displays. Does not cancel the Trino query.
- **Display error**: If one display's `on_stats` raises, log the error and continue delivering to others.

## Packaging

```
trino-progress/
├── pyproject.toml
├── src/
│   └── trino_progress/
│       ├── __init__.py       # public API exports
│       ├── progress.py       # TrinoProgress class
│       ├── poller.py         # QueryPoller, background thread
│       ├── stats.py          # QueryStats dataclass, Trino JSON parsing
│       └── display/
│           ├── __init__.py   # Display protocol
│           ├── tqdm.py       # TqdmDisplay
│           ├── web.py        # WebDisplay + embedded HTML
│           └── stderr.py     # StderrDisplay fallback
├── tests/
└── LICENSE
```

- **PyPI name**: `trino-progress`
- **Import name**: `trino_progress`
- **Layout**: `src/` layout, `pyproject.toml` only
- **Python**: 3.10+
- **Dependencies (base)**: `trino` (peer dependency, minimum version)
- **Optional extras**: `[tqdm]` adds `tqdm`
- **`display="tqdm"`** raises `ImportError` with install instructions if tqdm is not present

## Future Considerations (Out of Scope)

- Language-agnostic core stats library (query ID poller as a standalone service)
- Async (`asyncio`) poller as an optional layer
- Query cancellation support
- Multiple concurrent query tracking
