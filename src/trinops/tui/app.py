from __future__ import annotations

import time

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Footer, Header, Label, Static
from textual.timer import Timer
from textual.worker import Worker, WorkerState

from trinops.client import TrinopsClient
from trinops.config import ConnectionProfile
from trinops.formatting import format_bytes as _format_bytes, format_time_millis as _format_time
from trinops.models import ClusterStats, QueryInfo
from trinops.tui.detail import DetailPane


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
    #empty-message {
        width: 100%;
        height: 1fr;
        content-align: center middle;
        color: $text-muted;
        display: none;
    }
    #empty-message.visible {
        display: block;
    }
    #status-bar {
        height: 1;
    }
"""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh", "Refresh"),
        ("u", "toggle_user", "My queries"),
        ("a", "show_all", "All queries"),
        Binding("escape", "close_detail", "Close detail", show=False),
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
        yield Static("No queries", id="empty-message")
        yield DetailPane(id="detail-pane")
        yield StatusBar(id="status-bar")
        yield Footer()

    _COLUMN_LABELS = ("Query ID", "State", "User", "Elapsed", "Rows", "Memory", "SQL")

    def on_mount(self) -> None:
        table = self.query_one("#query-table", DataTable)
        col_keys = table.add_columns(*self._COLUMN_LABELS)
        table.cursor_type = "row"
        # Default sort: Elapsed descending (index 3)
        self._sort_col = col_keys[3]
        self._sort_reverse = True
        self._update_column_carets()

        if self._profile.allow_kill:
            self.bind("k", "kill_query", description="Kill query")

        table.focus()
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
        self._update_empty_message()
        self._schedule_refresh()

    # --- Query worker ---

    def _schedule_refresh(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        self._update_status_bar()
        self._update_empty_message()
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
        elif event.worker.name == "_fetch_query_raw":
            self._on_detail_done(event)
        elif event.worker.name == "_do_kill_query":
            self._on_kill_done(event)

    def _on_queries_done(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.SUCCESS:
            self._queries = event.worker.result
            if not self._loaded:
                self._loaded = True
            self._refreshing = False
            self._last_refresh = time.monotonic()
            self._update_table()
            self._update_empty_message()
            self._update_status_bar()
            # Trigger stats refresh so header picks up the new query data
            self._schedule_stats_refresh()
        elif event.state in (WorkerState.ERROR, WorkerState.CANCELLED):
            self._refreshing = False
            error = event.worker.error if event.state == WorkerState.ERROR else None
            if error is not None:
                self._handle_worker_error(error)
            self._update_status_bar()

    def _on_stats_done(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.SUCCESS:
            header = self.query_one("#cluster-header", ClusterHeader)
            header.update_stats(event.worker.result)
        elif event.state == WorkerState.ERROR and event.worker.error is not None:
            self._handle_worker_error(event.worker.error)
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

    def _handle_worker_error(self, error: BaseException) -> None:
        error_name = type(error).__name__
        msg = str(error)
        if "auth" in error_name.lower() or "401" in msg:
            self._flash(f"Auth failed: {msg}", duration=10.0)
            # Reset client so next refresh retries auth
            self._client = None
        elif "connect" in error_name.lower() or "connection" in msg.lower():
            self._flash(f"Connection error: {msg}", duration=10.0)
            self._client = None
        else:
            self._flash(f"Error: {msg}", duration=5.0)

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

    def _update_empty_message(self) -> None:
        empty = self.query_one("#empty-message", Static)
        table = self.query_one("#query-table", DataTable)
        detail = self.query_one("#detail-pane", DetailPane)
        show_empty = table.row_count == 0
        if show_empty:
            user = "all users" if self.show_all_users else (self._profile.user or "?")
            if self._refreshing or not self._loaded:
                empty.update(f"Refreshing queries for {user}")
            else:
                empty.update(f"No queries for {user}")
            empty.add_class("visible")
            table.display = False
        else:
            empty.remove_class("visible")
            table.display = True
            if not detail.has_class("visible"):
                table.focus()

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

        if self._sort_col is not None:
            table.sort(self._sort_col, reverse=self._sort_reverse)

        if cursor_key is not None:
            for idx in range(table.row_count):
                try:
                    if str(table.get_row_at(idx)[0]) == cursor_key:
                        table.move_cursor(row=idx)
                        break
                except Exception:
                    break

    def _show_detail_raw(self, data: dict) -> None:
        pane = self.query_one("#detail-pane", DetailPane)
        pane.set_data(data)
        pane.show()

    def _fetch_query_raw(self, query_id: str) -> dict | None:
        if self._client is None:
            self._client = TrinopsClient.from_profile(self._profile)
        return self._client.get_query_raw(query_id)

    def _on_detail_done(self, event: Worker.StateChanged) -> None:
        if event.state == WorkerState.SUCCESS:
            data = event.worker.result
            if data is None:
                self._flash("Query no longer available")
                return
            self._show_detail_raw(data)
        elif event.state == WorkerState.ERROR:
            self._flash(f"Failed to load query detail: {event.worker.error}")

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        table = self.query_one("#query-table", DataTable)
        col_key = event.column_key
        if self._sort_col == col_key:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col_key
            self._sort_reverse = False
        table.sort(col_key, reverse=self._sort_reverse)
        self._update_column_carets()

    def _update_column_carets(self) -> None:
        table = self.query_one("#query-table", DataTable)
        for col_key, column in table.columns.items():
            idx = list(table.columns.keys()).index(col_key)
            base = self._COLUMN_LABELS[idx]
            if col_key == self._sort_col:
                caret = " \u25b2" if not self._sort_reverse else " \u25bc"
                column.label = base + caret
            else:
                column.label = base

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        query_id = str(event.row_key.value)
        self.run_worker(
            lambda: self._fetch_query_raw(query_id),
            thread=True,
            name="_fetch_query_raw",
        )

    def action_close_detail(self) -> None:
        pane = self.query_one("#detail-pane", DetailPane)
        pane.hide()
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

        pane = self.query_one("#detail-pane", DetailPane)
        query_id = None
        if pane.has_class("visible") and pane.query_id:
            query_id = pane.query_id
        else:
            table = self.query_one("#query-table", DataTable)
            if table.row_count == 0 or table.cursor_row is None:
                return
            try:
                query_id = str(table.get_row_at(table.cursor_row)[0])
            except Exception:
                return

        if query_id is None:
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
