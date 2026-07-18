@ECHO OFF
REM PicoMEM CD helper (stub)
REM PicoMEM CD-ROM emulation is planned upstream (PicoMEM 2).
REM Today: attach pack VHD/IMG via PicoMEM BIOS disk select from MicroSD.
REM Optional: SBCD stack under C:\PICOMEM\SBCD for some SB-style CD setups.
REM
REM Usage (future):
REM   CALL C:\DRIVERS\HW\PMCD.BAT list
REM   CALL C:\DRIVERS\HW\PMCD.BAT load <path-or-index>
REM
REM See C:\DRIVERS\HW\README.HW and C:\PICOMEM\ (PMINIT, PMDFS, SBCD)

IF /I "%1"=="help" GOTO HELP
IF /I "%1"=="" GOTO HELP
ECHO PMCD: PicoMEM CD mount CLI not available yet.
ECHO       Mount the pack disk image in the PicoMEM BIOS, or use PGUSCD
ECHO       if this machine has a PicoGUS (drivers are on this VHD).
GOTO END

:HELP
ECHO PMCD.BAT - PicoMEM CD helper (stub)
ECHO   VHD/IMG: select disk image in PicoMEM BIOS (MicroSD)
ECHO   CD:      wait for upstream PicoMEM CD support
ECHO   Audio:   C:\PICOMEM\PMINIT.EXE /SB 1  or  /GUS 1
ECHO   SD/USB:  C:\PICOMEM\PMDFS.EXE S-D U-E
GOTO END

:END
