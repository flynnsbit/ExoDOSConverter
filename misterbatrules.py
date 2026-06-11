"""
Phase D5 rules engine for MiSTer-target bat rewriting.

Each rule is a pure function: line(s) -> rewritten line(s).
Rules are composed via apply_rules_to_lines() / apply_rules_to_file().

Current rules:
    R1  imgset -> CALL imgtry with CHD-fallback chain
        (drops dummy "/cd/<game>/d" unmount lines that become redundant)

Future rules (per plan.md):
    R2  pause -> @jchoice (Phase D + overrides.csv)
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


def apply_r1(line):
    """R1: imgset device "<path>" -> CALL imgtry device <letter> "<chd>" "<original>".

    Drops dummy "/cd/<game>/d" (or similar bare-dir) unmount lines.
    Returns either:
      - str: rewritten line (no trailing newline)
      - None: indicates the line should be DROPPED entirely
      - original line unchanged if not an imgset line

    Per plan.md R1: source-priority chain .chd > .cue > .iso > .img.
    The CHD path is derived via _derive_chd_path() which mirrors Top300's
    multi-dot-stripping convention. The fallback is the original path verbatim.

    Verified against Top300 ground-truth samples in baseline/ground-truth/top300_updates/.
    """
    m = IMGSET_RE.match(line)
    if not m:
        return line

    device = m.group('device').lower()
    path = m.group('path')

    if device not in DEVICE_DRIVE_LETTER:
        return line

    _, ext = os.path.splitext(path)

    # Dummy "/cd/<game>/d" or similar directory-unmount lines: the path basename
    # has no recognized media extension. These were used to flush the CD slot
    # before mounting; imgtry handles flush atomically so they're redundant.
    media_exts = {'.cue', '.iso', '.img', '.ima', '.bin', '.chd', '.vhd'}
    if ext.lower() not in media_exts:
        return None

    drive = DEVICE_DRIVE_LETTER[device]
    chd_path = _derive_chd_path(path)

    # If original is already .chd, no fallback needed -- just a single-path imgtry call
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
# Each rule takes a single line and returns: str (rewritten), None (drop), or
# the original line unchanged.
RULES = [
    ('R1', apply_r1),
    ('R2', apply_r2),
]


def apply_rules_to_line(line):
    """Run the rule pipeline on one line. Returns rewritten line or None."""
    current = line
    for _, rule in RULES:
        if current is None:
            return None
        current = rule(current)
    return current


def apply_rules_to_lines(lines):
    """Run the rule pipeline across a list of input lines.

    Returns list of output lines, with dropped lines (None results) filtered.
    Input lines may or may not have trailing newlines; output strings are
    bare (no newlines) so the caller chooses the line ending.
    """
    out = []
    for line in lines:
        # Strip trailing newline / whitespace for rule processing
        bare = line.rstrip('\r\n').rstrip()
        result = apply_rules_to_line(bare)
        if result is None:
            continue
        out.append(result)
    return out


def apply_rules_to_file(filepath, encoding='latin-1'):
    """Read filepath, apply rules to every line, write back with CRLF.

    Encoding defaults to latin-1 (round-trips any byte sequence losslessly).
    The converter writes generated bats without explicit encoding (Python's
    platform default), so latin-1 read + latin-1 write is the safest pairing
    that won't corrupt non-ASCII bytes.

    Returns (lines_read, lines_written, dropped_count) tuple for logging.
    """
    if not os.path.isfile(filepath):
        return (0, 0, 0)

    with open(filepath, 'r', encoding=encoding) as f:
        input_lines = f.readlines()

    output_lines = apply_rules_to_lines(input_lines)
    dropped = len(input_lines) - len(output_lines)

    with open(filepath, 'w', encoding=encoding, newline='\r\n') as f:
        for line in output_lines:
            f.write(line + '\n')

    return (len(input_lines), len(output_lines), dropped)
