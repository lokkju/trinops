from __future__ import annotations

import time

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static, TextArea
from textual.timer import Timer
from textual.worker import Worker, WorkerState

from trinops.client import TrinopsClient
from trinops.config import ConnectionProfile
from trinops.formatting import format_bytes as _format_bytes, format_time_millis as _format_time
from trinops.models import ClusterStats, QueryInfo


class KillConfirmScreen(ModalScreen[bool]):
    """Confirmation dialog for killing a query."""

    DEFAULT_CSS = """
    KillConfirmScreen {
        align: center middle;
    }
    #kill-dialog {
        width: 70;
        height: auto;
        max-height: 80%;
        border: thick $error;
        background: $surface;
        padding: 1 2;
    }
    #kill-dialog Label {
        width: 100%;
        margin-bottom: 1;
    }
    #kill-buttons {
        width: 100%;
        height: 3;
        align: center middle;
    }
    #kill-buttons Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        ("y", "confirm", "Yes"),
        ("n", "cancel", "No"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, query_id: str, user: str, sql_preview: str) -> None:
        super().__init__()
        self._query_id = query_id
        self._user = user
        self._sql_preview = sql_preview

    def compose(self) -> ComposeResult:
        with Container(id="kill-dialog"):
            yield Label(f"Kill query {self._query_id} by {self._user}?")
            yield Label(self._sql_preview)
            with Horizontal(id="kill-buttons"):
                yield Button("Yes", variant="error", id="kill-yes")
                yield Button("No", variant="primary", id="kill-no")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "kill-yes")


class ClusterHeader(Static):
    """Dense cluster status line, similar to top's summary header."""

    DEFAULT_CSS = """
    ClusterHeader {
        height: auto;
        background: $panel;
        color: $text;
        padding: 0 1;
    }
    """

    def update_stats(self, stats: ClusterStats) -> None:
        w = self.size.width
        if w <= 0:
            w = self.app.size.width if self.app else 120
        width = max(w - 2, 40)  # account for padding
        self.update(stats.format_line(width=width))


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
        Binding("k", "kill_query", "Kill query", show=False),
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
        self._stats_timer: Timer | None = None
        self._countdown_timer: Timer | None = None
        self._refreshing = False
        self._stats_refreshing = False
        self._last_refresh: float = 0.0
        self._loaded = False
        self._flash_message: str | None = None
        self._flash_timer: Timer | None = None
        self._kill_query_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield ClusterHeader(id="cluster-header")
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

        # Show kill binding in footer only when allow_kill is enabled
        if self._profile.allow_kill:
            for binding in self._bindings:
                if binding.action == "kill_query":
                    binding.show = True
                    break

        self._update_status_bar()
        self._refresh_timer = self.set_interval(self._interval, self._schedule_refresh)
        self._stats_timer = self.set_interval(self._interval, self._schedule_stats_refresh)
        self._countdown_timer = self.set_interval(0.5, self._update_status_bar)
        self._schedule_refresh()
        self._schedule_stats_refresh()

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

        if self._flash_message:
            bar.update(self._flash_message)
            bar.set_class(False, "loading")
            return

        parts = [user_label]
        if count_text:
            parts.append(count_text)
        parts.append(refresh_text)
        bar.update(" \u2502 ".join(parts))
        bar.set_class(is_loading, "loading")

    def watch_show_all_users(self) -> None:
        self._update_status_bar()
        self._schedule_refresh()

    # --- Query worker ---

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

    # --- Stats worker ---

    def _schedule_stats_refresh(self) -> None:
        if self._stats_refreshing:
            return
        self._stats_refreshing = True
        self.run_worker(self._fetch_stats, thread=True)

    def _fetch_stats(self) -> ClusterStats:
        if self._client is None:
            self._client = TrinopsClient.from_profile(self._profile)
        return self._client.build_cluster_stats(self._queries)

    # --- Worker completion ---

    def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.name == "_fetch_queries":
            self._on_queries_done(event)
        elif event.worker.name == "_fetch_stats":
            self._on_stats_done(event)
        elif event.worker.name == "_do_kill_query":
            self._on_kill_done(event)

    def _on_queries_done(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.SUCCESS:
            self._queries = event.worker.result
            if not self._loaded:
                self._loaded = True
            self._update_table()
            self._last_refresh = time.monotonic()
            self._refreshing = False
            self._update_status_bar()
            # Trigger stats refresh so header picks up the new query data
            self._schedule_stats_refresh()
        elif event.state in (WorkerState.ERROR, WorkerState.CANCELLED):
            self._refreshing = False
            self._update_status_bar()

    def _on_stats_done(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.SUCCESS:
            header = self.query_one("#cluster-header", ClusterHeader)
            header.update_stats(event.worker.result)
        self._stats_refreshing = False

    def _on_kill_done(self, event: Worker.StateChanged) -> None:
        qid = self._kill_query_id
        self._kill_query_id = None
        if event.state == WorkerState.SUCCESS:
            if event.worker.result:
                self._flash(f"Killed {qid}")
            else:
                self._flash(f"Query {qid} already completed")
            self._schedule_refresh()
        elif event.state == WorkerState.ERROR:
            self._flash(f"Kill failed: {event.worker.error}")

    def _do_kill_query(self, query_id: str) -> bool:
        if self._client is None:
            self._client = TrinopsClient.from_profile(self._profile)
        return self._client.kill_query(query_id)

    def _flash(self, message: str, duration: float = 3.0) -> None:
        self._flash_message = message
        self._update_status_bar()
        if self._flash_timer is not None:
            self._flash_timer.stop()
        self._flash_timer = self.set_timer(duration, self._clear_flash)

    def _clear_flash(self) -> None:
        self._flash_message = None
        self._flash_timer = None
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

    def action_quit(self) -> None:
        self.workers.cancel_all()
        self.exit()

    def action_refresh(self) -> None:
        self._schedule_refresh()
        self._schedule_stats_refresh()

    def action_toggle_user(self) -> None:
        self.show_all_users = not self.show_all_users

    def action_show_all(self) -> None:
        self.show_all_users = True

    def action_kill_query(self) -> None:
        if not self._profile.allow_kill:
            return
        table = self.query_one("#query-table", DataTable)
        if table.row_count == 0 or table.cursor_row is None:
            return
        try:
            query_id = str(table.get_row_at(table.cursor_row)[0])
        except Exception:
            return
        qi = None
        for q in self._queries:
            if q.query_id == query_id:
                qi = q
                break
        if qi is None:
            return

        if self._profile.confirm_kill:
            def on_confirm(confirmed: bool) -> None:
                if confirmed:
                    self._execute_kill(qi.query_id)
            self.push_screen(
                KillConfirmScreen(qi.query_id, qi.user, qi.truncated_sql(80)),
                on_confirm,
            )
        else:
            self._execute_kill(qi.query_id)

    def _execute_kill(self, query_id: str) -> None:
        self._kill_query_id = query_id
        self._flash(f"Killing {query_id}...")
        self.run_worker(lambda: self._do_kill_query(query_id), thread=True, name="_do_kill_query")

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
        if self._stats_timer is not None:
            self._stats_timer.stop()
        self._stats_timer = self.set_interval(self._interval, self._schedule_stats_refresh)
        self._update_status_bar()
