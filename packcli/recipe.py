"""Load pack recipes (YAML or simple game list)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

from packcli.config import default_collection, default_dosassets, default_output, expand_path


@dataclass
class PackRecipe:
    name: str
    games: List[str]
    collection: str = ""
    output: str = ""
    dosassets: str = ""
    launcher: str = "mymenu"
    audio: str = "sb"  # sb | gus
    boot: str = "auto"  # auto | msdos622 | freedos
    prefer_gus: bool = False
    include_qemm: bool = True
    include_ultrasnd: bool = True
    include_picomem: bool = True
    pminit_gus: bool = False
    long_game_folder: bool = True
    generate_readme_ans: bool = True

    def resolved(self) -> "PackRecipe":
        r = PackRecipe(
            name=self.name.strip() or "MisterPack",
            games=list(self.games),
            collection=expand_path(self.collection or default_collection()),
            output=expand_path(self.output or default_output()),
            dosassets=expand_path(self.dosassets or default_dosassets()),
            launcher=self.launcher or "mymenu",
            audio=(self.audio or "sb").lower(),
            boot=(self.boot or "auto").lower(),
            prefer_gus=bool(self.prefer_gus),
            include_qemm=bool(self.include_qemm),
            include_ultrasnd=bool(self.include_ultrasnd),
            include_picomem=bool(self.include_picomem),
            pminit_gus=bool(self.pminit_gus),
            long_game_folder=bool(self.long_game_folder),
            generate_readme_ans=bool(self.generate_readme_ans),
        )
        if r.audio == "gus":
            r.prefer_gus = True
            r.pminit_gus = True
            r.include_ultrasnd = True
            r.include_picomem = True
        return r


def _as_bool(val: Any, default: bool = False) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("1", "true", "yes", "on")


def load_recipe(path: str | Path) -> PackRecipe:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    data: dict
    if path.suffix.lower() in (".yaml", ".yml"):
        try:
            import yaml
        except ImportError as exc:
            raise SystemExit(
                "PyYAML required for .yaml recipes: pip install pyyaml"
            ) from exc
        data = yaml.safe_load(text) or {}
    else:
        # Plain selection: one game title per line; name from filename
        games = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
        data = {"name": path.stem, "games": games}

    if not isinstance(data, dict):
        raise SystemExit("recipe must be a mapping")

    opts = data.get("options") or {}
    if not isinstance(opts, dict):
        opts = {}

    games = data.get("games") or []
    if isinstance(games, str):
        games = [games]
    games = [str(g).strip() for g in games if str(g).strip()]

    return PackRecipe(
        name=str(data.get("name") or path.stem),
        games=games,
        collection=str(data.get("collection") or ""),
        output=str(data.get("output") or ""),
        dosassets=str(data.get("dosassets") or opts.get("dosassets") or ""),
        launcher=str(opts.get("launcher") or data.get("launcher") or "mymenu"),
        audio=str(opts.get("audio") or data.get("audio") or "sb"),
        boot=str(opts.get("boot") or data.get("boot") or "auto"),
        prefer_gus=_as_bool(opts.get("prefer_gus") or data.get("prefer_gus")),
        include_qemm=_as_bool(opts.get("include_qemm"), True),
        include_ultrasnd=_as_bool(opts.get("include_ultrasnd"), True),
        include_picomem=_as_bool(opts.get("include_picomem"), True),
        pminit_gus=_as_bool(opts.get("pminit_gus")),
        long_game_folder=_as_bool(opts.get("long_game_folder"), True),
        generate_readme_ans=_as_bool(opts.get("generate_readme_ans"), True),
    ).resolved()
