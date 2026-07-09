# MiSTer end-to-end test (dosforge VHD + MyMenu)

This is the shortest path from **game selection** to a **bootable pack** with:

- MS-DOS on a fixed VHD (via `dosforge create`)
- Top300-style `CONFIG.SYS` (HIRAM/EMM386/QEMM menu) + `AUTOEXEC.BAT` → drivers → **MyMenu**
- `C:\DRIVERS` + DOS supplements from `data/mister/boot-c.zip` (hydrated with MyMenu)
- `MYMENU.INI` → `DRV = GAMES;C:\GAMES\`
- Per-game `autorun.bat` + `README.ANS` + `1_Start.bat`
- External `cd/` / `floppy/` / `bootdisk/` next to the VHD (when present)

## Boot-C payload (Top300 drivers)

Every dosforge VHD stages **C:-only** boot files adapted from
[Top300_updates `_C`](https://github.com/flynnsbit/Top300_updates/tree/main/_C):

| Path | Role |
|------|------|
| `data/mister/boot-c.zip` | DRIVERS + QEMM + DOS supplements + CONFIG/AUTOEXEC templates |
| `data/mister/distro.zip` | MyMenu frontend |

Regenerate `boot-c.zip` from a BOOT-DOS98 VHD (same image as the classic Top300 boot disk):

```bash
python3 scripts/extract_boot_c_from_vhd.py \
  --vhd "/path/to/IDE 0-0 BOOT-DOS98.vhd" \
  --out data/mister/boot-c.zip
```

Known sources:

- Local template: `vhdtemplate/IDE 0-0 BOOT-DOS98.vhd` (gitignored)
- SMB: `smb://denpc/18tb/MiSTer Projects/top-300-final/IDE 0-0 BOOT-DOS98.vhd`

AUTOEXEC ends with MyMenu (no secondary `E:` VHD). Optional conf:
`misterIncludeQemm=false` skips the QEMM tree to shrink the pack.

## Prerequisites

1. **ExoDOSConverter** checkout (this repo)
2. **dosforge** on PATH (`pip install -e ../dosforge` from sibling clone)
3. **dosassets** for the boot mode (default `msdos622`):
   - `~/Projects/dosforge/dosassets/msdos622/` with install floppies, **or**
   - conf key `misterDosforgeBootAssets=...`
4. An **eXoDOS v6** collection with at least one game **zip** under `eXo/eXoDOS/`
   (selection names come from the converter CSV / bat titles, e.g. `Tris (1997)`, not always the XML short title)
5. Linux: non-interactive `sudo` for NBD (`sudo -n true` should work), **or** run after `sudo -v`
6. `data/mister/boot-c.zip` present (see above)

## GUI / TUI

1. Set collection path → eXoDOS root  
2. Conversion type → **MiSTer**  
3. Select one or more games  
4. Proceed (multi-game: enter pack name)  
5. Output: `<outputDir>/<build>/ao486/<name>/<name>.vhd`

Optional conf (`conf/conf-exo.conf`):

```
misterUseDosforge = true
misterLauncher = mymenu
misterBootMode = msdos622
misterDosInstallProfile = minimal
misterGenerateReadmeAns = true
misterDosforgeBootAssets = /path/to/dosassets/msdos622
misterIncludeQemm = true
```

`misterLauncher=none` restores “boot straight into the only game” for single-game packs.

## Headless smoke script

```bash
cd /path/to/ExoDOSConverter
python3 scripts/e2e_mister_smoke.py \
  --collection /path/to/eXoDOS \
  --title "Tris (1997)" \
  --out /tmp/edc-e2e \
  --boot-assets ~/Projects/dosforge/dosassets/msdos622
```

Exit 0 means all layout checks passed (MyMenu, AUTOEXEC, GAMES, autorun, README.ANS, COMMAND.COM).

## What “good” looks like on the VHD

| Path | Role |
|------|------|
| `C:\CONFIG.SYS` | Top300 multi-config menu (default HIRAM) |
| `C:\AUTOEXEC.BAT` | Drivers from `C:\DRIVERS`; MyMenu loop at end |
| `C:\DRIVERS\` | Mouse, CD, SBCTL, HIRAM, etc. |
| `C:\DOS\HIMEM.SYS` | Staged supplement (required by CONFIG) |
| `C:\RUNMENU.BAT` | Loads `DOSLFN.COM`, runs `MYMENU\MENU.BAT` (loop) |
| `C:\MYMENU\` | MyMenu binaries + `MYMENU.INI` |
| `C:\GAMES\<Title>\` | Game files, `autorun.bat`, `1_Start.bat`, `README.ANS` |
| `C:\COMMAND.COM` | Non-zero (~54 KB for MS-DOS 6.22) |

## Hardware / QEMU

Copy the whole `ao486/<name>/` folder (VHD + any `cd`/`floppy`/`bootdisk` siblings) to the MiSTer SD card under ao486, or boot the VHD in QEMU/86Box with IDE HDD = that VHD.
