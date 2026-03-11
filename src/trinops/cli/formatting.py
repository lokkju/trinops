from __future__ import annotations

import dataclasses
import json
from typing import Sequence

from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.text import Text

from trinops.formatting import format_bytes, format_time_millis
from trinops.models import QueryInfo


console = Console()


def print_queries_table(queries: Sequence[QueryInfo]) -> None:
    table = Table()
    table.add_column("Query ID", style="cyan")
    table.add_column("State")
    table.add_column("User")
    table.add_column("Elapsed")
    table.add_column("Rows")
    table.add_column("Memory")
    table.add_column("SQL")

    state_styles = {
        "RUNNING": "bold blue",
        "QUEUED": "yellow",
        "PLANNING": "yellow",
        "STARTING": "yellow",
        "DISPATCHING": "yellow",
        "WAITING_FOR_RESOURCES": "yellow",
        "FINISHING": "blue",
        "FINISHED": "green",
        "FAILED": "bold red",
    }

    for q in queries:
        state_text = Text(q.state.value)
        style = state_styles.get(q.state.value)
        if style:
            state_text.stylize(style)

        table.add_row(
            q.query_id,
            state_text,
            q.user,
            format_time_millis(q.elapsed_time_millis),
            f"{q.processed_rows:,}",
            format_bytes(q.peak_memory_bytes),
            q.truncated_sql(60),
        )

    console.print(table)


def print_query_detail(q: QueryInfo) -> None:
    console.print(f"[bold]Query ID:[/] {escape(q.query_id)}")
    console.print(f"[bold]State:[/]    {escape(q.state.value)}")
    console.print(f"[bold]User:[/]     {escape(q.user)}")
    if q.source:
        console.print(f"[bold]Source:[/]   {escape(q.source)}")
    console.print(f"[bold]Elapsed:[/]  {format_time_millis(q.elapsed_time_millis)}")
    console.print(f"[bold]CPU:[/]      {format_time_millis(q.cpu_time_millis)}")
    console.print(f"[bold]Rows:[/]     {q.processed_rows:,}")
    console.print(f"[bold]Data:[/]     {format_bytes(q.processed_bytes)}")
    console.print(f"[bold]Memory:[/]   {format_bytes(q.peak_memory_bytes)}")
    if q.error_message:
        console.print(f"[bold red]Error:[/]   {escape(q.error_message)}")
    console.print(f"\n[bold]SQL:[/]\n{escape(q.query)}")


def print_queries_json(queries: Sequence[QueryInfo]) -> None:
    for q in queries:
        print(json.dumps(dataclasses.asdict(q), default=str))


def print_query_json(q: QueryInfo) -> None:
    print(json.dumps(dataclasses.asdict(q), default=str))
