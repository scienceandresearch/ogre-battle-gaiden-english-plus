# Drives zenobia.exe through its window with posted key messages: title bar,
# window size, keyboard input, state slots, pause, F11 / Alt+Enter fullscreen
# (picture geometry checked on a capture), --exit-after and its statistics.
# Opens a real window for about 16 s. Use a copy of zenobia.exe (and
# ogre_en.bps) in a scratch folder: it creates states\ and zenobia.ini there.
#   powershell -File gui_test.ps1 -Exe APPDIR\zenobia.exe -Rom ROM -Out OUTDIR
param([string]$Exe, [string]$Rom, [string]$Out)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class W {
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr FindWindow(string cls, string title);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder sb, int n);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern IntPtr MonitorFromWindow(IntPtr h, uint flags);
  [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr ctx);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
}
"@
# measure in physical pixels, like the per-monitor DPI aware player
[void][W]::SetThreadDpiAwarenessContext([IntPtr](-4))
$WM_KEYDOWN = 0x100; $WM_KEYUP = 0x101; $WM_SYSKEYDOWN = 0x104; $WM_SYSKEYUP = 0x105
$results = New-Object System.Collections.ArrayList
function Check($name, $cond) { $s = if ($cond) { 'ok  ' } else { 'FAIL' }; [void]$results.Add("$s $name"); Write-Output "$s $name" }
function Title($h) { $sb = New-Object System.Text.StringBuilder 512; [void][W]::GetWindowText($h, $sb, 512); $sb.ToString() }
function Key($h, $vk) {
  [void][W]::PostMessage($h, $WM_KEYDOWN, [IntPtr]$vk, [IntPtr]1)
  Start-Sleep -Milliseconds 120
  [void][W]::PostMessage($h, $WM_KEYUP, [IntPtr]$vk, [IntPtr]0xC0000001)
  Start-Sleep -Milliseconds 250
}
function Capture($h, $path) {
  $r = New-Object W+RECT; [void][W]::GetClientRect($h, [ref]$r)
  $bmp = New-Object System.Drawing.Bitmap ([Math]::Max(1, $r.Right)), ([Math]::Max(1, $r.Bottom))
  $g = [System.Drawing.Graphics]::FromImage($bmp); $hdc = $g.GetHdc()
  [void][W]::PrintWindow($h, $hdc, 3)   # PW_CLIENTONLY | PW_RENDERFULLCONTENT
  $g.ReleaseHdc($hdc); $g.Dispose(); $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
  "$($r.Right)x$($r.Bottom)"
}

New-Item -ItemType Directory -Force $Out | Out-Null
$appdir = Split-Path $Exe
$p = Start-Process -FilePath $Exe -ArgumentList "`"$Rom`" --exit-after 16 --png `"$Out\exit.png`"" -PassThru `
     -RedirectStandardError "$Out\stderr.txt" -RedirectStandardOutput "$Out\stdout.txt"
$null = $p.Handle   # keeps the exit code readable after the process ends
$h = [IntPtr]::Zero
for ($i = 0; $i -lt 50 -and $h -eq [IntPtr]::Zero; $i++) { Start-Sleep -Milliseconds 100; $p.Refresh(); $h = $p.MainWindowHandle }
Check "window found" ($h -ne [IntPtr]::Zero)
Start-Sleep -Milliseconds 1500
$t = Title $h; Write-Output "title: $t"
Check "title starts with the game name" ($t.StartsWith('Ogre Battle Gaiden: Prince of Zenobia (English)'))
Check "title shows slot 0" ($t -match 'Slot 0')
$size = Capture $h "$Out\win_intro.png"; Write-Output "client $size"
Check "client area is 640x608 (scale 4)" ($size -eq '640x608')
if ($size -ne '640x608' -and (Get-Process -Name PersistentWindows -ErrorAction SilentlyContinue)) {
  # it restores the last size it saw for windows of the same program
  Write-Output "  note: PersistentWindows is running and restores window sizes; rerun with a copy of zenobia.exe under a new name (e.g. zen_check.exe)"
}

# keyboard -> game: Z (A button) skips the intro to the title screen
Key $h 0x5A; Start-Sleep -Milliseconds 1500
[void](Capture $h "$Out\win_title.png")

# save states in slots 0 and 1
Key $h 0x74   # F5
$t = Title $h; Write-Output "title: $t"
Check "F5 saved state 0" (($t -match 'State 0 saved') -and (Test-Path "$appdir\states\slot0.state"))
Key $h 0x76   # F7
$t = Title $h; Check "F7 selects slot 1" ($t -match 'Slot 1')
Key $h 0x74   # F5
Check "F5 saved state 1" (Test-Path "$appdir\states\slot1.state")
Key $h 0x75   # F6
$t = Title $h; Check "F6 back to slot 0" ($t -match 'Slot 0')

