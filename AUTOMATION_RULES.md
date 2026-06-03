# AUTOMATION_RULES.md

Canonical rules spec for the eXoDOS → MiSTer (and later Native-PC + PicoGUS + PicoIDE)
converter. Every rule has: trigger, input shape, output shape, source citation, priority.

**Architecture in one paragraph.** One payload tree (`C:\GAMES\<dosname>\`, eXoDOS-shaped,
verbatim copy from `G:\eXoDOS\eXo\eXoDOS\!dos\<dosname>\`) plus N parallel lightweight
view trees (`C:\<view-root>\<bucket>\<Long Title>\AUTORUN.BAT` + `README.ANS`, ~4 KB
per game per view). MyMenu navigates view trees live; stub bats `cd \GAMES\<dosname>`
into the real payload and run the rewritten launch sequence. Default views: A-Z (37
buckets) + All Games flat. Optional views: Year / Genre / Playlist / Source / Developer /
Publisher / Series.

**Priority key.** P0 = universal mechanical rule, must always emit. P1 = common pattern,
>10% of games. P2 = uncommon, <10%. P3 = escape-hatch via `data/mister/overrides.csv`.

---

## Section 1 — Universal mechanical rules (P0)

These apply to EVERY generated stub. Mined from A6 (original VHD vs Top300_updates
SHA256 diff across 300 games) and A3 (autorun_dump.txt across 286 games).

### R1 — CD-mount: `imgset` → `CALL imgtry` with CHD-preferred fallback
**Trigger:** game has ≥1 CD image. Frequency: **1220/7666 games (15.9%)** across full
eXoDOS v6 (NOT the 45% previously cited, which was a curated-Top300 subset). The vast
majority of games (6446 / 84.1%) need no CD mount at all.
**Input (legacy from eXoDOS dosbox.conf [autoexec]):**
`imgmount d ".\eXoDOS\<dosname>\cd\<image>.cue" -t cdrom`
**Output (emit):** `CALL imgtry ide10 D "/cd/<dosname>/<image>.chd" "/cd/<dosname>/<image>.cue"`
- Source-extension priority: `.chd` > `.cue` > `.iso` > `.img` > `.bin`
- Applies identically to `ide11` (second CD drive), `fdd0`/`fdd1` (floppy via R-Floppy), and
  `ide00`/`ide01` (bootdisk via R-Boot)

### R1a — Multi-disc Pattern A (disc-swap on single drive)
**Trigger:** legacy bat has single `imgmount d "a.cue" "b.cue" ...` line with N≥2 images
on the same drive letter. Frequency: vast majority of multi-disc games.
**Examples:** Gabriel Knight 2 (6 discs), 7th Guest (2 discs), most multi-CD titles.
**Output (emit):** `CALL imgtry ide10 D "a.chd" "b.chd" "c.chd" ...` — imgtry accepts
multi-image lists; MiSTer's AO486 supports Ctrl-F4-equivalent disc swap on each IDE CD slot.
**Preserve** any user-facing `echo This game has N CDs, press <key> to switch` text as
informational lines before the launcher.

### R1b — Multi-disc Pattern B (multi-drive expansion content)
**Trigger:** legacy bat has multiple `imgmount` lines mapping different drive letters
(D:, E:, F:, … up to J:) to different CD images. Auto-detect by: more than 2 distinct
drive letters used for cdrom mounts.
**Frequency:** ~10-20 games out of 88 multi-disc total (needs precise count in Phase D
pre-flight; estimate). Known examples: **Links LS 1997 (9 images across 7 drives)**,
likely Pandora Directive, Wing Commander IV PoF (6 images each — need verification).
**Constraint:** AO486 has only 2 IDE CD slots (`ide10` = D:, `ide11` = E:). Cannot
directly emulate 7-drive configs.
**Strategy:**
1. **Default behaviour:** emit `CALL imgtry ide10 D` with the first image, emit
   `CALL imgtry ide11 E` with the second image, log MULTI_DRIVE_CD_WARNING listing
   the dropped images for user awareness.
2. **Escape hatch via `overrides.csv` `__multi_drive_cd_swap: true`:** ships a small
   helper bat that lets the user manually swap any of the N images into the D: or E:
   slot via a per-game menu (uses MiSTer `imgtry` runtime swap support).
3. **For Native PC (PicoIDE) target later:** PicoIDE may support more CD drives — no
   work needed now, just preserve the per-image manifest in `<game>.cdimages` companion
   file for future use.
**Phase D pre-flight action:** classify each multi-disc game as A or B and report in
build_report.txt.

### R1c — Multi-disc Pattern A frequency distribution
**Across full eXoDOS v6:**
- 1132 games (14.77%): 1 CD image
- 53 games (0.69%): 2 CD images
- 19 games (0.25%): 3 CD images
- 10 games (0.13%): 4 CD images
- 2 games (0.03%): 5 CD images
- 3 games (0.04%): 6 CD images (GK2, pandora, WC4PoF)
- 1 game (0.01%): 9 CD images (LinksLS1)
**Source:** dosbox.conf [autoexec] `imgmount` scan, 2026-06-03.
**Source:** Top300_updates universal pattern, verified across LORDSOFA, ABUSE199,
ALBION19, DESCENT1, 7thguest, Abuse, ActionSo, etc. (`session-state/files/a5_a6_vhd_mining_report.md`).
**Full-collection scan (2026-06-03):** 1220/7666 games (15.9%) have at least one CD;
6446 (84.1%) have none. See R1c for image-count breakdown.

### R2 — `pause` → `@jchoice` universal substitution
**Trigger:** any generated bat needing a "press any key" prompt. Frequency: 300/300
games (3_Setup.bat) + 145/286 (~50.7%) AUTORUN.BAT.
**Input (legacy):** `pause`
**Output (emit):** `@jchoice`
- Joystick-friendly any-key prompt (same JCHOICE.EXE binary, no-arg mode)
- Bat emitter MUST NEVER emit bare `pause`
- Final stub line is always `@jchoice` (gives user time to read final output before
  MyMenu returns)
**Source:** Top300_updates universal pattern; root cause of 300/300 `3_Setup.bat` diffs.

### R3 — Drive-letter `e:` → `c:` (single-VHD normalisation)
**Trigger:** legacy bat uses `e:` / `cd e:\GAMES\…`. Frequency: 2/286 in AUTORUN.BAT
(low because most updates already normalised); will rise inside `1_Start.bat`/`run.bat`
payloads.
**Input (legacy):** `e:` / `cd e:\GAMES\<dosname>`
**Output (emit):** `c:` / `cd \GAMES\<dosname>` (or drop line if redundant — stub starts on
C: already after `cd \GAMES\<dosname>`)
- CD/floppy drive letters (`d:`, `f:`, `g:`, `a:`) are UNTOUCHED — those are dynamic
  mount targets, not partition letters
**Source:** Single-VHD architectural decision (#3); Top300 used C: + E: dual-volume.

### R4 — `@echo off` prefix always emitted
**Trigger:** every generated bat. Frequency: 286/286.
**Output (emit):** `@echo off` as line 1 of every stub.
**Source:** Universal hygiene; explicit in A6 finding R4.

### R5 — Multi-step `cd` chain → single `cd \GAMES\<dosname>`
**Trigger:** legacy bat uses nested `cd <subdir>` chain. Frequency: ~286/286 (universal).
**Input (legacy):**
```
cd Abuse
cd Abuse
call run
```
**Output (emit):**
```
cd \GAMES\<dosname>\Abuse\Abuse
call run
```
- The stub already does `cd \GAMES\<dosname>` before the rewritten payload, so collapse
  any post-cd chain into a single fully-qualified path
- Preserve case as it appears in the eXoDOS payload (DOS is case-insensitive but LFN
  display matters)
**Source:** A3-R12 (nearly universal); ALBION1 (cd adark1, cd DARK, cd INDARK), Abuse,
7thguest, etc.

### R6 — Stub AUTORUN.BAT canonical shape
**Trigger:** every game, every view tree.
**Output (emit) — full template:**
```
@echo off
cd \GAMES\<dosname>
<R5 collapsed cd chain if any>
<R1 imgtry mount lines, one per disc/floppy/bootdisk>
<launcher invocation: call run / call <game>.exe / <game>>
@jchoice
```
- Stub is written with CRLF line endings, CP437 encoding
- Stub lives at `C:\<view-root>\<bucket>\<Long Title>\AUTORUN.BAT`
- Stub size target: ≤256 B for no-CD games, ≤512 B for CD games
**Source:** Synthesis of R1-R5 + A9 stub-indirection architecture.

---

## Section 2 — First-run-fix sentinels — NOT migrated (P3 awareness)

### R7 — `IF NOT EXIST FIXED.TXT GOTO FIXGAME` pattern
**Trigger:** legacy game with payload-repair `xcopy` routine + `FIXED.TXT` sentinel.
**Action:** **DO NOT MIGRATE.** New builds stage fresh from `G:\eXoDOS\eXo\eXoDOS\!dos\<dosname>\`
which is already healthy. Recorded for context only.
- If a game does fail on fresh staging and needs first-run repair, that goes through
  `data/mister/overrides.csv` `__first_run_fix` flag (Phase D, P3)
**Source:** A6-R3 (DESCENT1 et al.).

---

## Section 3 — Metadata-driven rules (P0/P1, from A7)

### R8 — Title sanitisation pipeline (LFN-safe)
**Trigger:** every game's `<Title>` rendered into a folder name.
**Pipeline (apply in order):**
1. Unicode-NFKD-normalise, drop combining marks (e.g. `é` → `e`)
2. Character map: `:` → ` - ` (space-dash-space)
3. Drop: `?` `*` `|` `<` `>` `"` `/` `\` and all control chars 0x00-0x1F
4. Collapse multi-space to single space, strip leading/trailing whitespace
5. Cap length at 64 chars (truncate at last word boundary if possible)
6. Reserved-name guard: if result matches `CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]` or
   their `.<ext>` variants, append ` (game)`
7. Case-fold collision check across all games in pack; on collision, fall back to
   `<sanitised> (<dosname>)` (3 known collisions in v6: Enigma86/96, Escape94/99,
   jeapnse/JeopSp88)
**Source:** A7 + user-chosen mapping; 1214 games (15.8%) trigger sanitisation, mostly `:`.

### R9 — README.ANS generation (spec locked, see A8)
**Trigger:** every game in every view stub.
**Output:** 80-col × ≤25-row CP437 CRLF ANSI file containing:
- Top double-border, centred Title (cyan)
- Year + Source + Players + Mode row
- Genre row (raw eXoDOS genre — see open question below)
- Developer / Publisher rows
- Body: Notes wrapped at 76 cols, capped 18 lines with `[...] (description truncated, see manual)`
- Footer: Series (semicolon-joined, comma-rendered, truncated to 76 cols)
**Generation:** byte-deterministic (no timestamps). Reference impl: `session-state/files/mistereadmeans_proto.py`.
Production impl: `ExoDOSConverter/mistereadmeans.py` (Phase D3a).
**Fallbacks:** missing Notes → omit body; missing field → "n/a"; missing Genre →
"(unclassified)"; missing Series → omit footer.

### R10 — Genre canonicalisation (16 buckets)
**Trigger:** every game's `<Genre>` value (semicolon-list); used by optional Genre view
and as `__canonical_genre` metadata.
**Mapping:** `ExoDOSConverter/genre_mapping.py` (already implemented). 16 healthy
buckets: Puzzle, Adventure-Visual, Strategy-Management, ShootEmUp, Action-Adventure,
Platform, Misc, Simulation, RPG, Sports, Racing, BeatEmUp, Gun-FPS, Pinball, Tools,
Unknown.
**Phase D extension:** 48 compound raw genres (e.g. `Sports / Football`, `Shooter / Scrolling shoot'em up`)
need mapping. Mechanical task.
**Source:** A7 full report (`session-state/files/a7_metadata_report.txt`).

### R11 — Sound-init precedence chain
**Trigger:** game's sound configuration in stub bat (when injected; usually inherited
from per-game dosbox config which the converter does NOT modify).
**Precedence (highest to lowest):**
1. Per-game source dosbox config (eXoDOS-baked) — always wins
2. `data/mister/overrides.csv` `__sound_card` column (per-game manual override)
3. eXoDOS Playlist hint: MT-32 > Sound Canvas > GUS > others (user-confirmed default)
4. Genre default (none — fall through)
5. Hard default: SB16
**Dual-tagged games (419/7667, 5.5%):** in BOTH MT-32 and Sound Canvas playlists → default
MT-32 wins; flagged AMBIGUOUS-HARDWARE in build report.
**Source:** A7 + user decision; Architectural Decision #1.

