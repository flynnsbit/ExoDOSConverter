"""README.ANS generator for MiSTer / MyMenu (Phase D3a / A8 freeze).

Renders an 80-column CP437 ANSI document from eXoDOS metadata for
MyMenu's ``ReadMe=README.ANS`` preview (DOINFOPOPUP).

Layout (two stacked boxes):

* **Double-line box** around title + Year/Source/Players/Mode + Genre +
  Developer + Publisher (closed ╔╗ / ╚╝ frame; ╠═╣ under the title).
* **Single-line box** around the Notes body (and optional Series footer).
  Internal section separators use ├ + 78×─ + ┤ so the rule sits *inside*
  the single box rather than a full-width 80-column bar.

MS-DOS ANSI graphics line discipline (see ``_join_msdos_ansi_lines``):
80-column rows rely on DECAWM auto-wrap — no CR/LF after a full row —
so MyMenu does not paint a blank line between every row. Shorter rows
use CRLF. CP437, trailing reset; no BOM.

Pure stdlib — no new packages.
"""

from __future__ import annotations

import os
import re
import textwrap
import unicodedata


# --- CP437 box-drawing (double) ----------------------------------------------
_D_TL = "\u2554"  # ╔
_D_TR = "\u2557"  # ╗
_D_BL = "\u255a"  # ╚
_D_BR = "\u255d"  # ╝
_D_H = "\u2550"   # ═
_D_V = "\u2551"   # ║
_D_ML = "\u2560"  # ╠
_D_MR = "\u2563"  # ╣

# --- CP437 box-drawing (single) ----------------------------------------------
_S_TL = "\u250c"  # ┌
_S_TR = "\u2510"  # ┐
_S_BL = "\u2514"  # └
_S_BR = "\u2518"  # ┘
_S_H = "\u2500"   # ─
_S_V = "\u2502"   # │
_S_ML = "\u251c"  # ├
_S_MR = "\u2524"  # ┤

# ANSI SGR fragments (no ESC prefix)
_ESC = "\x1b["
_RESET = _ESC + "0m"
_BORDER = _ESC + "1;37;40m"   # bright white on black
_TITLE = _ESC + "1;36;40m"    # bright cyan
_LABEL = _ESC + "1;33;40m"    # bright yellow
_VALUE = _ESC + "0;37;40m"    # white
_BODY = _ESC + "0;37;40m"

# CSI sequences that do not consume a text-mode cell (SGR, DEC private modes, etc.)
_ANSI_CSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

_COLS = 80
_INNER = 78          # between the two vertical bars
_TEXT_WIDTH = 76     # body / field value wrap width
_MAX_BODY_LINES = 18
_TRUNC_MARKER = "[...] (description truncated, see manual)"

# Unicode → ASCII replacements applied before CP437 encode.
_UNICODE_MAP = {
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"',
    "\u2013": "-", "\u2014": "-", "\u2212": "-",
    "\u2026": "...",
    "\u00a0": " ",
    "\u00b7": "*", "\u2022": "*",
    "\u2122": "(TM)", "\u00ae": "(R)", "\u00a9": "(C)",
}


def _strip_controls(text: str) -> str:
    """Drop ASCII controls except TAB/LF/CR. Never allow ESC from metadata."""
    out = []
    for ch in text:
        o = ord(ch)
        if o in (0x09, 0x0A, 0x0D):
            out.append(ch)
        elif o < 0x20 or o == 0x7F:
            continue
        else:
            out.append(ch)
    return "".join(out)


def _transliterate(text: str) -> str:
    chars = []
    for ch in text:
        if ch in _UNICODE_MAP:
            chars.append(_UNICODE_MAP[ch])
            continue
        # Common accented Latin → ASCII base
        decomp = unicodedata.normalize("NFKD", ch)
        base = "".join(c for c in decomp if not unicodedata.combining(c))
        if base and all(ord(c) < 128 for c in base):
            chars.append(base)
        else:
            chars.append(ch)
    return "".join(chars)


