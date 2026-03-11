"""tqdm-based progress display."""

from __future__ import annotations

try:
    from tqdm.auto import tqdm
except ImportError:
    raise ImportError(
        "tqdm is required for TqdmDisplay. "
        "Install it with: pip install trino-progress[tqdm]"
    )

from trino_progress.stats import QueryStats


class TqdmDisplay:
    def __init__(self, **tqdm_kwargs) -> None:
        self._tqdm_kwargs = tqdm_kwargs
        self._pbar: tqdm | None = None

    def on_stats(self, stats: QueryStats) -> None:
        if self._pbar is None:
            self._pbar = tqdm(
                total=stats.total_splits,
                unit="splits",
                desc=stats.state,
                **self._tqdm_kwargs,
            )

        if self._pbar.total != stats.total_splits:
            self._pbar.total = stats.total_splits
            self._pbar.refresh()

        self._pbar.n = stats.completed_splits
        self._pbar.set_description(stats.state)
        self._pbar.set_postfix(
            rows=f"{stats.processed_rows:,}",
            cpu=f"{stats.cpu_time_millis / 1000:.1f}s",
            mem=f"{stats.peak_memory_bytes / 1024 / 1024:.0f}MB",
            refresh=False,
        )
        self._pbar.refresh()

    def close(self) -> None:
        if self._pbar is not None:
            self._pbar.close()
