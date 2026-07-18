"""Rebuild VHD from an already-converted pack directory."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from packcli.config import converter_root, default_audio, default_dosassets, expand_path


def run_rebuild(
    pack_dir: str,
    *,
    boot: str = "auto",
    name: str = "",
    dosassets: str = "",
    audio: str = "",
) -> int:
    root = str(converter_root())
    sys.path.insert(0, root)

    from logger import Logger
    import dosforgevhd

    pack = os.path.abspath(pack_dir)
    if not os.path.isdir(os.path.join(pack, "games")):
        print("ERROR: missing games/ under", pack, file=sys.stderr)
        return 1
    if not os.path.isdir(os.path.join(pack, "mymenu")):
        print("ERROR: missing mymenu/ under", pack, file=sys.stderr)
        return 1

    build_name = name or Path(pack).name
    assets = expand_path(dosassets or default_dosassets())
    boot = (boot or "auto").lower()

    # Prefer explicit assets subdir for classic 622 when auto/msdos622
    assets_path = assets
    if boot in ("auto", "msdos622") and assets:
        p = Path(assets)
        if (p / "msdos622").is_dir():
            # leave root; dosforge resolves modes under root
            assets_path = str(p)
        elif p.name == "msdos622":
            assets_path = str(p)

    audio_mode = (audio or default_audio() or "sb").strip().lower()
    conf = {
        "misterUseDosforge": "true",
        "misterLauncher": "mymenu",
        "misterBootMode": boot,
        "misterDosInstallProfile": "full",
        "misterIncludeQemm": "true",
        "misterBuildName": build_name,
        "misterStagingDir": os.path.join(pack, ".edc-staging"),
        "misterDosforgeBootAssets": assets_path,
        "misterAudio": audio_mode,
        "misterPreferGus": "true" if audio_mode == "gus" else "false",
    }

    logger = Logger()
    builder = dosforgevhd.DosforgeVhdBuilder(
        scriptDir=root,
        outputDir=pack,
        collectionVersion="eXoDOS v6",
        logger=logger,
        conversionConf=conf,
    )
    print("Rebuilding VHD from", pack, flush=True)
    print("  boot:", boot, "assets:", assets_path, flush=True)
    ok = builder.build()
    print("Result:", ok, flush=True)
    return 0 if ok else 1
