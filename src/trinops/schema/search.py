"""In-memory search over cached schema metadata."""
from __future__ import annotations

import fnmatch
from typing import Optional

from trinops.schema.cache import SchemaCache


def _has_glob_chars(pattern: str) -> bool:
    return any(c in pattern for c in ("*", "?", "["))


def _normalize_pattern(pattern: str) -> str:
    if _has_glob_chars(pattern):
        return pattern
    return f"*{pattern}*"


class SchemaSearch:
    def __init__(
        self,
        cache: SchemaCache,
        profile: str = "default",
        catalog: Optional[str] = None,
    ) -> None:
        self._cache = cache
        self._profile = profile
        self._catalog_filter = catalog
        self._entries: list[dict] = []
        self._load()

    def _load(self) -> None:
        catalogs = self._cache.list_catalogs(self._profile)
        if self._catalog_filter:
            catalogs = [c for c in catalogs if c == self._catalog_filter]
        self._entries = []
        for cat_name in catalogs:
            data = self._cache.read(self._profile, cat_name)
            if data is None:
                continue
            for schema_name, schema_data in data.get("schemas", {}).items():
                for table_name, table_data in schema_data.get("tables", {}).items():
                    self._entries.append(
                        {
                            "catalog": cat_name,
                            "schema": schema_name,
                            "table": table_name,
                            "type": table_data.get("type", "TABLE"),
                            "columns": table_data.get("columns", []),
                        }
                    )

    def search_tables(self, pattern: str) -> list[dict]:
        pat = _normalize_pattern(pattern)
        results = []
        for entry in self._entries:
            if fnmatch.fnmatch(entry["table"], pat):
                results.append(
                    {
                        "catalog": entry["catalog"],
                        "schema": entry["schema"],
                        "table": entry["table"],
                        "type": entry["type"],
                    }
                )
        return results

    def search_columns(self, pattern: str) -> list[dict]:
        pat = _normalize_pattern(pattern)
        results = []
        for entry in self._entries:
            for col in entry["columns"]:
                if fnmatch.fnmatch(col["name"], pat):
                    results.append(
                        {
                            "catalog": entry["catalog"],
                            "schema": entry["schema"],
                            "table": entry["table"],
                            "column": col["name"],
                            "column_type": col.get("type", ""),
                        }
                    )
        return results

    def lookup_table(self, fqn: str) -> Optional[dict]:
        parts = fqn.split(".")
        if len(parts) != 3:
            return None
        cat, sch, tbl = parts
        for entry in self._entries:
            if (
                entry["catalog"] == cat
                and entry["schema"] == sch
                and entry["table"] == tbl
            ):
                return {
                    "catalog": entry["catalog"],
                    "schema": entry["schema"],
                    "table": entry["table"],
                    "type": entry["type"],
                    "columns": entry["columns"],
                }
        return None

    def lookup_tables(self, name: str) -> list[dict]:
        parts = name.split(".")
        results = []
        for entry in self._entries:
            match = False
            if len(parts) == 1:
                match = entry["table"] == parts[0]
            elif len(parts) == 2:
                match = entry["schema"] == parts[0] and entry["table"] == parts[1]
            elif len(parts) == 3:
                match = (
                    entry["catalog"] == parts[0]
                    and entry["schema"] == parts[1]
                    and entry["table"] == parts[2]
                )
            if match:
                results.append(
                    {
                        "catalog": entry["catalog"],
                        "schema": entry["schema"],
                        "table": entry["table"],
                        "type": entry["type"],
                        "columns": entry["columns"],
                    }
                )
        return results

    def list_catalogs(self) -> list[str]:
        """Return sorted unique catalog names in the loaded entries."""
        return sorted({e["catalog"] for e in self._entries})

    def list_schemas(self, catalog: str) -> list[str]:
        """Return sorted unique schema names within a catalog."""
        return sorted({e["schema"] for e in self._entries if e["catalog"] == catalog})

    def list_tables_in_schema(self, catalog: str, schema: str) -> list[dict]:
        """Return tables within a specific catalog.schema."""
        return [
            {
                "catalog": e["catalog"],
                "schema": e["schema"],
                "table": e["table"],
                "type": e["type"],
            }
            for e in self._entries
            if e["catalog"] == catalog and e["schema"] == schema
        ]

    def dump_all(self) -> list[dict]:
        """Return all entries with full column data for JSON dump."""
        return [
            {
                "catalog": e["catalog"],
                "schema": e["schema"],
                "table": e["table"],
                "type": e["type"],
                "columns": e["columns"],
            }
            for e in self._entries
        ]
