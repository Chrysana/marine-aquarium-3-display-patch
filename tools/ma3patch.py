"""
Marine Aquarium 3 modernization patcher.

Patches a user's own copy of MarineAquarium3.scr. The input file is never modified;
a patched copy is written to the output path.

Patches
-------
borderless : Run every monitor's D3D9 device *windowed* (on the existing topmost,
             monitor-sized popup windows) instead of exclusive fullscreen, both
             when devices are created and whenever they are Reset. No display
             mode change ever happens, so monitors keep their native resolution
             and refresh rate.

Background: the screensaver is built on the DirectX SDK "D3DSaver" framework.
 * CreateFullscreenRenderUnit: if exclusive-mode CreateDevice fails it steps down
   to the next lower mode, retries, and saves the fallback mode to the registry.
 * Right after creation (and after any device loss) the framework rebuilds every
   unit's present parameters as exclusive fullscreen at the desktop resolution
   *and desktop refresh rate*, then Resets all devices. Some modes (e.g.
   2560x1440@144 on an AMD RX 9070 XT) reject exclusive fullscreen with
   D3DERR_INVALIDCALL; the framework then marks the unit failed but still calls
   RestoreDeviceObjects on it, which crashes on unloaded fish models.

Patch sites are located by byte signature (with wildcards) so the patcher can
work on different builds (trial / registered). Each signature must match
exactly once or the patcher refuses to continue.
"""
import argparse
import hashlib
import sys
from pathlib import Path


def sig(pattern: str):
    """'8b 4c 24 ?? 33 d2' -> list of int|None"""
    return [None if t == '??' else int(t, 16) for t in pattern.split()]


def find_all(data: bytes, pattern):
    first = next(i for i, b in enumerate(pattern) if b is not None)
    anchor = bytes([pattern[first]])
    hits, pos, n = [], 0, len(pattern)
    while True:
        pos = data.find(anchor, pos)
        if pos < 0:
            break
        start = pos - first
        if start >= 0 and start + n <= len(data) and all(
                p is None or data[start + i] == p for i, p in enumerate(pattern)):
            hits.append(start)
        pos += 1
    return hits


class Site:
    """One patch location: a signature and a function mapping the matched bytes to new bytes."""
    def __init__(self, label, pattern, build):
        self.label, self.pattern, self.build = label, sig(pattern), build


class Patch:
    def __init__(self, name, desc, sites):
        self.name, self.desc, self.sites = name, desc, sites


def splice(orig: bytes, at: int, new: bytes) -> bytes:
    return orig[:at] + new + orig[at + len(new):]


# --- borderless: site 1 — CreateFullscreenRenderUnit present params --------------
# Original (trial build @ VA 0x409862):
#   8b 4c 24 ??        mov  ecx, [esp+??]          ; this
#   33 d2              xor  edx, edx
#   89 56 38           mov  [esi+38h], edx         ; d3dpp.Windowed = FALSE
#   89 56 48           mov  [esi+48h], edx         ; d3dpp.FullScreen_RefreshRateInHz = 0
#   8b 81 ?? ?? ?? ??  mov  eax, [ecx+swapEffOfs]
#   89 46 30           mov  [esi+30h], eax         ; d3dpp.SwapEffect
#   8b 45 00           mov  eax, [ebp+0]
#   89 03              mov  [ebx], eax             ; d3dpp.BackBufferWidth  = mode.Width
#   8b 45 04           mov  eax, [ebp+4]
#   89 46 1c           mov  [esi+1Ch], eax         ; d3dpp.BackBufferHeight = mode.Height
#   8b 87 ?? ?? ?? ??  mov  eax, [edi+curModeOfs]  ; (context, not modified)
def build_create(orig: bytes) -> bytes:
    new = orig[0:4] + bytes.fromhex(
        "33 d2"            # xor  edx, edx
        "42"               # inc  edx              ; edx = 1
        "89 56 38"         # mov  [esi+38h], edx   ; Windowed = TRUE
        "4a"               # dec  edx              ; edx = 0
        "89 56 48"         # mov  [esi+48h], edx   ; RefreshRate = 0 (required when windowed)
    ) + orig[12:21] + bytes.fromhex(  # mov eax,[ecx+swapEffOfs] / mov [esi+30h],eax (unchanged)
        "89 13"            # mov  [ebx], edx       ; BackBufferWidth  = 0 -> client rect
        "89 56 1c")        # mov  [esi+1Ch], edx   ; BackBufferHeight = 0 -> client rect
    # bytes 0..31 rewritten; edx must be 0 on exit (next code stores it as MultiSampleType)
    new += b"\x90" * (32 - len(new))
    return new + orig[32:]


