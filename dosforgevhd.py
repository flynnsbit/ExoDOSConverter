"""Cross-platform ao486 VHD builder that shells out to dosforge.

Replaces the Linux-only template path in ``ao486vhd.Ao486VhdBuilder``
for greenfield packs: stage a C:\\ tree (GAMES + MYMENU + AUTOEXEC
launch script), size the VHD from the staged payload + buffer, then:

    dosforge create --custom-payload-path <vhd-root> ...

External media (cd/floppy/bootdisk) stays next to the VHD and is never
copied into the image.

Config keys (via conversionConf / conf-exo.conf):

* ``misterUseDosforge`` — ``true``/``false`` (default: true when
  dosforge is on PATH or ``misterDosforgeExecutable`` is set)
* ``misterDosforgeExecutable`` — absolute path to the dosforge binary
* ``misterBootMode`` — ``auto`` (default), ``msdos622``, ``msdos71``,
  ``freedos``, ...
* ``misterDosInstallProfile`` — ``minimal`` or ``full`` (default full)
* ``misterDosforgeBootAssets`` — optional dosassets path override
* ``misterSaveBufferMiB`` — extra free space for saves (default 64)

Falls back to the caller when dosforge is unavailable (see
``exoconverter`` wiring).
"""

from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile

import ao486vhd
import mymenupacker
import util


# FAT16 practical payload ceiling before promoting to FAT32 (Decision #8).
_FAT16_SOFT_CAP_BYTES = int(1.9 * 1024 * 1024 * 1024)
# Rough size of a full MS-DOS 6.22 / FreeDOS install on the VHD.
_DOS_SYSTEM_ESTIMATE_BYTES = 32 * 1024 * 1024
# Minimum VHD size dosforge will accept for a useful disk.
_MIN_VHD_BYTES = 64 * 1024 * 1024

# Support zips / game trees must never clobber dosforge-installed system
# files. A 0-byte COMMAND.COM from "(Manually Added Games).zip" was observed
# wiping the real COMMAND.COM after custom-payload copy.
_PROTECTED_ROOT_SYSTEM_FILES = frozenset({
    "COMMAND.COM",
    "IO.SYS",
    "MSDOS.SYS",
    "IBMBIO.COM",
    "IBMDOS.COM",
    "KERNEL.SYS",
    "CONFIG.SYS",
    "FDCONFIG.SYS",
    "FDAUTO.BAT",
    "AUTOEXEC.BAT",  # we write our own after this cleanup
})

# FreeDOS ships FDCONFIG.SYS + FDAUTO.BAT which take precedence over our
# Top300 CONFIG.SYS + AUTOEXEC.BAT. After payload install we remove them
# so the MiSTer menu boot path wins.
_FREEDOS_BOOT_OVERRIDE_FILES = frozenset({
    "FDCONFIG.SYS",
    "FDAUTO.BAT",
})


