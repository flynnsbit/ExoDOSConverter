# Native-PC pack path (PicoMEM / PicoGUS / PicoIDE)

Packs built with `packcli` can target **MiSTer ao486** or **native PC** hardware.
Every pack **stages all driver trees** so a VHD can move between systems; only
the **active** `options.target` changes CONFIG/AUTOEXEC and game CD lines.

**Related:** [MISTER_PACK.md](MISTER_PACK.md) · skill `/mister-pack`

---

## Recipe option

```yaml
options:
  target: mister    # mister | picomem | picogus | picoide
  audio: gus        # sb | gus  (common env for all targets)
```

Env / config: `MISTER_PACK_TARGET` or `PACK_TARGET`, config key `target`.

| Target | Primary use | CD / media | Audio init |
|--------|-------------|------------|------------|
| **mister** | MiSTer ao486 | External `cd/` + `CALL imgtry` | `PMINIT /SB` or `/GUS` |
| **picogus** | PicoGUS card | USB FAT32 root + `PGUSCD` / `pgusinit /cdload` | BLASTER/ULTRASND + `PGUSINIT`; PMINIT if present |
| **picomem** | PicoMEM card | VHD/IMG via **BIOS disk select**; CD stub | `PMINIT /SB` or `/GUS` |
| **picoide** | Future | Same helpers as PicoGUS (skeleton) | Same as picogus |

---

## What is always on the VHD

### `C:\DRIVERS\` (boot-c + native)

| Path | Role |
|------|------|
| XCDROM.SYS, SHSUCDX, HIRAM, CTMOUSE, SBCTL, … | Generic DOS pack base |
| IMGTRY.BAT | MiSTer media mount |
| **PICOGUS\CDMKE.SYS** | Panasonic/MKE CD device driver (PicoGUS) |
| **PICOGUS\PGUSINIT.EXE** | Mode / CD list / load (PicoGUS) |
| **HW\PGUSCD.BAT** | Wrapper: `list` \| `load n` \| `eject` |
| **HW\PMCD.BAT** | PicoMEM CD stub |
| **HW\IMGTRY.BAT** | Forwards to MiSTer imgtry |
| **HW\README.HW** | Human reference on the disk |
| **HW\SET_HW.BAT** | Writes `HW.CFG` profile note |

### `C:\PICOMEM\` (from ISA-PicoMEM drivers)

| File | Role |
|------|------|
| **PMINIT.EXE** | `/sb 1`, `/gus 1` (PM2), adlib, cms, … |
| **PMEMM.EXE** | EMS: `DEVICE=PMEMM.EXE /n` |
| **PMDFS.EXE** / **PMDFS3.EXE** | Map SD/USB as network drives (`pmdfs S-D U-E`) |
| **PMMOUSE.EXE** | USB mouse |
| **PM2000.COM** / **NE2000.COM** | Packet drivers |
| **PICOMEM.EXE** | Board utility |
| **ASTCLOCK.COM** | RTC → DOS date |
| **SBCD\** | Creative SBCD.SYS + CD utilities |

### `C:\ULTRASND\`

GUS software tree (ULTRADIR). Staged on every pack for portability.

---

## PicoGUS CD workflow (user)

Sources: [PicoGUS CD-ROM Emulation wiki](https://github.com/polpo/picogus/wiki/CD%E2%80%90ROM-Emulation)

1. Firmware ≥ 3.0.0; mode **SB** or **USB** at boot:  
   `PGUSINIT /mode sb /save` or `/mode usb /save`
2. CONFIG.SYS (auto when `target: picogus`):  
   `DEVICE=C:\DRIVERS\PICOGUS\CDMKE.SYS /P:250 /Q`
3. AUTOEXEC: MSCDEX `/D:MSCD000` (injected when target is picogus/picoide)
4. Copy pack `cd/` images onto a **FAT32 USB stick root** (no subdirs; ISO or BIN/CUE)
5. `CALL C:\DRIVERS\HW\PGUSCD.BAT list` then `load n`  
   Or: `PGUSINIT /cdlist` · `/cdload n` · `/cdload 0` (eject)

Build still stages sibling `cd/<game>/` for organization; it does **not** bake a USB image.

---

## PicoMEM workflow (user)

Sources: [ISA-PicoMEM](https://github.com/FreddyVRetro/ISA-PicoMEM) drivers README

1. Put pack **VHD/IMG** on MicroSD; select disk in **PicoMEM BIOS** (prefer &lt; ~500 MB images for DOS 6.x comfort)
2. Boot DOS; audio: `PMINIT /SB 1` or `/GUS 1` (AUTOEXEC when target is picomem/mister)
3. Optional: `PMDFS S-D U-E` for SD/USB file access  
4. **CD-ROM emulation is planned** on PicoMEM 2 — use `PMCD.BAT help` stub; SBCD tools are on disk under `C:\PICOMEM\SBCD`

---

## Shared audio (sb | gus)

Same env on all targets:

| Mode | AUTOEXEC env | Then |
|------|--------------|------|
| **sb** | `BLASTER=A220 I7 D1 H5 P330 T6` | PMINIT `/SB 1` and/or PGUSINIT mode |
| **gus** | `ULTRASND=240,1,1,5,5` + `ULTRADIR=C:\ULTRASND` | PMINIT `/GUS 1` (PM2); PicoGUS GUS firmware |

---

## Example recipes

```yaml
# recipes/native-picogus-demo.yaml
name: PicoGUS Demo
games:
  - DOOM (1993)
options:
  target: picogus
  audio: gus
  boot: auto
  launcher: mymenu
```

```bash
python3 -m packcli build -f recipes/native-picogus-demo.yaml
python3 -m packcli rebuild-vhd ./pack --target picomem --audio sb
python3 -m packcli patch-autoexec pack.vhd --audio gus --target picogus
```

---

## Payload sources (redistribution)

| Artifact | Upstream |
|----------|----------|
| PGUSINIT.EXE | polpo/picogus release zip |
| CDMKE.SYS | https://picogus.com/drivers/cdmke.zip |
| PicoMEM tools | FreddyVRetro/ISA-PicoMEM `drivers/` |
| ULTRASND | converter `data/mister/ultrasnd` |

Firmware UF2 is **not** placed on the VHD — flash cards separately.
