"""Smoke tests for DOS version boot file generation."""
from packcli.boot_rules import (
    ALL_BOOT_MODES,
    get_capabilities,
    render_boot_files,
    resolve_boot_and_fat,
)


def test_all_modes_render():
    for mode in ALL_BOOT_MODES:
        if mode == "auto":
            continue
        cfg, aut = render_boot_files(mode, audio="sb")
        assert b"FILES" in cfg or b"DEVICE" in cfg
        assert b"@ECHO OFF" in aut


def test_msdos622_has_menu_and_devicehigh():
    cfg, aut = render_boot_files("msdos622", audio="gus")
    assert b"[MENU]" in cfg
    assert b"EMM386" in cfg
    assert b"DEVICEHIGH" in cfg
    assert b"GOTO END" in aut
    assert b"REMENU" not in aut
    assert b"PMINIT" in aut.upper()


def test_msdos5_no_menu():
    cfg, _ = render_boot_files("msdos5")
    assert b"[MENU]" not in cfg
    assert b"DEVICEHIGH" in cfg


def test_early_dos_uses_qemm():
    cfg, _ = render_boot_files("msdos33", include_qemm=True)
    assert b"DEVICEHIGH" not in cfg
    assert b"QEMM" in cfg


def test_auto_size():
    assert resolve_boot_and_fat("auto", size_bytes=100 * 1024 * 1024) == (
        "msdos622",
        "fat16",
    )
    assert resolve_boot_and_fat("auto", size_bytes=3 * 1024**3) == (
        "msdos71",
        "fat32",
    )


def test_capabilities_labels():
    assert get_capabilities("msdos622").label.startswith("MS-DOS 6.22")
