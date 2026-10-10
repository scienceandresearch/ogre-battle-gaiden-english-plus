# Cartridge save in the window mode: debounced write, flush on Esc, ini values,
# pause when inactive. SAVE_PROMPT_STATE is a state on the "OK:A NO:B" bar of
# Data -> Save (build/states/data-popup_save_prompt.state, see explore-data.md),
# made with the same English image the ROM gives.
#   powershell -File gui_save_test.ps1 -AppDir DIR -Rom ROM -State SAVE_PROMPT_STATE -Out OUTDIR
param([string]$AppDir, [string]$Rom, [string]$State, [string]$Out)
$ErrorActionPreference = 'Stop'
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class W2 {
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder sb, int n);
}
"@
$results = New-Object System.Collections.ArrayList
function Check($name, $cond) { $s = if ($cond) { 'ok  ' } else { 'FAIL' }; [void]$results.Add("$s $name"); Write-Output "$s $name" }
function Title($h) { $sb = New-Object System.Text.StringBuilder 512; [void][W2]::GetWindowText($h, $sb, 512); $sb.ToString() }
function Key($h, $vk) {
  [void][W2]::PostMessage($h, 0x100, [IntPtr]$vk, [IntPtr]1); Start-Sleep -Milliseconds 120
  [void][W2]::PostMessage($h, 0x101, [IntPtr]$vk, [IntPtr]0xC0000001); Start-Sleep -Milliseconds 150
}
function Start-Player($tag) {
  $p = Start-Process -FilePath "$AppDir\zenobia.exe" -ArgumentList "`"$Rom`" --exit-after 40" -PassThru `
       -RedirectStandardError "$Out\$tag-stderr.txt" -RedirectStandardOutput "$Out\$tag-stdout.txt"
  $null = $p.Handle
  for ($i = 0; $i -lt 50 -and $p.MainWindowHandle -eq [IntPtr]::Zero; $i++) { Start-Sleep -Milliseconds 100; $p.Refresh() }
  Start-Sleep -Milliseconds 800
  return $p
}

New-Item -ItemType Directory -Force $Out, "$AppDir\states" | Out-Null
Copy-Item $State "$AppDir\states\slot0.state" -Force
# settings: half volume, pause while in the background
$ini = "[video]`r`nscale=3`r`n[audio]`r`nvolume=50`r`n[general]`r`npause_when_inactive=1`r`n"
[System.IO.File]::WriteAllText("$AppDir\zenobia.ini", $ini, [System.Text.Encoding]::ASCII)
$stem = [System.IO.Path]::GetFileNameWithoutExtension($Rom)
$sav = "$AppDir\saves\$stem.sav"
if (Test-Path $sav) { Remove-Item -LiteralPath $sav }

# 1. debounced write while playing
$p = Start-Player 'run1'; $h = $p.MainWindowHandle
Key $h 0x78   # F9: slot 0 = Data -> Save prompt
$t = Title $h; Write-Output "title: $t"; Check "state with the save prompt loaded" ($t -match 'State 0 loaded')
Key $h 0x5A   # Z = A: the game saves
Start-Sleep -Milliseconds 900
Check "no file yet (waits for 2 s without flash writes)" (-not (Test-Path $sav))
Start-Sleep -Milliseconds 2600
Check "save file written after the quiet period" (Test-Path $sav)
$t = Title $h; Write-Output "title: $t"; Check "title reports the write" ($t -match 'Cartridge save written')
# 2. pause while inactive
[void][W2]::PostMessage($h, 0x1C, [IntPtr]0, [IntPtr]0); Start-Sleep -Milliseconds 300   # WM_ACTIVATEAPP(FALSE)
$t = Title $h; Write-Output "title: $t"; Check "paused while inactive" ($t -match 'Paused \(inactive\)')
[void][W2]::PostMessage($h, 0x1C, [IntPtr]1, [IntPtr]0); Start-Sleep -Milliseconds 300
$t = Title $h; Check "resumes when active" (-not ($t -match 'Paused'))
Key $h 0x1B   # Esc
$p.WaitForExit(10000) | Out-Null
Check "Esc quits (exit code $($p.ExitCode))" ($p.HasExited -and $p.ExitCode -eq 0)
Get-Content "$Out\run1-stderr.txt" | ForEach-Object { Write-Output "stderr: $_" }
$len1 = (Get-Item $sav).Length

# 3. flush on exit: save in game again, quit before the quiet period ends
$t1 = (Get-Item $sav).LastWriteTimeUtc
Start-Sleep -Milliseconds 1100
$p = Start-Player 'run2'; $h = $p.MainWindowHandle
$t = Title $h; Write-Output "title: $t"; Check "existing save loaded at start" ($t -match 'Cartridge save loaded')
Key $h 0x78; Key $h 0x5A
Start-Sleep -Milliseconds 600
Check "not rewritten before quitting" ((Get-Item $sav).LastWriteTimeUtc -eq $t1)
Key $h 0x1B
$p.WaitForExit(10000) | Out-Null
Check "Esc wrote the pending save (exit code $($p.ExitCode))" (((Get-Item $sav).LastWriteTimeUtc -gt $t1) -and $p.ExitCode -eq 0)
Check "same file size ($len1)" ((Get-Item $sav).Length -eq $len1)
Check "previous file kept as .bak" ((Test-Path "$sav.bak") -and ((Get-Item "$sav.bak").Length -eq $len1))

$fails = ($results | Where-Object { $_.StartsWith('FAIL') }).Count
Write-Output "checks: $($results.Count), failed: $fails"
