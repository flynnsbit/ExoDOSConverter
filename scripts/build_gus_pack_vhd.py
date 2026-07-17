#!/usr/bin/env python3
"""Build a small MiSTer VHD pack with GUS defaults + UltraSound + PicoMEM.

Games: OMF 2097, DOOM, Jazz CD, Epic Pinball, Pinball Fantasies, Raptor,
Crusader No Remorse, Duke3D, Fallout, Blood, Shadow Warrior.
"""

from __future__ import annotations

import os
import sys
import time

GAMES = [
    "One Must Fall 2097 (1994)",
    "DOOM (1993)",
    "Jazz Jackrabbit CD-ROM (1994)",
    "Epic Pinball - The Complete Collection (1995)",
    "Pinball Fantasies (1992)",
    "Raptor - Call of the Shadows (1994)",
    "Crusader - No Remorse (1995)",
    "Duke Nukem 3D (1996)",
    "Fallout (1997)",
    "Blood (1997)",
    "Shadow Warrior (1997)",
]


def main() -> int:
    converter_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, converter_dir)

    from exoappstate import ExoAppState
    from logger import Logger
    import dosforgevhd

    collection = os.environ.get("EXODOS_COLLECTION", "/mnt/net/exodos/eXoDOS")
    out_root = os.environ.get(
        "EDC_OUT",
        os.path.join(converter_dir, "out", "mister-gus-pack"),
    )
    pack_name = os.environ.get("EDC_PACK_NAME", "GUS Classics")
    os.makedirs(out_root, exist_ok=True)

    sel_path = os.path.join(out_root, "selection.sel")
    with open(sel_path, "w", encoding="utf-8") as fh:
        for g in GAMES:
            fh.write(g + "\n")

    logger = Logger()
    state = ExoAppState(converter_dir, logger)
    state.setValue("collectionDir", os.path.abspath(collection))
    state.setValue("outputDir", os.path.abspath(out_root))
    state.setValue("conversionType", "MiSTer")
    state.setValue("downloadOnDemand", "0")
    state.setValue("genreSubFolders", "0")
    state.setValue("longGameFolder", "1")
    state.setValue("debugMode", "0")
    state.setValue("selectionPath", sel_path)
    state.setValue("misterLauncher", "mymenu")
    state.setValue("misterUseDosforge", "true")
    # auto promotes to FreeDOS/FAT32 when over FAT16 soft cap (~1.9 GiB)
    state.setValue("misterBootMode", "auto")
    state.setValue("misterDosInstallProfile", "full")
    state.setValue("misterGenerateReadmeAns", "true")
    state.setValue("misterIncludeQemm", "true")
    state.setValue("misterPreferGus", "true")
    state.setValue("preExtractGames", "1")

    assets = os.path.expanduser("~/Projects/dosforge/dosassets")
    if os.path.isdir(assets):
        state.setValue("misterDosforgeBootAssets", assets)

    print("=== GUS Classics MiSTer VHD ===", flush=True)
    print("  collection:", collection, flush=True)
    print("  out:", out_root, flush=True)
    print("  games:", len(GAMES), flush=True)
    print(
        "  dosforge:",
        dosforgevhd.DosforgeVhdBuilder.isAvailable({}),
        flush=True,
    )

    t0 = time.time()
    if not state.refreshCollection(buildCache=True):
        print("ERROR: collection refresh failed", file=sys.stderr)
        return 1

    state.loadCustomSelection()
    if not state.selectedGames:
        print("ERROR: no games matched selection", file=sys.stderr)
        print("  available sample:", list(state.fullnameToGameDir)[:5], file=sys.stderr)
        missing = [g for g in GAMES if g not in state.fullnameToGameDir]
        print("  missing:", missing, file=sys.stderr)
        return 1
    print("  selected:", state.selectedGames, flush=True)
    state.setBuildOutputName(pack_name)

    original = state._buildConversionConf

    def _conf():
        conf, long_names = original()
        conf["misterBuildName"] = pack_name
        conf["misterLauncher"] = "mymenu"
        conf["misterUseDosforge"] = "true"
        conf["misterBootMode"] = "auto"
        conf["misterDosInstallProfile"] = "full"
        conf["misterGenerateReadmeAns"] = "true"
        conf["misterIncludeQemm"] = "true"
        conf["misterPreferGus"] = "true"
        conf["preExtractGames"] = True
        conf["misterStagingDir"] = os.path.join(out_root, ".edc-staging")
        assets_path = state.getValue("misterDosforgeBootAssets")
        if assets_path:
            conf["misterDosforgeBootAssets"] = assets_path
        return conf, long_names

    state._buildConversionConf = _conf

    try:
        ok = state.runConversion()
    except Exception as exc:
        print("ERROR:", exc, file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1

    print(
        "=== done ok=%s elapsed=%.1f min ===" % (ok, (time.time() - t0) / 60.0),
        flush=True,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
