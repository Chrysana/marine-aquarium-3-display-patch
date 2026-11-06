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

The PE checksum is recalculated afterwards. In total, 39 bytes of code change (26 + 6 + 1 + 6). Some bytes in site 1 are rewritten with the same value.

## What is *not* changed

- Registration, licensing and trial logic: none of it is touched.
- Saved settings in the registry are left as they are. They're simply not used for the back-buffer size.
- The screensaver's own windowed/app mode (`StartWindowed`) and the preview pane use a
  different code path (`0x40dbe0`) and behave exactly as before.

## Ideas for later

- **DXVK:** rename the `d3d9.dll` import (it's only used for `Direct3DCreate9`) to a bundled
  copy of DXVK under a different name. Installing DXVK as `d3d9.dll` next to a
  screensaver in `SysWOW64` would hijack Direct3D 9 for every 32-bit program on the system.
- **Robustness:** skip `RestoreDeviceObjects` for units whose `Reset` failed (`0x409431`).
- **DPI:** the manifest doesn't declare DPI awareness, and the monitor rectangles come from
  `EnumDisplaySettings` (physical pixels).
