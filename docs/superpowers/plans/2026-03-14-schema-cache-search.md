# Schema Cache and Search Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cache Trino catalog/schema/table/column metadata locally as JSON files and provide CLI search commands.

**Architecture:** New `src/trinops/schema/` package with three modules: `cache.py` (JSON file I/O), `fetcher.py` (DB-API queries), `search.py` (in-memory index). CLI commands in a new `schema` Typer subcommand group. Cache stored at `~/.cache/trinops/schemas/<profile>/` with one JSON file per catalog.

**Tech Stack:** `trino` DB-API client (already a dependency), `fnmatch` (stdlib) for glob search, `json` (stdlib) for cache I/O, Typer for CLI commands, Rich for table output.

**Spec:** `docs/superpowers/specs/2026-03-14-schema-cache-search-design.md`

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/trinops/schema/__init__.py` | Package init, public API |
| Create | `src/trinops/schema/cache.py` | SchemaCache: read/write JSON, cache directory management |
| Create | `src/trinops/schema/fetcher.py` | SchemaFetcher: trino DB-API connection, information_schema queries |
| Create | `src/trinops/schema/search.py` | SchemaSearch: load cache, build index, glob/substring matching |
| Modify | `src/trinops/cli/commands.py` | Add `schema` subcommand group |
| Create | `tests/test_schema_cache.py` | Cache read/write tests |
| Create | `tests/test_schema_search.py` | Search index and matching tests |
| Create | `tests/test_schema_fetcher.py` | Fetcher tests (mocked DB-API) |
| Create | `tests/test_cli_schema.py` | CLI command integration tests |

---

## Chunk 1: Cache and Search Modules

### Task 1: SchemaCache — JSON File Management

**Files:**
- Create: `tests/test_schema_cache.py`
- Create: `src/trinops/schema/__init__.py`
- Create: `src/trinops/schema/cache.py`

**Context:** The cache stores JSON files at `~/.cache/trinops/schemas/<profile>/<catalog>.json`. Each file has the structure shown in the spec: `{"catalog": "...", "profile": "...", "fetched_at": "...", "schemas": {...}}`. The `SchemaCache` class needs to handle reading, writing, listing cached catalogs, and reporting cache age. Profile name `"default"` is used for the unnamed default profile.

- [ ] **Step 1: Write failing tests**

Create `tests/test_schema_cache.py`:

```python
"""Tests for SchemaCache."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


SAMPLE_CACHE = {
    "catalog": "tpch",
    "profile": "default",
    "fetched_at": "2026-03-14T12:00:00+00:00",
    "schemas": {
        "sf1": {
            "tables": {
                "lineitem": {
                    "type": "TABLE",
                    "columns": [
                        {"name": "orderkey", "type": "INTEGER", "nullable": True},
                        {"name": "quantity", "type": "DOUBLE", "nullable": True},
                    ],
                },
                "nation": {
                    "type": "TABLE",
                    "columns": [
                        {"name": "nationkey", "type": "INTEGER", "nullable": True},
                        {"name": "name", "type": "VARCHAR", "nullable": True},
                    ],
                },
            },
        },
    },
}


def test_cache_write_and_read(tmp_path):
    from trinops.schema.cache import SchemaCache

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    data = cache.read("default", "tpch")
    assert data is not None
    assert data["catalog"] == "tpch"
    assert "sf1" in data["schemas"]
    assert "lineitem" in data["schemas"]["sf1"]["tables"]


def test_cache_read_missing(tmp_path):
    from trinops.schema.cache import SchemaCache

    cache = SchemaCache(base_dir=tmp_path)
    assert cache.read("default", "nonexistent") is None


def test_cache_list_catalogs(tmp_path):
    from trinops.schema.cache import SchemaCache

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    cache.write("default", "hive", {**SAMPLE_CACHE, "catalog": "hive"})

    catalogs = cache.list_catalogs("default")
    assert set(catalogs) == {"tpch", "hive"}


def test_cache_list_catalogs_empty(tmp_path):
    from trinops.schema.cache import SchemaCache

    cache = SchemaCache(base_dir=tmp_path)
    assert cache.list_catalogs("default") == []


def test_cache_profile_isolation(tmp_path):
    from trinops.schema.cache import SchemaCache

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    cache.write("prod", "tpch", {**SAMPLE_CACHE, "profile": "prod"})

    default_data = cache.read("default", "tpch")
    prod_data = cache.read("prod", "tpch")
    assert default_data["profile"] == "default"
    assert prod_data["profile"] == "prod"
    assert cache.list_catalogs("staging") == []


def test_cache_file_structure(tmp_path):
    from trinops.schema.cache import SchemaCache

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    expected_path = tmp_path / "default" / "tpch.json"
    assert expected_path.exists()
    with open(expected_path) as f:
        data = json.load(f)
    assert data["catalog"] == "tpch"


def test_cache_stats(tmp_path):
    from trinops.schema.cache import SchemaCache

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    stats = cache.get_stats("default", "tpch")
    assert stats is not None
    assert stats["catalog"] == "tpch"
    assert stats["table_count"] == 2
    assert stats["column_count"] == 4
    assert "fetched_at" in stats
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_schema_cache.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'trinops.schema'`

- [ ] **Step 3: Implement SchemaCache**

Create `src/trinops/schema/__init__.py`:

```python
"""Schema cache and search for Trino metadata."""
```

Create `src/trinops/schema/cache.py`:

```python
"""JSON file cache for Trino schema metadata."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


