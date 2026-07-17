import os
import util
import shutil
import ntpath
import platform
import misterbatrules
import misteroverrides
from PIL import ImageFont
from PIL import Image
from PIL import ImageDraw


# Removed unused CDs (paths come from data/mister/overrides.csv)
def removeUnusedCds(game, localGameDataOutputDir, logger, scriptDir=None):
    if scriptDir is None:
        # Best-effort: walk up from this module to the converter root.
        scriptDir = os.path.dirname(os.path.abspath(__file__))
    paths = misteroverrides.unused_cd_paths(scriptDir, game, logger=logger)
    if not paths:
        return
    for rel in paths:
        cue = os.path.join(localGameDataOutputDir, util.localOSPath(rel))
        cueDir = os.path.dirname(cue)
        # The unused_cd map carries v5-era relative paths (e.g. "..\\WC\\cd") that
        # may not exist in the eXoDOS v6 extracted layout. Skip gracefully rather
        # than crashing the whole game conversion on a missing cleanup target.
        if not os.path.isdir(cueDir):
            logger.log("      no unused-cd cleanup dir for %s (%s); skipping"
                       % (game, cueDir), logger.WARNING)
            continue
        cdFiles = [file for file in os.listdir(cueDir) if
                   os.path.splitext(ntpath.basename(cue))[0] == os.path.splitext(file)[0]
                   and os.path.splitext(file)[-1].lower() in ['.ccd', '.sub', '.cue', '.iso', '.img', '.bin']]
        for cdFile in cdFiles:
            logger.log("      remove unused cd file %s" % cdFile)
            os.remove(os.path.join(cueDir, cdFile))


def ensure_cwd_is_game_payload(gGator):
    """If <dosname> still exists under the game folder, inject ``cd <dosname>``.

    Safety net when zip flatten did not run. eXoDOS mounts C: at the dosname
    folder; MyMenu starts with CWD at the LFN parent, so relative EXE lines in
    1_Start.bat miss the payload without this cd.
    """
    game_root = gGator.getLocalGameOutputDir()
    dosname = gGator.game
    nested = os.path.join(game_root, dosname)
    if not os.path.isdir(nested):
        return
    start_path = os.path.join(game_root, '1_Start.bat')
    if not os.path.isfile(start_path):
        return
    with open(start_path, 'r', encoding='utf-8', errors='replace') as fh:
        lines = fh.readlines()
    # Already has a cd into dosname (any case, optional quotes)
    for line in lines:
        stripped = line.lstrip('@ \t').rstrip('\r\n')
        if stripped.lower().startswith('cd '):
            target = stripped[3:].strip().strip('"').strip("'")
            # strip trailing \ or /
            target = target.rstrip('\\/')
            if target.lower() == dosname.lower() or target.lower() == '.\\' + dosname.lower():
                return
    # Insert after leading media / imgset lines so mounts stay at pack paths,
    # then enter the game payload for relative EXEs and nested cds.
    insert_at = 0
    for i, line in enumerate(lines):
        s = line.lstrip('@ \t').lower()
        if (
            s.startswith('imgset')
            or s.startswith('call imgtry')
            or s.startswith('imgmount')
            or s.startswith('mount ')
            or s.startswith('@jchoice')
            or s.startswith('jchoice')
            or s.strip() == ''
            or s.startswith('rem ')
            or s.startswith('echo ')
        ):
            insert_at = i + 1
            continue
        break
    cd_line = 'cd %s\r\n' % dosname
    lines.insert(insert_at, cd_line)
    with open(start_path, 'w', encoding='utf-8', newline='') as fh:
        fh.writelines(lines)
    gGator.logger.log(
        '      inject "cd %s" into 1_Start.bat (nested payload still present)' % dosname
    )


