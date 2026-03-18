from __future__ import annotations

import json as _json
import sys
from contextlib import contextmanager
from typing import Optional

import typer
from rich.console import Console

from trinops.client import TrinopsClient
from trinops.config import ConnectionProfile, load_config

_console = Console(stderr=True)


@contextmanager
def _status(message: str):
    """Show a spinner on stderr while work is in progress. Skip when piped."""
    if sys.stdout.isatty():
        with _console.status(message):
            yield
    else:
        yield

app = typer.Typer(name="trinops", help="Trino query monitoring tool", invoke_without_command=True)


def _version_callback(value: bool):
    if value:
        import trinops
        typer.echo(f"trinops {trinops.__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", "-V", callback=_version_callback, is_eager=True, help="Show version and exit"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug logging"),
):
    """Trino query monitoring tool."""
    if debug:
        import logging
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(message)s", stream=__import__("sys").stderr)
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


def _build_profile(
    server: Optional[str] = None,
    profile: Optional[str] = None,
    user: Optional[str] = None,
    auth: Optional[str] = None,
) -> ConnectionProfile:
    config = load_config()
    if server:
        return ConnectionProfile(
            server=server,
            auth=auth or "none",
            user=user or "trinops",
        )
    env_profile = ConnectionProfile.from_env()
    if env_profile is not None:
        return env_profile
    cp = config.get_profile(profile)
    if auth is not None:
        cp.auth = auth
    if user is not None:
        cp.user = user
    if cp.server is None:
        typer.echo(
            "No Trino server configured. Use one of:\n"
            "  --server host:port\n"
            "  TRINOPS_SERVER=host:port environment variable\n"
            "  trinops config init",
            err=True,
        )
        raise typer.Exit(1)
    return cp


def _build_client(
    server: Optional[str] = None,
    profile: Optional[str] = None,
    user: Optional[str] = None,
    auth: Optional[str] = None,
    check: bool = False,
) -> TrinopsClient:
    cp = _build_profile(server=server, profile=profile, user=user, auth=auth)
    client = TrinopsClient.from_profile(cp)
    if check:
        with _status("Connecting to Trino..."):
            try:
                client.check_connection()
            except ConnectionError as e:
                typer.echo(str(e), err=True)
                raise typer.Exit(1)
    return client


def _select_fields(data: dict, select: str) -> dict:
    """Extract dot-separated field paths from a dict.

    Example: _select_fields(d, "queryId,queryStats.elapsedTime")
    """
    result = {}
    for path in select.split(","):
        path = path.strip()
        if not path:
            continue
        parts = path.split(".")
        # Walk the source
        src = data
        for part in parts:
            if isinstance(src, dict):
                src = src.get(part)
            else:
                src = None
                break
        # Build nested output
        target = result
        for part in parts[:-1]:
            target = target.setdefault(part, {})
        target[parts[-1]] = src
    return result


