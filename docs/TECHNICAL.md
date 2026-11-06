# Technical notes

How the multi-monitor / high-refresh problem works inside Marine Aquarium 3, and exactly what
the patch changes. Addresses refer to the tested 3.3 trial build (SHA-256 `26d4bad7…aed9e`,
image base `0x400000`). The patcher finds each site by byte signature, not by address.

## Background

`MarineAquarium3.scr` is a 32-bit Direct3D 9 program built on the DirectX SDK's
**D3DSaver** sample framework (`d3dsaver.cpp`). D3DX9 is statically linked, and `d3d9.dll`
is imported normally (only `Direct3DCreate9`). The framework creates one *render unit* per
monitor. Each unit has its own `IDirect3DDevice9`, on a topmost `WS_POPUP` window that
already covers that monitor exactly.

## Root cause

There are two separate problems, and both come from always using exclusive fullscreen.

### 1. Mode fallback is saved permanently (`CreateFullscreenRenderUnit`, ~`0x409680`)

The present parameters are filled with `Windowed = FALSE`, `FullScreen_RefreshRateInHz = 0`
and the selected mode. If `CreateDevice` fails, the framework calls a "next lower mode"
helper (`0x405c80`) and retries. When a retry succeeds after a fallback, it **writes the
fallback mode to** `HKCU\Software\SereneScreen\MarineAquarium3\Screen N` (`Width`/`Height`/`Format`).

On the test system, exclusive fullscreen at 2560×1440 fails on a 144 Hz monitor (the driver
returns `D3DERR_INVALIDCALL`), even though D3D9 lists 2560×1440@144 as a supported mode.
The screensaver falls back to the next mode in its sorted list (1920×1200) and saves it, so
that resolution sticks from then on.

### 2. Every device Reset forces exclusive fullscreen again (`0x40d8d0`)

Right after the devices are created, and again after any device loss, `ResetAll`
(`0x4091a0`) calls a virtual method (vtable slot `+0x1c`, `0x40d8d0`). That method
**rebuilds every unit's present parameters** with `Windowed = m_bWindowed` (0 in screensaver
mode), the saved or desktop resolution, and the **desktop refresh rate**. It then calls
`IDirect3DDevice9::Reset`.

If that `Reset` fails, the unit is marked failed (`+0xe0 = 1`, HRESULT at `+0xe4`), but
`RestoreDeviceObjects` is still called for it. Fish models were never loaded for that unit,
so a frame lookup (`lstrcmpiA(…, "Wholefish")`, via `0x41e450`) reads a null pointer and
the process crashes in `KERNELBASE.dll`.

## The patch (`borderless`)

