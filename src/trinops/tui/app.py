from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import DataTable, Footer, Header, Static
from textual.timer import Timer

from trinops.client import TrinopsClient
from trinops.config import ConnectionProfile
from trinops.models import QueryInfo


def _format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def _format_time(millis: int) -> str:
    seconds = millis / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    return f"{minutes / 60:.1f}h"


class QueryDetail(Static):
    def update_query(self, qi: QueryInfo | None) -> None:
        if qi is None:
            self.update("Select a query to view details")
            return
        lines = [
            f"Query ID: {qi.query_id}",
            f"State:    {qi.state.value}",
            f"User:     {qi.user}",
            f"Elapsed:  {_format_time(qi.elapsed_time_millis)}",
            f"CPU:      {_format_time(qi.cpu_time_millis)}",
            f"Rows:     {qi.processed_rows:,}",
            f"Data:     {_format_bytes(qi.processed_bytes)}",
            f"Memory:   {_format_bytes(qi.peak_memory_bytes)}",
            "",
            qi.query,
        ]
        if qi.error_message:
            lines.insert(-1, f"Error:    {qi.error_message}")
        self.update("\n".join(lines))


class TrinopsApp(App):
    CSS = """
    #query-table {
        height: 1fr;
    }
    #detail {
        height: auto;
        max-height: 40%;
        border-top: solid green;
        padding: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("f", "filter", "Filter"),
        ("r", "refresh", "Refresh"),
        ("/", "search", "Search"),
    ]

    def __init__(self, profile: ConnectionProfile, interval: float = 1.0, **kwargs):
        super().__init__(**kwargs)
        self._profile = profile
        self._interval = interval
        self._client: TrinopsClient | None = None
        self._queries: list[QueryInfo] = []
        self._refresh_timer: Timer | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Container(
            DataTable(id="query-table"),
            QueryDetail(id="detail"),
        )
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#query-table", DataTable)
        table.add_columns("Query ID", "State", "User", "Elapsed", "Rows", "Memory", "SQL")
        table.cursor_type = "row"
        self._refresh_timer = self.set_interval(self._interval, self._refresh_queries)
        self._refresh_queries()

    def _refresh_queries(self) -> None:
        if self._client is None:
            self._client = TrinopsClient.from_profile(self._profile)

        try:
            self._queries = self._client.list_queries()
        except Exception:
            return

        table = self.query_one("#query-table", DataTable)
        table.clear()
        for qi in self._queries:
            table.add_row(
                qi.query_id,
                qi.state.value,
                qi.user,
                _format_time(qi.elapsed_time_millis),
                f"{qi.processed_rows:,}",
                _format_bytes(qi.peak_memory_bytes),
                qi.truncated_sql(60),
                key=qi.query_id,
            )

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        detail = self.query_one("#detail", QueryDetail)
        for qi in self._queries:
            if qi.query_id == str(event.row_key.value):
                detail.update_query(qi)
                return
        detail.update_query(None)

    def action_refresh(self) -> None:
        self._refresh_queries()

    def action_filter(self) -> None:
        pass  # v2: filter dialog

    def action_search(self) -> None:
        pass  # v2: search dialog
