"""Tables tab for query detail pane."""
from __future__ import annotations

from textual.widgets import Static


class TablesTab(Static):
    """Displays accessed tables and their columns from the query's inputs."""

    DEFAULT_CSS = """
    TablesTab {
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
        inputs = self._data.get("inputs", [])
        if not inputs:
            return "No table information available."

        lines: list[str] = []
        for inp in inputs:
            fqn = f"{inp.get('catalogName', '')}.{inp.get('schema', '')}.{inp.get('table', '')}"
            lines.append(fqn)
            for col in inp.get("columns", []):
                lines.append(f"  {col['name']:<30s} {col.get('type', '')}")
            lines.append("")

        return "\n".join(lines).rstrip()
