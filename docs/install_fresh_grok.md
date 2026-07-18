# Install & first pack from Grok Build CLI (minimal)

For a non-expert starting **inside Grok Build**. Goal: as few questions as possible; the agent runs almost everything. You only answer when something cannot be guessed, and only leave Grok for things the agent cannot fix alone (rare).

**Related:** [full shell install](install_fresh.md) · [mister-pack overview](MISTER_PACK.md) · skill: `/mister-pack`

---

## What you need on the machine (once)

Grok cannot invent these. Have them before you start:

| Need | Plain English |
|------|----------------|
| **eXoDOS** | Your game collection folder. Inside it you should see an `eXo` folder (and under that `eXoDOS`). |
| **dosassets** | Folder with MS-DOS / FreeDOS install images (`msdos622` and/or `freedos`). Often next to a dosforge install. |
| **Linux + internet** | So tools can be downloaded and the VHD can be built. |
| **Passwordless sudo** (recommended) | So disk image creation does not stop and wait for a password. In a normal terminal: `sudo -n true` should print nothing and succeed. |

You do **not** need to know pip, git remotes, or the converter GUI.

---

## What the agent installs for you

When you use `/mister-pack` or ask to set up / build a pack, the agent runs:

```text
python3 -m packcli setup
```

That **installs or updates** (from GitHub):

- **dosforge** (latest release)
- **ExoDOSConverter** (latest master + Python deps)

It **never** downloads the eXoDOS games. Those stay your folder.

---

## Your experience (what you do vs what Grok does)

### You type one of these in Grok

**First time on this machine:**

> /mister-pack set me up for MiSTer packs. My eXoDOS is at `/paste/your/path` and dosassets at `/paste/your/path`. Use GUS audio.

**If you do not know the paths:**

> /mister-pack set me up for MiSTer packs. I don’t know my paths yet.

**Later, just build:**

> /mister-pack create a GUS pack named Demo with DOOM and Blood

---

### What the agent does (you mostly wait)

| Step | Agent action | You only if… |
|------|----------------|--------------|
| 1 | Find or clone ExoDOSConverter; `cd` there | — |
| 2 | `python3 -m packcli setup` (engines from GitHub) | Network/firewall blocks GitHub → fix network outside Grok |
| 3 | Save paths into `~/.config/mister-pack/config.toml` | **Prompt:** “Where is your eXoDOS?” and optionally dosassets |
| 4 | `python3 -m packcli doctor` | doctor fails on **sudo** → see “Drop back to shell” below |
| 5 | `resolve` game names → write a small recipe | You pick titles / SB vs GUS if you didn’t say |
| 6 | `python3 -m packcli build -f …` | Build fails with a clear error → agent retries or asks one question |
| 7 | Print the folder path to copy to the MiSTer SD | You copy files to the SD card (or ask agent to `cp` if the SD is mounted) |

**Typical prompts (only when needed):**

1. **“What is the full path to your eXoDOS folder?”**  
   Hint: the folder that contains `eXo` → `eXoDOS`.  
   Example answer: `/mnt/media/eXoDOS`

2. **“What is the path to dosassets?”**  
   Hint: folder that contains `msdos622` or `freedos`.  
   Example: `/home/you/Projects/dosforge/dosassets`

3. **“Sound Blaster or GUS?”** if you didn’t say — default **sb** unless you want UltraSound / PicoGUS (**gus**).

That’s it for most people.

---

## Recommended first conversation (copy-paste)

Paste this whole block into Grok (edit the two paths):

```text
/mister-pack

I'm new. Please:
1. Install or update dosforge and ExoDOSConverter with packcli setup
2. Save collection = /REPLACE/WITH/YOUR/eXoDOS
3. Save dosassets = /REPLACE/WITH/YOUR/dosassets
4. Default audio gus
5. Run doctor
6. If doctor is green, resolve "doom" and "blood", then build a small pack named FirstPack with those two games
7. Tell me the exact folder to copy to my MiSTer SD card

Do not download the eXoDOS collection. Ask me if a path is wrong.
```

If you prefer the agent to ask for paths:

```text
/mister-pack set up tools and walk me through my first pack.
I have eXoDOS and dosassets on this PC but I need you to ask me for the paths.
Use GUS. Keep steps simple.
```

---

## When you must drop back to a real shell

Only these cases. The agent should tell you the exact command.

### A. Passwordless sudo not set up

Symptom: doctor warns about `sudo -n`, or VHD create hangs/fails on NBD.

In a normal terminal (not always possible from Grok):

```bash
sudo -n true
```

If that fails, configure passwordless sudo for your user (distro-specific), then return to Grok and say:

> sudo is fixed — run doctor and continue the build

### B. Host packages missing (rare)

If setup/doctor says `git` or `python3` is missing, in a terminal:

```bash
# Debian/Ubuntu example
sudo apt update
sudo apt install -y python3 python3-pip git nbd-client qemu-utils
```

Then in Grok:

> packages installed — run setup and doctor again

### C. eXoDOS or dosassets not on this machine yet

Grok will **not** download them. You must obtain eXoDOS and DOS install media yourself, put them on disk, then give Grok the paths.

### D. Copy pack to SD card

Agent will print something like:

```text
/home/you/Projects/ExoDOSConverter/out/mister-packs/FirstPack/ao486/FirstPack/
```

Copy **that whole folder** (`.vhd` **and** `cd/` if present) onto the MiSTer SD under `games/ao486/`.  
If the SD is already mounted in Linux, you can ask Grok:

> The SD is mounted at /media/me/MISTER — copy the pack there for me

---

## After the first successful pack

You can stay in Grok forever for normal work:

| You say | Agent runs |
|---------|------------|
| “Update the tools” | `python3 -m packcli setup` |
| “Is everything ready?” | `python3 -m packcli doctor` |
| “What’s the exact name for raptor?” | `python3 -m packcli resolve raptor` |
| “Make a pack with …” | resolve → recipe → `build` |
| “Switch this VHD to Sound Blaster” | `patch-autoexec … --audio sb` |
| “Only rebuild the VHD” | `rebuild-vhd …` |

No need to re-enter paths if `config.toml` was saved once.

---

## Mental model (one picture)

```text
  YOU (once)                    GROK / packcli (automatic)
  ──────────                    ─────────────────────────
  eXoDOS folder  ─────────────► path saved in config
  dosassets      ─────────────► path saved in config
  “make a pack”  ─────────────► setup (if needed)
                                doctor
                                resolve titles
                                build VHD + cd/
                                tell you the output folder
```

**Open source tools** = fetched and updated for you.  
**Your games and DOS media** = your folders only.

---

## If something fails (agent + you)

| Message-ish problem | What happens next |
|---------------------|-------------------|
| dosforge / converter missing | Agent runs `setup` |
| Collection path wrong | Agent asks again; you paste the correct folder |
| No games matched | Agent runs `resolve` and uses exact titles |
| VHD size / FAT16 error | Agent rebuilds with `boot: auto` or FreeDOS |
| Want SB instead of GUS | Agent runs `patch-autoexec --audio sb` |

You should not need to edit YAML by hand unless you want to.
