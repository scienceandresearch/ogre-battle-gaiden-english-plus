# Fast-forward (speed, muted sound), resized window geometry, and a start
# without a ROM (Open dialog, Cancel, hint screen, default zenobia.ini).
# EmptyAppDir: a folder holding only zenobia.exe. Window managers that restore
# window sizes (e.g. PersistentWindows) can disturb the size checks.
#   powershell -File gui_misc_test.ps1 -AppDir DIR -Rom ROM -EmptyAppDir DIR -Out OUTDIR
param([string]$AppDir, [string]$Rom, [string]$EmptyAppDir, [string]$Out)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
public static class W4 {
  public delegate bool CB(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(CB cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder sb, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder sb, int n);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int w, int hh, uint flags);
  [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr hdc, uint flags);
  [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr ctx);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  public static IntPtr FindDialog(uint pid) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => {
      uint p; GetWindowThreadProcessId(h, out p);
      if (p != pid || !IsWindowVisible(h)) return true;
      var sb = new StringBuilder(64); GetClassName(h, sb, 64);
      if (sb.ToString() == "#32770") { found = h; return false; }
      return true;
    }, IntPtr.Zero);
    return found;
  }
  public static string Text(IntPtr h) { var sb = new StringBuilder(512); GetWindowText(h, sb, 512); return sb.ToString(); }
}
"@
[void][W4]::SetThreadDpiAwarenessContext([IntPtr](-4))
$results = New-Object System.Collections.ArrayList
function Check($name, $cond) { $s = if ($cond) { 'ok  ' } else { 'FAIL' }; [void]$results.Add("$s $name"); Write-Output "$s $name" }
function Capture($h, $path) {
  $r = New-Object W4+RECT; [void][W4]::GetClientRect($h, [ref]$r)
  $bmp = New-Object System.Drawing.Bitmap ([Math]::Max(1, $r.Right)), ([Math]::Max(1, $r.Bottom))
  $g = [System.Drawing.Graphics]::FromImage($bmp); $hdc = $g.GetHdc()
  [void][W4]::PrintWindow($h, $hdc, 3)
  $g.ReleaseHdc($hdc); $g.Dispose(); $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png); $bmp.Dispose()
}
New-Item -ItemType Directory -Force $Out | Out-Null

# 1. fast-forward: Tab held for 3 s of a 6 s run
$p = Start-Process -FilePath "$AppDir\zenobia.exe" -ArgumentList "`"$Rom`" --exit-after 6" -PassThru -RedirectStandardError "$Out\ff-stderr.txt"
$null = $p.Handle
for ($i = 0; $i -lt 50 -and $p.MainWindowHandle -eq [IntPtr]::Zero; $i++) { Start-Sleep -Milliseconds 100; $p.Refresh() }
$h = $p.MainWindowHandle
Start-Sleep -Milliseconds 1000
[void][W4]::PostMessage($h, 0x100, [IntPtr]0x09, [IntPtr]1)   # Tab down (held)
Start-Sleep -Milliseconds 400
$t = [W4]::Text($h); Write-Output "  title: $t"; Check "title shows fast forward" ($t -match 'Fast forward')
Start-Sleep -Milliseconds 2600
[void][W4]::PostMessage($h, 0x101, [IntPtr]0x09, [IntPtr]0xC0000001)   # Tab up
# 2. resize to a client of about 1000x700: whole-number zoom 4, centred
$wr = New-Object W4+RECT; [void][W4]::GetWindowRect($h, [ref]$wr)
$cr = New-Object W4+RECT; [void][W4]::GetClientRect($h, [ref]$cr)
$fw = ($wr.Right - $wr.Left) - $cr.Right; $fh = ($wr.Bottom - $wr.Top) - $cr.Bottom
[void][W4]::SetWindowPos($h, [IntPtr]::Zero, $wr.Left, $wr.Top, 1000 + $fw, 700 + $fh, 0x14)   # NOZORDER|NOACTIVATE
Start-Sleep -Milliseconds 500
Capture $h "$Out\resized.png"
$bmp = [System.Drawing.Bitmap]::FromFile("$Out\resized.png")
Write-Output "  resized client $($bmp.Width)x$($bmp.Height)"
$s = [Math]::Min([Math]::Floor($bmp.Width / 160), [Math]::Floor($bmp.Height / 152))
$x0 = [int](($bmp.Width - 160 * $s) / 2); $y0 = [int](($bmp.Height - 152 * $s) / 2)
function Black($x, $y) { $c = $bmp.GetPixel($x, $y); ($c.R -eq 0) -and ($c.G -eq 0) -and ($c.B -eq 0) }
$my = $y0 + 76 * $s
Write-Output "  expected zoom $s at $x0,$y0"
Check "resized: black left border, picture from x0" ((Black ($x0 - 1) $my) -and -not (Black $x0 $my))
Check "resized: black right border" ((Black ($x0 + 160 * $s) $my) -and -not (Black ($x0 + 160 * $s - 1) $my))
$bmp.Dispose()
$p.WaitForExit(15000) | Out-Null
Get-Content "$Out\ff-stderr.txt" | ForEach-Object { Write-Output "  stderr: $_" }
$lines = Get-Content "$Out\ff-stderr.txt"
$frames = [int](($lines | Where-Object { $_ -match 'frames in' } | Select-Object -First 1) -replace '^zenobia: (\d+) frames.*', '$1')
Check "fast-forward ran more frames than real time ($frames in 6 s)" ($frames -gt 600)
$pushed = [int](($lines | Where-Object { $_ -match 'frames pushed' } | Select-Object -First 1) -replace '^.*: (\d+) frames pushed.*', '$1')
Check "sound muted while fast-forwarding ($pushed frames pushed, about 3 s)" ($pushed -lt 48000 * 4)

# 3. no ROM: the Open dialog appears; Cancel leaves the hint screen
$p = Start-Process -FilePath "$EmptyAppDir\zenobia.exe" -PassThru
$null = $p.Handle
$d = [IntPtr]::Zero
for ($i = 0; $i -lt 80 -and $d -eq [IntPtr]::Zero; $i++) { Start-Sleep -Milliseconds 100; $d = [W4]::FindDialog([uint32]$p.Id) }
$dt = if ($d -ne [IntPtr]::Zero) { [W4]::Text($d) } else { '' }
Write-Output "  dialog title: $dt"
Check "no ROM: Open dialog shown" ($dt -eq 'Open the Ogre Battle Gaiden ROM')
[void][W4]::PostMessage($d, 0x0111, [IntPtr]2, [IntPtr]0)   # WM_COMMAND IDCANCEL
Start-Sleep -Milliseconds 800
$p.Refresh(); $h = $p.MainWindowHandle
Capture $h "$Out\hint.png"
Check "hint screen title" ($p.MainWindowTitle -eq 'Ogre Battle Gaiden: Prince of Zenobia (English)')
[void][W4]::PostMessage($h, 0x0010, [IntPtr]0, [IntPtr]0)
$p.WaitForExit(10000) | Out-Null
Check "closes cleanly (exit $($p.ExitCode))" ($p.HasExited -and $p.ExitCode -eq 0)
Check "ini created with defaults" ((Test-Path "$EmptyAppDir\zenobia.ini") -and ((Get-Content "$EmptyAppDir\zenobia.ini" -Raw) -match 'pause_when_inactive=0'))

$fails = ($results | Where-Object { $_.StartsWith('FAIL') }).Count
Write-Output "checks: $($results.Count), failed: $fails"
