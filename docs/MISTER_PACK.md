# mister-pack (production pack CLI + Grok skill)

**Full feature & usage guide (skill instructions):** [MISTER_PACK_SKILL.md](MISTER_PACK_SKILL.md) and `.grok/skills/mister-pack/SKILL.md` (`/mister-pack`).

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
# AUTOEXEC sound: "sb" or "gus"
audio = "sb"
```

| `audio` | AUTOEXEC sets | Then runs |
|---------|----------------|-----------|
| `sb` | `BLASTER=A220 I7 D1 H5 P330 T6` | `C:\PICOMEM\PMINIT.EXE /SB 1` |
| `gus` | `ULTRASND=240,1,1,5,5` + `ULTRADIR=C:\ULTRASND` (and BLASTER kept) | `C:\PICOMEM\PMINIT.EXE /GUS 1` |

Env vars still win: `EXODOS_COLLECTION`, `DOSFORGE_DOSASSETS_DIR`, `MISTER_PACK_OUT`, `MISTER_PACK_AUDIO`.

```bash
python3 -m packcli patch-autoexec pack.vhd --audio sb
python3 -m packcli patch-autoexec pack.vhd --audio gus
python3 -m packcli rebuild-vhd ./pack --audio gus
```

## Grok

Skill: `/mister-pack` (project: `.grok/skills/mister-pack/`, also under `~/.grok/skills/mister-pack/`).

Example prompt:

> /mister-pack create a GUS pack named Demo with DOOM and Blood

## Recipe

See `recipes/gus-classics.yaml`. Options: `audio: gus|sb`, `boot: auto|msdos622|freedos`, `launcher: mymenu`.
