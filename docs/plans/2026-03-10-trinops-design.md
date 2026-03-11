# trinops Design

## Overview

A Python tool for Trino query monitoring with three interfaces over a shared core: an agent-friendly CLI, an interactive TUI dashboard, and a read-only MCP server. v1 is query-focused (list, detail, progress). Cluster-wide monitoring and write operations (kill queries) are deferred to v2.

Absorbs the existing trino-progress library as a subpackage. Distributed as a single PyPI package (`trinops`) with optional extras for each interface layer.

## Install Matrix

- `pip install trinops` — core library only (polling, stats, progress wrapper, auth, config)
- `pip install trinops[cli]` — adds typer, rich
- `pip install trinops[tui]` — adds textual
- `pip install trinops[mcp]` — adds MCP server dependencies
- `pip install trinops[tqdm]` — adds tqdm for progress bars
- `pip install trinops[all]` — everything

## Package Structure

```
trinops/
├── pyproject.toml
├── src/
│   └── trinops/
│       ├── __init__.py
│       ├── auth.py            # OAuth2 flow, JWT caching, auth helpers
│       ├── config.py          # Profile config (~/.config/trinops/config.toml)
│       ├── client.py          # Trino monitoring API client
│       ├── models.py          # QueryInfo, ClusterStats
│       ├── progress/          # trino-progress absorbed
│       │   ├── __init__.py    # TrinoProgress re-exported
│       │   ├── poller.py
│       │   ├── stats.py       # QueryStats, StageStats, parse_stats
│       │   └── display/
│       │       ├── __init__.py
│       │       ├── stderr.py
│       │       ├── tqdm.py
│       │       └── web.py
│       ├── cli/               # [cli] extra
│       │   ├── __init__.py
│       │   └── commands.py    # typer commands
│       ├── tui/               # [tui] extra
│       │   ├── __init__.py
│       │   └── app.py         # Textual app
│       └── mcp/               # [mcp] extra
│           ├── __init__.py
│           └── server.py      # MCP server
└── tests/
```

## Core Client & Data Model

Two data paths:

### Query Listing/Lookup

SQL queries against `system.runtime.queries`. This is the only stable, authenticated interface for per-query information. Returns query ID, SQL text, state, user, source, timestamps, resource usage for all running and recent queries (up to `query.max-history`). trinops opens a dedicated Trino connection for monitoring queries.

### Live Progress on Active Queries

Statement protocol stats field during execution. Per-stage splits, progress percentage, timing. This is what the progress wrapper uses for queries the user launched.

### Data Models

`QueryInfo` (from system table): query ID, SQL text, state, user, source, created/started/ended timestamps, CPU time, wall time, peak memory, cumulative memory, queued time, analysis time, rows/bytes processed, error info.

`QueryStats` (from statement protocol): state, splits (completed/running/queued/total), CPU time, wall time, elapsed time, rows/bytes, peak memory, per-stage breakdown. Frozen dataclass, immutable snapshot.

When watching a query you launched, both are available. When listing/looking up other queries, `QueryInfo` only.

### Future: HTTP Query API

Trino issue #22488 tracks making `/ui/api/query/` endpoints accessible to authenticated API users (currently locked behind `@ResourceSecurity(WEB_UI)` browser session auth). When this lands, add an HTTP client path for query listing that avoids the overhead of a SQL connection.

## CLI Interface

Powered by typer. Entry point: `trinops` command with subcommands.

```
trinops queries                    # list running/recent queries (table)
trinops queries --state RUNNING    # filter by state
trinops queries --json             # JSON output for agents
trinops query <query_id>           # detail view for a specific query
trinops query <query_id> --json    # JSON detail for agents
trinops query <query_id> --watch   # poll and refresh until terminal state
trinops auth login                 # OAuth2 flow, cache JWT
trinops auth status                # show current auth state
trinops config init                # create config file interactively
trinops config show                # dump current config
```

Connection specified via `--profile <name>` (from config file), `--server <url>`, or environment variables (`TRINOPS_SERVER`, `TRINOPS_USER`, etc.). Profile takes precedence over env vars.

Default output is a Rich table (compact, colored, human-readable). `--json` emits one JSON object per line for agent consumption. `--watch` re-polls on the configured interval and reprints.

The CLI is a thin layer: parse args, build client, call core, format output. No business logic in the CLI layer.

## TUI Dashboard

Textual app launched via `trinops tui` (or `trinops top` as alias).