# Creates launch.bat and handles mount and imgmount paths
def batsAndMounts(gGator):
    dosboxBat = open(os.path.join(gGator.getLocalGameOutputDir(), "dosbox.bat"), 'r')
    launchBat = open(os.path.join(gGator.getLocalGameOutputDir(), "1_Start.bat"), 'w', newline='\r\n')
    lines = dosboxBat.readlines()
    for line in lines:
        line = line.lstrip('@ ').rstrip(' \n\r')
        if line.lower() != 'c:' and not line.lower().startswith('path=') and not line.lower().startswith('path ='):
            if line.startswith("imgmount"):
                launchBat.write(convertImgMount(line, gGator))
            elif line.startswith("mount") and not line.lower().startswith('mountain'):
                launchBat.write(convertMount(line, gGator))
            elif line.startswith("boot") and line != 'boots':
                if line == 'boot -l c':
                    launchBat.write('imgset r\n')
                elif line != 'boot' and line != 'boot -l a':
                    launchBat.write(convertBoot(line, gGator))
                else:
                    gGator.logger.log('      <ERROR> Impossible to convert "%s" command' % line, gGator.logger.ERROR)
                    launchBat.write(line + '\n')
            elif line.lower() in ['d:', 'f:', 'g:', 'h:', 'i:', 'j:', 'k:']:
                launchBat.write('f:\n')
            elif line.lower() == 'call run' or line.lower() == 'call run.bat':
                script_dir = getattr(gGator, 'scriptDir', os.path.dirname(os.path.abspath(__file__)))
                if misteroverrides.needs_run_bat_handling(script_dir, gGator.game, logger=gGator.logger):
                    handleRunBat(gGator)
                # Always terminate the line — missing CRLF here produced the
                # classic "call runcall run" / "call run.batcall run.bat" bug.
                launchBat.write(line + '\n')
            else:
                launchBat.write(line + '\n')
    # Change imgmount iso command to imgset ide10 cdgames/gamefolder/game.iso
    # Include imgset in the outputDir ?
    # Convert imgmount or mount of floppy to imgset fdd0 /floppy/filename.img
    launchBat.close()
    dosboxBat.close()
    createSetupBat(gGator)
    createEditBat(gGator)
    os.remove(os.path.join(gGator.getLocalGameOutputDir(), 'dosbox.bat'))

    # If flatten failed and payload still lives under <dosname>/, ensure 1_Start
    # cds into it (MyMenu CWD is the LFN folder, not the dosname subfolder).
    ensure_cwd_is_game_payload(gGator)

    # Phase D5 rules engine: rewrite imgset -> CALL imgtry with CHD-fallback chain (R1),
    # pause -> @jchoice (R2), drop dummy directory-unmount lines.
    # Applied to all generated/cloned bats; R1 only fires on imgset lines so eXoDOS
    # source bats without imgset (most of them) pass through untouched.
    for bat_name in ('1_Start.bat', '3_Setup.bat', 'run.bat'):
        bat_path = os.path.join(gGator.getLocalGameOutputDir(), bat_name)
        if not os.path.isfile(bat_path):
            # run.bat for many games is in the data subdir, not the game output root
            bat_path = os.path.join(gGator.getLocalGameDataOutputDir(), bat_name)
        if os.path.isfile(bat_path):
            n_in, n_out, n_dropped = misterbatrules.apply_rules_to_file(bat_path)
            if n_dropped > 0:
                gGator.logger.log(
                    "      rules: dropped %i dummy imgset lines from %s"
                    % (n_dropped, bat_name))


