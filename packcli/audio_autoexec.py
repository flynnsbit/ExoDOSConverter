"""Sound Blaster vs Gravis UltraSound AUTOEXEC.BAT audio blocks.

User/recipe config selects ``sb`` or ``gus``. Hardware ``target`` adjusts
which init binary is preferred (PMINIT vs PGUSINIT) while keeping common env.

- SB:  ``SET BLASTER=A220 I7 D1 H5 P330 T6`` then hardware init
- GUS: ``SET ULTRASND=240,1,1,5,5`` + ``ULTRADIR`` then hardware init
"""

from __future__ import annotations

import re
from typing import Literal

AudioMode = Literal["sb", "gus"]
PackTarget = Literal["mister", "picomem", "picogus", "picoide"]

BLASTER_VALUE = "A220 I7 D1 H5 P330 T6"
ULTRASND_VALUE = "240,1,1,5,5"

# Marker region rewritten wholesale so mode switches stay clean.
_BEGIN = "REM --- mister-pack audio begin ---"
_END = "REM --- mister-pack audio end ---"
_HW_BEGIN = "REM --- mister-pack hw begin ---"
_HW_END = "REM --- mister-pack hw end ---"


def normalize_audio_mode(value: str | None, default: str = "sb") -> AudioMode:
    v = (value or default or "sb").strip().lower()
    if v in ("gus", "gravis", "ultrasound", "ultrasnd"):
        return "gus"
    if v in ("sb", "soundblaster", "sound_blaster", "blaster"):
        return "sb"
    return "sb" if default != "gus" else "gus"


def normalize_target(value: str | None, default: str = "mister") -> PackTarget:
    v = (value or default or "mister").strip().lower()
    if v in ("picomem", "pm"):
        return "picomem"
    if v in ("picogus", "guscard"):
        return "picogus"
    if v in ("picoide", "ide"):
        return "picoide"
    return "mister"


def audio_block(mode: AudioMode, target: PackTarget | str = "mister") -> str:
    """CRLF-free LF block (caller converts to CRLF for DOS)."""
    target = normalize_target(str(target))
    mode = normalize_audio_mode(str(mode))
    lines = [_BEGIN]
    if mode == "sb":
        lines.extend(
            [
                "REM Sound Blaster 16 defaults",
                r"IF EXIST C:\DRIVERS\SBCTL.EXE LOADHIGH C:\DRIVERS\SBCTL.EXE I7 T6",
                f"SET BLASTER={BLASTER_VALUE}",
            ]
        )
        lines.extend(_audio_init_lines(mode, target))
    else:
        lines.extend(
            [
                "REM Sound Blaster env (many titles still read BLASTER)",
                r"IF EXIST C:\DRIVERS\SBCTL.EXE LOADHIGH C:\DRIVERS\SBCTL.EXE I7 T6",
                f"SET BLASTER={BLASTER_VALUE}",
                "REM Gravis UltraSound / PicoGUS (DMA 1,1 + IRQ 5,5)",
                f"SET ULTRASND={ULTRASND_VALUE}",
                r"SET ULTRADIR=C:\ULTRASND",
            ]
        )
        lines.extend(_audio_init_lines(mode, target))
    lines.append(_END)
    return "\n".join(lines)


def _audio_init_lines(mode: AudioMode, target: PackTarget) -> list[str]:
    """Hardware-specific init after shared env vars."""
    if target in ("picogus", "picoide"):
        # PicoGUS: card firmware + pgusinit; still try PMINIT if both boards present
        lines = [
            r"IF EXIST C:\DRIVERS\PICOGUS\PGUSINIT.EXE C:\DRIVERS\PICOGUS\PGUSINIT.EXE /mode sb",
        ]
        if mode == "gus":
            lines = [
                "REM PicoGUS GUS mode is firmware; ensure card is in GUS mode",
                r"REM IF EXIST C:\DRIVERS\PICOGUS\PGUSINIT.EXE C:\DRIVERS\PICOGUS\PGUSINIT.EXE /mode gus",
            ]
        # Portable: also enable PicoMEM audio if that card is in the machine
        if mode == "sb":
            lines.append(
                r"IF EXIST C:\PICOMEM\PMINIT.EXE C:\PICOMEM\PMINIT.EXE /SB 1"
            )
        else:
            lines.append(
                r"IF EXIST C:\PICOMEM\PMINIT.EXE C:\PICOMEM\PMINIT.EXE /GUS 1"
            )
        return lines
    # mister + picomem (+ default): PMINIT when present
    if mode == "sb":
        return [r"IF EXIST C:\PICOMEM\PMINIT.EXE C:\PICOMEM\PMINIT.EXE /SB 1"]
    return [r"IF EXIST C:\PICOMEM\PMINIT.EXE C:\PICOMEM\PMINIT.EXE /GUS 1"]


