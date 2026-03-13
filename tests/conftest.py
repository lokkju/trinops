"""Shared fixtures for trinops tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import vcr

CASSETTES_DIR = Path(__file__).parent / "cassettes"


def _discover_versions() -> list[str]:
    """Find all trino-{version} cassette directories."""
    if not CASSETTES_DIR.exists():
        return []
    versions = []
    for d in sorted(CASSETTES_DIR.iterdir()):
        if d.is_dir() and d.name.startswith("trino-"):
            version = d.name.removeprefix("trino-")
            cassette = d / "responses.yaml"
            if cassette.exists():
                versions.append(version)
    return versions


_VERSIONS = _discover_versions()


@pytest.fixture(params=_VERSIONS if _VERSIONS else [pytest.param("none", marks=pytest.mark.skip("no cassettes recorded"))],
                ids=[f"trino-{v}" for v in _VERSIONS] if _VERSIONS else ["no-cassettes"])
def trino_version(request):
    """Parameterized fixture yielding (version_str, use_cassette, metadata).

    Usage in tests:
        def test_something(trino_version):
            version, use_cassette, metadata = trino_version
            with use_cassette():
                backend = HttpQueryBackend(profile)
                ...

    metadata keys: detail_query_id, kill_query_id
    """
    version = request.param
    version_dir = CASSETTES_DIR / f"trino-{version}"
    cassette_path = str(version_dir / "responses.yaml")

    metadata_path = version_dir / "metadata.json"
    metadata = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}

    my_vcr = vcr.VCR(
        record_mode="none",
        match_on=["method", "host", "port", "path"],
        decode_compressed_response=True,
    )

    def use_cassette():
        return my_vcr.use_cassette(cassette_path)

    return version, use_cassette, metadata
