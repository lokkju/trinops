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


TRINO_HEADERS = {
    "X-Trino-User": "trinops-recorder",
    "X-Trino-Source": "trinops-vcr",
    "Accept": "application/json",
}


def submit_query(base_url: str, sql: str) -> tuple[str, str | None]:
    """Submit a query via POST /v1/statement, return (query_id, next_uri)."""
    req = Request(
        f"{base_url}/v1/statement",
        data=sql.encode(),
        headers={**TRINO_HEADERS, "Content-Type": "text/plain"},
        method="POST",
    )
    with urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read())
    return data["id"], data.get("nextUri")


def follow_next_uri(next_uri: str | None, timeout: float = 120) -> str:
    """Follow the nextUri chain until the query reaches a terminal state.
    Returns the final state. Trino requires clients to poll nextUri to
    drive query execution forward; without this, queries are abandoned."""
    deadline = time.monotonic() + timeout
    while next_uri and time.monotonic() < deadline:
        try:
            req = Request(next_uri, headers=TRINO_HEADERS)
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            next_uri = data.get("nextUri")
            state = data.get("stats", {}).get("state", "")
            if state in ("FINISHED", "FAILED"):
                return state
        except (URLError, ConnectionError, OSError):
            pass
        time.sleep(0.5)
    return "TIMEOUT"


def activate_query(next_uri: str | None) -> str | None:
    """Follow nextUri a few times to activate the query without draining it.
    Returns the latest nextUri for continued polling if desired."""
    for _ in range(3):
        if not next_uri:
            break
        try:
            req = Request(next_uri, headers=TRINO_HEADERS)
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
            next_uri = data.get("nextUri")
        except (URLError, ConnectionError, OSError):
            break
        time.sleep(0.3)
    return next_uri


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
        # Trino requires clients to follow the nextUri chain to drive
        # query execution. Without polling, queries are abandoned.
        print("  Submitting TPC-H workload...")
        query_ids = []
        next_uris = []
        for i, sql in enumerate(TPCH_QUERIES):
            qid, next_uri = submit_query(base_url, sql)
            query_ids.append(qid)
            next_uris.append(next_uri)
            print(f"    Query {i+1}/{len(TPCH_QUERIES)}: {qid}")

        # Drain all but the last query to completion
        for i, next_uri in enumerate(next_uris[:-1]):
            state = follow_next_uri(next_uri)
            print(f"    Query {i+1} finished: {state}")

        # Activate the last query (don't drain — we'll kill it during recording)
        activate_query(next_uris[-1])

        # Now record the API interactions we care about
        print("  Recording API responses...")
        if cassette_dir.exists():
            shutil.rmtree(cassette_dir)
        cassette_dir.mkdir(parents=True)
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
    hdrs = {"Accept": "application/json", "X-Trino-User": "trinops-recorder"}

    # GET /v1/query (list all)
    req = Request(f"{base_url}/v1/query", headers=hdrs)
    with urlopen(req, timeout=30) as resp:
        queries = json.loads(resp.read())
    print(f"    GET /v1/query: {len(queries)} queries")

    # GET /v1/query?state=RUNNING
    req = Request(f"{base_url}/v1/query?state=RUNNING", headers=hdrs)
    with urlopen(req, timeout=30) as resp:
        running = json.loads(resp.read())
    print(f"    GET /v1/query?state=RUNNING: {len(running)} queries")

    # GET /v1/query/{id} (detail for first query)
    detail_id = query_ids[0]
    req = Request(f"{base_url}/v1/query/{detail_id}", headers=hdrs)
    with urlopen(req, timeout=30) as resp:
        detail = json.loads(resp.read())
    print(f"    GET /v1/query/{detail_id}: state={detail.get('state')}")

    # GET /v1/info
    req = Request(f"{base_url}/v1/info", headers=hdrs)
    with urlopen(req, timeout=30) as resp:
        info = json.loads(resp.read())
    print(f"    GET /v1/info: version={info.get('nodeVersion', {}).get('version', '?')}")

    # GET /v1/cluster
    req = Request(f"{base_url}/v1/cluster", headers=hdrs)
    try:
        with urlopen(req, timeout=30) as resp:
            cluster = json.loads(resp.read())
        print(f"    GET /v1/cluster: workers={cluster.get('activeWorkers')}")
    except Exception as e:
        print(f"    GET /v1/cluster: {e} (will be recorded as error)")

    # DELETE /v1/query/{id} (kill last query if still running)
    kill_id = query_ids[-1]
    req = Request(f"{base_url}/v1/query/{kill_id}", method="DELETE", headers=hdrs)
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
