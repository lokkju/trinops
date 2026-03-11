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


def test_auth_status_no_config():
    result = runner.invoke(app, ["auth", "status", "--config-path", "/tmp/nonexistent.toml"])
    assert result.exit_code == 0