@app.command()
def queries(
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
    auth: Optional[str] = typer.Option(None, help="Auth method (none/basic/jwt/oauth2/kerberos)"),
    query_user: Optional[str] = typer.Option(None, "--query-user", help="Filter by query owner (default: you, 'all' for everyone)"),
    state: Optional[str] = typer.Option(None, help="Filter by query state"),
    limit: int = typer.Option(25, "--limit", "-n", help="Max queries per page (0 for all)"),
    page: int = typer.Option(1, "--page", "-p", help="Page number (1-based)"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    select: Optional[str] = typer.Option(None, "--select", "-s", help="Comma-separated fields for JSON (e.g. query_id,state,user)"),
):
    """List running and recent queries."""
    cp = _build_profile(server=server, profile=profile, user=user, auth=auth)
    client = _build_client(server=server, profile=profile, user=user, auth=auth)
    effective_user = None if query_user == "all" else (query_user or cp.user)
    try:
        with _status("Loading..."):
            fetch_limit = limit * page if limit > 0 else 0
            results = client.list_queries(state=state, limit=fetch_limit, query_user=effective_user)
            total = len(results)
            if limit > 0:
                start = (page - 1) * limit
                results = results[start : start + limit]
            if json or select:
                import dataclasses
                items = [dataclasses.asdict(q) for q in results]
                if select:
                    items = [_select_fields(item, select) for item in items]
                sys.stdout.write(_json.dumps(items, default=str))
                sys.stdout.write("\n")
            else:
                from trinops.cli.formatting import print_queries_table
                print_queries_table(results)
                if limit > 0 and total > limit:
                    total_pages = (total + limit - 1) // limit
                    _console.print(f"Page {page}/{total_pages} ({total} total queries)")
    except Exception as e:
        typer.echo(f"Failed to fetch queries: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def query(
    query_id: str = typer.Argument(help="Trino query ID"),
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
    auth: Optional[str] = typer.Option(None, help="Auth method (none/basic/jwt/oauth2/kerberos)"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    select: Optional[str] = typer.Option(None, "--select", "-s", help="Comma-separated fields to include in JSON (e.g. queryId,state,queryStats.elapsedTime)"),
):
    """Show details for a specific query."""
    client = _build_client(server=server, profile=profile, user=user, auth=auth)
    try:
        with _status("Loading..."):
            if json or select:
                raw = client.get_query_raw(query_id)
                if raw is None:
                    typer.echo(f"Query not found: {query_id}", err=True)
                    raise typer.Exit(1)
                if select:
                    raw = _select_fields(raw, select)
                sys.stdout.write(_json.dumps(raw, default=str))
                sys.stdout.write("\n")
            else:
                raw = client.get_query_raw(query_id)
                if raw is None:
                    typer.echo(f"Query not found: {query_id}", err=True)
                    raise typer.Exit(1)
                from trinops.cli.formatting import print_query_detail_rich
                print_query_detail_rich(raw)
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Failed to fetch query: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def kill(
    query_id: str = typer.Argument(help="Trino query ID to kill"),
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
    auth: Optional[str] = typer.Option(None, help="Auth method (none/basic/jwt/oauth2/kerberos)"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Kill a running query."""
    cp = _build_profile(server=server, profile=profile, user=user, auth=auth)
    if not cp.allow_kill:
        typer.echo("Kill is disabled (allow_kill = false in config)", err=True)
        raise typer.Exit(1)

    client = _build_client(server=server, profile=profile, user=user, auth=auth)

    try:
        if cp.confirm_kill and not yes:
            with _status("Loading query..."):
                qi = client.get_query(query_id)
            if qi is None:
                typer.echo(f"Query {query_id} not found", err=True)
                raise typer.Exit(1)
            typer.confirm(
                f"Kill query {qi.query_id} by {qi.user}? [{qi.truncated_sql(80)}]",
                abort=True,
            )

        with _status("Killing query..."):
            result = client.kill_query(query_id)

        if result:
            typer.echo(f"Query {query_id} killed")
        else:
            typer.echo(f"Query {query_id} not found (already completed?)")
    except typer.Exit:
        raise
    except typer.Abort:
        raise
    except Exception as e:
        typer.echo(f"Failed to kill query: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def tui(
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
    auth: Optional[str] = typer.Option(None, help="Auth method (none/basic/jwt/oauth2/kerberos)"),
    interval: float = typer.Option(30.0, help="Refresh interval in seconds"),
):
    """Launch interactive TUI dashboard."""
    from trinops.tui.app import TrinopsApp

    cp = _build_profile(server=server, profile=profile, user=user, auth=auth)
    client = _build_client(server=server, profile=profile, user=user, auth=auth, check=True)
    client.close()
    tui_app = TrinopsApp(profile=cp, interval=interval)
    tui_app.run()


@app.command()
def top(
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
    auth: Optional[str] = typer.Option(None, help="Auth method (none/basic/jwt/oauth2/kerberos)"),
    interval: float = typer.Option(30.0, help="Refresh interval in seconds"),
):
    """Launch interactive TUI dashboard (alias for tui)."""
    tui(server=server, profile=profile, user=user, auth=auth, interval=interval)


config_app = typer.Typer(name="config", help="Manage trinops configuration", invoke_without_command=True)
auth_app = typer.Typer(name="auth", help="Manage authentication", invoke_without_command=True)
schema_app = typer.Typer(name="schema", help="Manage cached schema metadata", invoke_without_command=True)
app.add_typer(config_app, name="config")
app.add_typer(auth_app, name="auth")
app.add_typer(schema_app, name="schema")


@config_app.callback()
def config_callback(ctx: typer.Context):
    """Manage trinops configuration."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@auth_app.callback()
def auth_callback(ctx: typer.Context):
    """Manage authentication."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@schema_app.callback()
def schema_callback(ctx: typer.Context):
    """Manage cached schema metadata."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@config_app.command("show")
def config_show(
    config_path: Optional[str] = typer.Option(None, "--config-path", help="Config file path"),
    profile: Optional[str] = typer.Option(None, "--profile", help="Show a specific profile"),
):
    """Show current configuration."""
    from trinops.config import load_config, DEFAULT_CONFIG_PATH
    from pathlib import Path

    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if not path.exists():
        typer.echo(f"No config file found at {path}")
        return

    config = load_config(path)
    typer.echo(f"Config: {path}")

    if profile:
        try:
            cp = config.get_profile(profile)
        except KeyError:
            typer.echo(f"Unknown profile: {profile}", err=True)
            raise typer.Exit(1)
        typer.echo(f"Profile: {profile}")
    else:
        cp = config.default
        typer.echo("Profile: default")

    typer.echo(f"  server: {cp.server}")
    typer.echo(f"  scheme: {cp.scheme}")
    typer.echo(f"  user: {cp.user}")
    typer.echo(f"  auth: {cp.auth}")
    if cp.catalog:
        typer.echo(f"  catalog: {cp.catalog}")
    if cp.schema:
        typer.echo(f"  schema: {cp.schema}")
    typer.echo(f"  query_limit: {cp.query_limit}")

    if not profile and config.profiles:
        typer.echo(f"Profiles: {', '.join(config.profiles.keys())}")


@config_app.command("init")
def config_init(
    config_path: Optional[str] = typer.Option(None, "--config-path", help="Config file path"),
    server: Optional[str] = typer.Option(None, "--server", help="Trino server host:port"),
    scheme: Optional[str] = typer.Option(None, "--scheme", help="Connection scheme (http/https)"),
    user: Optional[str] = typer.Option(None, "--user", help="Trino user"),
    auth: Optional[str] = typer.Option(None, "--auth", help="Auth method (none/basic/jwt/oauth2/kerberos)"),
    catalog: Optional[str] = typer.Option(None, "--catalog", help="Default catalog"),
    schema: Optional[str] = typer.Option(None, "--schema", help="Default schema"),
    query_limit: Optional[int] = typer.Option(None, "--query-limit", help="Default query limit"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Overwrite without confirmation"),
):
    """Create or overwrite config file. Prompts for missing values unless all required options are provided."""
    from trinops.config import DEFAULT_CONFIG_PATH, save_config
    from pathlib import Path

    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if path.exists() and not yes:
        typer.confirm(f"{path} already exists. Overwrite?", abort=True)

    if server is None:
        server = typer.prompt("Trino server (host or host:port)")
    if scheme is None:
        scheme = typer.prompt("Scheme", default="https")
    if user is None:
        user = typer.prompt("User")
    if auth is None:
        auth = typer.prompt("Auth method (none/basic/jwt/oauth2/kerberos)", default="none")

    values: dict = {"server": server, "scheme": scheme, "user": user, "auth": auth}
    if catalog is not None:
        values["catalog"] = catalog
    if schema is not None:
        values["schema"] = schema
    if query_limit is not None:
        values["query_limit"] = query_limit

    save_config(path, "default", values)
    typer.echo(f"Config written to {path}")


@config_app.command("set")
def config_set(
    key: str = typer.Argument(help="Config key to set (e.g. server, auth, query_limit)"),
    value: str = typer.Argument(help="Value to set"),
    config_path: Optional[str] = typer.Option(None, "--config-path", help="Config file path"),
    profile: Optional[str] = typer.Option(None, "--profile", help="Profile to update (default: default)"),
):
    """Set a single config value."""
    from trinops.config import DEFAULT_CONFIG_PATH, save_config, ConnectionProfile
    from dataclasses import fields as dc_fields
    from pathlib import Path

    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    section = profile or "default"

    known = {f.name for f in dc_fields(ConnectionProfile)}
    if key not in known:
        typer.echo(f"Unknown config key: {key}", err=True)
        typer.echo(f"Valid keys: {', '.join(sorted(known))}", err=True)
        raise typer.Exit(1)

    # Coerce to the right type
    field_type = {f.name: f.type for f in dc_fields(ConnectionProfile)}[key]
    if field_type == "int":
        typed_value: object = int(value)
    elif field_type == "bool":
        if value.lower() in ("true", "1"):
            typed_value = True
        elif value.lower() in ("false", "0"):
            typed_value = False
        else:
            typer.echo(f"Invalid bool value: {value!r} (use true/false)", err=True)
            raise typer.Exit(1)
    else:
        typed_value = value

    save_config(path, section, {key: typed_value})
    label = f"profiles.{section}" if section != "default" else "default"
    typer.echo(f"Set {label}.{key} = {typed_value}")


@auth_app.command("status")
def auth_status(
    config_path: Optional[str] = typer.Option(None, "--config-path", help="Config file path"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
):
    """Show current authentication state."""
    from trinops.config import load_config
    from pathlib import Path

    path = Path(config_path) if config_path else None
    config = load_config(path)
    cp = config.get_profile(profile)
    typer.echo(f"Auth method: {cp.auth}")
    typer.echo(f"User: {cp.user}")
    if cp.auth == "oauth2":
        token_path = Path.home() / ".config" / "trinops" / "tokens"
        if token_path.exists():
            typer.echo("OAuth2 tokens cached: yes")
        else:
            typer.echo("OAuth2 tokens cached: no (run 'trinops auth login')")


@auth_app.command("login")
def auth_login(
    config_path: Optional[str] = typer.Option(None, "--config-path", help="Config file path"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
):
    """Run OAuth2 authentication flow and cache token."""
    from trinops.config import load_config
    from trinops.auth import build_auth
    from pathlib import Path

    path = Path(config_path) if config_path else None
    config = load_config(path)
    cp = config.get_profile(profile)

    if cp.auth != "oauth2":
        typer.echo(f"Profile uses auth method '{cp.auth}', not oauth2")
        raise typer.Exit(1)

    typer.echo("Starting OAuth2 flow...")
    auth = build_auth(cp)
    typer.echo("Authentication successful. Token cached.")


# ---------------------------------------------------------------------------
# schema subcommands
# ---------------------------------------------------------------------------


def _relative_age(iso_timestamp: str) -> str:
    """Return a human-readable relative age string like '2h ago' or '3d ago'."""
    from datetime import datetime, timezone

    try:
        dt = datetime.fromisoformat(iso_timestamp)
        delta = datetime.now(timezone.utc) - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s ago"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes}m ago"
        hours = minutes // 60
        if hours < 24:
            return f"{hours}h ago"
        days = hours // 24
        return f"{days}d ago"
    except (ValueError, TypeError):
        return iso_timestamp


@schema_app.command("refresh")
def schema_refresh(
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
    auth: Optional[str] = typer.Option(None, help="Auth method (none/basic/jwt/oauth2/kerberos)"),
    catalog: Optional[str] = typer.Option(None, "--catalog", help="Catalog to fetch (overrides profile default)"),
    all_catalogs: bool = typer.Option(False, "--all", help="Discover and fetch all catalogs"),
):
    """Fetch schema metadata from Trino and cache locally."""
    from trinops.schema.cache import SchemaCache
    from trinops.schema.fetcher import SchemaFetcher

    cp = _build_profile(server=server, profile=profile, user=user, auth=auth)
    profile_name = profile or "default"
    fetcher = SchemaFetcher(cp, profile_name=profile_name)
    cache = SchemaCache()

    if all_catalogs:
        with _status("Discovering catalogs..."):
            catalogs = fetcher.discover_catalogs()
        typer.echo(f"Found {len(catalogs)} catalogs", err=True)
        for cat in catalogs:
            try:
                with _status(f"Fetching {cat}..."):
                    data = fetcher.fetch_catalog(cat)
                cache.write(profile_name, cat, data)
                typer.echo(f"  {cat}: OK", err=True)
            except Exception as e:
                typer.echo(f"  {cat}: WARN {e}", err=True)
    else:
        cat = catalog or cp.catalog
        if not cat:
            typer.echo(
                "No catalog specified. Use --catalog or set a default catalog in your profile.",
                err=True,
            )
            raise typer.Exit(1)
        with _status(f"Fetching {cat}..."):
            data = fetcher.fetch_catalog(cat)
        cache.write(profile_name, cat, data)
        stats = cache.get_stats(profile_name, cat)
        typer.echo(
            f"Cached {stats['table_count']} tables, {stats['column_count']} columns for {cat}",
            err=True,
        )


@schema_app.command("search")
def schema_search(
    pattern: str = typer.Argument(help="Glob pattern to match table or column names"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    catalog: Optional[str] = typer.Option(None, "--catalog", help="Limit search to catalog"),
    columns: bool = typer.Option(False, "--columns", help="Search column names instead of table names"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Search cached schema metadata for tables or columns."""
    from rich.console import Console
    from rich.table import Table

    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch

    profile_name = profile or "default"
    cache = SchemaCache()
    search = SchemaSearch(cache, profile=profile_name, catalog=catalog)

    if columns:
        results = search.search_columns(pattern)
    else:
        results = search.search_tables(pattern)

    if json:
        sys.stdout.write(_json.dumps(results))
        sys.stdout.write("\n")
        return

    if not results:
        typer.echo("No matches found.")
        return

    console = Console()
    if columns:
        table = Table(title="Column matches")
        table.add_column("Catalog")
        table.add_column("Schema")
        table.add_column("Table")
        table.add_column("Column")
        table.add_column("Type")
        for r in results:
            table.add_row(r["catalog"], r["schema"], r["table"], r["column"], r["column_type"])
    else:
        table = Table(title="Table matches")
        table.add_column("Catalog")
        table.add_column("Schema")
        table.add_column("Table")
        table.add_column("Type")
        for r in results:
            table.add_row(r["catalog"], r["schema"], r["table"], r["type"])

    console.print(table)


@schema_app.command("show")
def schema_show(
    name: Optional[str] = typer.Argument(None, help="Name to browse: catalog, catalog.schema, catalog.schema.table, or table"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    catalog: Optional[str] = typer.Option(None, "--catalog", help="Limit to catalog (for full dump)"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Browse schema hierarchy or show table columns.

    No argument: list catalogs (or dump all with --json).
    One part: list schemas in that catalog.
    Two parts: list tables in catalog.schema.
    Three parts (or unqualified table name): show columns.
    """
    from rich.console import Console
    from rich.table import Table

    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch

    profile_name = profile or "default"
    cache = SchemaCache()
    search = SchemaSearch(cache, profile=profile_name, catalog=catalog)
    console = Console()

    if name is None:
        # No argument: list catalogs, or dump everything with --json
        if json:
            sys.stdout.write(_json.dumps(search.dump_all()))
            sys.stdout.write("\n")
            return
        catalogs = search.list_catalogs()
        if not catalogs:
            typer.echo("No cached catalogs found.")
            return
        table = Table(title="Catalogs")
        table.add_column("Catalog")
        for c in catalogs:
            table.add_row(c)
        console.print(table)
        return

    parts = name.split(".")

    if len(parts) == 1:
        # Could be a catalog name or an unqualified table name.
        # Try catalog first.
        schemas = search.list_schemas(parts[0])
        if schemas:
            if json:
                sys.stdout.write(_json.dumps({"catalog": parts[0], "schemas": schemas}))
                sys.stdout.write("\n")
                return
            table = Table(title=f"Schemas in {parts[0]}")
            table.add_column("Schema")
            for s in schemas:
                table.add_row(s)
            console.print(table)
            return
        # Fall through to table lookup
        matches = search.lookup_tables(name)
        if not matches:
            typer.echo(f"No catalog or table found: {name}", err=True)
            raise typer.Exit(1)
        if json:
            sys.stdout.write(_json.dumps(matches))
            sys.stdout.write("\n")
            return
        for m in matches:
            _print_table_columns(console, m)
        return

    if len(parts) == 2:
        # catalog.schema → list tables
        tables = search.list_tables_in_schema(parts[0], parts[1])
        if tables:
            if json:
                sys.stdout.write(_json.dumps(tables))
                sys.stdout.write("\n")
                return
            table = Table(title=f"Tables in {parts[0]}.{parts[1]}")
            table.add_column("Table")
            table.add_column("Type")
            for t in tables:
                table.add_row(t["table"], t["type"])
            console.print(table)
            return
        # Fall through to schema.table lookup
        matches = search.lookup_tables(name)
        if not matches:
            typer.echo(f"Not found: {name}", err=True)
            raise typer.Exit(1)
        if json:
            sys.stdout.write(_json.dumps(matches))
            sys.stdout.write("\n")
            return
        for m in matches:
            _print_table_columns(console, m)
        return

    # 3+ parts: catalog.schema.table
    matches = search.lookup_tables(name)
    if not matches:
        typer.echo(f"Table not found: {name}", err=True)
        raise typer.Exit(1)
    if json:
        sys.stdout.write(_json.dumps(matches))
        sys.stdout.write("\n")
        return
    for m in matches:
        _print_table_columns(console, m)


def _print_table_columns(console, m: dict) -> None:
    from rich.table import Table
    fqn = f"{m['catalog']}.{m['schema']}.{m['table']}"
    table = Table(title=fqn)
    table.add_column("Column")
    table.add_column("Type")
    table.add_column("Nullable")
    for col in m["columns"]:
        table.add_row(col["name"], col["type"], str(col.get("nullable", "")))
    console.print(table)


@schema_app.command("list")
def schema_list(
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
):
    """List cached catalogs."""
    from rich.console import Console
    from rich.table import Table

    from trinops.schema.cache import SchemaCache

    cache = SchemaCache()

    if profile:
        profiles = [profile]
    else:
        profiles = cache.list_profiles()

    if not profiles:
        typer.echo("No cached catalogs found.")
        return

    console = Console()
    table = Table(title="Cached catalogs")
    table.add_column("Profile")
    table.add_column("Catalog")
    table.add_column("Tables")
    table.add_column("Columns")
    table.add_column("Fetched")

    has_rows = False
    for prof in profiles:
        catalogs = cache.list_catalogs(prof)
        for cat in catalogs:
            stats = cache.get_stats(prof, cat)
            if stats:
                has_rows = True
                age = _relative_age(stats["fetched_at"])
                table.add_row(
                    prof,
                    cat,
                    str(stats["table_count"]),
                    str(stats["column_count"]),
                    age,
                )

    if not has_rows:
        typer.echo("No cached catalogs found.")
        return

    console.print(table)
