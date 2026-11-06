"""Try windowed D3D9 CreateDevice on every adapter (individually, then all at once), the way the
patched screensaver does: back buffer 0x0 (client rect), X8R8G8B8, D24S8/D16 depth, HW then SW VP."""
import ctypes as C
from ctypes import wintypes as W

u32 = C.WinDLL('user32', use_last_error=True)
u32.CreateWindowExW.restype = W.HWND
u32.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, C.c_int, C.c_int, C.c_int, C.c_int,
                                W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID]
d3d9 = C.WinDLL('d3d9')
d3d9.Direct3DCreate9.restype = C.c_void_p

class MODE(C.Structure):
    _fields_ = [('Width', C.c_uint), ('Height', C.c_uint), ('RefreshRate', C.c_uint), ('Format', C.c_uint)]

class PP(C.Structure):
    _fields_ = [('BackBufferWidth', C.c_uint), ('BackBufferHeight', C.c_uint), ('BackBufferFormat', C.c_uint),
                ('BackBufferCount', C.c_uint), ('MultiSampleType', C.c_uint), ('MultiSampleQuality', C.c_uint),
                ('SwapEffect', C.c_uint), ('hDeviceWindow', W.HWND), ('Windowed', C.c_int),
                ('EnableAutoDepthStencil', C.c_int), ('AutoDepthStencilFormat', C.c_uint), ('Flags', C.c_uint),
                ('FullScreen_RefreshRateInHz', C.c_uint), ('PresentationInterval', C.c_uint)]

p = d3d9.Direct3DCreate9(32)
vt = C.cast(C.cast(p, C.POINTER(C.c_void_p))[0], C.POINTER(C.c_void_p))
def m(idx, res, *args): return C.WINFUNCTYPE(res, C.c_void_p, *args)(vt[idx])
GetAdapterCount = m(4, C.c_uint)
GetAdapterDisplayMode = m(8, C.c_long, C.c_uint, C.POINTER(MODE))
CheckDeviceType = m(9, C.c_long, C.c_uint, C.c_uint, C.c_uint, C.c_uint, C.c_int)
GetAdapterMonitor = m(15, C.c_void_p, C.c_uint)
CreateDevice = m(16, C.c_long, C.c_uint, C.c_uint, W.HWND, C.c_uint, C.POINTER(PP), C.POINTER(C.c_void_p))

class MI(C.Structure):
    _fields_ = [('cbSize', W.DWORD), ('rcMonitor', W.RECT), ('rcWork', W.RECT), ('dwFlags', W.DWORD)]
u32.GetMonitorInfoW.argtypes = [C.c_void_p, C.POINTER(MI)]

def hx(hr): return f"0x{hr & 0xffffffff:08x}"

wins, devs = {}, []
def make(a, keep=False):
    mi = MI(); mi.cbSize = C.sizeof(MI); u32.GetMonitorInfoW(GetAdapterMonitor(p, a), C.byref(mi))
    r = mi.rcMonitor
    hwnd = wins.get(a) or u32.CreateWindowExW(0, "STATIC", "t", 0x80000000, r.left, r.top,
                                             r.right - r.left, r.bottom - r.top, None, None, None, None)
    wins[a] = hwnd
    cur = MODE(); GetAdapterDisplayMode(p, a, C.byref(cur))
    ct = CheckDeviceType(p, a, 1, cur.Format, 0x16, 1)
    for ds in (0x4b, 0x50):                     # D24S8, D16
        for beh in (0x40, 0x20):                # HW VP, SW VP
            pp = PP(0, 0, 0x16, 1, 0, 0, 1, hwnd, 1, 1, ds, 2, 0, 0x80000000)
            dev = C.c_void_p()
            hr = CreateDevice(p, a, 1, hwnd, beh, C.byref(pp), C.byref(dev))
            if hr >= 0:
                if keep: devs.append(dev)
                else:
                    C.WINFUNCTYPE(C.c_ulong, C.c_void_p)(C.cast(C.cast(dev, C.POINTER(C.c_void_p))[0], C.POINTER(C.c_void_p))[2])(dev)
                return f"OK  bb={pp.BackBufferWidth}x{pp.BackBufferHeight} ds=0x{ds:x} beh=0x{beh:x}"
            last = hr
    return f"FAIL {hx(last)}"

n = GetAdapterCount(p)
for a in range(n):
    cur = MODE(); GetAdapterDisplayMode(p, a, C.byref(cur))
    print(f"adapter {a}: {cur.Width}x{cur.Height}@{cur.RefreshRate}  individually -> {make(a)}")
print("all at once:")
for a in range(n):
    print(f"  adapter {a} -> {make(a, keep=True)}")
