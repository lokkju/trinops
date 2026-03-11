from __future__ import annotations

from typing import Optional

import typer

from trinops.client import TrinopsClient
from trinops.config import ConnectionProfile, load_config

app = typer.Typer(name="trinops", help="Trino query monitoring tool", invoke_without_command=True)


@app.callback()
def main(ctx: typer.Context):
    """Trino query monitoring tool."""
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
) -> TrinopsClient:
    cp = _build_profile(server=server, profile=profile, user=user, auth=auth)
    client = TrinopsClient.from_profile(cp, backend=backend)
    try:
        client.check_connection()
    except ConnectionError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    return client


@app.command()
def queries(
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
    auth: Optional[str] = typer.Option(None, help="Auth method (none/basic/jwt/oauth2/kerberos)"),
    state: Optional[str] = typer.Option(None, help="Filter by query state"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    backend: str = typer.Option("http", help="Backend (http/sql)"),
):
    """List running and recent queries."""
    client = _build_client(server=server, profile=profile, user=user, auth=auth, backend=backend)
    results = client.list_queries(state=state)

    if json:
        from trinops.cli.formatting import print_queries_json
        print_queries_json(results)
    else:
        from trinops.cli.formatting import print_queries_table
        print_queries_table(results)


@app.command()
def query(
    query_id: str = typer.Argument(help="Trino query ID"),
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
    auth: Optional[str] = typer.Option(None, help="Auth method (none/basic/jwt/oauth2/kerberos)"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
    backend: str = typer.Option("http", help="Backend (http/sql)"),
):
    """Show details for a specific query."""
    client = _build_client(server=server, profile=profile, user=user, auth=auth, backend=backend)
    qi = client.get_query(query_id)

    if qi is None:
        typer.echo(f"Query not found: {query_id}", err=True)
        raise typer.Exit(1)

    if json:
        from trinops.cli.formatting import print_query_json
        print_query_json(qi)
    else:
        from trinops.cli.formatting import print_query_detail
        print_query_detail(qi)


@app.command()
def tui(
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
    auth: Optional[str] = typer.Option(None, help="Auth method (none/basic/jwt/oauth2/kerberos)"),
    interval: float = typer.Option(1.0, help="Refresh interval in seconds"),
    backend: str = typer.Option("http", help="Backend (http/sql)"),
):
    """Launch interactive TUI dashboard."""
    from trinops.tui.app import TrinopsApp

    cp = _build_profile(server=server, profile=profile, user=user, auth=auth)
    # Verify connection before launching TUI
    client = TrinopsClient.from_profile(cp, backend=backend)
    try:
        client.check_connection()
    except ConnectionError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(1)
    client.close()
    tui_app = TrinopsApp(profile=cp, interval=interval)
    tui_app.run()


@app.command()
def top(
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
    auth: Optional[str] = typer.Option(None, help="Auth method (none/basic/jwt/oauth2/kerberos)"),
    interval: float = typer.Option(1.0, help="Refresh interval in seconds"),
    backend: str = typer.Option("http", help="Backend (http/sql)"),
):
    """Launch interactive TUI dashboard (alias for tui)."""
    tui(server=server, profile=profile, user=user, auth=auth, interval=interval, backend=backend)


mcp_app = typer.Typer(name="mcp", help="MCP server")
config_app = typer.Typer(name="config", help="Manage trinops configuration")
auth_app = typer.Typer(name="auth", help="Manage authentication")
app.add_typer(mcp_app, name="mcp")
app.add_typer(config_app, name="config")
app.add_typer(auth_app, name="auth")


@mcp_app.command("serve")
def mcp_serve(
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
    auth: Optional[str] = typer.Option(None, help="Auth method (none/basic/jwt/oauth2/kerberos)"),
    backend: str = typer.Option("http", help="Backend (http/sql)"),
):
    """Start MCP server on stdio."""
    from trinops.mcp.server import run_stdio_server

    client = _build_client(server=server, profile=profile, user=user, auth=auth, backend=backend)
    run_stdio_server(client)


@config_app.command("show")
def config_show(
    config_path: Optional[str] = typer.Option(None, "--config-path", help="Config file path"),
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
    typer.echo(f"Default server: {config.default.server}")
    typer.echo(f"Default user: {config.default.user}")
    typer.echo(f"Default auth: {config.default.auth}")
    if config.profiles:
        typer.echo(f"Profiles: {', '.join(config.profiles.keys())}")


@config_app.command("init")
def config_init(
    config_path: Optional[str] = typer.Option(None, "--config-path", help="Config file path"),
):
    """Create a new config file interactively."""
    from trinops.config import DEFAULT_CONFIG_PATH
    from pathlib import Path

    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if path.exists():
        typer.confirm(f"{path} already exists. Overwrite?", abort=True)

    server = typer.prompt("Trino server (host:port)")
    scheme = typer.prompt("Scheme", default="https")
    user = typer.prompt("User")
    auth = typer.prompt("Auth method (none/basic/jwt/oauth2/kerberos)", default="none")

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(f'[default]\nserver = "{server}"\nscheme = "{scheme}"\nuser = "{user}"\nauth = "{auth}"\n')

    typer.echo(f"Config written to {path}")


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
