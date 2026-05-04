# ExoDOSConverter Codebase Reference

This document summarizes every code file in this repository and how the pieces work together.

## 1) What this project does

ExoDOSConverter is a Tkinter desktop tool that converts LaunchBox-based retro collections into outputs usable by multiple target environments (Batocera, Recalbox, Retropie, Retrobat, Emuelec, OpenDingux flavors, MiSTer).  
It supports multiple source collections:

- eXoDOS v6
- eXoWin3x v2
- C64 Dreams
- eXoAppleIIGS
- eXoScummVM

## 2) Entry points and execution scripts

### `main.py`
- Program entry point.
- Creates `Logger`, instantiates `ExoGUI`, and starts UI loop.

### `main_tui.py`
- Linux TUI entry point.
- Creates `TuiLogger`, instantiates `ExoTUI`, and starts the Textual app loop.

### `ExoDOSConverter.sh`
- Runs `python3 main.py`.

### `exoDOSConverter.sh`
- Also runs `python3 main.py` (same behavior as above script).

### `launch_exodosconverter_tui.sh`
- Linux launcher for TUI mode.
- Bootstraps local virtualenv dependencies and runs `python main_tui.py`.

### `build.bat`
- Windows packaging script:
  - creates `build/`
  - copies `.py` and icon files
  - runs `pyinstaller --icon=exodosicon.ico --clean -F main.py`
  - removes build intermediates
  - copies runtime assets (`data`, `conf`, `GUI`, markdown/changelog) into `dist`
  - renames output exe/folder to include user-provided version

## 3) High-level runtime architecture

1. `main.py` starts `ExoGUI` (Tk desktop UI) or `main_tui.py` starts `ExoTUI` (Textual terminal UI).
2. Both frontends use shared state/workflow in `exoappstate.py` for:
   - config load/save (`conf/conf-exo.conf`)
   - path normalization and collection detection
   - game selection/filter/custom selection file operations
   - conversion parameter assembly and converter dispatch
3. UI flow then loads:
   - persistent config (`conf/conf-exo.conf`) via `conf.loadConf`
   - UI labels/help (`gui/gui-en-exo.csv`) via `util.loadUIStrings`
   - game mapping cache (`data/*.csv`) via `util.fullnameToGameDir`
4. User selects games and triggers **Proceed**.
5. Frontend chooses converter by detected collection type:
   - `ExoConverter`
   - `C64Converter`
   - `AppleIIGSConverter`
   - `ScummVMConverter`
6. Converter performs per-game processing and metadata export (`gamelist.xml`).
7. Target-specific post-processing adjusts output layout/launch artifacts.
8. Logs are pushed through queue-based logger and rendered in the active frontend.

## 4) Core shared concepts

- **Collection detection**: `util.validCollectionPath` and `util.exoCollectionsDirs`.
- **Metadata source**: collection XML in `xml/all` or `Data/Platforms`.
- **Image/manual handling**: copied to output `downloaded_images/` and `manuals/`.
- **Genre mapping**:
  - optional override CSV `data/fixGenres-<Collection>.csv`
  - fallback mapping in `genre_mapping.py`
- **DOSBox conversion**:
  - config parsing/writing: `dosboxconfv6.py`
  - command line rewriting: `ConfConverter` + `CommandHandler`
- **Controller mapping**:
  - keyb2joypad CSV parser: `Keyb2Joypad`
  - target format generation (mainly Batocera): `Mapping`

## 5) File-by-file reference (all code files)

## `TDLindexer.py`
- Purpose: legacy helper for the older TDL-based MiSTer packaging flow.
- Functions:
  - `scantree_files(path)`: recursive file discovery.
  - `clean_name(name)`: filename cleanup helper.
  - `index(outputDir, scriptDir, fullnameToGameDir, isDebug, preExtractGames, logger)`:
    - extracts legacy distro payload if needed
    - scans game archives and generates DOS index files for TDL
    - creates `FILES.IDX` / `TITLES.IDX` and staged `tdlprocessed` output
    - handles pre-extracted game-data move logic in the TDL workflow

