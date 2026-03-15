"""Errors tab for query detail pane."""
from __future__ import annotations

from textual.widgets import Static


class ErrorsTab(Static):
    """Displays error details and warnings for a query."""

    DEFAULT_CSS = """
    ErrorsTab {
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
        error_code = self._data.get("errorCode")
        failure_info = self._data.get("failureInfo")
        warnings = self._data.get("warnings", [])

        if not error_code and not failure_info and not warnings:
            return "No errors or warnings."

        lines: list[str] = []

        if error_code and isinstance(error_code, dict):
            lines.append(f"Error Code:  {error_code.get('name', '')} ({error_code.get('type', '')})")
            lines.append(f"Error ID:    {error_code.get('code', '')}")

        if failure_info and isinstance(failure_info, dict):
            msg = failure_info.get("message", "")
            if msg:
                lines.append("")
                lines.append("Message:")
                lines.append(f"  {msg}")

        if warnings:
            lines.append("")
            lines.append("Warnings:")
            for w in warnings:
                lines.append(f"  {w}")

        return "\n".join(lines)
