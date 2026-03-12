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
| `/v1/cluster` | Active worker count | Omit worker count segment |

## Graceful Endpoint Fallback

Each optional endpoint (`/v1/info`, `/v1/cluster`) gets a tri-state availability flag per backend instance:

- `UNKNOWN` (initial) — try on first refresh
- `AVAILABLE` — succeeded at least once; keep fetching
- `UNAVAILABLE` — returned 404, 405, or 501; stop trying for this session

Transient errors (timeouts, 500, 502, 503, 504) do not mark the endpoint as unavailable; they just produce a missing value for that refresh cycle. A successful response after transient errors resets to `AVAILABLE`.

The flags live on `HttpQueryBackend`. `SqlQueryBackend` has no REST access, so `TrinopsClient` skips the optional endpoint calls entirely when using a SQL backend and produces `ClusterStats` from the query list alone (all optional fields `None`).

Error handling for the new methods lives in the methods themselves, not in `_get_json`. Each method wraps the `_get_json` call in a try/except that handles both `urllib.error.HTTPError` (`.code`) and `requests.exceptions.HTTPError` (`.response.status_code`) to account for the dual HTTP client paths.

## Architecture

### New model: `ClusterStats`

A dataclass in `models.py`. All fields from optional endpoints are `Optional`; query-list aggregates are always present.

```python
@dataclasses.dataclass
class ClusterStats:
    # From /v1/info (optional)
    trino_version: Optional[str] = None
    uptime_millis: Optional[int] = None  # parsed from Airlift duration string
    starting: Optional[bool] = None

    # From /v1/cluster (optional)
    active_workers: Optional[int] = None

    # Aggregated from query list (always present)
    total_queries: int = 0
    running: int = 0
    queued: int = 0
    finished: int = 0
    failed: int = 0
    total_cpu_millis: int = 0        # sum of QueryInfo.cpu_time_millis
    total_peak_memory_bytes: int = 0  # sum of QueryInfo.peak_memory_bytes
    total_processed_rows: int = 0     # sum of QueryInfo.processed_rows
    total_processed_bytes: int = 0    # sum of QueryInfo.processed_bytes
```

`uptime` is stored as millis (parsed via the existing `parse_duration_millis` helper) rather than as a raw string. A new `format_compact_uptime` formatter produces the `3d2h` display form.

### New helpers in `formatting.py`

- `format_compact_number(n: int) -> str` — compact row/count formatting: `1.2B`, `34.1M`, `5.6K`, or raw int if < 1000
- `format_compact_uptime(millis: int) -> str` — multi-unit compact uptime: `3d2h`, `5h12m`, `45s`

### Backend changes

Add two new methods to `HttpQueryBackend` (these are NOT added to the `QueryBackend` Protocol, since `SqlQueryBackend` cannot implement them):

- `get_info() -> dict | None` — fetches `/v1/info`, respects availability flag
- `get_cluster() -> dict | None` — fetches `/v1/cluster`, respects availability flag

The `TrinopsClient` calls these via `isinstance(self._backend, HttpQueryBackend)` checks, the same pattern used by `check_connection()`.

Add a method to `TrinopsClient`:

- `build_cluster_stats(queries: list[QueryInfo]) -> ClusterStats` — if HTTP backend, calls `get_info()` and `get_cluster()`; always aggregates query-list stats; returns combined `ClusterStats`

### Expected endpoint response shapes

`/v1/info` (already partially used in `check_connection`):
```json
{
  "nodeVersion": {"version": "449"},
  "uptime": "3.12d",
  "starting": false
}
```

`/v1/cluster` (new; fields read by trinops):
```json
{
  "activeWorkers": 8
}
```

Only the fields listed above are read. Other fields in the response are ignored, which provides forward compatibility across Trino versions.

### TUI changes

Add a `ClusterHeader` widget (a `Static` subclass) between the Textual `Header` and `DataTable` in `compose()`. CSS: `height: 1; background: $panel; color: $text; padding: 0 1;` (matches `StatusBar`).

The `_fetch_queries` worker return type changes from `list[QueryInfo]` to `tuple[list[QueryInfo], ClusterStats]`. The `on_worker_state_changed` handler destructures the tuple, assigning queries to `self._queries` and stats to a new `self._cluster_stats` field. `_update_table` then updates the `ClusterHeader` widget.

## Formatting

Segments are pipe-separated with spaces. Each segment is included only if its data is available:

| Segment | Source | Example | When omitted |
|---------|--------|---------|-------------|
| Version | `/v1/info` | `trino 449` | Endpoint unavailable |
| Workers | `/v1/cluster` | `8 workers` | Endpoint unavailable |
| Query breakdown | query list | `47 queries: 12 run 3 queued 32 done` | Never (always shown) |
| Memory | query list | `124.5GB mem` | Never |
| CPU | query list | `45.2m cpu` | Never |
| Rows | query list | `1.2B rows` | Never |
| Data | query list | `340.2GB data` | Never |
| Uptime | `/v1/info` | `up 3d2h` | Endpoint unavailable |

Zero-value states in the query breakdown (e.g., 0 failed) are omitted to save space. Memory, CPU, and resource stats always come from query-list aggregation; `/v1/cluster` is used only for worker count.

## Testing

- Unit tests for `ClusterStats` aggregation from a list of `QueryInfo` objects
- Unit tests for `format_compact_number` and `format_compact_uptime`
- Unit tests for the header formatting function (various combinations of available/unavailable data)
- Unit tests for endpoint fallback behavior (404 marks unavailable, 500 does not, subsequent calls skip unavailable endpoints)
- Mock `/v1/info` and `/v1/cluster` in the existing test HTTP server
