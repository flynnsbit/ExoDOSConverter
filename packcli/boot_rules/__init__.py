"""DOS-version-aware CONFIG.SYS / AUTOEXEC.BAT generation for packs.

dosforge installs the OS; this module owns pack boot policy so each
``boot-mode`` only gets directives that exist for that DOS family, and
so we maximize conventional memory (DOS=HIGH, UMB, DEVICEHIGH/LOADHIGH
or QEMM LOADHI when native UMB is unavailable).
"""

from __future__ import annotations

from packcli.boot_rules.capabilities import (
    ALL_BOOT_MODES,
    FAT16_MODES,
    FAT32_MODES,
    DosCapabilities,
    get_capabilities,
    normalize_boot_mode,
    resolve_boot_and_fat,
)
from packcli.boot_rules.render import (
    render_autoexec,
    render_config_sys,
    render_boot_files,
)

__all__ = [
    "ALL_BOOT_MODES",
    "FAT16_MODES",
    "FAT32_MODES",
    "DosCapabilities",
    "get_capabilities",
    "normalize_boot_mode",
    "resolve_boot_and_fat",
    "render_autoexec",
    "render_config_sys",
    "render_boot_files",
]
