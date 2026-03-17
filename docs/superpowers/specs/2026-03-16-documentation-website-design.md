# trino.ps Documentation Website

## Goal

Build a static documentation website at trino.ps that serves as both a marketing landing page for prospective users and a reference for existing users. Hosted on Cloudflare Pages, built with MkDocs Material, source on a dedicated `website` branch.

## Architecture

The site source lives on a `website` branch, separate from the `main` branch that holds the tool source. GitHub Actions builds on push to `website` using `mkdocs build` and deploys the output to Cloudflare Pages via Wrangler. The custom domain trino.ps points to the Cloudflare Pages project.

MkDocs Material provides dark theme, instant navigation (SPA-like page transitions), code highlighting, mobile responsiveness, and search out of the box. The Trino-native color palette (magenta primary on dark backgrounds) signals ecosystem alignment.

## Branch Structure

```
website branch
├── mkdocs.yml
├── requirements-site.txt          # mkdocs, mkdocs-material
├── docs/                          # MkDocs source root (set via docs_dir in mkdocs.yml)
│   ├── index.md                   # Landing page → trino.ps/
│   ├── assets/
│   │   ├── screenshots/           # SVGs for docs pages
│   │   ├── hero.png               # OG image / social sharing
│   │   └── hero.gif               # Animated TUI demo
│   ├── docs/                      # Nested "docs" section → trino.ps/docs/*
│   │   ├── getting-started.md     #   → trino.ps/docs/getting-started/
│   │   ├── tui.md                 #   → trino.ps/docs/tui/
│   │   ├── schema.md              #   → trino.ps/docs/schema/
│   │   ├── configuration.md       #   → trino.ps/docs/configuration/
│   │   ├── cli.md                 #   → trino.ps/docs/cli/
│   │   └── library.md             #   → trino.ps/docs/library/
│   └── overrides/                 # Custom Material theme overrides
│       ├── main.html              # Landing page template
│       └── assets/
│           └── stylesheets/
│               └── custom.css     # Trino palette, installer selector
└── .github/
    └── workflows/
        └── deploy-site.yml        # Build + deploy to Cloudflare Pages
```

Note: The outer `docs/` is the MkDocs source root. The inner `docs/docs/` directory produces the `/docs/` URL prefix, keeping documentation pages separate from the landing page at root.

## Color Palette

Trino-native palette, derived from the Trino project brand:

| Role       | Color   | Usage                                    |
|------------|---------|------------------------------------------|
| Primary    | #dd00a1 | Brand mark, CTAs, headings, links        |
| Dark BG    | #1d1f3e | Page background, card backgrounds        |
| Accent     | #f472b6 | Hover states, secondary highlights       |
| Text       | #e0e0e0 | Body text                                |
| Links      | #7c3aed | Navigation links, cross-references       |
| Code BG    | #0d1117 | Code block backgrounds                   |
| Success    | #50fa7b | Success states, terminal prompts in code |

MkDocs Material dark theme with custom CSS overrides to apply these colors.

## Typography

**Monospace font:** JetBrains Mono (OFL license, loaded via Google Fonts). Used for all code blocks, inline code, and the hero brand mark. Chosen for on-screen readability, ligature support, and developer audience familiarity.

**Logo:** The `trino.ps` brand mark in the hero may be rendered as an SVG image rather than live text, for precise control over letterforms and spacing independent of font loading. Both approaches (live JetBrains Mono text vs. SVG render) should be compared during implementation; the spec supports either. If SVG, the letterforms should still be based on JetBrains Mono for visual consistency with code blocks.

## Landing Page (index.md)

The landing page uses a custom template override to break out of the standard docs layout.

### Section 1: Hero

- `trino.ps` in monospace as the brand name
- Tagline: "Trino query monitoring from the terminal."
- Animated GIF of the TUI dashboard (query list, detail pane opening, tab switching, sorting)
- Install box immediately below the hero image with package manager selector
- "Get Started" (links to /docs/getting-started/) and "GitHub" buttons

### Section 2: Feature Cards

Two wide cards, stacking vertically on mobile:

**Command Line** — List, inspect, and kill queries. Search schema metadata across catalogs. JSON output for scripting. Code block showing key commands.

**Live Dashboard** — "Like htop for Trino." Live-updating query table, tabbed detail view, kill support, cluster stats. Inline SVG screenshot.

The Python library is not featured on the landing page; it's a developer-focused feature covered in its own docs page.

### Section 3: TUI Screenshot Gallery

2x2 grid of SVG screenshots:

- Query list with sort indicators
- Detail pane: Overview tab
- Detail pane: Stats tab
- Kill confirmation dialog

### Section 4: Quick Start

Three steps:

1. Configure: `uvx trinops config init --server trino.example.com --user myuser` (port defaults to 443 for https, 8080 for http)
2. Authenticate (if needed): `uvx trinops config set auth oauth2` + `uvx trinops auth login` with note listing supported methods
3. Go: `uvx trinops top`

### Section 5: Footer

- Links: Documentation, GitHub, PyPI, Issues
- Attribution: "Built by Loki Coyote · A community tool for the [Trino](https://trino.io) ecosystem · PolyForm Shield 1.0.0"

### Package Manager Selector

A tabbed pill control (`uvx | pipx | pip`) that persists across page navigations via localStorage and a small JavaScript snippet stored in the theme override. On each page load (including MkDocs Material instant navigation events), the script reads the stored preference and rewrites code blocks accordingly. Selecting a package manager changes all code blocks on the current page and all subsequent pages.

- **uvx** (default): `uvx trinops <command>`
- **pipx**: `pipx run trinops <command>`
- **pip**: Shows a separate `pip install trinops` step, then bare `trinops <command>`

