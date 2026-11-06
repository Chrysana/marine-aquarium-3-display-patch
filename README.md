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

**After patching**, the screensaver draws into a borderless window that covers each
monitor. Monitors are never switched out of their desktop mode, so every display stays at
its native resolution and refresh rate.

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

### Fixing a resolution that was already saved wrong

You don't need to do anything. The patched screensaver always uses each monitor's desktop
resolution and ignores the lower fallback mode that the unpatched version may have saved.

## Safety

The patcher is deliberately conservative:

- It **refuses to touch** any file it doesn't recognise. Every patch location is found by an
  exact byte pattern, and all of them must match exactly once. Any mismatch (an unknown
  version, or an already-modified file) means nothing is written.
- It **always makes a backup** before changing anything, and checks the result after writing.
- It only changes **39 bytes** of display-setup code (plus the file's checksum field). It does not
  touch registration, licensing, or trial code in any way. See
  [docs/TECHNICAL.md](docs/TECHNICAL.md) for every byte that changes and why.
- Running it twice is harmless; it reports *Already patched*.

## Compatibility

| Build | SHA-256 of `MarineAquarium3.scr` | Status |
|---|---|---|
| 3.3 trial, file dated 2020-10-13 | `26d4bad747d764fdcc340cf84b0230e857c800606f14e6911c4e4dcd0b5aed9e` | ✅ Tested |
| 3.3 registered | — | Not yet tested. The patcher will tell you if it's unrecognised. |

Tested on Windows 11 with an AMD Radeon RX 9070 XT and three monitors: 3440×1440 @ 120 Hz,
2560×1440 @ 144 Hz and 2560×1440 @ 360 Hz.

If `Check Status.cmd` says your build is **Unknown**, please
[open an issue](../../issues) with the SHA-256 of your file. Get it with
`Get-FileHash C:\Windows\SysWOW64\MarineAquarium3.scr`. **Please don't upload the file itself.**

## Known limitations

- **Display scaling above 100%** hasn't been tested. The screensaver isn't DPI-aware, so on a
  scaled monitor the image may not fill the screen exactly. Reports welcome.
- Frames are presented through the Windows desktop compositor (like any borderless game).
  This is normally smooth; if you notice stutter, please open an issue.

## Roadmap

- **Optional Vulkan renderer via [DXVK](https://github.com/doitsujin/dxvk)**, for modern
  presentation and frame pacing, without replacing the system's `d3d9.dll`.
- Guard against a device failing on one monitor taking down the whole screensaver.
- DPI-awareness for scaled displays.

## For developers

- [`patch/Patch-MarineAquarium3.ps1`](patch/Patch-MarineAquarium3.ps1) — the user-facing
  patcher (Windows PowerShell 5.1+, patch engine in embedded C#).
- [`tools/ma3patch.py`](tools/ma3patch.py) — reference implementation in Python
  (`pip install pefile`). It produces byte-identical output and is handy for `--check`ing new builds.
- [`tools/diagnostics/`](tools/diagnostics) — scripts that reproduce the screensaver's display
  mode enumeration and test windowed D3D9 device creation on each monitor.
- [`docs/TECHNICAL.md`](docs/TECHNICAL.md) — root-cause analysis and a description of every patch site.

## License

The patcher and documentation in this repository are released under the [MIT License](LICENSE).
This license covers **only** the files in this repository. Marine Aquarium 3 itself is
proprietary software owned by its publisher and is not included here.