# pause
Key $h 0x50   # P
$t = Title $h; Write-Output "title: $t"; Check "P pauses" ($t -match 'Paused')
Start-Sleep -Milliseconds 500
Key $h 0x50
$t = Title $h; Check "P resumes" (-not ($t -match '- Paused'))

# fullscreen with F11 and back
$before = New-Object W+RECT; [void][W]::GetWindowRect($h, [ref]$before)
Key $h 0x7A   # F11
Start-Sleep -Milliseconds 700
$fs = New-Object W+RECT; [void][W]::GetWindowRect($h, [ref]$fs)
Write-Output ("fullscreen window: {0},{1} {2}x{3}" -f $fs.Left, $fs.Top, ($fs.Right - $fs.Left), ($fs.Bottom - $fs.Top))
$size = Capture $h "$Out\win_fullscreen.png"; Write-Output "fullscreen client $size"
Check "F11 makes the window larger" ((($fs.Right - $fs.Left) -gt ($before.Right - $before.Left)) -and (($fs.Bottom - $fs.Top) -gt ($before.Bottom - $before.Top)))
# picture geometry: whole-number scale, centred, black borders
$bmp = [System.Drawing.Bitmap]::FromFile("$Out\win_fullscreen.png")
$cw = $bmp.Width; $ch = $bmp.Height
$s = [Math]::Min([Math]::Floor($cw / 160), [Math]::Floor($ch / 152))
$x0 = [int](($cw - 160 * $s) / 2); $y0 = [int](($ch - 152 * $s) / 2); $x1 = $x0 + 160 * $s; $y1 = $y0 + 152 * $s
Write-Output "expected picture: scale $s at $x0,$y0 - $x1,$y1"
function Black($x, $y) { $c = $bmp.GetPixel($x, $y); ($c.R -eq 0) -and ($c.G -eq 0) -and ($c.B -eq 0) }
$my = [int](($y0 + $y1) / 2); $mx = [int](($x0 + $x1) / 2)
$ok = $true
if ($x0 -gt 0) { $ok = $ok -and (Black ($x0 - 1) $my) -and -not (Black $x0 $my) }
if ($x1 -lt $cw) { $ok = $ok -and (Black $x1 $my) -and -not (Black ($x1 - 1) $my) }
if ($y0 -gt 0) { $ok = $ok -and (Black $mx ($y0 - 1)) -and -not (Black $mx $y0) }
if ($y1 -lt $ch) { $ok = $ok -and (Black $mx $y1) }
$bmp.Dispose()
Check "fullscreen picture is whole-number scaled and centred" $ok
Key $h 0x7A
Start-Sleep -Milliseconds 700
$back = New-Object W+RECT; [void][W]::GetWindowRect($h, [ref]$back)
Check "F11 restores the window" (($back.Left -eq $before.Left) -and ($back.Top -eq $before.Top) -and ($back.Right -eq $before.Right) -and ($back.Bottom -eq $before.Bottom))
# Alt+Enter (WM_SYSKEYDOWN with the context bit)
[void][W]::PostMessage($h, $WM_SYSKEYDOWN, [IntPtr]0x0D, [IntPtr]0x20000001); Start-Sleep -Milliseconds 700
$fs2 = New-Object W+RECT; [void][W]::GetWindowRect($h, [ref]$fs2)
Check "Alt+Enter goes fullscreen" (($fs2.Right - $fs2.Left) -eq ($fs.Right - $fs.Left))
[void][W]::PostMessage($h, $WM_SYSKEYDOWN, [IntPtr]0x0D, [IntPtr]0x20000001); Start-Sleep -Milliseconds 700
$back2 = New-Object W+RECT; [void][W]::GetWindowRect($h, [ref]$back2)
Check "Alt+Enter restores" (($back2.Right - $back2.Left) -eq ($before.Right - $before.Left))

# load state 1 then 0
Key $h 0x76; Key $h 0x78   # F7, F9
$t = Title $h; Write-Output "title: $t"; Check "F9 loads state 1" ($t -match 'State 1 loaded')
Key $h 0x75; Key $h 0x78   # F6, F9
$t = Title $h; Check "F9 loads state 0" ($t -match 'State 0 loaded')
# an empty slot
Key $h 0x76; Key $h 0x76; Key $h 0x76; Key $h 0x78   # slot 3, F9
$t = Title $h; Write-Output "title: $t"; Check "empty slot reported" ($t -match 'empty')

$p.WaitForExit(30000) | Out-Null
Check "exited by itself" ($p.HasExited)
Check "exit code 0" ($p.ExitCode -eq 0)
Get-Content "$Out\stderr.txt" | ForEach-Object { Write-Output "stderr: $_" }
Check "exit PNG written" (Test-Path "$Out\exit.png")
$fails = ($results | Where-Object { $_.StartsWith('FAIL') }).Count
Write-Output "checks: $($results.Count), failed: $fails"