The selector appears above the first install code block in the hero and applies globally.

## Documentation Pages

All under `/docs/`. Navigation order reflects the user journey: onboarding first, features second, reference last.

### 1. Getting Started (`/docs/getting-started/`)

- Installation with uvx/pipx/pip options
- `trinops config init` walkthrough (interactive and non-interactive)
- Environment variable configuration as alternative
- First `trinops top` run
- Verifying the connection

### 2. TUI Dashboard (`/docs/tui/`)

The flagship feature page. Heavy on screenshots.

- Overview of the dashboard layout (cluster header, query table, status bar, footer)
- Keybindings table (full list, grouped by context: global, detail pane)
- Query table: sorting (click headers, default Elapsed descending), column descriptions
- Detail pane: how to open/close, tab descriptions (Overview, Stats, Tables, Errors)
- Screenshot per feature state
- Kill workflow: selecting a query, confirmation dialog, from table and from detail pane
- Empty state and error handling (auth failures, connection errors)
- Copy to clipboard (`c` key)

### 3. Schema Search (`/docs/schema/`)

Workflow-focused, not just flag reference.

- Use case framing: "You inherited a Trino cluster. Find the table you need."
- `schema refresh` — single catalog vs `--all`, what gets cached, where it's stored
- `schema search` — glob patterns, table vs column search, JSON output
- `schema show` — table detail view
- `schema list` — what's cached, when it was fetched
- Integration with CLI scripting (piping JSON to jq, etc.)

### 4. Configuration (`/docs/configuration/`)

- Config file location and format (`~/.config/trinops/config.toml`)
- Default profile vs named profiles
- All profile fields: server, scheme, user, auth, catalog, schema, password, password_cmd, jwt_token, query_limit, allow_kill, confirm_kill
- Auth methods, each with setup instructions and relevant fields:
  - none (default)
  - basic (password via keyring, or password_cmd for scripted retrieval)
  - jwt (jwt_token field)
  - oauth2 (interactive flow via `trinops auth login`)
  - kerberos
- Environment variable overrides (TRINOPS_SERVER, TRINOPS_USER, etc.)
- `config set` / `config show` usage
- Multi-profile workflow example

### 5. CLI Reference (`/docs/cli/`)

Command-by-command reference. Each command gets: synopsis, flags table, examples, sample output.

- `trinops queries` — list queries, filter by state/user, JSON output, --select
- `trinops query <id>` — inspect single query, --json, --select for field extraction
- `trinops kill <id>` — cancel a query
- `trinops tui` / `trinops top` — launch dashboard (flags: --interval, --profile)
- `trinops config init` / `config set` / `config show`
- `trinops auth status` / `auth login`
- `trinops schema refresh` / `schema search` / `schema show` / `schema list`
- `trinops --version`

### 6. Python Library (`/docs/library/`)

Developer-focused API reference.

- `TrinoProgress` — two modes: wrapping a cursor for execute-and-track, or wrapping a connection to monitor an existing query by ID
- Display backends: stderr (default), tqdm (with `[tqdm]` extra), web
- `QueryStats` and `StageStats` dataclasses
- Code examples for each pattern
- Installation with extras: `pip install trinops[tqdm]`

## Screenshots

### Generation

Expand the existing `scripts/screenshot.py` (on `main` branch) to capture multiple TUI states using Textual's `run_test()` and `save_screenshot()` with mock data.

Screenshots to generate:

| Filename              | Content                                      | Format    |
|-----------------------|----------------------------------------------|-----------|
| query-list.svg        | Query table with sort caret on Elapsed       | SVG       |
| detail-overview.svg   | Detail pane open, Overview tab               | SVG       |
| detail-stats.svg      | Detail pane open, Stats tab                  | SVG       |
| detail-tables.svg     | Detail pane open, Tables tab                 | SVG       |
| detail-errors.svg     | Detail pane open, Errors tab (failed query)  | SVG       |
| kill-confirm.svg      | Kill confirmation dialog                     | SVG       |
| empty-state.svg       | Empty table with "No queries" message        | SVG       |
| hero.png              | Static TUI shot for OG image / social cards  | PNG       |
| hero.gif              | Animated sequence: load → detail → tabs → sort| GIF      |

SVGs are the primary format for docs pages (crisp at any resolution, tiny file size, generated by Rich). PNG is converted from SVG using cairosvg for Open Graph / social sharing metadata. GIF is assembled by capturing multiple SVG frames, converting each to PNG via cairosvg, and combining with Pillow (PIL). Both cairosvg and Pillow are dev-only dependencies used by `scripts/screenshot.py`.

### Workflow

1. Run `scripts/screenshot.py` locally against mock data (no Trino cluster needed)
2. Commit generated assets to the `website` branch under `docs/assets/screenshots/`
3. Re-run when UI changes

## Build and Deploy

### GitHub Actions Workflow (`deploy-site.yml`)

Triggers on push to `website` branch. Steps:

1. Checkout `website` branch
2. Set up Python
3. `pip install -r requirements-site.txt`
4. `mkdocs build`
5. Deploy `site/` to Cloudflare Pages via `cloudflare/wrangler-action`

Requires GitHub secrets: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`.

### Cloudflare Pages Configuration

- Project name: `trino-ps`
- Custom domain: trino.ps
- Production branch: `website`
- Build output: `site/`

## Dependencies (website branch only)

```
# requirements-site.txt
mkdocs>=1.6
mkdocs-material>=9.5
```

No runtime dependencies on the tool itself. The site is pure static HTML/CSS/JS after build.

## Open Questions

None. All design decisions have been made.
