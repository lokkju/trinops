"""Tests for SchemaFetcher (mocked DB-API)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from trinops.config import ConnectionProfile


def _mock_cursor(rows):
    """Create a mock cursor that returns rows on fetchall()."""
    cursor = MagicMock()
    cursor.fetchall.return_value = rows
    cursor.description = [(f"col{i}",) for i in range(10)]
    return cursor


def test_fetcher_single_catalog():
    from trinops.schema.fetcher import SchemaFetcher

    profile = ConnectionProfile(
        server="localhost:8080", scheme="http", auth="none", user="dev", catalog="tpch"
    )
    fetcher = SchemaFetcher(profile)

    schemata_rows = [("sf1",), ("sf10",)]
    tables_rows = [
        ("sf1", "lineitem", "TABLE"),
        ("sf1", "nation", "TABLE"),
        ("sf10", "lineitem", "TABLE"),
    ]
    columns_rows = [
        ("sf1", "lineitem", "orderkey", "INTEGER", "YES"),
        ("sf1", "lineitem", "quantity", "DOUBLE", "YES"),
        ("sf1", "nation", "nationkey", "INTEGER", "YES"),
        ("sf10", "lineitem", "orderkey", "INTEGER", "YES"),
    ]

    mock_conn = MagicMock()
    cursors = [
        _mock_cursor(schemata_rows),
        _mock_cursor(tables_rows),
        _mock_cursor(columns_rows),
    ]
    cursor_idx = [0]

    def next_cursor():
        c = cursors[cursor_idx[0]]
        cursor_idx[0] += 1
        return c

    mock_conn.cursor.side_effect = next_cursor

    with patch("trinops.schema.fetcher.trino_connect", return_value=mock_conn):
        result = fetcher.fetch_catalog("tpch")

    assert result["catalog"] == "tpch"
    assert result["profile"] == "default"
    assert "fetched_at" in result
    assert "sf1" in result["schemas"]
    assert "lineitem" in result["schemas"]["sf1"]["tables"]
    cols = result["schemas"]["sf1"]["tables"]["lineitem"]["columns"]
    assert len(cols) == 2
    assert cols[0]["name"] == "orderkey"


def test_fetcher_discover_catalogs():
    from trinops.schema.fetcher import SchemaFetcher

    profile = ConnectionProfile(
        server="localhost:8080", scheme="http", auth="none", user="dev"
    )
    fetcher = SchemaFetcher(profile)

    mock_conn = MagicMock()
    cursor = _mock_cursor([("tpch",), ("hive",), ("system",)])
    mock_conn.cursor.return_value = cursor

    with patch("trinops.schema.fetcher.trino_connect", return_value=mock_conn):
        catalogs = fetcher.discover_catalogs()

    assert catalogs == ["tpch", "hive", "system"]


def test_fetcher_per_catalog_error_handling():
    from trinops.schema.fetcher import SchemaFetcher

    profile = ConnectionProfile(
        server="localhost:8080", scheme="http", auth="none", user="dev"
    )
    fetcher = SchemaFetcher(profile)

    mock_conn = MagicMock()
    mock_conn.cursor.side_effect = Exception("permission denied")

    with patch("trinops.schema.fetcher.trino_connect", return_value=mock_conn):
        with pytest.raises(Exception, match="permission denied"):
            fetcher.fetch_catalog("restricted")
