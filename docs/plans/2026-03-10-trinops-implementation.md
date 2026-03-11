# trinops Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build trinops, a Python tool for Trino query monitoring with CLI, TUI, and MCP server interfaces over a shared core, absorbing the existing trino-progress library.

**Architecture:** Shared core library (`trinops.client`, `trinops.models`, `trinops.auth`, `trinops.config`) talks to Trino via `system.runtime.queries` SQL and the statement protocol stats field. Three thin interface layers (CLI via typer, TUI via Textual, MCP server) consume the core. The existing trino-progress code moves to `trinops.progress` subpackage.

**Tech Stack:** Python 3.10+, trino-python-client, typer, rich, textual, tomli

---

### Task 1: Restructure Package from trino-progress to trinops

This task renames the package, moves files into the new layout, and updates all imports. No new functionality.

**Files:**
- Rename: `src/trino_progress/` → `src/trinops/progress/`
- Create: `src/trinops/__init__.py`
- Create: `src/trinops/models.py` (placeholder)
- Create: `src/trinops/client.py` (placeholder)
- Create: `src/trinops/auth.py` (placeholder)
- Create: `src/trinops/config.py` (placeholder)
- Create: `src/trinops/cli/__init__.py` (placeholder)
- Create: `src/trinops/tui/__init__.py` (placeholder)
- Create: `src/trinops/mcp/__init__.py` (placeholder)
- Modify: `pyproject.toml`
- Modify: all test files (update imports)

**Step 1: Restructure the directory layout**

```bash
mkdir -p src/trinops/progress/display
mkdir -p src/trinops/cli src/trinops/tui src/trinops/mcp

# Move existing files
mv src/trino_progress/stats.py src/trinops/progress/stats.py
mv src/trino_progress/poller.py src/trinops/progress/poller.py
mv src/trino_progress/progress.py src/trinops/progress/progress.py
mv src/trino_progress/display/__init__.py src/trinops/progress/display/__init__.py
mv src/trino_progress/display/stderr.py src/trinops/progress/display/stderr.py
mv src/trino_progress/display/tqdm.py src/trinops/progress/display/tqdm.py
mv src/trino_progress/display/web.py src/trinops/progress/display/web.py

# Remove old package
rm -rf src/trino_progress/
```

**Step 2: Update pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "trinops"
version = "0.1.0"
description = "Trino query monitoring: CLI, TUI dashboard, MCP server, and progress library"
readme = "README.md"
license = "Apache-2.0"
requires-python = ">=3.10"
dependencies = [
    "trino>=0.320",
]

[project.optional-dependencies]
tqdm = ["tqdm>=4.60"]
cli = ["typer>=0.9", "rich>=13.0"]
tui = ["textual>=0.40"]
mcp = []
all = ["trinops[tqdm]", "trinops[cli]", "trinops[tui]", "trinops[mcp]"]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "tqdm>=4.60",
    "typer>=0.9",
    "rich>=13.0",
    "textual>=0.40",
]

[project.scripts]
trinops = "trinops.cli:app"

[tool.hatch.build.targets.wheel]
packages = ["src/trinops"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Step 3: Create new package files**

`src/trinops/__init__.py`:
```python
from trinops.progress.stats import QueryStats, StageStats
from trinops.progress.progress import TrinoProgress

__all__ = ["TrinoProgress", "QueryStats", "StageStats"]
__version__ = "0.1.0"
```

`src/trinops/progress/__init__.py`:
```python
from trinops.progress.stats import QueryStats, StageStats
from trinops.progress.progress import TrinoProgress
from trinops.progress.display import Display
from trinops.progress.display.stderr import StderrDisplay
from trinops.progress.display.web import WebDisplay

__all__ = [
    "TrinoProgress",
    "QueryStats",
    "StageStats",
    "Display",
    "StderrDisplay",
    "WebDisplay",
]
```

Create empty placeholder files for:
- `src/trinops/models.py`
- `src/trinops/client.py`
- `src/trinops/auth.py`
- `src/trinops/config.py`
- `src/trinops/cli/__init__.py`
- `src/trinops/tui/__init__.py`
- `src/trinops/mcp/__init__.py`

**Step 4: Update all imports in source files**

Every `from trino_progress.` import becomes `from trinops.progress.`. Files to update:
- `src/trinops/progress/poller.py`
- `src/trinops/progress/progress.py`
- `src/trinops/progress/display/__init__.py`
- `src/trinops/progress/display/stderr.py`
- `src/trinops/progress/display/tqdm.py`
- `src/trinops/progress/display/web.py`

**Step 5: Update all test imports**

Every `from trino_progress` import becomes `from trinops.progress`. Files to update:
- `tests/test_stats.py`
- `tests/test_display_stderr.py`
- `tests/test_display_tqdm.py`
- `tests/test_display_web.py`
- `tests/test_poller.py`
- `tests/test_progress.py`
- `tests/test_integration.py`

Also update the integration test to import from `trinops` directly:
```python
from trinops import TrinoProgress, QueryStats
```

**Step 6: Reinstall and run tests**

Run: `uv pip install -e ".[dev]"` then `uv run pytest tests/ -v`
Expected: All 27 tests PASS with new import paths.

**Step 7: Commit**

```bash
git add -A
git commit -m "refactor: restructure package from trino-progress to trinops"
```

---

### Task 2: Config Module

**Files:**
- Create: `src/trinops/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

`tests/test_config.py`:
```python
import os
import tempfile

from trinops.config import TrinopsConfig, load_config, ConnectionProfile


SAMPLE_CONFIG = """\
[default]
server = "trino.example.com:8080"
scheme = "https"
user = "loki"
auth = "oauth2"
catalog = "hive"

[profiles.staging]
server = "trino-staging.example.com:8080"
scheme = "http"
auth = "basic"
user = "loki"
password = "secret123"

[profiles.local]
server = "localhost:8080"
auth = "none"
user = "dev"
"""


def test_load_config_from_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(SAMPLE_CONFIG)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)

    assert config.default.server == "trino.example.com:8080"
    assert config.default.scheme == "https"
    assert config.default.user == "loki"
    assert config.default.auth == "oauth2"
    assert config.default.catalog == "hive"


def test_load_config_profiles():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(SAMPLE_CONFIG)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)

    staging = config.get_profile("staging")
    assert staging.server == "trino-staging.example.com:8080"
    assert staging.auth == "basic"
    assert staging.password == "secret123"

    local = config.get_profile("local")
    assert local.auth == "none"


def test_get_profile_default():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(SAMPLE_CONFIG)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)

    default = config.get_profile(None)
    assert default.server == "trino.example.com:8080"


def test_get_profile_unknown_raises():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(SAMPLE_CONFIG)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)

    try:
        config.get_profile("nonexistent")
        assert False, "Should have raised"
    except KeyError:
        pass


def test_connection_profile_from_env(monkeypatch):
    monkeypatch.setenv("TRINOPS_SERVER", "env-host:9090")
    monkeypatch.setenv("TRINOPS_USER", "envuser")
    monkeypatch.setenv("TRINOPS_AUTH", "none")

    profile = ConnectionProfile.from_env()
    assert profile.server == "env-host:9090"
    assert profile.user == "envuser"
    assert profile.auth == "none"


def test_connection_profile_from_env_missing():
    # Should return None when no env vars set
    profile = ConnectionProfile.from_env()
    # At minimum server must be set for env profile to be valid
    assert profile is None or profile.server is None


def test_profile_merge_env_over_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(SAMPLE_CONFIG)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)

    profile = config.get_profile(None)
    assert profile.user == "loki"  # from file
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: ImportError.

**Step 3: Implement config.py**

