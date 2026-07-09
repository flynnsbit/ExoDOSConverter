"""README.ANS generator for MiSTer / MyMenu (Phase D3a / A8 freeze).

Renders an 80-column CP437 ANSI document from eXoDOS metadata for
MyMenu's ``ReadMe=README.ANS`` preview (DOINFOPOPUP).

Layout matches the frozen samples in
``exodos-toolkit/samples/readmeans/``:

* Double-line outer box (CP437)
* Title row (bright cyan, centred)
* Info block: Year/Source/Players/Mode, Genre, Developer, Publisher
* Notes body (wrap 76, max 18 lines; truncate with marker)
* Series footer (optional)
* LF-only newlines (not CRLF — MyMenu double-spaces CRLF), CP437, trailing reset; no BOM

Pure stdlib — no new packages.
"""

from __future__ import annotations

import os
import re
import textwrap
import unicodedata


# --- CP437 box-drawing -------------------------------------------------------
_TL = "\u2554"  # ╔
_TR = "\u2557"  # ╗
_BL = "\u255a"  # ╚
_BR = "\u255d"  # ╝
_H = "\u2550"   # ═
_V = "\u2551"   # ║
_HL = "\u2500"  # ─ (single horizontal separator)

# ANSI SGR fragments (no ESC prefix)
_ESC = "\x1b["
_RESET = _ESC + "0m"
_BORDER = _ESC + "1;37;40m"   # bright white on black
_TITLE = _ESC + "1;36;40m"    # bright cyan
_LABEL = _ESC + "1;33;40m"    # bright yellow
_VALUE = _ESC + "0;37;40m"    # white
_BODY = _ESC + "0;37;40m"

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


def _field_row_simple(label: str, value: str) -> str:
    """Build an info row with yellow label and white value, 80 cols total."""
    value = "n/a" if value in (None, "") else str(value)
    # After left bar: space + label + value, pad to INNER, right bar.
    # Colour switches mid-line: border V, then " ", label coloured, value coloured.
    label_part = label + ": "
    max_val = _INNER - 1 - len(label_part)  # -1 for the leading space
    if max_val < 0:
        max_val = 0
    val = value if len(value) <= max_val else value[:max_val]
    pad_len = _INNER - 1 - len(label_part) - len(val)
    if pad_len < 0:
        pad_len = 0
    return (
        f"{_BORDER}{_V} {_LABEL}{label_part}{_VALUE}{val}{' ' * pad_len}{_BORDER}{_V}{_RESET}"
    )


def _combo_info_row(year, source, players, mode) -> str:
    """Year / Source / Players / Mode on one row (matches frozen samples)."""
    year = year or "n/a"
    source = source or "n/a"
    players = players if players not in (None, "") else "n/a"
    mode = mode if mode not in (None, "") else "n/a"
    # Build as plain then colour-inject by reconstructing
    # Sample: " Year: 1995  Source: Commercial  Players: 1  Mode: Single Player"
    parts = [
        ("Year: ", str(year)),
        ("Source: ", str(source)),
        ("Players: ", str(players)),
        ("Mode: ", str(mode)),
    ]
    # Assemble coloured segments with two spaces between pairs
    segs = []
    for i, (lab, val) in enumerate(parts):
        if i:
            segs.append(_VALUE + "  ")
        segs.append(_LABEL + lab + _VALUE + val)
    plain_len = sum(len(lab) + len(val) for lab, val in parts) + 2 * (len(parts) - 1)
    # leading space after V
    pad = _INNER - 1 - plain_len
    if pad < 0:
        # Truncate mode value first
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
    return f"{_BORDER}{_V} " + "".join(segs) + (" " * pad) + f"{_BORDER}{_V}{_RESET}"


def _title_row(title: str) -> str:
    title = sanitise_text(title) or "Unknown"
    if len(title) > _TEXT_WIDTH:
        title = title[:_TEXT_WIDTH]
    centred = _centre(title, _INNER)
    # centred is full INNER width; colour only the title glyphs
    # Rebuild: left pad + title + right pad with cyan on title only
    pad = _INNER - len(title)
    left = pad // 2
    right = pad - left
    return (
        f"{_BORDER}{_V}{' ' * left}{_TITLE}{title}{_BORDER}{' ' * right}{_V}{_RESET}"
    )


def _top_border() -> str:
    return f"{_BORDER}{_TL}{_H * (_COLS - 2)}{_TR}{_RESET}"


def _bottom_border() -> str:
    return f"{_BORDER}{_BL}{_H * (_COLS - 2)}{_BR}{_RESET}"


def _sep_border() -> str:
    # Samples use a full-width single-line separator without corner joints
    # (plain ─ × 80) in bright white — matches frozen A8 output.
    return f"{_BORDER}{_HL * _COLS}{_RESET}"


def _body_row(text: str) -> str:
    text = text if text is not None else ""
    if len(text) > _TEXT_WIDTH:
        text = text[:_TEXT_WIDTH]
    # " " + text padded to INNER
    interior_text = _pad(" " + text, _INNER)
    # Colour: after V, body colour for the text area
    return f"{_BORDER}{_V}{_BODY}{interior_text[0]}{interior_text[1:]}{_BORDER}{_V}{_RESET}"


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

    Returns ``(cp437_bytes_with_lf_only, warnings)``.
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
    # Prefixed clear + home so MyMenu fullscreen paint is clean
    prefix = f"{_ESC}?7l{_ESC}40m{_ESC}2J{_ESC}H"

    lines.append(_top_border())
    lines.append(_title_row(title or "Unknown"))
    lines.append(_sep_border())
    lines.append(
        _combo_info_row(
            sanitise_text(year) if year else None,
            sanitise_text(source) if source else None,
            sanitise_text(str(max_players)) if max_players not in (None, "") else None,
            sanitise_text(play_mode) if play_mode else None,
        )
    )
    lines.append(_field_row_simple("Genre", sanitise_text(genre_str)))
    lines.append(
        _field_row_simple(
            "Developer",
            sanitise_text(developer) if developer else "n/a",
        )
    )
    lines.append(
        _field_row_simple(
            "Publisher",
            sanitise_text(publisher) if publisher else "n/a",
        )
    )
    lines.append(_sep_border())

    body, body_warns = _body_lines(notes or "")
    warnings.extend(body_warns)
    if body:
        for bl in body:
            lines.append(_body_row(bl))
        lines.append(_sep_border())

    series_text = sanitise_text(series) if series else ""
    if series_text:
        # " Series: <text>"
        label = "Series: "
        max_val = _TEXT_WIDTH - len(label)
        if len(series_text) > max_val:
            series_text = series_text[: max(0, max_val - 4)] + " ..."
        lines.append(_body_row(label + series_text))
    lines.append(_bottom_border())

    # First line gets clear prefix glued to top border
    lines[0] = prefix + lines[0]

    # Line endings: LF only (0x0A). Frozen A8 samples and MyMenu's ANSI
    # viewer treat CRLF as *two* advances (CR + LF), which shows as a blank
    # line after every row. DOS batch files still use CRLF elsewhere.
    raw = "\n".join(lines) + "\n"
    # Encode CP437 with replace; log replacements via warnings when non-encodable remain
    encoded = raw.encode("cp437", errors="replace")
    # Detect replacement chars that weren't intentional '?'
    # (best-effort; skip for box-drawing which are all in cp437)
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