## `appleiigsconverter.py`
- Class: `AppleIIGSConverter`
- Purpose: conversion path for eXoAppleIIGS.
- Methods:
  - `convertGames`: metadata load, loop games, write `gamelist.xml`, errors.
  - `__convertGame__`: genre + game conversion + metadata export.
  - `__copyGameDataToOutputDir__`: unzip source game zip, extract `.po/.2mg/.hdv`, normalize output names.
  - `getLocalGameOutputDir`: output path with or without genre subfolders.

## `c64converter.py`
- Class: `C64Converter`
- Purpose: conversion path for C64 Dreams.
- Methods:
  - `convertGames`: standard conversion loop and error log handling.
  - `__convertGame__`: convert one title and update metadata/gamelist.
  - `__copyManual`: copies `<game> Manual.cbz` if present.
  - `__copyGameDataToOutputDir__`: handles disk/cart files and output strategy.
  - `handleCompilationDisk`, `handleM3U`, `handleMultiDisksWithoutM3U`,
    `handleSingleDisk`, `handleSingleDiskWithCmd`, `handleSingleDiskWithoutCmd`, `createM3u`: detailed C64 multi-disk/launch resolution.
  - `getLocalGameOutputDir`: output path helper.

## `commandhandler.py`
- Class: `CommandHandler`
- Purpose: rewrites DOSBox command lines and mounted paths for target environments.
- Key methods:
  - `__dosRename__`: rename files to DOS-compatible 8.3 names.
  - `useLine`: decides whether a command line is retained.
  - `__pathListInCommandLine__`: parse token ranges for command arguments.
  - `reducePathExoPart`, `reducePath`: remove source collection prefixes and adjust path roots.
  - `handleImgmount`, `handleMount`, `handleBoot`: rewrite core DOSBox commands.
  - `__cleanCDname__`, `__cleanCue__`: normalize mounted media filenames and cue internals.

## `conf.py`
- Config parsing helpers:
  - `cleanString`
  - `loadConf(confFile)` reads `key = value` style `.conf` with comment support.

## `confconverter.py`
- Class: `ConfConverter`
- Purpose: convert source DOSBox config + autoexec to generated `dosbox.cfg` and `dosbox.bat`.
- Methods:
  - `processV6`: for v6-style config layering (`default + game + options` where relevant).
  - `setUserParameters`: applies GUI-selected settings (fullscreen, renderer, vsync, mapper, etc.).
  - `processV5`: legacy conversion path.
  - `__createDosboxBat__`: builds executable bat from autoexec body.
  - `__convertLine__`: per-command rewrite pipeline.
  - `__handlePotentialSubFile__`: recursively rewrites called sub-bat files (encoding aware).
  - `__handleRunBat__`: special-case run.bat treatment for known problematic games.

## `dosboxconfv6.py`
- Functions:
  - `loadDosboxConf(dosboxFile, dosboxConf)`: parse sections/keys (excluding `[autoexec]`).
  - `writeDosboxConf(path, dosboxConf)`: write sectioned config dict back to file.

## `exoconverter.py`
- Class: `ExoConverter`
- Purpose: main converter for eXoDOS/eXoWin3x.
- Methods:
  - `convertGames`: prechecks, metadata load, keyb2joypad load, per-game loop, gamelist write, post-processing, error log.
  - `__convertGame__`: metadata/genre, build `GameGenerator`, convert if not already output.
  - `__copyGameDataToOutputDir__`: finds source zip from game conf bats, optional download-on-demand, unzip, update zip merge, Win3x flattening.
  - `__unzipGame__`: unzip and fix root directory naming.
  - `__postConversion__`: target-specific cleanup; MiSTer path assembles MyMenu frontend payload, organizes ao486 media folders, and now triggers automatic ao486 VHD generation.