```
┌──────────────────────────────────────────────────────┐
│ trinops — trino.example.com:8080       ▲ 12 workers  │
├──────────────────────────────────────────────────────┤
│ Query ID          State    User    Splits   Elapsed  │
│ 20260310_143..    RUNNING  loki    488/988  6.8s     │
│ 20260310_142..    QUEUED   admin   0/0      1.2s     │
│ 20260310_141..    FINISHED bob     200/200  12.4s    │
├──────────────────────────────────────────────────────┤
│ Detail: 20260310_143...                               │
│ SELECT * FROM big_table WHERE ...                     │
│ Stage 0: RUNNING  50/100 splits  1M rows              │
│   Stage 1: FINISHED  888/888 splits  33M rows         │
│ CPU: 19.2s  Memory: 8.2MB  Rows: 34M                 │
└──────────────────────────────────────────────────────┘
```

Top panel: query list, sortable/filterable. Bottom panel: detail view for selected query. Keyboard-driven: arrow keys to navigate, `q` to quit, `f` to filter by state, `/` to search. Refresh interval configurable, default 1s.

Same connection options as CLI. Calls the same core client.

## MCP Server

Read-only MCP server launched via `trinops mcp serve`. Tools:

- `list_queries(state?: string)` — running/recent queries as JSON array
- `get_query(query_id: string)` — detail for a specific query
- `get_cluster_stats()` — aggregate cluster info (worker count, queue depth from `system.runtime.queries` aggregation)

No write operations in v1. Kill support deferred to v2, opt-in via configuration.

Runs as stdio MCP server by default. Optional `--transport sse` for HTTP-based clients.

Reads connection config from the same config file/env vars as CLI.

## Auth & Config

### Config File

Located at `~/.config/trinops/config.toml`:

```toml
[default]
server = "trino.example.com:8080"
scheme = "https"
user = "loki"
auth = "oauth2"
catalog = "hive"

[profiles.staging]
server = "trino-staging.example.com:8080"
auth = "basic"
user = "loki"
password_cmd = "vault read -field=password secret/trino/staging"
```

Profiles are named connection configs. `default` is used when no `--profile` is specified. `password_cmd` pulls secrets from external tools without storing them in the file.

### Auth Methods

- `basic` — username/password (from config, `password_cmd`, or prompt)
- `jwt` — static JWT token (from config or env var)
- `oauth2` — `trinops auth login` runs browser OAuth2 flow, caches JWT to `~/.config/trinops/tokens/`. Automatic refresh on expiry.
- `kerberos` — delegates to trino-python-client's KerberosAuthentication
- `none` — no auth (local dev clusters)

All auth flows produce a `trino.auth.Authentication` instance passed to the trino connection. No custom auth implementation; wraps trino-python-client's existing classes.

## Progress Wrapper (absorbed trino-progress)

The existing trino-progress code moves into `trinops/progress/` as a subpackage:

```python
from trinops.progress import TrinoProgress

with TrinoProgress(cursor, display="tqdm") as tp:
    tp.execute("SELECT * FROM big_table")
    rows = tp.fetchall()
```

### Poller Fix

The current poller builds URLs to `/v1/query/{queryId}`, which does not exist as a public endpoint. The poller needs to be fixed to use the cursor's own `stats` property during execution (for queries you started), or `system.runtime.queries` for watching queries started elsewhere.

### Display Backends

- `StderrDisplay` — zero-dependency fallback, `\r`-based line updates
- `TqdmDisplay` — optional `[tqdm]` extra, progress bar on splits
- `WebDisplay` — stdlib HTTP server with JSON API + HTML dashboard
- `"auto"` — tqdm if installed, stderr otherwise

## Dependencies

### Core (no extras)
- `trino>=0.320` (peer dependency)
- `tomli>=1.0` (config parsing, stdlib in 3.11+)

### [cli]
- `typer>=0.9`
- `rich>=13.0`

### [tui]
- `textual>=0.40`

### [mcp]
- MCP server SDK (TBD based on ecosystem at implementation time)

### [tqdm]
- `tqdm>=4.60`

### [all]
- All of the above

## v2 Considerations (Out of Scope)

- Cluster-wide monitoring (worker health, resource utilization)
- Kill queries via CLI/MCP (opt-in config)
- HTTP query API when Trino #22488 lands
- Query history persistence (local SQLite cache)
- Notifications/alerts on query state changes
- Multi-cluster support
