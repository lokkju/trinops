# VCR-Based Version Compatibility Testing

## Summary

Record real HTTP responses from multiple Trino versions using vcrpy, then replay them in tests to verify that `HttpQueryBackend` correctly parses every supported version's API responses. A standalone recording script manages the Docker lifecycle and workload; tests parameterize across all recorded versions automatically.

## Motivation

Trino's REST API response shapes can change between versions without structured documentation. Recording real responses from specific versions creates a versioned reference that future development runs against without needing Docker. When parsing logic or field handling changes, tests immediately surface which versions break.

## Components

### SUPPORTED_TRINO_VERSIONS

A plain text file at the project root listing one Trino Docker image tag per line. Comments (lines starting with `#`) and blank lines are ignored. This file drives the recording script; test discovery is based on which cassette directories exist.

```
# Oldest supported
400
# Mid-range
430
# Current
449
```

### Recording script: `scripts/record_trino.py`

A standalone CLI script runnable as `uv run python scripts/record_trino.py 449` or `uv run python scripts/record_trino.py --all`.

Lifecycle for a single version:

1. Pull `trinodb/trino:{version}` if not already present
2. Start a container with the `tpch` connector enabled (mount a minimal `tpch.properties` catalog file)
3. Wait for readiness by polling `GET /v1/info` until `starting` is `false` (timeout after 120s to accommodate slow image pulls)
4. Run workload: submit TPC-H queries against `tpch.sf1` via direct HTTP `POST /v1/statement`. Use a mix of fast queries (Q1, Q6) and slower ones (Q5, Q9) to produce queries in RUNNING, QUEUED, and FINISHED states on a single-node instance.
5. Exercise every endpoint through vcrpy recording:
   - `GET /v1/query` (unfiltered)
   - `GET /v1/query?state=RUNNING`
   - `GET /v1/query/{id}` for at least one query
   - `GET /v1/info`
   - `GET /v1/cluster`
   - `DELETE /v1/query/{id}` on one running query
6. Save cassette to `tests/cassettes/trino-{version}/responses.yaml` and write `tests/cassettes/trino-{version}/metadata.json` with `detail_query_id` and `kill_query_id` (the query IDs used for `GET /v1/query/{id}` and `DELETE /v1/query/{id}` respectively) so tests can reference the exact recorded IDs
7. Stop and remove the container

The `--all` flag reads `SUPPORTED_TRINO_VERSIONS` and records each version sequentially. If a cassette directory already exists for a version, it is overwritten (idempotent re-recording).

The endpoint list is a data structure in the script, not hardcoded inline, so adding future endpoints (e.g., `ui/` paths) is a one-line change followed by re-recording.

Auth: the script connects with `auth=none` to local Docker Trino. No credential scrubbing is needed, but the vcrpy config filters `Authorization` headers from cassettes as a safety net.

Query submission: the script submits queries by posting SQL directly to `POST /v1/statement` with `X-Trino-User` and `X-Trino-Source` headers, then follows the `nextUri` chain until the query reaches a terminal state or is observed in the desired state. This avoids depending on the trinops backend during recording (no circular dependency).

### Makefile targets

```makefile
record:
	uv run python scripts/record_trino.py $(VERSION)

record-all:
	uv run python scripts/record_trino.py --all
```

### Cassette structure

```
tests/cassettes/
  trino-400/
    responses.yaml
  trino-430/
    responses.yaml
  trino-449/
    responses.yaml
```

Each `responses.yaml` is a vcrpy cassette containing all recorded HTTP interactions for that version. Cassette files are committed to git as test fixtures.

Expected size: 50-100KB per version (TPC-H SQL text + query stats blobs). Not a concern for git.

### vcrpy configuration

Configured in `tests/conftest.py`. Uses raw `vcrpy` directly (no `pytest-recording`) for full control over cassette paths and fixture lifecycle.

