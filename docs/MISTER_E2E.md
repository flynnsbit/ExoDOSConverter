# MiSTer end-to-end test (dosforge VHD + MyMenu)

This is the shortest path from **game selection** to a **bootable pack** with:

- MS-DOS on a fixed VHD (via `dosforge create`)
- `AUTOEXEC.BAT` → `AUTORUN_EDC.BAT` → **MyMenu**
- `MYMENU.INI` → `DRV = GAMES;C:\GAMES\`
- Per-game `autorun.bat` + `README.ANS` + `1_Start.bat`
- External `cd/` / `floppy/` / `bootdisk/` next to the VHD (when present)

## Prerequisites

1. **ExoDOSConverter** checkout (this repo)
2. **dosforge** on PATH (`pip install -e ../dosforge` from sibling clone)
3. **dosassets** for the boot mode (default `msdos622`):
   - `~/Projects/dosforge/dosassets/msdos622/` with install floppies, **or**
   - conf key `misterDosforgeBootAssets=...`
4. An **eXoDOS v6** collection with at least one game **zip** under `eXo/eXoDOS/`
   (selection names come from the converter CSV / bat titles, e.g. `Tris (1997)`, not always the XML short title)
5. Linux: non-interactive `sudo` for NBD (`sudo -n true` should work), **or** run after `sudo -v`

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
| `C:\AUTOEXEC.BAT` | Calls `AUTORUN_EDC.BAT` |
| `C:\AUTORUN_EDC.BAT` | Loads DOSLFN (if present), runs `MYMENU\MENU.BAT` |
| `C:\MYMENU\` | MyMenu binaries + `MYMENU.INI` |
| `C:\GAMES\<Title>\` | Game files, `autorun.bat`, `1_Start.bat`, `README.ANS` |
| `C:\COMMAND.COM` | Non-zero (~54 KB for MS-DOS 6.22) |

## Hardware / QEMU

Copy the whole `ao486/<name>/` folder (VHD + any `cd`/`floppy`/`bootdisk` siblings) to the MiSTer SD card under ao486, or boot the VHD in QEMU/86Box with IDE HDD = that VHD.
