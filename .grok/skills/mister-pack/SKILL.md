---
name: mister-pack
description: >
  Build production MiSTer ao486 packs from eXoDOS games via ExoDOSConverter +
  dosforge (VHD + external cd/floppy, MyMenu, optional GUS/PicoMEM). Use when
  the user runs /mister-pack, asks to "create a pack", "build a VHD", "MiSTer
  pack", "eXoDOS convert to VHD", install/update pack tools, or wants games on
  a bootable DOS disk image with MyMenu. Open-source engines (dosforge +
  ExoDOSConverter) install/update via `packcli setup`; eXoDOS collection is
  user-supplied only (never downloaded).
---

# mister-pack — full feature & usage guide

Production path: **recipe → convert → dosforge VHD**. Stay in Grok CLI. Do **not** open the ExoDOSConverter GUI or run test suites for normal packs.

**CLI:** `python3 -m packcli …` or `python3 scripts/mister-pack …`  
**Slash:** `/mister-pack` (only after Grok can see this skill — not built into Grok)  
**Skill path:** `.grok/skills/mister-pack/SKILL.md` (synced docs: `docs/MISTER_PACK_SKILL.md`)  
**Fresh install (shell):** `docs/install_fresh.md`  
**Fresh install (Grok CLI, minimal):** `docs/install_fresh_grok.md`  
  — new users: clone this repo, start Grok from repo root, *then* `/mister-pack`  