`src/trinops/config.py`:
```python
from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "trinops" / "config.toml"


@dataclass
class ConnectionProfile:
    server: Optional[str] = None
    scheme: str = "https"
    user: Optional[str] = None
    auth: str = "none"
    catalog: Optional[str] = None
    schema: Optional[str] = None
    password: Optional[str] = None
    password_cmd: Optional[str] = None
    jwt_token: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> ConnectionProfile:
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    @classmethod
    def from_env(cls) -> Optional[ConnectionProfile]:
        server = os.environ.get("TRINOPS_SERVER")
        if server is None:
            return None
        return cls(
            server=server,
            scheme=os.environ.get("TRINOPS_SCHEME", "https"),
            user=os.environ.get("TRINOPS_USER"),
            auth=os.environ.get("TRINOPS_AUTH", "none"),
            catalog=os.environ.get("TRINOPS_CATALOG"),
            schema=os.environ.get("TRINOPS_SCHEMA"),
        )


@dataclass
class TrinopsConfig:
    default: ConnectionProfile = field(default_factory=ConnectionProfile)
    profiles: dict[str, ConnectionProfile] = field(default_factory=dict)

    def get_profile(self, name: Optional[str]) -> ConnectionProfile:
        if name is None:
            return self.default
        if name not in self.profiles:
            raise KeyError(f"Unknown profile: {name!r}")
        return self.profiles[name]


def load_config(path: str | Path | None = None) -> TrinopsConfig:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return TrinopsConfig()

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    default = ConnectionProfile.from_dict(data.get("default", {}))
    profiles = {}
    for name, profile_data in data.get("profiles", {}).items():
        profiles[name] = ConnectionProfile.from_dict(profile_data)

    return TrinopsConfig(default=default, profiles=profiles)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: All 7 tests PASS.

Note: May need `uv pip install tomli` for Python 3.10 support. Add `tomli>=1.0; python_version < "3.11"` to dependencies in pyproject.toml.

**Step 5: Commit**

```bash
git add src/trinops/config.py tests/test_config.py pyproject.toml
git commit -m "feat: add config module with TOML profiles and env var support"
```

---

### Task 3: Models Module

**Files:**
- Create: `src/trinops/models.py`
- Create: `tests/test_models.py`

**Step 1: Write the failing test**

`tests/test_models.py`:
```python
from datetime import datetime
from trinops.models import QueryInfo, QueryState


def test_query_info_creation():
    qi = QueryInfo(
        query_id="20260310_143549_08022_abc",
        state=QueryState.RUNNING,
        query="SELECT * FROM big_table",
        user="loki",
        source="trinops",
        created=datetime(2026, 3, 10, 14, 35, 49),
        started=datetime(2026, 3, 10, 14, 35, 50),
        ended=None,
        cpu_time_millis=19212,
        wall_time_millis=53095,
        queued_time_millis=100,
        elapsed_time_millis=6872,
        peak_memory_bytes=8650480,
        cumulative_memory_bytes=50000000,
        processed_rows=34148040,
        processed_bytes=474640412,
        error_code=None,
        error_message=None,
    )
    assert qi.query_id == "20260310_143549_08022_abc"
    assert qi.state == QueryState.RUNNING
    assert qi.is_terminal is False


def test_query_state_terminal():
    assert QueryState.FINISHED.is_terminal is True
    assert QueryState.FAILED.is_terminal is True
    assert QueryState.RUNNING.is_terminal is False
    assert QueryState.QUEUED.is_terminal is False


def test_query_info_from_system_row():
    row = {
        "query_id": "20260310_143549_08022_abc",
        "state": "RUNNING",
        "query": "SELECT 1",
        "user": "loki",
        "source": "trino-cli",
        "created": datetime(2026, 3, 10, 14, 35, 49),
        "started": datetime(2026, 3, 10, 14, 35, 50),
        "end": None,
        "cumulative_memory": 50000000.0,
        "peak_memory_bytes": 8650480,
        "cpu_time": 19.212,
        "wall_time": 53.095,
        "queued_time": 0.1,
        "elapsed_time": 6.872,
        "processed_rows": 34148040,
        "processed_bytes": 474640412,
        "error_code": None,
        "error_message": None,
    }
    qi = QueryInfo.from_system_row(row)
    assert qi.query_id == "20260310_143549_08022_abc"
    assert qi.state == QueryState.RUNNING
    assert qi.cpu_time_millis == 19212
    assert qi.wall_time_millis == 53095
    assert qi.elapsed_time_millis == 6872


def test_query_info_truncated_sql():
    qi = QueryInfo(
        query_id="test",
        state=QueryState.RUNNING,
        query="SELECT " + "x, " * 1000 + "y FROM t",
        user="loki",
        source="test",
        created=datetime.now(),
    )
    assert qi.truncated_sql(80).endswith("...")
    assert len(qi.truncated_sql(80)) <= 80
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_models.py -v`
Expected: ImportError.

**Step 3: Implement models.py**

`src/trinops/models.py`:
```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class QueryState(str, Enum):
    QUEUED = "QUEUED"
    PLANNING = "PLANNING"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    FINISHING = "FINISHING"
    FINISHED = "FINISHED"
    FAILED = "FAILED"

    @property
    def is_terminal(self) -> bool:
        return self in (QueryState.FINISHED, QueryState.FAILED)


@dataclass
class QueryInfo:
    query_id: str
    state: QueryState
    query: str
    user: str
    source: Optional[str] = None
    created: Optional[datetime] = None
    started: Optional[datetime] = None
    ended: Optional[datetime] = None
    cpu_time_millis: int = 0
    wall_time_millis: int = 0
    queued_time_millis: int = 0
    elapsed_time_millis: int = 0
    peak_memory_bytes: int = 0
    cumulative_memory_bytes: int = 0
    processed_rows: int = 0
    processed_bytes: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def is_terminal(self) -> bool:
        return self.state.is_terminal

    def truncated_sql(self, max_len: int = 80) -> str:
        sql = self.query.replace("\n", " ").strip()
        if len(sql) <= max_len:
            return sql
        return sql[: max_len - 3] + "..."

    @classmethod
    def from_system_row(cls, row: dict) -> QueryInfo:
        return cls(
            query_id=row["query_id"],
            state=QueryState(row["state"]),
            query=row["query"],
            user=row["user"],
            source=row.get("source"),
            created=row.get("created"),
            started=row.get("started"),
            ended=row.get("end"),
            cpu_time_millis=int(row.get("cpu_time", 0) * 1000),
            wall_time_millis=int(row.get("wall_time", 0) * 1000),
            queued_time_millis=int(row.get("queued_time", 0) * 1000),
            elapsed_time_millis=int(row.get("elapsed_time", 0) * 1000),
            peak_memory_bytes=int(row.get("peak_memory_bytes", 0)),
            cumulative_memory_bytes=int(row.get("cumulative_memory", 0)),
            processed_rows=int(row.get("processed_rows", 0)),
            processed_bytes=int(row.get("processed_bytes", 0)),
            error_code=row.get("error_code"),
            error_message=row.get("error_message"),
        )
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_models.py -v`
Expected: All 4 tests PASS.

**Step 5: Commit**

```bash
git add src/trinops/models.py tests/test_models.py
git commit -m "feat: add QueryInfo model with system.runtime.queries parsing"
```

---

### Task 4: Auth Module

**Files:**
- Create: `src/trinops/auth.py`
- Create: `tests/test_auth.py`

**Step 1: Write the failing test**

`tests/test_auth.py`:
```python
import pytest
from unittest.mock import MagicMock, patch

from trinops.auth import build_auth, resolve_password
from trinops.config import ConnectionProfile


def test_build_auth_none():
    profile = ConnectionProfile(server="localhost:8080", auth="none", user="dev")
    auth = build_auth(profile)
    assert auth is None


