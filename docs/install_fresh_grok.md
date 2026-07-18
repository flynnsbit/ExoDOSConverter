# Install & first pack from Grok Build CLI (minimal)

For a non-expert. Goal: as few questions as possible; Grok runs almost everything after a **one-time shell bootstrap** that gives you the skill.

**Related:** [full shell install](install_fresh.md) · [mister-pack overview](MISTER_PACK.md)

---

## Important: `/mister-pack` is not built into Grok

A brand-new Grok install **does not** include the mister-pack skill.

`/mister-pack` appears only after Grok can **see** the skill files. That happens when either:

| How | Where the skill lives | When `/mister-pack` works |
|-----|------------------------|---------------------------|
| **Recommended** | Inside the ExoDOSConverter git repo: `.grok/skills/mister-pack/` | You start Grok **from that repo** (cwd is the project) |
| Optional | `~/.grok/skills/mister-pack/` (user-wide copy) | Any directory, any project |

So the real first-time path is:

```text
1. Shell once  →  clone repo  →  start Grok inside it   (skill loads)
2. Inside Grok →  /mister-pack or plain English          (setup + build)
```

You do **not** need to “install an agent package” separately. Cloning the open-source repo **is** how you get the skill.

---

## Phase 0 — Shell once (get Grok + skill)

Do this in a normal terminal **before** expecting `/mister-pack` to exist.

### 0a. Install Grok Build CLI (if you don’t have it)

Follow current Grok install docs for your machine, then confirm:

```bash
grok --version   # or however you launch the TUI on your system
```

You need a working Grok session that can run shell commands.

### 0b. Clone ExoDOSConverter (this delivers the skill)

```bash
mkdir -p ~/Projects
cd ~/Projects
git clone https://github.com/flynnsbit/ExoDOSConverter.git
cd ExoDOSConverter
```

That checkout includes:

```text
.grok/skills/mister-pack/SKILL.md   ← this is the /mister-pack skill
packcli/                            ← setup / doctor / build CLI
```

### 0c. Start Grok **from inside the repo**

```bash
cd ~/Projects/ExoDOSConverter
grok
```

Grok discovers project skills under `.grok/skills/`. After a few seconds you should see **`/mister-pack`** when you type `/` (or use plain English about MiSTer packs — the skill description also triggers on those phrases).

**Check:** type `/` and look for `mister-pack`.  
If it’s missing: confirm you’re in the repo root (`ls .grok/skills/mister-pack/SKILL.md`) and restart Grok from that directory.

### Optional: install the skill for every project

If you want `/mister-pack` even when Grok’s cwd is not the converter repo:

```bash
mkdir -p ~/.grok/skills
cp -a ~/Projects/ExoDOSConverter/.grok/skills/mister-pack ~/.grok/skills/
```

Still keep the converter checkout for `packcli` and data files; the skill tells Grok how to run them.

---

## What you need on the machine (games data)

Grok will install **open-source tools**. It will **not** download games.

| Need | Plain English |
|------|----------------|
| **eXoDOS** | Your game collection folder. Inside it: `eXo/eXoDOS/`. |
| **dosassets** | Folder with MS-DOS / FreeDOS install images (`msdos622` and/or `freedos`). |
| **Internet** | First setup pulls dosforge + updates from GitHub. |
| **Passwordless sudo** (recommended) | So VHD create doesn’t stop for a password. Test: `sudo -n true` |

You do **not** need the converter GUI or to know pip/git remotes for day-to-day use.

---

## Phase 1 — Inside Grok (skill is loaded)

### What the agent installs for you

```text
python3 -m packcli setup
```

Installs or updates from GitHub:

- **dosforge** (latest release)
- **ExoDOSConverter** tip + packcli Python deps (if this tree is a git clone)

Never downloads the eXoDOS collection.

### What you type (minimal)

**First time — paths known:**

```text
/mister-pack

I'm new. Please:
1. Run packcli setup; install/update dosforge + converter
2. Save collection = /REPLACE/WITH/YOUR/eXoDOS
3. Save dosassets = /REPLACE/WITH/YOUR/dosassets
4. Default audio gus
5. Run doctor
6. If green, resolve "doom" and "blood", build pack FirstPack with those games
7. Tell me the folder to copy to the MiSTer SD

Do not download the eXoDOS collection. Ask if a path is wrong.
```

