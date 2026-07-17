#!/usr/bin/env python3
"""Rebuild ao486 VHD from an already-converted MiSTer pack directory.

Expects layout:
  <pack>/games/
  <pack>/mymenu/
  optional <pack>/ao486/cd|floppy|bootdisk/

Does not re-convert games from eXoDOS.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    converter_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, converter_dir)

    from logger import Logger
    import dosforgevhd

    pack = os.path.abspath(
        sys.argv[1]
        if len(sys.argv) > 1
        else os.path.join(
            converter_dir, "out", "mister-486-favorites", "486_Favorites"
        )
    )
    if not os.path.isdir(os.path.join(pack, "games")):
        print("ERROR: missing games/ under", pack, file=sys.stderr)
        return 1
    if not os.path.isdir(os.path.join(pack, "mymenu")):
        print("ERROR: missing mymenu/ under", pack, file=sys.stderr)
        return 1

    logger = Logger()
    # Large multi-game packs need FAT32. Prefer FreeDOS when Win95 OSR2
    # SYS media is incomplete (msdos71 needs SYS.COM+IO.SYS on Boot.img).
    conf = {
        "misterUseDosforge": "true",
        "misterLauncher": "mymenu",
        "misterBootMode": "freedos",
        "misterDosInstallProfile": "full",
        "misterIncludeQemm": "true",
        "misterBuildName": "486 Favorites",
        "misterStagingDir": os.path.join(pack, ".edc-staging"),
        "misterDosforgeBootAssets": os.path.expanduser(
            "~/Projects/dosforge/dosassets/freedos"
        ),
    }
    builder = dosforgevhd.DosforgeVhdBuilder(
        scriptDir=converter_dir,
        outputDir=pack,
        collectionVersion="eXoDOS v6",
        logger=logger,
        conversionConf=conf,
    )
    print("Rebuilding VHD from", pack, flush=True)
    print("  staging:", conf["misterStagingDir"], flush=True)
    ok = builder.build()
    print("Result:", ok, flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