DEFAULT_CACHE_DIR = Path.home() / ".cache" / "trinops" / "schemas"


class SchemaCache:
    """Manages JSON cache files at <base_dir>/<profile>/<catalog>.json."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or DEFAULT_CACHE_DIR

    def _catalog_path(self, profile: str, catalog: str) -> Path:
        return self._base_dir / profile / f"{catalog}.json"

    def write(self, profile: str, catalog: str, data: dict) -> None:
        path = self._catalog_path(profile, catalog)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def read(self, profile: str, catalog: str) -> Optional[dict]:
        path = self._catalog_path(profile, catalog)
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    def list_catalogs(self, profile: str) -> list[str]:
        profile_dir = self._base_dir / profile
        if not profile_dir.exists():
            return []
        return sorted(
            p.stem for p in profile_dir.glob("*.json")
        )

    def list_profiles(self) -> list[str]:
        if not self._base_dir.exists():
            return []
        return sorted(p.name for p in self._base_dir.iterdir() if p.is_dir())

    def get_stats(self, profile: str, catalog: str) -> Optional[dict]:
        data = self.read(profile, catalog)
        if data is None:
            return None
        table_count = 0
        column_count = 0
        for schema_data in data.get("schemas", {}).values():
            for table_data in schema_data.get("tables", {}).values():
                table_count += 1
                column_count += len(table_data.get("columns", []))
        return {
            "catalog": catalog,
            "profile": profile,
            "fetched_at": data.get("fetched_at", ""),
            "table_count": table_count,
            "column_count": column_count,
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_schema_cache.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add src/trinops/schema/__init__.py src/trinops/schema/cache.py tests/test_schema_cache.py
git commit -m "feat(schema): add SchemaCache for JSON file management"
```

---

### Task 2: SchemaSearch — In-Memory Index and Matching

**Files:**
- Create: `tests/test_schema_search.py`
- Create: `src/trinops/schema/search.py`

**Context:** `SchemaSearch` loads cached JSON files, builds an in-memory index, and supports search. Patterns without glob characters (`*`, `?`, `[`) are treated as substring matches (wrapped in `*pattern*`). Uses `fnmatch.fnmatch` for matching. Results are returned as a list of dicts with `catalog`, `schema`, `table`, and optionally `column`/`column_type` for column-level matches.

- [ ] **Step 1: Write failing tests**

Create `tests/test_schema_search.py`:

```python
"""Tests for SchemaSearch."""
from __future__ import annotations

import pytest

from tests.test_schema_cache import SAMPLE_CACHE


MULTI_CATALOG_CACHE = {
    "catalog": "hive",
    "profile": "default",
    "fetched_at": "2026-03-14T12:00:00+00:00",
    "schemas": {
        "analytics": {
            "tables": {
                "orders": {
                    "type": "TABLE",
                    "columns": [
                        {"name": "order_id", "type": "INTEGER", "nullable": True},
                        {"name": "customer_id", "type": "INTEGER", "nullable": True},
                        {"name": "total", "type": "DOUBLE", "nullable": True},
                    ],
                },
                "customers": {
                    "type": "TABLE",
                    "columns": [
                        {"name": "customer_id", "type": "INTEGER", "nullable": True},
                        {"name": "name", "type": "VARCHAR", "nullable": True},
                    ],
                },
            },
        },
    },
}


def test_search_table_glob(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    search = SchemaSearch(cache, profile="default")
    results = search.search_tables("*line*")
    assert len(results) == 1
    assert results[0]["table"] == "lineitem"
    assert results[0]["catalog"] == "tpch"
    assert results[0]["schema"] == "sf1"


def test_search_table_substring(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    # No glob chars — treated as substring match
    search = SchemaSearch(cache, profile="default")
    results = search.search_tables("nation")
    assert len(results) == 1
    assert results[0]["table"] == "nation"


def test_search_columns(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "hive", MULTI_CATALOG_CACHE)

    search = SchemaSearch(cache, profile="default")
    results = search.search_columns("customer_id")
    assert len(results) == 2  # appears in both orders and customers
    tables = {r["table"] for r in results}
    assert tables == {"orders", "customers"}
    assert all(r["column"] == "customer_id" for r in results)


def test_search_across_catalogs(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    cache.write("default", "hive", MULTI_CATALOG_CACHE)

    search = SchemaSearch(cache, profile="default")
    results = search.search_tables("*")  # match all
    catalogs = {r["catalog"] for r in results}
    assert catalogs == {"tpch", "hive"}


def test_search_scoped_to_catalog(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    cache.write("default", "hive", MULTI_CATALOG_CACHE)

    search = SchemaSearch(cache, profile="default", catalog="tpch")
    results = search.search_tables("*")
    assert all(r["catalog"] == "tpch" for r in results)


def test_search_no_results(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    search = SchemaSearch(cache, profile="default")
    results = search.search_tables("nonexistent")
    assert results == []


def test_search_fully_qualified(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    search = SchemaSearch(cache, profile="default")
    results = search.lookup_table("tpch.sf1.lineitem")
    assert results is not None
    assert results["table"] == "lineitem"
    assert len(results["columns"]) == 2


def test_search_unqualified_show(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    search = SchemaSearch(cache, profile="default")
    results = search.lookup_tables("lineitem")
    assert len(results) == 1
    assert results[0]["catalog"] == "tpch"
    assert results[0]["schema"] == "sf1"
    assert len(results[0]["columns"]) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_schema_search.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'trinops.schema.search'`

- [ ] **Step 3: Implement SchemaSearch**

Create `src/trinops/schema/search.py`:

```python
"""In-memory search over cached schema metadata."""
from __future__ import annotations

import fnmatch
from typing import Optional

from trinops.schema.cache import SchemaCache


def _has_glob_chars(pattern: str) -> bool:
    return any(c in pattern for c in ("*", "?", "["))


def _normalize_pattern(pattern: str) -> str:
    """If no glob chars, treat as substring match."""
    if _has_glob_chars(pattern):
        return pattern
    return f"*{pattern}*"


class SchemaSearch:
    """Loads cached schema JSON and provides search over tables and columns."""

    def __init__(
        self,
        cache: SchemaCache,
        profile: str = "default",
        catalog: Optional[str] = None,
    ) -> None:
        self._cache = cache
        self._profile = profile
        self._catalog_filter = catalog
        self._entries: list[dict] = []
        self._load()

    def _load(self) -> None:
        catalogs = self._cache.list_catalogs(self._profile)
        if self._catalog_filter:
            catalogs = [c for c in catalogs if c == self._catalog_filter]
        self._entries = []
        for cat_name in catalogs:
            data = self._cache.read(self._profile, cat_name)
            if data is None:
                continue
            for schema_name, schema_data in data.get("schemas", {}).items():
                for table_name, table_data in schema_data.get("tables", {}).items():
                    self._entries.append({
                        "catalog": cat_name,
                        "schema": schema_name,
                        "table": table_name,
                        "type": table_data.get("type", "TABLE"),
                        "columns": table_data.get("columns", []),
                    })

    def search_tables(self, pattern: str) -> list[dict]:
        pat = _normalize_pattern(pattern)
        results = []
        for entry in self._entries:
            if fnmatch.fnmatch(entry["table"], pat):
                results.append({
                    "catalog": entry["catalog"],
                    "schema": entry["schema"],
                    "table": entry["table"],
                    "type": entry["type"],
                })
        return results

    def search_columns(self, pattern: str) -> list[dict]:
        pat = _normalize_pattern(pattern)
        results = []
        for entry in self._entries:
            for col in entry["columns"]:
                if fnmatch.fnmatch(col["name"], pat):
                    results.append({
                        "catalog": entry["catalog"],
                        "schema": entry["schema"],
                        "table": entry["table"],
                        "column": col["name"],
                        "column_type": col.get("type", ""),
                    })
        return results

    def lookup_table(self, fqn: str) -> Optional[dict]:
        """Lookup a table by fully qualified name (catalog.schema.table)."""
        parts = fqn.split(".")
        if len(parts) != 3:
            return None
        cat, sch, tbl = parts
        for entry in self._entries:
            if entry["catalog"] == cat and entry["schema"] == sch and entry["table"] == tbl:
                return {
                    "catalog": entry["catalog"],
                    "schema": entry["schema"],
                    "table": entry["table"],
                    "type": entry["type"],
                    "columns": entry["columns"],
                }
        return None

    def lookup_tables(self, name: str) -> list[dict]:
        """Lookup tables by unqualified or partially qualified name.

        Accepts: "table", "schema.table", or "catalog.schema.table".
        Returns all matches with their columns.
        """
        parts = name.split(".")
        results = []
        for entry in self._entries:
            match = False
            if len(parts) == 1:
                match = entry["table"] == parts[0]
            elif len(parts) == 2:
                match = entry["schema"] == parts[0] and entry["table"] == parts[1]
            elif len(parts) == 3:
                match = (
                    entry["catalog"] == parts[0]
                    and entry["schema"] == parts[1]
                    and entry["table"] == parts[2]
                )
            if match:
                results.append({
                    "catalog": entry["catalog"],
                    "schema": entry["schema"],
                    "table": entry["table"],
                    "type": entry["type"],
                    "columns": entry["columns"],
                })
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_schema_search.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add src/trinops/schema/search.py tests/test_schema_search.py
git commit -m "feat(schema): add SchemaSearch with glob, substring, and qualified lookup"
```

---

### Task 3: SchemaFetcher — DB-API Queries

**Files:**
- Create: `tests/test_schema_fetcher.py`
- Create: `src/trinops/schema/fetcher.py`

**Context:** The fetcher connects to Trino via `trino.dbapi.connect()` and runs `information_schema` queries. Auth mapping from `ConnectionProfile`:
- `none` → no auth param
- `basic` → `trino.auth.BasicAuthentication`
- `jwt` → `trino.auth.JWTAuthentication`
- `oauth2` → `trino.auth.OAuth2Authentication`
- `kerberos` → `trino.auth.KerberosAuthentication`

The existing `build_auth()` in `src/trinops/auth.py` already handles this mapping and returns the right auth object. The fetcher reuses it. Password resolution uses `resolve_password()` from the same module.

The `ConnectionProfile` has `server` (e.g., `"host:8080"`), `scheme` (e.g., `"https"`), `user`, and `catalog`/`schema` fields. The fetcher parses host/port from `server`.

- [ ] **Step 1: Write failing tests**

Create `tests/test_schema_fetcher.py`:

```python
"""Tests for SchemaFetcher (mocked DB-API)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from trinops.config import ConnectionProfile