def test_build_auth_basic():
    profile = ConnectionProfile(
        server="localhost:8080", auth="basic", user="loki", password="secret"
    )
    auth = build_auth(profile)
    from trino.auth import BasicAuthentication
    assert isinstance(auth, BasicAuthentication)


def test_build_auth_jwt():
    profile = ConnectionProfile(
        server="localhost:8080", auth="jwt", jwt_token="eyJhbGciOi..."
    )
    auth = build_auth(profile)
    from trino.auth import JWTAuthentication
    assert isinstance(auth, JWTAuthentication)


def test_build_auth_unknown_raises():
    profile = ConnectionProfile(server="localhost:8080", auth="magic")
    with pytest.raises(ValueError, match="Unknown auth method"):
        build_auth(profile)


def test_resolve_password_direct():
    profile = ConnectionProfile(password="direct_secret")
    assert resolve_password(profile) == "direct_secret"


def test_resolve_password_cmd():
    profile = ConnectionProfile(password_cmd="echo hunter2")
    pw = resolve_password(profile)
    assert pw == "hunter2"


def test_resolve_password_none():
    profile = ConnectionProfile()
    assert resolve_password(profile) is None
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_auth.py -v`
Expected: ImportError.

**Step 3: Implement auth.py**

`src/trinops/auth.py`:
```python
from __future__ import annotations

import subprocess
from typing import Optional

from trinops.config import ConnectionProfile


def resolve_password(profile: ConnectionProfile) -> Optional[str]:
    if profile.password is not None:
        return profile.password
    if profile.password_cmd is not None:
        result = subprocess.run(
            profile.password_cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        result.check_returncode()
        return result.stdout.strip()
    return None


def build_auth(profile: ConnectionProfile):
    method = profile.auth

    if method == "none":
        return None

    if method == "basic":
        from trino.auth import BasicAuthentication
        password = resolve_password(profile)
        if password is None:
            raise ValueError("basic auth requires password or password_cmd")
        return BasicAuthentication(profile.user, password)

    if method == "jwt":
        from trino.auth import JWTAuthentication
        token = profile.jwt_token
        if token is None:
            raise ValueError("jwt auth requires jwt_token")
        return JWTAuthentication(token)

    if method == "oauth2":
        from trino.auth import OAuth2Authentication
        return OAuth2Authentication()

    if method == "kerberos":
        from trino.auth import KerberosAuthentication
        return KerberosAuthentication()

    raise ValueError(f"Unknown auth method: {method!r}")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_auth.py -v`
Expected: All 7 tests PASS.

**Step 5: Commit**

```bash
git add src/trinops/auth.py tests/test_auth.py
git commit -m "feat: add auth module with basic/jwt/oauth2/kerberos support"
```

---

### Task 5: Client Module with Backend Abstraction

The client uses a `QueryBackend` protocol so the data source (currently SQL via `system.runtime.queries`) can be swapped to the HTTP API when Trino #22488 lands. The backend protocol defines `list_queries` and `get_query`; `TrinopsClient` delegates to whatever backend is configured.

**Files:**
- Create: `src/trinops/backend.py`
- Create: `src/trinops/client.py`
- Create: `tests/test_backend.py`
- Create: `tests/test_client.py`

**Step 1: Write the failing test for the backend protocol**

`tests/test_backend.py`:
```python
from datetime import datetime
from unittest.mock import MagicMock

from trinops.backend import QueryBackend, SqlQueryBackend
from trinops.models import QueryInfo, QueryState


SYSTEM_QUERY_COLUMNS = [
    "query_id", "state", "query", "user", "source",
    "created", "started", "end",
    "cpu_time", "wall_time", "queued_time", "elapsed_time",
    "peak_memory_bytes", "cumulative_memory", "processed_rows", "processed_bytes",
    "error_code", "error_message",
]

SAMPLE_ROW = (
    "20260310_143549_08022_abc",
    "RUNNING",
    "SELECT * FROM t",
    "loki",
    "trinops",
    datetime(2026, 3, 10, 14, 35, 49),
    datetime(2026, 3, 10, 14, 35, 50),
    None,
    19.212,
    53.095,
    0.1,
    6.872,
    8650480,
    50000000.0,
    34148040,
    474640412,
    None,
    None,
)


def _make_mock_cursor(rows, columns):
    cursor = MagicMock()
    cursor.description = [(col, None, None, None, None, None, None) for col in columns]
    cursor.fetchall.return_value = rows
    return cursor


def _make_mock_connection(cursor):
    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn


def test_sql_backend_is_query_backend():
    assert issubclass(SqlQueryBackend, QueryBackend.__class__) or isinstance(
        SqlQueryBackend.__new__(SqlQueryBackend), QueryBackend
    ) or hasattr(SqlQueryBackend, "list_queries")


def test_sql_backend_list_queries(monkeypatch):
    cursor = _make_mock_cursor([SAMPLE_ROW], SYSTEM_QUERY_COLUMNS)
    conn = _make_mock_connection(cursor)

    import trinops.backend
    monkeypatch.setattr(trinops.backend.trino.dbapi, "connect", lambda **kw: conn)

    from trinops.config import ConnectionProfile
    profile = ConnectionProfile(server="localhost:8080", auth="none", user="dev")
    backend = SqlQueryBackend(profile)
    queries = backend.list_queries()

    assert len(queries) == 1
    assert queries[0].query_id == "20260310_143549_08022_abc"
    assert queries[0].state == QueryState.RUNNING


def test_sql_backend_get_query(monkeypatch):
    cursor = _make_mock_cursor([SAMPLE_ROW], SYSTEM_QUERY_COLUMNS)
    conn = _make_mock_connection(cursor)

    import trinops.backend
    monkeypatch.setattr(trinops.backend.trino.dbapi, "connect", lambda **kw: conn)

    from trinops.config import ConnectionProfile
    profile = ConnectionProfile(server="localhost:8080", auth="none", user="dev")
    backend = SqlQueryBackend(profile)
    qi = backend.get_query("20260310_143549_08022_abc")

    assert qi is not None
    assert qi.query_id == "20260310_143549_08022_abc"


def test_sql_backend_get_query_not_found(monkeypatch):
    cursor = _make_mock_cursor([], SYSTEM_QUERY_COLUMNS)
    conn = _make_mock_connection(cursor)

    import trinops.backend
    monkeypatch.setattr(trinops.backend.trino.dbapi, "connect", lambda **kw: conn)

    from trinops.config import ConnectionProfile
    profile = ConnectionProfile(server="localhost:8080", auth="none", user="dev")
    backend = SqlQueryBackend(profile)
    qi = backend.get_query("nonexistent")

    assert qi is None
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_backend.py -v`
Expected: ImportError.

**Step 3: Implement backend.py**

`src/trinops/backend.py`:
```python
from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

import trino.dbapi

from trinops.auth import build_auth
from trinops.config import ConnectionProfile
from trinops.models import QueryInfo


@runtime_checkable
class QueryBackend(Protocol):
    def list_queries(self, state: Optional[str] = None) -> list[QueryInfo]: ...
    def get_query(self, query_id: str) -> Optional[QueryInfo]: ...
    def close(self) -> None: ...


_SYSTEM_QUERY_SQL = """\
SELECT
    query_id, state, query, "user", source,
    created, started, "end",
    cpu_time, wall_time, queued_time, elapsed_time,
    peak_memory_bytes, cumulative_memory, processed_rows, processed_bytes,
    error_code, error_message
FROM system.runtime.queries
"""


class SqlQueryBackend:
    """Queries system.runtime.queries via SQL. Current default backend."""

    def __init__(self, profile: ConnectionProfile) -> None:
        self._profile = profile
        self._conn = None

    def _get_connection(self):
        if self._conn is None:
            host, _, port_str = self._profile.server.partition(":")
            port = int(port_str) if port_str else 8080
            auth = build_auth(self._profile)
            self._conn = trino.dbapi.connect(
                host=host,
                port=port,
                user=self._profile.user,
                catalog=self._profile.catalog or "system",
                schema=self._profile.schema or "runtime",
                http_scheme=self._profile.scheme,
                auth=auth,
            )
        return self._conn

    def _query_to_dicts(self, cursor, rows) -> list[dict]:
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in rows]

    def list_queries(self, state: Optional[str] = None) -> list[QueryInfo]:
        conn = self._get_connection()
        cursor = conn.cursor()

        sql = _SYSTEM_QUERY_SQL
        params = []
        if state is not None:
            sql += " WHERE state = ?"
            params.append(state)
        sql += " ORDER BY created DESC"

        cursor.execute(sql, params if params else None)
        rows = cursor.fetchall()
        dicts = self._query_to_dicts(cursor, rows)
        return [QueryInfo.from_system_row(row) for row in dicts]

    def get_query(self, query_id: str) -> Optional[QueryInfo]:
        conn = self._get_connection()
        cursor = conn.cursor()

        sql = _SYSTEM_QUERY_SQL + " WHERE query_id = ?"
        cursor.execute(sql, [query_id])
        rows = cursor.fetchall()
        if not rows:
            return None
        dicts = self._query_to_dicts(cursor, rows)
        return QueryInfo.from_system_row(dicts[0])

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None


