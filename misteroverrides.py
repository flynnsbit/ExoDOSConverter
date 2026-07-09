"""Data-driven per-game MiSTer overrides (Phase D5 / D6).

Replaces hardcoded dicts in ``mister.py`` / ``lists.py`` with a single
CSV file:

    data/mister/overrides.csv

Columns (header required)::

    dosname,override_type,payload

``dosname``
    eXoDOS short folder id (case-insensitive match against ``gGator.game``).

``override_type`` values
    unused_cd
        ``payload`` = relative cue/iso path (as previously in
        ``mister.removeUnusedCds``). Files sharing that stem are deleted
        from the extracted game tree so only the used disc remains.

    run_bat_handling
        ``payload`` ignored. Marks the game for special ``run.bat``
        rewriting (formerly ``lists.gamesWithRunBatHandling``).

    mount_other_game_cd
        ``payload`` = ``otherDosname/filename.ext`` (forward or back
        slashes). Emitted CD mount path becomes
        ``/cd/<otherDosname>/<filename>`` instead of this game's own
        folder. Used when Top300 mounts a prior-title disc (DW2→DW1,
        KQ5→KQ1, etc.).

    # reserved for later (parsed, not yet applied):
    force_root_install, force_mister_include, force_mister_exclude

Pure stdlib ``csv``. Missing file → empty overrides (no crash).
"""

from __future__ import annotations

import csv
import os


_OVERRIDE_TYPES = frozenset({
    "unused_cd",
    "run_bat_handling",
    "mount_other_game_cd",
    "force_root_install",
    "force_mister_include",
    "force_mister_exclude",
})

# Module-level cache keyed by absolute CSV path.
_CACHE = {}


def default_csv_path(script_dir: str) -> str:
    return os.path.join(script_dir, "data", "mister", "overrides.csv")


def load_overrides(csv_path: str | None, logger=None) -> dict:
    """Return ``{dosname_lower: {override_type: [payload, ...]}}``.

    Multiple rows of the same type for one game are allowed (list of
    payloads). Empty payload stored as ``""``.
    """
    if not csv_path:
        return {}
    abs_path = os.path.abspath(csv_path)
    if abs_path in _CACHE:
        return _CACHE[abs_path]
    result = {}
    if not os.path.isfile(abs_path):
        if logger is not None:
            logger.log(
                "  <WARNING> overrides.csv not found at %s (using empty set)"
                % abs_path,
                getattr(logger, "WARNING", None),
            )
        _CACHE[abs_path] = result
        return result

    with open(abs_path, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(
            (row for row in fh if row.strip() and not row.lstrip().startswith("#"))
        )
        if reader.fieldnames is None:
            _CACHE[abs_path] = result
            return result
        # Normalise header names
        field_map = {name.strip().lower(): name for name in reader.fieldnames}
        for required in ("dosname", "override_type"):
            if required not in field_map:
                if logger is not None:
                    logger.log(
                        "  <ERROR> overrides.csv missing column %r" % required,
                        getattr(logger, "ERROR", None),
                    )
                _CACHE[abs_path] = result
                return result

        for row in reader:
            dosname = (row.get(field_map["dosname"]) or "").strip()
            otype = (row.get(field_map["override_type"]) or "").strip().lower()
            payload_key = field_map.get("payload")
            payload = (row.get(payload_key) or "").strip() if payload_key else ""
            if not dosname or not otype:
                continue
            if otype not in _OVERRIDE_TYPES:
                if logger is not None:
                    logger.log(
                        "  <WARNING> overrides.csv unknown type %r for %s"
                        % (otype, dosname),
                        getattr(logger, "WARNING", None),
                    )
                continue
            key = dosname.lower()
            bucket = result.setdefault(key, {})
            bucket.setdefault(otype, []).append(payload)

    _CACHE[abs_path] = result
    if logger is not None:
        n_games = len(result)
        n_rows = sum(len(v) for g in result.values() for v in g.values())
        logger.log("  Loaded %i override row(s) for %i game(s) from %s"
                   % (n_rows, n_games, abs_path))
    return result


def clear_cache():
    """Test helper — drop the module cache."""
    _CACHE.clear()


def get_overrides_for(script_dir: str, dosname: str, logger=None) -> dict:
    """Return override-type → payloads map for one game (may be empty)."""
    table = load_overrides(default_csv_path(script_dir), logger=logger)
    return table.get((dosname or "").lower(), {})


def unused_cd_paths(script_dir: str, dosname: str, logger=None) -> list:
    ov = get_overrides_for(script_dir, dosname, logger=logger)
    return list(ov.get("unused_cd", []))


def needs_run_bat_handling(script_dir: str, dosname: str, logger=None) -> bool:
    ov = get_overrides_for(script_dir, dosname, logger=logger)
    if "run_bat_handling" in ov:
        return True
    # Backward-compat: still honour lists.py until fully retired.
    try:
        import lists
        if dosname in lists.gamesWithRunBatHandling:
            return True
    except Exception:
        pass
    return False


def mount_other_game_cd(script_dir: str, dosname: str, logger=None) -> str | None:
    """Return ``otherDosname/filename`` payload or None."""
    ov = get_overrides_for(script_dir, dosname, logger=logger)
    payloads = ov.get("mount_other_game_cd") or []
    if not payloads:
        return None
    # First payload wins for the primary CD mount.
    return payloads[0].replace("\\", "/")
