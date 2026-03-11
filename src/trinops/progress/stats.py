"""Query and stage statistics for Trino progress monitoring."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


TERMINAL_STATES = frozenset({"FINISHED", "FAILED"})


@dataclass(frozen=True)
class StageStats:
    stage_id: str
    state: str
    done: bool
    nodes: int
    total_splits: int
    queued_splits: int
    running_splits: int
    completed_splits: int
    cpu_time_millis: int
    wall_time_millis: int
    processed_rows: int
    processed_bytes: int
    failed_tasks: int
    sub_stages: tuple[StageStats, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class QueryStats:
    state: str
    queued: bool
    scheduled: bool
    nodes: int
    total_splits: int
    queued_splits: int
    running_splits: int
    completed_splits: int
    cpu_time_millis: int
    wall_time_millis: int
    queued_time_millis: int
    elapsed_time_millis: int
    processed_rows: int
    processed_bytes: int
    physical_input_bytes: int
    peak_memory_bytes: int
    spilled_bytes: int
    progress_percentage: Optional[float] = None
    planning_time_millis: Optional[int] = None
    analysis_time_millis: Optional[int] = None
    finishing_time_millis: Optional[int] = None
    physical_written_bytes: Optional[int] = None
    root_stage: Optional[StageStats] = None
    error: Optional[dict] = None

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES


def _parse_stage(data: dict) -> StageStats:
    return StageStats(
        stage_id=data["stageId"],
        state=data["state"],
        done=data.get("done", False),
        nodes=data.get("nodes", 0),
        total_splits=data.get("totalSplits", 0),
        queued_splits=data.get("queuedSplits", 0),
        running_splits=data.get("runningSplits", 0),
        completed_splits=data.get("completedSplits", 0),
        cpu_time_millis=data.get("cpuTimeMillis", 0),
        wall_time_millis=data.get("wallTimeMillis", 0),
        processed_rows=data.get("processedRows", 0),
        processed_bytes=data.get("processedBytes", 0),
        failed_tasks=data.get("failedTasks", 0),
        sub_stages=tuple(_parse_stage(s) for s in data.get("subStages", [])),
    )


def parse_stats(data: dict) -> QueryStats:
    root_stage = None
    if "rootStage" in data and data["rootStage"] is not None:
        root_stage = _parse_stage(data["rootStage"])

    return QueryStats(
        state=data["state"],
        queued=data.get("queued", False),
        scheduled=data.get("scheduled", False),
        nodes=data.get("nodes", 0),
        total_splits=data.get("totalSplits", 0),
        queued_splits=data.get("queuedSplits", 0),
        running_splits=data.get("runningSplits", 0),
        completed_splits=data.get("completedSplits", 0),
        cpu_time_millis=data.get("cpuTimeMillis", 0),
        wall_time_millis=data.get("wallTimeMillis", 0),
        queued_time_millis=data.get("queuedTimeMillis", 0),
        elapsed_time_millis=data.get("elapsedTimeMillis", 0),
        processed_rows=data.get("processedRows", 0),
        processed_bytes=data.get("processedBytes", 0),
        physical_input_bytes=data.get("physicalInputBytes", 0),
        peak_memory_bytes=data.get("peakMemoryBytes", 0),
        spilled_bytes=data.get("spilledBytes", 0),
        progress_percentage=data.get("progressPercentage"),
        planning_time_millis=data.get("planningTimeMillis"),
        analysis_time_millis=data.get("analysisTimeMillis"),
        finishing_time_millis=data.get("finishingTimeMillis"),
        physical_written_bytes=data.get("physicalWrittenBytes"),
        root_stage=root_stage,
        error=data.get("error"),
    )
