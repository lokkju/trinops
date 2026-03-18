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
    table.add_column("Query ID", style="#7c3aed")
    table.add_column("State")
    table.add_column("User")
    table.add_column("Elapsed")
    table.add_column("Rows")
    table.add_column("Memory")
    table.add_column("SQL")

    state_styles = {
        "RUNNING": "bold #dd00a1",
        "QUEUED": "#eab308",
        "PLANNING": "#eab308",
        "STARTING": "#eab308",
        "DISPATCHING": "#eab308",
        "WAITING_FOR_RESOURCES": "#eab308",
        "FINISHING": "#a78bfa",
        "FINISHED": "#22c55e",
        "FAILED": "bold #ef4444",
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
    import sys
    sys.stdout.write(json.dumps([dataclasses.asdict(q) for q in queries], default=str))
    sys.stdout.write("\n")


def print_query_json(q: QueryInfo) -> None:
    import sys
    sys.stdout.write(json.dumps(dataclasses.asdict(q), default=str))
    sys.stdout.write("\n")


_STATE_STYLES = {
    "RUNNING": "bold #dd00a1",
    "QUEUED": "#eab308",
    "PLANNING": "#eab308",
    "STARTING": "#eab308",
    "DISPATCHING": "#eab308",
    "WAITING_FOR_RESOURCES": "#eab308",
    "FINISHING": "#a78bfa",
    "FINISHED": "#22c55e",
    "FAILED": "bold #ef4444",
}


def print_query_detail_rich(raw: dict) -> None:
    """Print enriched query detail from raw REST API response."""
    session = raw.get("session", {})
    qs = raw.get("queryStats", {})
    state = raw.get("state", "UNKNOWN")
    style = _STATE_STYLES.get(state, "")

    console.print(f"[bold]Query ID:[/]  {escape(raw.get('queryId', ''))}")
    console.print(f"[bold]State:[/]     [{style}]{escape(state)}[/{style}]")
    if raw.get("queryType"):
        console.print(f"[bold]Type:[/]      {escape(raw['queryType'])}")
    console.print(f"[bold]User:[/]      {escape(session.get('user', ''))}")
    if session.get("source"):
        console.print(f"[bold]Source:[/]    {escape(session['source'])}")
    if session.get("catalog"):
        catalog = session["catalog"]
        schema = session.get("schema", "")
        console.print(f"[bold]Catalog:[/]   {escape(catalog)}.{escape(schema)}" if schema else f"[bold]Catalog:[/]   {escape(catalog)}")
    if raw.get("resourceGroupId"):
        console.print(f"[bold]Resource:[/]  {escape('.'.join(raw['resourceGroupId']))}")

    # Timing
    console.print()
    console.print("[bold underline]Timing[/]")
    console.print(f"  Created:    {escape(qs.get('createTime', ''))}")
    if qs.get("endTime"):
        console.print(f"  Ended:      {escape(qs['endTime'])}")
    console.print(f"  Elapsed:    {escape(qs.get('elapsedTime', ''))}")
    console.print(f"  Queued:     {escape(qs.get('queuedTime', ''))}")
    console.print(f"  Planning:   {escape(qs.get('planningTime', ''))}")
    console.print(f"  Execution:  {escape(qs.get('executionTime', ''))}")
    console.print(f"  CPU:        {escape(qs.get('totalCpuTime', ''))}")

    # Data
    console.print()
    console.print("[bold underline]Data[/]")
    console.print(f"  Input:      {escape(qs.get('physicalInputDataSize', ''))}  ({qs.get('physicalInputPositions', 0):,} rows)")
    console.print(f"  Processed:  {escape(qs.get('processedInputDataSize', ''))}  ({qs.get('processedInputPositions', 0):,} rows)")
    console.print(f"  Output:     {escape(qs.get('outputDataSize', ''))}  ({qs.get('outputPositions', 0):,} rows)")
    if qs.get("physicalWrittenDataSize") and qs["physicalWrittenDataSize"] != "0B":
        console.print(f"  Written:    {escape(qs['physicalWrittenDataSize'])}")
    if qs.get("spilledDataSize") and qs["spilledDataSize"] != "0B":
        console.print(f"  Spilled:    {escape(qs['spilledDataSize'])}")

    # Memory
    console.print()
    console.print("[bold underline]Memory[/]")
    console.print(f"  Peak user:  {escape(qs.get('peakUserMemoryReservation', ''))}")
    console.print(f"  Peak total: {escape(qs.get('peakTotalMemoryReservation', ''))}")

    # Tasks
    console.print()
    console.print("[bold underline]Tasks[/]")
    console.print(f"  Tasks:      {qs.get('completedTasks', 0)}/{qs.get('totalTasks', 0)}")
    console.print(f"  Drivers:    {qs.get('completedDrivers', 0)}/{qs.get('totalDrivers', 0)}")

    # Tables accessed
    inputs = raw.get("inputs", [])
    if inputs:
        console.print()
        console.print("[bold underline]Tables[/]")
        for inp in inputs:
            tbl = f"  {escape(inp.get('catalogName', ''))}.{escape(inp.get('schema', ''))}.{escape(inp.get('table', ''))}"
            cols = [c["name"] for c in inp.get("columns", [])]
            info = inp.get("connectorInfo", {})
            records = info.get("totalRecords", "")
            suffix = f"  ({records} records)" if records else ""
            console.print(f"{tbl}{suffix}")
            if cols:
                console.print(f"    columns: {', '.join(cols)}")

    # Errors
    error = raw.get("failureInfo")
    if error:
        console.print()
        console.print(f"[bold red]Error:[/] {escape(error.get('type', ''))}")
        if error.get("message"):
            console.print(f"  {escape(error['message'])}")

    # Warnings
    warnings = raw.get("warnings", [])
    if warnings:
        console.print()
        console.print("[bold yellow]Warnings:[/]")
        for w in warnings:
            console.print(f"  {escape(str(w))}")

    # SQL
    query = raw.get("query", "")
    if query:
        console.print()
        console.print("[bold underline]SQL[/]")
        console.print(escape(query))
