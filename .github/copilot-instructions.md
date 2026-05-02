# ExoDOSConverter Copilot Instructions

## Build, run, test, and lint commands

- Install dependencies:
  - `pip install -r requirements.txt`
- Run the app locally:
  - `python3 main.py`
  - or `./ExoDOSConverter.sh` (same target)
- Build Windows executable (from repo root):
  - `build.bat`
  - manual equivalent from `build.txt`: `pyinstaller --icon=exodosicon.ico --clean -F main.py`

### Tests

- There is no pytest/unittest suite configured in this repository.
- Existing test helper script:
  - `python3 test/test_genres.py`
- Single-test equivalent in this codebase is running that single script directly.
- `test/test_genres.py` is environment-dependent: it expects a local eXo collection path and imports `pandas` + `tabulate`.

### Lint

- No lint tooling/configuration is defined in this repository (`ruff`, `flake8`, `pylint`, `pyproject.toml`, etc. are absent).

## High-level architecture

`main.py` starts the Tkinter UI (`ExoGUI`). The GUI is the orchestration entrypoint: it loads persisted settings from `conf/conf-exo.conf`, loads UI labels/help text from `gui/gui-en-exo.csv`, validates the selected collection path, builds image caches, and dispatches conversion work in a background thread when the user clicks **Proceed**.

Converter selection is collection-driven in `ExoGUI.__clickProceed__`:

- `ExoConverter` for `eXoDOS v6` / `eXoWin3x v2`
- `C64Converter` for `C64 Dreams`
- `AppleIIGSConverter` for `eXoAppleIIGS`
- `ScummVMConverter` for `eXoScummVM`

All converters share the same broad loop:

1. load metadata (`MetadataHandler.parseXmlMetadata`)
2. ensure output support folders (`downloaded_images`, `manuals`)
3. convert each selected game
4. update/write `gamelist.xml`
5. write `error_log.txt` when needed

For DOS/Win3x conversion, `ExoConverter` delegates per-game work to `GameGenerator`, which:

- copies game/config payload
- converts DOSBox config via `ConfConverter`
- rewrites command lines via `CommandHandler` (`mount`, `imgmount`, `boot`, nested bat handling)
- applies distro-specific post steps (Batocera/Retrobat/Recalbox/Retropie/Emuelec/OpenDingux/MiSTer)

MiSTer output has additional post-processing in `mister.py`, then frontend assembly from `data/mister/distro.zip` via `mymenupacker.py`, producing a `mymenu/` root folder plus MyMenu-accessible game folders.

## Repository-specific conventions

- Use constants and helpers in `util.py` as the source of truth for:
  - supported collection IDs (`EXODOS`, `EXOWIN3X`, etc.)
  - conversion type names (`Batocera`, `MiSTer`, etc.)
  - path derivation (`getCollectionGamesDir*`, `getCollectionMetadataDir`, `getRomsFolderPrefix`)
- Do not hardcode collection folder layouts directly in new code; reuse `util.exoCollectionsDirs` + helper accessors.

- Logging is queue-based through `Logger` (not `logging` module). GUI console rendering (`ExoGUI.__updateConsoleFromQueue__`) depends on `Logger.log_queue`; keep that contract when adding logs.

- Metadata lookups are keyed by lowercase DOS shortname (`metadatas[dosname.lower()]`). Preserve this casing convention; special-case handling like `H.E.R.O` already exists in `MetadataHandler`.

- Genre assignment precedence is:
  1. per-collection CSV overrides (`data/fixGenres-*.csv`)
  2. `genre_mapping.py` (`MULTI_GENRE_MAPPER`, then `GENRE_MAPPER`)
  Keep changes centralized there instead of adding ad-hoc genre logic in converters.

- Generated game naming is intentionally conversion-type dependent:
  - short `game.pc` names vs long clean names (`util.getCleanGameID`)
  - optional zip output for dosbox-pure
  - optional genre subfolders
  Follow existing naming/path decisions in `MetadataHandler.__writeGamelistEntry__` and `GameGenerator`.

- `GameGenerator.isWin3x()` currently always returns `True` intentionally; avoid “fixing” this without validating downstream path logic (`ConfConverter`, `CommandHandler`, MiSTer transforms).

- Generated batch files intentionally use DOS/Windows semantics (CRLF newlines and Windows-style paths in many branches). Be careful when refactoring path or newline handling.