def sanitise_text(text: str | None) -> str:
    """Full A8 sanitisation pipeline steps 1–3 (no wrap/encode yet)."""
    if not text:
        return ""
    s = _strip_controls(str(text))
    s = _transliterate(s)
    # Collapse horizontal whitespace runs; keep blank-line paragraphs.
    paragraphs = re.split(r"\r?\n\s*\r?\n", s)
    cleaned = []
    for para in paragraphs:
        line = re.sub(r"[ \t]+", " ", para.replace("\r", "").replace("\n", " ")).strip()
        cleaned.append(line)
    # Re-join paragraphs with a blank line between non-empty ones
    parts = []
    for para in cleaned:
        if para:
            parts.append(para)
        else:
            parts.append("")
    # Drop leading/trailing empty paras
    while parts and parts[0] == "":
        parts.pop(0)
    while parts and parts[-1] == "":
        parts.pop()
    return "\n\n".join(parts)


def _pad(text: str, width: int) -> str:
    if len(text) > width:
        return text[:width]
    return text + (" " * (width - len(text)))


def _centre(text: str, width: int) -> str:
    if len(text) > width:
        text = text[:width]
    pad = width - len(text)
    left = pad // 2
    right = pad - left
    return (" " * left) + text + (" " * right)


def _visual_width(text: str) -> int:
    """Count text-mode cells (CP437 glyphs), ignoring CSI / ESC sequences."""
    return len(_ANSI_CSI_RE.sub("", text))


def _join_msdos_ansi_lines(lines: list[str]) -> str:
    """Join rows the way classic MS-DOS .ANS art expects.

    On an 80-column DOS console (ANSI.SYS / MyMenu), writing the 80th glyph
    auto-wraps the cursor to the next row (DECAWM). Emitting CR and/or LF
    *after* a full-width row advances a second time, which paints a blank
    line between every row — the double-spacing MyMenu showed for our
    earlier LF-only and CRLF outputs.

    Rules:
    * visual width == 80 → no terminator (auto-wrap *is* the line advance)
    * visual width < 80  → CRLF (DOS text standard)
    * visual width > 80  → CRLF (should not happen for our layout; safe fallback)
    """
    parts: list[str] = []
    for line in lines:
        parts.append(line)
        width = _visual_width(line)
        if width != _COLS:
            parts.append("\r\n")
    return "".join(parts)


def _vbar(double: bool) -> str:
    return _D_V if double else _S_V


def _field_row_simple(label: str, value: str, *, double: bool = True) -> str:
    """Build an info row with yellow label and white value, 80 cols total."""
    value = "n/a" if value in (None, "") else str(value)
    v = _vbar(double)
    # After left bar: space + label + value, pad to INNER, right bar.
    label_part = label + ": "
    max_val = _INNER - 1 - len(label_part)  # -1 for the leading space
    if max_val < 0:
        max_val = 0
    val = value if len(value) <= max_val else value[:max_val]
    pad_len = _INNER - 1 - len(label_part) - len(val)
    if pad_len < 0:
        pad_len = 0
    return (
        f"{_BORDER}{v} {_LABEL}{label_part}{_VALUE}{val}{' ' * pad_len}{_BORDER}{v}{_RESET}"
    )


def _combo_info_row(year, source, players, mode, *, double: bool = True) -> str:
    """Year / Source / Players / Mode on one row."""
    year = year or "n/a"
    source = source or "n/a"
    players = players if players not in (None, "") else "n/a"
    mode = mode if mode not in (None, "") else "n/a"
    v = _vbar(double)
    # Sample: " Year: 1995  Source: Commercial  Players: 1  Mode: Single Player"
    parts = [
        ("Year: ", str(year)),
        ("Source: ", str(source)),
        ("Players: ", str(players)),
        ("Mode: ", str(mode)),
    ]
    segs = []
    for i, (lab, val) in enumerate(parts):
        if i:
            segs.append(_VALUE + "  ")
        segs.append(_LABEL + lab + _VALUE + val)
    plain_len = sum(len(lab) + len(val) for lab, val in parts) + 2 * (len(parts) - 1)
    pad = _INNER - 1 - plain_len
    if pad < 0:
        overflow = -pad
        lab, val = parts[-1]
        parts[-1] = (lab, val[: max(0, len(val) - overflow)])
        segs = []
        for i, (lab, val) in enumerate(parts):
            if i:
                segs.append(_VALUE + "  ")
            segs.append(_LABEL + lab + _VALUE + val)
        plain_len = sum(len(lab) + len(val) for lab, val in parts) + 2 * (len(parts) - 1)
        pad = max(0, _INNER - 1 - plain_len)
    return f"{_BORDER}{v} " + "".join(segs) + (" " * pad) + f"{_BORDER}{v}{_RESET}"


