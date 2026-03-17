# CLI Reference

Global options available on every command:

| Flag | Description |
|------|-------------|
| `--version` / `-V` | Print version and exit |
| `--debug` | Enable debug logging to stderr |
| `--help` | Show help |

---

## queries

List running and recent queries.

```
trinops queries [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--server` | *(config)* | Trino server `host:port` |
| `--profile` | *(default)* | Config profile name |
| `--user` | *(config)* | Trino user |
| `--auth` | *(config)* | Auth method (`none`/`basic`/`jwt`/`oauth2`/`kerberos`) |
| `--query-user` | *(you)* | Filter by query owner; `all` for everyone |
| `--state` | *(any)* | Filter by query state |
| `--limit` / `-n` | `25` | Max queries per page; `0` for all |
| `--page` / `-p` | `1` | Page number (1-based) |
| `--json` | `false` | JSON output |
| `--select` / `-s` | *(all)* | Comma-separated fields for JSON output |

**Examples:**

```bash
# List your running queries
trinops queries

# All users, only RUNNING state, as JSON
trinops queries --query-user all --state RUNNING --json

# Page 2, 10 per page
trinops queries -n 10 -p 2

# Select specific fields
trinops queries --json -s "query_id,state,user"
```

---

## query

Show details for a specific query.

```
trinops query QUERY_ID [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--server` | *(config)* | Trino server `host:port` |
| `--profile` | *(default)* | Config profile name |
| `--user` | *(config)* | Trino user |
| `--auth` | *(config)* | Auth method |
| `--json` | `false` | JSON output |
| `--select` / `-s` | *(all)* | Comma-separated fields to include in JSON |

**Examples:**

```bash
trinops query 20240315_123456_00001_abcde

# Raw JSON with selected fields
trinops query 20240315_123456_00001_abcde --json -s "queryId,state,queryStats.elapsedTime"
```

---

## kill

Kill a running query.

```
trinops kill QUERY_ID [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--server` | *(config)* | Trino server `host:port` |
| `--profile` | *(default)* | Config profile name |
| `--user` | *(config)* | Trino user |
| `--auth` | *(config)* | Auth method |
| `--yes` / `-y` | `false` | Skip confirmation prompt |

The kill command respects `allow_kill` and `confirm_kill` in your profile. If `allow_kill` is `false`, the command exits with an error.

**Examples:**

```bash
trinops kill 20240315_123456_00001_abcde

# Skip confirmation
trinops kill 20240315_123456_00001_abcde -y
```

---

## top

Launch the interactive TUI dashboard.

```
trinops top [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--server` | *(config)* | Trino server `host:port` |
| `--profile` | *(default)* | Config profile name |
| `--user` | *(config)* | Trino user |
| `--auth` | *(config)* | Auth method |
| `--interval` | `30.0` | Refresh interval in seconds |

**Examples:**

```bash
trinops top
trinops top --interval 10
trinops top --profile staging
```

---

## tui

Alias for `top`. Identical flags and behavior.

```
trinops tui [OPTIONS]
```

---

## config init

Create or overwrite the config file. Prompts for missing values unless all required options are provided.

```
trinops config init [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--config-path` | `~/.config/trinops/config.toml` | Config file path |
| `--server` | *(prompt)* | Trino server `host:port` |
| `--scheme` | *(prompt, default https)* | `http` or `https` |
| `--user` | *(prompt)* | Trino user |
| `--auth` | *(prompt, default none)* | Auth method |
| `--catalog` | *(none)* | Default catalog |
| `--schema` | *(none)* | Default schema |
| `--query-limit` | *(none)* | Default query limit |
| `--yes` / `-y` | `false` | Overwrite without confirmation |

**Examples:**

```bash
# Interactive
trinops config init

# Non-interactive
trinops config init --server trino.example.com --scheme https --user alice --auth none -y
```

---

## config set

Set a single config value.

```
trinops config set KEY VALUE [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--config-path` | `~/.config/trinops/config.toml` | Config file path |
| `--profile` | `default` | Profile to update |

Valid keys: `server`, `scheme`, `user`, `auth`, `catalog`, `schema`, `password`, `password_cmd`, `jwt_token`, `query_limit`, `allow_kill`, `confirm_kill`.

**Examples:**

```bash
trinops config set query_limit 100
trinops config set auth basic --profile staging
trinops config set allow_kill false
```

---

## config show

Show current configuration.

```
trinops config show [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--config-path` | `~/.config/trinops/config.toml` | Config file path |
| `--profile` | *(default)* | Show a specific profile |

**Examples:**

```bash
trinops config show
trinops config show --profile staging
```

---

## auth status

Show the current authentication state.

```
trinops auth status [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--config-path` | `~/.config/trinops/config.toml` | Config file path |
| `--profile` | *(default)* | Config profile name |

---

## auth login

Run the OAuth2 authentication flow and cache the token. Only works when the profile's auth method is `oauth2`.

```
trinops auth login [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--config-path` | `~/.config/trinops/config.toml` | Config file path |
| `--profile` | *(default)* | Config profile name |

---

## schema refresh

Fetch schema metadata from Trino and cache it locally.

```
trinops schema refresh [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--server` | *(config)* | Trino server `host:port` |
| `--profile` | *(default)* | Config profile name |
| `--user` | *(config)* | Trino user |
| `--auth` | *(config)* | Auth method |
| `--catalog` | *(profile default)* | Catalog to fetch |
| `--all` | `false` | Discover and fetch all catalogs |

**Examples:**

```bash
trinops schema refresh --catalog hive
trinops schema refresh --all
trinops schema refresh --all --profile staging
```

---

## schema search

Search cached schema metadata for tables or columns using glob patterns.

```
trinops schema search PATTERN [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--profile` | *(default)* | Config profile name |
| `--catalog` | *(all)* | Limit search to a specific catalog |
| `--columns` | `false` | Search column names instead of table names |
| `--json` | `false` | JSON output |

**Examples:**

```bash
trinops schema search "*order*"
trinops schema search "analytics.*" --catalog hive
trinops schema search --columns "email"
trinops schema search "*event*" --json
```

---

## schema show

Show columns for a specific table.

```
trinops schema show TABLE_NAME [OPTIONS]
```

The table name can be unqualified (`users`), schema-qualified (`analytics.users`), or fully qualified (`hive.analytics.users`).

| Flag | Default | Description |
|------|---------|-------------|
| `--profile` | *(default)* | Config profile name |
| `--json` | `false` | JSON output |

**Examples:**

```bash
trinops schema show users
trinops schema show hive.analytics.page_views
trinops schema show orders --json
```

---

## schema list

List all cached catalogs.

```
trinops schema list [OPTIONS]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--profile` | *(default)* | Config profile name |

**Examples:**

```bash
trinops schema list
trinops schema list --profile staging
```
