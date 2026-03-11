"""Query models for trinops."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class QueryState(str, Enum):
    QUEUED = "QUEUED"
    WAITING_FOR_RESOURCES = "WAITING_FOR_RESOURCES"
    DISPATCHING = "DISPATCHING"
    PLANNING = "PLANNING"
    STARTING = "STARTING"
    RUNNING = "RUNNING"
    FINISHING = "FINISHING"
    FINISHED = "FINISHED"
    FAILED = "FAILED"

    @property
    def is_terminal(self) -> bool:
        return self in (QueryState.FINISHED, QueryState.FAILED)


@dataclass
class QueryInfo:
    query_id: str
    state: QueryState
    query: str
    user: str
    source: Optional[str] = None
    created: Optional[datetime] = None
    started: Optional[datetime] = None
    ended: Optional[datetime] = None
    cpu_time_millis: int = 0
    wall_time_millis: int = 0
    queued_time_millis: int = 0
    elapsed_time_millis: int = 0
    peak_memory_bytes: int = 0
    cumulative_memory_bytes: int = 0
    processed_rows: int = 0
    processed_bytes: int = 0
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    @property
    def is_terminal(self) -> bool:
        return self.state.is_terminal

    def truncated_sql(self, max_len: int = 80) -> str:
        sql = self.query.replace("\n", " ").strip()
        if len(sql) <= max_len:
            return sql
        return sql[: max_len - 3] + "..."

    @classmethod
    def from_system_row(cls, row: dict) -> QueryInfo:
        return cls(
            query_id=row["query_id"],
            state=QueryState(row["state"]),
            query=row["query"],
            user=row["user"],
            source=row.get("source"),
            created=row.get("created"),
            started=row.get("started"),
            ended=row.get("end"),
            cpu_time_millis=int(row.get("cpu_time", 0) * 1000),
            wall_time_millis=int(row.get("wall_time", 0) * 1000),
            queued_time_millis=int(row.get("queued_time", 0) * 1000),
            elapsed_time_millis=int(row.get("elapsed_time", 0) * 1000),
            peak_memory_bytes=int(row.get("peak_memory_bytes", 0)),
            cumulative_memory_bytes=int(row.get("cumulative_memory", 0)),
            processed_rows=int(row.get("processed_rows", 0)),
            processed_bytes=int(row.get("processed_bytes", 0)),
            error_code=row.get("error_code"),
            error_message=row.get("error_message"),
        )

    @classmethod
    def from_rest_response(cls, data: dict) -> QueryInfo:
        """Build QueryInfo from Trino REST API JSON (BasicQueryInfo or QueryInfo)."""
        from trinops.formatting import parse_duration_millis, parse_data_size_bytes

        stats = data.get("queryStats", {})
        session = data.get("session", {})

        error_code = None
        error_message = None
        if data.get("errorCode"):
            error_code = data["errorCode"].get("name")
        failure_info = data.get("failureInfo")
        if failure_info:
            error_message = failure_info.get("message")

        created = None
        if stats.get("createTime"):
            created = datetime.fromisoformat(stats["createTime"].replace("Z", "+00:00"))
        ended = None
        if stats.get("endTime"):
            ended = datetime.fromisoformat(stats["endTime"].replace("Z", "+00:00"))

        return cls(
            query_id=data["queryId"],
            state=QueryState(data["state"]),
            query=data.get("query", ""),
            user=session.get("user", ""),
            source=session.get("source"),
            created=created,
            ended=ended,
            cpu_time_millis=parse_duration_millis(stats.get("totalCpuTime", "0.00ns")),
            elapsed_time_millis=parse_duration_millis(stats.get("elapsedTime", "0.00ns")),
            queued_time_millis=parse_duration_millis(stats.get("queuedTime", "0.00ns")),
            peak_memory_bytes=parse_data_size_bytes(stats.get("peakUserMemoryReservation", "0B")),
            cumulative_memory_bytes=int(stats.get("cumulativeUserMemory", 0)),
            processed_rows=int(stats.get("processedInputPositions", 0)),
            processed_bytes=parse_data_size_bytes(stats.get("physicalInputDataSize", "0B")),
            error_code=error_code,
            error_message=error_message,
        )
