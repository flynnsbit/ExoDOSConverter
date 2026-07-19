"""Render CONFIG.SYS and AUTOEXEC.BAT for a DOS capability + pack options."""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

from packcli.audio_autoexec import apply_audio_mode, apply_config_sys_target
from packcli.boot_rules.capabilities import DosCapabilities, get_capabilities


def _crlf(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        text += "\n"
    return text.replace("\n", "\r\n")


def _device(
    cap: DosCapabilities,
    path: str,
    *,
    force_low: bool = False,
    args: str = "",
) -> str:
    """DEVICE= or DEVICEHIGH= depending on capability."""
    line = path if not args else f"{path} {args}".rstrip()
    if cap.devicehigh and not force_low:
        return f"DEVICEHIGH={line}"
    return f"DEVICE={line}"


def _use_qemm(cap: DosCapabilities, include_qemm: bool) -> bool:
    if not include_qemm:
        return False
    if cap.ems_provider == "qemm_only":
        return True
    if cap.qemm_for_high and not (cap.devicehigh and cap.dos_umb):
        return True
    return False


def render_config_sys(
    boot_mode: str,
    *,
    include_qemm: bool = True,
    target: str = "mister",
) -> str:
    """Generate CONFIG.SYS text (LF newlines; caller may CRLF)."""
    cap = get_capabilities(boot_mode)
    use_qemm = _use_qemm(cap, include_qemm)
    lines: List[str] = []

    if cap.config_menu and not use_qemm:
        lines.extend(_config_menu_ms6(cap))
    elif use_qemm:
        lines.extend(_config_qemm_only(cap))
    else:
        lines.extend(_config_single_profile(cap))

    # Common settings
    if not any(ln.startswith("[common]") or ln.startswith("[COMMON]") for ln in lines):
        # single-profile files put common at end without section
        pass

    text = "\n".join(lines) + "\n"
    # Hardware target DEVICE lines (e.g. CDMKE) when applicable
    text = apply_config_sys_target(text.replace("\n", "\r\n"), target)
    text = text.replace("\r\n", "\n")
    return text


def _common_tail() -> List[str]:
    return [
        "FILES=60",
        "BUFFERS=30",
        "FCBS=4,0",
        "STACKS=9,256",
        "LASTDRIVE=Z",
        "NUMLOCK=ON",
    ]


def _himem_line(cap: DosCapabilities) -> Optional[str]:
    if not cap.himem or not cap.himem_path:
        return None
    # FreeDOS HIMEMX takes no /TESTMEM
    if "HIMEMX" in cap.himem_path.upper():
        return f"DEVICE={cap.himem_path}"
    return f"DEVICE={cap.himem_path} /TESTMEM:OFF"


def _ems_line(cap: DosCapabilities) -> Optional[str]:
    if cap.ems_provider in ("none", "qemm_only") or not cap.emm_path:
        return None
    if cap.ems_provider == "jemm386":
        # JEMM386: provide UMBs; MAX= for EMS pages optional
        return f"DEVICE={cap.emm_path}"
    # MS EMM386: AUTO RAM → EMS + UMBs (max conventional after DOS=HIGH,UMB)
    return f"DEVICE={cap.emm_path} AUTO RAM"


def _dos_line(cap: DosCapabilities) -> Optional[str]:
    if cap.dos_high and cap.dos_umb:
        return "DOS=HIGH,UMB"
    if cap.dos_high:
        return "DOS=HIGH"
    return None


def _xcdrom_device(cap: DosCapabilities, high: bool) -> Optional[str]:
    if not cap.xcdrom:
        return None
    path = r"C:\DRIVERS\XCDROM.SYS /D:IDE-CD"
    if high and cap.devicehigh:
        return f"DEVICEHIGH={path}"
    return f"DEVICE={path}"


def _setver_device(cap: DosCapabilities, high: bool) -> Optional[str]:
    if not cap.setver or not cap.setver_path:
        return None
    if high and cap.devicehigh:
        return f"DEVICEHIGH={cap.setver_path}"
    return f"DEVICE={cap.setver_path}"


def _config_single_profile(cap: DosCapabilities) -> List[str]:
    """One CONFIG.SYS profile maximizing conventional memory."""
    lines: List[str] = [
        f"REM pack DOS: {cap.label} ({cap.boot_mode})",
    ]
    himem = _himem_line(cap)
    if himem:
        lines.append(himem)
    ems = _ems_line(cap)
    if ems:
        lines.append(ems)
    dos = _dos_line(cap)
    if dos:
        lines.append(dos)
    high = bool(cap.devicehigh and cap.dos_umb)
    sv = _setver_device(cap, high)
    if sv:
        lines.append(sv)
    xd = _xcdrom_device(cap, high)
    if xd:
        lines.append(xd)
    # SHELL last among devices is fine; MS prefers SHELL after devices
    lines.append(f"SHELL={cap.command_com} /E:1024 /P")
    lines.extend(_common_tail())
    return lines


def _config_menu_ms6(cap: DosCapabilities) -> List[str]:
    """MS-DOS 6+ multi-config: EMM386 default; EXTENDED/CLEAN/QEMM options."""
    lines: List[str] = [
        f"REM pack DOS: {cap.label} ({cap.boot_mode})",
        "[MENU]",
        "MENUDEFAULT=EMM386,2",
        "MENUITEM=EMM386,EMM386: HIMEM + EMM386 AUTO RAM (default, max free RAM).",
        "MENUITEM=EXTENDED,EXTENDED: HIMEM only + CD (no EMS).",
        "MENUITEM=CLEAN,CLEAN: CD only, boot to prompt.",
    ]
    # QEMM optional profile when pack stages QEMM
    lines.append("MENUITEM=QEMM,QEMM386: When a game requires QEMM.")
    lines.append("MENUCOLOR=15,3")
    lines.append("")

    # CLEAN — minimal conventional use of devices
    lines.extend(
        [
            "[CLEAN]",
            "SET MEMMGR=CLEAN",
        ]
    )
    xd = _xcdrom_device(cap, high=False)
    if xd:
        lines.append(xd.replace("DEVICEHIGH=", "DEVICE="))
    lines.append("")

    # EXTENDED — HIMEM + UMB without EMS page frame pressure on some games
    lines.extend(["[EXTENDED]", "SET MEMMGR=EXTENDED"])
    himem = _himem_line(cap)
    if himem:
        lines.append(himem)
    if cap.dos_high and cap.dos_umb:
        # Without EMM386, UMB may be limited; still request HIGH
        lines.append("DOS=HIGH")
    elif cap.dos_high:
        lines.append("DOS=HIGH")
    sv = _setver_device(cap, high=False)
    if sv:
        lines.append(sv.replace("DEVICEHIGH=", "DEVICE="))
    xd = _xcdrom_device(cap, high=False)
    if xd:
        lines.append(xd.replace("DEVICEHIGH=", "DEVICE="))
    lines.append("")

    # EMM386 — maximum free base memory path
    lines.extend(["[EMM386]", "SET MEMMGR=EMM386"])
    if himem:
        lines.append(himem)
    ems = _ems_line(cap)
    if ems:
        lines.append(ems)
    dos = _dos_line(cap)
    if dos:
        lines.append(dos)
    high = bool(cap.devicehigh and cap.dos_umb)
    sv = _setver_device(cap, high)
    if sv:
        lines.append(sv)
    xd = _xcdrom_device(cap, high)
    if xd:
        lines.append(xd)
    lines.append("")

    # QEMM profile
    lines.extend(_qemm_section())
    lines.append("")
    lines.append("[common]")
    lines.extend(_common_tail())
    return lines


def _qemm_section() -> List[str]:
    return [
        "[QEMM]",
        "SET MEMMGR=QEMM386",
        r"DEVICE=C:\QEMM\DOSDATA.SYS",
        r"SET LOADHIDATA=C:\QEMM\LOADHI.RF",
        r"DEVICE=C:\QEMM\QEMM386.SYS RAM",
        r"DEVICE=C:\QEMM\DOS-UP.SYS @C:\QEMM\DOS7-UP.DAT",
        r"DEVICE=C:\QEMM\LOADHI.SYS /RF C:\QEMM\QDPMI.SYS SWAPFILE=DPMI.SWP SWAPSIZE=1024",
        r"DEVICE=C:\QEMM\LOADHI.SYS /RF C:\DOS\SETVER.EXE",
        r"SHELL=C:\QEMM\LOADHI.COM /RF COMMAND.COM /P /E:640",
        "DOS=HIGH,UMB",
        r"DEVICE=C:\QEMM\LOADHI.SYS /RF C:\DRIVERS\XCDROM.SYS /D:IDE-CD",
    ]


def _config_qemm_only(cap: DosCapabilities) -> List[str]:
    lines = [
        f"REM pack DOS: {cap.label} ({cap.boot_mode}) — QEMM for high memory",
    ]
    lines.extend(_qemm_section())
    # Drop [QEMM] header for single-profile
    lines = [ln for ln in lines if ln != "[QEMM]"]
    lines.extend(_common_tail())
    return lines


def render_autoexec(
    boot_mode: str,
    *,
    audio: str = "sb",
    target: str = "mister",
    include_qemm: bool = True,
    launcher: str = "mymenu",
) -> str:
    """Generate AUTOEXEC.BAT (LF); audio/target applied via packcli helpers."""
    cap = get_capabilities(boot_mode)
    use_qemm = _use_qemm(cap, include_qemm)
    lh = "LOADHIGH " if cap.loadhigh else ""
    lines: List[str] = [
        "@ECHO OFF",
        f"REM pack DOS: {cap.label} ({cap.boot_mode})",
    ]

    # Audio markers — filled by apply_audio_mode
    lines.extend(
        [
            "REM --- mister-pack audio begin ---",
            "REM (filled at build)",
            "REM --- mister-pack audio end ---",
        ]
    )

    lines.append(r"SET TEMP=C:\TMP")
    lines.append(r"SET TMP=C:\TMP")
    path = ";".join(cap.path_dirs)
    lines.append(f"PATH={path}")
    lines.append("PROMPT $P$G")
    lines.append(r"SET DOS32A=C:\DRIVERS")

    if cap.autoexec_config_goto and not use_qemm:
        lines.append("GOTO %CONFIG%")
        lines.extend(_autoexec_config_branches(cap, lh))
    else:
        lines.append("GOTO COMMON")

    lines.extend(_autoexec_common(cap, lh, launcher=launcher, use_qemm=use_qemm))
    text = "\n".join(lines) + "\n"
    # Apply audio + hw markers
    text = apply_audio_mode(text.replace("\n", "\r\n"), audio, target=target)
    return text.replace("\r\n", "\n")


def _autoexec_config_branches(cap: DosCapabilities, lh: str) -> List[str]:
    lines: List[str] = [
        "",
        ":QEMM",
        r"IF EXIST C:\DRIVERS\SHSUCDX.COM C:\QEMM\LOADHI /RF C:\DRIVERS\SHSUCDX.COM /D:IDE-CD /L:D /V /C",
        r"IF EXIST C:\DRIVERS\CUTEPACK\CTMOUSE.EXE C:\QEMM\LOADHI /RF C:\DRIVERS\CUTEPACK\CTMOUSE.EXE /O",
        "GOTO COMMON",
        "",
        ":EXTENDED",
        "CLS",
        "GOTO COMMON",
        "",
        ":EMM386",
        "CLS",
        "GOTO COMMON",
        "",
        ":CLEAN",
        r"IF EXIST C:\DRIVERS\SHSUCDX.COM C:\DRIVERS\SHSUCDX.COM /D:IDE-CD /L:D /V /C",
        r"IF EXIST C:\DRIVERS\CUTEPACK\CTMOUSE.EXE C:\DRIVERS\CUTEPACK\CTMOUSE.EXE /O",
        "@ECHO.",
        "@ECHO CLEAN profile: MyMenu not auto-loaded.",
        "GOTO END",
        "",
    ]
    return lines


def _autoexec_common(
    cap: DosCapabilities,
    lh: str,
    *,
    launcher: str,
    use_qemm: bool,
) -> List[str]:
    lines: List[str] = [
        ":COMMON",
        "CLS",
        r"REM C:=HDD, D:=CD via SHSUCDX when present",
    ]
    if cap.shsucdx:
        if use_qemm:
            lines.append(
                r"IF EXIST C:\DRIVERS\SHSUCDX.COM C:\QEMM\LOADHI /RF C:\DRIVERS\SHSUCDX.COM /D:IDE-CD /L:D /V /C"
            )
        else:
            lines.append(
                f"IF EXIST C:\\DRIVERS\\SHSUCDX.COM {lh}C:\\DRIVERS\\SHSUCDX.COM /D:IDE-CD /L:D /V /C".replace(
                    "  ", " "
                )
            )
    # mouse
    if use_qemm:
        lines.append(
            r"IF EXIST C:\DRIVERS\CUTEPACK\CTMOUSE.EXE C:\QEMM\LOADHI /RF C:\DRIVERS\CUTEPACK\CTMOUSE.EXE /O"
        )
    else:
        lines.append(
            f"IF EXIST C:\\DRIVERS\\CUTEPACK\\CTMOUSE.EXE {lh}C:\\DRIVERS\\CUTEPACK\\CTMOUSE.EXE /O".replace(
                "  ", " "
            )
        )
    if cap.lfn_doslfnm:
        lines.append(
            f"IF EXIST C:\\MYMENU\\UTILS\\DOSLFNM.COM {lh}C:\\MYMENU\\UTILS\\DOSLFNM.COM".replace(
                "  ", " "
            )
        )
    lines.append("CLS")

    if launcher and launcher.lower() not in ("none", "false", "0"):
        lines.extend(
            [
                r"REM --- MyMenu (exit returns to DOS prompt; no remenu loop) ---",
                r"IF EXIST C:\RUNMENU.BAT CALL C:\RUNMENU.BAT",
                r"IF EXIST C:\MYMENU\MENU.BAT CALL C:\MYMENU\MENU.BAT",
                r"IF EXIST C:\MYMENU\MYMENU.EXE C:\MYMENU\MYMENU.EXE C:\GAMES",
            ]
        )
    lines.append("GOTO END")
    lines.append("")
    lines.append(":END")
    return lines


def render_boot_files(
    boot_mode: str,
    *,
    audio: str = "sb",
    target: str = "mister",
    include_qemm: bool = True,
    launcher: str = "mymenu",
) -> Tuple[bytes, bytes]:
    """Return (config_sys_bytes, autoexec_bat_bytes) as CRLF ASCII."""
    cfg = _crlf(
        render_config_sys(
            boot_mode, include_qemm=include_qemm, target=target
        )
    )
    aut = _crlf(
        render_autoexec(
            boot_mode,
            audio=audio,
            target=target,
            include_qemm=include_qemm,
            launcher=launcher,
        )
    )
    return cfg.encode("ascii", errors="replace"), aut.encode(
        "ascii", errors="replace"
    )
