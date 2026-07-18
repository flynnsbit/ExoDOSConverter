"""
Phase D5 rules engine for MiSTer-target bat rewriting.

Each rule is a pure function: line(s) -> rewritten line(s).
Rules are composed via apply_rules_to_lines() / apply_rules_to_file().

Current rules:
    R1  imgset -> CALL imgtry with CHD-fallback chain
        (drops dummy "/cd/<game>/d" unmount lines that become redundant)
    R2  pause -> @jchoice (joystick-friendly any-key prompt)

Per-game edge cases live in data/mister/overrides.csv (see misteroverrides.py),
not in this module.

Future rules (per plan.md):
    R4  @echo off prologue (already converter default)
    R5  multi-choice sound config picker (jchoice /C:...) -- from F4 v2 surfaced

Rules are MiSTer-only. Called from mister.batsAndMounts() after the
launch bat is generated. Other targets (Batocera, Retropie, etc.) are
not affected.

Rule format examples (from Top300 ground truth):
    Input:   imgset ide10 "/cd/7thguest/t7g1.cue"
    Output:  CALL imgtry ide10 D "/cd/7thguest/t7g1.chd" "/cd/7thguest/t7g1.cue"

    Input:   imgset fdd0 "/floppy/Populous/populo1.ima"
    Output:  CALL imgtry fdd0 A "/floppy/Populous/populo1.chd" "/floppy/Populous/populo1.ima"

    Input:   imgset ide10 "/cd/7thguest/d"   (dummy directory-unmount)
    Output:  (line dropped; imgtry handles unmount/mount atomically)
"""

import os
import re


# Device slot -> default DOS drive letter (matches Top300 convention)
# See: baseline/ground-truth/top300_updates/games/*/1_Start.bat samples
DEVICE_DRIVE_LETTER = {
    'ide10': 'D',   # CD primary
    'ide11': 'D',   # CD secondary (per plan; no samples in Top300 to confirm
                    # but plan.md R1 says same as ide10)
    'fdd0':  'A',   # floppy A
    'fdd1':  'B',   # floppy B
    'ide00': 'C',   # bootdisk primary master
    'ide01': 'D',   # bootdisk primary slave (rare; placeholder)
}

# Regex for imgset lines. Captures device, path. Optional leading whitespace.
IMGSET_RE = re.compile(r'^\s*imgset\s+(?P<device>\S+)\s+"(?P<path>[^"]+)"\s*$',
                        re.IGNORECASE)


def _derive_chd_path(orig_path):
    """Derive the CHD path for an original media file path.

    Top300 convention (verified against ground-truth samples):
        /cd/X/t7g1.cue      -> /cd/X/t7g1.chd            (single-dot stem)
        /cd/X/wake_1.0.cue  -> /cd/X/wake_1.chd          (strips .0 version suffix)
        /cd/X/moo2v1.0.cue  -> /cd/X/moo2v1.chd          (strips .0 version suffix)
        /cd/X/albion.cue    -> /cd/X/albion.chd
        /cd/X/disk1.ima     -> /cd/X/disk1.chd           (floppy)

    Rule: take stem (basename without extension); strip trailing .<digits>
    version segments; append .chd. Preserves forward-slash paths.
    """
    # Use forward-slash split to preserve posix-style paths (matches converter output)
    if '/' in orig_path:
        dirname, basename = orig_path.rsplit('/', 1)
        dirname += '/'
    else:
        dirname = ''
        basename = orig_path

    stem, _ = os.path.splitext(basename)
    # Strip trailing .<digit-only> segments (e.g., ".0", ".1.0")
    while re.search(r'\.\d+$', stem):
        stem = re.sub(r'\.\d+$', '', stem)
    return dirname + stem + '.chd'


