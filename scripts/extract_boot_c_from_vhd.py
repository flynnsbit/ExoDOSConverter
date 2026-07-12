#!/usr/bin/env python3
"""Rebuild data/mister/boot-c.zip from a Top300 BOOT-DOS98.vhd.

Extracts C:\\DRIVERS, C:\\QEMM, and DOS supplements (HIMEM/EMM386/SETVER/
ASSIGN/IFSHLP), then packs them with the adapted CONFIG.SYS / AUTOEXEC.BAT
templates already in this tree (or regenerates C:-only templates).

Example:
  python3 scripts/extract_boot_c_from_vhd.py \\
    --vhd vhdtemplate/IDE\\ 0-0\\ BOOT-DOS98.vhd \\
    --out data/mister/boot-c.zip

Source VHDs (same image):
  - Local:  ExoDOSConverter/vhdtemplate/IDE 0-0 BOOT-DOS98.vhd
  - SMB:    smb://denpc/18tb/MiSTer Projects/top-300-final/IDE 0-0 BOOT-DOS98.vhd
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile


FIXED_VHD_OFFSET = 32256  # 63 * 512 — typical fixed VHD first partition

# DOS files required by Top300 CONFIG.SYS / AUTOEXEC.BAT
_DOS_SUPPLEMENTS = (
    "HIMEM.SYS",
    "EMM386.EXE",
    "SETVER.EXE",
    "ASSIGN.COM",
    "IFSHLP.SYS",
)


def _mcopy(vhd: str, off: int, src: str, dest: str, recursive: bool = False) -> None:
    image = "%s@@%s" % (vhd, off)
    cmd = ["mcopy", "-n", "-i", image]
    if recursive:
        cmd.append("-s")
    cmd.extend([src, dest])
    env = os.environ.copy()
    env["MTOOLS_SKIP_CHECK"] = "1"
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if r.returncode != 0:
        raise RuntimeError("mcopy failed %s -> %s: %s" % (src, dest, r.stderr or r.stdout))


def _write_templates(workdir: str) -> None:
    """Write C:-only Top300-style CONFIG.SYS + AUTOEXEC.BAT (CRLF)."""
    config = """[MENU]
MENUDEFAULT=HIRAM,2

MENUITEM=HIRAM,HIRAM: Default for most games in the pack.
MENUITEM=EMM386,EMM386: Fall back option for games.
MENUITEM=QEMM,QEMM386: Only a couple of games require QEMM.
MENUITEM=EXTENDED,EXTENDED: Future use.
MENUITEM=CLEAN,CLEAN: HIMEM only, boots to command prompt.

MENUCOLOR=15,3

[CLEAN]
SET MEMMGR=CLEAN
DEVICE=C:\\DRIVERS\\XCDROM.SYS /D:IDE-CD

[HIRAM]
SET MEMMGR=HIRAM
DEVICE=C:\\DOS\\HIMEM.SYS /Q /TESTMEM:OFF /NUMHANDLES=128
DEVICEHIGH=C:\\DRIVERS\\HIRAM\\HIRAM.EXE /Exclude=CE00-CFFF
DEVICEHIGH=C:\\DOS\\SETVER.EXE
DOS=UMB,HIGH,NOAUTO
DEVICEHIGH=C:\\DRIVERS\\XCDROM.SYS /D:IDE-CD

[EXTENDED]
SET MEMMGR=EXTENDED
DEVICE=C:\\DOS\\HIMEM.SYS /Q /TESTMEM:OFF
DEVICEHIGH=C:\\DOS\\SETVER.EXE
DOS=UMB,HIGH,NOAUTO
DEVICEHIGH=C:\\DRIVERS\\XCDROM.SYS /D:IDE-CD

[EMM386]
SET MEMMGR=EMM386
DEVICE=C:\\DOS\\HIMEM.SYS /Q /TESTMEM:OFF
DEVICEHIGH=C:\\DOS\\EMM386.EXE AUTO 32768 RAM FRAME=D000 D=64 X=C000-CFFF I=B000-B7FF I=D000-EFFF
DEVICEHIGH=C:\\DOS\\SETVER.EXE
DOS=HIGH,UMB,NOAUTO
DEVICEHIGH=C:\\DRIVERS\\XCDROM.SYS /D:IDE-CD

