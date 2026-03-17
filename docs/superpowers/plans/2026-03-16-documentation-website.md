# trino.ps Documentation Website Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static documentation website at trino.ps using MkDocs Material, with a marketing landing page, six docs pages, automated screenshots, and GitHub Actions deployment to Cloudflare Pages.

**Architecture:** Source lives on an orphan `website` branch. MkDocs Material with custom theme overrides for Trino-native palette, JetBrains Mono typography, and a package manager selector. Screenshots generated on `main` via `scripts/screenshot.py`, committed to `website` branch. GitHub Actions builds and deploys to Cloudflare Pages.

**Tech Stack:** MkDocs Material, GitHub Actions, Cloudflare Pages (Wrangler), Textual (screenshot generation), cairosvg + Pillow (SVG-to-PNG/GIF conversion)

**Spec:** `docs/superpowers/specs/2026-03-16-documentation-website-design.md`

---

## Chunk 1: Screenshot Generation (main branch)

### Task 1: Update screenshot script for current TUI

The existing `scripts/screenshot.py` is outdated — its `MockTrinopsApp.on_mount()` doesn't match the current `TrinopsApp.on_mount()` which now uses `_COLUMN_LABELS`, `_sort_col`, `_sort_reverse`, `_update_column_carets()`, and `_update_empty_message()`. Update the mock to match, and produce multiple screenshots.

**Files:**
- Modify: `scripts/screenshot.py`

**Context for implementer:**
- Read `src/trinops/tui/app.py:182-202` for the current `on_mount()` — it calls `table.add_columns(*self._COLUMN_LABELS)`, captures column keys, sets default sort to Elapsed descending (col index 3), and calls `_update_column_carets()`.
- Read `src/trinops/tui/app.py:369-418` for `_update_table()` — builds rows from `self._queries` via `qi.truncated_sql(60)`, handles sort after update.
- Read `src/trinops/tui/app.py:350-368` for `_update_empty_message()` — toggles `#empty-message` visibility based on `table.row_count`.
- Read `src/trinops/tui/detail.py` for the `DetailPane` class — `set_data(dict)` populates tabs, `show()` adds "visible" class and focuses.
- Read `src/trinops/tui/app.py:419-437` for `_show_detail_raw(data)` and `_fetch_query_raw()`.
- The existing `MOCK_QUERIES` list has 7 realistic queries with varied states; keep it.
- `save_screenshot(path)` produces SVG. For PNG, use `save_screenshot(path)` with a `.svg` extension and then convert externally, or use `app.export_screenshot()` which returns SVG string.

- [ ] **Step 1: Read the current `on_mount()` and `_update_table()`**

Read `src/trinops/tui/app.py` to understand the current initialization flow. The `MockTrinopsApp` must replicate the column setup, default sort, and caret update without starting timers or workers.

- [ ] **Step 2: Rewrite `MockTrinopsApp.on_mount()` to match current TUI**

Replace the mock's `on_mount()` to use `_COLUMN_LABELS`, capture column keys, set `_sort_col` and `_sort_reverse`, call `_update_column_carets()`, and call `_update_empty_message()`. Do not start timers or schedule workers.

```python
class MockTrinopsApp(TrinopsApp):
    """TrinopsApp subclass that uses mock data instead of a real Trino connection."""

    def on_mount(self) -> None:
        table = self.query_one("#query-table", DataTable)
        col_keys = table.add_columns(*self._COLUMN_LABELS)
        table.cursor_type = "row"
        self._sort_col = col_keys[3]  # Elapsed
        self._sort_reverse = True
        self._queries = MOCK_QUERIES
        self._loaded = True
        # Use monotonic() so status bar shows "0s ago" instead of a huge number
        self._last_refresh = time.monotonic()
        self._refreshing = False
        # Bind kill key (the real on_mount does this conditionally on allow_kill)
        if self._profile.allow_kill:
            self.bind("k", "kill_query", description="Kill query")
        self._update_table()
        self._update_column_carets()
        self._update_empty_message()
        self._update_status_bar()
        table.focus()

    def _fetch_query_raw(self, query_id: str) -> dict | None:
        """Return mock detail data instead of hitting the Trino API."""
        if self._mock_detail_data is not None:
            return self._mock_detail_data
        # Fall back to MOCK_DETAIL_DATA for any query
        return MOCK_DETAIL_DATA
```

- [ ] **Step 3: Add a `MOCK_DETAIL_DATA` dict for the detail pane screenshots**

The detail pane uses raw REST API response dicts (not `QueryInfo` objects). Create a `MOCK_DETAIL_DATA` dict that matches the format in `tests/test_detail_tabs.py:FULL_QUERY_INFO`. Use data from the first mock query (the analytics revenue query).

