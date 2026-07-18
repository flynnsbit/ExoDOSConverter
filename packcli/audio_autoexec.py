"""Sound Blaster vs Gravis UltraSound AUTOEXEC.BAT audio blocks.

User/recipe config selects ``sb`` or ``gus``. Values match production defaults:

- SB:  ``SET BLASTER=A220 I7 D1 H5 P330 T6`` then ``PMINIT /SB 1``
- GUS: ``SET ULTRASND=240,1,1,5,5`` + ``ULTRADIR`` then ``PMINIT /GUS 1``
"""

from __future__ import annotations

import re
from typing import Literal

AudioMode = Literal["sb", "gus"]

BLASTER_VALUE = "A220 I7 D1 H5 P330 T6"
ULTRASND_VALUE = "240,1,1,5,5"

# Marker region rewritten wholesale so mode switches stay clean.
_BEGIN = "REM --- mister-pack audio begin ---"
_END = "REM --- mister-pack audio end ---"


def normalize_audio_mode(value: str | None, default: str = "sb") -> AudioMode:
    v = (value or default or "sb").strip().lower()
    if v in ("gus", "gravis", "ultrasound", "ultrasnd"):
        return "gus"
    if v in ("sb", "soundblaster", "sound_blaster", "blaster"):
        return "sb"
    return "sb" if default != "gus" else "gus"


def audio_block(mode: AudioMode) -> str:
    """CRLF-free LF block (caller converts to CRLF for DOS)."""
    lines = [_BEGIN]
    if mode == "sb":
        lines.extend(
            [
                "REM Sound Blaster 16 defaults",
                r"IF EXIST C:\DRIVERS\SBCTL.EXE LOADHIGH C:\DRIVERS\SBCTL.EXE I7 T6",
                f"SET BLASTER={BLASTER_VALUE}",
                r"IF EXIST C:\PICOMEM\PMINIT.EXE C:\PICOMEM\PMINIT.EXE /SB 1",
            ]
        )
    else:
        lines.extend(
            [
                "REM Sound Blaster env (many titles still read BLASTER)",
                r"IF EXIST C:\DRIVERS\SBCTL.EXE LOADHIGH C:\DRIVERS\SBCTL.EXE I7 T6",
                f"SET BLASTER={BLASTER_VALUE}",
                "REM Gravis UltraSound / PicoGUS (DMA 1,1 + IRQ 5,5)",
                f"SET ULTRASND={ULTRASND_VALUE}",
                r"SET ULTRADIR=C:\ULTRASND",
                r"IF EXIST C:\PICOMEM\PMINIT.EXE C:\PICOMEM\PMINIT.EXE /GUS 1",
            ]
        )
    lines.append(_END)
    return "\n".join(lines)


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
    ]
    for pat in patterns:
        text = re.sub(pat, "", text)
    return text


def apply_audio_mode(text: str, mode: AudioMode | str) -> str:
    """Rewrite AUTOEXEC (or autorun) text for the selected audio mode."""
    mode = normalize_audio_mode(str(mode))
    nl = "\r\n" if "\r\n" in text else "\n"
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    block = audio_block(mode)

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
        # Insert after @ECHO OFF if present, else at top
        m = re.search(r"(?im)^\s*@?ECHO\s+OFF\s*$", text)
        if m:
            insert_at = m.end()
            text = text[:insert_at] + "\n" + block + text[insert_at:]
        else:
            text = block + "\n" + text

    # PATH: always include PICOMEM; ULTRASND only for gus
    if re.search(r"(?im)^\s*PATH\s*=", text):

        def path_fix(m: re.Match) -> str:
            p = m.group(0)
            up = p.upper()
            # drop then re-add for clean mode switch
            parts = [x for x in re.split(r"[;=]", p, maxsplit=1)]
            # simpler: ensure required tokens
            need = [r"C:\PICOMEM"]
            if mode == "gus":
                need.insert(0, r"C:\ULTRASND")
            for token in need:
                if token.upper() not in up:
                    p = p.rstrip() + ";" + token
                    up = p.upper()
            if mode == "sb":
                # remove ULTRASND from path if present
                p = re.sub(r";?\s*C:\\ULTRASND\s*", "", p, flags=re.I)
                p = re.sub(r"=\s*;", "=", p)
            return p

        text = re.sub(r"(?im)^\s*PATH\s*=.*$", path_fix, text, count=1)

    return text.replace("\n", nl)


def audio_block_bytes(mode: AudioMode | str) -> bytes:
    """CRLF bytes for embedding (not a full AUTOEXEC)."""
    body = apply_audio_mode("@ECHO OFF\n", mode)
    # return only the marker block lines as CRLF
    text = body.replace("\r\n", "\n")
    if _BEGIN in text and _END in text:
        chunk = text[text.index(_BEGIN) : text.index(_END) + len(_END)]
    else:
        chunk = audio_block(normalize_audio_mode(str(mode)))
    return (chunk.replace("\n", "\r\n") + "\r\n").encode("ascii")
