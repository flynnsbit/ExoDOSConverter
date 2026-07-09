# AGENTS.md

## Quick start

```bash
pip install -r requirements.txt
python3 main.py          # Tkinter GUI
python3 main_tui.py      # Textual TUI (Linux)
```

No lint or formatter configured. Single test requires `pandas`, `tabulate`, and a local eXo collection path:

```bash
python3 test/test_genres.py
```

## Commit workflow

Run `./pre_commit_cleanup.sh` before push — it amends HEAD to strip Copilot co-author lines.

VHD files are gitignored. Never commit `.vhd` (>100 MB breaks GitHub push).

## Architecture

- **Two frontends** (GUI `exogui.py`, TUI `exotui.py`) share one backend via `exoappstate.py`.
- Conversion flow: `exoconverter.py` orchestrates → `gamegenerator.py` per-game → post-processing (MiSTeR `mister.py`, ao486 `ao486vhd.py`).
- Logging is a custom queue-based `Logger` (not stdlib `logging`). Both UIs consume `Logger.log_queue`.

## Key conventions an agent would get wrong

1. **`GameGenerator.isWin3x()` always returns `True`** — this is intentional. Do not "fix" it.
2. **Metadata keys are lowercase DOS shortnames**: `metadatas[dosname.lower()]`.
3. **Genre mapping precedence**: per-collection CSV (`data/fixGenres-*.csv`) → `MULTI_GENRE_MAPPER` → `GENRE_MAPPER` → `"Unknown"`.
4. **Generated batch files use DOS semantics** (CRLF, backslash paths). Don't normalize newlines.
5. **Collection paths must use helpers from `util.py`** (`exoCollectionsDirs`, accessors). Never hardcode.
6. **Each conversion creates a child build folder** under the output root — never writes directly to the root.
7. **VHD template discovery order**: `$EXODOS_AO486_TEMPLATE_ROOT` → `<repo>/vhdtemplate` → `~/exodos-build` → `/home/shawn/exodos-build` → legacy data fallback. Preferred FAT32 template: `vhdtemplate/450M-DOS71.vhd`.

## Key files to read first

`ao486vhd.py`, `exoconverter.py`, `exoappstate.py`, `util.py`, `CODEBASE_REFERENCE.md`

## Open backlog

- README.ANS metadata generator (`mistereadmeans.py`)
- `data/mister/overrides.csv` for remaining Top300 R-new diffs
- Native PC PicoIDE conversion type

## dosforge VHD path (Phase C)

MiSTer packs prefer **`dosforgevhd.DosforgeVhdBuilder`** when `dosforge` is on
PATH (or `misterDosforgeExecutable` is set). It stages `GAMES` + `MYMENU` +
`AUTOEXEC.BAT`/`AUTORUN_EDC.BAT`, sizes the VHD from payload + buffer, then:

```
dosforge create --custom-payload-path <vhd-root> --boot-mode msdos622|msdos71 …
```

Falls back to Linux-only `ao486vhd.Ao486VhdBuilder` (template copy) when
dosforge is unavailable or `misterUseDosforge=false`.

Optional conf keys: `misterUseDosforge`, `misterDosforgeExecutable`,
`misterBootMode` (default `auto`), `misterDosInstallProfile`,
`misterDosforgeBootAssets`, `misterSaveBufferMiB`.

## Other instruction sources

- `.github/copilot-instructions.md` — full architecture and conventions reference
- `CODEBASE_REFERENCE.md` — file-by-file module/method summary
- `context.md` — session history and operational rules
- `/home/shawn/Projects/exodos-toolkit/plan.md` — full MiSTer automation plan
