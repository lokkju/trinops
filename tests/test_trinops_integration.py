"""Verify all public imports work."""


def test_core_imports():
    from trinops import TrinoProgress, QueryStats, StageStats, QueryInfo, QueryState
    assert TrinoProgress is not None
    assert QueryStats is not None
    assert QueryState.RUNNING.value == "RUNNING"


def test_progress_imports():
    from trinops.progress import TrinoProgress, Display, StderrDisplay, WebDisplay
    assert TrinoProgress is not None
    assert Display is not None


def test_cli_importable():
    from trinops.cli import app
    assert app is not None


def test_version():
    import trinops
    assert trinops.__version__ != "0.0.0"
    assert isinstance(trinops.__version__, str)