```python
MOCK_DETAIL_DATA = {
    "queryId": "20260311_091522_00142_abcde",
    "state": "RUNNING",
    "queryType": "SELECT",
    "query": "SELECT customer_id, SUM(order_total) AS revenue\nFROM warehouse.sales.orders\nWHERE order_date >= DATE '2026-01-01'\nGROUP BY customer_id\nORDER BY revenue DESC\nLIMIT 100",
    "session": {
        "user": "analytics",
        "source": "trinops",
        "catalog": "warehouse",
        "schema": "sales",
    },
    "resourceGroupId": ["global", "analytics"],
    "queryStats": {
        "createTime": "2026-03-11T09:15:22.000Z",
        "endTime": None,
        "elapsedTime": "12.87s",
        "queuedTime": "0.10s",
        "planningTime": "0.42s",
        "executionTime": "12.35s",
        "totalCpuTime": "34.21s",
        "physicalInputDataSize": "1073741824B",
        "physicalInputPositions": 48291053,
        "processedInputDataSize": "536870912B",
        "processedInputPositions": 24145526,
        "outputDataSize": "8388608B",
        "outputPositions": 100,
        "physicalWrittenDataSize": "0B",
        "spilledDataSize": "0B",
        "peakUserMemoryReservation": "268435456B",
        "peakTotalMemoryReservation": "536870912B",
        "cumulativeUserMemory": 500000000.0,
        "completedTasks": 38,
        "totalTasks": 42,
        "completedDrivers": 380,
        "totalDrivers": 420,
    },
    "inputs": [
        {
            "catalogName": "warehouse",
            "schema": "sales",
            "table": "orders",
            "columns": [
                {"name": "customer_id", "type": "BIGINT"},
                {"name": "order_total", "type": "DECIMAL(12,2)"},
                {"name": "order_date", "type": "DATE"},
            ],
        },
    ],
    "errorCode": None,
    "failureInfo": None,
    "warnings": [],
}
```

Also create a `MOCK_FAILED_DETAIL` for the errors tab screenshot, matching the failed query in `MOCK_QUERIES`:

```python
MOCK_FAILED_DETAIL = {
    "queryId": "20260311_090830_00051_efghi",
    "state": "FAILED",
    "queryType": "SELECT",
    "query": "SELECT * FROM hive.raw.events WHERE event_date = CURRENT_DATE AND payload.action = 'purchase'",
    "session": {"user": "analytics", "source": "trinops"},
    "queryStats": {
        "createTime": "2026-03-11T09:08:30.000Z",
        "endTime": "2026-03-11T09:08:32.300Z",
        "elapsedTime": "2.30s",
        "queuedTime": "0.10s",
        "totalCpuTime": "1.20s",
        "peakUserMemoryReservation": "67108864B",
        "peakTotalMemoryReservation": "134217728B",
        "cumulativeUserMemory": 100000000.0,
        "processedInputPositions": 0,
        "physicalInputDataSize": "0B",
        "completedTasks": 1,
        "totalTasks": 1,
        "completedDrivers": 2,
        "totalDrivers": 2,
    },
    "errorCode": {"code": 1, "name": "SYNTAX_ERROR", "type": "USER_ERROR"},
    "failureInfo": {"message": "line 1:72: Column 'payload.action' cannot be resolved"},
    "warnings": [],
}
```

- [ ] **Step 4: Write the multi-screenshot capture function**

Replace the single `take_screenshot()` with a function that captures all 7 SVG screenshots. Each scenario drives the TUI to a specific state using `pilot.press()` and `pilot.pause()`.