# Treat run.bat command inside game directory
def handleRunBat(gGator):
    runBat = os.path.join(gGator.getLocalGameDataOutputDir(), 'run.bat')
    if os.path.exists(runBat):
        runFile = open(runBat, 'r')
        runFileClone = open(runBat + '1', 'w', newline='\r\n')
        # Clone run.bat and only modify imgmount lines
        # Add some hardcoded lines which are impossible to handle
        handled = {
            'imgmount d ".\\cd\\comma2.iso" ".\\cd\\comma1.iso" ".\\cd\\cover3.cue" -t cdrom': 'imgset ide10 "/cd/comcon/comma2.iso"',
            'imgmount d ".\\cd\\cover3.cue" ".\\cd\\comma2.iso" ".\\cd\\comma1.iso" -t cdrom': 'imgset ide10 "/cd/comcon/cover3.cue"',
            'imgmount d ".\\cd\\redal2.iso" ".\\cd\\redal1.iso" ".\\cd\\redal3.cue" ".\\cd\\redal4.cue" -t cdrom':
                'imgset ide10 "/cd/comconra/redal2.iso"',
            'imgmount d ".\\cd\\redal4.cue" ".\\cd\\redal1.iso" ".\\cd\\redal2.iso" ".\\cd\\redal3.cue" -t cdrom':
                'imgset ide10 "/cd/comconra/redal4.cue"',
            'imgmount d ".\\cd\\redal3.cue" ".\\cd\\redal1.iso" ".\\cd\\redal2.iso" ".\\cd\\redal4.cue" -t cdrom':
                'imgset ide10 "/cd/comconra/redal3.cue"',
            'imgmount d .\\cd\\redal4.cue -t cdrom': 'imgset ide10 "/cd/comconra/redal4.cue"'
        }
        for cmdline in runFile.readlines():
            cmdline = cmdline.lstrip('@ ').rstrip(' \n\r')
            if cmdline.lower().startswith("imgmount "):
                if cmdline not in handled:
                    handled[cmdline] = convertImgMount(cmdline, gGator)
                runFileClone.write(handled[cmdline] + '\n')
            elif cmdline.lower().startswith("config "):
                converted_sound_command = convertSoundConfig(cmdline)
                runFileClone.write(converted_sound_command + '\n')
            else:
                runFileClone.write(cmdline + '\n')
        runFileClone.close()
        runFile.close()
        # Delete runbat and rename runbat clone to runbat
        os.remove(os.path.join(gGator.getLocalGameDataOutputDir(), 'run.bat'))
        os.rename(os.path.join(gGator.getLocalGameDataOutputDir(), 'run.bat1'), os.path.join(gGator.getLocalGameDataOutputDir(), 'run.bat'))
    else:
        gGator.logger.log('    <ERROR> run.bat not found', gGator.logger.ERROR)


# Convert sound command for MiSTeR
def convertSoundConfig(line):
    if 'mididevice' in line:
        if 'mt32' in line:
            return 'mt32-pi -m -v'
        elif 'fluidsynth' in line:
            return 'mt32-pi -g -v'
        elif 'default' in line:
            return 'mt32-pi -g -v'
    return 'REM ' + line


# Convert imgmount command for MiSTeR
def convertImgMount(line, gGator):
    return handlesFileType(line, 2, gGator)


# Convert mount command for MiSTeR
def convertMount(line, gGator):
    return handlesFileType(line, 2, gGator)


# Convert boot command for MiSTeR
def convertBoot(line, gGator):
    return handlesFileType(line, 1, gGator)


# Determine type of files
def handlesFileType(line, pathPos, gGator):
    params = line.split(' ')
    # TODO Boot command without parameter will crash here, needs to be parsed properly
    path = params[pathPos].replace('"', '')
    if params[0] in ['imgmount', 'mount']:
        if params[-1].rstrip('\n\r ') == 'cdrom' or params[-1].rstrip('\n\r ') == 'iso':
            localPath = locateMountedFiles(path, gGator)
            misterCommand = convertCD(localPath, gGator, params[1])
            # params size > 5 and not extras param like -fs ?
            if len(params) > 5 and params[3] != '-t':
                i = 3
                while i < (len(params) - 2):
                    print(params[i])
                    localPath = locateMountedFiles(params[i].replace('"', ''), gGator)
                    # Only move the other CDs
                    convertCD(localPath, gGator, params[1])
                    i = i + 1
            return misterCommand
        elif params[-1].rstrip('\n\r ') == 'floppy':
            localPath = locateMountedFiles(path, gGator)
            misterCommand = convertFloppy(localPath, gGator, params[1])
            # Multi-disk floppy imgmount: move sibling images too (e.g. CKeen6
            # ALIENS_D1/D2/D3). Only the first image gets the imgset line.
            if len(params) > 5 and params[3] != '-t':
                i = 3
                while i < (len(params) - 2):
                    sibling = locateMountedFiles(params[i].replace('"', ''), gGator)
                    convertFloppy(sibling, gGator, params[1], emit_command=False)
                    i = i + 1
            return misterCommand
        else:  # Treat default version as cd
            localPath = locateMountedFiles(path, gGator)
            if params[1].rstrip('\n\r ') == 'c':
                return convertBootDisk(localPath, gGator)
            else:
                return convertCD(localPath, gGator)
    else:  # Boot command
        localPath = locateMountedFiles(path, gGator)
        return convertFloppy(localPath, gGator, 'a')


