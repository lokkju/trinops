"""Tests for SchemaCache."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


SAMPLE_CACHE = {
    "catalog": "tpch",
    "profile": "default",
    "fetched_at": "2026-03-14T12:00:00+00:00",
    "schemas": {
        "sf1": {
            "tables": {
                "lineitem": {
                    "type": "TABLE",
                    "columns": [
                        {"name": "orderkey", "type": "INTEGER", "nullable": True},
                        {"name": "quantity", "type": "DOUBLE", "nullable": True},
                    ],
                },
                "nation": {
                    "type": "TABLE",
                    "columns": [
                        {"name": "nationkey", "type": "INTEGER", "nullable": True},
                        {"name": "name", "type": "VARCHAR", "nullable": True},
                    ],
                },
            },
        },
    },
}


def test_cache_write_and_read(tmp_path):
    from trinops.schema.cache import SchemaCache
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    data = cache.read("default", "tpch")
    assert data is not None
    assert data["catalog"] == "tpch"
    assert "sf1" in data["schemas"]
    assert "lineitem" in data["schemas"]["sf1"]["tables"]


def test_cache_read_missing(tmp_path):
    from trinops.schema.cache import SchemaCache
    cache = SchemaCache(base_dir=tmp_path)
    assert cache.read("default", "nonexistent") is None


def test_cache_list_catalogs(tmp_path):
    from trinops.schema.cache import SchemaCache
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    cache.write("default", "hive", {**SAMPLE_CACHE, "catalog": "hive"})
    catalogs = cache.list_catalogs("default")
    assert set(catalogs) == {"tpch", "hive"}


def test_cache_list_catalogs_empty(tmp_path):
    from trinops.schema.cache import SchemaCache
    cache = SchemaCache(base_dir=tmp_path)
    assert cache.list_catalogs("default") == []


def test_cache_profile_isolation(tmp_path):
    from trinops.schema.cache import SchemaCache
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    cache.write("prod", "tpch", {**SAMPLE_CACHE, "profile": "prod"})
    default_data = cache.read("default", "tpch")
    prod_data = cache.read("prod", "tpch")
    assert default_data["profile"] == "default"
    assert prod_data["profile"] == "prod"
    assert cache.list_catalogs("staging") == []


def test_cache_file_structure(tmp_path):
    from trinops.schema.cache import SchemaCache
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    expected_path = tmp_path / "default" / "tpch.json"
    assert expected_path.exists()
    with open(expected_path) as f:
        data = json.load(f)
    assert data["catalog"] == "tpch"


def test_cache_stats(tmp_path):
    from trinops.schema.cache import SchemaCache
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    stats = cache.get_stats("default", "tpch")
    assert stats is not None
    assert stats["catalog"] == "tpch"
    assert stats["table_count"] == 2
    assert stats["column_count"] == 4
    assert "fetched_at" in stats
