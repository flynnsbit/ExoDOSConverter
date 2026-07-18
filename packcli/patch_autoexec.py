"""Patch AUTOEXEC.BAT (and optional game bats) on an existing VHD."""

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path


ULTRASND_VALUE = "240,1,1,5,5"
PMINIT_LINE = r"IF EXIST C:\PICOMEM\PMINIT.EXE C:\PICOMEM\PMINIT.EXE /GUS 1"


def _df(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "dosforge", *args],
        capture_output=True,
        text=True,
    )


def patch_text(text: str, *, gus: bool = True) -> str:
    nl = "\r\n" if "\r\n" in text else "\n"
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    if gus:
        text = re.sub(
            r"(?im)^(\s*SET\s+ULTRASND\s*=\s*).*$",
            r"\g<1>" + ULTRASND_VALUE,
            text,
        )
        if not re.search(r"(?im)^\s*SET\s+ULTRASND\s*=", text):
            # Insert after BLASTER block or near top after @ECHO OFF
            if re.search(r"(?im)^\s*SET\s+BLASTER\s*=", text):
                text = re.sub(
                    r"(?im)^(\s*SET\s+BLASTER\s*=\s*.*)$",
                    r"\1\nSET ULTRASND="
                    + ULTRASND_VALUE
                    + r"\nSET ULTRADIR=C:\ULTRASND\n"
                    + PMINIT_LINE.replace("\\", "\\\\"),
                    text,
                    count=1,
                )
            else:
                text = re.sub(
                    r"(?im)^(\s*@?ECHO\s+OFF\s*)$",
                    r"\1\nSET ULTRASND="
                    + ULTRASND_VALUE
                    + r"\nSET ULTRADIR=C:\ULTRASND\n"
                    + PMINIT_LINE.replace("\\", "\\\\"),
                    text,
                    count=1,
                )
        if not re.search(r"(?im)^\s*SET\s+ULTRADIR\s*=", text):
            text = re.sub(
                r"(?im)^(\s*SET\s+ULTRASND\s*=\s*.*)$",
                r"\1\nSET ULTRADIR=C:\\ULTRASND",
                text,
                count=1,
            )
        # Drop old PMINIT lines then re-insert after ULTRADIR
        text = re.sub(
            r"(?im)^\s*IF EXIST\s+C:\\PICOMEM\\PMINIT\.EXE\s+C:\\PICOMEM\\PMINIT\.EXE\s+/GUS\s+1\s*\n?",
            "",
            text,
        )
        text = re.sub(
            r"(?im)^(\s*SET\s+ULTRADIR\s*=\s*.*)$",
            r"\1\nIF EXIST C:\\PICOMEM\\PMINIT.EXE C:\\PICOMEM\\PMINIT.EXE /GUS 1",
            text,
            count=1,
        )

    # Ensure PATH includes ULTRASND and PICOMEM when GUS
    if gus and re.search(r"(?im)^\s*PATH\s*=", text):
        def path_fix(m):
            p = m.group(0)
            up = p.upper()
            add = []
            if "ULTRASND" not in up:
                add.append(r"C:\ULTRASND")
            if "PICOMEM" not in up:
                add.append(r"C:\PICOMEM")
            if not add:
                return p
            # PATH=a;b;c
            if p.rstrip().endswith("="):
                return p + ";".join(add)
            return p.rstrip() + ";" + ";".join(add)

        text = re.sub(r"(?im)^\s*PATH\s*=.*$", path_fix, text, count=1)

    return text.replace("\n", nl)


def run_patch_autoexec(vhd_path: str, *, gus: bool = True) -> int:
    vhd = Path(vhd_path)
    if not vhd.is_file():
        print("ERROR: VHD not found:", vhd, file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as td:
        local = Path(td) / "AUTOEXEC.BAT"
        r = _df("get", str(vhd), "::/AUTOEXEC.BAT", str(local))
        if r.returncode != 0:
            print("ERROR: dosforge get AUTOEXEC failed:", r.stderr or r.stdout, file=sys.stderr)
            return 1
        try:
            text = local.read_text(encoding="ascii")
        except UnicodeDecodeError:
            text = local.read_text(encoding="latin-1")
        new = patch_text(text, gus=gus)
        new = new.replace("\r\n", "\n").replace("\n", "\r\n")
        local.write_bytes(new.encode("ascii", errors="replace"))
        r = _df("put", str(vhd), str(local), "::/AUTOEXEC.BAT")
        if r.returncode != 0:
            print("ERROR: dosforge put AUTOEXEC failed:", r.stderr or r.stdout, file=sys.stderr)
            return 1

    print("Patched", vhd, "::/AUTOEXEC.BAT")
    r = _df("cat", str(vhd), "::/AUTOEXEC.BAT")
    for line in (r.stdout or "").splitlines():
        if any(x in line.upper() for x in ("ULTRA", "PMINIT", "BLASTER", "PATH=")):
            print(" ", line)
    return 0
