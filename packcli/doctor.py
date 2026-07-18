"""Environment checks for mister-pack."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from packcli.config import converter_root, default_collection, default_dosassets, default_output


def _ok(msg: str) -> None:
    print(f"  OK  {msg}")


def _bad(msg: str) -> None:
    print(f"  !!  {msg}")


def run_doctor() -> int:
    print("mister-pack doctor")
    print(f"  converter: {converter_root()}")
    failed = 0

    # Python
    if sys.version_info >= (3, 10):
        _ok(f"Python {sys.version.split()[0]}")
    else:
        _bad(f"Python {sys.version.split()[0]} (need 3.10+)")
        failed += 1

    # dosforge
    exe = shutil.which("dosforge")
    if exe:
        try:
            r = subprocess.run(
                [exe, "--version"], capture_output=True, text=True, timeout=15
            )
            ver = (r.stdout or r.stderr or "").strip().splitlines()[:1]
            _ok(f"dosforge: {exe} {ver[0] if ver else ''}".strip())
        except Exception as exc:
            _bad(f"dosforge found but failed: {exc}")
            failed += 1
    else:
        # module form
        r = subprocess.run(
            [sys.executable, "-m", "dosforge", "--version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode == 0:
            _ok(f"dosforge module: {(r.stdout or '').strip()}")
        else:
            _bad("dosforge not on PATH (pip install dosforge / sibling checkout)")
            failed += 1

    # converter payloads
    root = converter_root()
    for rel in (
        "data/mister/boot-c.zip",
        "data/mister/distro.zip",
        "data/eXoDOSv6.csv",
    ):
        p = root / rel
        if p.is_file():
            _ok(f"payload {rel}")
        else:
            _bad(f"missing {rel}")
            failed += 1

    for rel, label in (
        ("data/mister/ultrasnd", "ULTRASND tree"),
        ("data/mister/picomem", "PICOMEM tree"),
        ("data/native/picogus", "PicoGUS tools tree"),
        ("data/native/hw", "HW helper BATs"),
    ):
        p = root / rel
        if p.is_dir():
            _ok(f"{label}: {p}")
        else:
            _bad(f"optional missing {label} ({p})")

    # PicoGUS critical DOS tools (always staged for portability)
    for rel, label in (
        ("data/native/picogus/CDMKE.SYS", "CDMKE.SYS (PicoGUS CD)"),
        ("data/native/picogus/PGUSINIT.EXE", "PGUSINIT.EXE"),
        ("data/mister/picomem/PMINIT.EXE", "PMINIT.EXE"),
    ):
        p = root / rel
        if p.is_file():
            _ok(f"payload {label}")
        else:
            _bad(f"missing {label} ({p})")
            failed += 1

    # collection
    coll = default_collection()
    if coll and Path(coll).is_dir():
        exo = Path(coll) / "eXo" / "eXoDOS"
        if exo.is_dir():
            _ok(f"collection: {coll}")
        else:
            _bad(f"collection looks wrong (no eXo/eXoDOS): {coll}")
            failed += 1
    else:
        _bad(
            "EXODOS_COLLECTION not set or missing "
            f"(got {coll!r})"
        )
        failed += 1

    # dosassets (root must contain msdos622/Disk1.img and/or freedos/)
    assets = default_dosassets()
    if assets and Path(assets).is_dir():
        root = Path(assets)
        # If user pointed at msdos622/, walk up for display
        if root.name.lower() == "msdos622" and root.parent.is_dir():
            root = root.parent
        msdos = root / "msdos622"
        disk1 = msdos / "Disk1.img"
        if not disk1.is_file():
            disk1 = msdos / "DISK1.IMG"
        freedos = root / "freedos"
        _ok(f"dosassets: {root}")
        if disk1.is_file():
            _ok(f"msdos622 install disk: {disk1}")
        elif msdos.is_dir():
            _bad(
                f"msdos622/ present but no Disk1.img under {msdos} "
                "(dosforge msdos622 boot will fail)"
            )
            failed += 1
        if freedos.is_dir():
            _ok(f"freedos assets: {freedos}")
        if not disk1.is_file() and not freedos.is_dir():
            _bad(
                "no msdos622/Disk1.img or freedos/ under dosassets "
                f"(expected sibling of converter: "
                f"{Path(converter_root()).parent / 'dosforge' / 'dosassets'})"
            )
            failed += 1
    else:
        sibling = Path(converter_root()).parent / "dosforge" / "dosassets"
        _bad(
            f"dosassets missing (got {assets!r}); "
            f"set DOSFORGE_DOSASSETS_DIR or place media at {sibling}"
        )
        failed += 1

    out = default_output()
    _ok(f"default output: {out}")

    # sudo nbd hint
    if shutil.which("sudo"):
        r = subprocess.run(
            ["sudo", "-n", "true"], capture_output=True, timeout=5
        )
        if r.returncode == 0:
            _ok("sudo -n available (NBD/disk ops)")
        else:
            _bad("sudo -n not available (dosforge may prompt / fail headless)")
            # soft fail — not always required on all platforms
    else:
        _bad("sudo not found")

    print()
    if failed:
        print(f"doctor: {failed} problem(s)")
        print(
            "  Install/update open-source engines with:\n"
            "    python3 -m packcli setup\n"
            "  Point at your eXoDOS collection (not auto-downloaded) with:\n"
            "    python3 -m packcli setup --collection /path/to/eXoDOS"
        )
        return 1
    print("doctor: all required checks passed")
    return 0
