# VCR Version Compatibility Testing Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record real Trino REST API responses from multiple versions via Docker + vcrpy, then replay them in parameterized tests to verify parsing correctness across versions.

**Architecture:** A standalone recording script (`scripts/record_trino.py`) manages the Docker lifecycle and TPC-H workload, recording HTTP interactions into version-specific cassette directories. A pytest fixture in `conftest.py` discovers cassette directories and parameterizes tests. Tests in `test_version_compat.py` exercise `HttpQueryBackend` and `TrinopsClient` against each recorded version.

**Tech Stack:** Python, vcrpy, Docker (recording only), pytest

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `pyproject.toml` | Modify | Add `vcrpy>=6.0` to dev dependencies |
| `SUPPORTED_TRINO_VERSIONS` | Create | Version list driving the recording script |
| `scripts/tpch.properties` | Create | Minimal Trino catalog config for TPC-H connector |
| `scripts/record_trino.py` | Create | Docker lifecycle, workload submission, vcrpy recording |
| `Makefile` | Create | `record` and `record-all` targets |
| `tests/conftest.py` | Modify | Add `trino_version` fixture with cassette discovery and vcrpy config |
| `tests/test_version_compat.py` | Create | Parameterized tests across recorded versions |
| `tests/cassettes/` | Created by script | Version-specific cassette YAML files and metadata JSON |

---

## Chunk 1: Infrastructure and Recording Script

### Task 1: Add vcrpy dependency and version list

**Files:**
- Modify: `pyproject.toml:56-61`
- Create: `SUPPORTED_TRINO_VERSIONS`
- Create: `scripts/tpch.properties`

- [ ] **Step 1: Add vcrpy to dev dependencies**

In `pyproject.toml`, change:
```toml
[dependency-groups]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "tqdm>=4.60",
]
```
to:
```toml
[dependency-groups]
dev = [
    "pytest>=7.0",
    "pytest-cov>=4.0",
    "tqdm>=4.60",
    "vcrpy>=6.0",
]
```

- [ ] **Step 2: Install the new dependency**

Run: `uv sync`
Expected: vcrpy installed successfully

- [ ] **Step 3: Create SUPPORTED_TRINO_VERSIONS**

Create `SUPPORTED_TRINO_VERSIONS` at the project root:
```
# Trino versions to record VCR cassettes for.
# One Docker image tag per line. Comments and blank lines are ignored.
# Re-record after changes: make record-all

# Oldest supported
400
# Mid-range
430
# Current
449
```

- [ ] **Step 4: Create tpch.properties**

Create `scripts/tpch.properties`:
```
connector.name=tpch
```

- [ ] **Step 5: Verify vcrpy imports**