def hw_boot_block(target: PackTarget | str) -> str:
    """Optional AUTOEXEC fragment for CD stack (picogus/picoide)."""
    target = normalize_target(str(target))
    lines = [_HW_BEGIN, f"REM pack target: {target}"]
    if target in ("picogus", "picoide"):
        lines.extend(
            [
                "REM PicoGUS/PicoIDE: MKE CD driver should be in CONFIG.SYS",
                "REM MSCDEX after drivers; images on FAT32 USB root",
                r"IF EXIST C:\DOS\MSCDEX.EXE C:\DOS\MSCDEX.EXE /D:MSCD000",
                r"IF EXIST C:\FDOS\BIN\MSCDEX.EXE C:\FDOS\BIN\MSCDEX.EXE /D:MSCD000",
                r"REM CD helpers: CALL C:\DRIVERS\HW\PGUSCD.BAT list",
            ]
        )
    elif target == "picomem":
        lines.extend(
            [
                "REM PicoMEM: attach pack VHD/IMG via card BIOS; CD is future",
                r"REM optional: C:\PICOMEM\PMDFS.EXE S-D U-E",
                r"REM CD stub: CALL C:\DRIVERS\HW\PMCD.BAT help",
            ]
        )
    else:
        lines.extend(
            [
                "REM MiSTer ao486: external cd/ + CALL imgtry (see DRIVERS\\HW\\IMGTRY.BAT)",
            ]
        )
    lines.append(_HW_END)
    return "\n".join(lines)


def config_sys_extra_lines(target: PackTarget | str) -> list[str]:
    """Extra DEVICE= lines for CONFIG.SYS (picogus CDMKE)."""
    target = normalize_target(str(target))
    if target in ("picogus", "picoide"):
        return [
            "REM --- mister-pack native CD (PicoGUS/PicoIDE) ---",
            r"DEVICE=C:\DRIVERS\PICOGUS\CDMKE.SYS /P:250 /Q",
        ]
    return []


def _strip_legacy_audio_lines(text: str) -> str:
    """Remove older non-marker audio lines we used to inject."""
    patterns = [
        r"(?im)^\s*REM Sound Blaster.*\n",
        r"(?im)^\s*REM Gravis UltraSound.*\n",
        r"(?im)^\s*REM MS-DOS 6\.22 friendly:.*UltraSound.*\n",
        r"(?im)^\s*IF EXIST C:\\DRIVERS\\SBCTL\.EXE.*\n",
        r"(?im)^\s*SET BLASTER\s*=.*\n",
        r"(?im)^\s*SET ULTRASND\s*=.*\n",
        r"(?im)^\s*SET ULTRADIR\s*=.*\n",
        r"(?im)^\s*IF EXIST C:\\PICOMEM\\PMINIT\.EXE C:\\PICOMEM\\PMINIT\.EXE\s+/GUS\s+1\s*\n",
        r"(?im)^\s*IF EXIST C:\\PICOMEM\\PMINIT\.EXE C:\\PICOMEM\\PMINIT\.EXE\s+/SB\s+1\s*\n",
        r"(?im)^\s*C:\\PICOMEM\\PMINIT(\.EXE)?\s+/GUS\s+1\s*\n",
        r"(?im)^\s*C:\\PICOMEM\\PMINIT(\.EXE)?\s+/SB\s+1\s*\n",
        r"(?im)^\s*IF EXIST C:\\DRIVERS\\PICOGUS\\PGUSINIT\.EXE.*\n",
    ]
    for pat in patterns:
        text = re.sub(pat, "", text)
    return text