## `exogui.py`
- Class: `ExoGUI`
- Purpose: full desktop UI and orchestration layer.
- Main responsibilities:
  - build all UI frames (paths/config/selection/buttons/console)
  - load and persist config
  - validate collection path and detect version
  - build/load image cache
  - manage game selection and custom selection files
  - launch conversion worker thread
  - enable/disable controls based on context
  - stream logger queue to console text widget
- Methods include:
  - setup/drawing: `draw`, `__drawMainframe__`, `__drawPathsFrame__`, `__drawConfigurationFrame__`, `__drawSelectionFrame__`, `__drawButtonsFrame__`, `__drawConsole__`
  - handlers: `__handleCollectionFolder__`, `__filterGamesList__`, selection load/save/move methods
  - process actions: `__clickVerify__`, `__clickSave__`, `__clickProceed__`
  - UI state and console refresh: `__handleComponentsState__`, `__updateConsoleFromQueue__`, `__writeToConsole__`

## `exoappstate.py`
- Class: `ExoAppState`
- Purpose: shared non-visual app workflow used by TUI (and suitable for reuse by other frontends).
- Responsibilities:
  - load/normalize configuration values (including Linux path normalization)
  - refresh/validate collection and load cache/game maps
  - maintain selected games and filter state
  - load/save custom selection files
  - save config file using UI-string order/help comments
  - assemble conversion config and build/run appropriate converter class

## `exotui.py`
- Class: `ExoTUI` (Textual `App`)
- Purpose: native Linux terminal UI frontend.
- Responsibilities:
  - render path/config/forms, available/selected game lists, action buttons, and log pane
  - mirror GUI actions (refresh, verify, save config, proceed, load/save selection)
  - run long operations (collection refresh, conversion) in background threads
  - consume queue logs and render with severity colors
  - apply conversion/collection-dependent control enable/disable rules

## `gamegenerator.py`
- Class: `GameGenerator`
- Purpose: per-game conversion engine for ExoConverter path.
- Flow:
  - copy baseline game/config files
  - run DOSBox conversion through `ConfConverter`
  - apply specific fixes
  - run target-specific post-conversion transform
- Notable behavior:
  - `isWin3x()` currently hardcoded to `True` (important path behavior side effect).
  - handles dependency unzips for specific sequel titles.
  - target-specific methods:
    - `__postConversionForEmuelec__`
    - `__postConversionForRecalbox__`
    - `__postConversionForBatocera__`
    - `__postConversionDosboxPureZip__`
    - `__postConversionForMister__`
    - `__postConversionForOpenDingux__`
    - `__postConversionForRetropie__`

## `genre_mapping.py`
- Defines normalized target genre enum `Genre`.
- Mapping dictionaries:
  - `GENRE_MAPPER` for direct category mapping.
  - `MULTI_GENRE_MAPPER` for explicit multi-genre overrides.
- `mapGenres(input_genres)`:
  - deduplicates/sorts genres
  - applies multi-genre overrides
  - enforces precedence for some categories (FPS/RPG/Puzzle/etc.)
  - falls back to `Unknown`.

## `keyb2joypad.py`
- Class: `Keyb2Joypad`
- Purpose: parse `data/keyb2Joypad.csv` into per-game control mappings.
- Methods:
  - `load`: reads CSV (custom `$` separator), maps columns/buttons/sticks/hotkeys.
  - `get`, `getValues`: field extraction helpers.
  - `extractCtrlButtonConf`: writes mapping if a cell has values.
  - `emptyList`: blank value check helper.

## `lists.py`
- Contains one list constant:
  - `gamesWithRunBatHandling`: games requiring explicit run.bat custom handling in converter paths.

## `logger.py`
- Class: `Logger`
- Purpose: dual logging sink for console output and UI queue.
- Methods:
  - `log`: enqueue + print, supports line replacement (progress bars).
  - `logProcess`: streams subprocess stdout/stderr into logger with ANSI strip.
  - `printDict`, `logList`: convenience wrappers.

