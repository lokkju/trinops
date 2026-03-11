import tempfile
import os

from typer.testing import CliRunner
from trinops.cli import app

runner = CliRunner()


def test_config_show_no_config():
    result = runner.invoke(app, ["config", "show", "--config-path", "/tmp/nonexistent.toml"])
    assert result.exit_code == 0
    assert "no config" in result.output.lower() or "not found" in result.output.lower()


def test_config_show_with_config():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write('[default]\nserver = "localhost:8080"\nuser = "dev"\nauth = "none"\n')
        f.flush()
        result = runner.invoke(app, ["config", "show", "--config-path", f.name])

    os.unlink(f.name)
    assert result.exit_code == 0
    assert "localhost:8080" in result.output


def test_config_init_non_interactive(tmp_path):
    path = tmp_path / "config.toml"
    result = runner.invoke(app, [
        "config", "init", "--config-path", str(path),
        "--server", "trino.test:443", "--scheme", "https",
        "--user", "testuser", "--auth", "basic",
    ])
    assert result.exit_code == 0
    assert "Config written" in result.output
    # Verify it wrote correctly
    result2 = runner.invoke(app, ["config", "show", "--config-path", str(path)])
    assert "trino.test:443" in result2.output
    assert "testuser" in result2.output


def test_config_set_default(tmp_path):
    path = tmp_path / "config.toml"
    # Create initial config
    runner.invoke(app, [
        "config", "init", "--config-path", str(path),
        "--server", "trino:8080", "--user", "dev", "--auth", "none",
    ])
    # Update a value
    result = runner.invoke(app, ["config", "set", "user", "newuser", "--config-path", str(path)])
    assert result.exit_code == 0
    assert "Set default.user = newuser" in result.output
    # Verify
    result2 = runner.invoke(app, ["config", "show", "--config-path", str(path)])
    assert "newuser" in result2.output


def test_config_set_profile(tmp_path):
    path = tmp_path / "config.toml"
    runner.invoke(app, [
        "config", "init", "--config-path", str(path),
        "--server", "trino:8080", "--user", "dev", "--auth", "none",
    ])
    result = runner.invoke(app, [
        "config", "set", "server", "trino-prod:443",
        "--profile", "prod", "--config-path", str(path),
    ])
    assert result.exit_code == 0
    assert "profiles.prod" in result.output
    # Verify
    result2 = runner.invoke(app, ["config", "show", "--profile", "prod", "--config-path", str(path)])
    assert "trino-prod:443" in result2.output


def test_config_set_unknown_key(tmp_path):
    path = tmp_path / "config.toml"
    result = runner.invoke(app, ["config", "set", "bogus", "value", "--config-path", str(path)])
    assert result.exit_code == 1
    assert "Unknown config key" in result.output


def test_config_set_int_coercion(tmp_path):
    path = tmp_path / "config.toml"
    runner.invoke(app, [
        "config", "init", "--config-path", str(path),
        "--server", "trino:8080", "--user", "dev", "--auth", "none",
    ])
    result = runner.invoke(app, ["config", "set", "query_limit", "100", "--config-path", str(path)])
    assert result.exit_code == 0
    assert "100" in result.output


def test_auth_status_no_config():
    result = runner.invoke(app, ["auth", "status", "--config-path", "/tmp/nonexistent.toml"])
    assert result.exit_code == 0