Run: `uv run python -c "import vcr; print(vcr.__version__)"`
Expected: prints version number (6.x)

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml SUPPORTED_TRINO_VERSIONS scripts/tpch.properties
git commit -m "feat(test): add vcrpy dependency and supported Trino versions list"
```

### Task 2: Create the recording script

**Files:**
- Create: `scripts/record_trino.py`

- [ ] **Step 1: Create the recording script**

Create `scripts/record_trino.py`:

```python
#!/usr/bin/env python3
"""Record Trino REST API responses for VCR-based version compatibility tests.

Usage:
    uv run python scripts/record_trino.py 449          # Record a single version
    uv run python scripts/record_trino.py --all         # Record all versions from SUPPORTED_TRINO_VERSIONS
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

import vcr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VERSIONS_FILE = PROJECT_ROOT / "SUPPORTED_TRINO_VERSIONS"
CASSETTES_DIR = PROJECT_ROOT / "tests" / "cassettes"
TPCH_PROPERTIES = Path(__file__).resolve().parent / "tpch.properties"

CONTAINER_NAME_PREFIX = "trinops-vcr-"
TRINO_PORT = 8080

# TPC-H queries: mix of fast and slow to capture various states
TPCH_QUERIES = [
    # Q6 - fast, single table scan
    """SELECT sum(l_extendedprice * l_discount) AS revenue
       FROM tpch.sf1.lineitem
       WHERE l_shipdate >= DATE '1994-01-01'
         AND l_shipdate < DATE '1995-01-01'
         AND l_discount BETWEEN 0.05 AND 0.07
         AND l_quantity < 24""",
    # Q1 - moderate, aggregation
    """SELECT l_returnflag, l_linestatus,
              sum(l_quantity) AS sum_qty,
              sum(l_extendedprice) AS sum_base_price
       FROM tpch.sf1.lineitem
       WHERE l_shipdate <= DATE '1998-09-02'
       GROUP BY l_returnflag, l_linestatus
       ORDER BY l_returnflag, l_linestatus""",
    # Q5 - slower, multi-join
    """SELECT n_name, sum(l_extendedprice * (1 - l_discount)) AS revenue
       FROM tpch.sf1.customer, tpch.sf1.orders, tpch.sf1.lineitem,
            tpch.sf1.supplier, tpch.sf1.nation, tpch.sf1.region
       WHERE c_custkey = o_custkey AND l_orderkey = o_orderkey
         AND l_suppkey = s_suppkey AND c_nationkey = s_nationkey
         AND s_nationkey = n_nationkey AND n_regionkey = r_regionkey
         AND r_name = 'ASIA' AND o_orderdate >= DATE '1994-01-01'
         AND o_orderdate < DATE '1995-01-01'
       GROUP BY n_name ORDER BY revenue DESC""",
]


def parse_versions_file() -> list[str]:
    """Read SUPPORTED_TRINO_VERSIONS, ignoring comments and blanks."""
    if not VERSIONS_FILE.exists():
        print(f"Error: {VERSIONS_FILE} not found", file=sys.stderr)
        sys.exit(1)
    versions = []
    for line in VERSIONS_FILE.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            versions.append(line)
    return versions


def docker_run(version: str) -> str:
    """Start a Trino container, return container ID."""
    container_name = f"{CONTAINER_NAME_PREFIX}{version}"
    # Stop any existing container with the same name
    subprocess.run(["docker", "rm", "-f", container_name],
                   capture_output=True)

    cmd = [
        "docker", "run", "-d",
        "--name", container_name,
        "-p", f"{TRINO_PORT}:{TRINO_PORT}",
        "-v", f"{TPCH_PROPERTIES}:/etc/trino/catalog/tpch.properties:ro",
        f"trinodb/trino:{version}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def docker_stop(version: str) -> None:
    """Stop and remove the Trino container."""
    container_name = f"{CONTAINER_NAME_PREFIX}{version}"
    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)


def wait_for_trino(base_url: str, timeout: float = 120) -> None:
    """Poll /v1/info until Trino reports starting=false."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            req = Request(f"{base_url}/v1/info",
                          headers={"Accept": "application/json"})
            with urlopen(req, timeout=5) as resp:
                info = json.loads(resp.read())
                if not info.get("starting", True):
                    print(f"  Trino ready (version: {info.get('nodeVersion', {}).get('version', '?')})")
                    return
        except (URLError, ConnectionError, OSError):
            pass
        time.sleep(2)
    raise TimeoutError(f"Trino did not become ready within {timeout}s")


def submit_query(base_url: str, sql: str) -> str:
    """Submit a query via POST /v1/statement, return query ID."""
    req = Request(
        f"{base_url}/v1/statement",
        data=sql.encode(),
        headers={
            "X-Trino-User": "trinops-recorder",
            "X-Trino-Source": "trinops-vcr",
            "Content-Type": "text/plain",
        },
        method="POST",
    )
    with urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["id"]


def poll_query_until_state(base_url: str, query_id: str,
                           target_states: set[str],
                           timeout: float = 60) -> str:
    """Poll a query until it reaches one of the target states. Returns final state."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            req = Request(f"{base_url}/v1/query/{query_id}",
                          headers={"Accept": "application/json"})
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            state = data.get("state", "UNKNOWN")
            if state in target_states:
                return state
        except (URLError, ConnectionError, OSError):
            pass
        time.sleep(0.5)
    return "TIMEOUT"


def drain_query(base_url: str, query_id: str) -> None:
    """Follow nextUri chain to drain a query's results."""
    # Get initial nextUri from query detail
    try:
        req = Request(f"{base_url}/v1/query/{query_id}",
                      headers={"Accept": "application/json"})
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        state = data.get("state", "")
        if state in ("FINISHED", "FAILED"):
            return
    except (URLError, ConnectionError, OSError):
        return

    # Poll until terminal
    poll_query_until_state(
        base_url, query_id,
        {"FINISHED", "FAILED"},
        timeout=120,
    )


