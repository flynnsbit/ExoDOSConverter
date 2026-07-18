"""Paths and environment for mister-pack."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict


def converter_root() -> Path:
    return Path(__file__).resolve().parent.parent


def user_config_path() -> Path:
    return Path.home() / ".config" / "mister-pack" / "config.toml"


def _load_user_config() -> Dict[str, Any]:
    """Optional ~/.config/mister-pack/config.toml (no extra deps if tomllib)."""
    path = user_config_path()
    if not path.is_file():
        return {}
    try:
        import tomllib  # py3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore
        except ImportError:
            return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def env_path(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _cfg_str(key: str, default: str = "") -> str:
    cfg = _load_user_config()
    val = cfg.get(key)
    if val is None and "paths" in cfg and isinstance(cfg["paths"], dict):
        val = cfg["paths"].get(key)
    if val is None:
        return default
    return str(val).strip()


def default_collection() -> str:
    return env_path(
        "EXODOS_COLLECTION",
        env_path("EDC_COLLECTION", _cfg_str("collection", "")),
    )


def default_output() -> str:
    return env_path(
        "MISTER_PACK_OUT",
        env_path(
            "EDC_OUT",
            _cfg_str("output", str(converter_root() / "out" / "mister-packs")),
        ),
    )


def default_dosassets() -> str:
    candidates = [
        env_path("DOSFORGE_DOSASSETS_DIR"),
        env_path("MISTER_DOSASSETS"),
        _cfg_str("dosassets"),
        os.path.expanduser("~/Projects/dosforge/dosassets"),
        str(converter_root().parent / "dosforge" / "dosassets"),
    ]
    for c in candidates:
        if c and Path(c).is_dir():
            return c
    return next((c for c in candidates if c), "")


def expand_path(value: str) -> str:
    if not value:
        return ""
    # ${ENV} or $ENV
    if value.startswith("${") and value.endswith("}"):
        return env_path(value[2:-1])
    if value.startswith("$") and "/" not in value[1:] and "\\" not in value[1:]:
        return env_path(value[1:])
    return os.path.abspath(os.path.expanduser(os.path.expandvars(value)))
