import os
import shutil
from datetime import datetime
from functools import partial

import conf
import util
from appleiigsconverter import AppleIIGSConverter
from c64converter import C64Converter
from exoconverter import ExoConverter
from scummvmconverter import ScummVMConverter


class ExoAppState:
    BOOL_KEYS = [
        'genreSubFolders',
        'useKeyb2Joypad',
        'mapSticks',
        'longGameFolder',
        'downloadOnDemand',
        'preExtractGames',
        'dosboxPureZip',
        'debugMode',
        'expertMode',
        'vsyncCfg',
    ]
    PATH_KEYS = ['collectionDir', 'outputDir', 'selectionPath']
    DEFAULTS = {
        'outputDir': '',
        'collectionDir': '',
        'selectionPath': '',
        'conversionType': util.batocera,
        'collectionVersion': 'None',
        'genreSubFolders': '1',
        'mapper': 'None',
        'useKeyb2Joypad': '1',
        'mapSticks': '0',
        'longGameFolder': '1',
        'downloadOnDemand': '1',
        'preExtractGames': '0',
        'dosboxPureZip': '0',
        'debugMode': '0',
        'expertMode': '0',
        'mountPrefix': './',
        'fullresolutionCfg': 'desktop',
        'rendererCfg': 'auto',
        'outputCfg': 'texture',
        'vsyncCfg': '0',
    }

    def __init__(self, scriptDir, logger, setKey='exo'):
        self.scriptDir = scriptDir
        self.logger = logger
        self.setKey = setKey
        self.guiStrings = util.loadUIStrings(self.scriptDir, util.getGuiStringsFilename(self.setKey))

        self.confFilePath = os.path.join(self.scriptDir, util.confDir, util.getConfFilename(self.setKey))
        self.confBakPath = os.path.join(self.scriptDir, util.confDir, util.getConfBakFilename(self.setKey))
        loaded = conf.loadConf(self.confFilePath) if os.path.exists(self.confFilePath) else dict()
        self.configuration = self.DEFAULTS.copy()
        self.configuration.update(loaded)
        util.normalizeConfiguredPaths(self.configuration)

        for boolKey in self.BOOL_KEYS:
            self.configuration[boolKey] = '1' if str(self.configuration.get(boolKey, '0')) == '1' else '0'

        self.cache = None
        self.fullnameToGameDir = dict()
        self.sortedGameNames = []
        self.selectedGames = []
        self.filterValue = ''
        self.buildOutputName = ''

    def getValue(self, key, fallback=''):
        return str(self.configuration.get(key, fallback))

    def setValue(self, key, value):
        previousValue = str(self.configuration.get(key, ''))
        if key in self.PATH_KEYS:
            value = util.normalizeHostPath(value)
        if key in self.BOOL_KEYS:
            value = '1' if str(value) in ['1', 'true', 'True'] else '0'
        self.configuration[key] = str(value)
        if key == 'collectionDir' and str(value) != previousValue:
            self.cache = None
            self.fullnameToGameDir = dict()
            self.sortedGameNames = []
            self.selectedGames = []

    def getBool(self, key):
        return self.getValue(key, '0') == '1'

    def setBool(self, key, value):
        self.configuration[key] = '1' if value else '0'

    def setFilter(self, filterValue):
        self.filterValue = filterValue or ''

    def getAvailableGames(self):
        games = self.sortedGameNames
        if self.filterValue.strip() == '':
            return games.copy()
        lowered = self.filterValue.lower()
        return [game for game in games if lowered in game.lower()]

    def getSelectedGames(self):
        return sorted(self.selectedGames)

    def selectGames(self, gameNames):
        selectedSet = set(self.selectedGames)
        for gameName in gameNames:
            if gameName in self.fullnameToGameDir:
                selectedSet.add(gameName)
        self.selectedGames = sorted(list(selectedSet))

    def deselectGames(self, gameNames):
        toRemove = set(gameNames)
        self.selectedGames = [game for game in self.selectedGames if game not in toRemove]

    def clearSelection(self):
        self.selectedGames = []

    def setBuildOutputName(self, buildName):
        self.buildOutputName = str(buildName).strip() if buildName is not None else ''

    def getBuildOutputName(self):
        return self.buildOutputName

    def refreshCollection(self, buildCache=True, logInvalid=True):
        collectionDir = util.resolveCollectionPath(util.normalizeHostPath(self.getValue('collectionDir')))
        self.setValue('collectionDir', collectionDir)

        if collectionDir == '':
            self.configuration['collectionVersion'] = 'None'
            self.fullnameToGameDir = dict()
            self.cache = None
            return False

        collectionVersion = util.validCollectionPath(collectionDir)
        self.configuration['collectionVersion'] = collectionVersion if collectionVersion is not None else 'None'

        if collectionVersion is None:
            self.fullnameToGameDir = dict()
            self.sortedGameNames = []
            self.cache = None
            if logInvalid:
                self.logger.log(
                    "\n%s is not a directory, doesn't exist, or is not a valid eXo collection directory" % collectionDir,
                    self.logger.ERROR,
                )
                self.logger.log("Did you install the collection with setup.bat beforehand ?", self.logger.ERROR)
            return False

        self.fullnameToGameDir = util.fullnameToGameDir(collectionDir, self.scriptDir, collectionVersion, self.logger)
        self.sortedGameNames = sorted(list(self.fullnameToGameDir.keys()))
        self.selectedGames = [game for game in self.selectedGames if game in self.fullnameToGameDir]

        if buildCache:
            self.logger.log("\nBuild/Load image caches, this might take a while ...")
            self.cache = util.buildCache(self.scriptDir, collectionDir, collectionVersion, self.logger)

        return True

    def verifyPaths(self):
        errors = []
        for key in ['outputDir', 'collectionDir']:
            normalizedPath = util.normalizeHostPath(self.getValue(key))
            if key == 'collectionDir':
                normalizedPath = util.resolveCollectionPath(normalizedPath)
            self.setValue(key, normalizedPath)
            if not os.path.exists(normalizedPath):
                errors.append(key + ' folder does not exist')
        if not errors:
            self.logger.log('All Good!')
        else:
            for error in errors:
                self.logger.log(error, self.logger.ERROR)
        return errors

    def saveConfFile(self):
        os.makedirs(os.path.dirname(self.confFilePath), exist_ok=True)
        if os.path.exists(self.confBakPath):
            os.remove(self.confBakPath)
        if os.path.exists(self.confFilePath):
            shutil.copy2(self.confFilePath, self.confBakPath)

        excluded = [
            'verify',
            'save',
            'proceed',
            'confirm',
            'left',
            'right',
            'leftList',
            'rightList',
            'filter',
            'selectall',
            'unselectall',
            'loadCustom',
            'saveCustom',
            'selectOutputDir',
            'selectCollectionDir',
            'selectSelectionPath',
        ]
        sortedKeys = sorted(self.guiStrings.values(), key=lambda guiString: guiString.order)

        with open(self.confFilePath, 'w', encoding='utf-8') as confFile:
            for key in sortedKeys:
                if key.id in excluded:
                    continue
                if key.help:
                    confFile.write('# ' + key.help.replace('\n', '\n# ') + '\n')
                if key.id in self.configuration:
                    confFile.write(key.id + ' = ' + str(self.configuration[key.id]) + '\n')

        self.logger.log('    Configuration saved in ' + util.getConfFilename(self.setKey) + ' file')

    def loadCustomSelection(self):
        selectionFile = util.normalizeHostPath(self.getValue('selectionPath'))
        self.setValue('selectionPath', selectionFile)
        if not os.path.exists(selectionFile):
            self.logger.log('Selection File "%s" does not exist' % selectionFile, self.logger.ERROR)
            return

        selectedGames = []
        with open(selectionFile, 'r', encoding='utf-8') as file:
            for line in file.readlines():
                game = line.rstrip(' \n\r')
                if game in self.fullnameToGameDir:
                    selectedGames.append(game)
                else:
                    self.logger.log('Game "%s" not found in collection' % game, self.logger.ERROR)
        self.selectedGames = sorted(selectedGames)
        self.logger.log('Loaded selection File "%s" with %i games' % (selectionFile, len(selectedGames)))

    def saveCustomSelection(self):
        selectionFile = util.normalizeHostPath(self.getValue('selectionPath'))
        self.setValue('selectionPath', selectionFile)
        parentDir = os.path.dirname(selectionFile)
        if not os.path.exists(parentDir):
            self.logger.log(
                'Parent dir "%s" for Selection File "%s" does not exist' % (parentDir, selectionFile),
                self.logger.ERROR,
            )
            return

        if os.path.exists(selectionFile):
            shutil.move(selectionFile, selectionFile + '-' + datetime.now().strftime('%d-%m-%Y-%H-%M-%S'))

        with open(selectionFile, 'w', encoding='utf-8') as file:
            for selectedGame in self.selectedGames:
                file.write(selectedGame + '\n')
        self.logger.log('Saved selection File "%s" with %i games' % (selectionFile, len(self.selectedGames)))

    def _buildConversionConf(self):
        conversionType = self.getValue('conversionType')
        conversionConf = dict()
        conversionConf['useDebugMode'] = self.getBool('debugMode')
        conversionConf['useExpertMode'] = self.getBool('expertMode')
        conversionConf['useKeyb2Joypad'] = self.getBool('useKeyb2Joypad')
        conversionConf['mapSticks'] = self.getBool('mapSticks')
        conversionConf['mountPrefix'] = self.getValue('mountPrefix')
        conversionConf['fullresolutionCfg'] = self.getValue('fullresolutionCfg')
        conversionConf['rendererCfg'] = self.getValue('rendererCfg')
        conversionConf['outputCfg'] = self.getValue('outputCfg')
        conversionConf['vsyncCfg'] = self.getBool('vsyncCfg')
        conversionConf['preExtractGames'] = self.getBool('preExtractGames')
        conversionConf['downloadOnDemand'] = self.getBool('downloadOnDemand')
        conversionConf['mapper'] = self.getValue('mapper')

        if conversionType == util.mister:
            conversionConf['preExtractGames'] = False

        if conversionType in [util.retrobat, util.batocera, util.recalbox]:
            useLongFolderNames = self.getBool('longGameFolder')
            conversionConf['dosboxPureZip'] = self.getBool('dosboxPureZip')
        else:
            useLongFolderNames = False
            conversionConf['dosboxPureZip'] = False

        return conversionConf, useLongFolderNames

    def _buildConverter(self):
        collectionDir = util.resolveCollectionPath(util.normalizeHostPath(self.getValue('collectionDir')))
        outputDir = util.normalizeHostPath(self.getValue('outputDir'))
        self.setValue('collectionDir', collectionDir)
        self.setValue('outputDir', outputDir)
        conversionType = self.getValue('conversionType')
        useGenreSubFolders = self.getBool('genreSubFolders')

        if not self.refreshCollection(buildCache=False):
            self.logger.log("%s doesn't seem to be a valid collection folder" % collectionDir, self.logger.ERROR)
            return None

        if self.cache is None:
            self.cache = util.buildCache(self.scriptDir, collectionDir, self.getValue('collectionVersion'), self.logger)

        conversionConf, useLongFolderNames = self._buildConversionConf()
        games = [self.fullnameToGameDir.get(name) for name in self.selectedGames]

        for gameName in self.selectedGames:
            if self.fullnameToGameDir.get(gameName) is None:
                self.logger.log(
                    "Game data not found for %s\nIf you used a v4 selection, some games names may have changed in v5" % gameName,
                    self.logger.ERROR,
                )
        games = [game for game in games if game is not None]
        selectedGameLabels = self.getSelectedGames()
        if len(games) > 1 and self.buildOutputName.strip() == '':
            self.logger.log('Collection name is required for a multi-game build', self.logger.ERROR)
            return None

        if len(selectedGameLabels) == 1:
            buildOutputName = selectedGameLabels[0]
        elif len(selectedGameLabels) > 1:
            buildOutputName = self.buildOutputName
        else:
            buildOutputName = ''

        outputDir = util.createUniqueBuildOutputDir(outputDir, buildOutputName)
        self.logger.log('Using output build directory: ' + outputDir)

        if conversionType == util.mister:
            conversionConf['misterBuildName'] = buildOutputName

        self.logger.log(str(len(games)) + ' game(s) selected for conversion')

        collectionVersion = self.getValue('collectionVersion')
        noopPostProcess = partial(lambda: None)
        if collectionVersion == util.C64DREAMS:
            return C64Converter(
                games,
                self.cache,
                self.scriptDir,
                collectionVersion,
                collectionDir,
                outputDir,
                conversionType,
                useLongFolderNames,
                useGenreSubFolders,
                conversionConf,
                self.fullnameToGameDir,
                noopPostProcess,
                self.logger,
            )
        if collectionVersion == util.EXOAPPLEIIGS:
            return AppleIIGSConverter(
                games,
                self.cache,
                self.scriptDir,
                collectionVersion,
                collectionDir,
                outputDir,
                conversionType,
                useLongFolderNames,
                useGenreSubFolders,
                conversionConf,
                self.fullnameToGameDir,
                noopPostProcess,
                self.logger,
            )
        if collectionVersion == util.EXOSCUMMVM:
            return ScummVMConverter(
                games,
                self.cache,
                self.scriptDir,
                collectionVersion,
                collectionDir,
                outputDir,
                conversionType,
                useLongFolderNames,
                useGenreSubFolders,
                conversionConf,
                self.fullnameToGameDir,
                noopPostProcess,
                self.logger,
            )
        return ExoConverter(
            games,
            self.cache,
            self.scriptDir,
            collectionVersion,
            collectionDir,
            outputDir,
            conversionType,
            useLongFolderNames,
            useGenreSubFolders,
            conversionConf,
            self.fullnameToGameDir,
            noopPostProcess,
            self.logger,
        )

    def runConversion(self):
        converter = self._buildConverter()
        if converter is None:
            return False
        try:
            converter.convertGames()
            self.clearSelection()
            return True
        finally:
            self.setBuildOutputName('')
