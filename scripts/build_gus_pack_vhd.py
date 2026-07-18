#!/usr/bin/env python3
"""Build GUS Classics pack — thin wrapper around packcli + recipes/gus-classics.yaml."""

from __future__ import annotations

import os
import sys


def main() -> int:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, root)
    recipe = os.path.join(root, "recipes", "gus-classics.yaml")
    # Allow env overrides used by older scripts
    if os.environ.get("EDC_OUT") and not os.environ.get("MISTER_PACK_OUT"):
        os.environ["MISTER_PACK_OUT"] = os.environ["EDC_OUT"]
    from packcli.build import run_build

    return run_build(recipe)


if __name__ == "__main__":
    raise SystemExit(main())
