import os
import shutil
from zipfile import ZipFile


def copySupportZips(gamesDir, scriptDir, logger):
    supportZips = ['(Manually Added Games).zip', '(Utilities and System Files).zip']
    for supportZip in supportZips:
        sourceZip = os.path.join(scriptDir, 'data', 'mister', supportZip)
        if os.path.exists(sourceZip):
            shutil.copy2(sourceZip, gamesDir)
        else:
            logger.log('  <WARNING> Missing MiSTer support archive: %s' % supportZip, logger.WARNING)


def extractFrontend(outputDir, scriptDir, logger):
    distroZipPath = os.path.join(scriptDir, 'data', 'mister', 'distro.zip')
    if not os.path.exists(distroZipPath):
        logger.log('  <ERROR> Missing MyMenu payload archive: %s' % distroZipPath, logger.ERROR)
        return False

    mymenuDir = os.path.join(outputDir, 'mymenu')
    legacyDistroDir = os.path.join(outputDir, 'distro')

    for directory in [mymenuDir, legacyDistroDir]:
        if os.path.exists(directory) and os.path.isdir(directory):
            shutil.rmtree(directory)

    logger.log('  Extracting MyMenu payload archive')
    with ZipFile(distroZipPath, 'r') as zipFile:
        zipFile.extractall(path=outputDir)

    if os.path.exists(legacyDistroDir) and not os.path.exists(mymenuDir):
        logger.log('  <WARNING> Legacy distro payload detected, renaming distro -> mymenu', logger.WARNING)
        os.rename(legacyDistroDir, mymenuDir)

    if os.path.exists(os.path.join(outputDir, 'MYMENU')) and not os.path.exists(mymenuDir):
        os.rename(os.path.join(outputDir, 'MYMENU'), mymenuDir)

    if not os.path.exists(mymenuDir):
        logger.log('  <ERROR> MyMenu payload extraction did not produce a mymenu/ directory', logger.ERROR)
        return False

    return True


def extractBootC(stagingRoot, scriptDir, logger, includeQemm=True):
    """Hydrate Top300-style C:\\DRIVERS (+ QEMM/DOS supplements) into the VHD staging root.

    Payload: ``data/mister/boot-c.zip`` (from BOOT-DOS98.vhd + adapted CONFIG/AUTOEXEC).
    Returns True when DRIVERS was staged; False if the archive is missing (caller may
    still write a minimal boot config).
    """
    zipPath = os.path.join(scriptDir, 'data', 'mister', 'boot-c.zip')
    if not os.path.isfile(zipPath):
        logger.log(
            '  <WARNING> Missing boot-c payload archive: %s '
            '(regenerate with scripts/extract_boot_c_from_vhd.py)' % zipPath,
            logger.WARNING,
        )
        return False

    logger.log('  Extracting Top300 boot-c payload (DRIVERS/QEMM/DOS + templates)')
    with ZipFile(zipPath, 'r') as zipFile:
        names = zipFile.namelist()
        for name in names:
            # Normalise zip members; skip directory entries.
            if not name or name.endswith('/'):
                continue
            # Optional QEMM skip for smaller packs.
            if not includeQemm and name.replace('\\', '/').upper().startswith('QEMM/'):
                continue
            # Do not extract root CONFIG/AUTOEXEC here — dosforgevhd installs
            # the adapted templates after protected-root stripping.
            base = os.path.basename(name).upper()
            if base in ('CONFIG.SYS', 'AUTOEXEC.BAT'):
                continue
            # Security: no path escape.
            dest = os.path.normpath(os.path.join(stagingRoot, name))
            if not dest.startswith(os.path.normpath(stagingRoot) + os.sep) and dest != os.path.normpath(stagingRoot):
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zipFile.open(name) as src, open(dest, 'wb') as out:
                shutil.copyfileobj(src, out)

    driversDir = os.path.join(stagingRoot, 'DRIVERS')
    if not os.path.isdir(driversDir):
        logger.log('  <ERROR> boot-c extract did not produce DRIVERS/', logger.ERROR)
        return False

    # Empty TEMP for AUTOEXEC SET TEMP/TMP
    os.makedirs(os.path.join(stagingRoot, 'TMP'), exist_ok=True)

    critical = [
        os.path.join(driversDir, 'XCDROM.SYS'),
        os.path.join(driversDir, 'HIRAM', 'HIRAM.EXE'),
        os.path.join(driversDir, 'SHSUCDX.COM'),
        os.path.join(driversDir, 'DOSKEY20.COM'),
        os.path.join(driversDir, 'SBCTL.EXE'),
    ]
    missing = [p for p in critical if not os.path.isfile(p)]
    # CTMOUSE case variants
    ctmouse = os.path.join(driversDir, 'CUTEPACK', 'CTMOUSE.EXE')
    ctmouse_l = os.path.join(driversDir, 'CUTEPACK', 'ctmouse.exe')
    if not os.path.isfile(ctmouse) and not os.path.isfile(ctmouse_l):
        missing.append(ctmouse)
    if missing:
        for p in missing:
            logger.log('  <WARNING> boot-c missing critical file: %s' % p, logger.WARNING)

    logger.log(
        '  boot-c staged: DRIVERS%s + DOS supplements + TMP'
        % (' + QEMM' if includeQemm else '')
    )
    return True


def bootCTemplateBytes(scriptDir, name):
    """Return bytes of CONFIG.SYS or AUTOEXEC.BAT from boot-c.zip, or None."""
    zipPath = os.path.join(scriptDir, 'data', 'mister', 'boot-c.zip')
    if not os.path.isfile(zipPath):
        return None
    target = name.upper()
    with ZipFile(zipPath, 'r') as zipFile:
        for member in zipFile.namelist():
            if os.path.basename(member).upper() == target:
                return zipFile.read(member)
    return None
