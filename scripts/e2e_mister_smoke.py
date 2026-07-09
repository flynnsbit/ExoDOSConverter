#!/usr/bin/env python3
"""End-to-end MiSTer smoke: convert one eXoDOS game → dosforge VHD → verify layout.

Example:
  python3 scripts/e2e_mister_smoke.py \\
    --collection /home/shawn/Downloads/exodos/eXoDOS \\
    --title Tris \\
    --out /tmp/edc-e2e-out

Requires:
  - dosforge on PATH (or --dosforge)
  - dosassets for msdos622 (sibling ~/Projects/dosforge/dosassets or env)
  - game zip present under collection eXo/eXoDOS/ (or downloadOnDemand)
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--collection",
        required=True,
        help="eXoDOS v6 collection root (contains xml/ and eXo/)",
    )
    parser.add_argument(
        "--title",
        default="Tris",
        help="Exact <Title> from MS-DOS.xml (default: Tris)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output root (default: temp dir under /tmp)",
    )
    parser.add_argument(
        "--name",
        default="e2e-smoke",
        help="MiSTer pack / build name",
    )
    parser.add_argument(
        "--dosforge",
        default=None,
        help="Path to dosforge executable (default: PATH / python -m)",
    )
    parser.add_argument(
        "--boot-assets",
        default=None,
        help="Path to dosassets/<mode> or dosassets root",
    )
    args = parser.parse_args(argv)

    converter_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, converter_dir)

    from exoappstate import ExoAppState
    from logger import Logger
    import dosforgevhd

    out_root = os.path.abspath(args.out or tempfile.mkdtemp(prefix="edc-e2e-"))
    os.makedirs(out_root, exist_ok=True)
    packlist = os.path.join(out_root, "packlist.lst")
    with open(packlist, "w", encoding="utf-8") as fh:
        fh.write(args.title.strip() + "\n")

    logger = Logger()
    state = ExoAppState(converter_dir, logger)
    state.setValue("collectionDir", os.path.abspath(args.collection))
    state.setValue("outputDir", out_root)
    state.setValue("conversionType", "MiSTer")
    state.setValue("downloadOnDemand", "0")
    state.setValue("genreSubFolders", "0")
    state.setValue("longGameFolder", "1")
    state.setValue("debugMode", "1")
    state.setValue("selectionPath", packlist)
    state.setValue("misterLauncher", "mymenu")
    state.setValue("misterUseDosforge", "true")
    state.setValue("misterBootMode", "msdos622")
    state.setValue("misterDosInstallProfile", "minimal")
    state.setValue("misterGenerateReadmeAns", "true")
    if args.dosforge:
        state.setValue("misterDosforgeExecutable", args.dosforge)
    if args.boot_assets:
        state.setValue("misterDosforgeBootAssets", args.boot_assets)
    else:
        sibling = os.path.expanduser("~/Projects/dosforge/dosassets/msdos622")
        if os.path.isdir(sibling):
            state.setValue("misterDosforgeBootAssets", sibling)

    print("=== E2E MiSTer smoke ===")
    print("  collection:", state.getValue("collectionDir"))
    print("  out:       ", out_root)
    print("  title:     ", args.title)
    print("  dosforge:  ", dosforgevhd.DosforgeVhdBuilder.isAvailable(
        {"misterDosforgeExecutable": state.getValue("misterDosforgeExecutable")}
    ))

    if not state.refreshCollection(buildCache=False):
        print("ERROR: collection refresh failed", file=sys.stderr)
        return 1
    print("  metadata games:", len(state.fullnameToGameDir))

    state.loadCustomSelection()
    if not state.selectedGames:
        print(
            "ERROR: title %r not found in collection metadata. "
            "Check exact <Title> string." % args.title,
            file=sys.stderr,
        )
        # show close matches
        matches = [n for n in state.fullnameToGameDir if args.title.lower() in n.lower()]
        if matches:
            print("  close matches:", matches[:10], file=sys.stderr)
        return 1
    print("  selected:", state.selectedGames)

    # Inject build name for multi/single pack folder
    state.setValue("misterBuildName", args.name)

    # runConversion builds converter; we need misterBuildName in conf
    # Patch by setting a temporary hook via conversion conf through runConversion internals.
    # exoappstate sets misterBuildName only when multi-game UI path runs; force it:
    original_build = state._buildConversionConf

    def _build_conf_with_name():
        conf, long = original_build()
        conf["misterBuildName"] = args.name
        conf["misterLauncher"] = "mymenu"
        conf["misterUseDosforge"] = "true"
        conf["misterBootMode"] = state.getValue("misterBootMode") or "msdos622"
        conf["misterDosInstallProfile"] = (
            state.getValue("misterDosInstallProfile") or "minimal"
        )
        conf["misterGenerateReadmeAns"] = "true"
        exe = state.getValue("misterDosforgeExecutable")
        if exe:
            conf["misterDosforgeExecutable"] = exe
        assets = state.getValue("misterDosforgeBootAssets")
        if assets:
            conf["misterDosforgeBootAssets"] = assets
        return conf, long

    state._buildConversionConf = _build_conf_with_name

    print("--- converting ---")
    try:
        state.runConversion()
    except Exception as exc:
        print("ERROR: conversion failed:", exc, file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

    # Locate pack output
    vhd_paths = []
    for root, _dirs, files in os.walk(out_root):
        for f in files:
            if f.lower().endswith(".vhd"):
                vhd_paths.append(os.path.join(root, f))
    if not vhd_paths:
        print("ERROR: no .vhd produced under", out_root, file=sys.stderr)
        print("  (check logs for dosforge / mymenu / games staging errors)", file=sys.stderr)
        return 1

    vhd = max(vhd_paths, key=os.path.getmtime)
    print("  VHD:", vhd, "(%i bytes)" % os.path.getsize(vhd))

    # Verify contents via dosforge ls / cat
    env = os.environ.copy()
    dosforge_src = os.path.expanduser("~/Projects/dosforge/src")
    if os.path.isdir(dosforge_src):
        env["PYTHONPATH"] = dosforge_src + os.pathsep + env.get("PYTHONPATH", "")
    py = sys.executable

    def df(*args):
        cmd = [py, "-m", "dosforge", *args]
        r = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return r.returncode, r.stdout, r.stderr

    checks = []
    code, out, err = df("ls", vhd, "::/")
    print("--- ls ::/ ---")
    print(out or err)
    checks.append(("MYMENU dir", "MYMENU" in out.upper() or "mymenu" in out.lower()))
    checks.append(("GAMES dir", "GAMES" in out.upper()))
    checks.append(("AUTOEXEC.BAT", "AUTOEXEC" in out.upper()))
    checks.append(("AUTORUN_EDC", "AUTORUN" in out.upper() or "AUTORU" in out.upper()))
    # COMMAND.COM must be a real dosforge install, not a 0-byte support-zip clobber.
    cmd_tmp = os.path.join(out_root, "_check_command.com")
    code_c, _o, _e = df("get", vhd, "::/COMMAND.COM", cmd_tmp)
    cmd_ok = (
        code_c == 0
        and os.path.isfile(cmd_tmp)
        and os.path.getsize(cmd_tmp) > 1000
    )
    checks.append(("COMMAND.COM size > 1K", cmd_ok))

    code, out, err = df("cat", vhd, "::/AUTOEXEC.BAT")
    print("--- AUTOEXEC.BAT ---")
    print(out or err)
    checks.append(("AUTOEXEC calls AUTORUN_EDC", "AUTORUN_EDC" in (out or "").upper()))

    code, out, err = df("cat", vhd, "::/AUTORUN_EDC.BAT")
    print("--- AUTORUN_EDC.BAT ---")
    print(out or err)
    checks.append(
        ("MyMenu launch", "MYMENU" in (out or "").upper() or "MENU.BAT" in (out or "").upper())
    )

    code, out, err = df("ls", vhd, "::/GAMES")
    print("--- ls ::/GAMES ---")
    print(out or err)
    checks.append(("GAMES has content", "files" in out.lower() or "<DIR>" in out))

    # Find first game folder and check README.ANS + autorun.bat
    game_dirs = []
    for line in (out or "").splitlines():
        # mdir style: NAME     <DIR>
        if "<DIR>" in line:
            parts = line.split()
            if parts and parts[0] not in (".", ".."):
                game_dirs.append(parts[0])
    # Also try host-side games/ under build
    host_games = None
    for root, dirs, _files in os.walk(out_root):
        if os.path.basename(root) == "games" and dirs:
            host_games = [(d, os.path.join(root, d)) for d in dirs]
            break

    if host_games:
        gname, gpath = host_games[0]
        print("--- host game folder:", gpath)
        checks.append(
            ("autorun.bat", os.path.isfile(os.path.join(gpath, "autorun.bat")))
        )
        checks.append(
            ("README.ANS", os.path.isfile(os.path.join(gpath, "README.ANS")))
        )
        checks.append(
            ("1_Start.bat", os.path.isfile(os.path.join(gpath, "1_Start.bat")))
        )
        if os.path.isfile(os.path.join(gpath, "README.ANS")):
            print("  README.ANS size:", os.path.getsize(os.path.join(gpath, "README.ANS")))
        if os.path.isfile(os.path.join(gpath, "autorun.bat")):
            print("  autorun.bat:", open(os.path.join(gpath, "autorun.bat"), "rb").read())

    # MYMENU.INI DRV line
    code, out, err = df("cat", vhd, "::/MYMENU/MYMENU.INI")
    print("--- MYMENU.INI (tail) ---")
    text = out or err or ""
    print("\n".join(text.splitlines()[-15:]))
    checks.append(("MYMENU.INI has C:\\GAMES", "C:\\GAMES" in text.upper() or "C:/GAMES" in text.upper() or "GAMES;C:" in text.upper()))

    print("=== CHECK RESULTS ===")
    failed = 0
    for label, ok in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            failed += 1
        print("  [%s] %s" % (status, label))

    print()
    print("Pack ready for hardware/QEMU test:" if failed == 0 else "Pack incomplete:")
    print(" ", vhd)
    print("Output tree:", out_root)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
