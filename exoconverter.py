import os
import shutil
import sys
import traceback
from metadatahandler import MetadataHandler
from keyb2joypad import Keyb2Joypad
import util
import dosboxconfv6
from zipfile import ZipFile
import mymenupacker
import ao486vhd
import dosforgevhd
from gamegenerator import GameGenerator


# Main Converter
class ExoConverter:

    def __init__(self, games, cache, scriptDir, collectionVersion, collectionDir, outputDir, conversionType, useLongFolderNames, 
                 useGenreSubFolders, conversionConf, fullnameToGameDir, postProcess, logger):
        self.games = games
        self.cache = cache
        self.scriptDir = scriptDir
        self.collectionVersion = collectionVersion
        self.exoCollectionDir = collectionDir
        self.logger = logger
        self.collectionGamesDir = util.getCollectionGamesDir(collectionDir, collectionVersion)
        self.collectionGamesConfDir = util.getCollectionGamesConfDir(collectionDir, collectionVersion)
        self.outputDir = outputDir
        self.conversionType = conversionType
        self.useLongFolderNames = useLongFolderNames
        self.useGenreSubFolders = useGenreSubFolders
        self.conversionConf = conversionConf
        self.metadataHandler = MetadataHandler(scriptDir, collectionDir, collectionVersion, self.cache, self.logger)
        self.keyb2joypad = Keyb2Joypad(self.scriptDir, self.logger)
        self.fullnameToGameDir = fullnameToGameDir
        self.postProcess = postProcess
        self.defaultDosboxConf = dosboxconfv6.loadDosboxConf(os.path.join(scriptDir, 'data', 'dosbox-0.74-default.conf'), dict())
        self.dosboxPureZip = True if 'dosboxPureZip' in self.conversionConf and self.conversionConf['dosboxPureZip'] is True else False

    # Loops on all games to convert them
    def convertGames(self):
        # Pre-checks
        if len(self.games) == 0:
            self.postProcess()
            return
        if self.conversionType == util.mister and util.hasMisterPack(self.outputDir):
            self.logger.log("\nFound a previous MiSTeR pack in output folder, please move or delete it before processing with a new one\n", self.logger.ERROR)
            self.postProcess()
            return

        self.logger.log("Loading metadatas...")
        self.metadataHandler.parseXmlMetadata()
        if not os.path.exists(os.path.join(self.outputDir, 'downloaded_images')):
            os.mkdir(os.path.join(self.outputDir, 'downloaded_images'))
        if not os.path.exists(os.path.join(self.outputDir, 'manuals')):
            os.mkdir(os.path.join(self.outputDir, 'manuals'))

        self.logger.log("Loading keyb2joypad configurations")
        self.keyb2joypad.load()
        self.logger.log("")

        gamelist = self.metadataHandler.initXml(self.outputDir)

        count = 1
        total = len(self.games)
        errors = dict()

        for game in self.games:
            try:
                self.__convertGame__(game, gamelist, total, count)
            except:
                self.logger.log('  Error %s while converting game %s\n\n' % (sys.exc_info()[0], game),
                                self.logger.ERROR)
                excInfo = traceback.format_exc()
                errors[game] = excInfo

            count = count + 1

        self.metadataHandler.writeXml(self.outputDir, gamelist)

        self.logger.log('\n<--------- Post-conversion --------->')
        self.__postConversion__()

        self.logger.log('\n<--------- Finished Process --------->\n')

        if len(errors.keys()) > 0:
            self.logger.log('\n<--------- Errors rundown --------->', self.logger.ERROR)
            self.logger.log('%i errors were found during process' % len(errors.keys()), self.logger.ERROR)
            self.logger.log('See error log in your outputDir for more info\n', self.logger.ERROR)
            logFile = open(os.path.join(self.outputDir, 'error_log.txt'), 'w')
            for key in list(errors.keys()):
                logFile.write("Found error when processing %s" % key + " :\n")
                logFile.write(errors.get(key))
                logFile.write("\n")
            logFile.close()
        elif os.path.exists(os.path.join(self.outputDir, 'error_log.txt')):
            # Delete log from previous runs
            os.remove(os.path.join(self.outputDir, 'error_log.txt'))

        self.postProcess()

    # Full conversion for a given game    
    def __convertGame__(self, game, gamelist, totalSize, count):
        genre = self.metadataHandler.buildGenre(self.metadataHandler.metadatas.get(game.lower()), self.metadataHandler.fixGenres)
        self.logger.log(">>> %i/%i >>> %s: starting conversion" % (count, totalSize, game))
        metadata = self.metadataHandler.processGame(game, gamelist, genre, self.outputDir, self.useLongFolderNames, self.useGenreSubFolders,
                                                    self.conversionType, self.collectionVersion, self.dosboxPureZip, None, None)

        if (self.conversionType == util.batocera or self.conversionType == util.retrobat) and self.useLongFolderNames:
            gameDir = util.getCleanGameID(metadata,'.pc')
        else:
            gameDir = game + ".pc"
        gGator = GameGenerator(game, gameDir, genre, self.outputDir, self.collectionVersion, self.useLongFolderNames, self.useGenreSubFolders, metadata,
                               self.conversionType, self.conversionConf, self.exoCollectionDir, self.fullnameToGameDir,
                               self.scriptDir, self.keyb2joypad, self.defaultDosboxConf, self.logger)

        if not os.path.exists(gGator.getLocalGameOutputDir()):
            self.__copyGameDataToOutputDir__(gGator)
            gGator.convertGame()
        else:
            self.logger.log("  already converted in output folder")

        # TODO refine and reactivate
        # util.checkMultipleofSameGame(self.useGenreSubFolders, metadata, genre, game, gameDir, self.outputDir, self.logger)
        self.logger.log("")

    # Copy game data from collection to output dir
    def __copyGameDataToOutputDir__(self, gGator):
        # previous method kept for doc purpose
        # automatic Y, F and N to validate answers to exo's install.bat
        # fullscreen = true, output=overlay, aspect=true
        # subprocess.call("cmd /C (echo Y&echo F&echo N) | Install.bat", cwd=os.path.join(self.gamesDosDir, game),
        #                 shell=False)

        # Resolve game payload the same way eXo does:
        #   1) eXo/eXoDOS/<Title>.zip  (primary install zip)
        #   2) Content/GameData/eXoDOS/<Title>.zip  (full media package)
        #   3) already-unpacked tree under eXo/eXoDOS/ (post-install state)
        #   4) optional downloadOnDemand when zip is still missing
        confDir = os.path.join(self.collectionGamesConfDir, gGator.game)
        bats = [os.path.splitext(filename)[0] for filename in
                os.listdir(confDir) if
                os.path.splitext(filename)[-1].lower() == '.bat'
                and not os.path.splitext(filename)[0].lower() == 'install'
                and not os.path.splitext(filename)[0].lower() == 'exception']
        if not bats:
            self.logger.log(
                "  ERROR while trying to find zip file for " + confDir,
                self.logger.ERROR)
            return
        gameZip = bats[0] + '.zip'
        gameZipPath = self.__resolveGameZipPath__(gameZip)

        if gameZipPath is not None:
            # ensure gameZip not 0 bytes, this will trigger a download if it is.
            try:
                if not os.path.getsize(gameZipPath):
                    self.logger.log("  <WARNING>" + gameZipPath + " is 0 bytes. Removing.", self.logger.WARNING)
                    os.remove(gameZipPath)
                    gameZipPath = None
            except OSError:
                pass

        if gameZipPath is None:
            # Zip still missing — try already-unpacked eXo install tree.
            extracted = self.__resolveUnpackedGameSource__(gGator, bats[0])
            if extracted is not None:
                self.logger.log(
                    "  using already-unpacked game data at %s (no zip needed)" % extracted
                )
                self.__copyUnpackedGame__(extracted, gGator)
            else:
                primary = os.path.join(
                    util.getCollectionGamesDir(self.exoCollectionDir, self.collectionVersion),
                    gameZip,
                )
                self.logger.log('  <WARNING> %s not found' % primary, self.logger.WARNING)
                if self.conversionConf.get('downloadOnDemand'):
                    downloadZipSuccess = util.downloadZip(gameZip, primary, self.logger)
                    if not downloadZipSuccess:
                        self.logger.log("  <WARNING> Web download Failed, trying Torrent", self.logger.WARNING)
                        util.downloadTorrent(gameZip, primary, self.exoCollectionDir, self.logger)
                    if os.path.isfile(primary) and os.path.getsize(primary) > 0:
                        self.__unzipGame__(primary, gGator)
                    else:
                        self.logger.log(
                            "  <ERROR> Could not obtain game data for %s" % gGator.game,
                            self.logger.ERROR,
                        )
                        return
                else:
                    self.logger.log(
                        '  <ERROR> Game zip missing and no unpacked tree found for %s. '
                        'Point collectionDir at a complete eXoDOS install, or enable downloadOnDemand.'
                        % gGator.game,
                        self.logger.ERROR,
                    )
                    return
        else:
            self.__unzipGame__(gameZipPath, gGator)
        self.logger.log("  unzipped")

        # Handle game update if it exists
        updateZipPath = os.path.join(util.getCollectionUpdateDir(self.exoCollectionDir, self.collectionVersion),
                                     gameZip)
        if os.path.exists(updateZipPath):
            self.logger.log("  found an update for the game")
            self.__unzipGame__(updateZipPath, gGator)

    def __resolveGameZipPath__(self, gameZip):
        """Locate the install zip using eXoDOS's known locations."""
        gamesDir = util.getCollectionGamesDir(self.exoCollectionDir, self.collectionVersion)
        candidates = [
            os.path.join(gamesDir, gameZip),
            # Full media package (eXo torrent GameData path)
            os.path.join(self.exoCollectionDir, 'Content', 'GameData', 'eXoDOS', gameZip),
            os.path.join(self.exoCollectionDir, 'Content', 'GameData', 'eXoDOS', gameZip.replace(' - ', '_ ')),
        ]
        for path in candidates:
            if os.path.isfile(path) and os.path.getsize(path) > 0:
                if path != candidates[0]:
                    self.logger.log("  found game zip at alternate path: %s" % path)
                return path
        return None

    def __resolveUnpackedGameSource__(self, gGator, gameTitleStem):
        """Find game files already extracted by eXo (install unzipped into eXoDOS/).

        eXo runs: unzip "eXoDOS\\<Title>.zip" -d .\\eXoDOS\\
        which leaves a folder under eXo/eXoDOS/ with the game binaries.
        """
        gamesDir = util.getCollectionGamesDir(self.exoCollectionDir, self.collectionVersion)
        confDir = os.path.join(self.collectionGamesConfDir, gGator.game)
        candidates = [
            os.path.join(gamesDir, gGator.game),
            os.path.join(gamesDir, gameTitleStem),
            # Title without trailing " (YYYY)" — eXo IndexName style
            os.path.join(gamesDir, gameTitleStem[:-7]) if len(gameTitleStem) > 7 else None,
            confDir if self.__looksLikeUnpackedGame__(confDir) else None,
        ]
        for path in candidates:
            if path and self.__looksLikeUnpackedGame__(path):
                return path
        return None

    @staticmethod
    def __looksLikeUnpackedGame__(path):
        """True when path holds real game binaries, not just !dos install scaffolding."""
        if not path or not os.path.isdir(path):
            return False
        skip_names = {
            'install.bat', 'install.bsh', 'install.command',
            'dosbox.conf', 'dosbox_linux.conf', 'extras',
        }
        skip_ext = {'.bat', '.bsh', '.command', '.conf', '.txt', '.md'}
        game_ext = {'.exe', '.com', '.dat', '.ovl', '.dll', '.bin', '.img', '.iso', '.cue'}
        try:
            entries = os.listdir(path)
        except OSError:
            return False
        for name in entries:
            lower = name.lower()
            if lower in skip_names:
                continue
            full = os.path.join(path, name)
            if os.path.isdir(full):
                # Nested game dir with binaries counts
                if ExoConverter.__looksLikeUnpackedGame__(full):
                    return True
                continue
            ext = os.path.splitext(lower)[1]
            if ext in game_ext:
                return True
            if ext not in skip_ext and os.path.getsize(full) > 8192:
                return True
        return False

    def __copyUnpackedGame__(self, sourceDir, gGator):
        """Copy an already-unpacked eXo game tree into the converter output."""
        destRoot = gGator.getLocalGameOutputDir()
        os.makedirs(destRoot, exist_ok=True)
        destGame = os.path.join(destRoot, gGator.game)
        if os.path.abspath(sourceDir) == os.path.abspath(
            os.path.join(self.collectionGamesConfDir, gGator.game)
        ):
            # Source is the !dos conf dir itself (rare fully-inlined layout).
            # Copy everything into destGame.
            if os.path.exists(destGame):
                shutil.rmtree(destGame)
            shutil.copytree(sourceDir, destGame)
        else:
            # Source is eXo/eXoDOS/<folder> produced by unzip -d eXoDOS
            if os.path.exists(destGame):
                shutil.rmtree(destGame)
            shutil.copytree(sourceDir, destGame)
        self.logger.log("  copied unpacked game -> %s" % destGame)
        self.__flattenDosnameSubdirIfWin3x__(gGator)

    # Unzip game zip
    def __unzipGame__(self, gameZipPath, gGator):
        with ZipFile(gameZipPath, 'r') as zipFile:
            # Extract all the contents of zip file in current directory
            self.logger.log("  unzipping " + gameZipPath)
            zipFile.extractall(path=gGator.getLocalGameOutputDir())
        # Check folder name // !dos folder, if not the same rename it to the !dos one
        unzippedDirs = [file for file in os.listdir(gGator.getLocalGameOutputDir()) if
                        os.path.isdir(os.path.join(gGator.getLocalGameOutputDir(), file))]
        if len(unzippedDirs) == 1 and unzippedDirs[0] != gGator.game and not gGator.isWin3x():
            self.logger.log("  fixing extracted dir %s to !dos name %s" % (unzippedDirs[0], gGator.game))
            os.rename(os.path.join(gGator.getLocalGameOutputDir(), unzippedDirs[0]), os.path.join(gGator.getLocalGameOutputDir(), gGator.game))
        # isWin3x path: lift <dosname>/* to game root so CWD matches eXoDOS
        # "mount c .\eXoDOS\<dosname>" (MyMenu starts at LFN root, not dosname).
        self.__flattenDosnameSubdirIfWin3x__(gGator)

    def __flattenDosnameSubdirIfWin3x__(self, gGator):
        """Move game.pc/<dosname>/* up to game.pc/ when isWin3x() is True.

        eXoDOS mounts C: at the dosname folder; on MiSTer/MyMenu the equivalent
        is flattening that folder so 1_Start.bat at the LFN root finds the EXE.
        Shared by zip extract and already-unpacked copy paths.
        """
        if not gGator.isWin3x():
            return
        # do not use getLocalGameDataOutputDir as game data are in subdir at that point
        gameOutputDir = gGator.getLocalGameOutputDir()
        gameSubDir = self.__resolveExtractedGameSubDir__(gameOutputDir, gGator.game)
        if gameSubDir is None:
            self.logger.log(
                '  <WARNING> Could not find extracted game subdir "%s" in %s; keeping extracted layout as-is'
                % (gGator.game, gameOutputDir),
                self.logger.WARNING
            )
            return

        # Already flat (payload files sit next to conf/bats at output root).
        if os.path.abspath(gameSubDir) == os.path.abspath(gameOutputDir):
            return

        subDirTempName = gGator.game + '-tempEDC'
        subDirTempPath = os.path.join(gameOutputDir, subDirTempName)
        suffix = 2
        while os.path.exists(subDirTempPath):
            subDirTempPath = os.path.join(gameOutputDir, subDirTempName + '-' + str(suffix))
            suffix += 1

        self.logger.log(
            "  flattening %s -> game root (win3x / eXoDOS mount-c semantics)"
            % os.path.basename(gameSubDir)
        )
        os.rename(gameSubDir, subDirTempPath)
        for gameFile in os.listdir(subDirTempPath):
            shutil.move(os.path.join(subDirTempPath, gameFile), gameOutputDir)
        # Check if it's empty !! a subdir might be named the same
        if len(os.listdir(subDirTempPath)) == 0:
            shutil.rmtree(subDirTempPath)

    @staticmethod
    def __resolveExtractedGameSubDir__(outputDir, expectedGameDir):
        strictPath = os.path.join(outputDir, expectedGameDir)
        if os.path.isdir(strictPath):
            return strictPath

        caseInsensitivePath = util._findSubdirCaseInsensitive(outputDir, expectedGameDir)
        if caseInsensitivePath is not None:
            return caseInsensitivePath

        extractedDirs = [entry for entry in os.listdir(outputDir) if os.path.isdir(os.path.join(outputDir, entry))]
        if len(extractedDirs) == 1:
            return os.path.join(outputDir, extractedDirs[0])
        return None

    # specific convertion type treatments after converting all games
    def __postConversion__(self):
        # Cleaning for some conversions
        if self.conversionType in [util.esoteric, util.simplemenu, util.mister]:
            self.logger.log('Post cleaning for ' + self.conversionType)
            # Remove gamelist.xml and downloaded_images folder
            if os.path.exists(os.path.join(self.outputDir, 'gamelist.xml')):
                os.remove(os.path.join(self.outputDir, 'gamelist.xml'))
            if os.path.exists(os.path.join(self.outputDir, 'downloaded_images')):
                shutil.rmtree(os.path.join(self.outputDir, 'downloaded_images'))
            if self.conversionType == util.mister:
                # delete empty genres dir
                dirs = [file for file in os.listdir(self.outputDir) if
                        os.path.isdir(os.path.join(self.outputDir, file))
                        and file not in ['games', 'cd', 'floppy', 'manuals', 'bootdisk', 'ao486', 'mymenu']]
                gamesDir = os.path.join(self.outputDir, 'games')
                if os.path.exists(gamesDir):
                    for genreDir in dirs:
                        shutil.rmtree(os.path.join(self.outputDir, genreDir))
                    mymenupacker.copySupportZips(gamesDir, self.scriptDir, self.logger)
                    self.logger.log('Assembling MyMenu frontend for ' + self.conversionType)
                    if not mymenupacker.extractFrontend(self.outputDir, self.scriptDir, self.logger):
                        self.logger.log('  Failed to assemble MyMenu frontend payload', self.logger.ERROR)
                    # move cd, floppy, boot disk into ao486 folder
                    if not os.path.exists(os.path.join(self.outputDir, "ao486")):
                        os.mkdir(os.path.join(self.outputDir, "ao486"))
                    self.logger.log("  Moving cd folder to ao486, this might take a while ...")
                    if os.path.exists(os.path.join(self.outputDir, "cd")):
                        shutil.move(os.path.join(self.outputDir, "cd"),
                                    os.path.join(os.path.join(self.outputDir, "ao486")))
                    self.logger.log("  Moving floppy folder to ao486, this might take a while ...")
                    if os.path.exists(os.path.join(self.outputDir, "floppy")):
                        shutil.move(os.path.join(self.outputDir, "floppy"),
                                    os.path.join(os.path.join(self.outputDir, "ao486")))
                    self.logger.log("  Moving bootdisk folder to ao486, this might take a while ...")
                    if os.path.exists(os.path.join(self.outputDir, "bootdisk")):
                        shutil.move(os.path.join(self.outputDir, "bootdisk"),
                                    os.path.join(os.path.join(self.outputDir, "ao486")))

                    self.logger.log("  Building ao486 VHD output")
                    useDosforge = dosforgevhd.DosforgeVhdBuilder.shouldUse(
                        self.conversionConf
                    )
                    if useDosforge:
                        self.logger.log(
                            '  Using dosforge VHD builder (set misterUseDosforge=false '
                            'to force template/ao486vhd path)'
                        )
                        vhdBuilder = dosforgevhd.DosforgeVhdBuilder(
                            self.scriptDir,
                            self.outputDir,
                            self.collectionVersion,
                            self.logger,
                            self.conversionConf,
                        )
                    else:
                        if dosforgevhd.DosforgeVhdBuilder.isAvailable(self.conversionConf):
                            self.logger.log(
                                '  Using template ao486vhd builder (misterUseDosforge disabled)'
                            )
                        else:
                            self.logger.log(
                                '  Using template ao486vhd builder (dosforge not on PATH)'
                            )
                        vhdBuilder = ao486vhd.Ao486VhdBuilder(
                            self.scriptDir,
                            self.outputDir,
                            self.collectionVersion,
                            self.logger,
                            self.conversionConf,
                        )
                    if not vhdBuilder.build():
                        self.logger.log(
                            '  <ERROR> ao486 VHD generation failed (frontend pack was still generated)',
                            self.logger.ERROR
                        )
                else:
                    self.logger.log(
                        '  Some critical errors seems to have happened during process.\n  Skipping MyMenu assembly phase',
                        self.logger.ERROR)

        elif self.conversionType == util.emuelec:
            self.logger.log('Post cleaning for ' + self.conversionType)
            # move gamelist downloaded_images, manuals
            if os.path.exists(os.path.join(self.outputDir, 'gamelist.xml')):
                shutil.move(os.path.join(self.outputDir, 'gamelist.xml'), os.path.join(self.outputDir, 'pc'))
            if os.path.exists(os.path.join(self.outputDir, 'manuals')):
                shutil.move(os.path.join(self.outputDir, 'manuals'), os.path.join(self.outputDir, 'pc'))
            if os.path.exists(os.path.join(self.outputDir, 'downloaded_images')):
                shutil.move(os.path.join(self.outputDir, 'downloaded_images'), os.path.join(self.outputDir, 'pc'))
            # delete empty genres dir
            dirs = [file for file in os.listdir(self.outputDir) if
                    os.path.isdir(os.path.join(self.outputDir, file)) and file not in ['pc', 'pcdata']]
            for genreDir in dirs:
                shutil.rmtree(os.path.join(self.outputDir, genreDir))
            instructions = open(os.path.join(self.outputDir, 'instructions for emuelec.txt'), 'w')
            instructions.write('The script /emuelec/scripts/emuelecRunEmu.sh must be modified to read the exported configuration files (need to comment/uncomment the relevant RUNTHIS commands)\n')
            instructions.close()
