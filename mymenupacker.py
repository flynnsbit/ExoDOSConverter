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