def _mock_cursor(rows):
    """Create a mock cursor that returns rows on fetchall()."""
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    cursor.description = [(f"col{i}",) for i in range(10)]
    return cursor


def test_fetcher_single_catalog():
    from trinops.schema.fetcher import SchemaFetcher

    profile = ConnectionProfile(
        server="localhost:8080", scheme="http", auth="none", user="dev", catalog="tpch"
    )
    fetcher = SchemaFetcher(profile)

    schemata_rows = [("sf1",), ("sf10",)]
    tables_rows = [
        ("sf1", "lineitem", "TABLE"),
        ("sf1", "nation", "TABLE"),
        ("sf10", "lineitem", "TABLE"),
    ]
    columns_rows = [
        ("sf1", "lineitem", "orderkey", "INTEGER", "YES"),
        ("sf1", "lineitem", "quantity", "DOUBLE", "YES"),
        ("sf1", "nation", "nationkey", "INTEGER", "YES"),
        ("sf10", "lineitem", "orderkey", "INTEGER", "YES"),
    ]

    mock_conn = MagicMock()
    cursors = [
        _mock_cursor(schemata_rows),
        _mock_cursor(tables_rows),
        _mock_cursor(columns_rows),
    ]
    cursor_idx = [0]

    def next_cursor():
        c = cursors[cursor_idx[0]]
        cursor_idx[0] += 1
        return c

    mock_conn.cursor.side_effect = next_cursor

    with patch("trinops.schema.fetcher.trino_connect", return_value=mock_conn):
        result = fetcher.fetch_catalog("tpch")

    assert result["catalog"] == "tpch"
    assert result["profile"] == "default"
    assert "fetched_at" in result
    assert "sf1" in result["schemas"]
    assert "lineitem" in result["schemas"]["sf1"]["tables"]
    cols = result["schemas"]["sf1"]["tables"]["lineitem"]["columns"]
    assert len(cols) == 2
    assert cols[0]["name"] == "orderkey"