```python
import os

OUTPUT_DIR = "docs/screenshots"


async def capture_all():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    profile = ConnectionProfile(
        server="trino.example.com:443",
        user="analytics",
        allow_kill=True,
        confirm_kill=True,
    )

    # 1. Query list (default view with sort caret)
    app = MockTrinopsApp(profile=profile, interval=30.0)
    async with app.run_test(size=(140, 32)) as pilot:
        await pilot.pause()
        app.save_screenshot(f"{OUTPUT_DIR}/query-list.svg")

    # 2. Detail pane — Overview tab
    app = MockTrinopsApp(profile=profile, interval=30.0)
    async with app.run_test(size=(140, 42)) as pilot:
        await pilot.pause()
        app._show_detail_raw(MOCK_DETAIL_DATA)
        await pilot.pause()
        app.save_screenshot(f"{OUTPUT_DIR}/detail-overview.svg")

    # 3. Detail pane — Stats tab
    app = MockTrinopsApp(profile=profile, interval=30.0)
    async with app.run_test(size=(140, 42)) as pilot:
        await pilot.pause()
        app._show_detail_raw(MOCK_DETAIL_DATA)
        await pilot.pause()
        await pilot.press("right")  # Switch to Stats tab
        await pilot.pause()
        app.save_screenshot(f"{OUTPUT_DIR}/detail-stats.svg")

    # 4. Detail pane — Tables tab
    app = MockTrinopsApp(profile=profile, interval=30.0)
    async with app.run_test(size=(140, 42)) as pilot:
        await pilot.pause()
        app._show_detail_raw(MOCK_DETAIL_DATA)
        await pilot.pause()
        await pilot.press("right")  # Stats
        await pilot.press("right")  # Tables
        await pilot.pause()
        app.save_screenshot(f"{OUTPUT_DIR}/detail-tables.svg")

    # 5. Detail pane — Errors tab (failed query)
    app = MockTrinopsApp(profile=profile, interval=30.0)
    async with app.run_test(size=(140, 42)) as pilot:
        await pilot.pause()
        app._show_detail_raw(MOCK_FAILED_DETAIL)
        await pilot.pause()
        await pilot.press("right")  # Stats
        await pilot.press("right")  # Tables
        await pilot.press("right")  # Errors
        await pilot.pause()
        app.save_screenshot(f"{OUTPUT_DIR}/detail-errors.svg")

    # 6. Kill confirmation dialog
    app = MockTrinopsApp(profile=profile, interval=30.0)
    async with app.run_test(size=(140, 32)) as pilot:
        await pilot.pause()
        await pilot.press("k")  # Trigger kill dialog on first row
        await pilot.pause()
        app.save_screenshot(f"{OUTPUT_DIR}/kill-confirm.svg")

    # 7. Empty state
    app = MockTrinopsApp(profile=profile, interval=30.0)
    app._mock_empty = True  # Flag checked in on_mount
    async with app.run_test(size=(140, 32)) as pilot:
        await pilot.pause()
        app.save_screenshot(f"{OUTPUT_DIR}/empty-state.svg")
```

Add the `_mock_empty` support to `MockTrinopsApp.on_mount()`:

```python
    _mock_empty: bool = False
    _mock_detail_data: dict | None = None

    def on_mount(self) -> None:
        table = self.query_one("#query-table", DataTable)
        col_keys = table.add_columns(*self._COLUMN_LABELS)
        table.cursor_type = "row"
        self._sort_col = col_keys[3]
        self._sort_reverse = True
        if self._mock_empty:
            self._queries = []
        else:
            self._queries = MOCK_QUERIES
        self._loaded = True
        self._last_refresh = time.monotonic()
        self._refreshing = False
        if self._profile.allow_kill:
            self.bind("k", "kill_query", description="Kill query")
        self._update_table()
        self._update_column_carets()
        self._update_empty_message()
        self._update_status_bar()
        if not self._mock_empty:
            table.focus()

    def _fetch_query_raw(self, query_id: str) -> dict | None:
        """Return mock detail data instead of hitting the Trino API."""
        if self._mock_detail_data is not None:
            return self._mock_detail_data
        return MOCK_DETAIL_DATA
```

- [ ] **Step 5: Update `__main__` block and also keep backward-compatible single screenshot**

```python
if __name__ == "__main__":
    asyncio.run(capture_all())
```

- [ ] **Step 6: Run the script and verify all 7 SVGs are generated**

Run: `uv run python scripts/screenshot.py`
Expected: 7 `.svg` files in `docs/screenshots/`:
- `query-list.svg`
- `detail-overview.svg`
- `detail-stats.svg`
- `detail-tables.svg`
- `detail-errors.svg`
- `kill-confirm.svg`
- `empty-state.svg`

Visually inspect at least 2-3 SVGs by opening them in a browser to confirm they render correctly.

- [ ] **Step 7: Commit**

```bash
git add scripts/screenshot.py docs/screenshots/
git commit -m "feat(screenshots): expand screenshot script for website documentation"
```

---

### Task 2: Generate hero PNG and GIF

Convert the query-list SVG to PNG for social sharing, and assemble an animated GIF from multiple screenshot frames.

**Files:**
- Modify: `scripts/screenshot.py`

**Dependencies:** Task 1 must be complete. Requires `cairosvg` and `Pillow` — install as dev dependencies.

- [ ] **Step 1: Add cairosvg and Pillow as dev dependencies**

Run: `uv add --dev cairosvg pillow`

- [ ] **Step 2: Add PNG conversion function**

```python
def svg_to_png(svg_path: str, png_path: str, scale: float = 2.0) -> None:
    """Convert an SVG file to PNG at the given scale factor."""
    import cairosvg
    cairosvg.svg2png(url=svg_path, write_to=png_path, scale=scale)
```

- [ ] **Step 3: Add GIF assembly function**

```python
def assemble_gif(png_paths: list[str], gif_path: str, duration_ms: int = 1500) -> None:
    """Combine multiple PNGs into an animated GIF."""
    from PIL import Image
    frames = [Image.open(p) for p in png_paths]
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
    )
```

- [ ] **Step 4: Generate hero assets in `capture_all()`**

Add to the end of `capture_all()`:

