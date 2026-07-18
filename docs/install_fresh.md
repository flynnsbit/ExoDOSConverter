# Install from a brand-new system (shell)

Full path for someone with a clean Linux machine, terminal access, and no prior mister-pack setup.

**Related:** [install from Grok Build CLI](install_fresh_grok.md) · [mister-pack overview](MISTER_PACK.md) · [full skill guide](MISTER_PACK_SKILL.md)

---

## What this does / does not install

| Automatic (`packcli setup`) | You already have (never downloaded) |
|-----------------------------|-------------------------------------|
| **dosforge** (latest GitHub release) | **eXoDOS** game collection |
| **ExoDOSConverter** (git master + packcli deps) | **dosassets** (MS-DOS / FreeDOS install media) |

---

## Before you start

You need:

1. **Linux** (recommended for headless VHD create)
2. **Python 3.10+**, **git**, **pip**
3. **Network** (GitHub + pip)
4. **eXoDOS v6** on disk — root folder must contain `eXo/eXoDOS/`
5. **dosassets** on disk — folder with `msdos622/` and/or `freedos/` (DOS install floppies/images used by dosforge)
6. **`sudo -n true` works** (passwordless sudo) for NBD disk ops during VHD create

You do **not** need the ExoDOSConverter GUI or Windows.

---

## Step 1 — Host packages

Ubuntu/Debian-style example (adjust for your distro):

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git nbd-client qemu-utils
```

Check:

```bash
python3 --version   # need 3.10 or newer
git --version
sudo -n true        # must succeed for unattended VHD builds
```

If `sudo -n true` fails, configure passwordless sudo for your user (or run builds in a session where you can enter a password when asked — headless automation will fail).

---

## Step 2 — Clone ExoDOSConverter

```bash
mkdir -p ~/Projects
cd ~/Projects
git clone https://github.com/flynnsbit/ExoDOSConverter.git
cd ExoDOSConverter
```

---

## Step 3 — Install / update open-source engines + save your paths

```bash
# Replace BOTH paths with yours:
#   collection = folder that contains eXo/eXoDOS/
#   dosassets  = folder that contains msdos622/ and/or freedos/
python3 -m packcli setup \
  --collection /path/to/your/eXoDOS \
  --dosassets  /path/to/your/dosassets \
  --audio gus
```

What this does:

- Installs or updates **dosforge** from the latest GitHub release
- Updates this **ExoDOSConverter** tree to latest `master` (if it’s a git clone)
- Installs modern packcli Python deps (`requirements-packcli.txt`)
- Writes `~/.config/mister-pack/config.toml` with your paths
- Does **not** download games or DOS install media

Useful variants later:

```bash
python3 -m packcli setup                  # engines only (paths already in config)
python3 -m packcli setup --force          # force reinstall / hard-reset converter
python3 -m packcli setup --skip-dosforge  # converter only
python3 -m packcli setup --skip-converter # dosforge only
```

---

## Step 4 — Health check

```bash
python3 -m packcli doctor
```

All required lines should show `OK` (Python, dosforge, payloads, collection, dosassets; `sudo -n` preferred).

If collection fails: fix the path so `…/eXo/eXoDOS` exists, then re-run setup with `--collection` or:

```bash
export EXODOS_COLLECTION=/path/to/your/eXoDOS
export DOSFORGE_DOSASSETS_DIR=/path/to/your/dosassets
```

---

## Step 5 — Resolve game titles (recommended)

Fuzzy names → exact eXo titles for recipes:

```bash
python3 -m packcli resolve doom blood "duke nukem"
```

Use the best match (often marked `*`), e.g. `DOOM (1993)`, `Blood (1997)`.

---

## Step 6 — Build a pack

**Shipped GUS example:**

```bash
python3 -m packcli build -f recipes/gus-classics.yaml
```

**Or a tiny custom recipe:**

```bash
cat > /tmp/my-pack.yaml <<'EOF'
name: Demo Pack
collection: ${EXODOS_COLLECTION}
output: ./out/mister-packs

games:
  - DOOM (1993)
  - Blood (1997)

options:
  launcher: mymenu
  audio: gus
  boot: auto
EOF

python3 -m packcli build -f /tmp/my-pack.yaml
```

Output layout (approx.):

```text
out/mister-packs/<PackName>/ao486/<PackName>/
  <PackName>.vhd
  cd/          # external CD images if any
  floppy/      # if needed
```

Copy the **entire** `ao486/<PackName>/` folder to the MiSTer SD card (not only the `.vhd`).

---

## Step 7 — Common follow-ups

```bash
# Rebuild VHD only (games/ + mymenu/ already exist)
python3 -m packcli rebuild-vhd out/mister-packs/Demo_Pack --boot auto --audio gus

# Change sound on an existing VHD (no full rebuild)
python3 -m packcli patch-autoexec path/to/Pack.vhd --audio sb
python3 -m packcli patch-autoexec path/to/Pack.vhd --audio gus

# Months later: pull latest tools
cd ~/Projects/ExoDOSConverter
python3 -m packcli setup
```

---

## Minimal day-one checklist

```bash
# 0. Host: Python 3.10+, git, sudo -n, NBD tools
# 1. eXoDOS + dosassets already on disk

git clone https://github.com/flynnsbit/ExoDOSConverter.git
cd ExoDOSConverter

python3 -m packcli setup \
  --collection /YOUR/eXoDOS \
  --dosassets  /YOUR/dosassets \
  --audio gus

python3 -m packcli doctor
python3 -m packcli resolve doom blood
python3 -m packcli build -f recipes/gus-classics.yaml
```

---

## Config file (optional to edit by hand)

`~/.config/mister-pack/config.toml` is created/updated by `setup`. Example:

```toml
collection = "/path/to/your/eXoDOS"
dosassets  = "/path/to/your/dosassets"
output     = "/home/you/Projects/ExoDOSConverter/out/mister-packs"
converter  = "/home/you/Projects/ExoDOSConverter"
audio      = "gus"
```

Env vars override config when set: `EXODOS_COLLECTION`, `DOSFORGE_DOSASSETS_DIR`, `MISTER_PACK_OUT`, `MISTER_PACK_AUDIO`.