# --- borderless: site 2 — rebuild-present-params (virtual, called before every Reset) ---
# Trial build @ VA 0x40d964:
#   8b 97 ?? ?? ?? ??  mov  edx, [edi+m_bWindowed]
#   89 56 34           mov  [esi+34h], edx         ; d3dpp.Windowed = m_bWindowed (0 in /s mode)
#   ba 01 00 00 00     mov  edx, 1
#   89 56 20 89 6e 24 89 6e 28 89 56 2c            ; (context)
# -> xor edx,edx / inc edx / nop*3   so Windowed = TRUE, edx is reloaded with 1 right after.
def build_rebuild_windowed(orig: bytes) -> bytes:
    return splice(orig, 0, bytes.fromhex("33 d2 42 90 90 90"))


# Trial build @ VA 0x40da87 (fullscreen branch of the same function):
#   8b 88 ?? ?? ?? ??  mov  ecx, [eax+savedWidth]
#   3b cd              cmp  ecx, ebp
#   74 ??              je   use_desktop_mode       ; if no saved mode, use desktop mode
#   89 4e 14 8b 90 ?? ?? ?? ?? 89 56 18            ; (else use saved W/H/format)
# -> je -> jmp: always size the back buffer to the monitor's desktop mode.
def build_rebuild_desktop_size(orig: bytes) -> bytes:
    return splice(orig, 8, b"\xeb")


# Trial build @ VA 0x40dad9:
#   89 4e 48           mov  [esi+48h], ecx         ; PresentationInterval (context)
#   8b 90 ?? ?? ?? ??  mov  edx, [eax+desktopRefresh]
#   8b 46 1c           mov  eax, [esi+1Ch]
#   89 56 44           mov  [esi+44h], edx         ; d3dpp.FullScreen_RefreshRateInHz
#   83 f8 18                                       ; (context)
# -> xor edx,edx / nop*4   so RefreshRate = 0 (mandatory for windowed Reset).
def build_rebuild_refresh(orig: bytes) -> bytes:
    return splice(orig, 3, bytes.fromhex("33 d2 90 90 90 90"))


# --- dpi: per-monitor DPI awareness via the application manifest -----------------------
# RT_MANIFEST #1 is the last blob in .rsrc and is followed by linker padding, so the
# extended manifest is written in place; the resource data entry size, .rsrc VirtualSize
# and DataDirectory[RESOURCE].Size are updated. Mirrors ManifestSite in the .ps1.
ORIG_MANIFEST = (
    b'<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">'
    b'<assemblyIdentity version="1.0.0.0" processorArchitecture="X86" name="MarineAquarium3" type="win32"></assemblyIdentity>'
    b'<description>SereneScreen Marine Aquarium Version 3</description>'
    b'<dependency><dependentAssembly><assemblyIdentity type="win32" name="Microsoft.Windows.Common-Controls" version="6.0.0.0" processorArchitecture="X86" publicKeyToken="6595b64144ccf1df" language="*"></assemblyIdentity></dependentAssembly></dependency>'
    b'<trustInfo xmlns="urn:schemas-microsoft-com:asm.v3"><security><requestedPrivileges><requestedExecutionLevel level="asInvoker" uiAccess="false"></requestedExecutionLevel></requestedPrivileges></security></trustInfo>'
    b'</assembly>')
DPI_BLOCK = (
    b'<application xmlns="urn:schemas-microsoft-com:asm.v3"><windowsSettings>'
    b'<dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings">true/pm</dpiAware>'
    b'<dpiAwareness xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings">PerMonitorV2, PerMonitor</dpiAwareness>'
    b'</windowsSettings></application>')