# Locate mounted files
def locateMountedFiles(path, gGator):
    if platform.system() == 'Windows':
        path = path.replace('/', '\\')

    # Normalise leading .\ / ./ so joins don't lose the game root.
    clean = path.replace('/', os.sep).replace('\\', os.sep)
    while clean.startswith('.' + os.sep):
        clean = clean[2:]
    if clean.startswith(os.sep):
        clean = clean.lstrip(os.sep)

    candidates = [
        util.localOSPath(os.path.join(gGator.getLocalGameOutputDir(), clean)),
        util.localOSPath(os.path.join(gGator.getLocalGameDataOutputDir(), clean)),
        util.localOSPath(os.path.join(gGator.outputDir, clean)),
        # Conf rewrite often drops the dosname folder (.\eXoDOS\CKeen6\floppy\X
        # → .\floppy\X). Game data lives under <title>/<dosname>/floppy/X.
        util.localOSPath(os.path.join(gGator.getLocalGameOutputDir(), gGator.game, clean)),
        util.localOSPath(os.path.join(gGator.getLocalGameDataOutputDir(), gGator.game, clean)),
    ]
    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    # Source bats may still carry ".\eXoDOS\<dosname>\..." — strip and retry.
    strippedPath = __stripExoLayoutPrefix__(path)
    if strippedPath is not None:
        for root in (
            gGator.getLocalGameOutputDir(),
            gGator.getLocalGameDataOutputDir(),
        ):
            candidate = util.localOSPath(os.path.join(root, strippedPath))
            if os.path.exists(candidate):
                return candidate
            # Also try without the dosname segment (already under game output).
            parts = [p for p in strippedPath.replace('/', os.sep).split(os.sep) if p]
            if len(parts) >= 2 and parts[0].lower() == str(gGator.game).lower():
                candidate = util.localOSPath(os.path.join(root, *parts[1:]))
                if os.path.exists(candidate):
                    return candidate

    # Basename walk under the game folder (last resort for rewritten paths).
    base = ntpath.basename(path)
    if base:
        for root in (gGator.getLocalGameOutputDir(), gGator.getLocalGameDataOutputDir()):
            if not os.path.isdir(root):
                continue
            for dirpath, _dirs, files in os.walk(root):
                if base in files:
                    return os.path.join(dirpath, base)
                # Case-insensitive basename match (eXo confs sometimes wrong case).
                base_l = base.lower()
                for f in files:
                    if f.lower() == base_l:
                        return os.path.join(dirpath, f)

    # eXo conf typo / rename: e.g. Blood dosbox.conf says BLOOD121.CUE but the
    # zip ships BLOODCD1.cue/.img. If the path points under cd/, pick the only
    # (or best) disc image present so convertCD still moves external media.
    # Note: cleaned paths look like "cd/BLOOD121.CUE" (no leading slash), so
    # match "cd/" prefix / path segment, not only "/cd/".
    clean_l = clean.lower().replace('\\', '/')
    path_parts = [p for p in clean_l.split('/') if p]
    is_cd_path = (
        clean_l == 'cd'
        or clean_l.startswith('cd/')
        or clean_l.endswith('/cd')
        or '/cd/' in clean_l
        or 'cd' in path_parts
    )
    if is_cd_path:
        for root in (gGator.getLocalGameOutputDir(), gGator.getLocalGameDataOutputDir()):
            cd_dir = os.path.join(root, 'cd')
            if not os.path.isdir(cd_dir):
                # Also try <dosname>/cd after incomplete flatten
                cd_dir = os.path.join(root, str(gGator.game), 'cd')
            if not os.path.isdir(cd_dir):
                continue
            disc_ext = {'.cue', '.iso', '.img', '.bin', '.ccd'}
            discs = [
                f for f in os.listdir(cd_dir)
                if os.path.splitext(f)[1].lower() in disc_ext
            ]
            if not discs:
                continue
            # Prefer .cue when present (imgset/imgtry), else first disc image.
            cues = [f for f in discs if f.lower().endswith('.cue')]
            pick = sorted(cues)[0] if cues else sorted(discs)[0]
            found = os.path.join(cd_dir, pick)
            gGator.logger.log(
                '      CD path %s missing; using on-disk %s' % (path, found)
            )
            return found

    # Return the primary candidate even if missing so callers can log it.
    return candidates[0]