[QEMM]
SET MEMMGR=QEMM386
device=c:\\qemm\\dosdata.sys
SET LOADHIDATA=C:\\QEMM\\LOADHI.RF
DEVICE=C:\\QEMM\\QEMM386.SYS RAM BE:N FRAME=D000 ARAM=D000-EFFF ARAM=B000-B7FF RF
device=c:\\qemm\\dos-up.sys @c:\\qemm\\dos7-up.dat
DEVICE=C:\\QEMM\\LOADHI.SYS /RF C:\\QEMM\\QDPMI.SYS SWAPFILE=DPMI.SWP SWAPSIZE=1024
DEVICE=C:\\QEMM\\LOADHI.SYS /RF C:\\DOS\\SETVER.EXE
SHELL=C:\\QEMM\\LOADHI.COM /RF COMMAND.COM /P /E:640
DOS=HIGH,UMB
DEVICE=C:\\QEMM\\LOADHI.SYS /RF C:\\DOS\\IFSHLP.SYS
DEVICE=C:\\QEMM\\LOADHI.SYS /RF C:\\DRIVERS\\XCDROM.SYS /D:IDE-CD

[common]
FILESHIGH=60
BUFFERSHIGH=40
FCBSHIGH=4,0
STACKSHIGH=11,512
LASTDRIVEHIGH=Z
NUMLOCK=ON
"""
    autoexec = """@ECHO OFF
REM Top300-style base for single-VHD greenfield packs (C: only).
REM Source: flynnsbit/Top300_updates _C + BOOT-DOS98 drivers.

REM Comment this line if changing to IRQ 7
REM SET BLASTER=A220 I5 D1 T4

REM Sound Blaster on IRQ 7 (MiSTer ao486 default for many packs)
IF EXIST C:\\DRIVERS\\SBCTL.EXE LOADHIGH C:\\DRIVERS\\SBCTL.EXE I7 T6
SET BLASTER=A220 I7 D1 H5 P330 T6

SET DIRCMD=/A/4/O:GEN
SET TEMP=C:\\TMP
SET TMP=C:\\TMP
PATH=C:\\;C:\\DOS;C:\\DRIVERS;C:\\DRIVERS\\SHCD;C:\\MYMENU;C:\\MYMENU\\UTILS;C:\\UTILS
PROMPT $P$G
SET DOS32A=C:\\DRIVERS
GOTO %CONFIG%

:QEMM
IF EXIST C:\\DRIVERS\\SHSUCDX.COM C:\\QEMM\\LOADHI /RF C:\\DRIVERS\\SHSUCDX.COM /D:IDE-CD /L:D /V /C
IF EXIST C:\\DRIVERS\\CUTEPACK\\CTMOUSE.EXE C:\\QEMM\\LOADHI /RF C:\\DRIVERS\\CUTEPACK\\CTMOUSE.EXE /O
REM IF EXIST C:\\DRIVERS\\SOFTMPU\\SOFTMPU.EXE C:\\QEMM\\LOADHI /RF C:\\DRIVERS\\SOFTMPU\\SOFTMPU.EXE /MPU:330 /OUTPUT:COM1
IF EXIST C:\\DRIVERS\\DOSKEY20.COM C:\\QEMM\\LOADHI /RF C:\\DRIVERS\\DOSKEY20.COM /INSERT
GOTO COMMON

:HIRAM
CLS
GOTO COMMON

:EXTENDED
CLS
GOTO COMMON

:EMM386
REM IF EXIST C:\\DRIVERS\\SOFTMPU\\SOFTMPU.EXE LOADHIGH C:\\DRIVERS\\SOFTMPU\\SOFTMPU.EXE /MPU:330 /OUTPUT:COM1
GOTO COMMON

