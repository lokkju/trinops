# Schema Search

You inherited a Trino cluster with dozens of catalogs, hundreds of schemas, and thousands of tables. Someone asks "where's the customer data?" and you have no idea which catalog it lives in. trinops ships an offline schema cache so you can search table and column names without hitting Trino every time.

## Workflow

The schema workflow has two phases: **refresh** (fetch metadata from Trino and cache it locally) and **search** (query the local cache).

### Refresh the cache

Fetch metadata for a single catalog:

```bash
trinops schema refresh --catalog hive
```

Or discover and fetch all catalogs at once:

```bash
trinops schema refresh --all
```

The cache is stored per-profile, so different Trino clusters keep their metadata separate. The `schema list` command shows what you have cached.

### Search for tables

Use glob patterns to find tables:

```bash
trinops schema search "customer*"
trinops schema search "*order*"
trinops schema search "analytics.page_*"
```

The pattern matches against table names by default. Results are displayed as a Rich table with catalog, schema, table name, and table type.

### Search for columns

Add `--columns` to search column names instead:

```bash
trinops schema search --columns "email"
trinops schema search --columns "*_id"
```

Column search results include the catalog, schema, table, column name, and data type.

### Limit to a specific catalog

```bash
trinops schema search "*event*" --catalog iceberg
```

### Show table details

Look up a specific table to see its columns:

```bash
trinops schema show users
trinops schema show analytics.page_views
trinops schema show hive.analytics.page_views
```

The argument can be an unqualified table name, `schema.table`, or the fully qualified `catalog.schema.table`. If the name is ambiguous, all matching tables are shown.

### List cached catalogs

```bash
trinops schema list
```

This prints a table of cached catalogs with the profile name, catalog name, table count, column count, and when the data was fetched.

## JSON output

Every search and show command supports `--json` for machine-readable output:

```bash
trinops schema search "*order*" --json
trinops schema show orders --json
```

### Scripting with jq

Combine `--json` with `jq` for pipeline-friendly queries:

```bash
# Find all tables containing "event" and extract just the fully qualified names
trinops schema search "*event*" --json | \
  jq -r '.[] | "\(.catalog).\(.schema).\(.table)"'

# List column names and types for a specific table
trinops schema show page_views --json | \
  jq -r '.[].columns[] | "\(.name)\t\(.type)"'
```

## Commands reference

| Command | Description |
|---------|-------------|
| `schema refresh` | Fetch metadata from Trino and cache locally |
| `schema search <pattern>` | Search cached table or column names using glob patterns |
| `schema show <table>` | Show columns for a specific table |
| `schema list` | List all cached catalogs |

See the [CLI Reference](cli.md) for the full set of flags on each command.
