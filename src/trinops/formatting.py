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


def format_compact_number(n: int) -> str:
    """Format large numbers compactly: 1.2B, 34.1M, 5.6K, or raw int if < 1000."""
    if n < 1_000:
        return str(n)
    if n < 1_000_000:
        return f"{n / 1_000:.1f}K"
    if n < 1_000_000_000:
        return f"{n / 1_000_000:.1f}M"
    return f"{n / 1_000_000_000:.1f}B"


def format_compact_uptime(millis: int) -> str:
    """Format milliseconds as compact uptime: 3d2h, 5h12m, 5m12s, 45s."""
    total_seconds = millis // 1000
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if days > 0:
        return f"{days}d{hours}h"
    if hours > 0:
        return f"{hours}h{minutes}m"
    if minutes > 0:
        return f"{minutes}m{seconds}s"
    return f"{seconds}s"
