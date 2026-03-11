from __future__ import annotations

import time

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, Static
from textual.timer import Timer
from textual.worker import Worker, WorkerState

from trinops.client import TrinopsClient
from trinops.config import ConnectionProfile
from trinops.formatting import format_bytes as _format_bytes, format_time_millis as _format_time
from trinops.models import QueryInfo


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
    TITLE = "trinops"

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
        ("r", "refresh", "Refresh"),
        ("u", "toggle_user", "My queries"),
        ("a", "show_all", "All queries"),
    ]

    DEFAULT_QUERY_LIMIT = 50

    show_all_users: reactive[bool] = reactive(False)

    def __init__(self, profile: ConnectionProfile, interval: float = 1.0, **kwargs):
        super().__init__(**kwargs)
        self._profile = profile
        self._interval = interval
        self._client: TrinopsClient | None = None
        self._queries: list[QueryInfo] = []
        self._refresh_timer: Timer | None = None
        self._countdown_timer: Timer | None = None
        self._refreshing = False
        self._last_refresh: float = 0.0

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
        self._update_subtitle()
        self._refresh_timer = self.set_interval(self._interval, self._schedule_refresh)
        self._countdown_timer = self.set_interval(0.5, self._update_subtitle)
        self._schedule_refresh()

    def _update_subtitle(self) -> None:
        user_label = "all users" if self.show_all_users else (self._profile.user or "?")

        if self._refreshing:
            refresh_text = "refreshing..."
        elif self._last_refresh > 0:
            elapsed = time.monotonic() - self._last_refresh
            remaining = max(0, self._interval - elapsed)
            if remaining < 0.5:
                refresh_text = "refreshing..."
            else:
                refresh_text = f"refresh in {remaining:.0f}s"
        else:
            refresh_text = "loading..."

        self.sub_title = f"{user_label}  ·  {refresh_text}"

    def watch_show_all_users(self) -> None:
        self._update_subtitle()
        self._schedule_refresh()

    def _schedule_refresh(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        self._update_subtitle()
        self.run_worker(self._fetch_queries, thread=True)

    def _fetch_queries(self) -> list[QueryInfo]:
        if self._client is None:
            self._client = TrinopsClient.from_profile(self._profile)
        query_user = None if self.show_all_users else self._profile.user
        return self._client.list_queries(limit=self.DEFAULT_QUERY_LIMIT, query_user=query_user)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name == "_fetch_queries":
            if event.state == WorkerState.SUCCESS:
                self._queries = event.worker.result
                self._update_table()
                self._last_refresh = time.monotonic()
            self._refreshing = False
            self._update_subtitle()

    def _update_table(self) -> None:
        table = self.query_one("#query-table", DataTable)

        new_keys = set()
        new_data: dict[str, tuple] = {}
        for qi in self._queries:
            row = (
                qi.query_id,
                qi.state.value,
                qi.user,
                _format_time(qi.elapsed_time_millis),
                f"{qi.processed_rows:,}",
                _format_bytes(qi.peak_memory_bytes),
                qi.truncated_sql(60),
            )
            new_data[qi.query_id] = row
            new_keys.add(qi.query_id)

        # Remember cursor position
        cursor_key = None
        if table.row_count > 0 and table.cursor_row is not None:
            try:
                cursor_key = str(table.get_row_at(table.cursor_row)[0])
            except Exception:
                pass

        # Remove rows that no longer exist
        existing_keys = set()
        for row_key in list(table.rows):
            key_str = str(row_key.value)
            if key_str not in new_keys:
                table.remove_row(row_key)
            else:
                existing_keys.add(key_str)

        # Update existing rows, add new ones
        col_keys = list(table.columns.keys())
        for qi_id, row in new_data.items():
            if qi_id in existing_keys:
                for col_idx, col_key in enumerate(col_keys):
                    table.update_cell(qi_id, col_key, row[col_idx])
            else:
                table.add_row(*row, key=qi_id)

        # Restore cursor position
        if cursor_key is not None:
            for idx in range(table.row_count):
                try:
                    if str(table.get_row_at(idx)[0]) == cursor_key:
                        table.move_cursor(row=idx)
                        break
                except Exception:
                    break

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        detail = self.query_one("#detail", QueryDetail)
        for qi in self._queries:
            if qi.query_id == str(event.row_key.value):
                detail.update_query(qi)
                return
        detail.update_query(None)

    def action_refresh(self) -> None:
        self._schedule_refresh()

    def action_toggle_user(self) -> None:
        self.show_all_users = not self.show_all_users

    def action_show_all(self) -> None:
        self.show_all_users = True
