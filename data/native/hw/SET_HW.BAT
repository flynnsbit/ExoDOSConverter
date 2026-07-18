@ECHO OFF
REM Optional: record preferred hardware profile on the VHD (for humans/scripts).
REM Does not rewrite game batches — rebuild pack with options.target for that.
REM Usage: CALL SET_HW.BAT mister|picomem|picogus|picoide

IF "%1"=="" GOTO USAGE
ECHO %1> C:\DRIVERS\HW\HW.CFG
ECHO Hardware profile saved to C:\DRIVERS\HW\HW.CFG : %1
GOTO END

:USAGE
ECHO Usage: SET_HW.BAT mister ^| picomem ^| picogus ^| picoide
IF EXIST C:\DRIVERS\HW\HW.CFG TYPE C:\DRIVERS\HW\HW.CFG

:END