```python
    # Hero PNG (for OG image / social cards)
    svg_to_png(f"{OUTPUT_DIR}/query-list.svg", f"{OUTPUT_DIR}/hero.png")

    # Hero GIF — sequence: load → detail → tabs → sort (matches spec)
    gif_frames = [
        f"{OUTPUT_DIR}/query-list.svg",       # load
        f"{OUTPUT_DIR}/detail-overview.svg",   # detail
        f"{OUTPUT_DIR}/detail-stats.svg",      # tabs (Stats)
        f"{OUTPUT_DIR}/detail-tables.svg",     # tabs (Tables)
        f"{OUTPUT_DIR}/query-list.svg",        # back to list (sort visible)
    ]
    # Convert each frame to a temp PNG in an isolated temp directory
    import tempfile
    tmpdir = tempfile.mkdtemp(prefix="trinops-hero-")
    temp_pngs = []
    for i, svg in enumerate(gif_frames):
        tmp = os.path.join(tmpdir, f"frame_{i}.png")
        svg_to_png(svg, tmp, scale=1.5)
        temp_pngs.append(tmp)
    assemble_gif(temp_pngs, f"{OUTPUT_DIR}/hero.gif", duration_ms=2000)
    import shutil
    shutil.rmtree(tmpdir)
```

- [ ] **Step 5: Run and verify**

Run: `uv run python scripts/screenshot.py`
Expected: `docs/screenshots/hero.png` and `docs/screenshots/hero.gif` exist alongside the SVGs. Open `hero.gif` in a browser to confirm animation cycles through query list → detail overview → detail stats → back.

- [ ] **Step 6: Commit**

```bash
git add scripts/screenshot.py docs/screenshots/hero.png docs/screenshots/hero.gif pyproject.toml uv.lock
git commit -m "feat(screenshots): add hero PNG and animated GIF generation"
```

---

## Chunk 2: MkDocs Scaffolding and Theme (website branch)

### Task 3: Create orphan website branch with MkDocs skeleton

Create the `website` branch as an orphan (no shared history with `main`), add `mkdocs.yml`, `requirements-site.txt`, and a minimal `docs/index.md` that builds successfully.

**Files:**
- Create: `mkdocs.yml`
- Create: `requirements-site.txt`
- Create: `docs/index.md`
- Create: `docs/docs/getting-started.md` (and 5 other placeholder docs pages)

- [ ] **Step 1: Create orphan branch**

```bash
git checkout --orphan website
git rm -rf .
```

This removes all tracked files from the working tree. The branch has no commits yet.

- [ ] **Step 2: Create `requirements-site.txt`**

```
mkdocs>=1.6
mkdocs-material>=9.5
```

- [ ] **Step 3: Create `mkdocs.yml`**

```yaml
site_name: trino.ps
site_url: https://trino.ps
site_description: Trino query monitoring from the terminal
site_author: Loki Coyote

repo_url: https://github.com/lokkju/trinops
repo_name: lokkju/trinops

theme:
  name: material
  custom_dir: docs/overrides
  palette:
    scheme: slate
  font:
    code: JetBrains Mono
  features:
    - navigation.instant
    - navigation.instant.progress
    - navigation.tabs
    - navigation.sections
    - navigation.top
    - search.suggest
    - search.highlight
    - content.code.copy
    - content.tabs.link

extra_css:
  - overrides/assets/stylesheets/custom.css

extra:
  social:
    - icon: fontawesome/brands/github
      link: https://github.com/lokkju/trinops
    - icon: fontawesome/brands/python
      link: https://pypi.org/project/trinops/

nav:
  - Home: index.md
  - Documentation:
    - Getting Started: docs/getting-started.md
    - TUI Dashboard: docs/tui.md
    - Schema Search: docs/schema.md
    - Configuration: docs/configuration.md
    - CLI Reference: docs/cli.md
    - Python Library: docs/library.md

markdown_extensions:
  - admonition
  - pymdownx.details
  - pymdownx.superfences
  - pymdownx.tabbed:
      alternate_style: true
  - pymdownx.highlight:
      anchor_linenums: true
  - pymdownx.inlinehilite
  - pymdownx.snippets
  - attr_list
  - md_in_html
  - tables
  - toc:
      permalink: true
```

- [ ] **Step 4: Create minimal `docs/index.md`**

No custom template yet — the landing page template is created in Task 5. Use default layout for now.

```markdown
# trino.ps

Trino query monitoring from the terminal.
```

- [ ] **Step 5: Create placeholder docs pages**

Create each of these with a single heading so the nav doesn't break:

`docs/docs/getting-started.md`:
```markdown
# Getting Started
```

`docs/docs/tui.md`:
```markdown
# TUI Dashboard
```

`docs/docs/schema.md`:
```markdown
# Schema Search
```

`docs/docs/configuration.md`:
```markdown
# Configuration
```

`docs/docs/cli.md`:
```markdown
# CLI Reference
```

`docs/docs/library.md`:
```markdown
# Python Library
```

- [ ] **Step 6: Create override directories and placeholder files**

