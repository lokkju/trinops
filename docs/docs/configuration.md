# Configuration

## Config file

trinops reads its configuration from a TOML file at:

```
~/.config/trinops/config.toml
```

Create it with `trinops config init` or write it by hand. A minimal config looks like:

```toml
[default]
server = "trino.example.com"
scheme = "https"
user = "alice"
auth = "none"
```

## Profile fields

Every profile (including `[default]`) supports these fields:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `server` | string | *(none)* | Trino coordinator hostname or `host:port` |
| `scheme` | string | `"https"` | Connection scheme: `http` or `https` |
| `user` | string | *(none)* | Trino user name |
| `auth` | string | `"none"` | Authentication method (see below) |
| `catalog` | string | *(none)* | Default catalog for schema commands |
| `schema` | string | *(none)* | Default schema |
| `password` | string | *(none)* | Password for basic auth |
| `password_cmd` | string | *(none)* | Shell command that prints the password to stdout |
| `jwt_token` | string | *(none)* | JWT token string for jwt auth |
| `query_limit` | int | `50` | Maximum number of queries to fetch |
| `allow_kill` | bool | `true` | Enable the kill command and `k` binding |
| `confirm_kill` | bool | `true` | Show a confirmation prompt before killing |

## Authentication methods

Set the `auth` field to one of these values:

**`none`** — No authentication. Suitable for clusters that trust the network or use a proxy for auth.

**`basic`** — HTTP basic authentication. Provide credentials via `password` or `password_cmd`:

```toml
[default]
server = "trino.example.com"
auth = "basic"
user = "alice"
password_cmd = "pass show trino/alice"
```

Using `password_cmd` is preferred over storing a plaintext `password` in the config file.

**`jwt`** — Bearer token authentication. Set the token directly or fetch it from a command:

```toml
[default]
auth = "jwt"
jwt_token = "eyJhbGci..."
```

**`oauth2`** — OAuth2 device or browser flow. Run `trinops auth login` to initiate the flow and cache the token:

```bash
trinops auth login
```

Check the current auth state with `trinops auth status`.

**`kerberos`** — Kerberos/SPNEGO authentication. Requires a valid Kerberos ticket (e.g., from `kinit`).

## Environment variables

Environment variables override the config file when `TRINOPS_SERVER` is set. This is useful for CI, containers, or one-off invocations.

| Variable | Maps to | Default |
|----------|---------|---------|
| `TRINOPS_SERVER` | `server` | *(none — if unset, env vars are ignored)* |
| `TRINOPS_SCHEME` | `scheme` | `https` |
| `TRINOPS_USER` | `user` | *(none)* |
| `TRINOPS_AUTH` | `auth` | `none` |
| `TRINOPS_CATALOG` | `catalog` | *(none)* |
| `TRINOPS_SCHEMA` | `schema` | *(none)* |

`TRINOPS_SERVER` acts as the trigger. If it is not set, trinops falls back to the config file entirely.

## Multiple profiles

Define named profiles under `[profiles.<name>]` for clusters you connect to regularly:

```toml
[default]
server = "trino-prod.example.com"
scheme = "https"
user = "alice"
auth = "basic"
password_cmd = "pass show trino/prod"

[profiles.staging]
server = "trino-staging.example.com"
scheme = "https"
user = "alice"
auth = "none"

[profiles.local]
server = "localhost:8080"
scheme = "http"
user = "dev"
auth = "none"
```

Use `--profile` to select one:

```bash
trinops top --profile staging
trinops queries --profile local
trinops schema refresh --all --profile staging
```

Without `--profile`, trinops uses the `[default]` section.

## Setting individual values

Update a single field without rewriting the entire file:

```bash
trinops config set query_limit 100
trinops config set auth basic --profile staging
```

## Viewing the current config

```bash
trinops config show
trinops config show --profile staging
```
