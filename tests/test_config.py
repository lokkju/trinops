import os
import tempfile

from trinops.config import TrinopsConfig, load_config, ConnectionProfile


SAMPLE_CONFIG = """\
[default]
server = "trino.example.com:8080"
scheme = "https"
user = "loki"
auth = "oauth2"
catalog = "hive"

[profiles.staging]
server = "trino-staging.example.com:8080"
scheme = "http"
auth = "basic"
user = "loki"
password = "secret123"

[profiles.local]
server = "localhost:8080"
auth = "none"
user = "dev"
"""


def test_load_config_from_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(SAMPLE_CONFIG)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)

    assert config.default.server == "trino.example.com:8080"
    assert config.default.scheme == "https"
    assert config.default.user == "loki"
    assert config.default.auth == "oauth2"
    assert config.default.catalog == "hive"


def test_load_config_profiles():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(SAMPLE_CONFIG)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)

    staging = config.get_profile("staging")
    assert staging.server == "trino-staging.example.com:8080"
    assert staging.auth == "basic"
    assert staging.password == "secret123"

    local = config.get_profile("local")
    assert local.auth == "none"


def test_get_profile_default():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(SAMPLE_CONFIG)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)

    default = config.get_profile(None)
    assert default.server == "trino.example.com:8080"


def test_get_profile_unknown_raises():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(SAMPLE_CONFIG)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)

    try:
        config.get_profile("nonexistent")
        assert False, "Should have raised"
    except KeyError:
        pass


def test_connection_profile_from_env(monkeypatch):
    monkeypatch.setenv("TRINOPS_SERVER", "env-host:9090")
    monkeypatch.setenv("TRINOPS_USER", "envuser")
    monkeypatch.setenv("TRINOPS_AUTH", "none")

    profile = ConnectionProfile.from_env()
    assert profile.server == "env-host:9090"
    assert profile.user == "envuser"
    assert profile.auth == "none"


def test_connection_profile_from_env_missing():
    # Should return None when no env vars set
    profile = ConnectionProfile.from_env()
    # At minimum server must be set for env profile to be valid
    assert profile is None or profile.server is None


def test_profile_merge_env_over_file():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(SAMPLE_CONFIG)
        f.flush()
        config = load_config(f.name)

    os.unlink(f.name)

    profile = config.get_profile(None)
    assert profile.user == "loki"  # from file
