"""Resolve free-text game names to eXoDOS collection titles."""

from __future__ import annotations

import sys
from pathlib import Path
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


def resolve_query(query: str, limit: int = 15) -> List[Tuple[str, str]]:
    """Return list of (title, match_kind)."""
    q = query.strip().lower()
    if not q:
        return []
    titles = _load_csv_titles()
    exact = []
    starts = []
    contains = []
    for t in titles:
        tl = t.lower()
        if tl == q:
            exact.append((t, "exact"))
        elif tl.startswith(q) or q in tl.split("(")[0].strip().lower():
            starts.append((t, "prefix"))
        elif q in tl:
            contains.append((t, "contains"))
    out = exact + starts + contains
    # dedupe preserve order
    seen = set()
    uniq = []
    for t, k in out:
        if t in seen:
            continue
        seen.add(t)
        uniq.append((t, k))
    return uniq[:limit]


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
        for title, kind in hits:
            print(f"  [{kind:8}] {title}")
    return 0
