## Schema Raw JSON Output Without Table Argument

**Priority:** Medium
**Discovered:** 2026-03-16, during website brainstorming session

### Problem

`schema show --json` requires a table name. There's no way to dump the full cached schema as JSON for external tooling, scripting, or piping to jq.

### Proposed Solution

When `--json` is passed without a table argument, dump the entire cache for the current profile (or specified `--catalog`) as JSON to stdout. This pairs with the nested navigation work (see `schema-show-nested-navigation.md`).

### Affected Files

- `src/trinops/cli/commands.py` — `schema_show` command
- `src/trinops/schema/cache.py` — full dump read method
