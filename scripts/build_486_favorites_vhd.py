#!/usr/bin/env python3
"""Build a multi-game MiSTer VHD from eXoDOS-Favorites-486sx66.sel.

Uses MyMenu frontend, collection metadata (README.ANS / box art), dosforge
VHD creation (auto FAT32/msdos71 when over FAT16 cap).
"""

from __future__ import annotations

import os
import sys
import time


def main() -> int:
    converter_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, converter_dir)

    from exoappstate import ExoAppState
    from logger import Logger
    import dosforgevhd

    collection = os.environ.get(
        "EXODOS_COLLECTION", "/mnt/net/exodos/eXoDOS"
    )
    out_root = os.environ.get(
        "EDC_OUT",
        os.path.join(converter_dir, "out", "mister-486-favorites"),
    )
    sel_path = os.environ.get(
        "EDC_SELECTION",
        os.path.join(converter_dir, "eXoDOS-Favorites-486sx66.sel"),
    )
    pack_name = os.environ.get("EDC_PACK_NAME", "486 Favorites")

    os.makedirs(out_root, exist_ok=True)

    logger = Logger()
    state = ExoAppState(converter_dir, logger)
    state.setValue("collectionDir", os.path.abspath(collection))
    state.setValue("outputDir", os.path.abspath(out_root))
    state.setValue("conversionType", "MiSTer")
    state.setValue("downloadOnDemand", "0")
    state.setValue("genreSubFolders", "0")
    state.setValue("longGameFolder", "1")
    state.setValue("debugMode", "0")
    state.setValue("selectionPath", os.path.abspath(sel_path))
    state.setValue("misterLauncher", "mymenu")
    state.setValue("misterUseDosforge", "true")
    # auto → msdos71/FAT32 when payload > ~1.9 GiB (this pack will)
    state.setValue("misterBootMode", "auto")
    state.setValue("misterDosInstallProfile", "full")
    state.setValue("misterGenerateReadmeAns", "true")
    state.setValue("misterIncludeQemm", "true")
    state.setValue("preExtractGames", "1")

    sibling622 = os.path.expanduser("~/Projects/dosforge/dosassets/msdos622")
    sibling71 = os.path.expanduser("~/Projects/dosforge/dosassets/msdos71")
    if os.path.isdir(sibling71):
        # Prefer 71 assets root so auto promotion can find them; dosforge
        # resolves per-mode under dosassets/.
        assets_root = os.path.expanduser("~/Projects/dosforge/dosassets")
        state.setValue("misterDosforgeBootAssets", assets_root)
    elif os.path.isdir(sibling622):
        state.setValue("misterDosforgeBootAssets", sibling622)

    print("=== Build 486 Favorites MiSTer VHD ===", flush=True)
    print("  collection:", state.getValue("collectionDir"), flush=True)
    print("  out:       ", out_root, flush=True)
    print("  selection: ", sel_path, flush=True)
    print("  pack name: ", pack_name, flush=True)
    print(
        "  dosforge:  ",
        dosforgevhd.DosforgeVhdBuilder.isAvailable(
            {
                "misterDosforgeExecutable": state.getValue(
                    "misterDosforgeExecutable"
                )
            }
        ),
        flush=True,
    )

    t0 = time.time()
    if not state.refreshCollection(buildCache=True):
        print("ERROR: collection refresh failed", file=sys.stderr)
        return 1
    print("  collection games:", len(state.fullnameToGameDir), flush=True)

    state.loadCustomSelection()
    if not state.selectedGames:
        print("ERROR: no games loaded from selection", file=sys.stderr)
        return 1
    print("  selected:", len(state.selectedGames), flush=True)

    # Multi-game MiSTer packs require a collection/build name.
    state.setBuildOutputName(pack_name)

    original_build = state._buildConversionConf

    def _build_conf_with_name():
        conf, long_names = original_build()
        conf["misterBuildName"] = pack_name
        conf["misterLauncher"] = "mymenu"
        conf["misterUseDosforge"] = "true"
        conf["misterBootMode"] = state.getValue("misterBootMode") or "auto"
        conf["misterDosInstallProfile"] = (
            state.getValue("misterDosInstallProfile") or "full"
        )
        conf["misterGenerateReadmeAns"] = "true"
        conf["misterIncludeQemm"] = "true"
        conf["preExtractGames"] = True
        assets = state.getValue("misterDosforgeBootAssets")
        if assets:
            conf["misterDosforgeBootAssets"] = assets
        return conf, long_names

    state._buildConversionConf = _build_conf_with_name

    print("=== Starting conversion ===", flush=True)
    try:
        ok = state.runConversion()
    except Exception as exc:
        print("ERROR: conversion failed:", exc, file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1
    elapsed = time.time() - t0
    print(
        "=== Conversion finished ok=%s elapsed=%.1f min ==="
        % (ok, elapsed / 60.0),
        flush=True,
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
