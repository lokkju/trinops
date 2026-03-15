"""Stats tab for query detail pane."""
from __future__ import annotations

from textual.widgets import Static

from trinops.formatting import format_bytes, format_time_millis, parse_duration_millis, parse_data_size_bytes


def _duration(s: str | None) -> str:
    if not s:
        return "—"
    try:
        return format_time_millis(parse_duration_millis(s))
    except ValueError:
        return s


def _data_size(s: str | None) -> str:
    if not s:
        return "—"
    try:
        return format_bytes(parse_data_size_bytes(s))
    except ValueError:
        return s


class StatsTab(Static):
    """Displays detailed timing, data volumes, memory, and task counts."""

    DEFAULT_CSS = """
    StatsTab {
        height: auto;
        padding: 0 1;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._data: dict = {}

    def update_data(self, data: dict) -> None:
        self._data = data
        self.update(self.render_text())

    def render_text(self) -> str:
        qs = self._data.get("queryStats", {})
        if not qs:
            return "No stats available"

        lines: list[str] = []

        # Timing
        lines.append("Timing")
        lines.append(f"  Queued:      {_duration(qs.get('queuedTime'))}")
        lines.append(f"  Planning:    {_duration(qs.get('planningTime'))}")
        lines.append(f"  Execution:   {_duration(qs.get('executionTime'))}")
        lines.append(f"  Elapsed:     {_duration(qs.get('elapsedTime'))}")
        lines.append(f"  CPU:         {_duration(qs.get('totalCpuTime'))}")

        # Data
        lines.append("")
        lines.append("Data")
        phys_in = _data_size(qs.get("physicalInputDataSize"))
        phys_rows = qs.get("physicalInputPositions", 0)
        lines.append(f"  Input:       {phys_in}  ({phys_rows:,} rows)")
        proc_in = _data_size(qs.get("processedInputDataSize"))
        proc_rows = qs.get("processedInputPositions", 0)
        lines.append(f"  Processed:   {proc_in}  ({proc_rows:,} rows)")
        out = _data_size(qs.get("outputDataSize"))
        out_rows = qs.get("outputPositions", 0)
        lines.append(f"  Output:      {out}  ({out_rows:,} rows)")
        spilled = qs.get("spilledDataSize")
        if spilled and spilled != "0B":
            lines.append(f"  Spilled:     {_data_size(spilled)}")

        # Memory
        lines.append("")
        lines.append("Memory")
        lines.append(f"  Peak user:   {_data_size(qs.get('peakUserMemoryReservation'))}")
        lines.append(f"  Peak total:  {_data_size(qs.get('peakTotalMemoryReservation'))}")
        cum = qs.get("cumulativeUserMemory", 0)
        if cum:
            lines.append(f"  Cumulative:  {format_bytes(int(cum))}")

        # Tasks
        lines.append("")
        lines.append("Tasks")
        ct = qs.get("completedTasks", 0)
        tt = qs.get("totalTasks", 0)
        lines.append(f"  Tasks:       {ct}/{tt}")
        cd = qs.get("completedDrivers", 0)
        td = qs.get("totalDrivers", 0)
        lines.append(f"  Drivers:     {cd}/{td}")

        return "\n".join(lines)
