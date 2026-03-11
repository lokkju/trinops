"""Shared formatting utilities."""

from __future__ import annotations

import re

_DURATION_RE = re.compile(r"^([\d.]+)(ns|us|ms|s|m|h|d)$")

_DURATION_UNITS_TO_MS = {
    "ns": 1e-6,
    "us": 1e-3,
    "ms": 1.0,
    "s": 1000.0,
    "m": 60_000.0,
    "h": 3_600_000.0,
    "d": 86_400_000.0,
}


def parse_duration_millis(s: str) -> int:
    """Parse an Airlift Duration string (e.g. '5.23s') to milliseconds."""
    m = _DURATION_RE.match(s)
    if not m:
        raise ValueError(f"Invalid duration: {s!r}")
    value, unit = float(m.group(1)), m.group(2)
    return int(value * _DURATION_UNITS_TO_MS[unit])


def parse_data_size_bytes(s: str) -> int:
    """Parse an Airlift DataSize bytes string (e.g. '4194304B') to int bytes."""
    if not s.endswith("B"):
        raise ValueError(f"Invalid data size: {s!r}")
    return int(s[:-1])


def format_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}PB"


def format_time_millis(millis: int) -> str:
    seconds = millis / 1000
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = seconds / 60
    if minutes < 60:
        return f"{minutes:.1f}m"
    hours = minutes / 60
    return f"{hours:.1f}h"