:COMMON
CLS
IF EXIST C:\\DRIVERS\\UNIVBE.EXE LOADHIGH C:\\DRIVERS\\UNIVBE.EXE -w
REM Single-VHD: C: = HDD, D: = CD (imgset/imgtry). No ASSIGN / no E: games disk.
IF EXIST C:\\DRIVERS\\SHSUCDX.COM LOADHIGH C:\\DRIVERS\\SHSUCDX.COM /D:IDE-CD /L:D /V /C
IF EXIST C:\\DRIVERS\\CUTEPACK\\CTMOUSE.EXE LOADHIGH C:\\DRIVERS\\CUTEPACK\\CTMOUSE.EXE /O
IF EXIST C:\\DRIVERS\\DOSKEY20.COM LOADHIGH C:\\DRIVERS\\DOSKEY20.COM /INSERT
REM IF EXIST C:\\DRIVERS\\MISTERFS.EXE LOADHIGH C:\\DRIVERS\\MISTERFS.EXE Z
IF EXIST C:\\DRIVERS\\UNIVBE.EXE LOADHIGH C:\\DRIVERS\\UNIVBE.EXE -W
IF EXIST C:\\MYMENU\\UTILS\\DOSLFN.COM LOADHIGH C:\\MYMENU\\UTILS\\DOSLFN.COM
IF EXIST C:\\MYMENU\\UTILS\\DOSLFNM.COM LOADHIGH C:\\MYMENU\\UTILS\\DOSLFNM.COM
IF EXIST C:\\UTILS\\DOSLFN.COM LOADHIGH C:\\UTILS\\DOSLFN.COM
CLS

REM --- MyMenu frontend (single VHD, C: only) ---
IF EXIST C:\\RUNMENU.BAT CALL C:\\RUNMENU.BAT
IF EXIST C:\\MYMENU\\MENU.BAT CALL C:\\MYMENU\\MENU.BAT
IF EXIST C:\\MYMENU\\MYMENU.EXE C:\\MYMENU\\MYMENU.EXE C:\\GAMES
:REMENU
IF EXIST C:\\RUNMENU.BAT CALL C:\\RUNMENU.BAT
IF EXIST C:\\MYMENU\\MENU.BAT CALL C:\\MYMENU\\MENU.BAT
IF EXIST C:\\MYMENU\\MYMENU.EXE C:\\MYMENU\\MYMENU.EXE C:\\GAMES
GOTO REMENU

:CLEAN
IF EXIST C:\\DRIVERS\\SHSUCDX.COM C:\\DRIVERS\\SHSUCDX.COM /D:IDE-CD /L:D /V /C
IF EXIST C:\\DRIVERS\\CUTEPACK\\CTMOUSE.EXE C:\\DRIVERS\\CUTEPACK\\CTMOUSE.EXE /O
@ECHO.
@ECHO CLEAN profile: MyMenu not auto-loaded.
GOTO END

:END
"""
    for name, text in (("CONFIG.SYS", config), ("AUTOEXEC.BAT", autoexec)):
        data = text.replace("\r\n", "\n").replace("\n", "\r\n").encode("ascii", errors="replace")
        with open(os.path.join(workdir, name), "wb") as fh:
            fh.write(data)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--vhd",
        default=os.path.join(
            os.path.dirname(__file__),
            "..",
            "vhdtemplate",
            "IDE 0-0 BOOT-DOS98.vhd",
        ),
        help="Path to BOOT-DOS98.vhd",
    )
    parser.add_argument(
        "--out",
        default=os.path.join(
            os.path.dirname(__file__), "..", "data", "mister", "boot-c.zip"
        ),
        help="Output zip path",
    )
    parser.add_argument("--offset", type=int, default=FIXED_VHD_OFFSET)
    args = parser.parse_args(argv)

    vhd = os.path.abspath(args.vhd)
    out = os.path.abspath(args.out)
    if not os.path.isfile(vhd):
        print("ERROR: VHD not found: %s" % vhd, file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory(prefix="boot-c-") as work:
        print("Extracting from", vhd, "offset", args.offset)
        _mcopy(vhd, args.offset, "::/DRIVERS", work + os.sep, recursive=True)
        _mcopy(vhd, args.offset, "::/QEMM", work + os.sep, recursive=True)
        dosDir = os.path.join(work, "DOS")
        os.makedirs(dosDir, exist_ok=True)
        for name in _DOS_SUPPLEMENTS:
            try:
                _mcopy(vhd, args.offset, "::/DOS/%s" % name, dosDir + os.sep)
            except RuntimeError as exc:
                print("  warning: %s" % exc, file=sys.stderr)
        _write_templates(work)

        os.makedirs(os.path.dirname(out), exist_ok=True)
        if os.path.exists(out):
            os.remove(out)
        with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(work):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, work)
                    zf.write(full, rel)
        print("Wrote", out, "(%i bytes)" % os.path.getsize(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
