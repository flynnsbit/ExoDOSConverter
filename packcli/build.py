"""Build a MiSTer pack from a recipe."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from packcli.config import converter_root
from packcli.recipe import PackRecipe, load_recipe


def build_from_recipe(recipe: PackRecipe) -> int:
    recipe = recipe.resolved()
    root = str(converter_root())
    sys.path.insert(0, root)

    from exoappstate import ExoAppState
    from logger import Logger
    import dosforgevhd

    if not recipe.collection or not Path(recipe.collection).is_dir():
        print(
            "ERROR: collection path missing. Set EXODOS_COLLECTION or recipe.collection",
            file=sys.stderr,
        )
        return 1
    if not recipe.games:
        print("ERROR: recipe has no games", file=sys.stderr)
        return 1

    out_root = recipe.output
    os.makedirs(out_root, exist_ok=True)
    sel_path = os.path.join(out_root, "selection.sel")
    with open(sel_path, "w", encoding="utf-8") as fh:
        for g in recipe.games:
            fh.write(g + "\n")

    logger = Logger()
    state = ExoAppState(root, logger)
    state.setValue("collectionDir", os.path.abspath(recipe.collection))
    state.setValue("outputDir", os.path.abspath(out_root))
    state.setValue("conversionType", "MiSTer")
    state.setValue("downloadOnDemand", "0")
    state.setValue("genreSubFolders", "0")
    state.setValue("longGameFolder", "1" if recipe.long_game_folder else "0")
    state.setValue("debugMode", "0")
    state.setValue("selectionPath", sel_path)
    state.setValue("misterLauncher", recipe.launcher)
    state.setValue("misterUseDosforge", "true")
    state.setValue("misterBootMode", recipe.boot)
    state.setValue("misterDosInstallProfile", "full")
    state.setValue(
        "misterGenerateReadmeAns", "true" if recipe.generate_readme_ans else "false"
    )
    state.setValue("misterIncludeQemm", "true" if recipe.include_qemm else "false")
    state.setValue("misterPreferGus", "true" if recipe.prefer_gus else "false")
    state.setValue("preExtractGames", "1")
    if recipe.dosassets:
        state.setValue("misterDosforgeBootAssets", recipe.dosassets)

    print("=== mister-pack build ===", flush=True)
    print("  name:      ", recipe.name, flush=True)
    print("  collection:", recipe.collection, flush=True)
    print("  output:    ", out_root, flush=True)
    print("  games:     ", len(recipe.games), flush=True)
    print("  audio:     ", recipe.audio, "prefer_gus=", recipe.prefer_gus, flush=True)
    print("  boot:      ", recipe.boot, flush=True)
    print(
        "  dosforge:  ",
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
        missing = [g for g in recipe.games if g not in state.fullnameToGameDir]
        print("  missing:", missing, file=sys.stderr)
        # suggest resolves
        from packcli.resolve import resolve_query

        for m in missing[:5]:
            hits = resolve_query(m.split("(")[0].strip(), limit=3)
            if hits:
                print(f"  try '{m}' →", [h[0] for h in hits], file=sys.stderr)
        return 1

    print("  selected:  ", state.selectedGames, flush=True)
    state.setBuildOutputName(recipe.name)

    original = state._buildConversionConf

    def _conf():
        conf, long_names = original()
        conf["misterBuildName"] = recipe.name
        conf["misterLauncher"] = recipe.launcher
        conf["misterUseDosforge"] = "true"
        conf["misterBootMode"] = recipe.boot
        conf["misterDosInstallProfile"] = "full"
        conf["misterGenerateReadmeAns"] = (
            "true" if recipe.generate_readme_ans else "false"
        )
        conf["misterIncludeQemm"] = "true" if recipe.include_qemm else "false"
        conf["misterPreferGus"] = "true" if recipe.prefer_gus else "false"
        conf["preExtractGames"] = True
        conf["misterStagingDir"] = os.path.join(out_root, ".edc-staging")
        assets = state.getValue("misterDosforgeBootAssets")
        if assets:
            conf["misterDosforgeBootAssets"] = assets
        return conf, long_names

    state._buildConversionConf = _conf

    try:
        ok = state.runConversion()
    except Exception as exc:
        print("ERROR:", exc, file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1

    elapsed = (time.time() - t0) / 60.0
    print(
        "=== done ok=%s elapsed=%.1f min ===" % (ok, elapsed),
        flush=True,
    )
    if ok:
        # hint path
        pack_dir = Path(out_root) / recipe.name.replace(" ", "_")
        if not pack_dir.is_dir():
            # try spaced name
            pack_dir = Path(out_root) / recipe.name
        ao = pack_dir / "ao486"
        if ao.is_dir():
            print("  pack output under:", ao, flush=True)
            for p in sorted(ao.rglob("*.vhd")):
                print("  VHD:", p, flush=True)
    return 0 if ok else 1


def run_build(recipe_path: str) -> int:
    recipe = load_recipe(recipe_path)
    return build_from_recipe(recipe)
