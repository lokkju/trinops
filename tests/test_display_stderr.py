import io
from unittest.mock import patch

from trinops.progress.display.stderr import StderrDisplay
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


def test_stderr_display_on_stats():
    buf = io.StringIO()
    display = StderrDisplay(file=buf)
    stats = parse_stats(RUNNING_STATS)
    display.on_stats(stats)
    output = buf.getvalue()
    assert "RUNNING" in output
    assert "60/100" in output


def test_stderr_display_close():
    buf = io.StringIO()
    display = StderrDisplay(file=buf)
    stats = parse_stats(RUNNING_STATS)
    display.on_stats(stats)
    display.close()
    output = buf.getvalue()
    assert output.endswith("\n")


def test_stderr_display_finished():
    buf = io.StringIO()
    display = StderrDisplay(file=buf)
    finished = {**RUNNING_STATS, "state": "FINISHED", "completedSplits": 100, "runningSplits": 0, "queuedSplits": 0}
    stats = parse_stats(finished)
    display.on_stats(stats)
    output = buf.getvalue()
    assert "FINISHED" in output