### R12 — Joystick auto-inject restraint
**Trigger:** game's `<MaxPlayers>` ≥ 2 OR override flag.
**Policy:** Auto-inject `jchoice s` (joystick-init prompt) ONLY when:
- Source dosbox bat already includes it (preserve), OR
- `overrides.csv` `__inject_jchoice` column is set
**DO NOT auto-inject from `<MaxPlayers>` alone** — 73.6% (5643/7667) of games are
single-player and would get spurious prompts; for the 2024/7667 multi-player games,
the source dosbox bat already handles it if needed.
**Confirmation from A6:** zero of 300 sampled `1_Start.bat` invoke JCHOICE.EXE with
joystick-init args; only `@jchoice` (R2 mode). Restraint is correct.
**Source:** A7 + A6 negative finding.

### R13 — Metadata validation report (per-pack precheck)
**Trigger:** before staging starts.
**Output:** `<build>/build_report.txt` bucketed:
- **BUILD-BLOCKING:** missing `<ApplicationPath>`, missing/missing-on-disk source folder,
  duplicate `<Title>`+`<dosname>` collision → skip game, report
- **PATH-WARNING:** invalid/empty `<Title>` → fall back to `dosname`, report
- **FEATURE-WARNING:** empty `<Notes>` (no README.ANS body), missing `<Manual>`,
  unmapped `<Genre>` → omit feature, report