def record_version(version: str) -> None:
    """Record all API interactions for a single Trino version."""
    base_url = f"http://127.0.0.1:{TRINO_PORT}"
    cassette_dir = CASSETTES_DIR / f"trino-{version}"

    print(f"\n=== Recording Trino {version} ===")

    # Start container
    print(f"  Starting trinodb/trino:{version}...")
    try:
        docker_run(version)
    except subprocess.CalledProcessError as e:
        print(f"  Failed to start container: {e.stderr}", file=sys.stderr)
        return

    try:
        # Wait for readiness
        print("  Waiting for Trino to be ready...")
        wait_for_trino(base_url)

        # Submit workload (outside VCR recording)
        print("  Submitting TPC-H workload...")
        query_ids = []
        for i, sql in enumerate(TPCH_QUERIES):
            qid = submit_query(base_url, sql)
            query_ids.append(qid)
            print(f"    Query {i+1}/{len(TPCH_QUERIES)}: {qid}")

        # Wait for at least one query to finish
        time.sleep(2)
        for qid in query_ids[:-1]:
            drain_query(base_url, qid)

        # Now record the API interactions we care about
        print("  Recording API responses...")
        cassette_dir.mkdir(parents=True, exist_ok=True)
        cassette_path = str(cassette_dir / "responses.yaml")

        my_vcr = vcr.VCR(
            record_mode="all",
            match_on=["method", "host", "port", "path"],
            before_record_request=_scrub_request,
            decode_compressed_response=True,
        )

        with my_vcr.use_cassette(cassette_path):
            detail_id, kill_id = _exercise_endpoints(base_url, query_ids)

        # Write metadata sidecar so tests know which query IDs were recorded
        metadata = {"detail_query_id": detail_id, "kill_query_id": kill_id}
        metadata_path = cassette_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
        print(f"  Metadata saved: {metadata_path}")

        print(f"  Cassette saved: {cassette_path}")
        cassette_size = os.path.getsize(cassette_path)
        print(f"  Cassette size: {cassette_size:,} bytes")

    finally:
        print(f"  Stopping container...")
        docker_stop(version)


def _scrub_request(request):
    """Remove Authorization headers from recorded requests."""
    if "Authorization" in request.headers:
        del request.headers["Authorization"]
    return request


def _exercise_endpoints(base_url: str, query_ids: list[str]) -> tuple[str, str]:
    """Hit every endpoint the backend uses, in the order tests expect.
    Returns (detail_query_id, kill_query_id) so the caller can write metadata."""
    # GET /v1/query (list all)
    req = Request(f"{base_url}/v1/query",
                  headers={"Accept": "application/json"})
    with urlopen(req, timeout=30) as resp:
        queries = json.loads(resp.read())
    print(f"    GET /v1/query: {len(queries)} queries")

    # GET /v1/query?state=RUNNING
    req = Request(f"{base_url}/v1/query?state=RUNNING",
                  headers={"Accept": "application/json"})
    with urlopen(req, timeout=30) as resp:
        running = json.loads(resp.read())
    print(f"    GET /v1/query?state=RUNNING: {len(running)} queries")

    # GET /v1/query/{id} (detail for first query)
    detail_id = query_ids[0]
    req = Request(f"{base_url}/v1/query/{detail_id}",
                  headers={"Accept": "application/json"})
    with urlopen(req, timeout=30) as resp:
        detail = json.loads(resp.read())
    print(f"    GET /v1/query/{detail_id}: state={detail.get('state')}")

    # GET /v1/info
    req = Request(f"{base_url}/v1/info",
                  headers={"Accept": "application/json"})
    with urlopen(req, timeout=30) as resp:
        info = json.loads(resp.read())
    print(f"    GET /v1/info: version={info.get('nodeVersion', {}).get('version', '?')}")

    # GET /v1/cluster
    req = Request(f"{base_url}/v1/cluster",
                  headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=30) as resp:
            cluster = json.loads(resp.read())
        print(f"    GET /v1/cluster: workers={cluster.get('activeWorkers')}")
    except Exception as e:
        print(f"    GET /v1/cluster: {e} (will be recorded as error)")

    # DELETE /v1/query/{id} (kill last query if still running)
    kill_id = query_ids[-1]
    req = Request(f"{base_url}/v1/query/{kill_id}",
                  method="DELETE",
                  headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=30) as resp:
            print(f"    DELETE /v1/query/{kill_id}: {resp.status}")
    except Exception as e:
        print(f"    DELETE /v1/query/{kill_id}: {e}")

    return detail_id, kill_id


