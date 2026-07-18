---
name: mister-pack
description: >
  Build production MiSTer ao486 packs from eXoDOS games via ExoDOSConverter +
  dosforge (VHD + external cd/floppy, MyMenu, optional GUS/PicoMEM). Use when
  the user runs /mister-pack, asks to "create a pack", "build a VHD", "MiSTer
  pack", "eXoDOS convert to VHD", or wants games on a bootable DOS disk image
  with MyMenu.
---

# mister-pack — full feature & usage guide

Production path: **recipe → convert → dosforge VHD**. Stay in Grok CLI. Do **not** open the ExoDOSConverter GUI or run test suites for normal packs.

**Converter root (this machine):** `/home/shawn/Projects/ExoDOSConverter`  
**CLI:** `python3 -m packcli …` or `python3 scripts/mister-pack …`  
**Slash:** `/mister-pack`

---

## 1. What this skill produces

A **MiSTer ao486 pack** ready to copy to the SD card:

```text
<output>/<PackName>/ao486/<PackName>/
├── <PackName>.vhd      # bootable MS-DOS + games + MyMenu + drivers
├── cd/                 # external CD images (Blood, Fallout, etc.)
│   └── Blood/BLOODCD1.cue|.img|…
└── floppy/             # if any game needs floppies
```

Inside the VHD (typical):

| Path | Role |
|------|------|
| `C:\AUTOEXEC.BAT` / `CONFIG.SYS` | Boot: EMM386 default, audio block, MyMenu loop |
| `C:\GAMES\<Title>\` | Converted games, `autorun.bat`, `1_Start.bat`, `README.ANS` |
| `C:\MYMENU\` | MyMenu frontend (C:-only INI) |
| `C:\DRIVERS\` | Mouse, CD, SBCTL, etc. (boot-c) |
| `C:\ULTRASND\` | GUS driver tree (when GUS audio / staged) |
| `C:\PICOMEM\` | PicoMEM tools (`PMINIT.EXE`, …) |

---

## 2. One-time setup

### Required software

| Need | Notes |
|------|--------|
| Python 3.10+ | Converter + packcli |
| `dosforge` on PATH | `pip install` / sibling `~/Projects/dosforge` |
| ExoDOSConverter checkout | This repo |
| eXoDOS v6 tree | Must contain `eXo/eXoDOS/` game zips |
| dosforge dosassets | `msdos622/` (Disk1.img…) and/or `freedos/` |
| Linux `sudo -n` for NBD | Headless VHD create |

### Environment (session or shell profile)

```bash
export EXODOS_COLLECTION=/mnt/net/exodos/eXoDOS
export DOSFORGE_DOSASSETS_DIR=~/Projects/dosforge/dosassets
# optional:
export MISTER_PACK_OUT=~/Projects/ExoDOSConverter/out/mister-packs
export MISTER_PACK_AUDIO=sb    # or gus — default AUTOEXEC audio
cd /home/shawn/Projects/ExoDOSConverter
```

### Optional user config file

Copy and edit:

```bash
mkdir -p ~/.config/mister-pack
cp recipes/example-config.toml ~/.config/mister-pack/config.toml
```

Example `~/.config/mister-pack/config.toml`:

```toml
collection = "/mnt/net/exodos/eXoDOS"
dosassets  = "/home/shawn/Projects/dosforge/dosassets"
output     = "/home/shawn/Projects/ExoDOSConverter/out/mister-packs"

# Default AUTOEXEC sound mode when recipe does not set options.audio:
#   "sb"  or  "gus"
audio = "sb"
```

**Precedence (highest wins):** recipe `options.audio` → env `MISTER_PACK_AUDIO` → config.toml `audio` → `sb`.

### Health check (always run first if unsure)

```bash
python3 -m packcli doctor
```

Must report OK for: Python, dosforge, boot-c.zip, distro.zip, eXoDOSv6.csv, collection, dosassets. Fix failures before building.

---

## 3. CLI reference

### `doctor`

```bash
python3 -m packcli doctor
```

Checks collection path, dosforge, converter payloads (`boot-c.zip`, `distro.zip`, ULTRASND, PICOMEM), dosassets, sudo.

### `resolve` — fuzzy title → exact eXo name

```bash
python3 -m packcli resolve "doom" "blood" "duke nukem"
python3 -m packcli resolve doom --limit 10
```

- Uses `data/eXoDOSv6.csv`.
- Prints ranked matches; first line marked `*` is **best**.
- Example: `doom` → **DOOM (1993)** (not “Dr. Doom’s Revenge”).
- Recipe `games:` entries must be **exact** titles (usually with year).

### `build` — full pack (convert + VHD)

```bash
python3 -m packcli build -f recipes/gus-classics.yaml
python3 -m packcli build -f /tmp/my-pack.yaml
python3 -m packcli build -f selection.sel   # plain list: one title per line
```

### `rebuild-vhd` — VHD only (games tree already exists)

Use when convert finished but VHD failed, or you only need a new image from `games/` + `mymenu/`.

```bash
python3 -m packcli rebuild-vhd out/mister-gus-pack/GUS_Classics --boot auto
python3 -m packcli rebuild-vhd ./pack --boot freedos --audio gus
python3 -m packcli rebuild-vhd ./pack --name "My Pack" --dosassets ~/Projects/dosforge/dosassets
```

| Flag | Meaning |
|------|---------|
| `--boot auto\|msdos622\|freedos` | DOS/FAT choice (`auto` picks FreeDOS if payload &gt; ~1.9 GiB) |
| `--audio sb\|gus` | AUTOEXEC audio block (see §5) |
| `--name` | VHD/build folder name |
| `--dosassets` | Override dosassets path |

### `patch-autoexec` — fix sound on existing VHD (no rebuild)

```bash
python3 -m packcli patch-autoexec /path/to/Pack.vhd --audio sb
python3 -m packcli patch-autoexec /path/to/Pack.vhd --audio gus
```

Rewrites the marked audio section in `C:\AUTOEXEC.BAT` only.

---

## 4. Recipe file (main user artifact)

YAML (preferred) or a `.sel` list (one exact title per line).

### Full example

```yaml
# recipes/my-pack.yaml
name: My Cool Pack
collection: ${EXODOS_COLLECTION}    # or absolute path
output: ./out/mister-packs