# Strips a leading "[.\]eXoDOS\<dosname>\" segment from an eXoDOS source path so
# it matches the flattened game output layout. Returns None if no such prefix.
def __stripExoLayoutPrefix__(path):
    parts = [p for p in path.replace('/', '\\').split('\\') if p not in ('', '.')]
    if len(parts) >= 3 and parts[0].lower() == 'exodos':
        return os.path.join(*parts[2:])
    return None


# Convert cds file
def convertCD(localPath, gGator, letter='d'):
    # Move cds file
    # TODO see if we can do makedirs below instead
    if not os.path.exists(os.path.join(gGator.outputDir, 'cd')):
        os.mkdir(os.path.join(gGator.outputDir, 'cd'))

    if os.path.isdir(localPath):
        return convertMountedFolder('d', localPath, gGator)
    else:
        gameCDDir = os.path.join(gGator.outputDir, 'cd', gGator.game)
        # Move cds file
        if not os.path.exists(gameCDDir):
            os.mkdir(gameCDDir)

        imgmountDir = os.path.dirname(localPath)

        # Robustness guard: some games (notably multi-disc titles whose source
        # bats reference CD images via a path layout the extractor flattens, e.g.
        # eXoDOS v6 comconra/WC2DLX) resolve to a directory that does not exist on
        # disk. Listing it would raise FileNotFoundError and abort the WHOLE game
        # conversion. Warn and emit the imgset line on a best-effort basis instead
        # of crashing; such games are flagged for a per-game override.
        if not os.path.isdir(imgmountDir):
            gGator.logger.log(
                '      <WARNING> CD source dir not found for "%s" (%s); '
                'emitting imgset line without moving CD files - this game likely '
                'needs a per-game override' % (gGator.game, imgmountDir),
                gGator.logger.WARNING)
        else:
            cdFiles = [file for file in os.listdir(imgmountDir) if
                       os.path.splitext(ntpath.basename(localPath))[0] == os.path.splitext(file)[0]
                       and os.path.splitext(file)[-1].lower() in ['.ccd', '.sub', '.cue', '.iso', '.img', '.bin']]
            for cdFile in cdFiles:
                gGator.logger.log("      move %s to %s folder" % (cdFile, 'cd'))
                shutil.move(os.path.join(imgmountDir, cdFile), gameCDDir)
            # Move all music files except FLAC an FLA
            musicFiles = [file for file in os.listdir(imgmountDir)
                          if os.path.splitext(file)[-1].lower() in ['.ogg', '.mp3', '.wav']]
            for musicFile in musicFiles:
                gGator.logger.log("      move %s to %s folder" % (musicFile, 'cd'))
                shutil.move(os.path.join(imgmountDir, musicFile), gameCDDir)
            # Delete all FLAC and FLA files
            flacFiles = [file for file in os.listdir(imgmountDir)
                         if os.path.splitext(file)[-1].lower() in ['.flac', '.fla']]
            for flacFile in flacFiles:
                os.remove(os.path.join(imgmountDir, flacFile))
        # Modify and return command line. Optional mount_other_game_cd override
        # redirects the mount path to another title's disc (Top300 prior-game pattern).
        script_dir = getattr(gGator, 'scriptDir', os.path.dirname(os.path.abspath(__file__)))
        other = misteroverrides.mount_other_game_cd(script_dir, gGator.game, logger=gGator.logger)
        if other:
            # payload = "otherDosname/filename.ext"
            gGator.logger.log(
                '      override mount_other_game_cd -> /cd/%s' % other)
            rel = other.lstrip('/')
            if letter == 'd':
                return 'imgset ide10 "/cd/' + rel + '"\n'
            return 'imgset ide11 "/cd/' + rel + '"\n'
        if letter == 'd':
            return 'imgset ide10 "/cd/' + gGator.game + '/' + ntpath.basename(localPath) + '"\n'
        else:
            return 'imgset ide11 "/cd/' + gGator.game + '/' + ntpath.basename(localPath) + '"\n'


