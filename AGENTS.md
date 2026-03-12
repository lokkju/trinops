# Trinops Agent Instructions

## Project Overview

Trinops is a Trino query monitoring tool providing CLI commands, a TUI dashboard, and a Python library for embedding progress tracking. It queries Trino clusters via REST API (`/v1/query`, `/v1/info`, `/v1/cluster`) and SQL (`system.runtime.queries`).

## Tech Stack

- Python 3.10+, managed with `uv`
- Textual for the TUI
- `requests` (OAuth2/Kerberos) and `urllib` (all other auth) for HTTP
- `trino.dbapi` for SQL backend
- `hatch-vcs` for versioning from git tags
- PyPI publishing via GitHub Actions trusted publishing on tag push

## Development

- Run tests: `uv run python -m pytest tests/ -x -q`
- Build: `uv build`
- Version is derived from git tags (hatch-vcs); do not set it manually
- Publishing happens automatically on tag push matching `v[0-9]+.[0-9]+.[0-9]+`

## Architecture

- `src/trinops/backend.py` — `QueryBackend` protocol, `HttpQueryBackend`, `SqlQueryBackend`
- `src/trinops/client.py` — `TrinopsClient` wrapping backends
- `src/trinops/models.py` — `QueryInfo`, `ClusterStats`, `QueryState`
- `src/trinops/formatting.py` — Duration/size parsing and compact formatting
- `src/trinops/tui/app.py` — Textual TUI with `ClusterHeader`, `StatusBar`, DataTable
- `src/trinops/cli/` — CLI commands via Typer
- `src/trinops/progress/` — `TrinoProgress` library for embedding in scripts

## Conventions

- Conventional commits: `type(scope): description`
- Tests live in `tests/` mirroring source structure
- HTTP backend has dual code paths (urllib vs requests.Session); both must be handled in error cases
- Optional REST endpoints use tri-state availability tracking (`EndpointState`)
- TUI uses separate workers for queries and cluster stats
