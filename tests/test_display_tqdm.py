import pytest

from trinops.progress.display.tqdm import TqdmDisplay
from trinops.progress.stats import parse_stats


RUNNING_STATS = {
    "state": "RUNNING",
    "queued": False,
    "scheduled": True,
    "nodes": 4,
    "totalSplits": 100,
    "queuedSplits": 10,
    "runningSplits": 30,
    "completedSplits": 60,
    "cpuTimeMillis": 5000,
    "wallTimeMillis": 8000,
    "queuedTimeMillis": 100,
    "elapsedTimeMillis": 3000,
    "processedRows": 5000000,
    "processedBytes": 100000000,
    "physicalInputBytes": 100000000,
    "peakMemoryBytes": 4000000,
    "spilledBytes": 0,
}


def test_tqdm_display_updates_progress():
    display = TqdmDisplay()
    stats = parse_stats(RUNNING_STATS)
    display.on_stats(stats)
    assert display._pbar is not None
    assert display._pbar.total == 100
    assert display._pbar.n == 60
    display.close()


def test_tqdm_display_handles_total_change():
    display = TqdmDisplay()
    stats1 = parse_stats(RUNNING_STATS)
    display.on_stats(stats1)
    revised = {**RUNNING_STATS, "totalSplits": 200}
    stats2 = parse_stats(revised)
    display.on_stats(stats2)
    assert display._pbar.total == 200
    display.close()


def test_tqdm_display_close_completes_bar():
    display = TqdmDisplay()
    stats = parse_stats(RUNNING_STATS)
    display.on_stats(stats)
    display.close()
    assert display._pbar.disable


def test_tqdm_not_installed():
    """Verify helpful error when tqdm is missing."""
    import unittest.mock
    import sys

    with unittest.mock.patch.dict(sys.modules, {"tqdm": None, "tqdm.auto": None}):
        import importlib
        from trinops.progress.display import tqdm as tqdm_mod
        with pytest.raises(ImportError, match="tqdm"):
            importlib.reload(tqdm_mod)
