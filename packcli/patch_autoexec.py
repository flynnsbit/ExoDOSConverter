"""Patch AUTOEXEC.BAT on an existing VHD for SB or GUS audio."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from packcli.audio_autoexec import apply_audio_mode, normalize_audio_mode
from packcli.config import default_audio


def _df(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "dosforge", *args],
        capture_output=True,
        text=True,
    )


def run_patch_autoexec(
    vhd_path: str,
    *,
    audio: str | None = None,
    gus: bool | None = None,
) -> int:
    """Patch VHD AUTOEXEC for audio mode.

    ``audio`` is ``sb`` or ``gus``. Legacy ``gus=True/False`` still accepted.
    """
    if audio is None and gus is not None:
        mode = "gus" if gus else "sb"
    elif audio is None:
        mode = default_audio()
    else:
        mode = normalize_audio_mode(audio, default=default_audio())

    vhd = Path(vhd_path)
    if not vhd.is_file():
        print("ERROR: VHD not found:", vhd, file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as td:
        local = Path(td) / "AUTOEXEC.BAT"
        r = _df("get", str(vhd), "::/AUTOEXEC.BAT", str(local))
        if r.returncode != 0:
            print(
                "ERROR: dosforge get AUTOEXEC failed:",
                r.stderr or r.stdout,
                file=sys.stderr,
            )
            return 1
        try:
            text = local.read_text(encoding="ascii")
        except UnicodeDecodeError:
            text = local.read_text(encoding="latin-1")
        new = apply_audio_mode(text, mode)
        new = new.replace("\r\n", "\n").replace("\n", "\r\n")
        local.write_bytes(new.encode("ascii", errors="replace"))
        r = _df("put", str(vhd), str(local), "::/AUTOEXEC.BAT")
        if r.returncode != 0:
            print(
                "ERROR: dosforge put AUTOEXEC failed:",
                r.stderr or r.stdout,
                file=sys.stderr,
            )
            return 1

    print("Patched", vhd, f"::/AUTOEXEC.BAT (audio={mode})")
    r = _df("cat", str(vhd), "::/AUTOEXEC.BAT")
    for line in (r.stdout or "").splitlines():
        if any(
            x in line.upper()
            for x in ("ULTRA", "PMINIT", "BLASTER", "SBCTL", "mister-pack audio")
        ):
            print(" ", line)
    return 0