**Native PC targets:** `docs/NATIVE_PC_PACK.md` — `options.target`: mister \| picomem \| picogus \| picoide  
  (all drivers staged every pack; CD helpers under `C:\DRIVERS\HW\`)

---

## 0. Open-source engines vs user data (critical)

| Category | What | How it is obtained |
|----------|------|--------------------|
| **Open-source engines** | **dosforge**, **ExoDOSConverter** (+ packcli Python deps) | **`python3 -m packcli setup`** — installs or updates to the latest from GitHub |
| **User-supplied data** | **eXoDOS collection**, **dosassets** (MS-DOS/FreeDOS install media) | **User local paths only** — never auto-downloaded |

- If dosforge or the converter is missing or outdated → run **`setup`** (or `setup --force`).
- If collection path is unknown → **ask the user once** for the eXoDOS root (must contain `eXo/eXoDOS/`). Do **not** search the web for game packs or attempt to fetch the collection.
- dosassets (boot floppies under `msdos622/` / `freedos/`) are also local; ask if missing.

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

### Bootstrap (preferred)

From any machine with Python 3.10+ and network:

```bash
# 1) Install or update open-source engines from GitHub
python3 -m packcli setup

# 2) Record your local eXoDOS + dosassets paths (never downloaded)
python3 -m packcli setup \
  --collection /path/to/eXoDOS \
  --dosassets ~/Projects/dosforge/dosassets \
  --audio gus

# 3) Verify
python3 -m packcli doctor
```

If you do not yet have a converter checkout, either:

- Clone once: `git clone https://github.com/flynnsbit/ExoDOSConverter.git && cd ExoDOSConverter`, then `python3 -m packcli setup`, or  
- Point `setup --converter-dir ~/Projects/ExoDOSConverter` and let setup clone/update there.

### What `setup` installs / updates

| Component | Source of truth | Action when outdated |
|-----------|-----------------|----------------------|
| **dosforge** | Latest **GitHub release** tag (`flynnsbit/dosforge`) | `pip install` from `git+…@vX.Y.Z` |
| **ExoDOSConverter** | **git master** tip (`flynnsbit/ExoDOSConverter`) | `git pull --ff-only` (or clone); `--force` → hard reset to `origin/master` |
| **packcli deps** | `requirements-packcli.txt` (modern PyYAML/Pillow/requests) | `pip install -r …` |

`setup` does **not** fetch eXoDOS games or DOS install floppies.

### What you must supply

| Path | Meaning | How to set |
|------|---------|------------|
| **collection** | eXoDOS root containing `eXo/eXoDOS/` | `setup --collection`, `config.toml`, or `EXODOS_COLLECTION` |
| **dosassets** | Folder with `msdos622/` and/or `freedos/` | `setup --dosassets`, `config.toml`, or `DOSFORGE_DOSASSETS_DIR` |

### Prerequisites (host)

| Need | Notes |
|------|--------|
| Python 3.10+ | packcli + converter |
| Network | First setup / updates (GitHub) |
| `git` | Clone/pull ExoDOSConverter |
| Linux `sudo -n` for NBD | Headless VHD create (doctor soft-warns if missing) |

### User config (`~/.config/mister-pack/config.toml`)

Written/updated by `setup --collection …` / `--dosassets …` / `--audio …`, or copy `recipes/example-config.toml`:

```toml
# User-supplied only — never auto-downloaded
collection = "/mnt/net/exodos/eXoDOS"
dosassets  = "/home/you/Projects/dosforge/dosassets"
output     = "/home/you/mister-out"
converter  = "/home/you/Projects/ExoDOSConverter"   # optional; set by setup

# Default AUTOEXEC sound when recipe omits options.audio:
#   "sb" or "gus"
audio = "sb"
```

**Precedence (highest wins):** recipe `options.audio` → env `MISTER_PACK_AUDIO` → config.toml `audio` → `sb`.

Env overrides for paths: `EXODOS_COLLECTION`, `DOSFORGE_DOSASSETS_DIR`, `MISTER_PACK_OUT`, `MISTER_PACK_CONVERTER`.

### Health check

```bash
python3 -m packcli doctor
```

Must report OK for: Python, dosforge, boot-c.zip, distro.zip, eXoDOSv6.csv, collection, dosassets.  
If engines are missing/old → **`python3 -m packcli setup`**.  
If collection fails → **ask user for path**; do not download games.

---

## 3. CLI reference

### `setup` — install / update engines (+ optional path config)

```bash
python3 -m packcli setup
python3 -m packcli setup --force
python3 -m packcli setup --collection /path/to/eXoDOS --dosassets /path/to/dosassets --audio gus
python3 -m packcli setup --converter-dir ~/Projects/ExoDOSConverter
python3 -m packcli setup --skip-dosforge    # only update converter
python3 -m packcli setup --skip-converter   # only update dosforge
```

| Flag | Meaning |
|------|---------|
| `--force` | Reinstall/update even if versions match; converter: `git reset --hard origin/master` |
| `--converter-dir` | Clone/update target (default: this tree or `~/Projects/ExoDOSConverter`) |
| `--collection` | Save eXoDOS root to config (**not** downloaded) |
| `--dosassets` | Save dosassets path to config (**not** downloaded) |
| `--audio sb\|gus` | Default AUTOEXEC audio in config |
| `--skip-dosforge` / `--skip-converter` | Update only one engine |

Runs a post-setup **doctor** when possible.

### `doctor`

```bash
python3 -m packcli doctor
```

Checks collection path, dosforge, converter payloads (`boot-c.zip`, `distro.zip`, ULTRASND, PICOMEM), dosassets, sudo.  
On failure, prints hint to run `setup` and/or set `--collection`.

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
  target: mister            # mister | picomem | picogus | picoide
  audio: gus                # sb | gus  (see §5; common to all targets)
  boot: auto                # auto | msdos622 | freedos
  prefer_gus: true          # implied when audio: gus
  pminit_gus: true          # implied when audio: gus
  include_qemm: true
  include_ultrasnd: true    # always staged for portability
  include_picomem: true     # always staged for portability
  long_game_folder: true
  generate_readme_ans: true
```

Hardware targets (see `docs/NATIVE_PC_PACK.md`): **mister** = imgtry CD; **picogus** = CDMKE + PGUSCD/USB; **picomem** = BIOS VHD + PMINIT; **picoide** = stub like picogus. Every pack ships `C:\DRIVERS\PICOGUS\`, `C:\DRIVERS\HW\`, `C:\PICOMEM\`, `C:\ULTRASND\`.

Shipped example: `recipes/gus-classics.yaml` (11 GUS classics).

### Recipe fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | yes | Pack / VHD base name |
| `games` | yes | Exact eXo titles (from `resolve`) |
| `collection` | if env/config unset | eXoDOS root (user path) |
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

### A. First-time / “is my machine ready?” / “install or update tools”

1. Run **`python3 -m packcli setup`** — install or update **dosforge** (latest release) and **ExoDOSConverter** (git master). Network required.
2. If collection path is unknown, **ask the user once**: “Where is your eXoDOS root?” (folder that contains `eXo/eXoDOS/`). **Never download the collection.**
3. If dosassets unknown, ask for that path (or default after dosforge install if present under the dosforge tree).
4. `python3 -m packcli setup --collection /their/path --dosassets /their/dosassets` (optional `--audio sb|gus`).
5. `python3 -m packcli doctor` — all required checks green before first build.
6. Later sessions: re-run **`setup`** when the user asks to update tools, or when doctor shows missing/outdated engines.

### B. “Make a pack with these games…”

1. `doctor` if not green this session; if engines missing → `setup` first.
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
| Install / update tools / get latest dosforge | `python3 -m packcli setup` (+ ask for eXoDOS path if unset) |
| Update ExoDOSConverter only | `python3 -m packcli setup --skip-dosforge` |
| Update dosforge only | `python3 -m packcli setup --skip-converter` |
| Where should my eXoDOS go? | Explain: local path only; never auto-downloaded; save with `setup --collection` |
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
| `doctor` missing dosforge / old engines | `python3 -m packcli setup` (or `--force`) |
| `doctor` collection fail | Ask user for eXoDOS root; `setup --collection /path` or set `EXODOS_COLLECTION` / config `collection` (`eXo/eXoDOS` must exist) |
| No games matched | `resolve`; use exact CSV title with year |
| Blood CD empty | Conf typo `BLOOD121` vs on-disk `BLOODCD1` — fixed in converter; rebuild pack if old |
| dosforge “boot assets” error | `DOSFORGE_DOSASSETS_DIR` = dosassets **root** (with `msdos622/` / `freedos/`) |
| FAT16 / size error | `boot: auto` or `boot: freedos` |
| Convert OK, VHD fail | `rebuild-vhd` with correct `--dosassets` and `--audio` |
| GUS IRQ 7 in game | Env is 5,5; eXo presets patched when `prefer_gus`; re-apply via rebuild or new build |
| Need only AUTOEXEC sound change | `patch-autoexec --audio sb\|gus` |
| `git pull` failed on converter | Local changes; commit/stash or `setup --force` (hard reset) |
| pip / Pillow pin errors | Use `requirements-packcli.txt` via `setup` (not legacy `requirements.txt` freeze) |

---

## 10. What not to do

- Do not open the converter GUI for this workflow  
- Do not run full dosforge/converter test suites for pack builds  
- Do **not** download or ship the eXoDOS game collection — user path only  
- Do not clone eXoDOS into git or ship game zips  
- Do not rebuild MyMenu from Pascal unless `distro.zip` is missing  
- Do not invent setup files — use eXo GUS folders + standard env  
- Do not invent collection/dosassets paths; ask user or use config  
- Do not manually pin ancient converter `requirements.txt` (Pillow 9.x) for packcli; use `setup` / `requirements-packcli.txt`  

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
# Engines: latest dosforge release + ExoDOSConverter master
python3 -m packcli setup \
  --collection /mnt/net/exodos/eXoDOS \
  --dosassets ~/Projects/dosforge/dosassets \
  --audio gus

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

> /mister-pack install or update tools, then doctor
