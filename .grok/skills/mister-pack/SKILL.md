---
name: mister-pack
description: >
  Build production MiSTer ao486 packs from eXoDOS games via ExoDOSConverter +
  dosforge (VHD + external cd/floppy, MyMenu, optional GUS/PicoMEM). Use when
  the user runs /mister-pack, asks to "create a pack", "build a VHD", "MiSTer
  pack", "eXoDOS convert to VHD", or wants games on a bootable DOS disk image
  with MyMenu.
---

# mister-pack

Production path: **recipe → convert → dosforge VHD**. Stay in Grok CLI; do not open the converter GUI.

## Converter root

Prefer checkout: `/home/shawn/Projects/ExoDOSConverter` (or the repo this skill lives in).

```bash
export EXODOS_COLLECTION=/path/to/eXoDOS   # must contain eXo/eXoDOS/
export DOSFORGE_DOSASSETS_DIR=~/Projects/dosforge/dosassets
cd /home/shawn/Projects/ExoDOSConverter
```

## Commands (only these)

```bash
# One-time / session health
python3 -m packcli doctor
# or
python3 scripts/mister-pack doctor

# Resolve free-text titles to exact eXo names
python3 -m packcli resolve "doom" "blood" "duke nukem 3d"

# Build from recipe YAML
python3 -m packcli build -f recipes/gus-classics.yaml

# Rebuild VHD only (pack already has games/ + mymenu/)
python3 -m packcli rebuild-vhd out/mister-gus-pack/GUS_Classics --boot auto

# Patch AUTOEXEC on existing VHD (SB or GUS)
python3 -m packcli patch-autoexec path/to/pack.vhd --audio sb
python3 -m packcli patch-autoexec path/to/pack.vhd --audio gus
```

Optional config: `~/.config/mister-pack/config.toml` with `collection`, `dosassets`, `output`, **`audio = "sb"` or `"gus"`**.

| audio | Variables | PMINIT |
|-------|-----------|--------|
| `sb` | `BLASTER=A220 I7 D1 H5 P330 T6` | `/SB 1` |
| `gus` | `ULTRASND=240,1,1,5,5` + `ULTRADIR` (+ BLASTER kept) | `/GUS 1` |

Recipe `options.audio` overrides user config for a build.
## Workflow for a user prompt

1. **`doctor`** — if collection/dosforge/dosassets fail, fix env (do not invent paths).
2. **`resolve`** each fuzzy title → exact strings for the recipe `games:` list.
3. Write a recipe under `out/` or `recipes/` (YAML):

```yaml
name: My Pack
collection: ${EXODOS_COLLECTION}
output: ./out/mister-packs
games:
  - DOOM (1993)
  - Blood (1997)
options:
  launcher: mymenu
  audio: gus          # or sb
  boot: auto          # auto | msdos622 | freedos
  prefer_gus: true    # implied by audio: gus
```

4. **`build -f recipe.yaml`** and stream progress.
5. On success, print the pack folder to copy to MiSTer SD:

```text
<output>/<Name>/ao486/<NameOrVariant>/*.vhd
<output>/<Name>/ao486/<NameOrVariant>/cd/
```

## Defaults (already in boot-c / mistergus — do not re-litigate)

| Item | Value |
|------|--------|
| CONFIG menu default | EMM386, no NOAUTO |
| BLASTER | `A220 I7 D1 H5 P330 T6` |
| ULTRASND (GUS) | `240,1,1,5,5` (DMA 1,1 + IRQ **5,5** not 7,7) |
| After SET ULTRASND | `C:\PICOMEM\PMINIT.EXE /GUS 1` |
| ULTRADIR | `C:\ULTRASND` |
| Frontend | MyMenu, C:-only `MYMENU.INI` |
| CDs | External next to VHD (`cd/<dosname>/`), not inside image when convert works |
| Boot | `auto` → msdos622/FAT16 if fits; FreeDOS/FAT32 if oversized |

## Audio modes

- **`audio: sb`** — default SB16 env only.
- **`audio: gus`** — sets `prefer_gus`, stages ULTRASND + PICOMEM, applies eXo GUS presets, PMINIT.

## Failure playbooks

| Symptom | Action |
|---------|--------|
| No games matched | `resolve` title; use exact CSV name including year |
| Blood CD missing | Fixed in converter (`BLOOD121`→on-disk `BLOODCD1`); rebuild if old pack |
| dosforge boot assets | Point `DOSFORGE_DOSASSETS_DIR` at `dosassets` **root** or `msdos622`/`freedos` subdir with Disk1.img / KERNEL.SYS |
| FAT16 too small | Use `boot: auto` or `boot: freedos` |
| VHD create failed after convert | `rebuild-vhd` on pack dir with games/ + mymenu/ |
| Need env fix only | Patch AUTOEXEC on existing VHD (SET ULTRASND + PMINIT); no full rebuild |

## Do not

- Open ExoDOSConverter GUI for this path
- Run full dosforge/converter test suites for pack builds
- Clone eXoDOS into git
- Rebuild MyMenu from Pascal sources unless distro.zip is missing
- Invent game setup files — use eXo GUS folders + env defaults

## Example user lines → actions

| User says | You do |
|-----------|--------|
| `/mister-pack doctor` | `python3 -m packcli doctor` |
| pack DOOM + Duke with GUS | resolve → write recipe `audio: gus` → build |
| rebuild VHD only | `rebuild-vhd <packDir>` |
| add Blood to list | resolve Blood (1997), append recipe, rebuild full or convert+rebuild |

## Output checklist

After build, confirm:

- [ ] `.vhd` exists under `ao486/`
- [ ] `cd/` sibling present for CD games (Blood → `cd/Blood/BLOODCD1.*`)
- [ ] For GUS: VHD has `ULTRASND/`, `PICOMEM/`, AUTOEXEC has `ULTRASND=240,1,1,5,5` and `PMINIT /GUS 1`
