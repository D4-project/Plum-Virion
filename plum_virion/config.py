"""Local-only configuration; never accept credentials as MCP arguments."""

from dataclasses import dataclass, field
import ipaddress
import os
from pathlib import Path
from urllib.parse import urlsplit

import yaml


class ConfigError(ValueError):
    """Configuration error safe to display without configuration contents."""


@dataclass(frozen=True)
class Config:
    """The only upstream is the administrator-configured Plum controller."""

    hostname: str
    username: str = field(repr=False)
    password: str = field(repr=False)


def load_config(path):
    """Load a small private YAML mapping and fail closed before connecting."""
    try:
        with Path(path).open("rb") as stream:
            if os.name == "posix" and os.fstat(stream.fileno()).st_mode & 0o077:
                raise ConfigError("config.yaml must be private: chmod 600 config.yaml")
            raw = stream.read(16385)
    except OSError as error:
        raise ConfigError(
            "Cannot read config.yaml; provide --config with its absolute path"
        ) from error
    if len(raw) > 16384:
        raise ConfigError("Configuration exceeds 16 KiB")
    try:
        data = yaml.safe_load(raw)
    except (yaml.YAMLError, UnicodeError) as error:
        raise ConfigError("Invalid YAML configuration") from error
    if not isinstance(data, dict) or set(data) != {"hostname", "username", "password"}:
        raise ConfigError("Expected exactly hostname, username and password")
    if any(not isinstance(value, str) or not value.strip() for value in data.values()):
        raise ConfigError(
            "hostname, username and password must be nonempty quoted strings"
        )
    base = data["hostname"].rstrip("/")
    try:
        parsed = urlsplit(base)
        invalid_parts = (
            parsed.scheme not in {"http", "https"},
            not parsed.hostname,
            parsed.username is not None,
            parsed.password is not None,
            bool(parsed.query),
            bool(parsed.fragment),
            any(c.isspace() for c in base),
            "\\" in base,
            parsed.port == 0,
        )
        if any(invalid_parts):
            raise ValueError("invalid base URL")
        if parsed.scheme == "http":
            loopback = parsed.hostname.lower() == "localhost"
            if not loopback:
                loopback = ipaddress.ip_address(parsed.hostname).is_loopback
            if not loopback:
                raise ValueError("nonlocal HTTP")
    except ValueError as error:
        raise ConfigError(
            "hostname must be an HTTPS base URL without credentials/query; HTTP is loopback-only"
        ) from error
    return Config(base, data["username"], data["password"])
