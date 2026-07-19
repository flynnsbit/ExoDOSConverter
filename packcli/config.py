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
    """Resolve dosassets root (contains msdos622/, freedos/, …).

    Order: env → config → sibling of this converter checkout → ~/Projects/dosforge
    → ~/.dosforge. Prefers a tree that has msdos622 or freedos media.
    """
    candidates = [
        env_path("DOSFORGE_DOSASSETS_DIR"),
        env_path("MISTER_DOSASSETS"),
        _cfg_str("dosassets"),
        # Sibling of ExoDOSConverter (…/Projects/dosforge/dosassets)
        str(converter_root().parent / "dosforge" / "dosassets"),
        os.path.expanduser("~/Projects/dosforge/dosassets"),
        os.path.expanduser("~/.dosforge/dosassets"),
    ]

    def _score(path: str) -> int:
        p = Path(path)
        if not p.is_dir():
            return -1
        score = 0
        if (p / "msdos622" / "Disk1.img").is_file() or (
            p / "msdos622" / "DISK1.IMG"
        ).is_file():
            score += 2
        if (p / "freedos").is_dir():
            score += 1
        if (p / "msdos622").is_dir():
            score += 1
        return score

    best = ""
    best_score = -1
    for c in candidates:
        if not c:
            continue
        # Allow pointing at msdos622/ itself
        p = Path(c).expanduser()
        if p.is_dir() and p.name.lower() in (
            "msdos622",
            "freedos",
            "msdos71",
            "msdos5",
        ):
            c = str(p.parent)
        s = _score(c)
        if s > best_score:
            best_score = s
            best = c
    if best_score >= 0:
        return str(Path(best).expanduser().resolve())
    return next((c for c in candidates if c), "")


def default_audio() -> str:
    """Default AUTOEXEC audio mode: ``sb`` or ``gus``.

    Order: env ``MISTER_PACK_AUDIO`` → config.toml ``audio`` → ``sb``.
    """
    raw = env_path(
        "MISTER_PACK_AUDIO",
        env_path("EDC_AUDIO", _cfg_str("audio", "sb")),
    )
    v = raw.strip().lower()
    if v in ("gus", "gravis", "ultrasound", "ultrasnd"):
        return "gus"
    return "sb"


VALID_TARGETS = ("mister", "picomem", "picogus", "picoide")

# dosforge create --boot-mode values (+ auto)
VALID_BOOT_MODES = (
    "auto",
    "none",
    "freedos",
    "msdos71",
    "ibm8088",
    "msdos33",
    "msdos331",
    "msdos5",
    "msdos6",
    "msdos622",
    "pcdos7",
    "pcdos2000",
    "pcdos71",
    "compaq331",
    "compaq2",
    "pcdos3",
    "pcdos5",
    "compaq3",
    "drdos6",
    "drdos7",
    "4dos",
)


def normalize_boot_mode(value: str | None, default: str = "auto") -> str:
    try:
        from packcli.boot_rules.capabilities import normalize_boot_mode as _norm

        return _norm(value, default)
    except Exception:
        v = (value or default or "auto").strip().lower()
        return v if v in VALID_BOOT_MODES else default


def default_boot_mode() -> str:
    raw = env_path(
        "MISTER_PACK_DOS",
        env_path("MISTER_PACK_BOOT", _cfg_str("dos", _cfg_str("boot", "auto"))),
    )
    return normalize_boot_mode(raw or "auto", "auto")


def normalize_target(value: str | None, default: str = "mister") -> str:
    v = (value or default or "mister").strip().lower()
    aliases = {
        "ao486": "mister",
        "mister-ao486": "mister",
        "pm": "picomem",
        "gus": "picogus",  # ambiguous; prefer explicit picogus
        "picogus2": "picogus",
        "ide": "picoide",
    }
    v = aliases.get(v, v)
    if v not in VALID_TARGETS:
        return default if default in VALID_TARGETS else "mister"
    return v


def default_target() -> str:
    """Hardware pack target: mister | picomem | picogus | picoide.

    Order: env ``MISTER_PACK_TARGET`` / ``PACK_TARGET`` → config ``target`` → mister.
    """
    raw = env_path(
        "MISTER_PACK_TARGET",
        env_path("PACK_TARGET", _cfg_str("target", "mister")),
    )
    return normalize_target(raw, "mister")


def expand_path(value: str) -> str:
    if not value:
        return ""
    # ${ENV} or $ENV
    if value.startswith("${") and value.endswith("}"):
        return env_path(value[2:-1])
    if value.startswith("$") and "/" not in value[1:] and "\\" not in value[1:]:
        return env_path(value[1:])
    return os.path.abspath(os.path.expanduser(os.path.expandvars(value)))
