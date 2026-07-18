# mister-pack (production pack CLI + Grok skill)

**Full feature & usage guide (skill instructions):** [MISTER_PACK_SKILL.md](MISTER_PACK_SKILL.md) and `.grok/skills/mister-pack/SKILL.md` (`/mister-pack`).

**Fresh install guides:**

- [install_fresh.md](install_fresh.md) — brand-new system, full shell steps  
- [install_fresh_grok.md](install_fresh_grok.md) — start inside Grok Build CLI (minimal prompts)

Minimal path from a game list to a MiSTer ao486 pack **without** the converter GUI.

## Engines vs user data

| Auto-installed / updated by `setup` | User must supply (never downloaded) |
|-------------------------------------|-------------------------------------|
| **dosforge** — latest GitHub **release** via pip+git | **eXoDOS collection** root (`eXo/eXoDOS/`) |
| **ExoDOSConverter** — git **master** clone/pull + packcli deps | **dosassets** (MS-DOS/FreeDOS install media) |

The skill and CLI must **ask once** for the collection path if unset. Do not download game packs.

## Setup

```bash
# Install or update open-source engines (dosforge + ExoDOSConverter)
python3 -m packcli setup

# Same, and save local paths into ~/.config/mister-pack/config.toml
python3 -m packcli setup \
  --collection /path/to/eXoDOS \
  --dosassets ~/Projects/dosforge/dosassets \
  --audio gus

# Force reinstall / hard-reset converter to origin/master
python3 -m packcli setup --force

# Update only one engine
python3 -m packcli setup --skip-dosforge    # converter only
python3 -m packcli setup --skip-converter   # dosforge only

python3 -m packcli doctor
```

| Flag | Meaning |
|------|---------|
| `--force` | Update even if current; converter: `git reset --hard origin/master` |
| `--converter-dir` | Where to clone/update ExoDOSConverter |
| `--collection` | User eXoDOS path → config (not downloaded) |
| `--dosassets` | User dosassets path → config (not downloaded) |
| `--audio sb\|gus` | Default AUTOEXEC audio in config |

Requires: Python 3.10+, `git`, network for first setup/updates, Linux `sudo -n` for NBD VHD create.

Packcli Python deps live in `requirements-packcli.txt` (modern pins). Prefer those over the legacy root `requirements.txt` freeze.

## Commands

```bash
python3 -m packcli setup
python3 -m packcli doctor
python3 -m packcli resolve "doom" "blood"
python3 -m packcli build -f recipes/gus-classics.yaml
python3 -m packcli rebuild-vhd out/mister-gus-pack/GUS_Classics --boot auto
python3 -m packcli patch-autoexec path/to/pack.vhd --audio gus
```

Also: `python3 scripts/mister-pack …`

## Optional user config

`~/.config/mister-pack/config.toml` (also written by `setup --collection` / `--dosassets` / `--audio`):

```toml
# User-supplied paths only — never auto-downloaded
collection = "/mnt/net/exodos/eXoDOS"
dosassets = "/home/you/Projects/dosforge/dosassets"
output = "/home/you/mister-out"
converter = "/home/you/Projects/ExoDOSConverter"
# AUTOEXEC sound: "sb" or "gus"
audio = "sb"
```

| `audio` | AUTOEXEC sets | Then runs |
|---------|----------------|-----------|
| `sb` | `BLASTER=A220 I7 D1 H5 P330 T6` | `C:\PICOMEM\PMINIT.EXE /SB 1` |
| `gus` | `ULTRASND=240,1,1,5,5` + `ULTRADIR=C:\ULTRASND` (and BLASTER kept) | `C:\PICOMEM\PMINIT.EXE /GUS 1` |

Env vars still win: `EXODOS_COLLECTION`, `DOSFORGE_DOSASSETS_DIR`, `MISTER_PACK_OUT`, `MISTER_PACK_AUDIO`, `MISTER_PACK_CONVERTER`.

```bash
python3 -m packcli patch-autoexec pack.vhd --audio sb
python3 -m packcli patch-autoexec pack.vhd --audio gus
python3 -m packcli rebuild-vhd ./pack --audio gus
```

## Grok

Skill: `/mister-pack` (project: `.grok/skills/mister-pack/`, also under `~/.grok/skills/mister-pack/`).

Example prompts:

> /mister-pack install or update tools, then doctor

> /mister-pack create a GUS pack named Demo with DOOM and Blood

On first use, the skill runs `setup` for engines and **asks for** the local eXoDOS path if not configured.

## Recipe

See `recipes/gus-classics.yaml`. Options: `audio: gus|sb`, `boot: auto|msdos622|freedos`, `launcher: mymenu`.
