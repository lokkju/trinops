"""Main TrinoProgress entry point."""

from __future__ import annotations

import logging
import sys
from typing import Any, Sequence

from trinops.progress.display import Display
from trinops.progress.display.stderr import StderrDisplay
from trinops.progress.poller import QueryPoller
from trinops.progress.stats import QueryStats

logger = logging.getLogger(__name__)


def _resolve_displays(display, web_port: int = 0) -> list[Display]:
    if isinstance(display, list):
        result = []
        for d in display:
            if isinstance(d, str):
                result.extend(_resolve_displays(d, web_port=web_port))
            else:
                result.append(d)
        return result

    if isinstance(display, str):
        if display == "stderr":
            return [StderrDisplay()]
        elif display == "tqdm":
            from trinops.progress.display.tqdm import TqdmDisplay
            return [TqdmDisplay()]
        elif display == "web":
            from trinops.progress.display.web import WebDisplay
            return [WebDisplay(port=web_port)]
        elif display == "auto":
            try:
                from trinops.progress.display.tqdm import TqdmDisplay
                return [TqdmDisplay()]
            except ImportError:
                return [StderrDisplay()]
        else:
            raise ValueError(f"Unknown display type: {display!r}")

    return [display]


def _is_cursor(obj) -> bool:
    return hasattr(obj, "execute") and hasattr(obj, "fetchall")


class TrinoProgress:
    def __init__(
        self,
        cursor_or_connection,
        query_id: str | None = None,
        display: str | list | Display = "auto",
        interval: float = 1.0,
        max_failures: int = 5,
        web_port: int = 0,
    ) -> None:
        self._displays = _resolve_displays(display, web_port=web_port)
        self._interval = interval
        self._max_failures = max_failures
        self._poller: QueryPoller | None = None

        if _is_cursor(cursor_or_connection):
            self._cursor = cursor_or_connection
            self._connection = cursor_or_connection.connection
            self._query_id = query_id
            self._mode = "cursor"
        else:
            self._cursor = None
            self._connection = cursor_or_connection
            self._query_id = query_id
            self._mode = "standalone"

    def __enter__(self) -> TrinoProgress:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._poller is not None:
            self._poller.wait(timeout=30)
            self._poller.stop()
        self._close_displays()
        return None

    def start(self) -> None:
        if self._query_id is None:
            raise ValueError("query_id is required for standalone mode")
        self._start_poller()

    def stop(self) -> None:
        if self._poller is not None:
            self._poller.stop()
        self._close_displays()

    def wait(self, timeout: float | None = None) -> None:
        if self._poller is not None:
            self._poller.wait(timeout=timeout)
        self._close_displays()

    def execute(self, operation: str, parameters: Sequence | None = None) -> None:
        if self._cursor is None:
            raise RuntimeError("execute() requires cursor mode")
        if parameters is not None:
            self._cursor.execute(operation, parameters)
        else:
            self._cursor.execute(operation)
        self._query_id = self._cursor.query_id
        self._start_poller()

    def fetchone(self) -> Any:
        return self._cursor.fetchone()

    def fetchall(self) -> list:
        return self._cursor.fetchall()

    def fetchmany(self, size: int | None = None) -> list:
        if size is not None:
            return self._cursor.fetchmany(size)
        return self._cursor.fetchmany()

    def __iter__(self):
        return iter(self._cursor)

    @property
    def description(self):
        return self._cursor.description

    @property
    def query_id(self) -> str | None:
        return self._query_id

    @property
    def last_stats(self) -> QueryStats | None:
        if self._poller is not None:
            return self._poller.last_stats
        return None

    def _start_poller(self) -> None:
        self._poller = QueryPoller.from_connection(
            self._connection,
            query_id=self._query_id,
            interval=self._interval,
            max_failures=self._max_failures,
        )
        for display in self._displays:
            self._poller.add_callback(display.on_stats)
        self._poller.start()

    def _close_displays(self) -> None:
        for display in self._displays:
            try:
                display.close()
            except Exception:
                logger.exception("Error closing display")