NEW_MANIFEST = ORIG_MANIFEST.replace(b'</assembly>', DPI_BLOCK + b'</assembly>')


def apply_manifest(data: bytearray):
    import struct
    if data.count(ORIG_MANIFEST) != 1:
        sys.exit("error: dpi: original manifest not found exactly once")
    off = data.find(ORIG_MANIFEST)
    lfanew = struct.unpack_from('<I', data, 0x3c)[0]
    nsec, = struct.unpack_from('<H', data, lfanew + 6)
    optsize, = struct.unpack_from('<H', data, lfanew + 20)
    for i in range(nsec):
        h = lfanew + 24 + optsize + i * 40
        vsize, va, rawsize, raw = struct.unpack_from('<4I', data, h + 8)
        if raw <= off < raw + rawsize:
            break
    else:
        sys.exit("error: dpi: manifest not inside a section")
    rva = off - raw + va
    entry = struct.pack('<II', rva, len(ORIG_MANIFEST))
    if data.count(entry) != 1:
        sys.exit("error: dpi: resource data entry not found exactly once")
    entry_off = data.find(entry)
    end = off + len(NEW_MANIFEST)
    if end > raw + rawsize:
        sys.exit("error: dpi: no room for the extended manifest")
    if any(b not in b'PADDINGX\0' for b in data[off + len(ORIG_MANIFEST):end]):
        sys.exit("error: dpi: unexpected data after the manifest")
    data[off:end] = NEW_MANIFEST
    struct.pack_into('<I', data, entry_off + 4, len(NEW_MANIFEST))
    new_vsize = (off - raw) + len(NEW_MANIFEST)
    if new_vsize > vsize:
        struct.pack_into('<I', data, h + 8, new_vsize)
        dd = lfanew + 24 + 96 + 2 * 8
        if struct.unpack_from('<II', data, dd) == (va, vsize):
            struct.pack_into('<I', data, dd + 4, new_vsize)
    return off


# --- robust: site 6 — the framework's "skip this monitor?" check (0x4066f0) ----------
# Original: skip if no device; in windowed (app) mode skip unless it's the main window;
# otherwise skip if not valid or "Leave Black". Rewritten in its own 80 bytes with one
# extra check first: skip if the unit is marked failed (+0E0h).
ISSKIPPED_ORIG = (
    "8b 54 24 04 83 7a 14 00 75 08 b8 01 00 00 00 c2 04 00 8b 81 ac d4 00 00 85 c0 74 1d "
    "56 8b 32 8b b4 b1 38 f8 00 00 8b b6 b0 2b 00 00 3b b1 a8 d7 00 00 5e 75 d5 85 c0 75 0f "
    "83 7a 04 00 74 cb 83 ba dc 00 00 00 00 75 c2 33 c0 c2 04 00 cc cc cc")
ISSKIPPED_NEW = (
    "8b 54 24 04"            # mov edx,[esp+4]            ; RenderUnit*
    " 83 7a 14 00 74 3f"     # cmp [edx+14h],0 / je ret1  ; no device
    " 83 ba e0 00 00 00 00 75 36"  # cmp [edx+0E0h],0 / jne ret1 ; NEW: failed
    " 83 b9 ac d4 00 00 00 74 19"  # cmp [ecx+0D4ACh],0 / je fs   ; windowed app mode?
    " 8b 02 8b 84 81 38 f8 00 00 8b 80 b0 2b 00 00"  # hwnd of this unit's adapter
    " 3b 81 a8 d7 00 00 75 16 eb 0f"  # not main window -> ret1, else ret0
    " 83 7a 04 00 74 0e"     # fs: cmp [edx+4],0 / je ret1
    " 83 ba dc 00 00 00 00 75 05"  # cmp [edx+0DCh],0 / jne ret1 ; leave black
    " 33 c0 c2 04 00"        # ret0: xor eax,eax / ret 4
    " 33 c0 40 c2 04 00 cc") # ret1: eax=1 / ret 4 / pad


