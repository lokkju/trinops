# Drop SqlQueryBackend Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove `SqlQueryBackend` and all backend-selection plumbing, leaving `HttpQueryBackend` as the sole backend.

**Architecture:** Delete `SqlQueryBackend` and its column-discovery logic from `backend.py`. Remove the `backend` parameter from `TrinopsClient.from_profile()` and `_build_client()`. Remove `--backend` CLI flags. Simplify `TrinopsClient` methods that currently guard on backend type with `isinstance`/`hasattr` checks. Remove the `QueryBackend` protocol since there's only one implementation.

**Tech Stack:** Python, pytest

---

## File Structure

| File | Action | What changes |
|------|--------|--------------|
| `src/trinops/backend.py` | Modify | Delete `SqlQueryBackend`, `_REQUIRED_COLS`, `_OPTIONAL_COL_CANDIDATES`, column discovery. Delete `QueryBackend` protocol. Remove top-level `import trino.dbapi`. Update module docstring. |
| `src/trinops/client.py` | Modify | Remove `backend` param from `from_profile`. Remove `SqlQueryBackend` import. Remove `isinstance`/`hasattr` guards — call methods directly. |
| `src/trinops/cli/commands.py` | Modify | Remove `--backend` option from `queries`, `query`, `tui`, `top`. Remove `backend` param from `_build_client`. Simplify `kill` command (remove `backend="http"` and dead `NotImplementedError` handler). |
| `tests/test_backend.py` | Delete | All tests are SQL-backend-specific. |
| `tests/test_client.py` | Modify | Remove `test_client_from_profile_sql`. Update `test_client_from_profile_http` (no backend param). |
| `tests/test_http_backend.py` | Modify | Remove `QueryBackend` from import, remove `test_client_kill_query_sql_backend_raises`. |
| `AGENTS.md` | Modify | Update architecture and tech stack sections. |

---

## Chunk 1: Backend and Client

### Task 1: Delete SqlQueryBackend from backend.py

**Files:**
- Modify: `src/trinops/backend.py:1-182`

- [ ] **Step 1: Remove top-level `import trino.dbapi`**

Delete line 35:
```python
import trino.dbapi
```

- [ ] **Step 2: Delete `QueryBackend` protocol**

Delete lines 42-47 (including trailing blank line):
```python
@runtime_checkable
class QueryBackend(Protocol):
    def list_queries(self, state: Optional[str] = None, limit: int = 0, query_user: Optional[str] = None) -> list[QueryInfo]: ...
    def get_query(self, query_id: str) -> Optional[QueryInfo]: ...
    def close(self) -> None: ...
```

- [ ] **Step 3: Delete all SQL-related constants and the SqlQueryBackend class**

Delete lines 49-182 (everything from `_REQUIRED_COLS` through the end of `SqlQueryBackend.close`):
- `_REQUIRED_COLS`
- `_OPTIONAL_COL_CANDIDATES`
- `class SqlQueryBackend` (entire class, lines 76-182)

- [ ] **Step 4: Update module docstring**

Change line 1 from:
```python
"""Query backend protocol and SQL implementation for trinops."""
```
to:
```python
"""HTTP query backend for trinops."""
```

- [ ] **Step 5: Clean up unused imports**

Remove `Protocol` and `runtime_checkable` from the typing import (line 11). They're only used by `QueryBackend`. The line should become:
```python
from typing import Optional
```

- [ ] **Step 6: Verify backend.py parses**

Run: `uv run python -c "from trinops.backend import HttpQueryBackend; print('ok')"`
Expected: `ok`

- [ ] **Step 7: Delete tests/test_backend.py**

This file only contains SQL backend tests. Delete it entirely.

- [ ] **Step 8: Run remaining tests to check for breakage**

Run: `uv run python -m pytest tests/ -x -q`
Expected: Collection-time failures in `test_client.py` (imports `SqlQueryBackend`) and `test_http_backend.py` (imports `QueryBackend`). Fixed in Task 3.

### Task 2: Simplify TrinopsClient

**Files:**
- Modify: `src/trinops/client.py`

- [ ] **Step 1: Update imports**