def _title_row(title: str, *, double: bool = True) -> str:
    title = sanitise_text(title) or "Unknown"
    if len(title) > _TEXT_WIDTH:
        title = title[:_TEXT_WIDTH]
    v = _vbar(double)
    pad = _INNER - len(title)
    left = pad // 2
    right = pad - left
    return (
        f"{_BORDER}{v}{' ' * left}{_TITLE}{title}{_BORDER}{' ' * right}{v}{_RESET}"
    )


def _top_border(*, double: bool = True) -> str:
    if double:
        return f"{_BORDER}{_D_TL}{_D_H * _INNER}{_D_TR}{_RESET}"
    return f"{_BORDER}{_S_TL}{_S_H * _INNER}{_S_TR}{_RESET}"


def _bottom_border(*, double: bool = True) -> str:
    if double:
        return f"{_BORDER}{_D_BL}{_D_H * _INNER}{_D_BR}{_RESET}"
    return f"{_BORDER}{_S_BL}{_S_H * _INNER}{_S_BR}{_RESET}"


def _mid_border(*, double: bool = True) -> str:
    """T-junction mid rule that stays inside the box (78 horizontal cells)."""
    if double:
        return f"{_BORDER}{_D_ML}{_D_H * _INNER}{_D_MR}{_RESET}"
    return f"{_BORDER}{_S_ML}{_S_H * _INNER}{_S_MR}{_RESET}"


def _body_row(text: str, *, double: bool = False) -> str:
    """Content row; single-line sides by default (notes / series box)."""
    text = text if text is not None else ""
    if len(text) > _TEXT_WIDTH:
        text = text[:_TEXT_WIDTH]
    v = _vbar(double)
    interior_text = _pad(" " + text, _INNER)
    return f"{_BORDER}{v}{_BODY}{interior_text[0]}{interior_text[1:]}{_BORDER}{v}{_RESET}"


def _wrap_notes(notes: str) -> list[str]:
    notes = sanitise_text(notes)
    if not notes:
        return []
    lines = []
    paragraphs = notes.split("\n\n")
    for idx, para in enumerate(paragraphs):
        if para == "":
            lines.append("")
            continue
        wrapped = textwrap.wrap(
            para,
            width=_TEXT_WIDTH,
            replace_whitespace=True,
            drop_whitespace=True,
        )
        if not wrapped:
            lines.append("")
        else:
            lines.extend(wrapped)
        # Preserve blank-line paragraph separators from the Notes field.
        if idx < len(paragraphs) - 1:
            lines.append("")
    return lines


def _body_lines(notes: str) -> tuple[list[str], list[str]]:
    """Return (body_lines, warnings)."""
    warnings = []
    wrapped = _wrap_notes(notes)
    if not wrapped:
        return [], warnings
    if len(wrapped) > _MAX_BODY_LINES:
        warnings.append("body truncated to 18 lines")
        # 17 content lines + truncation marker
        kept = wrapped[: _MAX_BODY_LINES - 1]
        kept.append(_TRUNC_MARKER)
        return kept, warnings
    return wrapped, warnings


