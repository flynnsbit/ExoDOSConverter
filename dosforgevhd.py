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
    "AUTOEXEC.BAT",  # we write our own after this cleanup
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
            with tempfile.TemporaryDirectory(prefix='edc-dosforge-') as tempDir:
                stagingRoot = os.path.join(tempDir, 'vhd-root')
                os.makedirs(stagingRoot, exist_ok=True)

                # Stage GAMES + MYMENU + support zips + AUTORUN_EDC.BAT
                self._helper.__buildStagingTree__(stagingRoot, gameFolders, mode)
                # Drop anything that would overwrite dosforge OS bootstrap.
                self._stripProtectedRootSystemFiles(stagingRoot)
                # Root AUTOEXEC that survives dosforge create payload copy.
                self._writeRootAutoexec(stagingRoot)

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

    def _writeRootAutoexec(self, stagingRoot):
        """Write C:\\AUTOEXEC.BAT so payload copy replaces dosforge defaults.

        dosforge create installs a minimal AUTOEXEC then copies the custom
        payload on top — a root AUTOEXEC.BAT in the payload wins.
        """
        lines = [
            '@ECHO OFF',
            'PROMPT $P$G',
            'PATH C:\\DOS;C:\\FDOS;C:\\FDOS\\BIN;C:\\UTILS;C:\\MYMENU;C:\\MYMENU\\UTILS;%PATH%',
            'IF EXIST C:\\AUTORUN_EDC.BAT CALL C:\\AUTORUN_EDC.BAT',
        ]
        path = os.path.join(stagingRoot, 'AUTOEXEC.BAT')
        self._helper.__writeDosTextFile__(path, lines)

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

        bootAssets = str(self.conversionConf.get('misterDosforgeBootAssets', '') or '').strip()
        if bootAssets:
            cmd.extend(['--boot-assets-path', bootAssets])

        env = os.environ.copy()
        # Prefer sibling dosforge/dosassets when present and env not already set.
        if 'DOSFORGE_DOSASSETS_DIR' not in env:
            scriptRoot = os.path.abspath(self.scriptDir)
            candidates = [
                os.path.join(os.path.dirname(scriptRoot), 'dosforge', 'dosassets'),
                os.path.expanduser('~/Projects/dosforge/dosassets'),
                os.path.join(scriptRoot, '..', 'dosforge', 'dosassets'),
            ]
            for candidate in candidates:
                candidate = os.path.normpath(candidate)
                if os.path.isdir(candidate):
                    env['DOSFORGE_DOSASSETS_DIR'] = candidate
                    self.logger.log('  Using dosassets: %s' % candidate)
                    break

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
