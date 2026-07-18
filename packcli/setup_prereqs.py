"""Install / update open-source engines: dosforge + ExoDOSConverter.

Never downloads eXoDOS game collection or MS-DOS install media — those stay
user-supplied paths in config/env.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Optional, Tuple

from packcli.config import (
    converter_root,
    default_collection,
    default_dosassets,
    user_config_path,
)

DOSFORGE_REPO = "flynnsbit/dosforge"
CONVERTER_REPO = "flynnsbit/ExoDOSConverter"
DOSFORGE_GIT = f"https://github.com/{DOSFORGE_REPO}.git"
CONVERTER_GIT = f"https://github.com/{CONVERTER_REPO}.git"
GITHUB_API = "https://api.github.com"


def _ok(msg: str) -> None:
    print(f"  OK  {msg}", flush=True)


def _info(msg: str) -> None:
    print(f"  ..  {msg}", flush=True)


def _bad(msg: str) -> None:
    print(f"  !!  {msg}", flush=True)


# Modern flexible pins for packcli / converter on current Python (3.10–3.14).
# Do NOT use the root requirements.txt pins (Pillow==9.0.1 etc.) — they fail
# on newer interpreters. Legacy GUI pins are optional and best-effort only.
PACKCLI_DEPS = (
    "PyYAML>=6.0",
    "Pillow>=10.0",
    "requests>=2.28",
)


def _run(
    cmd: list[str],
    *,
    cwd: Optional[str] = None,
    check: bool = True,
    capture: bool = False,
) -> subprocess.CompletedProcess:
    _info("$ " + " ".join(cmd))
    return subprocess.run(
        cmd,
        cwd=cwd,
        check=check,
        capture_output=capture,
        text=capture,
    )


def _http_json(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "mister-pack-setup",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def latest_dosforge_tag() -> str:
    """Return latest release tag (e.g. v0.9.57)."""
    data = _http_json(f"{GITHUB_API}/repos/{DOSFORGE_REPO}/releases/latest")
    tag = (data.get("tag_name") or "").strip()
    if not tag:
        raise RuntimeError("could not determine latest dosforge release tag")
    return tag


def latest_converter_sha() -> Tuple[str, str]:
    """Return (short_sha, date) for default branch tip."""
    data = _http_json(f"{GITHUB_API}/repos/{CONVERTER_REPO}/commits/master")
    sha = (data.get("sha") or "")[:7]
    date = (
        (data.get("commit") or {}).get("committer") or {}
    ).get("date", "")
    if not sha:
        raise RuntimeError("could not determine latest ExoDOSConverter commit")
    return sha, date


def installed_dosforge_version() -> Optional[str]:
    try:
        r = subprocess.run(
            [sys.executable, "-m", "dosforge", "--version"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if r.returncode != 0:
            return None
        text = (r.stdout or r.stderr or "").strip()
        # "dosforge 0.9.57" or "0.9.57"
        m = re.search(r"(\d+\.\d+\.\d+)", text)
        return m.group(1) if m else text
    except Exception:
        return None


def _pip_install(args: list[str]) -> None:
    """pip install with fallbacks for user-site / PEP 668 managed envs."""
    base = [sys.executable, "-m", "pip", "install", "--upgrade"]
    attempts = [
        base + args,
        base + ["--user"] + args,
        base + ["--break-system-packages"] + args,
        base + ["--user", "--break-system-packages"] + args,
    ]
    last_err = ""
    for cmd in attempts:
        _info("$ " + " ".join(cmd))
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            return
        err = (r.stderr or r.stdout or "").strip()
        last_err = err
        # Only retry on environment policy / permission style failures
        low = err.lower()
        if not any(
            x in low
            for x in (
                "externally-managed-environment",
                "permission denied",
                "access is denied",
                "operation not permitted",
                "defaulting to user installation",
            )
        ):
            # Real package/build failure — do not mask with more flags
            raise subprocess.CalledProcessError(
                r.returncode, cmd, output=r.stdout, stderr=r.stderr
            )
    raise RuntimeError(f"pip install failed after fallbacks:\n{last_err[-1500:]}")


def _install_packcli_python_deps(dest: Path) -> None:
    """Install modern deps required by packcli + converter (not legacy GUI pins)."""
    packcli_req = dest / "requirements-packcli.txt"
    try:
        if packcli_req.is_file():
            _pip_install(["-r", str(packcli_req)])
        else:
            _pip_install(list(PACKCLI_DEPS))
        _ok("packcli Python dependencies installed")
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        # Soft-check: already present is fine
        missing = []
        for mod, pip_name in (
            ("yaml", "PyYAML"),
            ("PIL", "Pillow"),
            ("requests", "requests"),
        ):
            try:
                __import__(mod)
            except ImportError:
                missing.append(pip_name)
        if missing:
            _bad(f"missing Python packages {missing}: {exc}")
            raise
        _info(f"pip reported issues but required imports OK ({exc})")


def install_or_update_dosforge(*, force: bool = False) -> int:
    print("\n=== dosforge ===", flush=True)
    try:
        tag = latest_dosforge_tag()
    except Exception as exc:
        _bad(f"GitHub latest release failed: {exc}")
        return 1
    latest = tag.lstrip("v")
    current = installed_dosforge_version()
    _info(f"latest release: {tag}")
    _info(f"installed:      {current or '(none)'}")

    if current == latest and not force:
        _ok(f"dosforge already up to date ({current})")
        return 0

    # Prefer release tag pin for reproducibility
    spec = f"dosforge @ git+{DOSFORGE_GIT}@{tag}"
    try:
        _pip_install([spec])
    except (subprocess.CalledProcessError, RuntimeError):
        _bad("pip install dosforge from git tag failed; trying main branch")
        try:
            _pip_install([f"dosforge @ git+{DOSFORGE_GIT}@main"])
        except (subprocess.CalledProcessError, RuntimeError) as exc:
            _bad(f"dosforge install failed: {exc}")
            return 1

    new_ver = installed_dosforge_version()
    if new_ver:
        _ok(f"dosforge installed: {new_ver}")
        return 0
    _bad("dosforge install finished but --version failed")
    return 1


def _default_converter_dir() -> Path:
    env = (os.environ.get("MISTER_PACK_CONVERTER") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    # Prefer the tree this packcli is running from
    here = converter_root()
    if (here / "packcli").is_dir() and (here / "data" / "mister").is_dir():
        return here
    return Path.home() / "Projects" / "ExoDOSConverter"


def _git_head(repo: Path) -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode == 0:
            return (r.stdout or "").strip()
    except Exception:
        pass
    return None


def install_or_update_converter(
    *,
    target: Optional[str] = None,
    force: bool = False,
) -> Tuple[int, Optional[Path]]:
    print("\n=== ExoDOSConverter ===", flush=True)
    dest = Path(target).expanduser().resolve() if target else _default_converter_dir()
    try:
        remote_sha, remote_date = latest_converter_sha()
    except Exception as exc:
        _bad(f"GitHub tip commit failed: {exc}")
        return 1, None
    _info(f"latest master: {remote_sha} ({remote_date})")
    _info(f"install path:  {dest}")

    if dest.is_dir() and (dest / ".git").is_dir():
        local = _git_head(dest)
        _info(f"local HEAD:    {local or '(unknown)'}")
        # Compare short SHAs (prefix match handles 7 vs longer abbrev)
        same = bool(
            local
            and remote_sha
            and (local.startswith(remote_sha) or remote_sha.startswith(local))
        )
        if same and not force:
            _ok(f"ExoDOSConverter already up to date ({local})")
        else:
            try:
                _run(["git", "-C", str(dest), "fetch", "origin", "master"])
                _run(["git", "-C", str(dest), "pull", "--ff-only", "origin", "master"])
            except subprocess.CalledProcessError:
                _bad(
                    "git pull failed (local changes?). "
                    "Commit/stash or pass --force with a clean tree."
                )
                if not force:
                    return 1, dest
                try:
                    _run(["git", "-C", str(dest), "fetch", "origin", "master"])
                    _run(
                        [
                            "git",
                            "-C",
                            str(dest),
                            "reset",
                            "--hard",
                            "origin/master",
                        ]
                    )
                except subprocess.CalledProcessError as exc:
                    _bad(f"force update failed: {exc}")
                    return 1, dest
            new = _git_head(dest)
            _ok(f"ExoDOSConverter updated to {new}")
    elif dest.is_dir() and (dest / "packcli").is_dir():
        _info("directory exists but is not a git clone; installing deps only")
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            _run(
                [
                    "git",
                    "clone",
                    "--branch",
                    "master",
                    "--single-branch",
                    CONVERTER_GIT,
                    str(dest),
                ]
            )
        except subprocess.CalledProcessError as exc:
            _bad(f"git clone failed: {exc}")
            return 1, None
        _ok(f"cloned ExoDOSConverter → {dest}")

    # Python deps for packcli + converter (modern pins only — not GUI freeze)
    try:
        _install_packcli_python_deps(dest)
    except (subprocess.CalledProcessError, RuntimeError) as exc:
        _bad(f"pip install packcli deps failed: {exc}")
        return 1, dest

    # Payload sanity
    for rel in ("data/mister/boot-c.zip", "data/mister/distro.zip", "packcli"):
        p = dest / rel
        if p.exists():
            _ok(f"present {rel}")
        else:
            _bad(f"missing {rel} after install")
            return 1, dest

    return 0, dest


def _write_config_snippet(
    *,
    converter: Optional[Path],
    collection: Optional[str],
    dosassets: Optional[str],
    audio: Optional[str],
) -> None:
    """Merge keys into ~/.config/mister-pack/config.toml (create if needed)."""
    path = user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = ""
    if path.is_file():
        existing = path.read_text(encoding="utf-8")

    def upsert(text: str, key: str, value: str) -> str:
        line = f'{key} = "{value}"'
        pat = re.compile(rf"(?m)^\s*{re.escape(key)}\s*=.*$")
        if pat.search(text):
            return pat.sub(line, text)
        if text and not text.endswith("\n"):
            text += "\n"
        return text + line + "\n"

    text = existing
    if converter:
        text = upsert(text, "converter", str(converter))
    if collection:
        text = upsert(text, "collection", collection)
    if dosassets:
        text = upsert(text, "dosassets", dosassets)
    if audio in ("sb", "gus"):
        text = upsert(text, "audio", audio)

    if not text.strip():
        text = (
            "# mister-pack config (written by packcli setup)\n"
            f'converter = "{converter}"\n'
            if converter
            else "# mister-pack config\n"
        )

    path.write_text(text, encoding="utf-8")
    _ok(f"wrote {path}")


def run_setup(
    *,
    force: bool = False,
    converter_dir: Optional[str] = None,
    collection: Optional[str] = None,
    dosassets: Optional[str] = None,
    audio: Optional[str] = None,
    skip_dosforge: bool = False,
    skip_converter: bool = False,
) -> int:
    """Install/update OSS engines; optionally record user paths in config."""
    print("mister-pack setup (open-source engines only)", flush=True)
    print(
        "  Does NOT download eXoDOS game collection or DOS install floppies.",
        flush=True,
    )
    failed = 0

    if not skip_dosforge:
        failed += install_or_update_dosforge(force=force)
    else:
        _info("skipping dosforge")

    conv_path: Optional[Path] = None
    if not skip_converter:
        rc, conv_path = install_or_update_converter(
            target=converter_dir, force=force
        )
        failed += rc
    else:
        _info("skipping ExoDOSConverter")
        conv_path = _default_converter_dir()

    # User-supplied paths (collection required for builds, never auto-fetched)
    coll = (collection or default_collection() or "").strip()
    assets = (dosassets or default_dosassets() or "").strip()

    print("\n=== user-supplied paths ===", flush=True)
    if coll and Path(coll).is_dir() and (Path(coll) / "eXo" / "eXoDOS").is_dir():
        _ok(f"collection: {coll}")
    elif coll:
        _bad(f"collection path invalid (need eXo/eXoDOS under it): {coll}")
        failed += 1
    else:
        _info(
            "collection not set — pass --collection /path/to/eXoDOS "
            "or set EXODOS_COLLECTION / config.toml (never auto-downloaded)"
        )

    if assets and Path(assets).is_dir():
        _ok(f"dosassets: {assets}")
    elif assets:
        _bad(f"dosassets missing: {assets}")
        failed += 1
    else:
        _info(
            "dosassets not set — pass --dosassets "
            "(MS-DOS/FreeDOS install media; not auto-downloaded)"
        )

    _write_config_snippet(
        converter=conv_path if conv_path and conv_path.is_dir() else None,
        collection=coll if coll else None,
        dosassets=assets if assets else None,
        audio=audio,
    )

    print("\n=== post-setup doctor ===", flush=True)
    # Run doctor from updated tree if possible
    if conv_path and (conv_path / "packcli").is_dir():
        env = os.environ.copy()
        if coll:
            env["EXODOS_COLLECTION"] = coll
        if assets:
            env["DOSFORGE_DOSASSETS_DIR"] = assets
        r = subprocess.run(
            [sys.executable, "-m", "packcli", "doctor"],
            cwd=str(conv_path),
            env=env,
        )
        # doctor failures about missing collection are expected if not passed
        if r.returncode != 0 and coll and assets:
            failed += 1
    else:
        from packcli.doctor import run_doctor

        if run_doctor() != 0 and coll and assets:
            failed += 1

    print(flush=True)
    if failed:
        print(f"setup: finished with {failed} issue(s)", flush=True)
        print(
            "  Tip: set collection with:\n"
            "    python3 -m packcli setup --collection /path/to/eXoDOS",
            flush=True,
        )
        return 1
    print("setup: complete", flush=True)
    if conv_path:
        print(f"  Use converter at: {conv_path}", flush=True)
        print(
            f"  cd {conv_path} && python3 -m packcli build -f recipes/gus-classics.yaml",
            flush=True,
        )
    return 0
