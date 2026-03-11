from __future__ import annotations

from typing import Optional

import typer

from trinops.client import TrinopsClient
from trinops.config import ConnectionProfile, load_config

app = typer.Typer(name="trinops", help="Trino query monitoring tool")


def _build_profile(
    server: Optional[str] = None,
    profile: Optional[str] = None,
    user: Optional[str] = None,
) -> ConnectionProfile:
    config = load_config()
    if server:
        return ConnectionProfile(server=server, auth="none", user=user or "trinops")
    env_profile = ConnectionProfile.from_env()
    if env_profile is not None:
        return env_profile
    return config.get_profile(profile)


def _build_client(
    server: Optional[str] = None,
    profile: Optional[str] = None,
    user: Optional[str] = None,
) -> TrinopsClient:
    cp = _build_profile(server=server, profile=profile, user=user)
    return TrinopsClient.from_profile(cp)


@app.command()
def queries(
    server: Optional[str] = typer.Option(None, help="Trino server host:port"),
    profile: Optional[str] = typer.Option(None, help="Config profile name"),
    user: Optional[str] = typer.Option(None, help="Trino user"),
    state: Optional[str] = typer.Option(None, help="Filter by query state"),
    json: bool = typer.Option(False, "--json", help="JSON output"),
):
    """List running and recent queries."""
    client = _build_client(server=server, profile=profile, user=user)
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
    json: bool = typer.Option(False, "--json", help="JSON output"),
    watch: bool = typer.Option(False, "--watch", help="Poll until query finishes"),
):
    """Show details for a specific query."""
    client = _build_client(server=server, profile=profile, user=user)
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
