"""Trino query progress poller."""

from __future__ import annotations

import json
import logging
import threading
import warnings
from typing import Callable
from urllib.request import Request, urlopen

from trinops.progress.stats import QueryStats, parse_stats

logger = logging.getLogger(__name__)


class QueryPoller:
    def __init__(
        self,
        host: str,
        port: int,
        http_scheme: str = "http",
        query_id: str = "",
        interval: float = 1.0,
        max_failures: int = 5,
    ) -> None:
        warnings.warn(
            "QueryPoller uses /v1/query/{id} which is not a stable Trino API. "
            "Use CursorPoller (cursor mode) instead. Standalone HTTP polling will "
            "be replaced when Trino #22488 lands.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._host = host
        self._port = port
        self._http_scheme = http_scheme
        self._query_id = query_id
        self._interval = interval
        self._max_failures = max_failures
        self._callbacks: list[Callable[[QueryStats], None]] = []
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._done_event = threading.Event()
        self._last_stats: QueryStats | None = None

    @classmethod
    def from_connection(
        cls,
        connection,
        query_id: str,
        interval: float = 1.0,
        max_failures: int = 5,
    ) -> QueryPoller:
        return cls(
            host=connection.host,
            port=connection.port,
            http_scheme=connection.http_scheme,
            query_id=query_id,
            interval=interval,
            max_failures=max_failures,
        )

    def add_callback(self, callback: Callable[[QueryStats], None]) -> None:
        self._callbacks.append(callback)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def wait(self, timeout: float | None = None) -> None:
        self._done_event.wait(timeout=timeout)
        if self._thread is not None:
            self._thread.join(timeout=2)

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def last_stats(self) -> QueryStats | None:
        return self._last_stats

    def _build_url(self) -> str:
        return f"{self._http_scheme}://{self._host}:{self._port}/v1/query/{self._query_id}"

    def _fetch_stats(self) -> QueryStats:
        url = self._build_url()
        request = Request(url, headers={"Accept": "application/json"})
        with urlopen(request, timeout=max(self._interval, 2.0)) as response:
            data = json.loads(response.read())

        return parse_stats(data["stats"])

    def _poll_loop(self) -> None:
        consecutive_failures = 0

        try:
            while not self._stop_event.is_set():
                try:
                    stats = self._fetch_stats()
                    consecutive_failures = 0
                    self._last_stats = stats

                    for callback in self._callbacks:
                        try:
                            callback(stats)
                        except Exception:
                            logger.exception("Display callback error")

                    if stats.is_terminal:
                        return

                except Exception:
                    consecutive_failures += 1
                    logger.warning(
                        "Failed to poll Trino stats (attempt %d/%d)",
                        consecutive_failures,
                        self._max_failures,
                    )
                    if consecutive_failures >= self._max_failures:
                        logger.error("Max poll failures reached, stopping poller")
                        return

                self._stop_event.wait(timeout=self._interval)
        finally:
            self._done_event.set()


class CursorPoller:
    """Polls a trino cursor's stats property in a background thread."""

    def __init__(
        self,
        cursor,
        interval: float = 1.0,
    ) -> None:
        self._cursor = cursor
        self._interval = interval
        self._callbacks: list[Callable[[QueryStats], None]] = []
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._done_event = threading.Event()
        self._last_stats: QueryStats | None = None

    def add_callback(self, callback: Callable[[QueryStats], None]) -> None:
        self._callbacks.append(callback)

    def start(self) -> None:
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def wait(self, timeout: float | None = None) -> None:
        self._done_event.wait(timeout=timeout)
        if self._thread is not None:
            self._thread.join(timeout=2)

    def is_alive(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def last_stats(self) -> QueryStats | None:
        return self._last_stats

    def _poll_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    raw_stats = self._cursor.stats
                    if raw_stats is None:
                        self._stop_event.wait(timeout=self._interval)
                        continue
                    stats = parse_stats(raw_stats)
                    self._last_stats = stats

                    for callback in self._callbacks:
                        try:
                            callback(stats)
                        except Exception:
                            logger.exception("Display callback error")

                    if stats.is_terminal:
                        return

                except Exception:
                    logger.exception("Error polling cursor stats")
                    return

                self._stop_event.wait(timeout=self._interval)
        finally:
            self._done_event.set()