- **AMBIGUOUS-HARDWARE:** multiple sound-playlist memberships → resolved via R11, report
- **HARDPATH-WARNING (R14):** see below
**No invented metadata.** Where eXoDOS data is missing, deterministic fallback or
omit; never fabricate.
**Source:** A7 + Architectural Decision #1.

### R14 — Hardcoded install-path pre-flight scan
**Trigger:** before staging each game's payload.
**Action:** grep the payload's `.CFG`/`.INI`/`.CMD`/`.PIF` files for `C:\<TOKEN>\`
references where `<TOKEN>` is not in the allowlist `{GAMES, UTILS, DOS, FDOS, MYMENU, WINDOWS}`.
**Output:** emit HARDPATH-WARNING line in `build_report.txt` naming game + file + line +
matched token. Stage normally — warning informs user to test first.
**Escape hatch:** if game fails on test, user sets `__force_root_install: true` in
`overrides.csv`. Next build moves payload to `C:\<Title>\` and rewrites stubs to
`cd \<Title>` instead of `cd \GAMES\<dosname>`.
**Source:** Architectural Decision #10 (user policy from session); pattern observed in
11 root-installed games on original Top300 VHD (ALBION, COKTEL, INDY256, SCREAMER,
SIERRA, T7G, TIECD, TIM2, WC3, WINTER, THEME.CD).

---

## Section 4 — Optional / contextual patterns (P2/P3, from A3)

### R15 — `subst` floppy emulation
**Trigger:** legacy bat maps floppies via `subst a: <game>\floppy`. Frequency: 11/286 (~3.8%).
**Action:** preserve `subst` calls verbatim into stub when game requires; pair with
`subst a: /d` cleanup at stub exit. Most games don't need this with `imgtry fdd0`
mounts via R1.
**Priority:** P2.
**Source:** A3-R7 (WC2DLX, SimCity, Wasteland).

### R16 — `sysctl` cache/CPU toggle
**Trigger:** game needs L1/L2 cache disabled for compatibility (CPU-speed-sensitive
games on too-fast CPUs). Frequency: 2/286 (~0.7%).
**Input (legacy):** `sysctl sys L1- L2-`
**Output (emit):** preserve verbatim, prepended before launcher.
**Priority:** P3 — record per game in `overrides.csv` `__pre_launch_cmds` column.
**Source:** A3-R8 (2400 AD).

### R17 — Custom helper bats (`call go`, `call as`, `call brix`)
**Trigger:** game's source dosbox bat delegates to non-`run` helper. Frequency: ~15/286.
**Action:** inline the helper's effect into the stub rather than calling it (the helper
lives at `\GAMES\<dosname>\<helper>.bat` so it's reachable, but inlining keeps stub
self-contained).
**Priority:** P2.
**Source:** A3-R5 (A.G.E., Action Soccer, Brix family).

### R18 — DOS4GW / DPMI residue
**Trigger:** `REM cwsdpmi` or explicit DPMI invocation. Frequency: 3/286 (~1.0%).
**Action:** drop REM lines; preserve active `cwsdpmi` invocations.
**Priority:** P3.
**Source:** A3-R9.

### R19 — Comment / REM blocks
**Trigger:** `REM <text>` lines. Frequency: common.
**Action:** drop unless REM line encodes an alternate path/CD switch the user might need
to flip manually (preserve in those cases, prefixed with `REM (preserved from source):`).
**Priority:** P2.
**Source:** A3-R11.

### R20 — Sound-card init blocks (SBOS / MAXSBOS / MIDIDEMO / MT32 helpers)
**Trigger:** game's payload directory contains a sound-init helper bat
(`SBOS.BAT`, `MAXSBOS.BAT`, `MIDIDEMO.BAT`, etc.).
**Policy:** the converter does NOT inject sound calls into stubs — sound init comes
from per-game dosbox config (which set `SET BLASTER=…`/`SET ULTRADIR=…` in the source
launcher). The helper bats live unchanged in `\GAMES\<dosname>\` and the source
launcher (which we inline via R5) calls them if needed.
**Confirmation from A6:** no baked-in sound-init layer in any of 300 sampled launchers.
**Priority:** P0 by absence (the rule is "do not inject"). Recorded for context.
**Source:** A6 negative finding.

### R-Floppy — Floppy disk mount via imgtry fdd0/fdd1
**Trigger:** legacy `imgmount a "...img" -t floppy` (or `b` for fdd1). Frequency:
**121/7666 games (1.6%)** across full eXoDOS v6.
**Input (legacy):** `imgmount a ".\eXoDOS\<dosname>\floppy\disk1.img" -t floppy`
**Output (emit):** `CALL imgtry fdd0 A "/floppy/<dosname>/disk1.img"`
- Multi-floppy games (Pattern A disc-swap equivalent): pass multiple images on same
  fdd slot, user swaps via Ctrl-F4 equivalent
- Floppy `.img` files don't have CHD/cue/iso alternatives; just pass `.img` directly
**Priority:** P1 (deterministic mechanical rule, applies to 121 games).
**Source:** eXoDOS dosbox.conf scan (2026-06-03).

### R-Boot — Hard-disk boot image via imgtry ide00
**Trigger:** legacy `boot c.img` or `imgmount c c.img -t hdd` then `boot`. Frequency:
**16/7666 games (0.2%)** plus 2 with hdd imgmount (no boot).
**Input (legacy):** `imgmount c ".\boot.img" -t hdd` + `boot c`
**Output (emit):** `CALL imgtry ide00 C "/bootdisk/<dosname>/boot.img"` — AO486 boots from
the imgtry'd HDD image directly.
**Priority:** P3 — rare enough that per-game testing is appropriate. Most "boot"
games on eXoDOS are Windows 3.1/95 titles that fall outside the MiSTer AO486 scope
anyway.
**Source:** eXoDOS dosbox.conf scan (2026-06-03).

---

## Section 5 — Existing hardcoded MiSTer flow (P0/P1, to retire)

These are the pre-existing per-game hardcoded artifacts in the current Python codebase
that Phase D replaces with metadata-driven rules + `overrides.csv`.

### R21 — `mister.removeUnusedCds` dict (mister.py:13-32)
**Current:** hardcoded dict of `{game_dosname: [cd_filename_to_remove, …]}` for games
whose source dosbox config references CDs that don't actually exist in the eXoDOS payload.
**Replacement (Phase D):** validate at staging time — if a CD referenced in the source
config doesn't exist on disk, log a CDMISSING-WARNING and skip the mount line; record
per-game exception in `overrides.csv` only when the auto-detection misses.
**Source:** existing code; A1 inventory.

### R22 — `mister.handleRunBat` dict (mister.py:80-90) + `lists.gamesWithRunBatHandling`
**Current:** hardcoded `{game_dosname: handler}` for games with nested `run.bat`
calling other bats that need rewriting in addition to the top-level one.
**Replacement (Phase D):** recursive bat-rewrite — when inlining R5, follow `call <bat>`
chains within the payload and rewrite each level. No game list needed; the rewriter
just descends. Cap recursion at depth 3 to avoid loops.
**Source:** existing code; A1 inventory.

### R23 — `commandhandler.py:94` Carmaged special-case
**Current:** `if game == "Carmaged": skip subpath stripping`.
**Replacement (Phase D):** add `__preserve_subpath: true` flag to `overrides.csv` for
Carmaged (and any other game found needing it). One row in CSV, zero special-case code.
**Source:** existing code; A1 inventory.

### R24 — `gamegenerator.py:126` SWTieCD special-case + `needsFirstGame` dependency map
**Current:** `__specificFixes` stub with SWTieCD logic; `__copyGameFiles__` has hardcoded
`needsFirstGame` map for games that depend on another game's files being present.
**Replacement (Phase D):** declare cross-game dependencies in `overrides.csv` via
`__depends_on_game` column (semicolon list of dosnames). Staging copies dependencies
first. Removes the hardcoded map.
**Source:** existing code; A1 inventory.

---

## Section 6 — OS-portability rules (P0, from A2)

Phase B (portability) cleans the existing Linux-coupled code. These are NOT bat-generation
rules — they're code-portability rules for the converter itself.

### R25 — Path separator centralisation
**Rule:** every host-side path goes through `util.normalizeHostPath` / `util.localOSPath`
(already exist). DOS-side paths (written into bats) go through a single new helper
`util.toDosPath(s)` that returns `s.replace('/', '\\')` and validates against LFN limits.
**Affected sites:** `mister.py:188-190, 200, 225-227, 246, 266-267`; `commandhandler.py:69-79, 200`;
`gamegenerator.py:60-61`; `metadatahandler.py:70-80`.

### R26 — VHD builder abstraction
**Rule:** retire direct Linux-only tool calls (`mtools`/`sfdisk`/`fatresize`/`qemu-img`)
from `ao486vhd.py`. Replace `Ao486VhdBuilder` with `DosForgeVhdBuilder` (Phase C) that
shells out to `dosforge` CLI for VHD create + format + populate + DOS install.
**Affected sites:** `ao486vhd.py:25, 300-304, 331-333, 349-350, 357-367, 414-423, 437-439, 471-479, 485-499, 520`.

### R27 — Hardcoded user paths removed
**Rule:** no `/home/shawn/`, `/mnt/`, `~/` literals anywhere. All paths via env var
`EXODOS_BUILD_ROOT` (default `<output_dir>/_build`) or CLI argument.
**Affected sites:** `ao486vhd.py:300-304, 331-333`.

### R28 — Platform branches consolidated
**Rule:** all `platform.system()` / `sys.platform` branches in one helper module
`util.platform`. GUI-only branches (`exogui.py:43-44` iconbitmap) stay where they are.
**Affected sites:** `util.py:155-160, 193-199, 288-291, 345-360`; `commandhandler.py:173-175`;
`metadatahandler.py:139-144`.

### R29 — CRLF + CP437 enforcement
**Rule:** every generated DOS artefact (`.BAT`, `.INI`, `.SYS`, `.CFG`, `.ANS`) uses
`open(path, 'w', encoding='cp437', errors='replace', newline='\r\n')`. New helper
`util.openDosFile(path, mode)` centralises this.
**Already correct:** `mister.py:37, 77, 281, 339` use `newline='\r\n'`. `ao486vhd.py:211-236`
doesn't always — fix in Phase B.

### R30 — Case-folded game-list lookups
**Rule:** any lookup against a hardcoded game-name list uses lowercased compare. After
Phase D removes most lists, only the few remaining (override CSV keys) follow this rule.
**Affected sites:** `mister.py:57-59` (`gamesWithRunBatHandling` lookup).

---

## Section 7 — Escape hatches (`data/mister/overrides.csv`)

When automation can't decide or a game needs something unusual, the user adds a row
to `data/mister/overrides.csv`. CSV schema:

| column | type | purpose |
|---|---|---|
| `dosname` | str (key) | eXoDOS internal id, lowercase |
| `__sound_card` | str | force sound card: `mt32`/`sc`/`gus`/`sb16`/`pcjr`/`cga`. Used by R11. |
| `__inject_jchoice` | bool | force `jchoice s` joystick init. Used by R12. |
| `__force_root_install` | bool | stage to `C:\<Title>\` instead of `C:\GAMES\<dosname>\`. Used by R14. |
| `__depends_on_game` | str (semi-list) | dosnames of other games whose files this needs. Used by R24. |
| `__preserve_subpath` | bool | skip CommandHandler subpath stripping. Used by R23. |
| `__pre_launch_cmds` | str (pipe-list) | commands to inject before launcher (e.g. `sysctl sys L1- L2-`). Used by R16. |
| `__first_run_fix` | str | path to a one-shot fix bat shipped with the converter. Used by R7. |
| `__custom_view` | str (semi-list) | force inclusion in named optional views regardless of metadata. |
| `__exclude_view` | str (semi-list) | force exclusion from named views. |
| `__multi_drive_cd_swap` | bool | enable helper bat for multi-drive expansion CDs (Pattern B per R1b). For 10-20 games like Links LS 1997 that use 3+ drive letters for CDs. |
| `__notes` | str | freeform; ignored by code, useful for the user. |

**Target size:** the CSV should grow over time but stay small (<200 rows expected for
full eXoDOS v6) — most games convert with zero overrides.

---

## Section 8 — Open questions for Checkpoint A

- **Q1:** README.ANS Genre row — show raw eXoDOS genre (informative, matches source) or
  canonical R10 bucket (matches optional Genre view folder)? Current sample
  (`samples/readmeans/03_unicode_BattInse.ans`) shows raw `Action; Shooter / Scrolling shoot'em up`.
  Recommendation: show raw; the canonical bucket is implicit from view-folder path.
