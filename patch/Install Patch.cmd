@echo off
rem Runs the Marine Aquarium 3 display patch (see Patch-MarineAquarium3.ps1 - plain text, safe to read).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Patch-MarineAquarium3.ps1" -PauseAtEnd
