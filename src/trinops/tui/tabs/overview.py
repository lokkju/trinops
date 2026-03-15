"""Overview tab for query detail pane."""
from __future__ import annotations

from textual.widgets import Static

from trinops.formatting import format_bytes, format_time_millis, parse_data_size_bytes, parse_duration_millis


class OverviewTab(Static):
    """Displays query identity, session info, timing summary, and SQL.

    SQL is rendered with Rich Syntax highlighting when displayed via update_data().
    For render_text() (used in tests), SQL is included as plain text.
    """

    DEFAULT_CSS = """
    OverviewTab {
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
        d = self._data
        if not d:
            return "No data"
        session = d.get("session", {})
        qs = d.get("queryStats", {})

        lines: list[str] = []

        # Identity
        lines.append(f"Query ID:  {d.get('queryId', '')}")
        lines.append(f"State:     {d.get('state', '')}")
        if d.get("queryType"):
            lines.append(f"Type:      {d['queryType']}")
        lines.append(f"User:      {session.get('user', '')}")
        if session.get("source"):
            lines.append(f"Source:    {session['source']}")
        if session.get("catalog"):
            cat = session["catalog"]
            sch = session.get("schema", "")
            lines.append(f"Catalog:   {cat}.{sch}" if sch else f"Catalog:   {cat}")
        rg = d.get("resourceGroupId")
        if rg:
            lines.append(f"Resource:  {'.'.join(rg) if isinstance(rg, list) else rg}")

        # Timing summary
        lines.append("")
        if qs.get("createTime"):
            lines.append(f"Created:   {qs['createTime']}")
        if qs.get("elapsedTime"):
            lines.append(f"Elapsed:   {qs['elapsedTime']}")
        if qs.get("totalCpuTime"):
            lines.append(f"CPU:       {qs['totalCpuTime']}")
        if qs.get("peakUserMemoryReservation"):
            try:
                mem = parse_data_size_bytes(qs["peakUserMemoryReservation"])
                lines.append(f"Memory:    {format_bytes(mem)}")
            except ValueError:
                lines.append(f"Memory:    {qs['peakUserMemoryReservation']}")

        # SQL
        query = d.get("query", "")
        if query:
            lines.append("")
            lines.append("--- SQL " + "-" * 40)
            lines.append(query)

        return "\n".join(lines)