PATCHES = {
    "borderless": Patch(
        "borderless",
        "Windowed (borderless) D3D9 devices instead of exclusive fullscreen",
        [
            Site("create: windowed, refresh 0, back buffer = window",
                 "8b 4c 24 ?? 33 d2 89 56 38 89 56 48 8b 81 ?? ?? ?? ?? 89 46 30 "
                 "8b 45 00 89 03 8b 45 04 89 46 1c 8b 87 ?? ?? ?? ??",
                 build_create),
            Site("reset: windowed",
                 "8b 97 ?? ?? ?? ?? 89 56 34 ba 01 00 00 00 89 56 20 89 6e 24 89 6e 28 89 56 2c",
                 build_rebuild_windowed),
            Site("reset: back buffer = desktop size",
                 "8b 88 ?? ?? ?? ?? 3b cd 74 ?? 89 4e 14 8b 90 ?? ?? ?? ?? 89 56 18",
                 build_rebuild_desktop_size),
            Site("reset: refresh 0",
                 "89 4e 48 8b 90 ?? ?? ?? ?? 8b 46 1c 89 56 44 83 f8 18",
                 build_rebuild_refresh),
        ]),
    # Safety net (v1.2.0): a monitor whose device fails stays black instead of crashing
    # the screensaver or looping device resets. Mirrors sites 6 and 7 in the .ps1.
    "robust": Patch(
        "robust",
        "Safety net: isolate a monitor whose display device fails",
        [
            Site("safety: skip monitors whose device failed",
                 ISSKIPPED_ORIG, lambda o: bytes.fromhex(ISSKIPPED_NEW)),
            Site("safety: forget a device whose reset failed",
                 "6a 00 55 e8 ?? ?? ?? ?? 6a 00 55 e8 ?? ?? ?? ?? 83 c4 10 "
                 "c7 87 90 00 00 00 01 00 00 00 89 af 94 00 00 00",
                 lambda o: splice(o, 19, bytes.fromhex("ff 87 90 00 00 00 83 67 c4 00"))),
        ]),
}


def fix_checksum(path: Path):
    try:
        import pefile
    except ImportError:
        return
    pe = pefile.PE(str(path))
    pe.OPTIONAL_HEADER.CheckSum = pe.generate_checksum()
    data = pe.write()
    pe.close()
    path.write_bytes(data)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path, help="original MarineAquarium3.scr")
    ap.add_argument("output", type=Path, nargs="?", help="where to write the patched copy")
    ap.add_argument("--patch", action="append", choices=sorted(PATCHES) + ["dpi"], default=None,
                    help="patch(es) to apply (default: all)")
    ap.add_argument("--check", action="store_true", help="only report whether patch sites are found")
    args = ap.parse_args()
    if not args.check and args.output is None:
        ap.error("output path is required unless --check is given")

    data = bytearray(args.input.read_bytes())
    if data[:2] != b"MZ" or b"SereneScreen Marine Aquarium" not in data:
        sys.exit("error: input does not look like MarineAquarium3.scr")
    print(f"input : {args.input}  sha256={hashlib.sha256(data).hexdigest()[:16]}...")

    plan = []
    for name in [n for n in (args.patch or list(PATCHES)) if n in PATCHES]:
        p = PATCHES[name]
        print(f"[{name}] {p.desc}")
        for s in p.sites:
            hits = find_all(data, s.pattern)
            if len(hits) != 1:
                sys.exit(f"error: {name} / '{s.label}': expected 1 signature match, found {len(hits)} "
                         f"(unsupported build or already patched)")
            off = hits[0]
            orig = bytes(data[off:off + len(s.pattern)])
            new = s.build(orig)
            assert len(new) == len(orig)
            plan.append((off, new))
            print(f"    0x{off:06x}  {s.label}")

    if args.check:
        return
    if args.output.resolve() == args.input.resolve():
        sys.exit("error: refusing to overwrite the input file; choose a different output path")

    for off, new in plan:
        data[off:off + len(new)] = new
    if args.patch is None or "dpi" in args.patch:
        print(f"[dpi] Per-monitor DPI awareness (manifest)")
        print(f"    0x{apply_manifest(data):06x}  manifest: per-monitor DPI aware")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    fix_checksum(args.output)
    print(f"output: {args.output}  sha256={hashlib.sha256(args.output.read_bytes()).hexdigest()[:16]}...")


if __name__ == "__main__":
    main()
