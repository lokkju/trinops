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
    backend: str = "http",
    check: bool = False,
) -> TrinopsClient:
    cp = _build_profile(server=server, profile=profile, user=user, auth=auth)
    client = TrinopsClient.from_profile(cp, backend=backend)
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
    backend: str = typer.Option("http", help="Backend (http/sql)"),
):
    """List running and recent queries."""
    cp = _build_profile(server=server, profile=profile, user=user, auth=auth)
    client = _build_client(server=server, profile=profile, user=user, auth=auth, backend=backend)
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
    backend: str = typer.Option("http", help="Backend (http/sql)"),
):
    """Show details for a specific query."""
    client = _build_client(server=server, profile=profile, user=user, auth=auth, backend=backend)
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
def tui(
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
    auth: Optional[str] = typer.Option(None, help="Auth method (none/basic/jwt/oauth2/kerberos)"),
    interval: float = typer.Option(30.0, help="Refresh interval in seconds"),
    backend: str = typer.Option("http", help="Backend (http/sql)"),
):
    """Launch interactive TUI dashboard."""
    from trinops.tui.app import TrinopsApp

    cp = _build_profile(server=server, profile=profile, user=user, auth=auth)
    client = _build_client(server=server, profile=profile, user=user, auth=auth, backend=backend, check=True)
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
    backend: str = typer.Option("http", help="Backend (http/sql)"),
):
    """Launch interactive TUI dashboard (alias for tui)."""
    tui(server=server, profile=profile, user=user, auth=auth, interval=interval, backend=backend)


config_app = typer.Typer(name="config", help="Manage trinops configuration")
auth_app = typer.Typer(name="auth", help="Manage authentication")
app.add_typer(config_app, name="config")
app.add_typer(auth_app, name="auth")


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
