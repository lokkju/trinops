"""Tests for CLI schema commands."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from trinops.cli.commands import app


runner = CliRunner()


def test_schema_list_no_cache(tmp_path):
    with patch("trinops.schema.cache.DEFAULT_CACHE_DIR", tmp_path):
        result = runner.invoke(app, ["schema", "list"])
    assert result.exit_code == 0
    assert "No cached catalogs" in result.output


def test_schema_list_with_cache(tmp_path):
    from trinops.schema.cache import SchemaCache
    from tests.test_schema_cache import SAMPLE_CACHE

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    with patch("trinops.schema.cache.DEFAULT_CACHE_DIR", tmp_path):
        result = runner.invoke(app, ["schema", "list"])
    assert result.exit_code == 0
    assert "tpch" in result.output


def test_schema_search_tables(tmp_path):
    from trinops.schema.cache import SchemaCache
    from tests.test_schema_cache import SAMPLE_CACHE

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    with patch("trinops.schema.cache.DEFAULT_CACHE_DIR", tmp_path):
        result = runner.invoke(app, ["schema", "search", "*line*"])
    assert result.exit_code == 0
    assert "lineitem" in result.output


def test_schema_search_json(tmp_path):
    from trinops.schema.cache import SchemaCache
    from tests.test_schema_cache import SAMPLE_CACHE

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    with patch("trinops.schema.cache.DEFAULT_CACHE_DIR", tmp_path):
        result = runner.invoke(app, ["schema", "search", "*line*", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert len(data) == 1
    assert data[0]["table"] == "lineitem"


def test_schema_show_table(tmp_path):
    from trinops.schema.cache import SchemaCache
    from tests.test_schema_cache import SAMPLE_CACHE

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    with patch("trinops.schema.cache.DEFAULT_CACHE_DIR", tmp_path):
        result = runner.invoke(app, ["schema", "show", "lineitem"])
    assert result.exit_code == 0
    assert "orderkey" in result.output
    assert "INTEGER" in result.output


def test_schema_show_not_found(tmp_path):
    from trinops.schema.cache import SchemaCache
    from tests.test_schema_cache import SAMPLE_CACHE

    cache = SchemaCache(base_dir=tmp_path)
    cache.write("default", "tpch", SAMPLE_CACHE)

    with patch("trinops.schema.cache.DEFAULT_CACHE_DIR", tmp_path):
        result = runner.invoke(app, ["schema", "show", "nonexistent"])
    assert result.exit_code == 1