def render_readme_ans(
    *,
    title: str,
    year: str | None = None,
    genres=None,
    developer: str | None = None,
    publisher: str | None = None,
    notes: str | None = None,
    source: str | None = None,
    max_players: str | None = None,
    play_mode: str | None = None,
    series: str | None = None,
) -> tuple[bytes, list[str]]:
    """Render README.ANS bytes and a list of warning strings.

    Returns ``(cp437_msdos_ansi_bytes, warnings)``.
    """
    warnings: list[str] = []
    genres = genres or []
    if isinstance(genres, str):
        genre_str = genres
    else:
        genre_str = "; ".join(g.strip() for g in genres if g and str(g).strip())
    if not genre_str:
        genre_str = "(unclassified)"

    lines = []
    # Clear screen + home. Enable DECAWM (ESC[?7h) so the 80th column
    # auto-wraps — required for full-width MS-DOS .ANS line discipline.
    # MyMenu stock GAMEANSI files use ?7h the same way.
    prefix = f"{_ESC}?7h{_ESC}40m{_ESC}2J{_ESC}H"

    # --- Double-line box: title + metadata ------------------------------------
    lines.append(_top_border(double=True))
    lines.append(_title_row(title or "Unknown", double=True))
    lines.append(_mid_border(double=True))  # ╠════╣ under title, inside double box
    lines.append(
        _combo_info_row(
            sanitise_text(year) if year else None,
            sanitise_text(source) if source else None,
            sanitise_text(str(max_players)) if max_players not in (None, "") else None,
            sanitise_text(play_mode) if play_mode else None,
            double=True,
        )
    )
    lines.append(_field_row_simple("Genre", sanitise_text(genre_str), double=True))
    lines.append(
        _field_row_simple(
            "Developer",
            sanitise_text(developer) if developer else "n/a",
            double=True,
        )
    )
    lines.append(
        _field_row_simple(
            "Publisher",
            sanitise_text(publisher) if publisher else "n/a",
            double=True,
        )
    )
    lines.append(_bottom_border(double=True))

    # --- Single-line box: notes body + optional series ------------------------
    body, body_warns = _body_lines(notes or "")
    warnings.extend(body_warns)
    series_text = sanitise_text(series) if series else ""
    if series_text:
        label = "Series: "
        max_val = _TEXT_WIDTH - len(label)
        if len(series_text) > max_val:
            series_text = series_text[: max(0, max_val - 4)] + " ..."
        series_line = label + series_text
    else:
        series_line = ""

    if body or series_line:
        lines.append(_top_border(double=False))
        if body:
            for bl in body:
                lines.append(_body_row(bl, double=False))
        if body and series_line:
            # Inner section rule: 78 ─ between ├ ┤ (inside the single box)
            lines.append(_mid_border(double=False))
        if series_line:
            lines.append(_body_row(series_line, double=False))
        lines.append(_bottom_border(double=False))

    # Sanity: every layout row should be exactly 80 cells (box edges).
    for idx, row in enumerate(lines):
        vw = _visual_width(row)
        if vw != _COLS:
            warnings.append("row %i visual width %i (expected %i)" % (idx, vw, _COLS))

    # Clear/home prefix has zero visual width — glue onto first row so the
    # 80-cell border still triggers a single auto-wrap, not wrap+newline.
    lines[0] = prefix + lines[0]

    raw = _join_msdos_ansi_lines(lines)
    encoded = raw.encode("cp437", errors="replace")
    return encoded, warnings


def render_from_dosgame(metadata, *, source=None, max_players=None, play_mode=None, series=None):
    """Convenience wrapper around a ``DosGame`` namedtuple / duck type.

    Explicit kwargs override fields present on ``metadata`` (used by tests).
    """
    return render_readme_ans(
        title=getattr(metadata, "name", None) or getattr(metadata, "dosname", "Unknown"),
        year=getattr(metadata, "year", None),
        genres=getattr(metadata, "genres", None) or [],
        developer=getattr(metadata, "developer", None),
        publisher=getattr(metadata, "publisher", None),
        notes=getattr(metadata, "desc", None) or "",
        source=source if source is not None else getattr(metadata, "source", None),
        max_players=(
            max_players if max_players is not None
            else getattr(metadata, "maxplayers", None)
        ),
        play_mode=(
            play_mode if play_mode is not None
            else getattr(metadata, "playmode", None)
        ),
        series=series if series is not None else getattr(metadata, "series", None),
    )


def write_readme_ans(game_dir: str, metadata, logger=None, **kwargs) -> bool:
    """Write ``README.ANS`` into ``game_dir``. Returns True on success.

    Skips (returns False) only on hard failure. Empty Notes still writes a
    header-only card (matches A8 empty-Notes sample).
    """
    try:
        data, warnings = render_from_dosgame(metadata, **kwargs)
        out_path = os.path.join(game_dir, "README.ANS")
        with open(out_path, "wb") as fh:
            fh.write(data)
        if logger is not None:
            for w in warnings:
                logger.log("    README.ANS: %s" % w, getattr(logger, "WARNING", None))
            logger.log("    Wrote README.ANS (%i bytes)" % len(data))
        return True
    except Exception as exc:
        if logger is not None:
            logger.log(
                "    <WARNING> README.ANS generation failed: %s" % exc,
                getattr(logger, "WARNING", None),
            )
        return False
