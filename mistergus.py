"""Apply Gravis UltraSound as the default audio preset for converted games.

eXoDOS packs ship GUS/ (or gus/) preset folders and run.bat sound menus.
For MiSTer we apply those presets up front and rewrite autorun so CHOICE menus
are skipped (no keyboard required at boot).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def _copy_tree_files(src: Path, dest: Path) -> int:
    """Copy files from src into dest (non-recursive files only + one level)."""
    if not src.is_dir():
        return 0
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    for item in src.iterdir():
        if item.is_file():
            shutil.copy2(item, dest / item.name)
            n += 1
    return n


def _write_sel(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\r\n")


def _write_dos_text(path: Path, lines: list[str]) -> None:
    text = "\r\n".join(lines) + "\r\n"
    path.write_bytes(text.encode("ascii", errors="replace"))


def apply_gus_defaults(gameDir: str, logger=None) -> bool:
    """Apply GUS presets under a converted game folder (…/games/<Title>/).

    Returns True when any GUS action was taken.
    """
    root = Path(gameDir)
    if not root.is_dir():
        return False

    actions = 0
    # Case-insensitive search for known GUS layout patterns.
    lowers = {p.name.lower(): p for p in root.rglob("*") if p.is_dir()}

    def log(msg: str) -> None:
        if logger is not None:
            logger.log("    GUS: %s" % msg)
        else:
            print("    GUS:", msg)

    # --- Pattern: root GUS/ or gus/ (DOOM, Raptor) ---
    for name in ("gus", "GUS"):
        g = root / name
        if g.is_dir():
            actions += _copy_tree_files(g, root)
            _write_sel(root / "GUS.SEL")
            log("applied root %s/ + GUS.SEL" % name)
            break

    # Nested GUS next to game EXE dirs (Duke3D, OMF, Crusader, Epic, Blood)
    for rel in (
        "DUKE3D",
        "Duke3D",
        "duke3d",
        "OMF",
        "CRUSADER",
        "Crusader",
        "EPIC",
        "Epic",
        "BLOOD",
        "Blood",
        "Blood3D",
        "BLOODcp",
        "BloodPak",
        "SW",
        "JAZZ",
        "Jazz",
    ):
        gameSub = root / rel
        if not gameSub.is_dir():
            continue
        for gname in ("GUS", "gus"):
            gdir = gameSub / gname
            if gdir.is_dir():
                actions += _copy_tree_files(gdir, gameSub)
                _write_sel(gameSub / "GUS.SEL")
                _write_sel(root / "GUS.SEL")
                log("applied %s/%s -> %s" % (rel, gname, rel))
                break

    # Blood multi-tree
    for blood in ("BLOOD", "Blood", "Blood3D", "BLOODcp", "BloodPak", "blood"):
        b = root / blood
        if not b.is_dir():
            continue
        for gname in ("GUS", "gus"):
            gdir = b / gname
            if gdir.is_dir():
                actions += _copy_tree_files(gdir, b)
                _write_sel(b / "GUS.SEL")
                actions += 1
                log("blood tree %s GUS" % blood)

    # Pinball Fantasies: SOUND.CFG points at active SDR driver
    for sound_cfg in root.rglob("SOUND.CFG"):
        parent = sound_cfg.parent
        if (parent / "GUS.SDR").is_file():
            sound_cfg.write_bytes(b"GUS.SDR\r\n")
            actions += 1
            log("Pinball Fantasies SOUND.CFG -> GUS.SDR")

    # Jazz Jackrabbit: if a GUS mus/driver exists under jazz, prefer it
    for soundcrd in root.rglob("SOUNDCRD.INF"):
        parent = soundcrd.parent
        # If gus/SOUNDCRD.INF exists, copy it over
        for gname in ("GUS", "gus"):
            alt = parent / gname / "SOUNDCRD.INF"
            if alt.is_file():
                shutil.copy2(alt, soundcrd)
                actions += 1
                log("SOUNDCRD.INF from %s" % gname)
                break

    # Flatten any run.bat that has a :GUS label into a GUS-only launcher
    # (skips CHOICE sound menus on MiSTer).
    for run_bat in list(root.rglob("run.bat")) + list(root.rglob("RUN.BAT")):
        try:
            text = run_bat.read_text(encoding="latin-1", errors="replace")
        except OSError:
            continue
        if ":GUS" not in text.upper():
            continue
        if _rewrite_run_bat_gus_only(run_bat, text):
            actions += 1
            log("rewrote %s as GUS-only" % run_bat.relative_to(root))

    # autorun: env + optional ULTRAMID + 1_Start (which calls run / game)
    start = root / "1_Start.bat"
    autorun = root / "autorun.bat"
    lines = [
        "@ECHO OFF",
        "REM Default audio: Gravis UltraSound",
        "SET ULTRASND=240,1,1,5,5",
        "SET ULTRADIR=C:\\ULTRASND",
        "IF EXIST C:\\ULTRASND\\ULTRAMID.EXE C:\\ULTRASND\\ULTRAMID.EXE",
        "IF EXIST GUS\\NUL COPY /Y GUS\\*.* .>NUL",
        "IF EXIST gus\\NUL COPY /Y gus\\*.* .>NUL",
        "IF NOT EXIST GUS.SEL ECHO.>GUS.SEL",
    ]
    if start.is_file():
        lines.append("CALL 1_Start.bat")
    elif (root / "run.bat").is_file():
        lines.append("CALL run.bat")
    _write_dos_text(autorun, lines)
    actions += 1
    log("rewrote autorun.bat for GUS default")

    return actions > 0


def _rewrite_run_bat_gus_only(run_bat: Path, text: str) -> bool:
    """Replace a multi-sound run.bat with a direct GUS apply + launch path."""
    upper = text.upper()
    idx = upper.find(":GUS")
    if idx < 0:
        return False
    # Take from :GUS until :QUIT or next major menu label that isn't launch
    chunk = text[idx:]
    # Keep through first 'goto quit' / exit after launch
    lines_out = [
        "@ECHO OFF",
        "REM GUS-only launcher (sound menu removed for MiSTer default)",
        "SET ULTRASND=240,1,1,5,5",
        "SET ULTRADIR=C:\\ULTRASND",
    ]
    # Prefer known apply patterns from eXo GUS labels
    body = chunk.splitlines()
    kept = []
    for line in body:
        s = line.strip()
        su = s.upper()
        if su.startswith(":GUS"):
            continue
        if su.startswith(":") and su not in (":QUIT", ":Q", ":N"):
            # stop at next label after we've seen a launch
            if kept and any(
                x in "\n".join(kept).upper()
                for x in ("@DOOM", "@DUKE", "@RAP", "@OMF", "@CRUSADER", "@PINBALL", "@BLOOD", "GOTO QUIT", "GOTO MENU2")
            ):
                break
            if su in (":SB16", ":SC55", ":MENU", ":START", ":SETUP", ":NETWORK", ":CDA", ":SW", ":SWS"):
                break
        # Drop DOSBox-only CONFIG -set lines
        if su.startswith("CONFIG ") or su.startswith("CONFIG\t"):
            continue
        kept.append(line.rstrip("\r\n"))
        if su in ("GOTO QUIT", "GOTO Q", "EXIT") or su.startswith("@DOOM") or su.startswith("@DUKE"):
            # include a few more lines then stop
            pass
    if not kept:
        return False
    lines_out.extend(kept)
    if not any(l.strip().upper() in ("GOTO QUIT", "EXIT") for l in lines_out):
        lines_out.append("EXIT")
    _write_dos_text(run_bat, lines_out)
    return True


def apply_gus_to_pack_games(gamesRoot: str, logger=None) -> int:
    """Apply GUS defaults to every folder under gamesRoot. Returns count."""
    root = Path(gamesRoot)
    if not root.is_dir():
        return 0
    count = 0
    for child in sorted(root.iterdir()):
        if child.is_dir() and apply_gus_defaults(str(child), logger=logger):
            count += 1
    return count
