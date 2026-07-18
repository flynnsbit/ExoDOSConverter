"""Paths and environment for mister-pack."""

from __future__ import annotations

import os
from pathlib import Path


def converter_root() -> Path:
    return Path(__file__).resolve().parent.parent


def env_path(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def default_collection() -> str:
    return env_path(
        "EXODOS_COLLECTION",
        env_path("EDC_COLLECTION", ""),
    )


def default_output() -> str:
    return env_path(
        "MISTER_PACK_OUT",
        env_path("EDC_OUT", str(converter_root() / "out" / "mister-packs")),
    )


def default_dosassets() -> str:
    candidates = [
        env_path("DOSFORGE_DOSASSETS_DIR"),
        env_path("MISTER_DOSASSETS"),
        os.path.expanduser("~/Projects/dosforge/dosassets"),
        str(converter_root().parent / "dosforge" / "dosassets"),
    ]
    for c in candidates:
        if c and Path(c).is_dir():
            return c
    return candidates[0] if candidates[0] else ""


def expand_path(value: str) -> str:
    if not value:
        return ""
    # ${ENV} or $ENV
    if value.startswith("${") and value.endswith("}"):
        return env_path(value[2:-1])
    if value.startswith("$") and "/" not in value[1:] and "\\" not in value[1:]:
        return env_path(value[1:])
    return os.path.abspath(os.path.expanduser(os.path.expandvars(value)))
