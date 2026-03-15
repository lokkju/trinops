"""Fetch schema metadata from Trino via DB-API."""
from __future__ import annotations

from datetime import datetime, timezone

from trino.dbapi import connect as trino_connect

from trinops.auth import build_auth
from trinops.config import ConnectionProfile


class SchemaFetcher:
    """Connects to Trino and fetches information_schema metadata."""

    def __init__(self, profile: ConnectionProfile, profile_name: str = "default") -> None:
        self._profile = profile
        self._profile_name = profile_name

    def _connect(self):
        p = self._profile
        host, _, port_str = p.server.partition(":")
        port = int(port_str) if port_str else (443 if p.scheme == "https" else 8080)

        kwargs = {
            "host": host,
            "port": port,
            "user": p.user or "trinops",
            "http_scheme": p.scheme,
        }

        if p.auth and p.auth != "none":
            auth = build_auth(p)
            if auth is not None:
                kwargs["auth"] = auth

        return trino_connect(**kwargs)

    def discover_catalogs(self) -> list[str]:
        """Return a list of catalog names available on the cluster."""
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute("SHOW CATALOGS")
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def fetch_catalog(self, catalog: str) -> dict:
        """Fetch all schemas, tables, and columns for a single catalog.

        Returns a dict with catalog name, profile, timestamp, and nested
        schema/table/column structure suitable for caching.
        """
        conn = self._connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT schema_name FROM {catalog}.information_schema.schemata"
            )
            schema_names = [row[0] for row in cursor.fetchall()]

            cursor = conn.cursor()
            cursor.execute(
                f"SELECT table_schema, table_name, table_type "
                f"FROM {catalog}.information_schema.tables"
            )
            tables_by_schema: dict[str, dict[str, dict]] = {}
            for schema, table, table_type in cursor.fetchall():
                tables_by_schema.setdefault(schema, {})[table] = {
                    "type": table_type,
                    "columns": [],
                }

            cursor = conn.cursor()
            cursor.execute(
                f"SELECT table_schema, table_name, column_name, data_type, is_nullable "
                f"FROM {catalog}.information_schema.columns"
            )
            for schema, table, col_name, data_type, nullable in cursor.fetchall():
                tbl = tables_by_schema.get(schema, {}).get(table)
                if tbl is not None:
                    tbl["columns"].append({
                        "name": col_name,
                        "type": data_type,
                        "nullable": nullable == "YES",
                    })

            schemas = {}
            for schema_name in schema_names:
                if schema_name in tables_by_schema:
                    schemas[schema_name] = {"tables": tables_by_schema[schema_name]}

            return {
                "catalog": catalog,
                "profile": self._profile_name,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
                "schemas": schemas,
            }
        finally:
            conn.close()