# Convert floppy file
def convertFloppy(localPath, gGator, letter, emit_command=True):
    # Move bootable file
    # TODO see if we can do makedirs below instead
    if not os.path.exists(os.path.join(gGator.outputDir, 'floppy')):
        os.mkdir(os.path.join(gGator.outputDir, 'floppy'))

    if os.path.isdir(localPath):
        return convertMountedFolder(letter, localPath, gGator)
    else:
        gameFloppyDir = os.path.join(gGator.outputDir, 'floppy', gGator.game)
        if not os.path.exists(gameFloppyDir):
            os.mkdir(gameFloppyDir)
        dest = os.path.join(gameFloppyDir, ntpath.basename(localPath))
        if not os.path.exists(localPath):
            # Soft-fail like convertCD: do not abort the whole game when a
            # rewritten imgmount path cannot be resolved (e.g. multi-disk
            # floppies after confconverter drops the dosname folder).
            gGator.logger.log(
                '      <WARNING> floppy source not found for "%s" (%s); '
                'emitting imgset without moving the image'
                % (gGator.game, localPath),
                gGator.logger.WARNING,
            )
        elif os.path.abspath(localPath) != os.path.abspath(dest):
            gGator.logger.log("      move %s to %s folder" % (ntpath.basename(localPath), 'floppy'))
            if os.path.exists(dest):
                os.remove(dest)
            shutil.move(localPath, gameFloppyDir)
        # Modify and return command line (optional for multi-disk siblings)
        if not emit_command:
            return ''
        return 'imgset fdd0 "/floppy/' + gGator.game + '/' + ntpath.basename(localPath) + '"\n'


# Convert bootdisk file
def convertBootDisk(localPath, gGator):
    # Move bootable file
    # TODO see if we can do makedirs below instead
    if not os.path.exists(os.path.join(gGator.outputDir, 'bootdisk')):
        os.mkdir(os.path.join(gGator.outputDir, 'bootdisk'))

    if os.path.isdir(localPath):
        return convertMountedFolder('c', localPath, gGator)
    else:
        gameBootDiskDir = os.path.join(gGator.outputDir, 'bootdisk', gGator.game)
        if not os.path.exists(gameBootDiskDir):
            os.mkdir(gameBootDiskDir)
        gGator.logger.log("      move %s to %s folder" % (ntpath.basename(localPath), 'bootdisk'))
        shutil.move(localPath,
                    os.path.join(gameBootDiskDir, os.path.splitext(ntpath.basename(localPath))[0] + '.vhd'))
        # Modify and return command line
        return 'imgset ide00 "/bootdisk/' + gGator.game + '/' + os.path.splitext(ntpath.basename(localPath))[
            0] + '.vhd' + '"\n'


# Convert mounted or imgmounted folder
def convertMountedFolder(letter, localPath, gGator):
    if localPath.endswith('\\'):
        localPath = localPath[:-1]
    # TODO game\basename is not good either, path is lost !! needs reduction of the path instead / missing parts
    gGator.logger.log("      subst folder %s as %s:" % (ntpath.basename(localPath), letter))
    return 'subst ' + letter + ': /d\nsubst ' + letter + ': ' + gGator.game + '\\' + ntpath.basename(localPath)


# Create Setup.bat file
def createSetupBat(gGator):
    setupBat = open(os.path.join(gGator.getLocalGameOutputDir(), "3_Setup.bat"), 'w', newline='\r\n')
    setupBat.write('@echo off\n')
    if not gGator.isWin3x:
        setupBat.write('cd %s\n' % gGator.game)
    setupFiles = [file.lower() for file in os.listdir(gGator.getLocalGameDataOutputDir()) if file.lower() in
                  [gGator.game.lower(), 'setsound.exe', 'sound.exe', 'sound.com', 'install.exe', 'install.com',
                   'setup.exe', 'setup.com']]
    if len(setupFiles) <= 1 and os.path.exists(os.path.join(gGator.getLocalGameDataOutputDir(), gGator.game)):
        setupBat.write('cd %s\n' % gGator.game)
    setupBat.write('\n')
    setupBat.write('IF EXIST setsound.exe goto :sound1\n')
    setupBat.write('IF EXIST sound.exe goto :sound2\n')
    setupBat.write('IF EXIST sound.com goto :sound3\n')
    setupBat.write('IF EXIST install.exe goto :install1\n')
    setupBat.write('IF EXIST install.com goto :install2\n')
    setupBat.write('IF EXIST setup.exe goto :setup1\n')
    setupBat.write('IF EXIST setup.com goto :setup2\n')
    setupBat.write('\n')
    setupBat.write(
        'ECHO No setup files were found for this game.  You will need to manually run the appropriate setup in DOS.\n')
    setupBat.write('pause\n')
    setupBat.write('goto :END\n')
    setupBat.write('\n')
    setupBat.write(':sound1\n')
    setupBat.write('call setsound.exe\n')
    setupBat.write('goto :END\n')
    setupBat.write('\n')
    setupBat.write(':sound2\n')
    setupBat.write('call sound.exe\n')
    setupBat.write('goto :END\n')
    setupBat.write('\n')
    setupBat.write(':sound3\n')
    setupBat.write('call sound.com\n')
    setupBat.write('goto :END\n')
    setupBat.write('\n')
    setupBat.write(':setup1\n')
    setupBat.write('call setup.exe\n')
    setupBat.write('goto :END\n')
    setupBat.write('\n')
    setupBat.write(':setup2\n')
    setupBat.write('call setup.com\n')
    setupBat.write('goto :END\n')
    setupBat.write('\n')
    setupBat.write(':install1\n')
    setupBat.write('call install.exe\n')
    setupBat.write('goto :END\n')
    setupBat.write('\n')
    setupBat.write(':install2\n')
    setupBat.write('call install.com\n')
    setupBat.write('goto :END\n')
    setupBat.write('\n')
    setupBat.write(':END\n')
    setupBat.write('CLS\n')
    setupBat.close()