- **Q2:** Should HARDPATH-WARNING break the build by default or warn-and-continue?
  Recommendation: warn-and-continue; the user policy explicitly says "log and find them
  in game testing".
- **Q3:** R22 recursive bat-rewrite depth cap of 3 — does any game in the user's
  experience need deeper than 3 levels? If yes, raise cap or convert to explicit override.

---

## Appendix — Source citations summary

- A1 (existing MiSTer flow inventory): `exoconverter.py:41-125`, `gamegenerator.py:67-320`,
  `mister.py:13-277`, `commandhandler.py:69-200`, `mymenupacker.py:6-45`, `ao486vhd.py:34-520`.
- A2 (OS-couplings catalog): 35 sites in `ao486vhd.py`, `mister.py`, `commandhandler.py`,
  `util.py`, `metadatahandler.py`, `gamegenerator.py`, `exogui.py`.
- A3 (autorun pattern mining): `session-state/files/autorun_dump.txt` (2180 lines,
  286 games).
- A5+A6 (VHD mining): `session-state/files/a5_a6_vhd_mining_report.md`.
- A7 (metadata + genre): `session-state/files/a7_metadata_report.txt` (7667 games,
  16 buckets, 48 unmapped, 419 dual-tagged, 1214 sanitisation triggers).
- A8 (README.ANS spec): `session-state/files/mistereadmeans_proto.py` + 4 samples in
  `samples/readmeans/`.
- A9 (MyMenu layout): inspected `DOS_Shareware_MyMenu` reference repo + user-corrected
  stub-indirection architecture (this session, Rev 5 plan).
