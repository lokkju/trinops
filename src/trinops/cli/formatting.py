from __future__ import annotations

import dataclasses
import json
from typing import Sequence

from rich.console import Console
from rich.table import Table

from trinops.models import QueryInfo


console = Console(width=200)


def format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def format_time_millis(millis: int) -> str:
    seconds = millis / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"


def print_queries_table(queries: Sequence[QueryInfo]) -> None:
    table = Table()
    table.add_column("Query ID", style="cyan")
    table.add_column("State")
    table.add_column("User")
    table.add_column("Elapsed")
    table.add_column("Rows")
    table.add_column("Memory")
    table.add_column("SQL")

    for q in queries:
        state_style = {
            "RUNNING": "bold blue",
            "QUEUED": "yellow",
            "PLANNING": "yellow",
            "FINISHED": "green",
            "FAILED": "bold red",
        }.get(q.state.value, "")

        table.add_row(
            q.query_id,
            f"[{state_style}]{q.state.value}[/]",
            q.user,
            format_time_millis(q.elapsed_time_millis),
            f"{q.processed_rows:,}",
            format_bytes(q.peak_memory_bytes),
            q.truncated_sql(60),
        )

    console.print(table)


def print_query_detail(q: QueryInfo) -> None:
    console.print(f"[bold]Query ID:[/] {q.query_id}")
    console.print(f"[bold]State:[/]    {q.state.value}")
    console.print(f"[bold]User:[/]     {q.user}")
    if q.source:
        console.print(f"[bold]Source:[/]   {q.source}")
    console.print(f"[bold]Elapsed:[/]  {format_time_millis(q.elapsed_time_millis)}")
    console.print(f"[bold]CPU:[/]      {format_time_millis(q.cpu_time_millis)}")
    console.print(f"[bold]Rows:[/]     {q.processed_rows:,}")
    console.print(f"[bold]Data:[/]     {format_bytes(q.processed_bytes)}")
    console.print(f"[bold]Memory:[/]   {format_bytes(q.peak_memory_bytes)}")
    if q.error_message:
        console.print(f"[bold red]Error:[/]   {q.error_message}")
    console.print(f"\n[bold]SQL:[/]\n{q.query}")


def print_queries_json(queries: Sequence[QueryInfo]) -> None:
    for q in queries:
        print(json.dumps(dataclasses.asdict(q), default=str))


def print_query_json(q: QueryInfo) -> None:
    print(json.dumps(dataclasses.asdict(q), default=str))
