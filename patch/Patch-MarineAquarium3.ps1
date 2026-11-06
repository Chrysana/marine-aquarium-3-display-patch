<#
.SYNOPSIS
    Unofficial display patch for an existing installation of SereneScreen Marine Aquarium 3.

.DESCRIPTION
    Makes the screensaver render in borderless windows on every monitor instead of
    switching monitors into exclusive fullscreen. Monitors keep their native resolution
    and refresh rate (e.g. 1440p at 144 Hz, 240 Hz, 360 Hz), which fixes the screensaver
    forcing a lower resolution or crashing on high-refresh multi-monitor setups.

    This does NOT unlock, register, crack or provide the full version. It only edits
    display-mode code in a copy of MarineAquarium3.scr that you already have installed.
    Trial copies stay trial copies.

    A backup of the original file is saved next to it as MarineAquarium3.scr.bak and can
    be restored at any time with -Restore.

.PARAMETER Path
    Path to MarineAquarium3.scr. If omitted, the script looks in the standard install
    locations (Windows\SysWOW64, Windows\System32) and the currently selected screensaver.

.PARAMETER Restore
    Put the original (backed-up) file back.

.PARAMETER Status
    Only report whether each copy found is unpatched, patched, or unrecognised.

.EXAMPLE
    .\Patch-MarineAquarium3.ps1
.EXAMPLE
    .\Patch-MarineAquarium3.ps1 -Status
.EXAMPLE
    .\Patch-MarineAquarium3.ps1 -Restore
#>
[CmdletBinding()]
param(
    [string]$Path,
    [switch]$Restore,
    [switch]$Status,
    [switch]$PauseAtEnd
)

$ErrorActionPreference = 'Stop'
$PatchVersion = '1.0.0'

# Always run as a 64-bit process on 64-bit Windows, so System32 / SysWOW64 paths mean what
# they say (a 32-bit PowerShell would see SysWOW64 under both names).
if ([Environment]::Is64BitOperatingSystem -and -not [Environment]::Is64BitProcess) {
    $ps64 = Join-Path $env:WINDIR 'Sysnative\WindowsPowerShell\v1.0\powershell.exe'
    if (Test-Path -LiteralPath $ps64) {
        $relaunch = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath)
        foreach ($kv in $PSBoundParameters.GetEnumerator()) {
            if ($kv.Value -is [switch]) { if ($kv.Value.IsPresent) { $relaunch += "-$($kv.Key)" } }
            else { $relaunch += "-$($kv.Key)"; $relaunch += [string]$kv.Value }
        }
        & $ps64 @relaunch
        exit $LASTEXITCODE
    }
}

# ---------------------------------------------------------------------------------------
# Patch engine (C#). Each site is located by a byte signature with wildcards and must
# match exactly once. See docs/TECHNICAL.md for what every site does and why.
# ---------------------------------------------------------------------------------------
$engine = @'
using System;
using System.Collections.Generic;

public static class Ma3Patch
{
    class Site
    {
        public string Label;
        public short[] Orig;
        public short[] Patched;
        public Func<byte[], byte[]> Build;
    }