```bash
mkdir -p docs/overrides/assets/stylesheets
mkdir -p docs/overrides/assets/javascripts
mkdir -p docs/assets/screenshots
```

Create `docs/overrides/assets/stylesheets/custom.css` as an empty file (populated in Task 4).

Do **not** create `docs/overrides/main.html` yet — MkDocs Material would use an empty `main.html` override as the base template for all pages, breaking the entire site. Task 5 creates this file with proper content.

- [ ] **Step 7: Verify build**

```bash
pip install -r requirements-site.txt
mkdocs build
```

Expected: `site/` directory created with `index.html` and docs subpages. No build errors.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat(website): initial MkDocs Material skeleton"
```

---

### Task 4: Custom theme — Trino palette, JetBrains Mono, installer selector

Apply the Trino-native color palette via CSS overrides and implement the package manager selector JavaScript.

**Files:**
- Create: `docs/overrides/assets/stylesheets/custom.css`
- Create: `docs/overrides/assets/javascripts/installer-selector.js`
- Modify: `mkdocs.yml` (add extra_javascript)

**Context for implementer:**
- MkDocs Material uses CSS custom properties for theming. The dark scheme (`slate`) exposes `--md-primary-fg-color`, `--md-accent-fg-color`, etc. Override these in `custom.css`.
- Material's instant navigation fires `document$` events (RxJS observable). For the installer selector JS to work across navigation, subscribe to `document$` or use MutationObserver on the content area.
- Code blocks that should be rewritten by the selector must be marked with a data attribute. Use `<div class="install-command" data-uvx="uvx trinops top" data-pipx="pipx run trinops top" data-pip="trinops top">` wrappers in markdown (via `attr_list` extension) or in the landing page HTML.

- [ ] **Step 1: Write `custom.css` with Trino palette**

```css
/* Trino-native palette */
:root {
  --md-primary-fg-color: #dd00a1;
  --md-primary-fg-color--light: #f472b6;
  --md-primary-fg-color--dark: #aa0080;
  --md-accent-fg-color: #f472b6;
}

[data-md-color-scheme="slate"] {
  --md-default-bg-color: #1d1f3e;
  --md-default-bg-color--light: #252850;
  --md-code-bg-color: #0d1117;
  --md-code-fg-color: #e6edf3;
  --md-typeset-a-color: #7c3aed;
}

/* JetBrains Mono for all code */
.md-typeset code,
.md-typeset pre code,
.md-typeset kbd {
  font-family: "JetBrains Mono", monospace;
}

/* Brand mark styling */
.trinops-brand {
  font-family: "JetBrains Mono", monospace;
  font-size: 3rem;
  font-weight: 700;
  color: #dd00a1;
}

/* Package manager selector pill */
.installer-selector {
  display: inline-flex;
  background: var(--md-code-bg-color);
  border-radius: 6px 6px 0 0;
  overflow: hidden;
  font-size: 0.75rem;
  margin-bottom: -1px;
}

.installer-selector button {
  background: none;
  border: none;
  color: #888;
  padding: 6px 14px;
  cursor: pointer;
  font-family: "JetBrains Mono", monospace;
  font-size: 0.75rem;
  border-right: 1px solid #333;
}

.installer-selector button:last-child {
  border-right: none;
}

.installer-selector button.active {
  background: #dd00a1;
  color: #fff;
  font-weight: 700;
}

/* Footer attribution */
.md-footer-meta {
  background: #0d1117;
}
```

- [ ] **Step 2: Write `installer-selector.js`**

```javascript
(function () {
  const STORAGE_KEY = "trinops-installer";
  const INSTALLERS = {
    uvx: { prefix: "uvx ", install: null },
    pipx: { prefix: "pipx run ", install: null },
    pip: { prefix: "", install: "pip install trinops" },
  };

  function getInstaller() {
    return localStorage.getItem(STORAGE_KEY) || "uvx";
  }

  function setInstaller(name) {
    localStorage.setItem(STORAGE_KEY, name);
    applyInstaller(name);
  }

  function applyInstaller(name) {
    // Update selector buttons
    document.querySelectorAll(".installer-selector button").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.installer === name);
    });

    // Update code blocks marked with data-install-command
    document.querySelectorAll("[data-install-command]").forEach((el) => {
      const cmd = el.dataset.installCommand;
      const installer = INSTALLERS[name];
      if (installer.install && cmd === "install") {
        el.textContent = installer.install;
      } else {
        el.textContent = installer.prefix + "trinops " + cmd;
      }
    });
  }

  function init() {
    // Bind click handlers on selector buttons
    document.querySelectorAll(".installer-selector button").forEach((btn) => {
      btn.addEventListener("click", () => setInstaller(btn.dataset.installer));
    });
    applyInstaller(getInstaller());
  }

  // Support MkDocs Material instant navigation
  if (typeof document$ !== "undefined") {
    document$.subscribe(() => init());
  } else {
    document.addEventListener("DOMContentLoaded", init);
  }
})();
```

- [ ] **Step 3: Add extra_javascript to `mkdocs.yml`**

Add under the existing `extra_css`:

```yaml
extra_javascript:
  - overrides/assets/javascripts/installer-selector.js
