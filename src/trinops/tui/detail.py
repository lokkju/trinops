"""Detail pane with tabbed content for query detail view."""
from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import TabbedContent, TabPane
from textual.widgets._tabs import Tabs

from trinops.tui.tabs.overview import OverviewTab
from trinops.tui.tabs.stats import StatsTab
from trinops.tui.tabs.tables import TablesTab
from trinops.tui.tabs.errors import ErrorsTab


class DetailPane(Container):
    """Tabbed detail view for a single query.

    Receives raw REST API response dict via set_data().
    Tracks query_id for kill-from-detail support.
    Focus lives on this container; scroll keys are forwarded to the active TabPane.
    """

    can_focus = True

    BINDINGS = [
        Binding("up", "scroll_up", "Scroll up", show=False),
        Binding("down", "scroll_down", "Scroll down", show=False),
        Binding("left", "prev_tab", "Prev tab", show=False),
        Binding("right", "next_tab", "Next tab", show=False),
        Binding("pageup", "page_up", "Page up", show=False),
        Binding("pagedown", "page_down", "Page down", show=False),
        Binding("home", "scroll_home", "Top", show=False),
        Binding("end", "scroll_end", "Bottom", show=False),
        Binding("c", "copy_tab", "Copy"),
        Binding("escape", "close_detail", "Close"),
    ]

    DEFAULT_CSS = """
    DetailPane {
        height: 60%;
        border-top: solid $primary;
        display: none;
    }
    DetailPane.visible {
        display: block;
    }
    DetailPane TabbedContent {
        height: 1fr;
    }
    DetailPane ContentSwitcher {
        height: 1fr;
    }
    DetailPane TabPane {
        height: 1fr;
        padding: 0;
        overflow-y: auto;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._query_id: Optional[str] = None
        self._overview = OverviewTab()
        self._stats = StatsTab()
        self._tables = TablesTab()
        self._errors = ErrorsTab()

    @property
    def query_id(self) -> Optional[str]:
        return self._query_id

    _TAB_MAP: dict[str, str] = {
        "tab-1": "_overview",
        "tab-2": "_stats",
        "tab-3": "_tables",
        "tab-4": "_errors",
    }

    def _active_pane(self) -> TabPane | None:
        tc = self.query_one(TabbedContent)
        return tc.active_pane

    def _active_tab_widget(self) -> OverviewTab | StatsTab | TablesTab | ErrorsTab | None:
        tc = self.query_one(TabbedContent)
        attr = self._TAB_MAP.get(tc.active)
        if attr is not None:
            return getattr(self, attr)
        return None

    def compose(self) -> ComposeResult:
        with TabbedContent():
            with TabPane("Overview"):
                yield self._overview
            with TabPane("Stats"):
                yield self._stats
            with TabPane("Tables"):
                yield self._tables
            with TabPane("Errors"):
                yield self._errors

    def set_data(self, data: Optional[dict]) -> None:
        if data is None:
            self._query_id = None
            return
        self._query_id = data.get("queryId")
        for tab in (self._overview, self._stats, self._tables, self._errors):
            tab._data = data
            if self.is_mounted:
                tab.update_data(data)

    def show(self) -> None:
        self.add_class("visible")
        self.focus()

    def hide(self) -> None:
        self.remove_class("visible")
        self._query_id = None

    def action_scroll_up(self) -> None:
        pane = self._active_pane()
        if pane is not None:
            pane.scroll_up()

    def action_scroll_down(self) -> None:
        pane = self._active_pane()
        if pane is not None:
            pane.scroll_down()

    def action_page_up(self) -> None:
        pane = self._active_pane()
        if pane is not None:
            pane.scroll_page_up()

    def action_page_down(self) -> None:
        pane = self._active_pane()
        if pane is not None:
            pane.scroll_page_down()

    def action_scroll_home(self) -> None:
        pane = self._active_pane()
        if pane is not None:
            pane.scroll_home()

    def action_scroll_end(self) -> None:
        pane = self._active_pane()
        if pane is not None:
            pane.scroll_end()

    def action_next_tab(self) -> None:
        self.query_one(Tabs).action_next_tab()

    def action_prev_tab(self) -> None:
        self.query_one(Tabs).action_previous_tab()

    def action_close_detail(self) -> None:
        self.app.action_close_detail()

    def action_copy_tab(self) -> None:
        tab = self._active_tab_widget()
        if tab is None:
            return
        text = tab.render_text()
        self.app.copy_to_clipboard(text)
        self.app._flash("Copied to clipboard")
