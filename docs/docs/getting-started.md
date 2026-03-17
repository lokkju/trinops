# Getting Started

## Installation

trinops requires Python 3.10+. Choose your preferred installer:

=== "uvx (recommended)"

    ```bash
    # Run directly without installing
    uvx trinops top

    # Or install globally
    uv tool install trinops
    ```

=== "pipx"

    ```bash
    pipx install trinops
    ```

=== "pip"

    ```bash
    pip install trinops
    ```

## Configure your connection

trinops needs to know where your Trino coordinator lives. The fastest way to set that up is `config init`.

### Interactive setup

```bash
trinops config init
```

You will be prompted for:

| Prompt | Default | Description |
|--------|---------|-------------|
| Trino server | *(required)* | Hostname or `host:port` |
| Scheme | `https` | `http` or `https` |
| User | *(required)* | Trino user name |
| Auth method | `none` | `none`, `basic`, `jwt`, `oauth2`, or `kerberos` |

The config file is written to `~/.config/trinops/config.toml`.

### Non-interactive setup

Pass every required value as a flag and trinops skips the prompts:

```bash
trinops config init \
  --server trino.example.com \
  --scheme https \
  --user alice \
  --auth none \
  --yes
```

The `--yes` flag overwrites an existing config file without asking.

### Port defaults

When the server value does not include an explicit port, trinops infers one from the scheme:

- `https` defaults to port **443**
- `http` defaults to port **8080**

So `--server trino.example.com --scheme https` connects to `trino.example.com:443`.

### Environment variables

If you prefer not to use a config file, set environment variables instead. trinops checks these before falling back to the config file:

```bash
export TRINOPS_SERVER=trino.example.com:443
export TRINOPS_SCHEME=https
export TRINOPS_USER=alice
export TRINOPS_AUTH=none
```

See [Configuration](configuration.md) for the full list of environment variables and config fields.

## First run

Launch the TUI dashboard:

```bash
trinops top
```

![trinops query list](../assets/screenshots/query-list.svg)

The dashboard refreshes every 30 seconds by default. Press `r` to refresh immediately, `q` to quit.

If you see "No queries," your Trino cluster may not have any active queries at the moment. Press `a` to switch to "all users" mode and pick up queries submitted by anyone.

## Next steps

- [TUI Dashboard](tui.md) — keybindings, layout, and kill workflow
- [Schema Search](schema.md) — explore catalogs and tables from the terminal
- [CLI Reference](cli.md) — every command and flag
- [Configuration](configuration.md) — profiles, auth methods, and tuning