# Future: HttpQueryBackend will implement QueryBackend using /ui/api/query/
# when Trino #22488 lands. Drop-in replacement for SqlQueryBackend.
```

**Step 4: Write client test**

`tests/test_client.py`:
```python
from unittest.mock import MagicMock
from datetime import datetime

from trinops.client import TrinopsClient
from trinops.models import QueryInfo, QueryState


SAMPLE_QUERY = QueryInfo(
    query_id="20260310_143549_08022_abc",
    state=QueryState.RUNNING,
    query="SELECT * FROM t",
    user="loki",
    created=datetime(2026, 3, 10, 14, 35, 49),
)


def test_client_delegates_to_backend():
    backend = MagicMock()
    backend.list_queries.return_value = [SAMPLE_QUERY]

    client = TrinopsClient(backend=backend)
    queries = client.list_queries()

    assert len(queries) == 1
    assert queries[0].query_id == "20260310_143549_08022_abc"
    backend.list_queries.assert_called_once_with(state=None)


def test_client_passes_state_filter():
    backend = MagicMock()
    backend.list_queries.return_value = [SAMPLE_QUERY]

    client = TrinopsClient(backend=backend)
    client.list_queries(state="RUNNING")
    backend.list_queries.assert_called_once_with(state="RUNNING")


def test_client_get_query():
    backend = MagicMock()
    backend.get_query.return_value = SAMPLE_QUERY

    client = TrinopsClient(backend=backend)
    qi = client.get_query("20260310_143549_08022_abc")
    assert qi.query_id == "20260310_143549_08022_abc"


def test_client_from_profile():
    """TrinopsClient.from_profile creates a SqlQueryBackend by default."""
    from trinops.config import ConnectionProfile
    from trinops.backend import SqlQueryBackend

    profile = ConnectionProfile(server="localhost:8080", auth="none", user="dev")
    client = TrinopsClient.from_profile(profile)
    assert isinstance(client._backend, SqlQueryBackend)
```

**Step 5: Implement client.py**

`src/trinops/client.py`:
```python
from __future__ import annotations

from typing import Optional

from trinops.backend import QueryBackend, SqlQueryBackend
from trinops.config import ConnectionProfile
from trinops.models import QueryInfo


class TrinopsClient:
    def __init__(self, backend: QueryBackend) -> None:
        self._backend = backend

    @classmethod
    def from_profile(cls, profile: ConnectionProfile) -> TrinopsClient:
        backend = SqlQueryBackend(profile)
        return cls(backend=backend)

    def list_queries(self, state: Optional[str] = None) -> list[QueryInfo]:
        return self._backend.list_queries(state=state)

    def get_query(self, query_id: str) -> Optional[QueryInfo]:
        return self._backend.get_query(query_id)

    def close(self) -> None:
        self._backend.close()
```

**Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_backend.py tests/test_client.py -v`
Expected: All 8 tests PASS.

**Step 7: Commit**

```bash
git add src/trinops/backend.py src/trinops/client.py tests/test_backend.py tests/test_client.py
git commit -m "feat: add QueryBackend protocol with SqlQueryBackend and TrinopsClient"
```

---

### Task 6: Fix QueryPoller to Use Correct API

The existing poller hits `/v1/query/{queryId}` which doesn't exist. Fix it to poll query stats from the cursor's own stats property during execution.

**Files:**
- Modify: `src/trinops/progress/poller.py`
- Modify: `tests/test_poller.py`

**Step 1: Write the failing test for the new cursor-based poller**

Add to `tests/test_poller.py`:
```python
def test_cursor_poller_delivers_stats():
    """Poller can poll stats from a cursor's stats property."""
    from trinops.progress.poller import CursorPoller
    from trinops.progress.stats import QueryStats

    mock_cursor = MagicMock()
    # Simulate cursor.stats returning progressively updated stats
    stats_sequence = [
        {
            "state": "RUNNING", "queued": False, "scheduled": True, "nodes": 4,
            "totalSplits": 100, "queuedSplits": 20, "runningSplits": 30,
            "completedSplits": 50, "cpuTimeMillis": 3000, "wallTimeMillis": 5000,
            "queuedTimeMillis": 100, "elapsedTimeMillis": 2000,
            "processedRows": 2000000, "processedBytes": 80000000,
            "physicalInputBytes": 80000000, "peakMemoryBytes": 5000000,
            "spilledBytes": 0,
        },
        {
            "state": "FINISHED", "queued": False, "scheduled": True, "nodes": 4,
            "totalSplits": 100, "queuedSplits": 0, "runningSplits": 0,
            "completedSplits": 100, "cpuTimeMillis": 5000, "wallTimeMillis": 8000,
            "queuedTimeMillis": 100, "elapsedTimeMillis": 3000,
            "processedRows": 5000000, "processedBytes": 100000000,
            "physicalInputBytes": 100000000, "peakMemoryBytes": 4000000,
            "spilledBytes": 0,
        },
    ]
    call_count = [0]
    def get_stats():
        idx = min(call_count[0], len(stats_sequence) - 1)
        call_count[0] += 1
        return stats_sequence[idx]

    type(mock_cursor).stats = PropertyMock(side_effect=get_stats)

    received = []
    poller = CursorPoller(cursor=mock_cursor, interval=0.1)
    poller.add_callback(lambda s: received.append(s))
    poller.start()
    poller.wait(timeout=5)

    assert len(received) >= 2
    assert received[-1].state == "FINISHED"
    assert not poller.is_alive()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_poller.py::test_cursor_poller_delivers_stats -v`
Expected: ImportError — CursorPoller not defined.

**Step 3: Add CursorPoller to poller.py**

