"""Per-DOS capability tables (dosforge boot-mode names).

Feature facts (MS-DOS line, PC-DOS peers, FreeDOS, DR-DOS):

- Multi-config ``[MENU]`` / ``MENUITEM`` / ``%CONFIG%``: MS-DOS **6.0+**
  (and PC-DOS 6+/7+ equivalents). Not on 3.x/5.x or FreeDOS FDCONFIG the same way.
- ``HIMEM.SYS`` + ``DOS=HIGH``: MS-DOS **5.0+** (4.0 had early XMS; we treat 5+).
- ``EMM386`` + UMBs + ``DEVICEHIGH`` / ``LOADHIGH``: MS-DOS **5.0+** with EMM386.
- FreeDOS: ``HIMEMX`` / ``JEMM386`` (or HIMEM/EMM386 if present), LOADHIGH/DEVICEHIGH.
- DR-DOS 6/7: ``HIDOS.SYS``, own EMM386, HILOAD / DEVICEHIGH variants — use QEMM
  or DR high-load when staged.
- MS-DOS 3.3 / Compaq 3.31 / PC-DOS 3: **no** DEVICEHIGH/LOADHIGH/EMM386 menu;
  optional **QEMM** for high loading when ``include_qemm``.
- FAT32: FreeDOS, MS-DOS 7.1 (Win95 OSR2+), PC-DOS 7.1 — not 6.22.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Sequence, Tuple

# Soft cap used by dosforgevhd for FAT16 packs (~1.9 GiB)
FAT16_SOFT_CAP_BYTES = int(1.9 * 1024 * 1024 * 1024)

ALL_BOOT_MODES: Tuple[str, ...] = (
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

FAT32_MODES = frozenset({"freedos", "msdos71", "pcdos71", "pcdos7", "pcdos2000"})
FAT16_MODES = frozenset(
    {
        "msdos622",
        "msdos6",
        "msdos5",
        "msdos33",
        "msdos331",
        "ibm8088",
        "compaq331",
        "compaq2",
        "compaq3",
        "pcdos3",
        "pcdos5",
        "drdos6",
        "drdos7",
        "4dos",
        "none",
    }
)


@dataclass(frozen=True)
class DosCapabilities:
    boot_mode: str
    # Memory / config
    config_menu: bool
    himem: bool
    himem_path: str
    ems_provider: str  # none | emm386 | jemm386 | qemm_only
    emm_path: str
    devicehigh: bool
    loadhigh: bool
    dos_high: bool
    dos_umb: bool
    setver: bool
    setver_path: str
    # When native UMB unavailable but QEMM can provide high load
    qemm_for_high: bool
    # Paths
    command_com: str
    path_dirs: Tuple[str, ...]
    # CD / extras
    xcdrom: bool
    shsucdx: bool
    lfn_doslfnm: bool
    autoexec_config_goto: bool
    # FAT preference when auto-format
    prefer_fat32: bool
    label: str


def _ms5_plus(
    mode: str,
    *,
    menu: bool,
    label: str,
    prefer_fat32: bool = False,
    himem: str = r"C:\DOS\HIMEM.SYS",
    emm: str = r"C:\DOS\EMM386.EXE",
    setver: str = r"C:\DOS\SETVER.EXE",
    command: str = r"C:\DOS\COMMAND.COM",
    path_extra: Sequence[str] = (),
) -> DosCapabilities:
    path = (
        "C:\\",
        "C:\\DOS",
        "C:\\DRIVERS",
        "C:\\DRIVERS\\SHCD",
        "C:\\ULTRASND",
        "C:\\PICOMEM",
        "C:\\MYMENU",
        "C:\\MYMENU\\UTILS",
        "C:\\UTILS",
    ) + tuple(path_extra)
    return DosCapabilities(
        boot_mode=mode,
        config_menu=menu,
        himem=True,
        himem_path=himem,
        ems_provider="emm386",
        emm_path=emm,
        devicehigh=True,
        loadhigh=True,
        dos_high=True,
        dos_umb=True,
        setver=True,
        setver_path=setver,
        qemm_for_high=False,
        command_com=command,
        path_dirs=path,
        xcdrom=True,
        shsucdx=True,
        lfn_doslfnm=True,
        autoexec_config_goto=menu,
        prefer_fat32=prefer_fat32,
        label=label,
    )


def _early_dos(
    mode: str,
    *,
    label: str,
    command: str = r"C:\COMMAND.COM",
) -> DosCapabilities:
    """DOS 3.x / early: no UMB/DEVICEHIGH; QEMM optional for high load."""
    return DosCapabilities(
        boot_mode=mode,
        config_menu=False,
        himem=False,
        himem_path="",
        ems_provider="none",
        emm_path="",
        devicehigh=False,
        loadhigh=False,
        dos_high=False,
        dos_umb=False,
        setver=False,
        setver_path="",
        qemm_for_high=True,
        command_com=command,
        path_dirs=(
            "C:\\",
            "C:\\DOS",
            "C:\\DRIVERS",
            "C:\\PICOMEM",
            "C:\\MYMENU",
            "C:\\MYMENU\\UTILS",
            "C:\\UTILS",
        ),
        xcdrom=True,
        shsucdx=True,
        lfn_doslfnm=False,
        autoexec_config_goto=False,
        prefer_fat32=False,
        label=label,
    )


def _build_table() -> Dict[str, DosCapabilities]:
    t: Dict[str, DosCapabilities] = {}

    t["msdos622"] = _ms5_plus(
        "msdos622", menu=True, label="MS-DOS 6.22"
    )
    t["msdos6"] = _ms5_plus("msdos6", menu=True, label="MS-DOS 6.0")
    t["msdos5"] = _ms5_plus(
        "msdos5",
        menu=False,  # multi-config menu is 6.0+
        label="MS-DOS 5.0",
    )
    t["msdos71"] = _ms5_plus(
        "msdos71",
        menu=True,
        label="MS-DOS 7.1 (Win9x)",
        prefer_fat32=True,
        # Win9x DOS often still has C:\DOS or C:\WINDOWS\COMMAND — pack stages DOS/
        himem=r"C:\DOS\HIMEM.SYS",
        emm=r"C:\DOS\EMM386.EXE",
    )
    t["pcdos7"] = _ms5_plus(
        "pcdos7", menu=True, label="PC-DOS 7", prefer_fat32=False
    )
    t["pcdos2000"] = _ms5_plus(
        "pcdos2000", menu=True, label="PC-DOS 2000", prefer_fat32=False
    )
    t["pcdos71"] = _ms5_plus(
        "pcdos71", menu=True, label="PC-DOS 7.1", prefer_fat32=True
    )
    t["pcdos5"] = _ms5_plus(
        "pcdos5", menu=False, label="PC-DOS 5"
    )

    # FreeDOS — JEMM/HIMEMX when present under DRIVERS or FDOS
    t["freedos"] = DosCapabilities(
        boot_mode="freedos",
        config_menu=False,
        himem=True,
        himem_path=r"C:\FDOS\BIN\HIMEMX.EXE",
        ems_provider="jemm386",
        emm_path=r"C:\DRIVERS\JEMM386\JEMM386.EXE",
        devicehigh=True,
        loadhigh=True,
        dos_high=True,
        dos_umb=True,
        setver=False,
        setver_path="",
        qemm_for_high=False,
        command_com=r"C:\FDOS\BIN\COMMAND.COM",
        path_dirs=(
            "C:\\",
            "C:\\FDOS",
            "C:\\FDOS\\BIN",
            "C:\\DOS",
            "C:\\DRIVERS",
            "C:\\DRIVERS\\SHCD",
            "C:\\ULTRASND",
            "C:\\PICOMEM",
            "C:\\MYMENU",
            "C:\\MYMENU\\UTILS",
            "C:\\UTILS",
        ),
        xcdrom=True,
        shsucdx=True,
        lfn_doslfnm=True,
        autoexec_config_goto=False,
        prefer_fat32=True,
        label="FreeDOS",
    )

    # DR-DOS — prefer QEMM for reliable high load in packs; native HIDOS is
    # install-layout dependent.
    for mode, label in (("drdos6", "DR-DOS 6"), ("drdos7", "DR-DOS 7")):
        t[mode] = DosCapabilities(
            boot_mode=mode,
            config_menu=False,
            himem=False,
            himem_path="",
            ems_provider="qemm_only",
            emm_path="",
            devicehigh=False,
            loadhigh=False,
            dos_high=False,
            dos_umb=False,
            setver=False,
            setver_path="",
            qemm_for_high=True,
            command_com=r"C:\COMMAND.COM",
            path_dirs=(
                "C:\\",
                "C:\\DOS",
                "C:\\DRIVERS",
                "C:\\PICOMEM",
                "C:\\MYMENU",
                "C:\\MYMENU\\UTILS",
                "C:\\UTILS",
            ),
            xcdrom=True,
            shsucdx=True,
            lfn_doslfnm=False,
            autoexec_config_goto=False,
            prefer_fat32=False,
            label=label,
        )

    # Early DOS / XT-class
    for mode, label in (
        ("msdos33", "MS-DOS 3.3"),
        ("msdos331", "MS-DOS 3.31"),
        ("ibm8088", "IBM 8088 DOS"),
        ("compaq331", "Compaq DOS 3.31"),
        ("compaq2", "Compaq DOS 2.x"),
        ("compaq3", "Compaq DOS 3.x"),
        ("pcdos3", "PC-DOS 3"),
    ):
        t[mode] = _early_dos(mode, label=label)

    # 4DOS is a shell; host DOS still required — treat like 6.22 capabilities
    # for config generation; shell path may be 4DOS.COM when staged.
    t["4dos"] = _ms5_plus(
        "4dos",
        menu=True,
        label="4DOS (host DOS)",
        command=r"C:\4DOS\4DOS.COM",
    )

    t["none"] = DosCapabilities(
        boot_mode="none",
        config_menu=False,
        himem=False,
        himem_path="",
        ems_provider="none",
        emm_path="",
        devicehigh=False,
        loadhigh=False,
        dos_high=False,
        dos_umb=False,
        setver=False,
        setver_path="",
        qemm_for_high=True,
        command_com=r"C:\COMMAND.COM",
        path_dirs=("C:\\", "C:\\DRIVERS", "C:\\MYMENU", "C:\\UTILS"),
        xcdrom=True,
        shsucdx=True,
        lfn_doslfnm=False,
        autoexec_config_goto=False,
        prefer_fat32=False,
        label="No DOS install (payload only)",
    )

    return t


_TABLE = _build_table()


def normalize_boot_mode(value: Optional[str], default: str = "auto") -> str:
    v = (value or default or "auto").strip().lower()
    aliases = {
        "dos622": "msdos622",
        "msdos6.22": "msdos622",
        "6.22": "msdos622",
        "dos71": "msdos71",
        "msdos7": "msdos71",
        "win98": "msdos71",
        "win95": "msdos71",
        "fd": "freedos",
        "free": "freedos",
    }
    v = aliases.get(v, v)
    if v == "auto" or v in _TABLE:
        return v
    return default if default in _TABLE or default == "auto" else "auto"


def get_capabilities(boot_mode: str) -> DosCapabilities:
    mode = normalize_boot_mode(boot_mode, "msdos622")
    if mode == "auto":
        mode = "msdos622"
    return _TABLE[mode]


def resolve_boot_and_fat(
    requested: str,
    *,
    size_bytes: int,
    fat16_cap: int = FAT16_SOFT_CAP_BYTES,
) -> Tuple[str, str]:
    """Return (boot_mode, fat_format) for dosforge create.

    ``auto`` → msdos622/fat16 under cap, else msdos71/fat32.
    Explicit FAT16-only modes raise if over cap (caller may catch).
    """
    mode = normalize_boot_mode(requested, "auto")
    if mode == "auto":
        if size_bytes > fat16_cap:
            return "msdos71", "fat32"
        return "msdos622", "fat16"

    cap = get_capabilities(mode)
    if mode in FAT32_MODES or cap.prefer_fat32:
        # Prefer FAT32 for large volumes; small images may still use FAT16
        if size_bytes > 512 * 1024 * 1024:
            return mode, "fat32"
        return mode, "fat16" if mode not in ("freedos",) else "fat32"

    if size_bytes > fat16_cap:
        raise ValueError(
            "boot-mode %s is FAT16-only and cannot hold ~%.1f GiB; "
            "use auto, msdos71, pcdos71, or freedos"
            % (mode, size_bytes / (1024**3))
        )
    return mode, "fat16"