## `tuilogger.py`
- Class: `TuiLogger`
- Purpose: queue-only logger variant for Textual UI.
- Behavior:
  - reuses `Logger` queue contract
  - suppresses direct stdout printing so terminal rendering remains controlled by Textual

## `mapping.py`
- Class: `Mapping`
- Purpose: generate target controller mapping files (primarily Batocera `padto.keys`).
- Methods:
  - `__initGameMapping__`: builds final mapping from defaults + optional stick mapping + keyb2joypad overrides.
  - `__convertK2JToGeneric__`: normalize key naming.
  - `mapForBatocera`:
    - use premade mapping from `data/padtokeys` if available
    - otherwise generate JSON mapping output in game dir.

## `mymenupacker.py`
- Purpose: MyMenu frontend assembly helper for MiSTer packaging.
- Functions:
  - `copySupportZips`: copies optional support archives into `games/`.
  - `extractFrontend`: extracts `data/mister/distro.zip` into output root, normalizing frontend folder to `mymenu/`.

## `ao486vhd.py`
- Class: `Ao486VhdBuilder`
- Purpose: build ao486-compatible VHD images from MiSTeR conversion output.
- Responsibilities:
  - detect single-game vs multi-game mode from converted `games/` folders
  - choose build name from the conversion run build name (single-game auto-name or user-provided multi-game collection name)
  - stage `C:\` layout payload (`GAMES`, `MYMENU`, optional support archives)
  - preserve external MiSTeR media automation by keeping `cd`, `floppy`, and `bootdisk` alongside the generated VHD inside each build pack directory
  - size-select template VHDs from DOS/Win3 template families with extra growth buffer
  - for DOS FAT32 builds, prefer `450M-DOS71.vhd` as the default FAT32 base when available
  - auto-expand selected template when required free space exceeds current template free capacity
  - estimate FAT/cluster metadata overhead during sizing and retry with larger targets when copy-time disk-full errors still occur
  - for FAT32 templates, use rebuild-based expansion (reformat larger FAT32 image with preserved DOS boot sector + recopy template payload) to avoid `fatresize` partition-growth limits on small FAT32 bases
  - patch `AUTOEXEC.BAT` with managed ExoDOSConverter autoboot block
  - emit final VHD file under `<run-output>/ao486/<build-name>/` (auto-suffixed on collisions)

## `metadatahandler.py`
- Class: `MetadataHandler`
- Purpose: read source metadata and write output gamelist metadata.
- Responsibilities:
  - parse collection XML into `DosGame` tuples
  - resolve front image/manual paths
  - compute single target genre
  - create/update/write `gamelist.xml`
  - manage hidden entries (for multi-file auxiliary outputs)
  - apply optional fixed-genre CSV overrides
- Important methods:
  - `parseXmlMetadata`
  - `processGame`
  - `__writeGamelistEntry__`
  - `writeHiddenGamelistEntry`
  - `loadFixGenre`
  - `buildGenre`

## `mister.py`
- Purpose: MiSTer-specific post-processing helpers.
- Functions:
  - media cleanup/translation: `removeUnusedCds`, `batsAndMounts`, `handleRunBat`
  - command converters: `convertSoundConfig`, `convertImgMount`, `convertMount`, `convertBoot`, `handlesFileType`
  - path/media relocation: `locateMountedFiles`, `convertCD`, `convertFloppy`, `convertBootDisk`, `convertMountedFolder`
  - convenience batch generation: `createSetupBat`, `createEditBat`
  - about image generator: `text2png` (draws text + cover art into preview image)

## `scummvmconverter.py`
- Class: `ScummVMConverter`
- Purpose: conversion path for eXoScummVM.
- Methods:
  - `convertGames`: standard converter loop.
  - `__convertGame__`: convert one game and register resulting output folders in gamelist.
  - `__copyGameDataToOutputDir__`: unzip game and handle single-folder vs multi-platform-folder layouts.
  - `generatescummvmfiles`: parse source bat and emit `.scummvm` key file(s).
  - `getLocalGameOutputDir`: output path helper.

## `util.py`
- Purpose: central constants + utility functions used across the project.
- Main constant groups:
  - conversion type labels
  - collection version labels
  - collection directory metadata (`exoCollectionsDirs`)
  - mapper option lists
  - download URL and MiSTer name map
- Function groups:
  - mapper and collection helpers:
    - `getMapperValues`, `isWin3x`
    - `getCollectionRootDirToken`, `getCollectionGamesDirToken`
    - `getCollectionMetadataDir`, `getCollectionGamesDir`, `getCollectionGamesConfDir`, `getCollectionUpdateDir`
    - `getCollectionMetadataID`, `getCollectionPicID`
  - config/ui filename helpers:
    - `getKeySetString`, `getConfFilename`, `getConfBakFilename`, `getGuiStringsFilename`
  - process/download:
    - `callProcess`
    - `installAria2cWindows`, `installAria2cLinux`, `installAria2cMac`, `installAria2c`
    - `downloadTorrent`, `downloadZip`
  - UI and path/image:
    - `loadUIStrings`, `localOSPath`, `resize`, `getCleanGameID`, `getRomsFolderPrefix`
  - collection validation and game mapping:
    - `isCollectionPath`, `validCollectionPath`
    - `fullnameToGameDir`, `buildCollectionCSV`
  - image cache:
    - `findPics`, `cleanPicName`, `findPic`
    - `buildPicCache`, `loadPicCache`, `buildCache`
  - duplicate-folder diagnostics:
    - `checkMultipleofSameGame`, `moveFolderifExist`

## `wckToolTips.py`
- Third-party tooltip manager utility for Tk widgets.
- Class `ToolTipManager`:
  - tooltip registration/unregistration
  - delayed display and hide handlers on enter/leave.
- Module wrappers:
  - `register(widget, text)`
  - `unregister(widget)`

## `test/test_genres.py`
- Script-style test/analysis helper (not pytest-based).
- Purpose:
  - compare old genre logic (`buildGenre_old`) vs new `MetadataHandler.buildGenre`
  - generate CSV/report of changed mappings.
- Notes:
  - hardcoded collection path (`exo_folder = r'Z:\\'`)
  - depends on `pandas` and `tabulate` (not present in `requirements.txt`)

## 6) Converter behavior differences by source collection

- **eXoDOS / eXoWin3x**:
  - full DOSBox command/config conversion path (`ExoConverter` + `GameGenerator` + `ConfConverter` + `CommandHandler`)
  - optional download-on-demand for missing zips
  - target-specific post transforms for each output platform

- **C64 Dreams**:
  - file-centric conversion (`.crt/.d64/.d81/.t64/.g64/.m3u`)
  - explicit handling of multi-disk and `.cmd` launch parameters

- **eXoAppleIIGS**:
  - unzip and normalize Apple II GS game image files (`.po/.2mg/.hdv`)

- **eXoScummVM**:
  - unzip game payload
  - generate `.scummvm` key file from source batch launch command

## 7) Important runtime artifacts generated in output

- Each conversion run uses a new child build directory under the selected output root; all items below are created within that run directory.
- `gamelist.xml` (metadata index)
- `downloaded_images/` and `manuals/`
- per-game folders/files (`.pc`, `.zip`, `.m3u`, `.scummvm`, etc. depending on flow)
- `error_log.txt` when conversion errors occur
- MiSTer-specific:
  - frontend folder `mymenu/`
  - game folders under `games/` with `autorun.bat` entrypoints
  - `ao486` media structure (`cd`, `floppy`, `bootdisk`) moved under `ao486/<build-name>/`
  - per-build ao486 pack directories in `ao486/<build-name>/` containing VHD + media folders

## 8) External dependencies used by code

- Runtime dependencies from `requirements.txt`:
  - `Pillow`
  - `requests`
  - `chardet`
  - urllib/idna/certifi/charset-normalizer stack
  - `tk` (Tkinter is used heavily in UI)
- Additional dependency used only by script in `test/test_genres.py`:
  - `pandas`
  - `tabulate`
