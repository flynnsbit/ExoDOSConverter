# mister-pack (production pack CLI + Grok skill)

Minimal path from a game list to a MiSTer ao486 pack **without** the converter GUI.

## Setup (once)

```bash
export EXODOS_COLLECTION=/path/to/eXoDOS
export DOSFORGE_DOSASSETS_DIR=~/Projects/dosforge/dosassets
cd /path/to/ExoDOSConverter
python3 -m packcli doctor
```

Requires: Python 3.10+, `dosforge` on PATH, this checkout, eXoDOS v6 tree, dosassets.

## Commands

```bash
python3 -m packcli doctor
python3 -m packcli resolve "doom" "blood"
python3 -m packcli build -f recipes/gus-classics.yaml
python3 -m packcli rebuild-vhd out/mister-gus-pack/GUS_Classics --boot auto
python3 -m packcli patch-autoexec path/to/pack.vhd
```

Also: `python3 scripts/mister-pack …`

## Optional user config

`~/.config/mister-pack/config.toml`:

```toml
collection = "/mnt/net/exodos/eXoDOS"
dosassets = "/home/you/Projects/dosforge/dosassets"
output = "/home/you/mister-out"
```

Env vars still win: `EXODOS_COLLECTION`, `DOSFORGE_DOSASSETS_DIR`, `MISTER_PACK_OUT`.

## Grok

Skill: `/mister-pack` (project: `.grok/skills/mister-pack/`, also under `~/.grok/skills/mister-pack/`).

Example prompt:

> /mister-pack create a GUS pack named Demo with DOOM and Blood

## Recipe

See `recipes/gus-classics.yaml`. Options: `audio: gus|sb`, `boot: auto|msdos622|freedos`, `launcher: mymenu`.