# Create Edit.bat file
def createEditBat(gGator):
    editBat = open(os.path.join(gGator.getLocalGameOutputDir(), "4_Edit.bat"), 'w', newline='\r\n')
    editBat.write('@echo off\nedit 1_Start.bat\n')
    editBat.close()


# Create about.png
def text2png(scriptDir, text, cover, generatedImgpath):
    if hasattr(Image, 'Resampling'):
        resampleFilter = Image.Resampling.LANCZOS
    else:
        resampleFilter = Image.ANTIALIAS

    def getTextSize(value):
        if hasattr(font, 'getbbox'):
            left, top, right, bottom = font.getbbox(value)
            return right - left, bottom - top
        return font.getsize(value)

    padding = 10
    imageWidth = 200
    textWidth = 640 - imageWidth
    color = "#FFF"
    bgcolor = "#000"
    REPLACEMENT_CHARACTER = u'\uFFFD'
    NEWLINE_REPLACEMENT_STRING = ' ' + REPLACEMENT_CHARACTER + ' '
    # font = ImageFont.truetype('DejaVuSans.ttf', 12)
    font = ImageFont.truetype(os.path.join(scriptDir, 'data', 'mister','DejaVuSans.ttf'), 12)
    text = text.replace('\n', NEWLINE_REPLACEMENT_STRING)

    img = Image.new("RGB", (640, 480), bgcolor)
    draw = ImageDraw.Draw(img)
    # Paste cover in the top right corner
    coverImg = Image.open(os.path.join(cover))
    coverWidth, coverHeight = coverImg.size
    ratio = float(coverHeight) / float(coverWidth)
    newHeight = int(ratio * float(imageWidth))
    img.paste(coverImg.resize((imageWidth, newHeight), resampleFilter), (textWidth - padding, padding))

    lines = []
    line = u""
    line_height = getTextSize('Ag')[1]
    text_height = 0
    for word in text.split():
        if word == REPLACEMENT_CHARACTER:  # give a blank line
            lines.append(line[1:])  # slice the white space in the begining of the line
            line = u""
            lines.append(u"")  # the blank line
            text_height = text_height + line_height
            # Change the text width when we are below coevr height + padding
            if text_height >= (newHeight + padding):
                textWidth = 640
        elif getTextSize(line + ' ' + word)[0] <= (textWidth - padding - padding):
            line += ' ' + word
        else:  # start a new line
            lines.append(line[1:])  # slice the white space in the begining of the line
            line = u""
            # Not done: handle too long words at this point
            line += ' ' + word  # for now, assume no word alone can exceed the line width
            text_height = text_height + line_height
            # Change the text width when we are below coevr height + padding
            if text_height >= (newHeight + padding):
                textWidth = 640

    if len(line) != 0:
        lines.append(line[1:])  # add the last line

    y = padding
    for line in lines:
        draw.text((padding, y), line, color, font=font)
        y += line_height

    img.save(generatedImgpath)