def test_fetcher_discover_catalogs():
    from trinops.schema.fetcher import SchemaFetcher

    profile = ConnectionProfile(
        server="localhost:8080", scheme="http", auth="none", user="dev"
    )
    fetcher = SchemaFetcher(profile)

    mock_conn = MagicMock()
    cursor = _mock_cursor([("tpch",), ("hive",), ("system",)])
    mock_conn.cursor.return_value = cursor

    with patch("trinops.schema.fetcher.trino_connect", return_value=mock_conn):
        catalogs = fetcher.discover_catalogs()

    assert catalogs == ["tpch", "hive", "system"]


def test_fetcher_per_catalog_error_handling():
    from trinops.schema.fetcher import SchemaFetcher

    profile = ConnectionProfile(
        server="localhost:8080", scheme="http", auth="none", user="dev"
    )
    fetcher = SchemaFetcher(profile)

    mock_conn = MagicMock()
    mock_conn.cursor.side_effect = Exception("permission denied")

    with patch("trinops.schema.fetcher.trino_connect", return_value=mock_conn):
        with pytest.raises(Exception, match="permission denied"):
            fetcher.fetch_catalog("restricted")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_schema_fetcher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'trinops.schema.fetcher'`

- [ ] **Step 3: Implement SchemaFetcher**

Create `src/trinops/schema/fetcher.py`:

```python
"""Fetch schema metadata from Trino via DB-API."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from trino.dbapi import connect as trino_connect

from trinops.auth import build_auth, resolve_password
from trinops.config import ConnectionProfile


class SchemaFetcher:
    """Connects to Trino and fetches information_schema metadata."""

    def __init__(self, profile: ConnectionProfile, profile_name: str = "default") -> None:
        self._profile = profile
        self._profile_name = profile_name

    def _connect(self):
        p = self._profile
        host, _, port_str = p.server.partition(":")
        port = int(port_str) if port_str else (443 if p.scheme == "https" else 8080)

        kwargs = {
            "host": host,
            "port": port,
            "user": p.user or "trinops",
            "http_scheme": p.scheme,
        }

        if p.auth and p.auth != "none":
            auth = build_auth(p)
            if auth is not None:
                kwargs["auth"] = auth

        return trino_connect(**kwargs)

    def discover_catalogs(self) -> list[str]:
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute("SHOW CATALOGS")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def fetch_catalog(self, catalog: str) -> dict:
        conn = self._connect()
        try:
            # 1. Discover schemas
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT schema_name FROM {catalog}.information_schema.schemata"
            )
            schema_names = [row[0] for row in cursor.fetchall()]

            # 2. Discover tables
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT table_schema, table_name, table_type "
                f"FROM {catalog}.information_schema.tables"
            )
            tables_by_schema: dict[str, dict[str, dict]] = {}
            for schema, table, table_type in cursor.fetchall():
                tables_by_schema.setdefault(schema, {})[table] = {
                    "type": table_type,
                    "columns": [],
                }

            # 3. Discover columns
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT table_schema, table_name, column_name, data_type, is_nullable "
                f"FROM {catalog}.information_schema.columns"
            )
            for schema, table, col_name, data_type, nullable in cursor.fetchall():
                tbl = tables_by_schema.get(schema, {}).get(table)
                if tbl is not None:
                    tbl["columns"].append({
                        "name": col_name,
                        "type": data_type,
                        "nullable": nullable == "YES",
                    })

            # Assemble result
            schemas = {}
            for schema_name in schema_names:
                if schema_name in tables_by_schema:
                    schemas[schema_name] = {"tables": tables_by_schema[schema_name]}

            return {
                "catalog": catalog,
                "profile": self._profile_name,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "schemas": schemas,
            }
        finally:
            conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_schema_fetcher.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/trinops/schema/fetcher.py tests/test_schema_fetcher.py
git commit -m "feat(schema): add SchemaFetcher for DB-API information_schema queries"
```

---

## Chunk 2: CLI Commands

### Task 4: CLI Schema Commands

**Files:**
- Create: `tests/test_cli_schema.py`
- Modify: `src/trinops/cli/commands.py`

**Context:** Add a `schema` Typer subcommand group with `refresh`, `search`, `show`, and `list` commands. Follow the existing CLI pattern: `_build_profile()` for connection options, `_status()` for spinner on stderr, Rich tables for output, `--json` for structured output. See `src/trinops/cli/commands.py:284-287` for how `config_app` and `auth_app` are registered as sub-Typers.

The `refresh` command needs the profile name string to pass to the fetcher and cache. The config system (`TrinopsConfig`) doesn't expose the profile name — you infer it from the `--profile` flag (default is `"default"`).

- [ ] **Step 1: Write failing tests**

Create `tests/test_cli_schema.py`:

```python
"""Tests for CLI schema commands."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from trinops.cli.commands import app


