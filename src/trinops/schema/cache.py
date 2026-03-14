"""JSON file cache for Trino schema metadata."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


DEFAULT_CACHE_DIR = Path.home() / ".cache" / "trinops" / "schemas"


class SchemaCache:
    """Manages JSON cache files at <base_dir>/<profile>/<catalog>.json."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or DEFAULT_CACHE_DIR

    def _catalog_path(self, profile: str, catalog: str) -> Path:
        return self._base_dir / profile / f"{catalog}.json"

    def write(self, profile: str, catalog: str, data: dict) -> None:
        path = self._catalog_path(profile, catalog)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def read(self, profile: str, catalog: str) -> Optional[dict]:
        path = self._catalog_path(profile, catalog)
        if not path.exists():
            return None
        with open(path) as f:
            return json.load(f)

    def list_catalogs(self, profile: str) -> list[str]:
        profile_dir = self._base_dir / profile
        if not profile_dir.exists():
            return []
        return sorted(p.stem for p in profile_dir.glob("*.json"))

    def list_profiles(self) -> list[str]:
        if not self._base_dir.exists():
            return []
        return sorted(p.name for p in self._base_dir.iterdir() if p.is_dir())

    def get_stats(self, profile: str, catalog: str) -> Optional[dict]:
        data = self.read(profile, catalog)
        if data is None:
            return None
        table_count = 0
        column_count = 0
        for schema_data in data.get("schemas", {}).values():
            for table_data in schema_data.get("tables", {}).values():
                table_count += 1
                column_count += len(table_data.get("columns", []))
        return {
            "catalog": catalog,
            "profile": profile,
            "fetched_at": data.get("fetched_at", ""),
            "table_count": table_count,
            "column_count": column_count,
        }
