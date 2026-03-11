from trino_progress.stats import QueryStats, StageStats, parse_stats


SAMPLE_STATS = {
    "state": "RUNNING",
    "queued": False,
    "scheduled": True,
    "progressPercentage": 45.2,
    "nodes": 12,
    "totalSplits": 988,
    "queuedSplits": 100,
    "runningSplits": 200,
    "completedSplits": 688,
    "cpuTimeMillis": 19212,
    "wallTimeMillis": 53095,
    "queuedTimeMillis": 1,
    "elapsedTimeMillis": 6872,
    "planningTimeMillis": 50,
    "analysisTimeMillis": 30,
    "finishingTimeMillis": 0,
    "processedRows": 34148040,
    "processedBytes": 474640412,
    "physicalInputBytes": 474640412,
    "physicalWrittenBytes": 0,
    "peakMemoryBytes": 8650480,
    "spilledBytes": 0,
    "rootStage": {
        "stageId": "0",
        "state": "RUNNING",
        "done": False,
        "nodes": 1,
        "totalSplits": 100,
        "queuedSplits": 10,
        "runningSplits": 40,
        "completedSplits": 50,
        "cpuTimeMillis": 5000,
        "wallTimeMillis": 10000,
        "processedRows": 1000000,
        "processedBytes": 50000000,
        "failedTasks": 0,
        "subStages": [
            {
                "stageId": "1",
                "state": "FINISHED",
                "done": True,
                "nodes": 11,
                "totalSplits": 888,
                "queuedSplits": 0,
                "runningSplits": 0,
                "completedSplits": 888,
                "cpuTimeMillis": 14000,
                "wallTimeMillis": 43000,
                "processedRows": 33148040,
                "processedBytes": 424640412,
                "failedTasks": 0,
                "subStages": [],
            }
        ],
    },
}


def test_parse_stats_basic_fields():
    stats = parse_stats(SAMPLE_STATS)
    assert isinstance(stats, QueryStats)
    assert stats.state == "RUNNING"
    assert stats.total_splits == 988
    assert stats.completed_splits == 688
    assert stats.running_splits == 200
    assert stats.queued_splits == 100
    assert stats.cpu_time_millis == 19212
    assert stats.elapsed_time_millis == 6872
    assert stats.processed_rows == 34148040
    assert stats.processed_bytes == 474640412
    assert stats.peak_memory_bytes == 8650480
    assert stats.progress_percentage == 45.2


def test_parse_stats_stages():
    stats = parse_stats(SAMPLE_STATS)
    assert stats.root_stage is not None
    assert stats.root_stage.stage_id == "0"
    assert stats.root_stage.state == "RUNNING"
    assert stats.root_stage.completed_splits == 50
    assert len(stats.root_stage.sub_stages) == 1
    assert stats.root_stage.sub_stages[0].stage_id == "1"
    assert stats.root_stage.sub_stages[0].done is True


def test_parse_stats_immutable():
    stats = parse_stats(SAMPLE_STATS)
    try:
        stats.state = "FINISHED"
        assert False, "Should have raised"
    except AttributeError:
        pass


def test_parse_stats_missing_optional_fields():
    minimal = {
        "state": "QUEUED",
        "queued": True,
        "scheduled": False,
        "nodes": 0,
        "totalSplits": 0,
        "queuedSplits": 0,
        "runningSplits": 0,
        "completedSplits": 0,
        "cpuTimeMillis": 0,
        "wallTimeMillis": 0,
        "queuedTimeMillis": 0,
        "elapsedTimeMillis": 0,
        "processedRows": 0,
        "processedBytes": 0,
        "physicalInputBytes": 0,
        "peakMemoryBytes": 0,
        "spilledBytes": 0,
    }
    stats = parse_stats(minimal)
    assert stats.state == "QUEUED"
    assert stats.root_stage is None
    assert stats.progress_percentage is None
    assert stats.planning_time_millis is None


def test_query_stats_is_terminal():
    for state in ("FINISHED", "FAILED"):
        stats = parse_stats({**SAMPLE_STATS, "state": state})
        assert stats.is_terminal is True
    for state in ("QUEUED", "PLANNING", "STARTING", "RUNNING", "FINISHING"):
        stats = parse_stats({**SAMPLE_STATS, "state": state})
        assert stats.is_terminal is False
