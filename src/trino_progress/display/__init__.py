"""Display backends for Trino progress monitoring."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from trino_progress.stats import QueryStats


@runtime_checkable
class Display(Protocol):
    def on_stats(self, stats: QueryStats) -> None: ...
    def close(self) -> None: ...