class DosforgeVhdBuilder:
    """Build a single bootable VHD via the dosforge CLI."""

    def __init__(self, scriptDir, outputDir, collectionVersion, logger, conversionConf=None):
        self.scriptDir = scriptDir
        self.outputDir = outputDir
        self.collectionVersion = collectionVersion
        self.logger = logger
        self.conversionConf = conversionConf if conversionConf is not None else dict()
        # Reuse staging / naming / media-move helpers from the template builder.
        self._helper = ao486vhd.Ao486VhdBuilder(
            scriptDir, outputDir, collectionVersion, logger, conversionConf
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def isAvailable(conversionConf=None):
        """Return True when a dosforge binary can be resolved."""
        conf = conversionConf if conversionConf is not None else {}
        return DosforgeVhdBuilder._resolveExecutable(conf) is not None

    @staticmethod
    def shouldUse(conversionConf=None):
        """Honor misterUseDosforge flag; default true when binary exists."""
        conf = conversionConf if conversionConf is not None else {}
        flag = str(conf.get('misterUseDosforge', 'auto')).strip().lower()
        if flag in ('0', 'false', 'no', 'off'):
            return False
        if flag in ('1', 'true', 'yes', 'on'):
            return DosforgeVhdBuilder.isAvailable(conf)
        # auto
        return DosforgeVhdBuilder.isAvailable(conf)

    def build(self):
        dosforgeBin = self._resolveExecutable(self.conversionConf)
        if dosforgeBin is None:
            self.logger.log(
                '  <ERROR> dosforge binary not found. Set misterDosforgeExecutable '
                'in conf or install dosforge on PATH.',
                self.logger.ERROR,
            )
            return False

        gamesDir = os.path.join(self.outputDir, 'games')
        if not os.path.isdir(gamesDir):
            self.logger.log(
                '  <ERROR> games/ folder is missing, cannot build ao486 VHD',
                self.logger.ERROR,
            )
            return False

        gameFolders = sorted(
            folder
            for folder in os.listdir(gamesDir)
            if os.path.isdir(os.path.join(gamesDir, folder))
        )
        if not gameFolders:
            self.logger.log(
                '  <ERROR> No converted game folders were found in games/',
                self.logger.ERROR,
            )
            return False

        # MyMenu is the shipping default: even a single selected game boots
        # into MyMenu so README.ANS previews and autorun.bat work as on multi
        # packs. Set misterLauncher=none for the old "boot straight into game"
        # single-game shortcut.
        launcher = str(
            self.conversionConf.get('misterLauncher', 'mymenu') or 'mymenu'
        ).strip().lower()
        if launcher in ('none', 'single') and len(gameFolders) == 1:
            mode = 'single'
        else:
            mode = 'multi'
        self.logger.log(
            '  Preparing ao486 VHD via dosforge in %s mode (%i game(s), launcher=%s)'
            % (mode, len(gameFolders), launcher)
        )

        try:
            # Stage on the same large filesystem as the pack output — never on
            # /tmp (often a small tmpfs). Large multi-game packs exceed /tmp.
            stagingParent = str(
                self.conversionConf.get('misterStagingDir', '') or ''
            ).strip()
            if not stagingParent:
                stagingParent = os.path.join(self.outputDir, '.edc-staging')
            os.makedirs(stagingParent, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix='edc-dosforge-', dir=stagingParent
            ) as tempDir:
                stagingRoot = os.path.join(tempDir, 'vhd-root')
                os.makedirs(stagingRoot, exist_ok=True)

                # Stage GAMES + MYMENU + support zips + AUTORUN_EDC.BAT
                self._helper.__buildStagingTree__(stagingRoot, gameFolders, mode)
                # Top300-style C:\DRIVERS (+ QEMM/DOS supplements) for CONFIG/AUTOEXEC.
                includeQemm = str(
                    self.conversionConf.get('misterIncludeQemm', 'true') or 'true'
                ).strip().lower() not in ('0', 'false', 'no', 'off')
                mymenupacker.extractBootC(
                    stagingRoot,
                    self.scriptDir,
                    self.logger,
                    includeQemm=includeQemm,
                )
                # Drop anything that would overwrite dosforge OS bootstrap.
                self._stripProtectedRootSystemFiles(stagingRoot)
                # Top300 multi-config CONFIG.SYS + AUTOEXEC ending in MyMenu (C: only).
                self._writeRootBootFiles(stagingRoot, mode)

                stagedBytes, requiredFree = self._helper.__calculateRequiredFreeBytes__(
                    stagingRoot
                )
                sizeBytes, fatFormat, bootMode = self._pickSizeAndFormat(
                    stagedBytes, requiredFree
                )

                buildName = self._helper.__resolveBuildName__(mode, gameFolders)
                buildOutputDir = self._helper.__createBuildOutputDir__(buildName)
                vhdPath = self._helper.__buildOutputVhdPath__(buildOutputDir, buildName)
                self._helper.__prepareExternalMediaForBuild__(buildOutputDir)

                if os.path.exists(vhdPath):
                    os.remove(vhdPath)

                sizeArg = self._formatSizeArg(sizeBytes)
                self.logger.log(
                    '  dosforge create: size=%s format=%s boot-mode=%s payload=%s'
                    % (
                        sizeArg,
                        fatFormat,
                        bootMode,
                        self._helper.__formatBytes__(stagedBytes),
                    )
                )

                self._runDosforgeCreate(
                    dosforgeBin=dosforgeBin,
                    vhdPath=vhdPath,
                    sizeArg=sizeArg,
                    fatFormat=fatFormat,
                    bootMode=bootMode,
                    payloadDir=stagingRoot,
                )

                if bootMode in ('freedos', 'msdos71', 'pcdos71'):
                    self._stripFreedosBootOverrides(dosforgeBin, vhdPath)

                self.logger.log('  ao486 VHD created: %s' % vhdPath)
                self.logger.log('  ao486 pack directory: %s' % buildOutputDir)
                return True
        except RuntimeError as err:
            self.logger.log(
                '  <ERROR> dosforge VHD build failed: %s' % err, self.logger.ERROR
            )
            return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _resolveExecutable(conversionConf):
        configured = str(conversionConf.get('misterDosforgeExecutable', '') or '').strip()
        if configured:
            if os.path.isfile(configured) and os.access(configured, os.X_OK):
                return configured
            # Still allow non-executable-bit on Windows.
            if os.path.isfile(configured):
                return configured
        which = shutil.which('dosforge')
        if which:
            return which
        # Sibling checkout heuristics (Linux + Windows layouts).
        scriptGuesses = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), 'dosforge', 'dosforge'),
            os.path.expanduser('~/Projects/dosforge/.venv/bin/dosforge'),
        ]
        for guess in scriptGuesses:
            if os.path.isfile(guess):
                return guess
        return None

    def _stripProtectedRootSystemFiles(self, stagingRoot):
        """Remove root files that must come from dosforge, not support zips."""
        try:
            names = os.listdir(stagingRoot)
        except OSError:
            return
        for name in names:
            if name.upper() not in _PROTECTED_ROOT_SYSTEM_FILES:
                continue
            path = os.path.join(stagingRoot, name)
            if not os.path.isfile(path):
                continue
            try:
                size = os.path.getsize(path)
            except OSError:
                size = -1
            self.logger.log(
                '  stripping payload root system file %s (%s bytes) so dosforge OS install wins'
                % (name, size)
            )
            try:
                os.remove(path)
            except OSError as exc:
                self.logger.log(
                    '  <WARNING> could not remove %s: %s' % (path, exc),
                    self.logger.WARNING,
                )

    def _audioMode(self) -> str:
        """sb | gus from conversionConf (misterAudio / misterPreferGus)."""
        raw = str(self.conversionConf.get('misterAudio', '') or '').strip().lower()
        if raw in ('gus', 'gravis', 'ultrasound', 'ultrasnd', 'sb', 'soundblaster', 'blaster'):
            if raw in ('gus', 'gravis', 'ultrasound', 'ultrasnd'):
                return 'gus'
            return 'sb'
        prefer = str(self.conversionConf.get('misterPreferGus', 'false')).strip().lower()
        if prefer in ('1', 'true', 'yes', 'on'):
            return 'gus'
        return 'sb'

    def _packTarget(self) -> str:
        """mister | picomem | picogus | picoide."""
        raw = str(self.conversionConf.get('misterTarget', '') or '').strip().lower()
        if raw in ('mister', 'picomem', 'picogus', 'picoide'):
            return raw
        return 'mister'

    def _applyAudioModeToAutoexec(self, autoexecBytes: bytes) -> bytes:
        """Rewrite AUTOEXEC audio + hardware block for SB/GUS and pack target."""
        mode = self._audioMode()
        target = self._packTarget()
        try:
            # Prefer packcli helper when running from ExoDOSConverter tree.
            sys_path_root = self.scriptDir
            if sys_path_root not in __import__('sys').path:
                __import__('sys').path.insert(0, sys_path_root)
            from packcli.audio_autoexec import apply_audio_mode
        except Exception as exc:
            self.logger.log(
                '  <WARNING> audio AUTOEXEC patch unavailable: %s' % exc,
                self.logger.WARNING,
            )
            return autoexecBytes
        text = autoexecBytes.decode('ascii', errors='replace')
        new = apply_audio_mode(text, mode, target=target)
        new = new.replace('\r\n', '\n').replace('\n', '\r\n')
        self.logger.log('  AUTOEXEC audio mode: %s target: %s' % (mode, target))
        return new.encode('ascii', errors='replace')

    def _applyTargetToConfigSys(self, configBytes: bytes) -> bytes:
        """Inject native CD DEVICE lines (e.g. CDMKE) when target needs them."""
        target = self._packTarget()
        try:
            sys_path_root = self.scriptDir
            if sys_path_root not in __import__('sys').path:
                __import__('sys').path.insert(0, sys_path_root)
            from packcli.audio_autoexec import apply_config_sys_target
        except Exception as exc:
            self.logger.log(
                '  <WARNING> CONFIG.SYS target patch unavailable: %s' % exc,
                self.logger.WARNING,
            )
            return configBytes
        text = configBytes.decode('ascii', errors='replace')
        new = apply_config_sys_target(text, target)
        new = new.replace('\r\n', '\n').replace('\n', '\r\n')
        if target in ('picogus', 'picoide'):
            self.logger.log('  CONFIG.SYS: CDMKE.SYS for target %s' % target)
        return new.encode('ascii', errors='replace')

    def _writeRootBootFiles(self, stagingRoot, mode):
        """Write Top300-style CONFIG.SYS + AUTOEXEC.BAT for MiSTer boot.

        Prefer templates from ``data/mister/boot-c.zip`` (Top300 ``_C`` adapted
        for single-VHD C: layout with MyMenu at the end). Fall back to a
        minimal MyMenu-only AUTOEXEC if the archive is missing.

        Critical: never CALL a long-named bat (e.g. AUTORUN_EDC.BAT) before
        DOSLFN is loaded — MS-DOS 6.22 without LFN will not find it and will
        drop straight to ``C:\\>``.
        """
        configBytes = mymenupacker.bootCTemplateBytes(self.scriptDir, 'CONFIG.SYS')
        autoexecBytes = mymenupacker.bootCTemplateBytes(self.scriptDir, 'AUTOEXEC.BAT')

        if configBytes:
            self.logger.log('  Installing Top300-style CONFIG.SYS (C: only)')
            configBytes = self._applyTargetToConfigSys(configBytes)
            with open(os.path.join(stagingRoot, 'CONFIG.SYS'), 'wb') as fh:
                fh.write(configBytes)

        if autoexecBytes and mode != 'single':
            self.logger.log(
                '  Installing Top300-style AUTOEXEC.BAT (C: only, MyMenu end)'
            )
            autoexecBytes = self._applyAudioModeToAutoexec(autoexecBytes)
            with open(os.path.join(stagingRoot, 'AUTOEXEC.BAT'), 'wb') as fh:
                fh.write(autoexecBytes)
            dosSrc = os.path.join(stagingRoot, 'DOS')
            if os.path.isdir(dosSrc):
                self.logger.log('  DOS supplements staged for HIMEM/EMM386/SETVER')
            return

        if mode == 'single':
            # Direct-to-game: keep Top300 driver loaders, but end with RUNMENU
            # (which CDs into the only game and calls autorun/1_Start) — never
            # MyMenu. Prefer rewriting the boot-c AUTOEXEC body when present.
            self.logger.log(
                '  Installing AUTOEXEC.BAT for single-game direct launch (no MyMenu)'
            )
            if autoexecBytes:
                text = autoexecBytes.decode('ascii', errors='replace')
                # Cut off at the MyMenu frontend block; replace with RUNMENU only.
                marker = 'REM --- MyMenu frontend'
                if marker in text:
                    text = text.split(marker)[0]
                lines = [ln.rstrip('\r\n') for ln in text.replace('\r\n', '\n').split('\n')]
                while lines and lines[-1].strip() in ('', ':END', 'GOTO END', ':CLEAN'):
                    lines.pop()
                # Drop any leftover :CLEAN section if split left mid-file junk
                cleaned = []
                for ln in lines:
                    if ln.strip().upper() == ':CLEAN':
                        break
                    cleaned.append(ln)
                lines = cleaned
                lines.extend([
                    '',
                    'REM --- single game direct launch (misterLauncher=none) ---',
                    'IF EXIST C:\\RUNMENU.BAT CALL C:\\RUNMENU.BAT',
                    'GOTO END',
                    '',
                    ':CLEAN',
                    'IF EXIST C:\\DRIVERS\\SHSUCDX.COM C:\\DRIVERS\\SHSUCDX.COM /D:IDE-CD /L:D /V /C',
                    'IF EXIST C:\\DRIVERS\\CUTEPACK\\CTMOUSE.EXE C:\\DRIVERS\\CUTEPACK\\CTMOUSE.EXE /O',
                    '@ECHO.',
                    '@ECHO CLEAN profile: game not auto-loaded.',
                    'GOTO END',
                    '',
                    ':END',
                ])
                # Apply SB/GUS audio block after single-game rewrite.
                path = os.path.join(stagingRoot, 'AUTOEXEC.BAT')
                self._helper.__writeDosTextFile__(path, lines)
                try:
                    raw = open(path, 'rb').read()
                    open(path, 'wb').write(self._applyAudioModeToAutoexec(raw))
                except OSError:
                    pass
            else:
                self._helper.__writeDosTextFile__(
                    os.path.join(stagingRoot, 'AUTOEXEC.BAT'),
                    [
                        '@ECHO OFF',
                        'PROMPT $P$G',
                        'PATH C:\\;C:\\DOS;C:\\DRIVERS;C:\\UTILS;C:\\MYMENU;C:\\MYMENU\\UTILS',
                        'IF EXIST C:\\MYMENU\\UTILS\\DOSLFNM.COM C:\\MYMENU\\UTILS\\DOSLFNM.COM',
                        'IF EXIST C:\\RUNMENU.BAT CALL C:\\RUNMENU.BAT',
                    ],
                )
                path = os.path.join(stagingRoot, 'AUTOEXEC.BAT')
                try:
                    raw = open(path, 'rb').read()
                    open(path, 'wb').write(self._applyAudioModeToAutoexec(raw))
                except OSError:
                    pass
            return

        self.logger.log(
            '  <WARNING> boot-c templates missing; writing minimal MyMenu AUTOEXEC',
            self.logger.WARNING,
        )
        autoexec = [
            '@ECHO OFF',
            'PROMPT $P$G',
            'PATH C:\\;C:\\DOS;C:\\FDOS;C:\\FDOS\\BIN;C:\\DRIVERS;C:\\UTILS;C:\\MYMENU;C:\\MYMENU\\UTILS',
            'IF EXIST C:\\MYMENU\\UTILS\\DOSLFNM.COM C:\\MYMENU\\UTILS\\DOSLFNM.COM',
            'IF EXIST C:\\RUNMENU.BAT CALL C:\\RUNMENU.BAT',
            'IF EXIST C:\\MYMENU\\MENU.BAT CALL C:\\MYMENU\\MENU.BAT',
            'IF EXIST C:\\MYMENU\\MYMENU.EXE C:\\MYMENU\\MYMENU.EXE C:\\GAMES',
            ':REMENU',
            'IF EXIST C:\\RUNMENU.BAT CALL C:\\RUNMENU.BAT',
            'IF EXIST C:\\MYMENU\\MENU.BAT CALL C:\\MYMENU\\MENU.BAT',
            'GOTO REMENU',
        ]
        self._helper.__writeDosTextFile__(
            os.path.join(stagingRoot, 'AUTOEXEC.BAT'), autoexec
        )
        if not configBytes:
            config_lines = [
                'FILES=40',
                'BUFFERS=30',
                'STACKS=9,256',
                'SHELL=C:\\COMMAND.COM C:\\ /E:1024 /P',
            ]
            self._helper.__writeDosTextFile__(
                os.path.join(stagingRoot, 'CONFIG.SYS'), config_lines
            )

    def _pickSizeAndFormat(self, stagedBytes, requiredFree):
        """Return (size_bytes, fat_format, boot_mode)."""
        confMode = str(self.conversionConf.get('misterBootMode', 'auto') or 'auto').strip().lower()
        bufferMiB = self.conversionConf.get('misterSaveBufferMiB', 64)
        try:
            bufferBytes = int(bufferMiB) * 1024 * 1024
        except (TypeError, ValueError):
            bufferBytes = 64 * 1024 * 1024

        # requiredFree already includes growth/copy/FAT safety from ao486vhd.
        # Add DOS system estimate and optional extra save buffer if conf raises it.
        base = int(requiredFree) + _DOS_SYSTEM_ESTIMATE_BYTES
        # If user asked for more than the built-in 50 MiB growth buffer, top up.
        builtinGrowth = getattr(self._helper, 'GROWTH_BUFFER_BYTES', 50 * 1024 * 1024)
        if bufferBytes > builtinGrowth:
            base += bufferBytes - builtinGrowth

        sizeBytes = max(_MIN_VHD_BYTES, int(math.ceil(base / (1024 * 1024.0)) * 1024 * 1024))

        if confMode not in ('', 'auto'):
            bootMode = confMode
            if bootMode in ('msdos71', 'freedos', 'pcdos71'):
                fatFormat = 'fat32' if sizeBytes > 512 * 1024 * 1024 else 'fat16'
                if bootMode == 'msdos622':
                    fatFormat = 'fat16'
            elif bootMode in ('msdos622', 'msdos5', 'msdos6', 'compaq331'):
                fatFormat = 'fat16'
                if sizeBytes > _FAT16_SOFT_CAP_BYTES:
                    raise RuntimeError(
                        'Configured boot-mode %s cannot hold %s (FAT16 soft cap ~1.9 GiB). '
                        'Use misterBootMode=msdos71 or freedos.'
                        % (bootMode, self._helper.__formatBytes__(sizeBytes))
                    )
            else:
                fatFormat = 'fat16'
            return sizeBytes, fatFormat, bootMode

        # auto: promote to FAT32 when over soft cap or many games force All-Games view later
        if sizeBytes > _FAT16_SOFT_CAP_BYTES:
            bootMode = 'msdos71'
            fatFormat = 'fat32'
            self.logger.log(
                '  Auto-selected %s/%s (payload needs %s)'
                % (bootMode, fatFormat, self._helper.__formatBytes__(sizeBytes))
            )
        else:
            bootMode = 'msdos622'
            fatFormat = 'fat16'
            self.logger.log(
                '  Auto-selected %s/%s (size %s)'
                % (bootMode, fatFormat, self._helper.__formatBytes__(sizeBytes))
            )
        return sizeBytes, fatFormat, bootMode

    @staticmethod
    def _formatSizeArg(sizeBytes):
        mib = int(math.ceil(sizeBytes / (1024.0 * 1024.0)))
        if mib >= 1024 and mib % 1024 == 0:
            return '%dG' % (mib // 1024)
        return '%dM' % mib

    # boot-mode → subdirectory under dosassets/ (dosforge expects Disk*.img there)
    _BOOT_MODE_ASSET_SUBDIR = {
        'msdos622': 'msdos622',
        'msdos71': 'msdos71',
        'msdos6': 'msdos6',
        'msdos5': 'msdos5',
        'msdos33': 'msdos33',
        'msdos331': 'msdos331',
        'freedos': 'freedos',
        'pcdos7': 'pcdos7',
        'pcdos71': 'pcdos71',
        'compaq331': 'compaq331',
        'compaq2': 'compaq2',
        'compaq3': 'compaq3',
        'pcdos3': 'pcdos3',
        'pcdos5': 'pcdos5',
        'drdos6': 'drdos6',
        'drdos7': 'drdos7',
        '4dos': '4dos',
    }

    def _discoverDosassetsRoot(self):
        """Find dosassets root: conf → env → sibling dosforge checkout.

        Layout expected::

            <root>/msdos622/Disk1.img
            <root>/freedos/...
        """
        candidates = []
        conf = str(
            self.conversionConf.get('misterDosforgeBootAssets', '') or ''
        ).strip()
        if conf:
            candidates.append(os.path.expanduser(conf))
        envRoot = (os.environ.get('DOSFORGE_DOSASSETS_DIR') or '').strip()
        if envRoot:
            candidates.append(os.path.expanduser(envRoot))
        envAlt = (os.environ.get('MISTER_DOSASSETS') or '').strip()
        if envAlt:
            candidates.append(os.path.expanduser(envAlt))

        scriptRoot = os.path.abspath(self.scriptDir)
        # Sibling of ExoDOSConverter: ~/Projects/dosforge/dosassets
        candidates.extend(
            [
                os.path.join(os.path.dirname(scriptRoot), 'dosforge', 'dosassets'),
                os.path.normpath(
                    os.path.join(scriptRoot, '..', 'dosforge', 'dosassets')
                ),
                os.path.expanduser('~/Projects/dosforge/dosassets'),
                os.path.expanduser('~/.dosforge/dosassets'),
            ]
        )

        def _normalize_root(path):
            """Accept either dosassets root or a mode subdir (…/msdos622)."""
            path = os.path.normpath(os.path.abspath(path))
            if not os.path.isdir(path):
                return None
            base = os.path.basename(path).lower()
            # User pointed at msdos622/ or freedos/ directly
            if base in self._BOOT_MODE_ASSET_SUBDIR.values():
                parent = os.path.dirname(path)
                if os.path.basename(parent).lower() == 'dosassets' or os.path.isdir(
                    os.path.join(parent, 'freedos')
                ) or os.path.isdir(os.path.join(parent, 'msdos622')):
                    return parent
                # Still usable as a single-mode tree; treat parent as root if it
                # looks like a collection of version dirs, else return parent.
                return parent if os.path.isdir(parent) else path
            # Looks like dosassets root if it has known subdirs or readme
            for sub in ('msdos622', 'freedos', 'msdos71', 'msdos5'):
                if os.path.isdir(os.path.join(path, sub)):
                    return path
            if os.path.isfile(os.path.join(path, 'readme.txt')):
                return path
            # Accept any existing dir as last resort
            return path

        for c in candidates:
            if not c:
                continue
            root = _normalize_root(c)
            if root:
                return root
        return None

    def _resolveDosassetsForBootMode(self, bootMode):
        """Return (assets_root, path_for_--boot-assets-path).

        dosforge's ``--boot-assets-path`` must point at the **mode directory**
        that contains Disk1.img (e.g. ``…/dosassets/msdos622``), not the
        parent ``dosassets/`` root.  If we only set the env root and omit the
        flag, dosforge resolves ``msdos622`` via ``DOSFORGE_DOSASSETS_DIR``.
        """
        root = self._discoverDosassetsRoot()
        if not root:
            return None, None
        mode = (bootMode or '').strip().lower()
        sub = self._BOOT_MODE_ASSET_SUBDIR.get(mode)
        if sub:
            modePath = os.path.join(root, sub)
            if os.path.isdir(modePath):
                return root, modePath
        # Mode subdir missing: pass root and hope, or freedos fallback
        freedos = os.path.join(root, 'freedos')
        if mode in ('auto', '') and os.path.isdir(freedos):
            return root, freedos
        return root, root if os.path.isdir(root) else None

    def _runDosforgeCreate(
        self,
        *,
        dosforgeBin,
        vhdPath,
        sizeArg,
        fatFormat,
        bootMode,
        payloadDir,
    ):
        # Default full so C:\DOS\HIMEM.SYS exists for DOSLFN / MyMenu.
        profile = str(
            self.conversionConf.get('misterDosInstallProfile', 'full') or 'full'
        ).strip().lower()
        if profile not in ('minimal', 'full'):
            profile = 'full'

        cmd = [
            dosforgeBin,
            'create',
            '--path', vhdPath,
            '--media-type', 'vhd',
            '--size', sizeArg,
            '--format', fatFormat,
            '--boot-mode', bootMode,
            '--dos-install-profile', profile,
            '--custom-payload-path', payloadDir,
            '--label', 'EXODOS',
            '--overwrite',
        ]

        env = os.environ.copy()
        assetsRoot, assetsModePath = self._resolveDosassetsForBootMode(bootMode)
        if assetsRoot:
            # dosforge looks for Disk1.img *inside* the path we pass — so for
            # msdos622 we must pass .../dosassets/msdos622, not the parent root.
            # Also set DOSFORGE_DOSASSETS_DIR so bare-name fallbacks work.
            env['DOSFORGE_DOSASSETS_DIR'] = assetsRoot
            if assetsModePath:
                cmd.extend(['--boot-assets-path', assetsModePath])
            self.logger.log(
                '  Using dosassets root: %s (boot-mode path: %s)'
                % (assetsRoot, assetsModePath or '(auto)')
            )
        else:
            self.logger.log(
                '  <WARNING> no dosassets found (env/config/sibling); '
                'dosforge may fail to install DOS',
                self.logger.WARNING,
            )

        self.logger.log('  Running: %s' % ' '.join(cmd))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=env,
            )
        except FileNotFoundError as exc:
            raise RuntimeError('Failed to execute dosforge: %s' % exc) from exc

        if result.stdout:
            for line in result.stdout.strip().splitlines()[-20:]:
                self.logger.log('    [dosforge] %s' % line)
        if result.returncode != 0:
            err = (result.stderr or result.stdout or '').strip()
            raise RuntimeError(
                'dosforge create failed (exit %s)%s'
                % (result.returncode, ': ' + err if err else '')
            )

        if not os.path.isfile(vhdPath):
            raise RuntimeError('dosforge reported success but VHD is missing: %s' % vhdPath)

    def _stripFreedosBootOverrides(self, dosforgeBin, vhdPath):
        """Remove FreeDOS FDCONFIG/FDAUTO so Top300 CONFIG/AUTOEXEC control boot."""
        for name in sorted(_FREEDOS_BOOT_OVERRIDE_FILES):
            cmd = [dosforgeBin, 'rm', vhdPath, '::/%s' % name]
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=60
                )
            except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
                self.logger.log(
                    '  <WARNING> could not remove %s from VHD: %s' % (name, exc),
                    self.logger.WARNING,
                )
                continue
            if result.returncode == 0:
                self.logger.log('  Removed FreeDOS override %s from VHD' % name)
            else:
                # Missing is fine (already gone / not FreeDOS profile).
                msg = (result.stderr or result.stdout or '').strip()
                if msg and 'not found' not in msg.lower() and 'No such' not in msg:
                    self.logger.log(
                        '  <WARNING> dosforge rm %s: %s' % (name, msg),
                        self.logger.WARNING,
                    )
