"""Resolve free-text game names to eXoDOS collection titles."""

from __future__ import annotations

import re
import sys
from typing import List, Tuple

from packcli.config import converter_root, default_collection, expand_path


def _load_csv_titles() -> List[str]:
    csv_path = converter_root() / "data" / "eXoDOSv6.csv"
    titles = []
    if not csv_path.is_file():
        return titles
    for line in csv_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or ";" not in line:
            continue
        title, _dos = line.rsplit(";", 1)
        titles.append(title.strip())
    return titles


def _base_name(title: str) -> str:
    """Title without trailing (year) / edition noise for matching."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", title).strip().lower()


def resolve_query(query: str, limit: int = 15) -> List[Tuple[str, str]]:
    """Return list of (title, match_kind) best-first."""
    q = query.strip().lower()
    if not q:
        return []
    titles = _load_csv_titles()
    scored: List[Tuple[int, str, str]] = []
    # lower score = better
    for t in titles:
        tl = t.lower()
        base = _base_name(t)
        if tl == q or base == q:
            scored.append((0, t, "exact"))
        elif base == q or re.fullmatch(re.escape(q), base):
            scored.append((0, t, "exact"))
        elif base.startswith(q + " ") or base.startswith(q + ":"):
            scored.append((1, t, "prefix"))
        elif re.search(r"\b" + re.escape(q) + r"\b", base):
            # whole-word in base name (prefer over random contains)
            # "doom" in "DOOM" base ranks high; "doom" in "Dr. Doom's…" still matches
            if base == q or base.startswith(q):
                scored.append((1, t, "prefix"))
            elif base.split()[0] == q:
                scored.append((2, t, "word"))
            else:
                scored.append((4, t, "word"))
        elif tl.startswith(q):
            scored.append((3, t, "prefix"))
        elif q in tl:
            scored.append((5, t, "contains"))
    scored.sort(key=lambda x: (x[0], x[1].lower()))
    seen = set()
    uniq: List[Tuple[str, str]] = []
    for _s, t, k in scored:
        if t in seen:
            continue
        seen.add(t)
        uniq.append((t, k))
        if len(uniq) >= limit:
            break
    return uniq


def run_resolve(queries: List[str], limit: int = 15) -> int:
    if not queries:
        print("usage: mister-pack resolve <query> [query...]", file=sys.stderr)
        return 2
    coll = expand_path(default_collection())
    print(f"collection hint: {coll or '(unset)'}")
    print(f"title index: {converter_root() / 'data' / 'eXoDOSv6.csv'}")
    for q in queries:
        print(f"\n=== {q!r} ===")
        hits = resolve_query(q, limit=limit)
        if not hits:
            print("  (no matches)")
            continue
        for i, (title, kind) in enumerate(hits):
            mark = " *" if i == 0 else "  "
            print(f"{mark}[{kind:8}] {title}")
        if hits:
            print(f"  best: {hits[0][0]}")
    return 0
