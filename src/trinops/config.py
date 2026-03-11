"""Configuration module for trinops."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib


DEFAULT_CONFIG_PATH = Path.home() / ".config" / "trinops" / "config.toml"


@dataclass
class ConnectionProfile:
    server: Optional[str] = None
    scheme: str = "https"
    user: Optional[str] = None
    auth: str = "none"
    catalog: Optional[str] = None
    schema: Optional[str] = None
    password: Optional[str] = None
    password_cmd: Optional[str] = None
    jwt_token: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> ConnectionProfile:
        known = {f.name for f in fields(cls)}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    @classmethod
    def from_env(cls) -> Optional[ConnectionProfile]:
        server = os.environ.get("TRINOPS_SERVER")
        if server is None:
            return None
        return cls(
            server=server,
            scheme=os.environ.get("TRINOPS_SCHEME", "https"),
            user=os.environ.get("TRINOPS_USER"),
            auth=os.environ.get("TRINOPS_AUTH", "none"),
            catalog=os.environ.get("TRINOPS_CATALOG"),
            schema=os.environ.get("TRINOPS_SCHEMA"),
        )


@dataclass
class TrinopsConfig:
    default: ConnectionProfile = field(default_factory=ConnectionProfile)
    profiles: dict[str, ConnectionProfile] = field(default_factory=dict)

    def get_profile(self, name: Optional[str]) -> ConnectionProfile:
        if name is None:
            return self.default
        if name not in self.profiles:
            raise KeyError(f"Unknown profile: {name!r}")
        return self.profiles[name]


def load_config(path: str | Path | None = None) -> TrinopsConfig:
    config_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not config_path.exists():
        return TrinopsConfig()

    with open(config_path, "rb") as f:
        data = tomllib.load(f)

    default = ConnectionProfile.from_dict(data.get("default", {}))
    profiles = {}
    for name, profile_data in data.get("profiles", {}).items():
        profiles[name] = ConnectionProfile.from_dict(profile_data)

    return TrinopsConfig(default=default, profiles=profiles)
