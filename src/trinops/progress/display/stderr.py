"""Stderr-based progress display."""

from __future__ import annotations

import sys
from typing import TextIO

from trinops.formatting import format_bytes as _format_bytes, format_time_millis as _format_time
from trinops.progress.stats import QueryStats


class StderrDisplay:
    def __init__(self, file: TextIO | None = None) -> None:
        self._file = file or sys.stderr
        self._started = False

    def on_stats(self, stats: QueryStats) -> None:
        splits = f"{stats.completed_splits}/{stats.total_splits}"
        rows = f"{stats.processed_rows:,} rows"
        bytes_ = _format_bytes(stats.processed_bytes)
        elapsed = _format_time(stats.elapsed_time_millis)
        cpu = _format_time(stats.cpu_time_millis)

        line = f"\r{stats.state} | splits {splits} | {rows} | {bytes_} | elapsed {elapsed} | cpu {cpu}"
        self._file.write(line)
        self._file.flush()
        self._started = True

    def close(self) -> None:
        if self._started:
            self._file.write("\n")
            self._file.flush()