def apply_r1(line, target='mister'):
    """R1: imgset → hardware-specific CD/media mount.

    * **mister** (default): ``CALL imgtry …`` with CHD fallback (Top300).
    * **picogus / picoide**: REM lines + ``CALL …\\PGUSCD.BAT list`` (USB root images).
    * **picomem**: REM stub (BIOS disk / future CD).

    Returns str, list[str], None (drop), or original line.
    Drops dummy "/cd/<game>/d" bare-dir unmount lines for all targets.
    """
    m = IMGSET_RE.match(line)
    if not m:
        return line

    device = m.group('device').lower()
    path = m.group('path')

    if device not in DEVICE_DRIVE_LETTER:
        return line

    _, ext = os.path.splitext(path)

    # Dummy "/cd/<game>/d" or similar directory-unmount lines
    media_exts = {'.cue', '.iso', '.img', '.ima', '.bin', '.chd', '.vhd'}
    if ext.lower() not in media_exts:
        return None

    target = (target or 'mister').strip().lower()
    basename = path.replace('\\', '/').rsplit('/', 1)[-1]

    if target in ('picogus', 'picoide'):
        # User copies pack cd/ files to USB root; index via pgusinit /cdlist
        return [
            'REM native %s: copy %s to FAT32 USB root' % (target, basename),
            'REM then: CALL C:\\DRIVERS\\HW\\PGUSCD.BAT load n',
            'CALL C:\\DRIVERS\\HW\\PGUSCD.BAT list',
        ]

    if target == 'picomem':
        return [
            'REM picomem: media "%s"' % path,
            'REM attach VHD/IMG via PicoMEM BIOS; CD: CALL C:\\DRIVERS\\HW\\PMCD.BAT help',
            'CALL C:\\DRIVERS\\HW\\PMCD.BAT help',
        ]

    # mister (default)
    drive = DEVICE_DRIVE_LETTER[device]
    chd_path = _derive_chd_path(path)

    if ext.lower() == '.chd':
        return 'CALL imgtry {device} {drive} "{path}"'.format(
            device=device, drive=drive, path=path)

    return 'CALL imgtry {device} {drive} "{chd}" "{orig}"'.format(
        device=device, drive=drive, chd=chd_path, orig=path)


def apply_r2(line):
    """R2: pause -> @jchoice (joystick-friendly any-key prompt).

    Per plan.md A6 finding: this is the ONLY difference in 3_Setup.bat for 300/300
    Top 300 games (universal substitution). Also applies wherever the launcher
    emits a bare `pause`. Case-insensitive match; preserves leading whitespace.
    Per Top300 convention: emits "@jchoice" prefixed with @ to suppress echo.

    Verified against Top300 ground-truth samples: every bare `pause` becomes `@jchoice`.
    """
    stripped = line.strip()
    if stripped.lower() == 'pause':
        # Preserve leading whitespace if any
        leading = line[:len(line) - len(line.lstrip())]
        return leading + '@jchoice'
    return line


# Ordered pipeline of (rule_name, rule_function) pairs.
# R1 is special-cased with target=; R2 is target-agnostic.
RULES = [
    ('R1', apply_r1),
    ('R2', apply_r2),
]


def apply_rules_to_line(line, target='mister'):
    """Run the rule pipeline on one line.

    Returns str, list[str], or None (drop).
    """
    current = line
    for name, rule in RULES:
        if current is None:
            return None
        if isinstance(current, list):
            # Already expanded by a prior rule — apply R2 per line only
            if name == 'R2':
                current = [rule(x) if isinstance(x, str) else x for x in current]
            continue
        if name == 'R1':
            current = rule(current, target=target)
        else:
            current = rule(current)
    return current


def apply_rules_to_lines(lines, target='mister'):
    """Run the rule pipeline across a list of input lines.

    Returns list of output lines, with dropped lines (None results) filtered.
    Rules may expand one line into several (list return).
    """
    out = []
    for line in lines:
        bare = line.rstrip('\r\n').rstrip()
        result = apply_rules_to_line(bare, target=target)
        if result is None:
            continue
        if isinstance(result, list):
            for item in result:
                if item is None:
                    continue
                out.append(item)
        else:
            out.append(result)
    return out


def apply_rules_to_file(filepath, encoding='latin-1', target='mister'):
    """Read filepath, apply rules to every line, write back with CRLF.

    Encoding defaults to latin-1 (round-trips any byte sequence losslessly).
    ``target`` selects media rewrite style (mister|picomem|picogus|picoide).

    Returns (lines_read, lines_written, dropped_count) tuple for logging.
    """
    if not os.path.isfile(filepath):
        return (0, 0, 0)

    with open(filepath, 'r', encoding=encoding) as f:
        input_lines = f.readlines()

    output_lines = apply_rules_to_lines(input_lines, target=target)
    # Dropped is approximate when rules expand lines
    dropped = max(0, len(input_lines) - len(output_lines))

    with open(filepath, 'w', encoding=encoding, newline='\r\n') as f:
        for line in output_lines:
            f.write(line + '\n')

    return (len(input_lines), len(output_lines), dropped)
