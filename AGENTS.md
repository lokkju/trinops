# AGENTS.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Structure

This repo has two independent branches with separate stacks:

- **`main`** — Python CLI/TUI tool (trinops)
- **`website`** — Astro + Starlight documentation site (trino.ps)

Never merge these branches. Always branch from the correct base: `git fetch origin && git checkout -b <branch> origin/<base>`.

---

## Website Branch (`website`)

### Commands

```sh
npm ci           # install dependencies
npm run dev      # Astro dev server (hot reload)
npm run build    # build static site to dist/
npm run preview  # preview built site
```

`mise` tasks mirror the npm scripts (`mise run dev`, `mise run build`, `mise run preview`). Node 22.16.0 is required (managed by mise).

### Architecture

- **Framework**: Astro 6 + Starlight docs theme
- **Content**: MDX pages in `src/content/docs/docs/` — one file per doc page
- **Landing page**: `src/pages/index.astro` — custom Astro component (not Starlight)
- **Styling**: `src/styles/custom.css` — Starlight CSS variable overrides (magenta/purple palette, JetBrains Mono font)
- **Static assets**: `public/screenshots/` — SVG/GIF/PNG TUI screenshots used in docs and landing page
- **Sidebar order**: defined explicitly in `astro.config.mjs` (not auto-discovered)
- **Deployment**: Cloudflare Pages via GitHub Actions on push to `website` branch; production branch is `main` in the Cloudflare project

---

## Main Branch (`main`)

### Commands

```sh
uv run python -m pytest tests/ -x -q   # run tests (stop on first failure)
uv build                                # build distribution
```

Version is derived from git tags via `hatch-vcs` — do not set it manually. Publishing happens automatically on tag push matching `v[0-9]+.[0-9]+.[0-9]+`.

### Architecture

- **`src/trinops/backend.py`** — `HttpQueryBackend`: REST API client for Trino (`/v1/query`, `/v1/info`, `/v1/cluster`). Has dual code paths for urllib vs requests.Session; both must handle errors. Optional REST endpoints use tri-state `EndpointState` tracking.
- **`src/trinops/client.py`** — `TrinopsClient` wrapping backends
- **`src/trinops/models.py`** — `QueryInfo`, `ClusterStats`, `QueryState` dataclasses
- **`src/trinops/formatting.py`** — duration/size parsing and compact display formatting
- **`src/trinops/tui/app.py`** — Textual TUI with `ClusterHeader`, `StatusBar`, DataTable; separate workers for queries and cluster stats
- **`src/trinops/cli/`** — Typer CLI commands (entry point: `trinops.cli:app`)
- **`src/trinops/progress/`** — `TrinoProgress` library for embedding query tracking in scripts
- **`src/trinops/auth.py`** — OAuth2, JWT, basic auth, Kerberos
- **`src/trinops/config.py`** — TOML config with profile support (keyring for credential storage)

Tests mirror source structure in `tests/`.

---

## Conventions

- Conventional commits: `type(scope): description`
- License: PolyForm Shield 1.0.0
