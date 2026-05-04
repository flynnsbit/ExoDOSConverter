import glob
import math
import os
import re
import shutil
import subprocess
import tempfile
import zipfile

import util


class Ao486VhdBuilder:
    PARTITION_OFFSET_BYTES = 63 * 512
    GROWTH_BUFFER_BYTES = 50 * 1024 * 1024
    COPY_OVERHEAD_BYTES = 8 * 1024 * 1024
    FAT_METADATA_SAFETY_BYTES = 32 * 1024 * 1024
    COPY_RETRY_LIMIT = 3
    COPY_RETRY_GROWTH_BYTES = 256 * 1024 * 1024
    FAT32_DEFAULT_DOS_TEMPLATE = '450M-DOS71.vhd'

    AUTOBOOT_BEGIN = 'REM >>> EXODOSCONVERTER AUTOBOOT BEGIN >>>'
    AUTOBOOT_END = 'REM <<< EXODOSCONVERTER AUTOBOOT END <<<'

    TOOL_NAMES = ['qemu-img', 'mdir', 'mcopy', 'mmd', 'mtype', 'sfdisk', 'fatresize', 'mformat', 'mattrib']

    def __init__(self, scriptDir, outputDir, collectionVersion, logger, conversionConf=None):
        self.scriptDir = scriptDir
        self.outputDir = outputDir
        self.collectionVersion = collectionVersion
        self.logger = logger
        self.conversionConf = conversionConf if conversionConf is not None else dict()

    def build(self):
        if not self.__hasRequiredTools__():
            return False

        gamesDir = os.path.join(self.outputDir, 'games')
        if not os.path.isdir(gamesDir):
            self.logger.log('  <ERROR> games/ folder is missing, cannot build ao486 VHD', self.logger.ERROR)
            return False

        gameFolders = sorted([
            folder for folder in os.listdir(gamesDir)
            if os.path.isdir(os.path.join(gamesDir, folder))
        ])

        if len(gameFolders) == 0:
            self.logger.log('  <ERROR> No converted game folders were found in games/, cannot build ao486 VHD', self.logger.ERROR)
            return False

        mode = 'single' if len(gameFolders) == 1 else 'multi'
        templateFamily = 'win3' if util.isWin3x(self.collectionVersion) else 'dos'
        self.logger.log('  Preparing ao486 VHD in %s mode (%i game(s))' % (mode, len(gameFolders)))

        try:
            templates = self.__catalogTemplates__(templateFamily)
            if len(templates) == 0:
                raise RuntimeError('No %s ao486 templates are available' % templateFamily)

            with tempfile.TemporaryDirectory(prefix='edc-ao486-') as tempDir:
                stagingRoot = os.path.join(tempDir, 'C')
                os.makedirs(stagingRoot, exist_ok=True)

                self.__buildStagingTree__(stagingRoot, gameFolders, mode)

                stagedBytes, requiredFree = self.__calculateRequiredFreeBytes__(stagingRoot)
                buildName = self.__resolveBuildName__(mode, gameFolders)
                buildOutputDir = self.__createBuildOutputDir__(buildName)
                vhdPath = self.__buildOutputVhdPath__(buildOutputDir, buildName)
                self.__prepareExternalMediaForBuild__(buildOutputDir)

                targetFree = requiredFree
                copyCompleted = False
                for attempt in range(1, self.COPY_RETRY_LIMIT + 1):
                    if attempt > 1:
                        self.logger.log('  Retrying ao486 VHD sizing (%i/%i)' % (attempt, self.COPY_RETRY_LIMIT))

                    selectedTemplate = self.__selectTemplate__(templates, targetFree)
                    if selectedTemplate is None:
                        selectedTemplate = self.__selectExpansionTemplate__(templates)
                        if selectedTemplate.get('is_preferred_fat32'):
                            self.logger.log(
                                '  No template has enough free space (%s needed), using preferred FAT32 default %s for auto-expand'
                                % (self.__formatBytes__(targetFree), os.path.basename(selectedTemplate['path']))
                            )
                        else:
                            self.logger.log(
                                '  No template has enough free space (%s needed), attempting to auto-expand %s'
                                % (self.__formatBytes__(targetFree), os.path.basename(selectedTemplate['path']))
                            )
                    else:
                        self.logger.log(
                            '  Selected template %s (free %s)'
                            % (os.path.basename(selectedTemplate['path']), self.__formatBytes__(selectedTemplate['free_bytes']))
                        )

                    if os.path.exists(vhdPath):
                        os.remove(vhdPath)

                    shutil.copy2(selectedTemplate['path'], vhdPath)
                    availableFree = self.__readFreeBytes__(vhdPath)

                    if availableFree < targetFree:
                        self.__autoExpandTemplate__(vhdPath, availableFree, targetFree)
                        availableFree = self.__readFreeBytes__(vhdPath)
                        if availableFree < targetFree:
                            raise RuntimeError(
                                'Expanded image still has insufficient free space (%s available, %s required)'
                                % (self.__formatBytes__(availableFree), self.__formatBytes__(targetFree))
                            )

                    try:
                        self.__copyStagingToImage__(stagingRoot, vhdPath)
                        self.__patchAutoexecInImage__(vhdPath)
                        copyCompleted = True
                        break
                    except RuntimeError as err:
                        if attempt >= self.COPY_RETRY_LIMIT or not self.__isDiskSpaceCopyError__(err):
                            raise
                        growthStep = max(self.COPY_RETRY_GROWTH_BYTES, int(stagedBytes * 0.15))
                        targetFree += growthStep
                        self.logger.log(
                            '  Copy ran out of VHD space, increasing target by %s and retrying'
                            % self.__formatBytes__(growthStep),
                            self.logger.WARNING
                        )

                if not copyCompleted:
                    raise RuntimeError('Failed to finalize ao486 VHD after sizing retries')

                self.logger.log(
                    '  ao486 VHD created: %s (%s free after copy)'
                    % (vhdPath, self.__formatBytes__(self.__readFreeBytes__(vhdPath)))
                )
                self.logger.log('  ao486 pack directory: %s' % buildOutputDir)
                return True
        except RuntimeError as err:
            self.logger.log('  <ERROR> ao486 VHD build failed: %s' % err, self.logger.ERROR)
            return False

    def __resolveBuildName__(self, mode, gameFolders):
        requestedName = str(self.conversionConf.get('misterBuildName', '')).strip()
        if requestedName != '':
            return self.__sanitizeFileName__(requestedName)

        if mode == 'single':
            return self.__sanitizeFileName__(gameFolders[0])

        if requestedName == '':
            raise RuntimeError('Multiple games selected: please provide a collection name before building')
        return self.__sanitizeFileName__(requestedName)

    def __buildOutputVhdPath__(self, buildOutputDir, buildName):
        return os.path.join(buildOutputDir, buildName + '.vhd')

    def __createBuildOutputDir__(self, buildName):
        ao486Dir = os.path.join(self.outputDir, 'ao486')
        os.makedirs(ao486Dir, exist_ok=True)
        buildDir = os.path.join(ao486Dir, buildName)
        index = 2
        while os.path.exists(buildDir):
            buildDir = os.path.join(ao486Dir, buildName + '-' + str(index))
            index += 1
        os.makedirs(buildDir, exist_ok=True)
        return buildDir

    def __prepareExternalMediaForBuild__(self, buildOutputDir):
        ao486Dir = os.path.join(self.outputDir, 'ao486')
        for mediaDir in ['cd', 'floppy', 'bootdisk']:
            sourcePath = os.path.join(ao486Dir, mediaDir)
            if not os.path.isdir(sourcePath):
                continue
            destinationPath = os.path.join(buildOutputDir, mediaDir)
            if os.path.exists(destinationPath):
                shutil.rmtree(destinationPath)
            shutil.move(sourcePath, destinationPath)

    def __buildStagingTree__(self, stagingRoot, gameFolders, mode):
        gamesSourceDir = os.path.join(self.outputDir, 'games')
        gamesDestDir = os.path.join(stagingRoot, 'GAMES')
        os.makedirs(gamesDestDir, exist_ok=True)

        for gameFolder in gameFolders:
            sourceFolder = os.path.join(gamesSourceDir, gameFolder)
            destFolder = os.path.join(gamesDestDir, gameFolder)
            shutil.copytree(sourceFolder, destFolder)

        mymenuSourceDir = os.path.join(self.outputDir, 'mymenu')
        if not os.path.isdir(mymenuSourceDir):
            raise RuntimeError('mymenu/ folder is missing, cannot build ao486 VHD')
        mymenuDestDir = os.path.join(stagingRoot, 'MYMENU')
        shutil.copytree(mymenuSourceDir, mymenuDestDir)
        if mode == 'multi':
            self.__patchMyMenuPayload__(mymenuDestDir)

        self.__extractSupportArchive__('(Utilities and System Files).zip', stagingRoot)
        self.__extractSupportArchive__('(Manually Added Games).zip', stagingRoot)
        self.__writeAutorunScript__(stagingRoot, mode, gameFolders)

    def __extractSupportArchive__(self, archiveName, stagingRoot):
        archivePath = os.path.join(self.scriptDir, 'data', 'mister', archiveName)
        if not os.path.exists(archivePath):
            self.logger.log('  <WARNING> Missing MiSTeR support archive: %s' % archiveName, self.logger.WARNING)
            return
        with zipfile.ZipFile(archivePath, 'r') as zipFile:
            zipFile.extractall(path=stagingRoot)

    def __writeAutorunScript__(self, stagingRoot, mode, gameFolders):
        scriptPath = os.path.join(stagingRoot, 'AUTORUN_EDC.BAT')
        lines = ['@ECHO OFF']

        lines.append('IF EXIST C:\\MYMENU\\UTILS\\DOSLFNM.COM C:\\MYMENU\\UTILS\\DOSLFNM.COM')

        if mode == 'single':
            lines.extend([
                'CD "C:\\GAMES\\%s"' % gameFolders[0],
                'IF EXIST AUTORUN.BAT CALL AUTORUN.BAT',
                'IF NOT EXIST AUTORUN.BAT IF EXIST 1_START.BAT CALL 1_START.BAT',
            ])
        else:
            lines.extend([
                'IF EXIST C:\\MYMENU\\MENU.BAT CALL C:\\MYMENU\\MENU.BAT',
                'IF NOT EXIST C:\\MYMENU\\MENU.BAT IF EXIST C:\\MYMENU\\MYMENU.EXE C:\\MYMENU\\MYMENU.EXE C:\\GAMES',
            ])

        self.__writeDosTextFile__(scriptPath, lines)

    def __patchMyMenuPayload__(self, mymenuDir):
        menuBatPath = os.path.join(mymenuDir, 'MENU.BAT')
        if os.path.exists(menuBatPath):
            self.__writeDosTextFile__(menuBatPath, [
                '@echo off',
                'if exist c:\\mymenu\\utils\\doslfnm.com c:\\mymenu\\utils\\doslfnm.com',
                'c:\\mymenu\\mymenu.exe c:\\games',
            ])

        iniPath = os.path.join(mymenuDir, 'MYMENU.INI')
        if not os.path.exists(iniPath):
            self.logger.log('  <WARNING> MYMENU.INI missing from payload, skipping INI patch', self.logger.WARNING)
            return

        with open(iniPath, 'r', encoding='latin-1', errors='ignore') as iniFile:
            originalLines = [line.rstrip('\r\n') for line in iniFile.readlines()]

        updatedLines = []
        foundLFN = False
        foundDriveList = False

        for line in originalLines:
            if re.match(r'^\s*LFN\s*=', line, flags=re.IGNORECASE):
                updatedLines.append('LFN=T')
                foundLFN = True
            elif re.match(r'^\s*DOLISTDRV\s*=', line, flags=re.IGNORECASE):
                updatedLines.append('DOLISTDRV=C')
                foundDriveList = True
            elif re.match(r'^\s*DRV\s*=', line, flags=re.IGNORECASE):
                continue
            else:
                updatedLines.append(line)

        if not foundLFN:
            updatedLines.append('LFN=T')
        if not foundDriveList:
            updatedLines.append('DOLISTDRV=C')
        updatedLines.append('DRV = GAMES;C:\\GAMES\\')

        self.__writeDosTextFile__(iniPath, updatedLines)

    def __catalogTemplates__(self, templateFamily):
        templateDir = self.__resolveTemplateDir__(templateFamily)
        if templateDir is None:
            raise RuntimeError('Could not find %s template directory' % templateFamily)

        pattern = 'ao486_win3_*.vhd' if templateFamily == 'win3' else 'ao486_dos_*.vhd'
        templatePaths = sorted(glob.glob(os.path.join(templateDir, pattern)))
        preferredFat32Path = self.__resolvePreferredFat32TemplatePath__(templateFamily, templateDir)
        if preferredFat32Path is not None and preferredFat32Path not in templatePaths:
            templatePaths.append(preferredFat32Path)

        templates = []
        for path in templatePaths:
            freeBytes = self.__readFreeBytes__(path)
            nominalMb = self.__extractNominalMb__(path)
            templates.append({
                'path': path,
                'free_bytes': freeBytes,
                'image_bytes': os.path.getsize(path),
                'nominal_mb': nominalMb,
                'fat_type': self.__readFatType__(path),
                'is_preferred_fat32': preferredFat32Path is not None and os.path.normpath(path) == os.path.normpath(preferredFat32Path),
            })

        templates.sort(key=lambda item: (item['nominal_mb'], item['image_bytes']))
        self.logger.log('  Found %i ao486 %s template(s) in %s' % (len(templates), templateFamily, templateDir))
        preferredFat32Template = self.__findPreferredFat32Template__(templates)
        if preferredFat32Template is not None:
            self.logger.log('  Preferred FAT32 template: %s' % os.path.basename(preferredFat32Template['path']))
        return templates

    def __selectTemplate__(self, templates, requiredFree):
        fat16Eligible = [
            template for template in templates
            if template.get('fat_type') != 'fat32' and template['free_bytes'] >= requiredFree
        ]
        if len(fat16Eligible) > 0:
            return fat16Eligible[0]

        preferredFat32Template = self.__findPreferredFat32Template__(templates)
        if preferredFat32Template is not None:
            return preferredFat32Template

        eligible = [template for template in templates if template['free_bytes'] >= requiredFree]
        return eligible[0] if len(eligible) > 0 else None

    def __selectExpansionTemplate__(self, templates):
        preferredFat32Template = self.__findPreferredFat32Template__(templates)
        if preferredFat32Template is not None:
            return preferredFat32Template
        return templates[-1]

    def __resolveTemplateDir__(self, templateFamily):
        subDir = 'ao486_win31_templates' if templateFamily == 'win3' else 'ao486_dos622_templates'

        candidates = []
        envRoot = os.environ.get('EXODOS_AO486_TEMPLATE_ROOT', '').strip()
        if envRoot != '':
            candidates.append(envRoot)
        candidates.extend([
            os.path.join(self.scriptDir, 'vhdtemplate'),
            os.path.expanduser('~/exodos-build'),
            '/home/shawn/exodos-build',
            os.path.join(self.scriptDir, 'data', 'mister', 'ao486_templates'),
        ])

        checked = set()
        for root in candidates:
            if root in checked:
                continue
            checked.add(root)
            if os.path.basename(root) == subDir and os.path.isdir(root):
                return root
            candidate = os.path.join(root, subDir)
            if os.path.isdir(candidate):
                return candidate
        return None

    def __readFreeBytes__(self, imagePath):
        cmd = ['mdir', '-i', imagePath + '@@' + str(self.PARTITION_OFFSET_BYTES), '::']
        output = self.__runCommand__(cmd, 'Failed to read free space for %s' % imagePath, useCLocale=True)
        match = re.search(r'([0-9][0-9 ,]+)\s+bytes free', output)
        if match is None:
            raise RuntimeError('Could not parse free space from mdir output for %s' % imagePath)
        return int(re.sub(r'[^0-9]', '', match.group(1)))

    def __readFatType__(self, imagePath):
        result = subprocess.run(
            ['fatresize', '-i', '-n', '1', imagePath],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return 'unknown'
        match = re.search(r'FAT:\s*([a-zA-Z0-9]+)', result.stdout)
        if match is None:
            return 'unknown'
        return match.group(1).lower()

    def __resolvePreferredFat32TemplatePath__(self, templateFamily, templateDir):
        if templateFamily != 'dos':
            return None

        candidates = [
            os.path.join(templateDir, self.FAT32_DEFAULT_DOS_TEMPLATE),
            os.path.join(os.path.dirname(templateDir), self.FAT32_DEFAULT_DOS_TEMPLATE),
            os.path.join(self.scriptDir, 'vhdtemplate', self.FAT32_DEFAULT_DOS_TEMPLATE),
        ]
        checked = set()
        for candidate in candidates:
            normalized = os.path.normpath(candidate)
            if normalized in checked:
                continue
            checked.add(normalized)
            if os.path.isfile(normalized):
                return normalized
        return None

    @staticmethod
    def __findPreferredFat32Template__(templates):
        for template in templates:
            if template.get('is_preferred_fat32'):
                return template
        return None

    def __autoExpandTemplate__(self, vhdPath, currentFree, requiredFree):
        if requiredFree <= currentFree:
            return

        delta = requiredFree - currentFree
        targetBytes = os.path.getsize(vhdPath) + delta + (32 * 1024 * 1024)
        targetBytes = int(math.ceil(float(targetBytes) / float(1024 * 1024)) * 1024 * 1024)

        partInfo = self.__readPartitionInfo__(vhdPath)
        fsInfo = self.__readFilesystemInfo__(vhdPath)
        if fsInfo['fat_type'] == 'fat32':
            self.__expandFat32ByRebuild__(vhdPath, targetBytes, partInfo)
            newFree = self.__readFreeBytes__(vhdPath)
            if newFree <= currentFree:
                raise RuntimeError('FAT32 rebuild expansion did not increase free space (needed %s)'
                                   % self.__formatBytes__(requiredFree))
            return

        self.__runCommand__(
            ['qemu-img', 'resize', '-f', 'raw', vhdPath, str(targetBytes)],
            'Failed to resize VHD image to %i bytes' % targetBytes
        )

        partitionSpec = '%i,,%s,*\n' % (partInfo['start'], partInfo['id'])
        self.__runCommand__(
            ['sfdisk', '--no-reread', '--no-tell-kernel', vhdPath],
            'Failed to resize VHD partition layout',
            inputText=partitionSpec
        )

        fsInfo = self.__readFilesystemInfo__(vhdPath)
        desiredFsSize = fsInfo['cur_size'] + delta + (8 * 1024 * 1024)
        maxUsableFsSize = fsInfo['max_size'] - (1024 * 1024)
        if maxUsableFsSize <= fsInfo['cur_size']:
            maxUsableFsSize = fsInfo['max_size'] - (64 * 1024)
        targetFsSize = min(desiredFsSize, maxUsableFsSize)
        if targetFsSize <= fsInfo['cur_size']:
            targetFsSize = min(fsInfo['cur_size'] + (1024 * 1024), maxUsableFsSize)
        if targetFsSize <= fsInfo['cur_size']:
            raise RuntimeError('FAT filesystem cannot be expanded further inside selected template')

        self.__runCommand__(
            ['fatresize', '-f', '-n', '1', '-s', str(targetFsSize), vhdPath],
            'Failed to expand FAT filesystem inside VHD'
        )

        newFree = self.__readFreeBytes__(vhdPath)
        if newFree <= currentFree and targetFsSize < maxUsableFsSize:
            self.__runCommand__(
                ['fatresize', '-f', '-n', '1', '-s', str(maxUsableFsSize), vhdPath],
                'Failed to retry FAT expansion near maximum size'
            )
            newFree = self.__readFreeBytes__(vhdPath)
        if newFree <= currentFree:
            raise RuntimeError('Filesystem expansion did not increase free space (needed %s)'
                               % self.__formatBytes__(requiredFree))

    def __expandFat32ByRebuild__(self, vhdPath, targetBytes, partInfo):
        self.logger.log('  FAT32 template detected, using rebuild-based expansion path')
        with tempfile.TemporaryDirectory(prefix='edc-ao486-fat32-expand-') as tempDir:
            sourcePath = os.path.join(tempDir, 'source.vhd')
            expandedPath = os.path.join(tempDir, 'expanded.vhd')
            bootSectorPath = os.path.join(tempDir, 'bootsector.bin')
            stageDir = os.path.join(tempDir, 'stage')
            os.makedirs(stageDir, exist_ok=True)

            shutil.copy2(vhdPath, sourcePath)
            with open(sourcePath, 'rb') as sourceFile:
                sourceFile.seek(partInfo['start'] * 512)
                bootSector = sourceFile.read(512)
            if len(bootSector) != 512:
                raise RuntimeError('Failed to read FAT32 boot sector for expansion rebuild')
            with open(bootSectorPath, 'wb') as bootFile:
                bootFile.write(bootSector)

            self.__runCommand__(
                ['qemu-img', 'create', '-f', 'raw', expandedPath, str(targetBytes)],
                'Failed to allocate expanded FAT32 VHD image'
            )
            partitionSpec = '%i,,%s,*\n' % (partInfo['start'], partInfo['id'])
            self.__runCommand__(
                ['sfdisk', '--no-reread', '--no-tell-kernel', expandedPath],
                'Failed to create expanded FAT32 partition layout',
                inputText=partitionSpec
            )

            imageSpec = expandedPath + '@@' + str(partInfo['start'] * 512)
            env = os.environ.copy()
            env['MTOOLS_SKIP_CHECK'] = '1'
            result = subprocess.run(
                ['mformat', '-F', '-i', imageSpec, '-B', bootSectorPath, '::'],
                capture_output=True,
                text=True,
                env=env,
            )
            if result.returncode != 0:
                details = (result.stderr or result.stdout).strip()
                raise RuntimeError(
                    'Failed to format expanded FAT32 image%s'
                    % (': ' + details if details != '' else '')
                )

            sourceSpec = sourcePath + '@@' + str(partInfo['start'] * 512)
            self.__runCommand__(
                ['mcopy', '-s', '-i', sourceSpec, '::/*', stageDir],
                'Failed to stage FAT32 image contents for rebuild expansion'
            )
            for entry in sorted(os.listdir(stageDir)):
                sourceEntry = os.path.join(stageDir, entry)
                self.__runCommand__(
                    ['mcopy', '-o', '-s', '-i', imageSpec, sourceEntry, '::/'],
                    'Failed to copy staged FAT32 content %s into rebuilt image' % entry
                )

            self.__setBootFileAttributes__(imageSpec)
            shutil.copy2(expandedPath, vhdPath)

    def __setBootFileAttributes__(self, imageSpec):
        attributes = [
            ('IO.SYS', ['+s', '+h', '+r']),
            ('MSDOS.SYS', ['+s', '+h', '+r']),
            ('COMMAND.COM', ['+r']),
        ]
        for filename, flags in attributes:
            result = subprocess.run(
                ['mattrib', '-i', imageSpec] + flags + ['::' + filename],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                continue
            details = (result.stderr or result.stdout).strip()
            if 'not found' in details.lower():
                continue
            raise RuntimeError(
                'Failed to set DOS attributes on %s%s'
                % (filename, ': ' + details if details != '' else '')
            )

    def __readPartitionInfo__(self, imagePath):
        output = self.__runCommand__(['sfdisk', '-d', imagePath], 'Failed to inspect partition table for %s' % imagePath)
        for line in output.splitlines():
            if ': start=' not in line:
                continue
            startMatch = re.search(r'start=\s*([0-9]+)', line)
            typeMatch = re.search(r'type=\s*([0-9A-Fa-f]+)', line)
            if startMatch is None or typeMatch is None:
                continue
            return {'start': int(startMatch.group(1)), 'id': typeMatch.group(1).lower()}
        raise RuntimeError('Unable to parse first partition entry in %s' % imagePath)

    def __readFilesystemInfo__(self, imagePath):
        output = self.__runCommand__(
            ['fatresize', '-i', '-n', '1', imagePath],
            'Failed to inspect FAT filesystem information'
        )
        curSizeMatch = re.search(r'Cur size:\s*([0-9]+)', output)
        maxSizeMatch = re.search(r'Max size:\s*([0-9]+)', output)
        minSizeMatch = re.search(r'Min size:\s*([0-9]+)', output)
        fatTypeMatch = re.search(r'FAT:\s*([a-zA-Z0-9]+)', output)
        if curSizeMatch is None or maxSizeMatch is None or minSizeMatch is None:
            raise RuntimeError('Unable to parse FAT size info from fatresize output')
        return {
            'fat_type': fatTypeMatch.group(1).lower() if fatTypeMatch is not None else 'unknown',
            'cur_size': int(curSizeMatch.group(1)),
            'min_size': int(minSizeMatch.group(1)),
            'max_size': int(maxSizeMatch.group(1)),
        }

    def __copyStagingToImage__(self, stagingRoot, vhdPath):
        imageSpec = vhdPath + '@@' + str(self.PARTITION_OFFSET_BYTES)

        for root, dirs, files in os.walk(stagingRoot):
            dirs.sort()
            files.sort()
            relRoot = os.path.relpath(root, stagingRoot)

            for directory in dirs:
                relDir = directory if relRoot == '.' else os.path.join(relRoot, directory)
                self.__ensureDirectoryInImage__(imageSpec, relDir)

            destinationDir = '::/' if relRoot == '.' else '::/' + relRoot.replace(os.sep, '/') + '/'
            for filename in files:
                sourcePath = os.path.join(root, filename)
                self.__runCommand__(
                    ['mcopy', '-o', '-i', imageSpec, sourcePath, destinationDir],
                    'Failed to copy %s into VHD' % sourcePath
                )

    def __ensureDirectoryInImage__(self, imageSpec, relDir):
        mtoolsDir = '::/' + relDir.replace(os.sep, '/')
        result = subprocess.run(
            ['mmd', '-i', imageSpec, mtoolsDir],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            return

        errorMsg = (result.stderr or result.stdout or '').lower()
        if 'exists' in errorMsg:
            return
        raise RuntimeError('Failed to create VHD directory %s: %s' % (mtoolsDir, (result.stderr or result.stdout).strip()))

    def __patchAutoexecInImage__(self, vhdPath):
        imageSpec = vhdPath + '@@' + str(self.PARTITION_OFFSET_BYTES)
        autoexecText = self.__readTextFileFromImage__(imageSpec, '::AUTOEXEC.BAT')
        cleanedText = self.__removeManagedAutobootBlock__(autoexecText)
        cleanedLines = []
        for line in cleanedText.splitlines():
            stripped = line.strip().upper()
            # Win3 templates include an automatic WIN launch line; remove it so ExoDOSConverter controls startup.
            if stripped == 'WIN' or stripped.startswith('WIN '):
                continue
            cleanedLines.append(line.rstrip('\r\n'))
        cleanedText = '\r\n'.join(cleanedLines).rstrip('\r\n')

        managedLines = [
            self.AUTOBOOT_BEGIN,
            'IF EXIST C:\\AUTORUN_EDC.BAT CALL C:\\AUTORUN_EDC.BAT',
            self.AUTOBOOT_END,
        ]

        if cleanedText != '':
            newText = cleanedText + '\r\n' + '\r\n'.join(managedLines) + '\r\n'
        else:
            newText = '\r\n'.join(managedLines) + '\r\n'

        with tempfile.NamedTemporaryFile('w', delete=False, encoding='latin-1', newline='') as tempFile:
            tempFile.write(newText)
            tempPath = tempFile.name

        try:
            self.__runCommand__(
                ['mcopy', '-o', '-i', imageSpec, tempPath, '::AUTOEXEC.BAT'],
                'Failed to patch AUTOEXEC.BAT inside VHD'
            )
        finally:
            if os.path.exists(tempPath):
                os.remove(tempPath)

    def __readTextFileFromImage__(self, imageSpec, filePath):
        result = subprocess.run(
            ['mtype', '-i', imageSpec, filePath],
            capture_output=True,
        )
        if result.returncode != 0:
            raise RuntimeError('Failed to read %s from image: %s' % (filePath, result.stderr.decode('latin-1', errors='ignore').strip()))
        return result.stdout.decode('latin-1', errors='ignore')

    def __removeManagedAutobootBlock__(self, text):
        pattern = re.compile(
            r'(?is)\r?\n?%s.*?%s\r?\n?'
            % (re.escape(self.AUTOBOOT_BEGIN), re.escape(self.AUTOBOOT_END))
        )
        return re.sub(pattern, '\r\n', text)

    def __writeDosTextFile__(self, path, lines):
        with open(path, 'w', encoding='latin-1', newline='\r\n') as outputFile:
            for line in lines:
                outputFile.write(line + '\n')

    def __extractNominalMb__(self, path):
        filename = os.path.basename(path)
        match = re.search(r'_(\d+)MB\.vhd$', filename, flags=re.IGNORECASE)
        if match is None:
            match = re.match(r'^(\d+)M(?:B)?(?:[-_].*)?\.vhd$', filename, flags=re.IGNORECASE)
        if match is None:
            return 0
        return int(match.group(1))

    def __sanitizeFileName__(self, name):
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', name).strip().rstrip('.')
        return sanitized if sanitized != '' else 'ao486'

    def __calculateRequiredFreeBytes__(self, stagingRoot):
        payloadBytes = 0
        clusterAlignedPayloadBytes = 0
        directoryAllocationBytes = 0
        clusterSize = 32 * 1024

        for root, dirs, files in os.walk(stagingRoot):
            dirs.sort()
            files.sort()
            entryCount = len(dirs) + len(files) + 2
            dirBytes = max(entryCount * 32, 32)
            directoryAllocationBytes += int(math.ceil(float(dirBytes) / float(clusterSize)) * clusterSize)

            for filename in files:
                path = os.path.join(root, filename)
                if not os.path.isfile(path):
                    continue
                fileSize = os.path.getsize(path)
                payloadBytes += fileSize
                if fileSize > 0:
                    clusterAlignedPayloadBytes += int(math.ceil(float(fileSize) / float(clusterSize)) * clusterSize)

        estimatedClusterCount = int(math.ceil(float(clusterAlignedPayloadBytes) / float(clusterSize)))
        fatTableBytes = estimatedClusterCount * 8

        requiredFree = (
            clusterAlignedPayloadBytes
            + directoryAllocationBytes
            + fatTableBytes
            + self.GROWTH_BUFFER_BYTES
            + self.COPY_OVERHEAD_BYTES
            + self.FAT_METADATA_SAFETY_BYTES
        )
        return payloadBytes, requiredFree

    def __getFolderSize__(self, folder):
        total = 0
        for root, _, files in os.walk(folder):
            for filename in files:
                path = os.path.join(root, filename)
                if os.path.isfile(path):
                    total += os.path.getsize(path)
        return total

    def __isDiskSpaceCopyError__(self, error):
        message = str(error).lower()
        patterns = [
            'disk full',
            'no free clusters',
            'no space left',
            'not enough free space',
            'no directory slots',
            'directory full',
        ]
        return any(pattern in message for pattern in patterns)

    def __runCommand__(self, command, errorMessage, inputText=None, useCLocale=False):
        env = os.environ.copy()
        if useCLocale:
            env['LC_ALL'] = 'C'

        result = subprocess.run(
            command,
            input=inputText,
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            details = (result.stderr or result.stdout).strip()
            raise RuntimeError('%s%s' % (errorMessage, ': ' + details if details != '' else ''))
        return result.stdout

    def __hasRequiredTools__(self):
        missing = [tool for tool in self.TOOL_NAMES if shutil.which(tool) is None]
        if len(missing) == 0:
            return True
        self.logger.log(
            '  <ERROR> Missing required tools for ao486 VHD build: %s' % ', '.join(missing),
            self.logger.ERROR
        )
        return False

    def __formatBytes__(self, value):
        value = int(value)
        if value < 1024:
            return str(value) + ' B'
        if value < 1024 * 1024:
            return '%.1f KB' % (float(value) / 1024.0)
        if value < 1024 * 1024 * 1024:
            return '%.1f MB' % (float(value) / (1024.0 * 1024.0))
        return '%.2f GB' % (float(value) / (1024.0 * 1024.0 * 1024.0))