Change:
```python
from trinops.backend import QueryBackend, HttpQueryBackend, SqlQueryBackend
```
to:
```python
from trinops.backend import HttpQueryBackend
```

- [ ] **Step 2: Simplify `__init__`**

Change:
```python
def __init__(self, backend: QueryBackend, profile: Optional[ConnectionProfile] = None) -> None:
    self._backend = backend
    self._profile = profile
```
to:
```python
def __init__(self, backend: HttpQueryBackend, profile: Optional[ConnectionProfile] = None) -> None:
    self._backend = backend
    self._profile = profile
```

- [ ] **Step 3: Simplify `from_profile`**

Remove the `backend` parameter and the SQL branch. Change:
```python
@classmethod
def from_profile(cls, profile: ConnectionProfile, backend: str = "http") -> TrinopsClient:
    if backend == "sql":
        return cls(backend=SqlQueryBackend(profile), profile=profile)
    return cls(backend=HttpQueryBackend(profile), profile=profile)
```
to:
```python
@classmethod
def from_profile(cls, profile: ConnectionProfile) -> TrinopsClient:
    return cls(backend=HttpQueryBackend(profile), profile=profile)
```

- [ ] **Step 4: Simplify `check_connection`**

The current code has an `isinstance` check and a fallback path for SQL backend. Since the backend is always HTTP now, simplify to:
```python
def check_connection(self) -> None:
    """Verify connectivity and auth via HTTP health check."""
    self._backend.check_connection()
```

- [ ] **Step 5: Simplify `get_query_raw`**

Change from `hasattr` check:
```python
def get_query_raw(self, query_id: str) -> Optional[dict]:
    """Return raw REST API response for a single query (HTTP backend only)."""
    if hasattr(self._backend, "get_query_raw"):
        return self._backend.get_query_raw(query_id)
    return None
```
to direct call:
```python
def get_query_raw(self, query_id: str) -> Optional[dict]:
    """Return raw REST API response for a single query."""
    return self._backend.get_query_raw(query_id)
```

- [ ] **Step 6: Simplify `kill_query`**

Change from `hasattr` check:
```python
def kill_query(self, query_id: str) -> bool:
    """Kill a query. Returns True on success, False if already gone."""
    if hasattr(self._backend, "kill_query"):
        return self._backend.kill_query(query_id)
    raise NotImplementedError("kill_query requires HTTP backend")
```
to direct call:
```python
def kill_query(self, query_id: str) -> bool:
    """Kill a query. Returns True on success, False if already gone."""
    return self._backend.kill_query(query_id)
```

- [ ] **Step 7: Simplify `build_cluster_stats`**

Remove the `isinstance` guard that skips REST endpoints for non-HTTP backends. The method currently checks `if not isinstance(self._backend, HttpQueryBackend): return stats` — remove that check since backend is always HTTP. Change:
```python
def build_cluster_stats(self, queries: list[QueryInfo]) -> ClusterStats:
    """Build cluster stats from queries and optional REST endpoints."""
    stats = ClusterStats.from_queries(queries)
    if not isinstance(self._backend, HttpQueryBackend):
        return stats

    info = self._backend.get_info()
```
to:
```python
def build_cluster_stats(self, queries: list[QueryInfo]) -> ClusterStats:
    """Build cluster stats from queries and optional REST endpoints."""
    stats = ClusterStats.from_queries(queries)

    info = self._backend.get_info()
```

- [ ] **Step 8: Verify client.py parses**

Run: `uv run python -c "from trinops.client import TrinopsClient; print('ok')"`
Expected: `ok`

### Task 3: Update client tests

**Files:**
- Modify: `tests/test_client.py`
- Modify: `tests/test_http_backend.py`

- [ ] **Step 1: Update test_client.py**

Delete `test_client_from_profile_sql` (lines 65-71) and `test_client_from_profile_http` (lines 56-62). The existing `test_client_from_profile` (line 47) already covers the default path and needs no changes.

- [ ] **Step 2: Fix test_http_backend.py imports and remove SQL test**

Change line 12 from:
```python
from trinops.backend import HttpQueryBackend, QueryBackend, EndpointState
```
to:
```python
from trinops.backend import HttpQueryBackend, EndpointState
```

