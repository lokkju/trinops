"""Detail pane with tabbed content for query detail view."""
from __future__ import annotations

from typing import Optional

from textual.app import ComposeResult
from textual.containers import Container
from textual.widgets import TabbedContent, TabPane

from trinops.tui.tabs.overview import OverviewTab
from trinops.tui.tabs.stats import StatsTab
from trinops.tui.tabs.tables import TablesTab
from trinops.tui.tabs.errors import ErrorsTab


class DetailPane(Container):
    """Tabbed detail view for a single query.

    Receives raw REST API response dict via set_data().
    Tracks query_id for kill-from-detail support.
    """

    DEFAULT_CSS = """
    DetailPane {
        height: auto;
        max-height: 50%;
        border-top: solid green;
        display: none;
    }
    DetailPane.visible {
        display: block;
    }
    DetailPane TabbedContent {
        height: auto;
    }
    DetailPane TabPane {
        height: auto;
        padding: 0;
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
