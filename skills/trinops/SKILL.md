---
name: trinops
description: Use when working with Trino queries, cluster monitoring, or query performance analysis. Activates when the user mentions Trino queries, running queries, query performance, or cluster activity.
---

# trinops — Trino Query Monitoring CLI

You have access to `trinops`, a CLI for monitoring Trino queries. Use `uv run trinops` to invoke it. All JSON output pipes cleanly to `jq`.

## Listing Queries

```bash
# Your recent queries (default)
uv run trinops queries --json

# All users
uv run trinops queries --json --query-user all

# Filter by state
uv run trinops queries --json --state RUNNING

# Paginate
uv run trinops queries --json -n 10 -p 2

# Select specific fields (reduces output size)
uv run trinops queries --select "query_id,state,user,elapsed_time_millis"
```

Using `--select` implies JSON output. Fields use the QueryInfo model names:
`query_id`, `state`, `query`, `user`, `source`, `created`, `cpu_time_millis`, `elapsed_time_millis`, `peak_memory_bytes`, `processed_rows`, `processed_bytes`, `error_code`, `error_message`

## Single Query Detail

```bash
# Human-readable detail (timing, data, memory, tables, SQL)
uv run trinops query <query_id>

# Full raw JSON from Trino REST API (all fields, stages, operators)
uv run trinops query <query_id> --json

# Select specific fields from raw API response (dot notation for nesting)
uv run trinops query <query_id> --select "queryId,state,queryStats.elapsedTime,queryStats.totalCpuTime,queryStats.peakUserMemoryReservation"
```

### Useful --select paths for query detail

Timing: `queryStats.elapsedTime`, `queryStats.queuedTime`, `queryStats.planningTime`, `queryStats.executionTime`, `queryStats.totalCpuTime`

Data: `queryStats.physicalInputDataSize`, `queryStats.physicalInputPositions`, `queryStats.processedInputDataSize`, `queryStats.outputDataSize`, `queryStats.physicalWrittenDataSize`, `queryStats.spilledDataSize`

Memory: `queryStats.peakUserMemoryReservation`, `queryStats.peakTotalMemoryReservation`

Tasks: `queryStats.totalTasks`, `queryStats.completedTasks`, `queryStats.totalDrivers`, `queryStats.completedDrivers`

Metadata: `queryId`, `state`, `queryType`, `query`, `resourceGroupId`, `session.user`, `session.source`, `session.catalog`

Tables: `inputs` (array of tables with columns, record counts), `referencedTables`

Errors: `failureInfo.type`, `failureInfo.message`, `warnings`

## Context Management

When investigating queries, start narrow and expand as needed:

1. **Find queries**: `--select "query_id,state,user,elapsed_time_millis"` to list candidates
2. **Quick check**: `--select "queryId,state,queryStats.elapsedTime,queryStats.totalCpuTime"` for a specific query
3. **Full detail**: `--json` only when you need the complete picture (stages, operators, etc.)

The `--select` flag is the primary tool for keeping context small. Prefer it over `--json | jq` when possible.

## Configuration

trinops reads `~/.config/trinops/config.toml`:

```toml
[default]
server = "trino.example.com:443"
scheme = "https"
user = "myuser"
auth = "oauth2"
query_limit = 50
```

Connection can also come from `--server host:port` flags or `TRINOPS_SERVER` / `TRINOPS_USER` / `TRINOPS_AUTH` environment variables.

Auth methods: `none`, `basic`, `jwt`, `oauth2`, `kerberos`
