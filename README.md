# Marine Aquarium 3 — Modern Display Patch

An unofficial, community-made patch that lets **your existing copy** of SereneScreen's
*Marine Aquarium 3* screensaver run properly on modern monitors: native resolutions, high
refresh rates (120 / 144 / 240 / 360 Hz…) and multi-monitor setups.

> [!IMPORTANT]
> ## This is NOT a crack, keygen, or free copy
>
> - ❌ This patch **does not unlock** the registered/paid version.
> - ❌ This patch **does not remove** trial limitations, nag screens, or registration checks.
> - ❌ This repository **does not contain or distribute** Marine Aquarium 3, its installer, or any of its files.
> - ✅ It **only** changes how the screensaver sets up the display, in a copy **you already have installed**.
>
> A trial copy stays a trial copy. A registered copy stays registered. If you want the full
> version, **buy it from SereneScreen** — the developers deserve it, and this patch is only
> useful if you have the screensaver in the first place.

This project is not affiliated with, endorsed by, or supported by SereneScreen or Prolific
Publishing, Inc. "Marine Aquarium" and "SereneScreen" are trademarks of their respective
owners. Please don't contact them for support with this patch.

> [!NOTE]
> **Made with AI.** The reverse engineering, patch, scripts and documentation in this
> repository were produced with **Claude** (Anthropic's AI model, via Claude Code), under
> the direction of and tested by the repository owner. See
> [How this was made](#how-this-was-made) for details.

---

## What problem does this fix?

Marine Aquarium 3 takes every monitor into old-style *exclusive fullscreen* and picks its
own display mode. On modern setups that goes wrong:

- **Your monitor gets switched to a lower resolution.** For example, a 2560×1440 monitor
  running at 144 Hz gets forced to 1920×1200. Setting the monitor to 120 Hz "fixes" it.
- **The wrong resolution keeps coming back.** After falling back once, the screensaver
  saves the lower resolution and keeps using it.
- **It can crash on startup** on multi-monitor, high-refresh setups.
- Monitors visibly blank and resync when the screensaver starts and stops.
- **The picture looks zoomed in** on monitors that use Windows display scaling (125%, 150%…).
  The screensaver predates per-monitor scaling, so Windows enlarges it and part of the
  picture ends up off-screen.

**After patching**, the screensaver draws into a borderless window that covers each
monitor exactly. Monitors are never switched out of their desktop mode, so every display
stays at its native resolution and refresh rate. The screensaver is also marked as
per-monitor DPI aware, so scaled monitors show the full picture at full sharpness.
And if one monitor's display device fails anyway, that monitor stays black while the
others keep running, instead of the whole screensaver crashing.

## Requirements

- Windows 10 or 11.
- Marine Aquarium 3 **already installed** (trial or registered). The patch has been tested
  on the build listed under [Compatibility](#compatibility).
- Administrator rights. The screensaver is installed in the Windows folder, so changing it
  needs admin approval.

Nothing else is needed. The patcher is a plain-text PowerShell script that comes with
Windows; there is nothing to install.

## How to use

1. Download the latest release ZIP from the [Releases](../../releases) page and extract it
   anywhere (for example your Downloads folder).
2. Close the screensaver and its settings window if either is open.
3. Double-click **`Install Patch.cmd`** and approve the administrator prompt.
4. You should see `Patched successfully.` That's it. Use the screensaver as normal.

The installer may put copies in both `C:\Windows\System32` and `C:\Windows\SysWOW64`. If so,
the patcher lists and patches each one, and each gets its own backup.

| File | What it does |
|---|---|
| `Install Patch.cmd` | Finds your installed `MarineAquarium3.scr`, backs it up, and patches it. |
| `Restore Original.cmd` | Puts your original, unpatched file back from the backup. |
| `Check Status.cmd` | Shows whether your copy is unpatched, patched, or an unrecognised version. Changes nothing. |
| `Patch-MarineAquarium3.ps1` | The actual patcher. The `.cmd` files just run this. You can open it in Notepad to read exactly what it does. |

**Windows SmartScreen** may warn about running a file downloaded from the internet. That's
expected for any unsigned script. Click *More info → Run anyway*, or right-click the ZIP
before extracting → *Properties* → tick *Unblock*.

**If the screensaver is installed somewhere unusual**, run the script with `-Path`:

```powershell
powershell -ExecutionPolicy Bypass -File .\Patch-MarineAquarium3.ps1 -Path "D:\Somewhere\MarineAquarium3.scr"
```

### Undoing the patch

Double-click **`Restore Original.cmd`**. The original file is kept next to the screensaver
as `MarineAquarium3.scr.bak` until you restore it. Uninstalling Marine Aquarium 3 normally
also removes the patched file.

### Updating from an older version of the patch

Download the new release and double-click **`Install Patch.cmd`** again. It recognises a copy
patched by an older version, applies only what's new, and keeps your original backup.
`Check Status.cmd` shows *"Patched by an older version of this patch"* for such copies.

### Fixing a resolution that was already saved wrong

You don't need to do anything. The patched screensaver always uses each monitor's desktop
resolution and ignores the lower fallback mode that the unpatched version may have saved.

## Safety

The patcher is deliberately conservative:

- It **refuses to touch** any file it doesn't recognise. Every patch location is found by an
  exact byte pattern, and all of them must match exactly once. Any mismatch (an unknown
  version, or a file modified by something else) means nothing is written.
- It **always makes a backup** before changing anything, and checks the result after writing.
- It only changes **107 bytes** of display-setup code, adds a standard DPI-awareness setting
  to the program's manifest (the settings block Windows reads when starting a program), and
  updates the matching size fields and checksum. It does not touch registration, licensing,
  or trial code in any way. See [docs/TECHNICAL.md](docs/TECHNICAL.md) for every change and why.
- Running it twice is harmless; it reports *Already patched*.

## Compatibility

| Build | SHA-256 of `MarineAquarium3.scr` | Status |
|---|---|---|
| 3.3, file dated 2020-10-13 — **trial and registered** | `26d4bad747d764fdcc340cf84b0230e857c800606f14e6911c4e4dcd0b5aed9e` | ✅ Tested (patch + installer) |

The trial and registered versions use the **same, byte-identical** `MarineAquarium3.scr`.
Registration is stored separately in your Windows user settings, not in the file, so
patching neither needs nor affects it. Other builds haven't been seen yet; the patcher
will tell you if yours is unrecognised.

Tested on Windows 11 with an AMD Radeon RX 9070 XT and three monitors: 3440×1440 @ 120 Hz,
2560×1440 @ 144 Hz and 2560×1440 @ 360 Hz, including one monitor at 175% display scaling
alongside monitors at 100%.

If `Check Status.cmd` says your build is **Unknown**, please
[open an issue](../../issues) with the SHA-256 of your file. Get it with
`Get-FileHash C:\Windows\SysWOW64\MarineAquarium3.scr`. **Please don't upload the file itself.**

## Known limitations

- **Keep the file name `MarineAquarium3.scr`.** The screensaver itself behaves differently
  when its file is renamed: the background is missing and moving fish leave trails. The
  same patched file works correctly under its original name, so this comes from the
  original program, not from the patch's changes. The patcher always patches the file in
  place, so this only matters if you copy or rename it yourself.
- The screensaver's **settings dialog** hasn't been checked on scaled monitors. It may look
  small or slightly off there. Reports welcome.
- Frames are presented through the Windows desktop compositor (like any borderless game).
  This is normally smooth; if you notice stutter, please open an issue.

## Roadmap

- **Optional Vulkan renderer via [DXVK](https://github.com/doitsujin/dxvk)**, for modern
  presentation and frame pacing, without replacing the system's `d3d9.dll`.

## For developers

- [`patch/Patch-MarineAquarium3.ps1`](patch/Patch-MarineAquarium3.ps1) — the user-facing
  patcher (Windows PowerShell 5.1+, patch engine in embedded C#).
- [`tools/ma3patch.py`](tools/ma3patch.py) — reference implementation in Python
  (`pip install pefile`). It produces byte-identical output and is handy for `--check`ing new builds.
- [`tools/diagnostics/`](tools/diagnostics) — scripts that reproduce the screensaver's display
  mode enumeration and test windowed D3D9 device creation on each monitor.
- [`docs/TECHNICAL.md`](docs/TECHNICAL.md) — root-cause analysis and a description of every patch site.

## How this was made

This project was built with **Claude Opus 5.5**, Anthropic's AI model, working in Claude
Code. The repository owner directed the work, decided its scope, and ran every test on real
hardware. The AI did the technical work:

- **Analysis:** disassembled the screensaver from the owner's own installed copy, identified
  the display-setup code, and read a crash dump to find the root cause. The full write-up is
  in [docs/TECHNICAL.md](docs/TECHNICAL.md).
- **Code:** wrote the patch, the PowerShell patcher and its launchers, the Python reference
  implementation, and the diagnostic scripts.
- **Docs:** wrote this README and the technical notes.

The scope was deliberately limited to fixing display behaviour. The analysis never targeted
registration, licensing or trial code, and the patch doesn't change them. No part of the
original program is included in this repository. The patcher only contains short byte
patterns it uses to find the code it changes.

The patcher is a plain-text script so that anyone can review exactly what it does before
running it. Corrections and reviews are welcome via issues and pull requests.

## License

The patcher and documentation in this repository are released under the [MIT License](LICENSE).
This license covers **only** the files in this repository. Marine Aquarium 3 itself is
proprietary software owned by its publisher and is not included here.