- **Record mode**: `none` by default (pure replay in tests). The recording script uses `all` mode.
- **Request matching**: match on `method`, `host`, `port`, `path`. Ignore query string parameters (the `?state=` filter on `/v1/query` doesn't affect response shape for testing purposes) and headers.
- **Response filtering**: strip `Authorization` headers from recorded requests.
- **Compression**: `decode_compressed_response=True` in both recording and replay configs. The backend sends `Accept-Encoding: gzip`; this setting decodes compressed bodies and strips `Content-Encoding` headers in cassettes, preventing double-decompression during replay.
- **Interception**: vcrpy patches at the `http.client.HTTPConnection` / `HTTPSConnection` level, which underlies both `urllib.request.urlopen` (the backend's default code path) and `requests.Session` (the OAuth2/Kerberos path). Both paths are intercepted without additional configuration.

### Test fixture: `conftest.py`

A `trino_version` fixture discovers all `tests/cassettes/trino-*/` directories, extracts the version string, and parameterizes tests across them. Each test gets vcrpy configured to replay from that version's cassette, plus a `metadata` dict loaded from the version's `metadata.json` sidecar.

The fixture yields a 3-tuple: `(version_str, use_cassette_fn, metadata_dict)`. Tests that need version-specific cassettes use the `trino_version` fixture. Tests that don't need cassettes (existing unit tests, fake server tests) are unaffected.

### Test file: `tests/test_version_compat.py`

Parameterized tests that exercise `HttpQueryBackend` and `TrinopsClient` against recorded responses:

- `test_list_queries` — `HttpQueryBackend.list_queries()` returns a non-empty list of `QueryInfo` objects with valid `query_id`, `state`, `user`, `created` fields
- `test_get_query` — reads `detail_query_id` from the metadata sidecar, then calls `get_query(id)`. Returns a `QueryInfo` with populated detail fields (elapsed time, memory, rows).
- `test_get_info` — `HttpQueryBackend.get_info()` returns a dict with `nodeVersion.version` (string) and `uptime` (string), or `None` on versions where the endpoint 404s
- `test_get_cluster` — `HttpQueryBackend.get_cluster()` returns a dict with `activeWorkers`, or `None` on versions where the endpoint 404s
- `test_kill_query` — reads `kill_query_id` from the metadata sidecar, then calls `kill_query(id)`. Returns `True` (cassette contains the DELETE response with 204 status).
- `test_build_cluster_stats` — `TrinopsClient.build_cluster_stats()` populates `ClusterStats` fields from recorded data; `trino_version` is present, `active_workers` is present or `None` depending on version

Each test runs once per recorded version. Failures identify the exact version that broke.

### Relationship to existing tests

The existing `test_http_backend.py` tests (using `FakeTrinoAPI`) remain unchanged. They test behavioral concerns (error handling, auth header construction, tri-state availability tracking, kill success/failure paths) that don't vary by Trino version. The VCR tests are complementary: they test parsing correctness against real response shapes from real Trino versions.

### Dependencies

Add to `[dependency-groups] dev` in `pyproject.toml`:

- `vcrpy>=6.0`

(`pytest-recording` is not needed; the `conftest.py` fixture uses `vcrpy` directly for full control over cassette paths and lifecycle.)

### New files

- `SUPPORTED_TRINO_VERSIONS` — version list at project root
- `scripts/record_trino.py` — recording script
- `scripts/tpch.properties` — minimal catalog config (`connector.name=tpch`) mounted into Docker container
- `Makefile` — project does not currently have one; create with `record` and `record-all` targets
- `tests/test_version_compat.py` — parameterized VCR tests
- `tests/cassettes/` — cassette directories (created by recording script)

### Future: `ui/` endpoints

When Trino ships the `ui/` API endpoints, the recording script's endpoint list gains new entries and all versions are re-recorded. Versions that don't support the new endpoints will return 404, which the cassettes capture. Version compatibility tests can then assert "endpoint returns data on version X+ and `None` on older versions" using the existing graceful-fallback pattern (`_try_optional_endpoint` with tri-state tracking).