Add a `CursorPoller` class that polls `cursor.stats` directly instead of making HTTP calls. Keep the existing `QueryPoller` for backward compatibility (it's used in tests). Add `CursorPoller` alongside it:

```python
class CursorPoller:
    """Polls a trino cursor's stats property in a background thread."""

    def __init__(
        self,
        cursor,
        interval: float = 1.0,
    ) -> None:
        self._cursor = cursor
        self._interval = interval
        self._callbacks: list[Callable[[QueryStats], None]] = []
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._done_event = threading.Event()
        self._last_stats: QueryStats | None = None

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
        if self._thread is not None:
            self._thread.join(timeout=2)

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def last_stats(self) -> QueryStats | None:
        return self._last_stats

    def _poll_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    raw_stats = self._cursor.stats
                    if raw_stats is None:
                        self._stop_event.wait(timeout=self._interval)
                        continue
                    stats = parse_stats(raw_stats)
                    self._last_stats = stats

                    for callback in self._callbacks:
                        try:
                            callback(stats)
                        except Exception:
                            logger.exception("Display callback error")

                    if stats.is_terminal:
                        return

                except Exception:
                    logger.exception("Error polling cursor stats")
                    return

                self._stop_event.wait(timeout=self._interval)
        finally:
            self._done_event.set()
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_poller.py -v`
Expected: All 5 tests PASS (4 existing + 1 new).

**Step 5: Commit**

```bash
git add src/trinops/progress/poller.py tests/test_poller.py
git commit -m "feat: add CursorPoller that polls cursor.stats directly"
```

---

### Task 7: Update TrinoProgress to Use CursorPoller

**Files:**
- Modify: `src/trinops/progress/progress.py`
- Modify: `tests/test_progress.py`

**Step 1: Write the failing test**

Add to `tests/test_progress.py`:
```python
def test_context_manager_uses_cursor_stats():
    """TrinoProgress in cursor mode polls cursor.stats, not HTTP."""
    cursor = MagicMock()
    cursor.query_id = "test_cursor_stats"
    cursor.connection = MagicMock(spec=["host", "port", "http_scheme", "auth"])

    stats_sequence = [
        {
            "state": "RUNNING", "queued": False, "scheduled": True, "nodes": 4,
            "totalSplits": 100, "queuedSplits": 20, "runningSplits": 30,
            "completedSplits": 50, "cpuTimeMillis": 3000, "wallTimeMillis": 5000,
            "queuedTimeMillis": 100, "elapsedTimeMillis": 2000,
            "processedRows": 2000000, "processedBytes": 80000000,
            "physicalInputBytes": 80000000, "peakMemoryBytes": 5000000,
            "spilledBytes": 0,
        },
        {
            "state": "FINISHED", "queued": False, "scheduled": True, "nodes": 4,
            "totalSplits": 100, "queuedSplits": 0, "runningSplits": 0,
            "completedSplits": 100, "cpuTimeMillis": 5000, "wallTimeMillis": 8000,
            "queuedTimeMillis": 100, "elapsedTimeMillis": 3000,
            "processedRows": 5000000, "processedBytes": 100000000,
            "physicalInputBytes": 100000000, "peakMemoryBytes": 4000000,
            "spilledBytes": 0,
        },
    ]
    call_count = [0]
    def get_stats():
        idx = min(call_count[0], len(stats_sequence) - 1)
        call_count[0] += 1
        return stats_sequence[idx]

    type(cursor).stats = PropertyMock(side_effect=get_stats)

    with TrinoProgress(cursor, display="stderr", interval=0.1) as tp:
        tp.execute("SELECT 1")

    assert tp.last_stats is not None
    assert tp.last_stats.state == "FINISHED"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_progress.py::test_context_manager_uses_cursor_stats -v`
Expected: FAIL (still uses old HTTP-based QueryPoller).

**Step 3: Update progress.py to use CursorPoller in cursor mode**

In `_start_poller`, check if in cursor mode and use `CursorPoller` instead of `QueryPoller`:

```python
from trinops.progress.poller import QueryPoller, CursorPoller

# In _start_poller:
def _start_poller(self) -> None:
    if self._mode == "cursor" and self._cursor is not None:
        self._poller = CursorPoller(
            cursor=self._cursor,
            interval=self._interval,
        )
    else:
        self._poller = QueryPoller.from_connection(
            self._connection,
            query_id=self._query_id,
            interval=self._interval,
            max_failures=self._max_failures,
        )
    for display in self._displays:
        self._poller.add_callback(display.on_stats)
    self._poller.start()
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_progress.py -v`
Expected: All tests PASS.

**Step 5: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS.

**Step 6: Commit**

```bash
git add src/trinops/progress/progress.py tests/test_progress.py
git commit -m "feat: use CursorPoller in cursor mode for correct API usage"
```

---

### Task 8: CLI — Core Commands

**Files:**
- Create: `src/trinops/cli/__init__.py`
- Create: `src/trinops/cli/commands.py`
- Create: `src/trinops/cli/formatting.py`
- Create: `tests/test_cli.py`

**Step 1: Write the failing test**

`tests/test_cli.py`:
```python
from datetime import datetime
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from trinops.cli import app
from trinops.models import QueryInfo, QueryState


runner = CliRunner()

SAMPLE_QUERIES = [
    QueryInfo(
        query_id="20260310_143549_08022_abc",
        state=QueryState.RUNNING,
        query="SELECT * FROM big_table WHERE id > 100",
        user="loki",
        source="trinops",
        created=datetime(2026, 3, 10, 14, 35, 49),
        cpu_time_millis=19212,
        elapsed_time_millis=6872,
        processed_rows=34148040,
        processed_bytes=474640412,
        peak_memory_bytes=8650480,
    ),
    QueryInfo(
        query_id="20260310_142000_07000_def",
        state=QueryState.FINISHED,
        query="SELECT count(*) FROM users",
        user="admin",
        source="trino-cli",
        created=datetime(2026, 3, 10, 14, 20, 0),
        cpu_time_millis=500,
        elapsed_time_millis=1200,
        processed_rows=1,
        processed_bytes=8,
        peak_memory_bytes=100000,
    ),
]


@patch("trinops.cli.commands._build_client")
def test_queries_table_output(mock_build):
    client = MagicMock()
    client.list_queries.return_value = SAMPLE_QUERIES
    mock_build.return_value = client

    result = runner.invoke(app, ["queries", "--server", "localhost:8080"])
    assert result.exit_code == 0
    assert "20260310_143549" in result.output
    assert "RUNNING" in result.output
    assert "loki" in result.output


@patch("trinops.cli.commands._build_client")
def test_queries_json_output(mock_build):
    client = MagicMock()
    client.list_queries.return_value = SAMPLE_QUERIES
    mock_build.return_value = client

    result = runner.invoke(app, ["queries", "--server", "localhost:8080", "--json"])
    assert result.exit_code == 0
    import json
    lines = [l for l in result.output.strip().split("\n") if l]
    data = [json.loads(l) for l in lines]
    assert len(data) == 2
    assert data[0]["query_id"] == "20260310_143549_08022_abc"


@patch("trinops.cli.commands._build_client")
def test_queries_filter_state(mock_build):
    client = MagicMock()
    client.list_queries.return_value = [SAMPLE_QUERIES[0]]
    mock_build.return_value = client

    result = runner.invoke(app, ["queries", "--server", "localhost:8080", "--state", "RUNNING"])
    assert result.exit_code == 0
    client.list_queries.assert_called_once_with(state="RUNNING")


@patch("trinops.cli.commands._build_client")
def test_query_detail(mock_build):
    client = MagicMock()
    client.get_query.return_value = SAMPLE_QUERIES[0]
    mock_build.return_value = client

    result = runner.invoke(app, ["query", "20260310_143549_08022_abc", "--server", "localhost:8080"])
    assert result.exit_code == 0
    assert "20260310_143549_08022_abc" in result.output
    assert "SELECT * FROM big_table" in result.output


@patch("trinops.cli.commands._build_client")
def test_query_detail_json(mock_build):
    client = MagicMock()
    client.get_query.return_value = SAMPLE_QUERIES[0]
    mock_build.return_value = client

    result = runner.invoke(app, ["query", "20260310_143549_08022_abc", "--server", "localhost:8080", "--json"])
    assert result.exit_code == 0
    import json
    data = json.loads(result.output.strip())
    assert data["query_id"] == "20260310_143549_08022_abc"


@patch("trinops.cli.commands._build_client")
def test_query_not_found(mock_build):
    client = MagicMock()
    client.get_query.return_value = None
    mock_build.return_value = client

    result = runner.invoke(app, ["query", "nonexistent", "--server", "localhost:8080"])
    assert result.exit_code != 0 or "not found" in result.output.lower()
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: ImportError.

**Step 3: Implement CLI**

`src/trinops/cli/__init__.py`:
```python
from trinops.cli.commands import app

__all__ = ["app"]
```

`src/trinops/cli/formatting.py`:
```python
from __future__ import annotations

import dataclasses
import json
from typing import Sequence

from rich.console import Console
from rich.table import Table

from trinops.models import QueryInfo


console = Console()


def format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def format_time_millis(millis: int) -> str:
    seconds = millis / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"


def print_queries_table(queries: Sequence[QueryInfo]) -> None:
    table = Table()
    table.add_column("Query ID", style="cyan")
    table.add_column("State")
    table.add_column("User")
    table.add_column("Elapsed")
    table.add_column("Rows")
    table.add_column("Memory")
    table.add_column("SQL")

    for q in queries:
        state_style = {
            "RUNNING": "bold blue",
            "QUEUED": "yellow",
            "PLANNING": "yellow",
            "FINISHED": "green",
            "FAILED": "bold red",
        }.get(q.state.value, "")

        table.add_row(
            q.query_id,
            f"[{state_style}]{q.state.value}[/]",
            q.user,
            format_time_millis(q.elapsed_time_millis),
            f"{q.processed_rows:,}",
            format_bytes(q.peak_memory_bytes),
            q.truncated_sql(60),
        )

    console.print(table)


def print_query_detail(q: QueryInfo) -> None:
    console.print(f"[bold]Query ID:[/] {q.query_id}")
    console.print(f"[bold]State:[/]    {q.state.value}")
    console.print(f"[bold]User:[/]     {q.user}")
    if q.source:
        console.print(f"[bold]Source:[/]   {q.source}")
    console.print(f"[bold]Elapsed:[/]  {format_time_millis(q.elapsed_time_millis)}")
    console.print(f"[bold]CPU:[/]      {format_time_millis(q.cpu_time_millis)}")
    console.print(f"[bold]Rows:[/]     {q.processed_rows:,}")
    console.print(f"[bold]Data:[/]     {format_bytes(q.processed_bytes)}")
    console.print(f"[bold]Memory:[/]   {format_bytes(q.peak_memory_bytes)}")
    if q.error_message:
        console.print(f"[bold red]Error:[/]   {q.error_message}")
    console.print(f"\n[bold]SQL:[/]\n{q.query}")


def print_queries_json(queries: Sequence[QueryInfo]) -> None:
    for q in queries:
        print(json.dumps(dataclasses.asdict(q), default=str))


def print_query_json(q: QueryInfo) -> None:
    print(json.dumps(dataclasses.asdict(q), default=str))
```

`src/trinops/cli/commands.py`:
```python
from __future__ import annotations

from typing import Optional

import typer

from trinops.client import TrinopsClient
from trinops.config import ConnectionProfile, load_config

app = typer.Typer(name="trinops", help="Trino query monitoring tool")


def _build_client(
    server: Optional[str] = None,
    profile: Optional[str] = None,
    user: Optional[str] = None,
) -> TrinopsClient:
    config = load_config()
    if server:
        cp = ConnectionProfile(server=server, auth="none", user=user or "trinops")
    else:
        env_profile = ConnectionProfile.from_env()
        if env_profile is not None:
            cp = env_profile
        else:
            cp = config.get_profile(profile)
    return TrinopsClient.from_profile(cp)


@app.command()
def queries(
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
    state: Optional[str] = typer.Option(None, help="Filter by query state"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
):
    """List running and recent queries."""
    client = _build_client(server=server, profile=profile, user=user)
    results = client.list_queries(state=state)

    if json:
        from trinops.cli.formatting import print_queries_json
        print_queries_json(results)
    else:
        from trinops.cli.formatting import print_queries_table
        print_queries_table(results)


@app.command()
def query(
    query_id: str = typer.Argument(help="Trino query ID"),
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    watch: bool = typer.Option(False, "--watch", help="Poll until query finishes"),
):
    """Show details for a specific query."""
    client = _build_client(server=server, profile=profile, user=user)
    qi = client.get_query(query_id)

    if qi is None:
        typer.echo(f"Query not found: {query_id}", err=True)
        raise typer.Exit(1)

    if json:
        from trinops.cli.formatting import print_query_json
        print_query_json(qi)
    else:
        from trinops.cli.formatting import print_query_detail
        print_query_detail(qi)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: All 6 tests PASS.

**Step 5: Commit**

```bash
git add src/trinops/cli/ tests/test_cli.py
git commit -m "feat: add CLI with queries and query commands"
```

---

### Task 9: CLI — Auth and Config Commands

**Files:**
- Modify: `src/trinops/cli/commands.py`
- Create: `tests/test_cli_config.py`

**Step 1: Write the failing test**

`tests/test_cli_config.py`:
```python
import tempfile
import os

from typer.testing import CliRunner
from trinops.cli import app

runner = CliRunner()


def test_config_show_no_config():
    result = runner.invoke(app, ["config", "show", "--config-path", "/tmp/nonexistent.toml"])
    assert result.exit_code == 0
    assert "no config" in result.output.lower() or "not found" in result.output.lower()


def test_config_show_with_config():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write('[default]\nserver = "localhost:8080"\nuser = "dev"\nauth = "none"\n')
        f.flush()
        result = runner.invoke(app, ["config", "show", "--config-path", f.name])

    os.unlink(f.name)
    assert result.exit_code == 0
    assert "localhost:8080" in result.output


def test_auth_status_no_config():
    result = runner.invoke(app, ["auth", "status", "--config-path", "/tmp/nonexistent.toml"])
    assert result.exit_code == 0
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli_config.py -v`
Expected: Fails because config/auth subcommands don't exist.

**Step 3: Add config and auth subcommands**

Add to `src/trinops/cli/commands.py`:

```python
config_app = typer.Typer(name="config", help="Manage trinops configuration")
auth_app = typer.Typer(name="auth", help="Manage authentication")
app.add_typer(config_app, name="config")
app.add_typer(auth_app, name="auth")


@config_app.command("show")
def config_show(
    config_path: Optional[str] = typer.Option(None, "--config-path", help="Config file path"),
):
    """Show current configuration."""
    from trinops.config import load_config, DEFAULT_CONFIG_PATH
    from pathlib import Path

    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        typer.echo(f"No config file found at {path}")
        return

    config = load_config(path)
    typer.echo(f"Config: {path}")
    typer.echo(f"Default server: {config.default.server}")
    typer.echo(f"Default user: {config.default.user}")
    typer.echo(f"Default auth: {config.default.auth}")
    if config.profiles:
        typer.echo(f"Profiles: {', '.join(config.profiles.keys())}")


@config_app.command("init")
def config_init(
    config_path: Optional[str] = typer.Option(None, "--config-path", help="Config file path"),
):
    """Create a new config file interactively."""
    from trinops.config import DEFAULT_CONFIG_PATH
    from pathlib import Path

    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if path.exists():
        typer.confirm(f"{path} already exists. Overwrite?", abort=True)

    server = typer.prompt("Trino server (host:port)")
    scheme = typer.prompt("Scheme", default="https")
    user = typer.prompt("User")
    auth = typer.prompt("Auth method (none/basic/jwt/oauth2/kerberos)", default="none")

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(f'[default]\nserver = "{server}"\nscheme = "{scheme}"\nuser = "{user}"\nauth = "{auth}"\n')

    typer.echo(f"Config written to {path}")


@auth_app.command("status")
def auth_status(
    config_path: Optional[str] = typer.Option(None, "--config-path", help="Config file path"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
):
    """Show current authentication state."""
    from trinops.config import load_config
    from pathlib import Path

    path = Path(config_path) if config_path else None
    config = load_config(path)
    cp = config.get_profile(profile)
    typer.echo(f"Auth method: {cp.auth}")
    typer.echo(f"User: {cp.user}")
    if cp.auth == "oauth2":
        token_path = Path.home() / ".config" / "trinops" / "tokens"
        if token_path.exists():
            typer.echo("OAuth2 tokens cached: yes")
        else:
            typer.echo("OAuth2 tokens cached: no (run 'trinops auth login')")


@auth_app.command("login")
def auth_login(
    config_path: Optional[str] = typer.Option(None, "--config-path", help="Config file path"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
):
    """Run OAuth2 authentication flow and cache token."""
    from trinops.config import load_config
    from trinops.auth import build_auth
    from pathlib import Path

    path = Path(config_path) if config_path else None
    config = load_config(path)
    cp = config.get_profile(profile)

    if cp.auth != "oauth2":
        typer.echo(f"Profile uses auth method '{cp.auth}', not oauth2")
        raise typer.Exit(1)

    typer.echo("Starting OAuth2 flow...")
    auth = build_auth(cp)
    typer.echo("Authentication successful. Token cached.")
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli_config.py -v`
Expected: All 3 tests PASS.

**Step 5: Commit**

```bash
git add src/trinops/cli/commands.py tests/test_cli_config.py
git commit -m "feat: add config and auth CLI subcommands"
```

---

### Task 10: TUI Dashboard

**Files:**
- Create: `src/trinops/tui/__init__.py`
- Create: `src/trinops/tui/app.py`
- Create: `tests/test_tui.py`

**Step 1: Write the failing test**

`tests/test_tui.py`:
```python
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

from trinops.models import QueryInfo, QueryState


SAMPLE_QUERIES = [
    QueryInfo(
        query_id="20260310_143549_08022_abc",
        state=QueryState.RUNNING,
        query="SELECT * FROM big_table",
        user="loki",
        source="trinops",
        created=datetime(2026, 3, 10, 14, 35, 49),
        cpu_time_millis=19212,
        elapsed_time_millis=6872,
        processed_rows=34148040,
        processed_bytes=474640412,
        peak_memory_bytes=8650480,
    ),
]


@pytest.mark.asyncio
async def test_tui_app_creates():
    from trinops.tui.app import TrinopsApp
    from trinops.config import ConnectionProfile

    profile = ConnectionProfile(server="localhost:8080", auth="none", user="dev")
    app = TrinopsApp(profile=profile)
    assert app is not None


@pytest.mark.asyncio
async def test_tui_app_has_query_table():
    from trinops.tui.app import TrinopsApp
    from trinops.config import ConnectionProfile

    profile = ConnectionProfile(server="localhost:8080", auth="none", user="dev")
    app = TrinopsApp(profile=profile)

    async with app.run_test() as pilot:
        # App should have a data table for queries
        assert app.query_for_one("#query-table") is not None
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tui.py -v`
Expected: ImportError.

Note: Add `pytest-asyncio` to dev dependencies.

**Step 3: Implement TUI app**

`src/trinops/tui/__init__.py`:
```python
"""trinops TUI dashboard."""
```

`src/trinops/tui/app.py`:
```python
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import DataTable, Footer, Header, Static
from textual.timer import Timer

from trinops.client import TrinopsClient
from trinops.config import ConnectionProfile
from trinops.models import QueryInfo


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
    return f"{minutes / 60:.1f}h"


class QueryDetail(Static):
    def update_query(self, qi: QueryInfo | None) -> None:
        if qi is None:
            self.update("Select a query to view details")
            return
        lines = [
            f"Query ID: {qi.query_id}",
            f"State:    {qi.state.value}",
            f"User:     {qi.user}",
            f"Elapsed:  {_format_time(qi.elapsed_time_millis)}",
            f"CPU:      {_format_time(qi.cpu_time_millis)}",
            f"Rows:     {qi.processed_rows:,}",
            f"Data:     {_format_bytes(qi.processed_bytes)}",
            f"Memory:   {_format_bytes(qi.peak_memory_bytes)}",
            "",
            qi.query,
        ]
        if qi.error_message:
            lines.insert(-1, f"Error:    {qi.error_message}")
        self.update("\n".join(lines))


class TrinopsApp(App):
    CSS = """
    #query-table {
        height: 1fr;
    }
    #detail {
        height: auto;
        max-height: 40%;
        border-top: solid green;
        padding: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("f", "filter", "Filter"),
        ("r", "refresh", "Refresh"),
        ("/", "search", "Search"),
    ]

    def __init__(self, profile: ConnectionProfile, interval: float = 1.0, **kwargs):
        super().__init__(**kwargs)
        self._profile = profile
        self._interval = interval
        self._client: TrinopsClient | None = None
        self._queries: list[QueryInfo] = []
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            DataTable(id="query-table"),
            QueryDetail(id="detail"),
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#query-table", DataTable)
        table.add_columns("Query ID", "State", "User", "Elapsed", "Rows", "Memory", "SQL")
        table.cursor_type = "row"
        self._refresh_timer = self.set_interval(self._interval, self._refresh_queries)
        self._refresh_queries()

    def _refresh_queries(self) -> None:
        if self._client is None:
            self._client = TrinopsClient.from_profile(self._profile)

        try:
            self._queries = self._client.list_queries()
        except Exception:
            return

        table = self.query_one("#query-table", DataTable)
        table.clear()
        for qi in self._queries:
            table.add_row(
                qi.query_id,
                qi.state.value,
                qi.user,
                _format_time(qi.elapsed_time_millis),
                f"{qi.processed_rows:,}",
                _format_bytes(qi.peak_memory_bytes),
                qi.truncated_sql(60),
                key=qi.query_id,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        detail = self.query_one("#detail", QueryDetail)
        for qi in self._queries:
            if qi.query_id == str(event.row_key.value):
                detail.update_query(qi)
                return
        detail.update_query(None)

    def action_refresh(self) -> None:
        self._refresh_queries()

    def action_filter(self) -> None:
        pass  # v2: filter dialog

    def action_search(self) -> None:
        pass  # v2: search dialog
```

Add `trinops tui` subcommand to `src/trinops/cli/commands.py`:

```python
@app.command()
def tui(
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
    interval: float = typer.Option(1.0, help="Refresh interval in seconds"),
):
    """Launch interactive TUI dashboard."""
    from trinops.tui.app import TrinopsApp

    cp = _build_profile(server=server, profile=profile, user=user)
    app = TrinopsApp(profile=cp, interval=interval)
    app.run()
```

Also refactor `_build_client` to expose `_build_profile` that returns a `ConnectionProfile`:

```python
def _build_profile(
    server: Optional[str] = None,
    profile: Optional[str] = None,
    user: Optional[str] = None,
) -> ConnectionProfile:
    config = load_config()
    if server:
        return ConnectionProfile(server=server, auth="none", user=user or "trinops")
    env_profile = ConnectionProfile.from_env()
    if env_profile is not None:
        return env_profile
    return config.get_profile(profile)


def _build_client(
    server: Optional[str] = None,
    profile: Optional[str] = None,
    user: Optional[str] = None,
) -> TrinopsClient:
    cp = _build_profile(server=server, profile=profile, user=user)
    return TrinopsClient.from_profile(cp)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tui.py -v`
Expected: All 2 tests PASS.

**Step 5: Commit**

```bash
git add src/trinops/tui/ src/trinops/cli/commands.py tests/test_tui.py pyproject.toml
git commit -m "feat: add Textual TUI dashboard with query list and detail view"
```

---

### Task 11: MCP Server

**Files:**
- Create: `src/trinops/mcp/__init__.py`
- Create: `src/trinops/mcp/server.py`
- Create: `tests/test_mcp.py`

**Step 1: Write the failing test**

`tests/test_mcp.py`:
```python
from datetime import datetime
from unittest.mock import MagicMock, patch

from trinops.mcp.server import list_tools, handle_tool_call
from trinops.models import QueryInfo, QueryState


SAMPLE_QUERIES = [
    QueryInfo(
        query_id="20260310_143549_08022_abc",
        state=QueryState.RUNNING,
        query="SELECT * FROM big_table",
        user="loki",
        source="trinops",
        created=datetime(2026, 3, 10, 14, 35, 49),
        cpu_time_millis=19212,
        elapsed_time_millis=6872,
        processed_rows=34148040,
        processed_bytes=474640412,
        peak_memory_bytes=8650480,
    ),
]


def test_list_tools():
    tools = list_tools()
    names = [t["name"] for t in tools]
    assert "list_queries" in names
    assert "get_query" in names
    assert "get_cluster_stats" in names


def test_handle_list_queries():
    client = MagicMock()
    client.list_queries.return_value = SAMPLE_QUERIES

    result = handle_tool_call("list_queries", {}, client)
    assert len(result) == 1
    assert result[0]["query_id"] == "20260310_143549_08022_abc"


def test_handle_list_queries_with_state():
    client = MagicMock()
    client.list_queries.return_value = SAMPLE_QUERIES

    handle_tool_call("list_queries", {"state": "RUNNING"}, client)
    client.list_queries.assert_called_once_with(state="RUNNING")


def test_handle_get_query():
    client = MagicMock()
    client.get_query.return_value = SAMPLE_QUERIES[0]

    result = handle_tool_call("get_query", {"query_id": "20260310_143549_08022_abc"}, client)
    assert result["query_id"] == "20260310_143549_08022_abc"


def test_handle_get_query_not_found():
    client = MagicMock()
    client.get_query.return_value = None

    result = handle_tool_call("get_query", {"query_id": "nonexistent"}, client)
    assert "error" in result


def test_handle_unknown_tool():
    client = MagicMock()
    result = handle_tool_call("unknown_tool", {}, client)
    assert "error" in result
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_mcp.py -v`
Expected: ImportError.

**Step 3: Implement MCP server**

`src/trinops/mcp/__init__.py`:
```python
"""trinops MCP server."""
```

`src/trinops/mcp/server.py`:
```python
from __future__ import annotations

import dataclasses
import json
import sys
from typing import Any, Optional

from trinops.client import TrinopsClient
from trinops.models import QueryInfo


_TOOLS = [
    {
        "name": "list_queries",
        "description": "List running and recent Trino queries",
        "inputSchema": {
            "type": "object",
            "properties": {
                "state": {
                    "type": "string",
                    "description": "Filter by query state (QUEUED, RUNNING, FINISHED, FAILED)",
                },
            },
        },
    },
    {
        "name": "get_query",
        "description": "Get details for a specific Trino query by ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query_id": {
                    "type": "string",
                    "description": "The Trino query ID",
                },
            },
            "required": ["query_id"],
        },
    },
    {
        "name": "get_cluster_stats",
        "description": "Get aggregate cluster statistics from running queries",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def list_tools() -> list[dict]:
    return _TOOLS


def _query_to_dict(qi: QueryInfo) -> dict:
    return dataclasses.asdict(qi)


def handle_tool_call(
    tool_name: str,
    arguments: dict[str, Any],
    client: TrinopsClient,
) -> Any:
    if tool_name == "list_queries":
        state = arguments.get("state")
        queries = client.list_queries(state=state)
        return [_query_to_dict(q) for q in queries]

    if tool_name == "get_query":
        query_id = arguments["query_id"]
        qi = client.get_query(query_id)
        if qi is None:
            return {"error": f"Query not found: {query_id}"}
        return _query_to_dict(qi)

    if tool_name == "get_cluster_stats":
        queries = client.list_queries()
        running = [q for q in queries if q.state.value == "RUNNING"]
        queued = [q for q in queries if q.state.value == "QUEUED"]
        return {
            "total_queries": len(queries),
            "running_queries": len(running),
            "queued_queries": len(queued),
            "total_rows_processed": sum(q.processed_rows for q in running),
            "total_peak_memory": sum(q.peak_memory_bytes for q in running),
        }

    return {"error": f"Unknown tool: {tool_name}"}


def run_stdio_server(client: TrinopsClient) -> None:
    """Run a simple JSON-RPC stdio MCP server."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = request.get("method")
        req_id = request.get("id")

        if method == "tools/list":
            response = {"jsonrpc": "2.0", "id": req_id, "result": {"tools": list_tools()}}
        elif method == "tools/call":
            params = request.get("params", {})
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = handle_tool_call(tool_name, arguments, client)
            content = json.dumps(result, default=str)
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"content": [{"type": "text", "text": content}]},
            }
        else:
            response = {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"},
            }

        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()
```

Add `trinops mcp serve` subcommand to `src/trinops/cli/commands.py`:

```python
mcp_app = typer.Typer(name="mcp", help="MCP server")
app.add_typer(mcp_app, name="mcp")


@mcp_app.command("serve")
def mcp_serve(
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
):
    """Start MCP server on stdio."""
    from trinops.mcp.server import run_stdio_server

    client = _build_client(server=server, profile=profile, user=user)
    run_stdio_server(client)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_mcp.py -v`
Expected: All 6 tests PASS.

**Step 5: Commit**

```bash
git add src/trinops/mcp/ src/trinops/cli/commands.py tests/test_mcp.py
git commit -m "feat: add read-only MCP server with list_queries/get_query/get_cluster_stats"
```

---

### Task 12: Final Integration and Verification

**Files:**
- Modify: `src/trinops/__init__.py` (ensure all public exports)
- Create: `tests/test_trinops_integration.py`

**Step 1: Update top-level __init__.py**

`src/trinops/__init__.py`:
```python
from trinops.progress.stats import QueryStats, StageStats
from trinops.progress.progress import TrinoProgress
from trinops.models import QueryInfo, QueryState

__all__ = [
    "TrinoProgress",
    "QueryStats",
    "StageStats",
    "QueryInfo",
    "QueryState",
]

__version__ = "0.1.0"
```

**Step 2: Write integration test**

`tests/test_trinops_integration.py`:
```python
"""Verify all public imports work."""


def test_core_imports():
    from trinops import TrinoProgress, QueryStats, StageStats, QueryInfo, QueryState
    assert TrinoProgress is not None
    assert QueryStats is not None
    assert QueryState.RUNNING.value == "RUNNING"


def test_progress_imports():
    from trinops.progress import TrinoProgress, Display, StderrDisplay, WebDisplay
    assert TrinoProgress is not None
    assert Display is not None


def test_cli_importable():
    from trinops.cli import app
    assert app is not None


def test_version():
    import trinops
    assert trinops.__version__ == "0.1.0"
```

**Step 3: Run full test suite with coverage**

Run: `uv run pytest tests/ -v --cov=trinops --cov-report=term-missing`
Expected: All tests PASS.

**Step 4: Verify package builds**

Run: `uv build`
Expected: Produces wheel and sdist.

**Step 5: Verify CLI entry point**

Run: `uv run trinops --help`
Expected: Shows help with queries, query, tui, config, auth, mcp subcommands.

**Step 6: Commit**

```bash
git add -A
git commit -m "feat: finalize trinops package with all interfaces"
```