def main():
    parser = argparse.ArgumentParser(
        description="Record Trino REST API responses for VCR tests"
    )
    parser.add_argument("version", nargs="?", help="Trino version to record")
    parser.add_argument("--all", action="store_true",
                        help="Record all versions from SUPPORTED_TRINO_VERSIONS")
    args = parser.parse_args()

    if args.all:
        versions = parse_versions_file()
        print(f"Recording {len(versions)} versions: {', '.join(versions)}")
        for version in versions:
            record_version(version)
    elif args.version:
        record_version(args.version)
    else:
        parser.print_help()
        sys.exit(1)

    print("\nDone.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify the script parses**

Run: `uv run python scripts/record_trino.py --help`
Expected: prints usage help without errors

- [ ] **Step 3: Commit**

```bash
git add scripts/record_trino.py
git commit -m "feat(test): add VCR recording script for Trino version testing"
```

### Task 3: Create the Makefile

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create Makefile**

Create `Makefile` at the project root:

```makefile
.PHONY: record record-all test

record:
ifndef VERSION
	$(error VERSION is required. Usage: make record VERSION=449)
endif
	uv run python scripts/record_trino.py $(VERSION)

record-all:
	uv run python scripts/record_trino.py --all

test:
	uv run python -m pytest tests/ -x -q
```

- [ ] **Step 2: Verify make targets**

Run: `make test`
Expected: runs pytest, all existing tests pass

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "build: add Makefile with record and test targets"
```

## Chunk 2: Test Fixtures and Version Compatibility Tests

### Task 4: Add VCR fixtures to conftest.py

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Write the conftest fixtures**

Replace the contents of `tests/conftest.py` with:

```python
"""Shared fixtures for trinops tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import vcr

CASSETTES_DIR = Path(__file__).parent / "cassettes"


def _discover_versions() -> list[str]:
    """Find all trino-{version} cassette directories."""
    if not CASSETTES_DIR.exists():
        return []
    versions = []
    for d in sorted(CASSETTES_DIR.iterdir()):
        if d.is_dir() and d.name.startswith("trino-"):
            version = d.name.removeprefix("trino-")
            cassette = d / "responses.yaml"
            if cassette.exists():
                versions.append(version)
    return versions


_VERSIONS = _discover_versions()


@pytest.fixture(params=_VERSIONS if _VERSIONS else [pytest.param("none", marks=pytest.mark.skip("no cassettes recorded"))],
                ids=[f"trino-{v}" for v in _VERSIONS] if _VERSIONS else ["no-cassettes"])
def trino_version(request):
    """Parameterized fixture yielding (version_str, use_cassette, metadata).

    Usage in tests:
        def test_something(trino_version):
            version, use_cassette, metadata = trino_version
            with use_cassette():
                backend = HttpQueryBackend(profile)
                ...

    metadata keys: detail_query_id, kill_query_id
    """
    version = request.param
    version_dir = CASSETTES_DIR / f"trino-{version}"
    cassette_path = str(version_dir / "responses.yaml")

    metadata_path = version_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}

    my_vcr = vcr.VCR(
        record_mode="none",
        match_on=["method", "host", "port", "path"],
        decode_compressed_response=True,
    )

    def use_cassette():
        return my_vcr.use_cassette(cassette_path)

    return version, use_cassette, metadata
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `uv run python -m pytest tests/ -x -q`
Expected: all 125 tests pass (no cassettes exist yet, so `trino_version` fixture skips)

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "feat(test): add VCR cassette discovery fixtures to conftest"
```

### Task 5: Create version compatibility tests

**Files:**
- Create: `tests/test_version_compat.py`

- [ ] **Step 1: Create the test file**

Create `tests/test_version_compat.py`:

```python
"""Version compatibility tests using VCR cassettes.

These tests replay recorded HTTP responses from real Trino versions
to verify that HttpQueryBackend parses all supported versions correctly.

To record cassettes: make record-all
"""
from __future__ import annotations

import pytest

from trinops.backend import HttpQueryBackend
from trinops.client import TrinopsClient
from trinops.config import ConnectionProfile
from trinops.models import QueryState


def _make_profile() -> ConnectionProfile:
    """Create a profile pointing at the recorded server."""
    return ConnectionProfile(
        server="127.0.0.1:8080",
        scheme="http",
        auth="none",
        user="trinops-recorder",
    )


def test_list_queries(trino_version):
    """list_queries returns QueryInfo objects with valid core fields."""
    version, use_cassette, _metadata = trino_version
    profile = _make_profile()
    backend = HttpQueryBackend(profile)

    with use_cassette():
        queries = backend.list_queries()

    assert len(queries) > 0, f"No queries returned for Trino {version}"
    for qi in queries:
        assert qi.query_id, "query_id must not be empty"
        assert isinstance(qi.state, QueryState), f"state must be QueryState, got {type(qi.state)}"
        assert qi.user, "user must not be empty"
        assert qi.created is not None, "created must not be None"
        assert qi.query, "query SQL must not be empty"


def test_get_query(trino_version):
    """get_query returns a QueryInfo with detail fields populated."""
    version, use_cassette, metadata = trino_version
    profile = _make_profile()
    backend = HttpQueryBackend(profile)

    # Use the exact query ID recorded in the cassette
    query_id = metadata["detail_query_id"]

    with use_cassette():
        qi = backend.get_query(query_id)

    assert qi is not None, f"get_query returned None for {query_id}"
    assert qi.query_id == query_id
    assert isinstance(qi.state, QueryState)
    assert qi.user
    assert qi.query


def test_get_info(trino_version):
    """get_info returns version and uptime from /v1/info."""
    version, use_cassette, _metadata = trino_version
    profile = _make_profile()
    backend = HttpQueryBackend(profile)

    with use_cassette():
        info = backend.get_info()

    if info is None:
        pytest.skip(f"Trino {version} does not expose /v1/info")

    assert "nodeVersion" in info
    assert isinstance(info["nodeVersion"], dict)
    assert "version" in info["nodeVersion"]
    assert isinstance(info["nodeVersion"]["version"], str)
    assert "uptime" in info
    assert isinstance(info["uptime"], str)


def test_get_cluster(trino_version):
    """get_cluster returns worker count from /v1/cluster."""
    version, use_cassette, _metadata = trino_version
    profile = _make_profile()
    backend = HttpQueryBackend(profile)

    with use_cassette():
        cluster = backend.get_cluster()

    if cluster is None:
        pytest.skip(f"Trino {version} does not expose /v1/cluster")

    assert "activeWorkers" in cluster
    assert isinstance(cluster["activeWorkers"], int)


def test_kill_query(trino_version):
    """kill_query returns True for a recorded DELETE response."""
    version, use_cassette, metadata = trino_version
    profile = _make_profile()
    backend = HttpQueryBackend(profile)

    # Use the exact query ID that the recording script killed
    query_id = metadata["kill_query_id"]

    with use_cassette():
        result = backend.kill_query(query_id)

    assert result is True, f"kill_query should return True for recorded 204 response"


def test_build_cluster_stats(trino_version):
    """build_cluster_stats populates ClusterStats from recorded data."""
    version, use_cassette, _metadata = trino_version
    profile = _make_profile()
    client = TrinopsClient.from_profile(profile)

    with use_cassette():
        queries = client.list_queries()
        stats = client.build_cluster_stats(queries)

    assert stats.total_queries > 0
    # trino_version should be populated since all supported versions expose /v1/info
    if stats.trino_version is not None:
        assert isinstance(stats.trino_version, str)
        assert len(stats.trino_version) > 0
```

- [ ] **Step 2: Verify tests are collected but skipped (no cassettes yet)**

Run: `uv run python -m pytest tests/test_version_compat.py -v`
Expected: all 6 tests show as SKIPPED with "no cassettes recorded"

- [ ] **Step 3: Verify all tests still pass**

Run: `uv run python -m pytest tests/ -x -q`
Expected: 125 passed, 6 skipped

- [ ] **Step 4: Commit**

```bash
git add tests/test_version_compat.py
git commit -m "feat(test): add version compatibility tests with VCR replay"
```

### Task 6: Record cassettes and verify tests pass

**Files:**
- Creates: `tests/cassettes/trino-{version}/responses.yaml` (via script)

This task requires Docker. It validates the full pipeline end-to-end.

- [ ] **Step 1: Record a single version to test the pipeline**

Run: `make record VERSION=449`
Expected: script pulls image, starts container, submits queries, records cassette, stops container. Output shows each endpoint hit with response summary.

- [ ] **Step 2: Verify the cassette was created**

Run: `ls -la tests/cassettes/trino-449/responses.yaml`
Expected: file exists, 10KB+ in size

- [ ] **Step 3: Run version compat tests against the recorded cassette**

Run: `uv run python -m pytest tests/test_version_compat.py -v`
Expected: 6 tests pass with `[trino-449]` parameterization

- [ ] **Step 4: Run full test suite**

Run: `uv run python -m pytest tests/ -x -q`
Expected: 131 passed (125 existing + 6 new)

- [ ] **Step 5: Record all versions**

Run: `make record-all`
Expected: records cassettes for 400, 430, 449 sequentially

- [ ] **Step 6: Run version compat tests against all versions**

Run: `uv run python -m pytest tests/test_version_compat.py -v`
Expected: 18 tests pass (6 tests × 3 versions). Some tests may skip on older versions if endpoints 404.

- [ ] **Step 7: Run full test suite**

Run: `uv run python -m pytest tests/ -x -q`
Expected: all tests pass

- [ ] **Step 8: Commit cassettes**

```bash
git add tests/cassettes/
git commit -m "test: add VCR cassettes for Trino 400, 430, 449"
```
