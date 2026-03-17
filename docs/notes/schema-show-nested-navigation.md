## Schema Show: Nested Navigation

**Priority:** Medium
**Discovered:** 2026-03-16, during website brainstorming session

### Problem

`schema show` currently only works with fully qualified table names. There's no way to browse the hierarchy interactively or dump a full catalog.

### Proposed Changes

1. `schema show <catalog>` — list schemas in that catalog
2. `schema show <catalog>.<schema>` — list tables in that schema
3. `schema show <catalog>.<schema>.<table>` — show columns (current behavior)
4. `schema show --json` (no argument) — dump everything in the cache as raw JSON

Each level accepts `--json` for machine-readable output.

### Affected Files

- `src/trinops/cli/commands.py` — `schema_show` command
- `src/trinops/schema/search.py` — may need new lookup methods per hierarchy level
- `src/trinops/schema/cache.py` — raw dump method
- `tests/test_schema_search.py` — new test cases per level