def apply_audio_mode(
    text: str,
    mode: AudioMode | str,
    target: PackTarget | str = "mister",
) -> str:
    """Rewrite AUTOEXEC (or autorun) text for the selected audio mode + target."""
    mode = normalize_audio_mode(str(mode))
    target = normalize_target(str(target))
    nl = "\r\n" if "\r\n" in text else "\n"
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    block = audio_block(mode, target)
    hw = hw_boot_block(target)

    if _BEGIN in text and _END in text:
        text = re.sub(
            re.escape(_BEGIN) + r".*?" + re.escape(_END),
            lambda _m: block,
            text,
            count=1,
            flags=re.S,
        )
    else:
        text = _strip_legacy_audio_lines(text)
        m = re.search(r"(?im)^\s*@?ECHO\s+OFF\s*$", text)
        if m:
            insert_at = m.end()
            text = text[:insert_at] + "\n" + block + text[insert_at:]
        else:
            text = block + "\n" + text

    if _HW_BEGIN in text and _HW_END in text:
        text = re.sub(
            re.escape(_HW_BEGIN) + r".*?" + re.escape(_HW_END),
            lambda _m: hw,
            text,
            count=1,
            flags=re.S,
        )
    else:
        # Insert hardware block after audio block
        if _END in text:
            idx = text.index(_END) + len(_END)
            text = text[:idx] + "\n" + hw + text[idx:]
        else:
            text = hw + "\n" + text

    # PATH: always include PICOMEM + PICOGUS tools; ULTRASND for gus
    if re.search(r"(?im)^\s*PATH\s*=", text):

        def path_fix(m: re.Match) -> str:
            p = m.group(0)
            up = p.upper()
            need = [r"C:\PICOMEM", r"C:\DRIVERS\PICOGUS", r"C:\DRIVERS\HW"]
            if mode == "gus":
                need.insert(0, r"C:\ULTRASND")
            for token in need:
                if token.upper() not in up:
                    p = p.rstrip() + ";" + token
                    up = p.upper()
            if mode == "sb":
                p = re.sub(r";?\s*C:\\ULTRASND\s*", "", p, flags=re.I)
                p = re.sub(r"=\s*;", "=", p)
            return p

        text = re.sub(r"(?im)^\s*PATH\s*=.*$", path_fix, text, count=1)

    return text.replace("\n", nl)


def apply_config_sys_target(text: str, target: PackTarget | str) -> str:
    """Inject or refresh native DEVICE lines in CONFIG.SYS."""
    target = normalize_target(str(target))
    nl = "\r\n" if "\r\n" in text else "\n"
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # strip previous mister-pack CD device block
    text = re.sub(
        r"(?im)^\s*REM --- mister-pack native CD.*\n(?:^\s*DEVICE=.*CDMKE.*\n)?",
        "",
        text,
    )
    extras = config_sys_extra_lines(target)
    if extras:
        # Insert after first DEVICE= line or at end
        m = re.search(r"(?im)^\s*DEVICE\s*=.*$", text)
        if m:
            insert_at = m.end()
            text = text[:insert_at] + "\n" + "\n".join(extras) + text[insert_at:]
        else:
            text = text.rstrip() + "\n" + "\n".join(extras) + "\n"
    return text.replace("\n", nl)


def audio_block_bytes(mode: AudioMode | str, target: PackTarget | str = "mister") -> bytes:
    """CRLF bytes for embedding (not a full AUTOEXEC)."""
    body = apply_audio_mode("@ECHO OFF\n", mode, target)
    text = body.replace("\r\n", "\n")
    if _BEGIN in text and _END in text:
        chunk = text[text.index(_BEGIN) : text.index(_END) + len(_END)]
    else:
        chunk = audio_block(normalize_audio_mode(str(mode)), normalize_target(str(target)))
    return (chunk.replace("\n", "\r\n") + "\r\n").encode("ascii")