games:
  - DOOM (1993)
  - Duke Nukem 3D (1996)
  - Blood (1997)

options:
  launcher: mymenu          # mymenu | none (single-game direct launch)
  audio: gus                # sb | gus  (see §5)
  boot: auto                # auto | msdos622 | freedos
  prefer_gus: true          # implied when audio: gus
  pminit_gus: true          # implied when audio: gus
  include_qemm: true
  include_ultrasnd: true    # stage C:\ULTRASND
  include_picomem: true     # stage C:\PICOMEM
  long_game_folder: true
  generate_readme_ans: true
```

Shipped example: `recipes/gus-classics.yaml` (11 GUS classics).

### Recipe fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Pack / VHD base name |
| `games` | yes | Exact eXo titles (from `resolve`) |
| `collection` | if env unset | eXoDOS root |
| `output` | no | Output root (default from config/env) |
| `options.audio` | no | `sb` or `gus` |
| `options.boot` | no | `auto` / `msdos622` / `freedos` |
| `options.launcher` | no | `mymenu` (default) or `none` |

---

## 5. Audio modes (SB vs GUS) — detail

Chosen by **recipe** → **env** → **config.toml**.

### `audio: sb` (Sound Blaster)

AUTOEXEC block (after `@ECHO OFF`):

```bat
REM --- mister-pack audio begin ---
REM Sound Blaster 16 defaults
IF EXIST C:\DRIVERS\SBCTL.EXE LOADHIGH C:\DRIVERS\SBCTL.EXE I7 T6
SET BLASTER=A220 I7 D1 H5 P330 T6
IF EXIST C:\PICOMEM\PMINIT.EXE C:\PICOMEM\PMINIT.EXE /SB 1
REM --- mister-pack audio end ---
```

- IRQ **7**, DMA **1**, HDMA **5**, type **6** (SB16).
- PicoMEM: **`PMINIT /SB 1`**.

### `audio: gus` (Gravis UltraSound / PicoGUS)

```bat
REM --- mister-pack audio begin ---
REM Sound Blaster env (many titles still read BLASTER)
IF EXIST C:\DRIVERS\SBCTL.EXE LOADHIGH C:\DRIVERS\SBCTL.EXE I7 T6
SET BLASTER=A220 I7 D1 H5 P330 T6
REM Gravis UltraSound / PicoGUS (DMA 1,1 + IRQ 5,5)
SET ULTRASND=240,1,1,5,5
SET ULTRADIR=C:\ULTRASND
IF EXIST C:\PICOMEM\PMINIT.EXE C:\PICOMEM\PMINIT.EXE /GUS 1
REM --- mister-pack audio end ---
```

- ULTRASND: port **240**, DMA **1,1**, IRQ **5,5** (not 7,7).
- PicoMEM: **`PMINIT /GUS 1`**.
- Also: stages `C:\ULTRASND` + `C:\PICOMEM`, applies eXo GUS presets (`misterPreferGus`), rewrites game `autorun`/`run.bat` where possible.

### Switching audio on an existing pack

```bash
python3 -m packcli patch-autoexec ./ao486/MyPack/MyPack.vhd --audio sb
python3 -m packcli patch-autoexec ./ao486/MyPack/MyPack.vhd --audio gus
```

No full convert required.

---

## 6. Boot / DOS defaults (do not re-argue unless user asks)

| Item | Production default |
|------|-------------------|
| CONFIG.SYS menu | **EMM386** default; no `NOAUTO` |
| EMM386 line | `EMM386.EXE AUTO RAM` (simple) |
| LFN | **DOSLFNM** only (once) |
| UNIVBE | Not loaded |
| MyMenu | C: only (`DRV = GAMES;C:\GAMES\`) |
| CD layout | External `cd/<dosname>/` beside VHD |
| Boot mode | `auto`: MS-DOS 6.22 + FAT16 if fits; FreeDOS + FAT32 if oversized |

---

## 7. Agent workflow (when user prompts in chat)

### A. First-time / “is my machine ready?”

1. `python3 -m packcli doctor`
2. Report failures; set env or `config.toml`; re-run doctor.

### B. “Make a pack with these games…”

1. `doctor` if not green this session.
2. `resolve` each fuzzy name → exact titles.
3. Write `recipe.yaml` (use `audio: gus` or `sb` from user intent; default config otherwise).
4. `python3 -m packcli build -f recipe.yaml`
5. On success, print absolute path to `ao486/` folder (VHD + `cd/`).
6. Checklist:
   - [ ] `.vhd` present  
   - [ ] CD games have files under sibling `cd/` (e.g. Blood → `BLOODCD1.cue`)  
   - [ ] Audio: AUTOEXEC has correct `PMINIT /SB` or `/GUS`  
   - [ ] GUS builds: `ULTRASND` + `PICOMEM` dirs on VHD  

### C. “Only rebuild the VHD”

```bash
python3 -m packcli rebuild-vhd <packDirWith_games_and_mymenu> --boot auto --audio gus
```

### D. “Switch this pack to Sound Blaster / GUS”

```bash
python3 -m packcli patch-autoexec <vhd> --audio sb   # or gus
```

### E. “Add another game”

1. Resolve exact title.  
2. Add to recipe `games:`.  
3. Full `build` again (or convert that game into existing pack tree + `rebuild-vhd` if expert).  

---

## 8. Example user phrases → actions

| User says | Agent does |
|-----------|------------|
| `/mister-pack doctor` | `python3 -m packcli doctor` |
| Create GUS pack with DOOM and Blood | resolve → recipe `audio: gus` → build |
| Pack with SB only | recipe `audio: sb` → build |
| What’s the exact name for raptor? | `resolve raptor` → print best title |
| Rebuild VHD only | `rebuild-vhd <dir>` |
| Change existing VHD to GUS | `patch-autoexec <vhd> --audio gus` |
| Change existing VHD to SB | `patch-autoexec <vhd> --audio sb` |
| Copy path for MiSTer? | Print `…/ao486/<pack>/` (entire folder) |

---

## 9. Failure playbooks

| Symptom | Fix |
|---------|-----|
| `doctor` collection fail | Set `EXODOS_COLLECTION` or `config.toml` `collection` to eXoDOS root (`eXo/eXoDOS` must exist) |
| No games matched | `resolve`; use exact CSV title with year |
| Blood CD empty | Conf typo `BLOOD121` vs on-disk `BLOODCD1` — fixed in converter; rebuild pack if old |
| dosforge “boot assets” error | `DOSFORGE_DOSASSETS_DIR` = dosassets **root** (with `msdos622/` / `freedos/`) |
| FAT16 / size error | `boot: auto` or `boot: freedos` |
| Convert OK, VHD fail | `rebuild-vhd` with correct `--dosassets` and `--audio` |
| GUS IRQ 7 in game | Env is 5,5; eXo presets patched when `prefer_gus`; re-apply via rebuild or new build |
| Need only AUTOEXEC sound change | `patch-autoexec --audio sb\|gus` |

---

## 10. What not to do

- Do not open the converter GUI for this workflow  
- Do not run full dosforge/converter test suites for pack builds  
- Do not clone eXoDOS into git or ship game zips  
- Do not rebuild MyMenu from Pascal unless `distro.zip` is missing  
- Do not invent setup files — use eXo GUS folders + standard env  
- Do not invent collection/dosassets paths; ask user or use config  

---

## 11. Copy to MiSTer

Copy the **whole** pack directory next to the VHD (not only the `.vhd`):

```text
SD:/games/ao486/<PackName>/
  <PackName>.vhd
  cd/
  floppy/   (if present)
```

CD mounts use `imgtry` paths like `/cd/Blood/BLOODCD1.cue` relative to that folder.

---

## 12. Quick start (copy-paste)

```bash
export EXODOS_COLLECTION=/mnt/net/exodos/eXoDOS
export DOSFORGE_DOSASSETS_DIR=~/Projects/dosforge/dosassets
cd ~/Projects/ExoDOSConverter

python3 -m packcli doctor
python3 -m packcli resolve doom blood
python3 -m packcli build -f recipes/gus-classics.yaml

# Existing VHD: switch sound
python3 -m packcli patch-autoexec \
  "out/mister-gus-pack/GUS_Classics/ao486/GUS Classics/GUS_Classics.vhd" \
  --audio gus
```

Or in Grok:

> /mister-pack create a GUS pack named Demo with DOOM and Blood; put output under out/demo
