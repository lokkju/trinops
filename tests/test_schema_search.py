"""Tests for SchemaSearch."""
from __future__ import annotations

import pytest

from tests.test_schema_cache import SAMPLE_CACHE


MULTI_CATALOG_CACHE = {
    "catalog": "hive",
    "profile": "default",
    "fetched_at": "2026-03-14T12:00:00+00:00",
    "schemas": {
        "analytics": {
            "tables": {
                "orders": {
                    "type": "TABLE",
                    "columns": [
                        {"name": "order_id", "type": "INTEGER", "nullable": True},
                        {"name": "customer_id", "type": "INTEGER", "nullable": True},
                        {"name": "total", "type": "DOUBLE", "nullable": True},
                    ],
                },
                "customers": {
                    "type": "TABLE",
                    "columns": [
                        {"name": "customer_id", "type": "INTEGER", "nullable": True},
                        {"name": "name", "type": "VARCHAR", "nullable": True},
                    ],
                },
            },
        },
    },
}


def test_search_table_glob(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    search = SchemaSearch(cache, profile="default")
    results = search.search_tables("*line*")
    assert len(results) == 1
    assert results[0]["table"] == "lineitem"
    assert results[0]["catalog"] == "tpch"
    assert results[0]["schema"] == "sf1"


def test_search_table_substring(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    search = SchemaSearch(cache, profile="default")
    results = search.search_tables("nation")
    assert len(results) == 1
    assert results[0]["table"] == "nation"


def test_search_columns(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "hive", MULTI_CATALOG_CACHE)
    search = SchemaSearch(cache, profile="default")
    results = search.search_columns("customer_id")
    assert len(results) == 2
    tables = {r["table"] for r in results}
    assert tables == {"orders", "customers"}
    assert all(r["column"] == "customer_id" for r in results)


def test_search_across_catalogs(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    cache.write("default", "hive", MULTI_CATALOG_CACHE)
    search = SchemaSearch(cache, profile="default")
    results = search.search_tables("*")
    catalogs = {r["catalog"] for r in results}
    assert catalogs == {"tpch", "hive"}


def test_search_scoped_to_catalog(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    cache.write("default", "hive", MULTI_CATALOG_CACHE)
    search = SchemaSearch(cache, profile="default", catalog="tpch")
    results = search.search_tables("*")
    assert all(r["catalog"] == "tpch" for r in results)


def test_search_no_results(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    search = SchemaSearch(cache, profile="default")
    results = search.search_tables("nonexistent")
    assert results == []


def test_search_fully_qualified(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    search = SchemaSearch(cache, profile="default")
    results = search.lookup_table("tpch.sf1.lineitem")
    assert results is not None
    assert results["table"] == "lineitem"
    assert len(results["columns"]) == 2


def test_search_unqualified_show(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    search = SchemaSearch(cache, profile="default")
    results = search.lookup_tables("lineitem")
    assert len(results) == 1
    assert results[0]["catalog"] == "tpch"
    assert results[0]["schema"] == "sf1"
    assert len(results[0]["columns"]) == 2


def test_list_catalogs(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    cache.write("default", "hive", MULTI_CATALOG_CACHE)
    search = SchemaSearch(cache, profile="default")
    catalogs = search.list_catalogs()
    assert catalogs == ["hive", "tpch"]


def test_list_schemas(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    search = SchemaSearch(cache, profile="default")
    schemas = search.list_schemas("tpch")
    assert schemas == ["sf1"]


def test_list_schemas_unknown_catalog(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    search = SchemaSearch(cache, profile="default")
    assert search.list_schemas("nonexistent") == []


def test_list_tables_in_schema(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    search = SchemaSearch(cache, profile="default")
    tables = search.list_tables_in_schema("tpch", "sf1")
    assert len(tables) == 2
    names = {t["table"] for t in tables}
    assert names == {"lineitem", "nation"}
    assert all("columns" not in t for t in tables)


def test_dump_all(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    cache.write("default", "hive", MULTI_CATALOG_CACHE)
    search = SchemaSearch(cache, profile="default")
    dump = search.dump_all()
    assert len(dump) == 4  # 2 tpch + 2 hive
    assert all("columns" in d for d in dump)


def test_dump_all_with_catalog_filter(tmp_path):
    from trinops.schema.cache import SchemaCache
    from trinops.schema.search import SchemaSearch
    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)
    cache.write("default", "hive", MULTI_CATALOG_CACHE)
    search = SchemaSearch(cache, profile="default", catalog="tpch")
    dump = search.dump_all()
    assert len(dump) == 2
    assert all(d["catalog"] == "tpch" for d in dump)
