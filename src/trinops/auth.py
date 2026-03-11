"""Authentication module for trinops."""

from __future__ import annotations

import shlex
import subprocess
from typing import Optional

from trinops.config import ConnectionProfile


def resolve_password(profile: ConnectionProfile) -> Optional[str]:
    if profile.password is not None:
        return profile.password
    if profile.password_cmd is not None:
        result = subprocess.run(
            shlex.split(profile.password_cmd),
            capture_output=True,
            text=True,
            timeout=10,
        )
        result.check_returncode()
        return result.stdout.strip()
    return None


def build_auth(profile: ConnectionProfile):
    method = profile.auth

    if method == "none":
        return None

    if method == "basic":
        from trino.auth import BasicAuthentication
        password = resolve_password(profile)
        if password is None:
            raise ValueError("basic auth requires password or password_cmd")
        return BasicAuthentication(profile.user, password)

    if method == "jwt":
        from trino.auth import JWTAuthentication
        token = profile.jwt_token
        if token is None:
            raise ValueError("jwt auth requires jwt_token")
        return JWTAuthentication(token)

    if method == "oauth2":
        from trino.auth import OAuth2Authentication
        return OAuth2Authentication()

    if method == "kerberos":
        from trino.auth import KerberosAuthentication
        return KerberosAuthentication()

    raise ValueError(f"Unknown auth method: {method!r}")
