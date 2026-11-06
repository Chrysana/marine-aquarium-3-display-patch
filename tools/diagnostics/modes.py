"""Replicates MarineAquarium3.scr's BuildDeviceList mode collection (0x409de0..0x409f02)
against the live D3D9 runtime, to see whether the 99-mode cap truncates the native mode."""
import ctypes as C
from ctypes import wintypes as W

d3d9 = C.WinDLL('d3d9')
d3d9.Direct3DCreate9.restype = C.c_void_p
d3d9.Direct3DCreate9.argtypes = [C.c_uint]

class MODE(C.Structure):
    _fields_ = [('Width', C.c_uint), ('Height', C.c_uint), ('RefreshRate', C.c_uint), ('Format', C.c_uint)]

class IDENT(C.Structure):
    _fields_ = [('Driver', C.c_char * 512), ('Description', C.c_char * 512), ('DeviceName', C.c_char * 32),
                ('rest', C.c_byte * 2048)]

p = d3d9.Direct3DCreate9(32)  # D3D_SDK_VERSION
vt = C.cast(C.cast(p, C.POINTER(C.c_void_p))[0], C.POINTER(C.c_void_p))
def m(idx, res, *args): return C.WINFUNCTYPE(res, C.c_void_p, *args)(vt[idx])
GetAdapterCount = m(4, C.c_uint)
GetAdapterIdentifier = m(5, C.c_long, C.c_uint, C.c_uint, C.POINTER(IDENT))
GetAdapterModeCount = m(6, C.c_uint, C.c_uint, C.c_uint)
EnumAdapterModes = m(7, C.c_long, C.c_uint, C.c_uint, C.c_uint, C.POINTER(MODE))
GetAdapterDisplayMode = m(8, C.c_long, C.c_uint, C.POINTER(MODE))

for a in range(GetAdapterCount(p)):
    ident = IDENT(); GetAdapterIdentifier(p, a, 0, C.byref(ident))
    cur = MODE(); GetAdapterDisplayMode(p, a, C.byref(cur))
    print(f"\n=== Adapter {a} {ident.DeviceName.decode()}  desktop {cur.Width}x{cur.Height}@{cur.RefreshRate}Hz fmt={cur.Format}")
    kept, dropped, raw = [], [], 0
    for fmt in (0x16, 0x18, 0x17):          # X8R8G8B8, X1R5G5B5, R5G6B5 -- same order as the .scr
        n = GetAdapterModeCount(p, a, fmt); raw += n
        for i in range(n):
            md = MODE(); EnumAdapterModes(p, a, fmt, i, C.byref(md))
            if md.Width < 640 or md.Height < 400: continue
            key = (md.Width, md.Height, md.Format)
            if key in kept or key in dropped: continue
            (kept if len(kept) < 99 else dropped).append(key)
    has_native = (cur.Width, cur.Height, 0x16) in kept
    print(f"raw modes={raw}  unique={len(kept)+len(dropped)}  kept={len(kept)}  dropped={len(dropped)}")
    print(f"native {cur.Width}x{cur.Height} X8R8G8B8 survives cap: {has_native}")
    if dropped: print("first dropped:", dropped[:8], "...")
    print("largest kept 32bpp:", sorted([k for k in kept if k[2] == 0x16])[-4:])
