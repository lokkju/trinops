import json
import time
import urllib.request

from trinops.progress.display.web import WebDisplay
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


def test_web_display_serves_stats_json():
    display = WebDisplay(port=0)
    stats = parse_stats(RUNNING_STATS)
    display.on_stats(stats)

    url = f"http://localhost:{display.port}/stats"
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.loads(resp.read())

    assert data["state"] == "RUNNING"
    assert data["completed_splits"] == 60
    display.close()


def test_web_display_serves_history():
    display = WebDisplay(port=0)
    stats1 = parse_stats(RUNNING_STATS)
    display.on_stats(stats1)
    stats2 = parse_stats({**RUNNING_STATS, "completedSplits": 80})
    display.on_stats(stats2)

    url = f"http://localhost:{display.port}/stats/history"
    with urllib.request.urlopen(url, timeout=5) as resp:
        data = json.loads(resp.read())

    assert len(data) == 2
    assert data[0]["completed_splits"] == 60
    assert data[1]["completed_splits"] == 80
    display.close()


def test_web_display_serves_html():
    display = WebDisplay(port=0)
    stats = parse_stats(RUNNING_STATS)
    display.on_stats(stats)

    url = f"http://localhost:{display.port}/"
    with urllib.request.urlopen(url, timeout=5) as resp:
        html = resp.read().decode()

    assert "<html" in html.lower()
    assert "trino" in html.lower()
    display.close()


def test_web_display_close_stops_server():
    display = WebDisplay(port=0)
    port = display.port
    display.close()

    try:
        urllib.request.urlopen(f"http://localhost:{port}/stats", timeout=1)
        assert False, "Server should be stopped"
    except Exception:
        pass
