# PicoGUS DOS tools (staged into C:\DRIVERS\PICOGUS\)

| File | Source | Role |
|------|--------|------|
| **PGUSINIT.EXE** | [polpo/picogus](https://github.com/polpo/picogus) release v4.1.1 | Mode, GUS, CD image list/load |
| **CDMKE.SYS** | [picogus.com/drivers/cdmke.zip](https://picogus.com/drivers/cdmke.zip) | Panasonic/MKE CD-ROM device driver |
| **CDMKE.TXT** | same zip | Upstream driver notes |

## CONFIG.SYS / AUTOEXEC (when pack target is picogus)

```bat
DEVICE=C:\DRIVERS\PICOGUS\CDMKE.SYS /P:250 /Q
```

```bat
MSCDEX /D:MSCD000
REM optional: C:\DRIVERS\PICOGUS\PGUSINIT.EXE /mode sb /save
```

## CD image management (USB stick)

- FAT32 USB only; images on **root** (ISO or BIN/CUE).
- `PGUSINIT /cdlist` · `/cdload n` · `/cdload 0` (eject) · `/cdauto 0|1`
- See: https://github.com/polpo/picogus/wiki/CD‐ROM-Emulation

Firmware UF2 is **not** shipped on the VHD (flash the card separately).