```

- [ ] **Step 4: Verify build**

Run: `mkdocs build`
Expected: Build succeeds. Check `site/overrides/assets/javascripts/installer-selector.js` and `site/overrides/assets/stylesheets/custom.css` exist in the build output.

- [ ] **Step 5: Test locally**

Run: `mkdocs serve`
Open `http://localhost:8000` in a browser. Verify:
- Dark background matches #1d1f3e
- Code blocks have #0d1117 background
- Links are purple (#7c3aed)
- JetBrains Mono loads for code blocks (check DevTools → Network → Fonts)

- [ ] **Step 6: Commit**

```bash
git add docs/overrides/ mkdocs.yml
git commit -m "feat(website): Trino palette, JetBrains Mono, installer selector"
```

---

### Task 5: Landing page template and content

Build the custom landing page at `docs/index.md` using a Material theme override template. The landing page breaks out of the standard docs layout to show hero, feature cards, screenshot gallery, quick start, and footer.

**Files:**
- Create: `docs/overrides/home.html`
- Modify: `docs/index.md`

**Context for implementer:**
- MkDocs Material supports per-page custom templates via frontmatter: `template: home.html`. The template extends `main.html` and overrides blocks.
- The landing page HTML uses Material's CSS grid system and utility classes where possible, falling back to custom CSS in `custom.css` for the feature cards and screenshot gallery.
- Screenshot SVGs will be referenced from `assets/screenshots/`. They won't exist yet on this branch — use `<img>` tags with the paths so they work once assets are committed.
- The installer selector buttons and `[data-install-command]` spans must be present for the JS from Task 4 to work.

- [ ] **Step 1: Create `docs/overrides/home.html`**

This template extends Material's base, hides the sidebar and TOC, and renders the landing page content from the markdown file's HTML.

```html
{% extends "main.html" %}

{% block tabs %}
  {{ super() }}
{% endblock %}

{% block content %}
  {{ page.content }}
{% endblock %}

{% block sidebar %}{% endblock %}
{% block toc %}{% endblock %}
```

- [ ] **Step 2: Write `docs/index.md` with full landing page content**

Write the complete landing page markdown/HTML. This is a long file (~200 lines) because it contains the hero, feature cards, screenshot gallery, quick start, and footer sections as inline HTML within markdown.

The file must include:
- Frontmatter: `template: home.html`
- Hero section with `.trinops-brand`, tagline, animated GIF (hero.gif), installer selector pill, install command
- Two feature cards (CLI, TUI Dashboard) in a responsive grid
- 2x2 screenshot gallery with SVG `<img>` tags
- Quick start steps with `[data-install-command]` spans for the selector
- Footer with attribution line

Use `<div markdown>` blocks where markdown content is needed inside HTML containers. Use inline HTML for layout-critical sections (hero, cards, gallery).

Reference screenshots as: `assets/screenshots/query-list.svg`, `assets/screenshots/detail-overview.svg`, etc.

Reference hero as: `assets/screenshots/hero.gif`

- [ ] **Step 3: Add landing-page-specific CSS to `custom.css`**

Append styles for the hero section, feature cards grid, screenshot gallery grid, quick start section, and responsive breakpoints. Feature cards should be `display: grid; grid-template-columns: 1fr 1fr;` with a `@media (max-width: 768px)` rule that switches to single column.

- [ ] **Step 4: Verify build and local preview**

Run: `mkdocs serve`
Open `http://localhost:8000`. Verify:
- Landing page renders without sidebar/TOC
- Hero section centered with brand name
- Feature cards display side by side (shrink browser to verify mobile stack)
- Screenshot placeholders show as broken images (expected — assets not yet committed)
- Installer selector toggles between uvx/pipx/pip and rewrites visible commands
- Quick start section readable
- Footer attribution visible

- [ ] **Step 5: Commit**

```bash
git add docs/overrides/home.html docs/index.md docs/overrides/assets/stylesheets/custom.css
git commit -m "feat(website): landing page with hero, features, gallery, and quick start"
```

---

## Chunk 3: Documentation Pages and CI/CD (website branch)

### Task 6: Write all six documentation pages

Write the full content for each docs page. Each page is self-contained markdown.

**Files:**
- Modify: `docs/docs/getting-started.md`
- Modify: `docs/docs/tui.md`
- Modify: `docs/docs/schema.md`
- Modify: `docs/docs/configuration.md`
- Modify: `docs/docs/cli.md`
- Modify: `docs/docs/library.md`

**Context for implementer:**
- Read the spec's "Documentation Pages" section (lines 120-192) for the complete content requirements per page.
- Read `src/trinops/cli/commands.py` for exact CLI flags and option names.
- Read `src/trinops/config.py` for `ConnectionProfile` fields and defaults.
- Read `src/trinops/progress/progress.py` for `TrinoProgress` constructor and methods.
- Read `src/trinops/tui/app.py` for TUI keybindings (BINDINGS list) and `src/trinops/tui/detail.py` for detail pane bindings.
- Use MkDocs Material admonitions (`!!! tip`, `!!! note`, `!!! warning`) sparingly for important callouts.
- Use `pymdownx.tabbed` for the uvx/pipx/pip install variants on the Getting Started page.
- Reference screenshots with relative paths: `../assets/screenshots/query-list.svg`

- [ ] **Step 1: Write `docs/docs/getting-started.md`**

Content:
- Installation section with tabbed code blocks (uvx/pipx/pip)
- `trinops config init` walkthrough — interactive prompts and non-interactive flags
- Environment variable alternative (TRINOPS_SERVER, TRINOPS_USER, TRINOPS_AUTH, TRINOPS_CATALOG, TRINOPS_SCHEMA)
- First run: `trinops top` with a note about what to expect
- Verifying connection: `trinops queries` should return results
- Note about port defaults (443 for https, 8080 for http)

- [ ] **Step 2: Write `docs/docs/tui.md`**

Content:
- Opening paragraph: "The TUI dashboard is trinops' flagship feature — a live-updating terminal interface for monitoring Trino queries."
- Dashboard layout overview (cluster header, query table, detail pane, status bar, footer)
- Screenshot: `../assets/screenshots/query-list.svg`
- Keybindings tables — two tables: "Global" and "Detail Pane"
- Column descriptions (Query ID, State, User, Elapsed, Rows, Memory, SQL)
- Sorting: click headers, default Elapsed descending, caret indicators
- Detail pane section: Enter to open, Escape to close, tabs (Overview, Stats, Tables, Errors)
- Screenshots per tab: `detail-overview.svg`, `detail-stats.svg`, `detail-tables.svg`, `detail-errors.svg`
- Kill workflow: `k` to kill, confirmation dialog, works from table or detail pane
- Screenshot: `kill-confirm.svg`
- Copy to clipboard: `c` copies current tab content
- Empty state: screenshot `empty-state.svg`
- Error handling: auth failures and connection errors displayed in status bar

- [ ] **Step 3: Write `docs/docs/schema.md`**

Content:
- Opening: "You inherited a Trino cluster with dozens of catalogs. trinops schema helps you find what you need."
- `schema refresh` — fetch and cache metadata (`--catalog` for single, `--all` for discovery)
- Where cache lives (`~/.config/trinops/schema/`)
- `schema search` — glob patterns (`"order*"`, `"*customer*"`), `--columns` for column search, `--json` for machine output
- `schema show` — fully qualified table name, column types, nullable
- `schema list` — list cached catalogs with table/column counts and fetch timestamps
- Scripting example: `trinops schema search --json "orders" | jq '.[] | .catalog + "." + .schema + "." + .table'`

- [ ] **Step 4: Write `docs/docs/configuration.md`**

Content:
- Config file: `~/.config/trinops/config.toml`
- Example config file showing default and named profiles
- All profile fields in a table: field, type, default, description (server, scheme, user, auth, catalog, schema, password, password_cmd, jwt_token, query_limit, allow_kill, confirm_kill)
- Auth methods section — one subsection per method:
  - none: no configuration needed
  - basic: `trinops config set auth basic`, password stored in system keyring, or `password_cmd` for scripted retrieval
  - jwt: `trinops config set jwt_token <path-or-value>`
  - oauth2: `trinops config set auth oauth2` then `trinops auth login` for interactive flow
  - kerberos: requires valid Kerberos ticket
- Environment variables table: TRINOPS_SERVER, TRINOPS_SCHEME, TRINOPS_USER, TRINOPS_AUTH, TRINOPS_CATALOG, TRINOPS_SCHEMA
- `config set` / `config show` usage with examples
- Multi-profile workflow: named profiles, `--profile prod` flag

- [ ] **Step 5: Write `docs/docs/cli.md`**

Content:
- Each command as an `##` heading
- For each: synopsis (code block), flags/options table, examples, sample output where useful
- Commands:
  - `trinops queries` — flags: `--state`, `--query-user`, `--json`, `--select`, `--limit`, `--profile`, `--server`, `--user`, `--auth`
  - `trinops query <id>` — flags: `--json`, `--select`, `--profile`
  - `trinops kill <id>` — flags: `--profile`, `--force`
  - `trinops tui` / `trinops top` — flags: `--interval`, `--profile`
  - `trinops config init` — flags: `--server`, `--user`, `--auth`, `--profile`
  - `trinops config set <key> <value>` — flags: `--profile`
  - `trinops config show` — flags: `--profile`
  - `trinops auth status` / `trinops auth login` — flags: `--profile`
  - `trinops schema refresh` — flags: `--catalog`, `--all`, `--profile`
  - `trinops schema search <pattern>` — flags: `--columns`, `--json`, `--catalog`, `--profile`
  - `trinops schema show <table>` — flags: `--json`, `--profile`
  - `trinops schema list` — flags: `--profile`
  - `trinops --version`

- [ ] **Step 6: Write `docs/docs/library.md`**

Content:
- Opening: "trinops includes a Python library for embedding Trino query progress tracking in your scripts and applications."
- Installation: `pip install trinops` or `pip install trinops[tqdm]`
- Cursor mode example (TrinoProgress wrapping a cursor)
- Standalone mode example (TrinoProgress wrapping a connection + query_id)
- Display backends:
  - stderr (default) — compact progress bar
  - tqdm — `pip install trinops[tqdm]`, richer bar
  - web — browser-based progress UI
- QueryStats and StageStats dataclasses — key fields
- Note: "The progress library is under active development. The polling API uses /v1/query/{id} which is not a stable Trino API."

- [ ] **Step 7: Verify full build**

Run: `mkdocs build`
Expected: Build succeeds. Note: screenshot image references (e.g., `../assets/screenshots/query-list.svg`) will produce broken image links since assets are committed in Task 7. This is expected. Use `mkdocs build --strict` only after Task 7 completes.

- [ ] **Step 8: Commit**

```bash
git add docs/docs/
git commit -m "feat(website): complete documentation for all six pages"
```

---

### Task 7: Copy screenshots to website branch

Copy the generated screenshot assets from `main` branch into the `website` branch.

**Files:**
- Create: `docs/assets/screenshots/*.svg`
- Create: `docs/assets/screenshots/hero.png`
- Create: `docs/assets/screenshots/hero.gif`

- [ ] **Step 1: Copy screenshots from main branch**

From the `website` branch, checkout the screenshot files from `main`:

```bash
git checkout main -- docs/screenshots/
mv docs/screenshots/* docs/assets/screenshots/
rm -rf docs/screenshots/
```

- [ ] **Step 2: Verify all expected files are present**

```bash
ls docs/assets/screenshots/
```

Expected: 7 SVGs (`query-list.svg`, `detail-overview.svg`, `detail-stats.svg`, `detail-tables.svg`, `detail-errors.svg`, `kill-confirm.svg`, `empty-state.svg`) plus `hero.png` and `hero.gif`. If any are missing, re-run `scripts/screenshot.py` on `main` branch and repeat Step 1.

- [ ] **Step 3: Verify images render in local preview**

Run: `mkdocs serve`
Open `http://localhost:8000`. Verify:
- Landing page hero GIF animates
- Screenshot gallery shows all 4 SVGs
- TUI docs page shows all screenshots inline
- No broken image links

- [ ] **Step 4: Commit**

```bash
git add docs/assets/screenshots/
git commit -m "feat(website): add generated TUI screenshots and hero assets"
```

---

### Task 8: GitHub Actions deploy workflow

Create the GitHub Actions workflow that builds the MkDocs site and deploys to Cloudflare Pages on push to the `website` branch.

**Files:**
- Create: `.github/workflows/deploy-site.yml`

**Context for implementer:**
- Use `cloudflare/wrangler-action@v3` for deployment. It needs `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` as secrets.
- The Cloudflare Pages project must be created manually first (or via Wrangler CLI). Project name: `trino-ps`. Production branch: `website`.
- Build output directory: `site/` (MkDocs default).

- [ ] **Step 1: Write `.github/workflows/deploy-site.yml`**

```yaml
name: Deploy Website

on:
  push:
    branches:
      - website

permissions:
  contents: read

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: pip install -r requirements-site.txt

      - name: Build site
        run: mkdocs build --strict

      - name: Deploy to Cloudflare Pages
        uses: cloudflare/wrangler-action@v3
        with:
          apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          accountId: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          command: pages deploy site --project-name=trino-ps
```

- [ ] **Step 2: Verify workflow syntax**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/deploy-site.yml'))"`
Expected: No errors.

Or if `actionlint` is available: `actionlint .github/workflows/deploy-site.yml`

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/deploy-site.yml
git commit -m "ci(website): add GitHub Actions workflow for Cloudflare Pages deployment"
```

- [ ] **Step 4: Run strict build to verify everything**

Now that Task 7 has committed screenshots, run a strict build to catch any remaining issues:

```bash
mkdocs build --strict
```

Expected: Clean build with zero warnings. All image references resolve, all nav links valid.

**Manual setup required (not automated):** Before the first push to `website`, the user must:
- Create a Cloudflare Pages project named `trino-ps` (via dashboard or `npx wrangler pages project create trino-ps --production-branch website`)
- Add GitHub repository secrets: `CLOUDFLARE_API_TOKEN` (with "Cloudflare Pages: Edit" permission) and `CLOUDFLARE_ACCOUNT_ID`