runner = CliRunner()


def test_schema_list_no_cache(tmp_path):
    with patch("trinops.schema.cache.DEFAULT_CACHE_DIR", tmp_path):
        result = runner.invoke(app, ["schema", "list"])
    assert result.exit_code == 0
    assert "No cached catalogs" in result.output


def test_schema_list_with_cache(tmp_path):
    from trinops.schema.cache import SchemaCache
    from tests.test_schema_cache import SAMPLE_CACHE

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    with patch("trinops.schema.cache.DEFAULT_CACHE_DIR", tmp_path):
        result = runner.invoke(app, ["schema", "list"])
    assert result.exit_code == 0
    assert "tpch" in result.output


def test_schema_search_tables(tmp_path):
    from trinops.schema.cache import SchemaCache
    from tests.test_schema_cache import SAMPLE_CACHE

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    with patch("trinops.schema.cache.DEFAULT_CACHE_DIR", tmp_path):
        result = runner.invoke(app, ["schema", "search", "*line*"])
    assert result.exit_code == 0
    assert "lineitem" in result.output


def test_schema_search_json(tmp_path):
    from trinops.schema.cache import SchemaCache
    from tests.test_schema_cache import SAMPLE_CACHE

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    with patch("trinops.schema.cache.DEFAULT_CACHE_DIR", tmp_path):
        result = runner.invoke(app, ["schema", "search", "*line*", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 1
    assert data[0]["table"] == "lineitem"


def test_schema_show_table(tmp_path):
    from trinops.schema.cache import SchemaCache
    from tests.test_schema_cache import SAMPLE_CACHE

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    with patch("trinops.schema.cache.DEFAULT_CACHE_DIR", tmp_path):
        result = runner.invoke(app, ["schema", "show", "lineitem"])
    assert result.exit_code == 0
    assert "orderkey" in result.output
    assert "INTEGER" in result.output


def test_schema_show_not_found(tmp_path):
    from trinops.schema.cache import SchemaCache
    from tests.test_schema_cache import SAMPLE_CACHE

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    with patch("trinops.schema.cache.DEFAULT_CACHE_DIR", tmp_path):
        result = runner.invoke(app, ["schema", "show", "nonexistent"])
    assert result.exit_code == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run python -m pytest tests/test_cli_schema.py -v`
Expected: FAIL — "No such command 'schema'"

- [ ] **Step 3: Add schema subcommand group to CLI**

In `src/trinops/cli/commands.py`, after the `auth_app` registration (around line 287), add:

```python
schema_app = typer.Typer(name="schema", help="Manage schema cache and search")
app.add_typer(schema_app, name="schema")


@schema_app.command("refresh")
def schema_refresh(
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
    auth: Optional[str] = typer.Option(None, help="Auth method"),
    catalog: Optional[str] = typer.Option(None, "--catalog", help="Catalog to refresh (default: profile catalog)"),
    all_catalogs: bool = typer.Option(False, "--all", help="Refresh all catalogs"),
):
    """Fetch and cache schema metadata from Trino."""
    from trinops.schema.cache import SchemaCache
    from trinops.schema.fetcher import SchemaFetcher

    cp = _build_profile(server=server, profile=profile, user=user, auth=auth)
    profile_name = profile or "default"
    fetcher = SchemaFetcher(cp, profile_name=profile_name)
    cache = SchemaCache()

    if all_catalogs:
        with _status("Discovering catalogs..."):
            catalogs = fetcher.discover_catalogs()
        typer.echo(f"Found {len(catalogs)} catalogs")
        for cat in catalogs:
            try:
                with _status(f"Fetching {cat}..."):
                    data = fetcher.fetch_catalog(cat)
                cache.write(profile_name, cat, data)
                stats = cache.get_stats(profile_name, cat)
                typer.echo(f"  {cat}: {stats['table_count']} tables, {stats['column_count']} columns")
            except Exception as e:
                typer.echo(f"  {cat}: FAILED ({e})", err=True)
    else:
        target = catalog or cp.catalog
        if not target:
            typer.echo(
                "No catalog specified. Use --catalog or configure one:\n"
                "  trinops config set catalog <name>",
                err=True,
            )
            raise typer.Exit(1)
        with _status(f"Fetching {target}..."):
            data = fetcher.fetch_catalog(target)
        cache.write(profile_name, target, data)
        stats = cache.get_stats(profile_name, target)
        typer.echo(f"{target}: {stats['table_count']} tables, {stats['column_count']} columns")


@schema_app.command("search")
def schema_search(
    pattern: str = typer.Argument(help="Search pattern (glob or substring)"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    catalog: Optional[str] = typer.Option(None, "--catalog", help="Scope to catalog"),
    columns: bool = typer.Option(False, "--columns", help="Include column-level matches"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Search cached schema metadata."""
    import json as _json
    import sys
    from rich.console import Console
    from rich.table import Table

    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch

    profile_name = profile or "default"
    cache = SchemaCache()
    search = SchemaSearch(cache, profile=profile_name, catalog=catalog)

    results = search.search_tables(pattern)
    if columns:
        results.extend(search.search_columns(pattern))

    if not results:
        typer.echo("No matches found")
        raise typer.Exit(1)

    if json:
        sys.stdout.write(_json.dumps(results, indent=2))
        sys.stdout.write("\n")
        return

    table = Table()
    table.add_column("Catalog")
    table.add_column("Schema")
    table.add_column("Table")
    if columns:
        table.add_column("Column")
        table.add_column("Type")
    for r in results:
        if columns and "column" in r:
            table.add_row(r["catalog"], r["schema"], r["table"], r["column"], r.get("column_type", ""))
        else:
            if columns:
                table.add_row(r["catalog"], r["schema"], r["table"], "", "")
            else:
                table.add_row(r["catalog"], r["schema"], r["table"])
    Console().print(table)


@schema_app.command("show")
def schema_show(
    table_name: str = typer.Argument(help="Table name (unqualified, schema.table, or catalog.schema.table)"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Show columns for a table."""
    import json as _json
    import sys
    from rich.console import Console
    from rich.table import Table

    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch

    profile_name = profile or "default"
    cache = SchemaCache()
    search = SchemaSearch(cache, profile=profile_name)

    matches = search.lookup_tables(table_name)
    if not matches:
        typer.echo(f"Table not found: {table_name}", err=True)
        raise typer.Exit(1)

    if json:
        sys.stdout.write(_json.dumps(matches, indent=2))
        sys.stdout.write("\n")
        return

    for m in matches:
        fqn = f"{m['catalog']}.{m['schema']}.{m['table']}"
        typer.echo(f"\n{fqn}")
        table = Table()
        table.add_column("Column")
        table.add_column("Type")
        table.add_column("Nullable")
        for col in m.get("columns", []):
            table.add_row(col["name"], col.get("type", ""), "YES" if col.get("nullable") else "NO")
        Console().print(table)


@schema_app.command("list")
def schema_list(
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
):
    """List cached catalogs."""
    from rich.console import Console
    from rich.table import Table

    from trinops.schema.cache import SchemaCache

    cache = SchemaCache()

    # If no profile specified, show all profiles
    if profile:
        profiles_to_show = [profile]
    else:
        profiles_to_show = cache.list_profiles()

    if not profiles_to_show:
        typer.echo("No cached catalogs. Run 'trinops schema refresh' first.")
        return

    all_empty = True
    table = Table()
    table.add_column("Profile")
    table.add_column("Catalog")
    table.add_column("Tables")
    table.add_column("Columns")
    table.add_column("Age")
    for pname in profiles_to_show:
        catalogs = cache.list_catalogs(pname)
        for cat in catalogs:
            all_empty = False
            stats = cache.get_stats(pname, cat)
            if stats:
                age = _relative_age(stats["fetched_at"])
                table.add_row(
                    pname,
                    cat,
                    str(stats["table_count"]),
                    str(stats["column_count"]),
                    age,
                )

    if all_empty:
        typer.echo("No cached catalogs. Run 'trinops schema refresh' first.")
        return

    Console().print(table)


def _relative_age(iso_timestamp: str) -> str:
    """Convert ISO timestamp to relative age string like '2h ago', '3d ago'."""
    from datetime import datetime, timezone
    try:
        fetched = datetime.fromisoformat(iso_timestamp)
        now = datetime.now(timezone.utc)
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=timezone.utc)
        delta = now - fetched
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"
    except (ValueError, TypeError):
        return iso_timestamp
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run python -m pytest tests/test_cli_schema.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Run full test suite**

Run: `uv run python -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/trinops/cli/commands.py tests/test_cli_schema.py
git commit -m "feat(cli): add schema refresh, search, show, list commands"
```