**First time — paths unknown:**

```text
/mister-pack set me up for MiSTer packs.
I have eXoDOS and dosassets on this PC; please ask me for the paths.
Use GUS. Keep steps simple.
```

**No slash yet?** (skill loaded but you forget the name) — plain English still works:

```text
Set up MiSTer pack tools and build a small GUS pack with DOOM and Blood.
```

**Later builds** (config already saved):

```text
/mister-pack create a GUS pack named Demo with DOOM and Blood
```

### What the agent does (you mostly wait)

| Step | Agent action | You only if… |
|------|----------------|--------------|
| 1 | Use this repo; run `python3 -m packcli setup` | Network blocks GitHub |
| 2 | Save paths to `~/.config/mister-pack/config.toml` | **Prompt:** eXoDOS path / dosassets path |
| 3 | `python3 -m packcli doctor` | sudo / missing host packages (shell fix below) |
| 4 | `resolve` titles → write recipe | You pick games / SB vs GUS if unset |
| 5 | `python3 -m packcli build -f …` | Fixable build error → agent retries or one question |
| 6 | Print output folder for the SD card | You copy (or ask agent to `cp` if SD is mounted) |

**Typical prompts (only when needed):**

1. Full path to eXoDOS (folder that contains `eXo/eXoDOS/`)
2. Path to dosassets (`msdos622` or `freedos` inside)
3. Sound Blaster (**sb**) or GUS (**gus**) if you didn’t say

---

## When you must drop back to a real shell

### Skill / Grok not ready

```bash
cd ~/Projects/ExoDOSConverter   # must be here for project skill
ls .grok/skills/mister-pack/SKILL.md
grok                            # restart from repo root
```

### Passwordless sudo

```bash
sudo -n true
```

If that fails, fix sudo for your user, then in Grok:  
> sudo is fixed — run doctor and continue

### Host packages missing

```bash
# Debian/Ubuntu example
sudo apt update
sudo apt install -y python3 python3-pip git nbd-client qemu-utils
```

Then in Grok:  
> packages installed — run setup and doctor again

### eXoDOS / dosassets not on this PC

Obtain them yourself, put them on disk, give Grok the paths. Never auto-downloaded.

### Copy pack to SD

Agent prints something like:

```text
…/out/mister-packs/FirstPack/ao486/FirstPack/
```

Copy that **whole** folder (`.vhd` and `cd/` if present) to the MiSTer SD under `games/ao486/`.

---

## End-to-end picture (new user)

```text
SHELL (once)
  install Grok CLI
  git clone flynnsbit/ExoDOSConverter
  cd ExoDOSConverter
  grok                          ← skill loads from .grok/skills/mister-pack/

GROK (after that)
  /mister-pack  or  plain English
       │
       ├─ packcli setup     → dosforge + converter (open source)
       ├─ ask paths once    → eXoDOS + dosassets (your data)
       ├─ doctor
       ├─ resolve + build
       └─ “here is the folder for your SD card”
```

| Automatic | You supply |
|-----------|------------|
| Skill (via clone + start Grok in repo) | eXoDOS path |
| dosforge + ExoDOSConverter updates | dosassets path |
| packcli workflow | Game list / pack name when you want a pack |

---

## After the first successful pack

Stay in Grok (still best from the ExoDOSConverter directory, unless you installed the skill under `~/.grok/skills/`):

| You say | Agent runs |
|---------|------------|
| “Update the tools” | `python3 -m packcli setup` |
| “Is everything ready?” | `python3 -m packcli doctor` |
| “Exact name for raptor?” | `resolve raptor` |
| “Make a pack with …” | resolve → recipe → `build` |
| “Switch this VHD to SB” | `patch-autoexec --audio sb` |

No need to re-enter paths if config was saved once.

---

## If something fails

| Problem | Fix |
|---------|-----|
| `/mister-pack` missing | Start Grok from ExoDOSConverter root, or copy skill to `~/.grok/skills/` |
| dosforge / converter missing | Agent runs `setup` |
| Collection path wrong | Agent asks again |
| No games matched | Agent runs `resolve` with exact titles |
| VHD / FAT16 size error | Agent uses `boot: auto` or FreeDOS |
| Want SB instead of GUS | `patch-autoexec --audio sb` |