Delete `test_client_kill_query_sql_backend_raises` (lines 469-474).

- [ ] **Step 3: Run all tests**

Run: `uv run python -m pytest tests/ -x -q`
Expected: All pass. The CLI commands still reference the old `backend` parameter in `_build_client` / `from_profile`, but there are no CLI-specific tests that exercise the call path, so this won't fail until Task 4.

- [ ] **Step 4: Commit**

```bash
git add src/trinops/backend.py src/trinops/client.py tests/test_client.py tests/test_http_backend.py
git rm tests/test_backend.py
git commit -m "refactor(backend): drop SqlQueryBackend, simplify to HTTP-only"
```

## Chunk 2: CLI and Documentation

### Task 4: Remove --backend flag from CLI commands

**Files:**
- Modify: `src/trinops/cli/commands.py`

- [ ] **Step 1: Remove `backend` param from `_build_client`**

Change:
```python
def _build_client(
    server: Optional[str] = None,
    profile: Optional[str] = None,
    user: Optional[str] = None,
    auth: Optional[str] = None,
    backend: str = "http",
    check: bool = False,
) -> TrinopsClient:
    cp = _build_profile(server=server, profile=profile, user=user, auth=auth)
    client = TrinopsClient.from_profile(cp, backend=backend)
```
to:
```python
def _build_client(
    server: Optional[str] = None,
    profile: Optional[str] = None,
    user: Optional[str] = None,
    auth: Optional[str] = None,
    check: bool = False,
) -> TrinopsClient:
    cp = _build_profile(server=server, profile=profile, user=user, auth=auth)
    client = TrinopsClient.from_profile(cp)
```

- [ ] **Step 2: Remove `--backend` from `queries` command**

Delete the `backend` parameter line:
```python
    backend: str = typer.Option("http", help="Backend (http/sql)"),
```

Update the `_build_client` call to remove `backend=backend`:
```python
    client = _build_client(server=server, profile=profile, user=user, auth=auth)
```

- [ ] **Step 3: Remove `--backend` from `query` command**

Delete the `backend` parameter line and update the `_build_client` call:
```python
    client = _build_client(server=server, profile=profile, user=user, auth=auth)
```

- [ ] **Step 4: Remove `--backend` from `tui` command**

Delete the `backend` parameter line and update the `_build_client` call:
```python
    client = _build_client(server=server, profile=profile, user=user, auth=auth, check=True)
```

- [ ] **Step 5: Remove `--backend` from `top` command**

Delete the `backend` parameter line and update the `tui()` call:
```python
    tui(server=server, profile=profile, user=user, auth=auth, interval=interval)
```

- [ ] **Step 6: Simplify `kill` command**

Remove `backend="http"` from the `_build_client` call:
```python
    client = _build_client(server=server, profile=profile, user=user, auth=auth)
```

Remove the now-dead `NotImplementedError` handler (lines 252-254):
```python
    except NotImplementedError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
```
`kill_query` can no longer raise `NotImplementedError` since the backend is always HTTP.

- [ ] **Step 7: Run all tests**

Run: `uv run python -m pytest tests/ -x -q`
Expected: All pass.

- [ ] **Step 8: Verify CLI help has no --backend references**

Run: `uv run python -m trinops queries --help | grep -i backend`
Expected: No output (no --backend flag).

### Task 5: Update AGENTS.md

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Update Tech Stack**

Remove the `trino.dbapi` line. Change:
```
- `trino.dbapi` for SQL backend
```
Remove this line entirely. `trino` is still a dependency (used by auth and progress modules) but is no longer relevant to the backend architecture.

- [ ] **Step 2: Update Architecture**

Change:
```
- `src/trinops/backend.py` — `QueryBackend` protocol, `HttpQueryBackend`, `SqlQueryBackend`
```
to:
```
- `src/trinops/backend.py` — `HttpQueryBackend` (REST API client for Trino)
```

- [ ] **Step 3: Commit**

```bash
git add src/trinops/cli/commands.py AGENTS.md
git commit -m "refactor(cli): remove --backend flag, update docs for HTTP-only backend"
```
