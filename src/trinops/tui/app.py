from __future__ import annotations

import time

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.reactive import reactive
from textual.widgets import DataTable, Footer, Header, Static, TextArea
from textual.timer import Timer
from textual.worker import Worker, WorkerState

from trinops.client import TrinopsClient
from trinops.config import ConnectionProfile
from trinops.formatting import format_bytes as _format_bytes, format_time_millis as _format_time
from trinops.models import QueryInfo


class StatusBar(Static):
    """Status bar showing user filter, query count, and refresh countdown."""

    DEFAULT_CSS = """
    StatusBar {
        height: 1;
        background: $panel;
        color: $text;
        padding: 0 1;
    }
    StatusBar.loading {
        background: $warning;
        color: $text;
        text-style: bold;
    }
    """


class TrinopsApp(App):
    TITLE = "trinops"

    CSS = """
    #query-table {
        height: 1fr;
    }
    #status-bar {
        height: 1;
    }
    #detail-pane {
        height: auto;
        max-height: 50%;
        border-top: solid green;
        display: none;
    }
    #detail-pane.visible {
        display: block;
    }
    #detail-meta {
        height: auto;
        padding: 0 1;
    }
    #detail-sql {
        height: 1fr;
        min-height: 5;
        padding: 0 1;
    }
"""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("u", "toggle_user", "My queries"),
        ("a", "show_all", "All queries"),
        ("escape", "close_detail", "Close detail"),
        Binding("-", "interval_up", "Refresh rate", key_display="-/+"),
        Binding("+", "interval_down", "", show=False),
        ("tab", "focus_next", "Next pane"),
        ("shift+tab", "focus_previous", "Prev pane"),
    ]

    INTERVAL_STEPS = [5, 10, 15, 30, 60, 120, 300]

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
        self._loaded = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield DataTable(id="query-table")
        yield Container(
            Static(id="detail-meta"),
            TextArea(id="detail-sql", read_only=True),
            id="detail-pane",
        )
        yield StatusBar(id="status-bar")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#query-table", DataTable)
        table.add_columns("Query ID", "State", "User", "Elapsed", "Rows", "Memory", "SQL")
        table.cursor_type = "row"
        self._update_status_bar()
        self._refresh_timer = self.set_interval(self._interval, self._schedule_refresh)
        self._countdown_timer = self.set_interval(0.5, self._update_status_bar)
        self._schedule_refresh()

    def _update_status_bar(self) -> None:
        bar = self.query_one("#status-bar", StatusBar)
        user_label = "all users" if self.show_all_users else (self._profile.user or "?")

        is_loading = self._refreshing or self._last_refresh == 0
        if not is_loading and self._last_refresh > 0:
            elapsed = time.monotonic() - self._last_refresh
            remaining = max(0, self._interval - elapsed)
            if remaining < 0.5:
                is_loading = True

        if is_loading:
            refresh_text = "loading..."
        else:
            elapsed = time.monotonic() - self._last_refresh
            remaining = max(0, self._interval - elapsed)
            refresh_text = f"refresh in {remaining:.0f}s"

        count = len(self._queries)
        count_text = f"{count} queries" if self._loaded else ""

        parts = [user_label]
        if count_text:
            parts.append(count_text)
        parts.append(refresh_text)
        bar.update(" \u2502 ".join(parts))
        bar.set_class(is_loading, "loading")

    def watch_show_all_users(self) -> None:
        self._update_status_bar()
        self._schedule_refresh()

    def _schedule_refresh(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        self._update_status_bar()
        self.run_worker(self._fetch_queries, thread=True)

    def _fetch_queries(self) -> list[QueryInfo]:
        if self._client is None:
            self._client = TrinopsClient.from_profile(self._profile)
        query_user = None if self.show_all_users else self._profile.user
        return self._client.list_queries(limit=self._profile.query_limit, query_user=query_user)

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name != "_fetch_queries":
            return
        if event.state == WorkerState.SUCCESS:
            self._queries = event.worker.result
            if not self._loaded:
                self._loaded = True
            self._update_table()
            self._last_refresh = time.monotonic()
            self._refreshing = False
            self._update_status_bar()
        elif event.state in (WorkerState.ERROR, WorkerState.CANCELLED):
            self._refreshing = False
            self._update_status_bar()

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

        cursor_key = None
        if table.row_count > 0 and table.cursor_row is not None:
            try:
                cursor_key = str(table.get_row_at(table.cursor_row)[0])
            except Exception:
                pass

        existing_keys = set()
        for row_key in list(table.rows):
            key_str = str(row_key.value)
            if key_str not in new_keys:
                table.remove_row(row_key)
            else:
                existing_keys.add(key_str)

        col_keys = list(table.columns.keys())
        for qi_id, row in new_data.items():
            if qi_id in existing_keys:
                for col_idx, col_key in enumerate(col_keys):
                    table.update_cell(qi_id, col_key, row[col_idx])
            else:
                table.add_row(*row, key=qi_id)

        if cursor_key is not None:
            for idx in range(table.row_count):
                try:
                    if str(table.get_row_at(idx)[0]) == cursor_key:
                        table.move_cursor(row=idx)
                        break
                except Exception:
                    break

    def _show_detail(self, qi: QueryInfo) -> None:
        pane = self.query_one("#detail-pane")
        meta = self.query_one("#detail-meta", Static)
        sql_area = self.query_one("#detail-sql", TextArea)

        lines = [
            f"Query ID: {qi.query_id}    State: {qi.state.value}    User: {qi.user}",
            f"Elapsed: {_format_time(qi.elapsed_time_millis)}    "
            f"CPU: {_format_time(qi.cpu_time_millis)}    "
            f"Rows: {qi.processed_rows:,}    "
            f"Data: {_format_bytes(qi.processed_bytes)}    "
            f"Memory: {_format_bytes(qi.peak_memory_bytes)}",
        ]
        if qi.error_message:
            lines.append(f"Error: {qi.error_message}")

        meta.update("\n".join(lines))
        sql_area.load_text(qi.query)
        pane.add_class("visible")
        sql_area.focus()

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        table = self.query_one("#query-table", DataTable)
        col_key = event.column_key
        # Toggle sort direction if clicking the same column again
        if getattr(self, "_sort_col", None) == col_key:
            self._sort_reverse = not getattr(self, "_sort_reverse", False)
        else:
            self._sort_col = col_key
            self._sort_reverse = False
        table.sort(col_key, reverse=self._sort_reverse)

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        for qi in self._queries:
            if qi.query_id == str(event.row_key.value):
                self._show_detail(qi)
                return

    def action_close_detail(self) -> None:
        pane = self.query_one("#detail-pane")
        pane.remove_class("visible")
        self.query_one("#query-table", DataTable).focus()

    def action_refresh(self) -> None:
        self._schedule_refresh()

    def action_toggle_user(self) -> None:
        self.show_all_users = not self.show_all_users

    def action_show_all(self) -> None:
        self.show_all_users = True

    def action_interval_down(self) -> None:
        steps = self.INTERVAL_STEPS
        new = steps[0]
        for s in steps:
            if s < self._interval:
                new = s
        self._set_interval(new)

    def action_interval_up(self) -> None:
        steps = self.INTERVAL_STEPS
        for s in steps:
            if s > self._interval:
                self._set_interval(s)
                return
        self._set_interval(steps[-1])

    def _set_interval(self, seconds: float) -> None:
        self._interval = seconds
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
        self._refresh_timer = self.set_interval(self._interval, self._schedule_refresh)
        self._update_status_bar()
