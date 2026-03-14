# Schema Cache and Search

**GitHub Issue:** #3

**Goal:** Cache Trino catalog/schema/table/column metadata locally as JSON files and provide CLI search. This is a foundational layer that will later be consumed by MCP (issue #4), LSP, and TUI schema browsing.

**Architecture:** New `src/trinops/schema/` package with three concerns: fetching metadata from Trino via DB-API, managing the JSON file cache, and searching cached metadata via in-memory index. CLI commands in a new `schema` subcommand group.

## Cache Storage

JSON files at `~/.cache/trinops/schemas/<profile>/`, one file per catalog. The `<profile>` directory name is the profile name from config (e.g., `prod`, `staging`). The unnamed default profile uses the directory name `default`.

```
~/.cache/trinops/schemas/
  default/
    tpch.json
    hive.json
  prod/
    hive.json
    iceberg.json
```

### JSON Format (per catalog)

```json
{
  "catalog": "tpch",
  "profile": "default",
  "fetched_at": "2026-03-14T12:00:00Z",
  "schemas": {
    "sf1": {
      "tables": {
        "lineitem": {
          "type": "TABLE",
          "columns": [
            {"name": "orderkey", "type": "INTEGER", "nullable": true},
            {"name": "quantity", "type": "DOUBLE", "nullable": true}
          ]
        }
      }
    }
  }
}
```

The format is intentionally simple and inspectable with `jq`. Consumers (MCP, LSP) build their own in-memory indexes from these files as needed.

## Fetching

The fetcher connects to Trino via the `trino` DB-API client (`trino.dbapi.connect()`) using the existing `ConnectionProfile`. Auth mapping from `ConnectionProfile` to `trino.dbapi.connect()`:

- `auth=none`: `trino.dbapi.connect(user=profile.user)` with no auth parameter
- `auth=basic`: `trino.dbapi.connect(user=profile.user, http_scheme="https", auth=trino.auth.BasicAuthentication(profile.user, profile.password))`
- `auth=jwt`: `trino.dbapi.connect(user=profile.user, http_scheme="https", auth=trino.auth.JWTAuthentication(token))`
- `auth=oauth2`: `trino.dbapi.connect(user=profile.user, http_scheme="https", auth=trino.auth.OAuth2Authentication())`
- `auth=kerberos`: `trino.dbapi.connect(user=profile.user, http_scheme="https", auth=trino.auth.KerberosAuthentication(...))`

The `scheme` field from `ConnectionProfile` maps to `http_scheme`. Password resolution uses the existing `resolve_password()` from `auth.py`.

The fetcher runs three queries against `information_schema`:

1. `SELECT schema_name FROM <catalog>.information_schema.schemata` — discover schemas
2. `SELECT table_schema, table_name, table_type FROM <catalog>.information_schema.tables` — discover tables
3. `SELECT table_schema, table_name, column_name, data_type, is_nullable FROM <catalog>.information_schema.columns` — discover columns

Results are assembled into the JSON structure and written to the cache.

### Catalog Scoping

By default, `trinops schema refresh` fetches metadata for the catalog configured in the active profile (`ConnectionProfile.catalog`). If no catalog is configured, the command errors with a message to specify `--catalog` or configure one via `trinops config set catalog <name>`.

- `--catalog <name>` overrides the profile's catalog for a single refresh.
- `--all` fetches all catalogs (discovered via `SHOW CATALOGS`). Use with caution on large clusters. In `--all` mode, per-catalog errors are logged as warnings and skipped rather than failing the entire refresh (the user may lack permissions on some catalogs).

## Search

Search loads cached JSON files into memory, builds a simple index, and matches against it. The index is built per invocation for CLI use; long-lived consumers hold it in memory.

Search supports:
- **Glob patterns:** `*order*` matches table names containing "order" (uses `fnmatch`)
- **Substring matching:** patterns without glob characters (`*`, `?`, `[`) are treated as substring matches, equivalent to wrapping in `*pattern*`
- **Fully qualified names:** `tpch.sf1.lineitem` for exact lookup (dot-separated, matched structurally)

By default, search matches table names. `--columns` includes column-level matches.

## CLI Commands

### `trinops schema refresh`

Fetch and cache metadata.

```
trinops schema refresh                    # fetch profile's configured catalog
trinops schema refresh --catalog tpch     # fetch specific catalog
trinops schema refresh --all              # fetch all catalogs (SHOW CATALOGS)
```

Options: `--server`, `--profile`, `--user`, `--auth` (standard connection options).

Output: progress messages showing schemas/tables/columns fetched per catalog.

### `trinops schema search <pattern>`

Search cached metadata.

```
trinops schema search "*order*"                     # glob match on table names
trinops schema search orderkey --columns             # match column names too
trinops schema search "*order*" --catalog tpch       # scope to one catalog
trinops schema search "*order*" --json               # structured JSON output
```

Output: table of matches (catalog, schema, table, and optionally column name/type). `--json` outputs a JSON array for piping to `jq` or other tools.

### `trinops schema show <table>`

Show columns for a specific table.

```
trinops schema show lineitem                         # search across cached catalogs
trinops schema show tpch.sf1.lineitem                # fully qualified
trinops schema show lineitem --json                  # JSON output
```

Output: table of columns (name, type, nullable). `--json` outputs structured JSON. If the unqualified name matches multiple tables across catalogs/schemas, all matches are shown with their fully qualified names.

### `trinops schema list`

List cached catalogs with staleness info.

```
trinops schema list                                  # all profiles
trinops schema list --profile prod                   # specific profile
```

Output: table of cached catalogs with profile, catalog name, table count, column count, and age (e.g., "2h ago", "3d ago").

## Code Structure

New files:

- `src/trinops/schema/__init__.py`
- `src/trinops/schema/fetcher.py` — `SchemaFetcher` class. Takes a `ConnectionProfile`, connects via `trino.dbapi`, runs `information_schema` queries, returns structured dicts.
- `src/trinops/schema/cache.py` — `SchemaCache` class. Manages `~/.cache/trinops/schemas/<profile>/` directory. Read/write JSON files, list cached catalogs, report cache age.
- `src/trinops/schema/search.py` — `SchemaSearch` class. Loads cached JSON, builds in-memory index, supports glob/substring search. Returns structured results.
- `src/trinops/cli/commands.py` (modify) — Add `schema` subcommand group with `refresh`, `search`, `show`, `list` commands.

## Testing

- **Fetcher tests:** Mock the `trino.dbapi` connection. Verify correct SQL queries are generated for single catalog and `--all` modes. Verify the structured dict output matches expected format.
- **Cache tests:** Write to a temp directory. Verify JSON format, read/write round-trip, cache age reporting, per-profile isolation.
- **Search tests:** Load known JSON fixtures. Verify glob matching, substring matching, fully qualified lookups, column-level search, catalog scoping.
- **CLI tests:** Mock the fetcher/cache/search layers. Verify command output format for both table and JSON modes.

## Out of Scope

- **TUI schema browser**: deferred by design decision during brainstorming. Issue #2 already introduces significant TUI changes (tabbed detail view, new navigation model); adding a schema browser pane on top would be a separate interaction design problem. Will be added after #2 lands.
- **Automatic cache refresh / TTL**: explicit refresh only for this pass. The `fetched_at` field in the JSON format provides the foundation for TTL-based invalidation later.
- **MCP/LSP integration**: issues #4 and future work. They consume the cache and search layers built here.
- **View definitions, function metadata, or other non-table schema objects.**