All four edits keep the same instruction length, so nothing jumps into the middle of a
rewritten instruction. The only jump into the first site lands on its unchanged first
instruction (the framework's retry loop).

### Site 1: device creation (`0x409862`, 32 bytes)

```
before                                   after
mov  ecx,[esp+10h]                       mov  ecx,[esp+10h]
xor  edx,edx                             xor  edx,edx
mov  [esi+38h],edx   ; Windowed=0        inc  edx
mov  [esi+48h],edx   ; Refresh=0         mov  [esi+38h],edx   ; Windowed=1
mov  eax,[ecx+0F9B0h]                    dec  edx
mov  [esi+30h],eax   ; SwapEffect        mov  [esi+48h],edx   ; Refresh=0
mov  eax,[ebp+0]                         mov  eax,[ecx+0F9B0h]
mov  [ebx],eax       ; BackBufferWidth   mov  [esi+30h],eax   ; SwapEffect
mov  eax,[ebp+4]                         mov  [ebx],edx       ; BackBufferWidth=0
mov  [esi+1Ch],eax   ; BackBufferHeight  mov  [esi+1Ch],edx   ; BackBufferHeight=0
                                         nop ×4
```

A zero back-buffer size makes D3D9 use the client area of the device window, which is the
whole monitor. D3D9 then writes the real size back into the structure. `edx` is 0 on exit,
as the code that follows expects (it stores `edx` as `MultiSampleType`).

### Site 2: Reset rebuild, windowed (`0x40d964`, 6 bytes)

`mov edx,[edi+m_bWindowed]` → `xor edx,edx / inc edx / nop×3`, so `Windowed = TRUE`. The
framework flag itself is unchanged, so the per-monitor ("fullscreen") branch still runs,
rather than the single-window branch used by the screensaver's own windowed mode.

### Site 3: Reset rebuild, desktop size (`0x40da8f`, 1 byte)

`je use_desktop_mode` → `jmp`. The back buffer always matches the monitor's desktop
resolution, never a previously saved fallback mode.

### Site 4: Reset rebuild, refresh 0 (`0x40dadc`, 6 bytes)

`mov edx,[eax+desktopRefresh]` → `xor edx,edx / nop×4`. A windowed `Reset` requires
`FullScreen_RefreshRateInHz = 0`.

In total, 39 bytes of code change (26 + 6 + 1 + 6). Some bytes in site 1 are rewritten with the same value.

## The patch (`dpi`) — added in v1.1.0

### Problem

The original manifest declares no DPI awareness. On a monitor with Windows display
scaling (for example 150%), Windows virtualises coordinates for the process and
bitmap-stretches its windows. The monitor rectangles the framework builds come from
`EnumDisplaySettings` (`dmPosition` / `dmPelsWidth`), so its popup window comes out
oversized and only part of the rendered view is visible. The picture looks zoomed in.

### Site 5: application manifest (`RT_MANIFEST` #1)

The manifest gets a standard `<application><windowsSettings>` block with
`<dpiAware>true/pm</dpiAware>` and `<dpiAwareness>PerMonitorV2, PerMonitor</dpiAwareness>`.
The process then runs per-monitor DPI aware. All window, monitor and back-buffer sizes are
physical pixels, which is what the framework already assumes.

The manifest (730 bytes) is the last item in `.rsrc`. It's followed by 436 bytes of linker
padding (`PADDINGXXPADDING…`) inside the section's raw data, so the extended manifest
(1038 bytes) is written **in place**, and nothing else in the file moves. The patcher:

1. finds the exact original manifest text (it must occur once) and its
   `IMAGE_RESOURCE_DATA_ENTRY` (RVA and size must occur once);
2. checks that the bytes it overwrites past the old manifest are only linker padding, and
   that the new manifest fits inside the section's raw data;
3. writes the new manifest and updates the data entry's size, `.rsrc` `VirtualSize` and
   `DataDirectory[RESOURCE].Size` (0x5fb44c → 0x5fb57e). `SizeOfImage` already covers it.

The PE checksum is recalculated afterwards.

Measured with `GetProcessDpiAwareness` on the settings dialog process: the original build
starts **UNAWARE**, and the patched build starts **PER_MONITOR_AWARE**.

## The patch (`robust`) — added in v1.2.0

A safety net. With the borderless patch, device creation and reset should not fail, but if
one monitor's device does fail, only that monitor should go black.

### What the original framework does with a failed monitor

Each render unit has a *failed* flag (`+0xE0`). It is set in exactly four places, all
failure handlers: `CreateDevice` failed (`0x411118`), `Reset` failed (`0x409282`),
`InitDeviceObjects` failed (`0x409453`) and `RestoreDeviceObjects` failed (`0x40947c`).
Rendering (`0x40a83d`, `0x420bbf`) already skips failed units, but two paths do not:

- **Per-unit setup** in `ResetAll` still calls `InitDeviceObjects` / `RestoreDeviceObjects`
  on a failed unit whose scene was never loaded, which crashes (null fish model, see above).
- **The per-frame device health check** (`0x40a651`) calls `TestCooperativeLevel` on every
  unit. A failed unit keeps answering `D3DERR_DEVICENOTRESET`, so `ResetAll` runs every
  frame. That retries the failed unit and resets all the others too. Result: about 1 FPS
  with a black flash per frame.

### Site 6: "skip this monitor?" (`0x4066f0`, 80 bytes)

The framework's central check, used by 13 callers (setup, the health check, render and
present loops, and others), skips units with no device, units that aren't the main window
in windowed app mode, and units set to "Leave Black". It is rewritten within its own
80 bytes with the same logic plus one extra test first: **skip units marked failed**. It no
longer needs to save `esi`; it still only clobbers `eax`/`edx`. With the flag at 0 it
behaves identically to the original. 64 bytes differ.

### Site 7: forget a device whose `Reset` failed (`0x409282`, 4 bytes differ)

`mov dword [edi+90h],1` (10 bytes) becomes `inc dword [edi+90h]` (6 bytes), which sets the
same flag (every reader only tests it for zero). The 4 freed bytes hold
`and dword [edi-3Ch],0`, which clears the unit's device pointer. The failed monitor is then
handled exactly like one whose device was never created, a state the framework already
supports everywhere, and `ResetAll` no longer retries it. The error code is still stored.

### How it was tested

- **Real failure, exclusive mode:** a test build with only site 1 (devices created windowed,
  reset path still exclusive) reproduces the original crash on a 144 Hz monitor whose
  exclusive `Reset` fails. With sites 6 + 7 added, it no longer crashes or loops.
- **Injected failure, shipping configuration:** the full patch plus a test-only stub that
  forces `D3DERR_INVALIDCALL` from one unit's `Reset`. The two other monitors render
  normally, and the failed one stays black. Unit state was read from the running process
  (failed flag set, device cleared, main unit unchanged), and screenshots confirmed it.
- **No change in normal operation:** with nothing failing, unit state and screenshots match v1.1.

### Side finding: the file name matters

Renamed copies of the screensaver render without the background, so moving objects leave
trails. This was confirmed with both v1.1 and v1.2 builds, and the same bytes render
correctly under the original name. This is the original program's behavior and was not investigated further: it
sits close to the program's identity and licensing code, which this project doesn't touch.

## Upgrading copies patched by an older version

Each site reports *Original*, *Patched* or *Missing*. If every site is Original or Patched
(some of each), the file is *Partial*, meaning it was patched by an older version. The
patcher applies only the Original sites and keeps the existing `.bak` (which must be an
unpatched original). The result is byte-identical to patching an original file.

## What is *not* changed

- Registration, licensing and trial logic: none of it is touched.
- Saved settings in the registry are left as they are. They're simply not used for the back-buffer size.
- The screensaver's own windowed/app mode (`StartWindowed`) and the preview pane use a
  different code path (`0x40dbe0`) and behave as before. Site 6's extra check applies
  there too, but only matters for a unit whose device has failed.

## Ideas for later

- **DXVK:** rename the `d3d9.dll` import (it's only used for `Direct3DCreate9`) to a bundled
  copy of DXVK under a different name. Installing DXVK as `d3d9.dll` next to a
  screensaver in `SysWOW64` would hijack Direct3D 9 for every 32-bit program on the system.
