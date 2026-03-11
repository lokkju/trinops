import pytest
from unittest.mock import MagicMock, patch

from trinops.auth import build_auth, resolve_password
from trinops.config import ConnectionProfile


def test_build_auth_none():
    profile = ConnectionProfile(server="localhost:8080", auth="none", user="dev")
    auth = build_auth(profile)
    assert auth is None


def test_build_auth_basic():
    profile = ConnectionProfile(
        server="localhost:8080", auth="basic", user="loki", password="secret"
    )
    auth = build_auth(profile)
    from trino.auth import BasicAuthentication
    assert isinstance(auth, BasicAuthentication)


def test_build_auth_jwt():
    profile = ConnectionProfile(
        server="localhost:8080", auth="jwt", jwt_token="eyJhbGciOi..."
    )
    auth = build_auth(profile)
    from trino.auth import JWTAuthentication
    assert isinstance(auth, JWTAuthentication)


def test_build_auth_unknown_raises():
    profile = ConnectionProfile(server="localhost:8080", auth="magic")
    with pytest.raises(ValueError, match="Unknown auth method"):
        build_auth(profile)


def test_resolve_password_direct():
    profile = ConnectionProfile(password="direct_secret")
    assert resolve_password(profile) == "direct_secret"


def test_resolve_password_cmd():
    profile = ConnectionProfile(password_cmd="echo hunter2")
    pw = resolve_password(profile)
    assert pw == "hunter2"


def test_resolve_password_none():
    profile = ConnectionProfile()
    assert resolve_password(profile) is None
