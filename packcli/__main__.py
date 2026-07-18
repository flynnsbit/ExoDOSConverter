#!/usr/bin/env python3
"""mister-pack CLI: doctor | resolve | build | rebuild-vhd."""

from __future__ import annotations

import argparse
import sys


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="mister-pack",
        description="Build MiSTer eXoDOS packs (recipe → convert → VHD)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="Check collection, dosforge, payloads, dosassets")

    p_res = sub.add_parser("resolve", help="Fuzzy-match game titles")
    p_res.add_argument("query", nargs="+", help="Search string(s)")
    p_res.add_argument("--limit", type=int, default=15)

    p_build = sub.add_parser("build", help="Build pack from recipe YAML or .sel")
    p_build.add_argument(
        "-f",
        "--recipe",
        required=True,
        help="Path to recipe.yaml or selection .sel",
    )

    p_reb = sub.add_parser(
        "rebuild-vhd", help="Rebuild VHD from existing pack games/ + mymenu/"
    )
    p_reb.add_argument("pack_dir", help="Pack directory containing games/ and mymenu/")
    p_reb.add_argument(
        "--boot",
        default="auto",
        help="auto|msdos622|freedos (default auto)",
    )
    p_reb.add_argument("--name", default="", help="Build/VHD name override")
    p_reb.add_argument("--dosassets", default="", help="dosassets path override")

    p_patch = sub.add_parser(
        "patch-autoexec",
        help="Patch AUTOEXEC on existing VHD (ULTRASND 5,5 + PMINIT /GUS 1)",
    )
    p_patch.add_argument("vhd", help="Path to .vhd")
    p_patch.add_argument(
        "--no-gus",
        action="store_true",
        help="Do not inject GUS/PicoMEM lines",
    )

    args = parser.parse_args(argv)

    if args.cmd == "doctor":
        from packcli.doctor import run_doctor

        return run_doctor()
    if args.cmd == "resolve":
        from packcli.resolve import run_resolve

        return run_resolve(args.query, limit=args.limit)
    if args.cmd == "build":
        from packcli.build import run_build

        return run_build(args.recipe)
    if args.cmd == "rebuild-vhd":
        from packcli.rebuild import run_rebuild

        return run_rebuild(
            args.pack_dir,
            boot=args.boot,
            name=args.name,
            dosassets=args.dosassets,
        )
    if args.cmd == "patch-autoexec":
        from packcli.patch_autoexec import run_patch_autoexec

        return run_patch_autoexec(args.vhd, gus=not args.no_gus)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
