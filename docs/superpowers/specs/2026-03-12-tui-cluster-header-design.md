# TUI Cluster Status Header

## Summary

Add a single-line cluster status header to the TUI, displayed between the Textual Header and the DataTable. The line shows cluster identity, query state breakdown, and aggregate resource usage in a dense, pipe-separated format similar to `top`'s summary line.

Example output:

```
trino 449 │ 8 workers │ 47 queries: 12 run 3 queued 32 done │ 124.5GB mem │ 45.2m cpu │ 1.2B rows │ 340.2GB data │ up 3d2h
```

When endpoints are unavailable, segments degrade gracefully:

```
47 queries: 12 run 3 queued 32 done │ 124.5GB mem │ 45.2m cpu │ 1.2B rows │ 340.2GB data
```

## Data Sources

Three endpoint tiers, each with independent availability tracking:

| Endpoint | Data provided | Fallback |
|----------|--------------|----------|
| `/v1/query` (already fetched) | Query counts by state, aggregate CPU/mem/rows/bytes from query list | None (always available) |
| `/v1/info` | Trino version, uptime, starting status | Omit version/uptime segments |
| `/v1/cluster` | Active worker count, more accurate cluster-wide resource stats | Omit worker count; use query-list aggregates for resources |

## Graceful Endpoint Fallback

Each optional endpoint (`/v1/info`, `/v1/cluster`) gets a tri-state availability flag per backend instance:

- `UNKNOWN` (initial) — try on first refresh
- `AVAILABLE` — succeeded at least once; keep fetching
- `UNAVAILABLE` — returned 404, 405, or 501; stop trying for this session

Transient errors (timeouts, 500, 502, 503, 504) do not mark the endpoint as unavailable; they just produce a missing value for that refresh cycle. A successful response after transient errors resets to `AVAILABLE`.

The flags live on `HttpQueryBackend`. `SqlQueryBackend` always reports `UNAVAILABLE` for both since it has no REST access.

## Architecture

### New model: `ClusterStats`

A dataclass holding the combined cluster status, with all fields optional except what comes from the query list:

```python
@dataclasses.dataclass
class ClusterStats:
    # From /v1/info (optional)
    trino_version: Optional[str] = None
    uptime: Optional[str] = None
    starting: Optional[bool] = None

    # From /v1/cluster (optional)
    active_workers: Optional[int] = None

    # Aggregated from query list (always present)
    total_queries: int = 0
    running: int = 0
    queued: int = 0
    finished: int = 0
    failed: int = 0
    total_cpu_millis: int = 0
    total_peak_memory_bytes: int = 0
    total_processed_rows: int = 0
    total_processed_bytes: int = 0
```

### Backend changes

Add two new methods to `HttpQueryBackend`:

- `get_cluster_info() -> dict | None` — fetches `/v1/info`, respects availability flag
- `get_cluster_stats() -> dict | None` — fetches `/v1/cluster`, respects availability flag

Add a method to `TrinopsClient`:

- `get_cluster_stats(queries: list[QueryInfo]) -> ClusterStats` — calls both backend methods (if HTTP backend), aggregates query-list stats, returns combined `ClusterStats`

### TUI changes

Add a new `ClusterHeader` widget (a `Static` subclass) positioned between the Textual `Header` and the `DataTable`. It renders `ClusterStats` into the dense one-line format. Styling: `height: 1`, matching the existing `StatusBar` aesthetic.

The refresh cycle in `_fetch_queries` fetches cluster stats alongside queries (both in the same worker thread). `_update_table` updates the header widget with the new stats.

## Formatting

Segments are pipe-separated with spaces. Each segment is included only if its data is available:

| Segment | Source | Example | When omitted |
|---------|--------|---------|-------------|
| Version | `/v1/info` | `trino 449` | Endpoint unavailable |
| Workers | `/v1/cluster` | `8 workers` | Endpoint unavailable |
| Query breakdown | query list | `47 queries: 12 run 3 queued 32 done` | Never (always shown) |
| Memory | query list or `/v1/cluster` | `124.5GB mem` | Never |
| CPU | query list | `45.2m cpu` | Never |
| Rows | query list | `1.2B rows` | Never |
| Data | query list | `340.2GB data` | Never |
| Uptime | `/v1/info` | `up 3d2h` | Endpoint unavailable |

Zero-value states in the query breakdown (e.g., 0 failed) are omitted to save space. Formatting uses the existing `_fmt_bytes` / `_fmt_duration` helpers or equivalent compact formatters (1.2B, 45.2m, 124.5GB).

## Testing

- Unit tests for `ClusterStats` aggregation from a list of `QueryInfo` objects
- Unit tests for the header formatting function (various combinations of available/unavailable data)
- Unit tests for endpoint fallback behavior (404 marks unavailable, 500 does not, subsequent calls skip unavailable endpoints)
- Mock `/v1/info` and `/v1/cluster` in the existing test HTTP server