    static short[] P(string s)
    {
        string[] t = s.Split(new char[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
        short[] r = new short[t.Length];
        for (int i = 0; i < t.Length; i++)
            r[i] = t[i] == "??" ? (short)-1 : Convert.ToInt16(t[i], 16);
        return r;
    }

    static byte[] Hex(string s)
    {
        string[] t = s.Split(new char[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
        byte[] r = new byte[t.Length];
        for (int i = 0; i < t.Length; i++) r[i] = Convert.ToByte(t[i], 16);
        return r;
    }

    static byte[] Splice(byte[] orig, int at, byte[] repl)
    {
        byte[] r = (byte[])orig.Clone();
        Array.Copy(repl, 0, r, at, repl.Length);
        return r;
    }

    static readonly List<Site> Sites = new List<Site>();

    static Ma3Patch()
    {
        // 1. CreateFullscreenRenderUnit: build present parameters as windowed,
        //    refresh rate 0, back buffer 0x0 (= size of the monitor-sized window).
        Sites.Add(new Site {
            Label = "device creation: windowed, refresh 0, back buffer = window",
            Orig = P("8b 4c 24 ?? 33 d2 89 56 38 89 56 48 8b 81 ?? ?? ?? ?? 89 46 30 8b 45 00 89 03 8b 45 04 89 46 1c 8b 87 ?? ?? ?? ??"),
            Patched = P("8b 4c 24 ?? 33 d2 42 89 56 38 4a 89 56 48 8b 81 ?? ?? ?? ?? 89 46 30 89 13 89 56 1c 90 90 90 90 8b 87 ?? ?? ?? ??"),
            Build = delegate(byte[] o) {
                byte[] r = (byte[])o.Clone();
                List<byte> n = new List<byte>();
                for (int i = 0; i < 4; i++) n.Add(o[i]);                    // mov ecx,[esp+??]
                n.AddRange(Hex("33 d2 42 89 56 38 4a 89 56 48"));          // Windowed=1, Refresh=0
                for (int i = 12; i < 21; i++) n.Add(o[i]);                  // SwapEffect (unchanged)
                n.AddRange(Hex("89 13 89 56 1c"));                          // BackBuffer W/H = 0
                while (n.Count < 32) n.Add(0x90);
                n.CopyTo(r, 0);
                return r;
            }
        });
        // 2. Rebuild-present-parameters (runs before every device Reset): Windowed = TRUE.
        Sites.Add(new Site {
            Label = "device reset: windowed",
            Orig = P("8b 97 ?? ?? ?? ?? 89 56 34 ba 01 00 00 00 89 56 20 89 6e 24 89 6e 28 89 56 2c"),
            Patched = P("33 d2 42 90 90 90 89 56 34 ba 01 00 00 00 89 56 20 89 6e 24 89 6e 28 89 56 2c"),
            Build = delegate(byte[] o) { return Splice(o, 0, Hex("33 d2 42 90 90 90")); }
        });
        // 3. Same function: always size the back buffer to the monitor's desktop mode
        //    (ignore a previously saved, possibly lower, fallback resolution).
        Sites.Add(new Site {
            Label = "device reset: back buffer = desktop size",
            Orig = P("8b 88 ?? ?? ?? ?? 3b cd 74 ?? 89 4e 14 8b 90 ?? ?? ?? ?? 89 56 18"),
            Patched = P("8b 88 ?? ?? ?? ?? 3b cd eb ?? 89 4e 14 8b 90 ?? ?? ?? ?? 89 56 18"),
            Build = delegate(byte[] o) { return Splice(o, 8, new byte[] { 0xeb }); }
        });
        // 4. Same function: refresh rate 0 (required for windowed devices).
        Sites.Add(new Site {
            Label = "device reset: refresh 0",
            Orig = P("89 4e 48 8b 90 ?? ?? ?? ?? 8b 46 1c 89 56 44 83 f8 18"),
            Patched = P("89 4e 48 33 d2 90 90 90 90 8b 46 1c 89 56 44 83 f8 18"),
            Build = delegate(byte[] o) { return Splice(o, 3, Hex("33 d2 90 90 90 90")); }
        });
    }

    public static List<int> FindAll(byte[] d, short[] p)
    {
        List<int> hits = new List<int>();
        int first = 0;
        while (p[first] < 0) first++;
        byte anchor = (byte)p[first];
        int pos = 0;
        while (true)
        {
            pos = Array.IndexOf(d, anchor, pos);
            if (pos < 0) break;
            int start = pos - first;
            if (start >= 0 && start + p.Length <= d.Length)
            {
                bool ok = true;
                for (int i = 0; i < p.Length; i++)
                    if (p[i] >= 0 && d[start + i] != (byte)p[i]) { ok = false; break; }
                if (ok) hits.Add(start);
            }
            pos++;
        }
        return hits;
    }

    // Returns "Unpatched", "Patched" or "Unknown"; details describe each site.
    public static string GetStatus(byte[] d, out string[] details)
    {
        int orig = 0, patched = 0;
        details = new string[Sites.Count];
        for (int i = 0; i < Sites.Count; i++)
        {
            int o = FindAll(d, Sites[i].Orig).Count;
            int p = FindAll(d, Sites[i].Patched).Count;
            if (o == 1 && p == 0) orig++;
            if (p == 1 && o == 0) patched++;
            details[i] = String.Format("{0}: original={1} patched={2}", Sites[i].Label, o, p);
        }
        if (orig == Sites.Count) return "Unpatched";
        if (patched == Sites.Count) return "Patched";
        return "Unknown";
    }

    public static bool LooksLikeMa3(byte[] d)
    {
        if (d.Length < 0x1000 || d[0] != 0x4d || d[1] != 0x5a) return false;
        byte[] marker = System.Text.Encoding.ASCII.GetBytes("SereneScreen Marine Aquarium");
        short[] p = new short[marker.Length];
        for (int i = 0; i < marker.Length; i++) p[i] = marker[i];
        return FindAll(d, p).Count > 0;
    }

    public static byte[] Apply(byte[] d)
    {
        string[] details;
        if (GetStatus(d, out details) != "Unpatched")
            throw new InvalidOperationException("File is not an unpatched, recognised build.");
        byte[] r = (byte[])d.Clone();
        foreach (Site s in Sites)
        {
            int off = FindAll(r, s.Orig)[0];
            byte[] o = new byte[s.Orig.Length];
            Array.Copy(r, off, o, 0, o.Length);
            byte[] n = s.Build(o);
            if (n.Length != o.Length) throw new InvalidOperationException("internal: size mismatch");
            Array.Copy(n, 0, r, off, n.Length);
        }
        FixChecksum(r);
        if (GetStatus(r, out details) != "Patched")
            throw new InvalidOperationException("internal: verification after patching failed");
        return r;
    }

    // Standard PE image checksum (same algorithm as imagehlp CheckSumMappedFile).
    public static void FixChecksum(byte[] d)
    {
        int lfanew = BitConverter.ToInt32(d, 0x3c);
        int ckOff = lfanew + 4 + 20 + 0x40;
        ulong sum = 0;
        int n = (d.Length + 3) / 4;
        for (int i = 0; i < n; i++)
        {
            if (i * 4 == ckOff) continue;
            uint dw = 0;
            for (int b = 0; b < 4 && i * 4 + b < d.Length; b++) dw |= (uint)d[i * 4 + b] << (8 * b);
            sum += dw;
            if (sum >= 0x100000000UL) sum = (sum & 0xffffffffUL) + (sum >> 32);
        }
        sum = (sum & 0xffff) + (sum >> 16);
        sum = sum + (sum >> 16);
        sum &= 0xffff;
        uint ck = (uint)(sum + (ulong)d.Length);
        BitConverter.GetBytes(ck).CopyTo(d, ckOff);
    }
}
'@
if (-not ('Ma3Patch' -as [type])) { Add-Type -TypeDefinition $engine -Language CSharp }

# ---------------------------------------------------------------------------------------
function Write-Step($msg)  { Write-Host "  $msg" }
function Write-Good($msg)  { Write-Host "  $msg" -ForegroundColor Green }
function Write-Warn2($msg) { Write-Host "  $msg" -ForegroundColor Yellow }
function Write-Bad($msg)   { Write-Host "  $msg" -ForegroundColor Red }

function Test-Admin {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    (New-Object Security.Principal.WindowsPrincipal $id).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

# The screensaver is 32-bit. On 64-bit Windows, a 32-bit program that asks for
# C:\Windows\System32\MarineAquarium3.scr (which is what the screensaver settings record)
# is silently redirected to C:\Windows\SysWOW64. This script always runs 64-bit (see the
# relaunch near the top), so map such paths to where the file really is.
function Resolve-ScrPath([string]$p) {
    if (-not $p) { return $null }
    $p = [Environment]::ExpandEnvironmentVariables($p.Trim('"'))
    if (Test-Path -LiteralPath $p -PathType Leaf) { return (Get-Item -LiteralPath $p).FullName }
    $sys32 = Join-Path $env:WINDIR 'System32'
    if ($p.StartsWith($sys32 + '\', [StringComparison]::OrdinalIgnoreCase)) {
        $alt = Join-Path (Join-Path $env:WINDIR 'SysWOW64') $p.Substring($sys32.Length + 1)
        if (Test-Path -LiteralPath $alt -PathType Leaf) { return (Get-Item -LiteralPath $alt).FullName }
    }
    return $null
}

function Find-Targets {
    $found = New-Object System.Collections.Generic.List[string]
    $candidates = @(
        (Join-Path $env:WINDIR 'SysWOW64\MarineAquarium3.scr'),
        (Join-Path $env:WINDIR 'System32\MarineAquarium3.scr')
    )
    try {
        $cur = (Get-ItemProperty 'HKCU:\Control Panel\Desktop' -Name 'SCRNSAVE.EXE' -ErrorAction Stop).'SCRNSAVE.EXE'
        if ($cur) { $candidates += $cur }
    } catch { }
    foreach ($c in $candidates) {
        $full = Resolve-ScrPath $c
        if ($full) {
            if ($found -notcontains $full) {
                $bytes = [IO.File]::ReadAllBytes($full)
                if ([Ma3Patch]::LooksLikeMa3($bytes)) { $found.Add($full) }
            }
        }
    }
    return $found.ToArray()
}

function Test-NeedsAdmin([string]$file) {
    try {
        $fs = [IO.File]::Open($file, 'Open', 'ReadWrite', 'ReadWrite')
        $fs.Close()
        $dir = Split-Path -Parent $file
        $probe = Join-Path $dir ('.ma3patch_' + [guid]::NewGuid().ToString('N'))
        [IO.File]::WriteAllBytes($probe, @())
        Remove-Item -LiteralPath $probe -Force
        return $false
    } catch {
        # Access denied => needs elevation. Other errors (e.g. file in use) are reported later.
        $e = $_.Exception
        while ($e) {
            if ($e -is [UnauthorizedAccessException] -or $e -is [Security.SecurityException]) { return $true }
            $e = $e.InnerException
        }
        return $false
    }
}

function Get-FileStatus([string]$file) {
    $bytes = [IO.File]::ReadAllBytes($file)
    $details = $null
    $st = [Ma3Patch]::GetStatus($bytes, [ref]$details)
    return @{ Status = $st; Details = $details; Bytes = $bytes }
}

function Invoke-Patch([string]$file) {
    Write-Host ""
    Write-Host "$file"
    $s = Get-FileStatus $file
    switch ($s.Status) {
        'Patched' { Write-Good "Already patched - nothing to do."; return }
        'Unknown' {
            Write-Bad "This build of MarineAquarium3.scr is not recognised (or is partly modified)."
            Write-Bad "Nothing was changed. Details:"
            $s.Details | ForEach-Object { Write-Step "  $_" }
            return
        }
    }
    $backup = "$file.bak"
    if (Test-Path -LiteralPath $backup) {
        $b = Get-FileStatus $backup
        if ($b.Status -ne 'Unpatched') {
            Write-Bad "A backup already exists at $backup but it is not an original copy. Nothing was changed."
            return
        }
        Write-Step "Existing backup found (original copy): $backup"
    } else {
        Copy-Item -LiteralPath $file -Destination $backup
        Write-Step "Backup saved: $backup"
    }
    $patched = [Ma3Patch]::Apply($s.Bytes)
    $tmp = "$file.patching"
    [IO.File]::WriteAllBytes($tmp, $patched)
    try {
        Copy-Item -LiteralPath $tmp -Destination $file -Force
    } catch {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        Write-Bad "Could not write the file. Is the screensaver (or its settings dialog) running? Close it and try again."
        Write-Bad $_.Exception.Message
        return
    }
    Remove-Item -LiteralPath $tmp -Force
    if ((Get-FileStatus $file).Status -eq 'Patched') { Write-Good "Patched successfully." }
    else { Write-Bad "Verification failed after writing. Run with -Restore to put the original back." }
}

function Invoke-Restore([string]$file) {
    Write-Host ""
    Write-Host "$file"
    $backup = "$file.bak"
    if (-not (Test-Path -LiteralPath $backup)) {
        if ((Get-FileStatus $file).Status -eq 'Unpatched') { Write-Good "Not patched - nothing to restore." }
        else { Write-Bad "No backup found at $backup." }
        return
    }
    if ((Get-FileStatus $backup).Status -ne 'Unpatched') {
        Write-Bad "The backup at $backup is not an original copy; not restoring it."
        return
    }
    try {
        Copy-Item -LiteralPath $backup -Destination $file -Force
    } catch {
        Write-Bad "Could not write the file. Is the screensaver (or its settings dialog) running? Close it and try again."
        Write-Bad $_.Exception.Message
        return
    }
    Remove-Item -LiteralPath $backup -Force
    Write-Good "Original restored."
}

# ---------------------------------------------------------------------------------------
Write-Host ""
Write-Host "Marine Aquarium 3 display patch v$PatchVersion (unofficial)" -ForegroundColor Cyan
Write-Host "Borderless rendering at native resolution and refresh rate."
Write-Host "Does NOT unlock or provide the full version - it only patches your existing copy."

function Main {
    if ($Path) {
        $full = Resolve-ScrPath $Path
        if (-not $full) { throw "File not found: $Path" }
        if (-not [Ma3Patch]::LooksLikeMa3([IO.File]::ReadAllBytes($full))) { throw "Not a Marine Aquarium 3 screensaver: $full" }
        $targets = @($full)
    } else {
        $targets = @(Find-Targets)
    }
    if ($targets.Count -eq 0) {
        Write-Host ""
        Write-Bad "MarineAquarium3.scr was not found. Install Marine Aquarium 3 first, or pass -Path <file>."
        return 1
    }

    if ($Status) {
        foreach ($t in $targets) {
            $s = Get-FileStatus $t
            Write-Host ""
            Write-Host "$t"
            Write-Step "Status: $($s.Status)"
            if ($s.Status -eq 'Unknown') { $s.Details | ForEach-Object { Write-Step "  $_" } }
        }
        return 0
    }

    $needAdmin = $false
    foreach ($t in $targets) { if (Test-NeedsAdmin $t) { $needAdmin = $true } }
    if ($needAdmin -and -not (Test-Admin)) {
        Write-Host ""
        Write-Warn2 "Administrator rights are needed to modify files in the Windows folder."
        Write-Warn2 "Approve the prompt - the patch continues in a new window."
        $argList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$PSCommandPath`"", '-PauseAtEnd')
        if ($Restore) { $argList += '-Restore' }
        if ($Path) { $argList += @('-Path', "`"$Path`"") }
        try {
            Start-Process -FilePath 'powershell.exe' -ArgumentList $argList -Verb RunAs | Out-Null
            $script:HandedOff = $true
            return 0
        } catch {
            Write-Bad "Elevation was cancelled. Nothing was changed."
            return 1
        }
    }

    foreach ($t in $targets) {
        if ($Restore) { Invoke-Restore $t } else { Invoke-Patch $t }
    }
    return 0
}

$script:HandedOff = $false
$code = 1
try {
    $code = Main | Select-Object -Last 1
} catch {
    Write-Host ""
    Write-Bad "Error: $($_.Exception.Message)"
    $code = 1
}
if ($PauseAtEnd -and -not $script:HandedOff) {
    Write-Host ""
    Read-Host "Press Enter to close" | Out-Null
}
exit $code
