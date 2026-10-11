# Interactive ROM decisions: message boxes for a missing patch and for an
# unrecognised ROM, and the F12 reset confirmation, answered by clicking
# their buttons. AppDir needs zenobia.exe and ogre_en.bps; OtherRom is any
# file that is not the Japanese ROM (e.g. a copy with one byte changed).
#   powershell -File gui_dialog_test.ps1 -AppDir DIR -JapaneseRom ROM -OtherRom ROM -Out OUTDIR
param([string]$AppDir, [string]$JapaneseRom, [string]$OtherRom, [string]$Out)
$ErrorActionPreference = 'Stop'
Add-Type @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class W3 {
  public delegate bool CB(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(CB cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder sb, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder sb, int n);
  [DllImport("user32.dll")] public static extern IntPtr GetDlgItem(IntPtr h, int id);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
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
  public static string Text(IntPtr h) { var sb = new StringBuilder(4096); GetWindowText(h, sb, 4096); return sb.ToString(); }
}
"@
$results = New-Object System.Collections.ArrayList
function Check($name, $cond) { $s = if ($cond) { 'ok  ' } else { 'FAIL' }; [void]$results.Add("$s $name"); Write-Output "$s $name" }
function WaitDialog($p) {
  for ($i = 0; $i -lt 60; $i++) { $d = [W3]::FindDialog([uint32]$p.Id); if ($d -ne [IntPtr]::Zero) { return $d }; Start-Sleep -Milliseconds 100 }
  return [IntPtr]::Zero
}
New-Item -ItemType Directory -Force $Out | Out-Null
# no "continue where you left off" question at the starts below (gui_extras_test.ps1 covers it)
[System.IO.File]::WriteAllText("$AppDir\zenobia.ini", "[general]`r`nresume=no`r`n", [System.Text.Encoding]::Unicode)
if (Test-Path "$AppDir\states\resume.state") { Remove-Item "$AppDir\states\resume.state" }

# 1. Japanese ROM, patch missing: offered to run untranslated -> Yes
$p = Start-Process -FilePath "$AppDir\zenobia.exe" -ArgumentList "`"$JapaneseRom`" --patch `"$AppDir\no_such.bps`"" -PassThru
$null = $p.Handle
$d = WaitDialog $p
Check "missing patch: dialog shown" ($d -ne [IntPtr]::Zero)
$msg = [W3]::Text([W3]::GetDlgItem($d, 0xFFFF)); Write-Output "  dialog text: $($msg -replace "`r?`n", ' | ')"
Check "  explains the missing patch" ($msg -match 'English patch was not found')
Check "  offers to run untranslated" ($msg -match 'untranslated')
[void][W3]::PostMessage([W3]::GetDlgItem($d, 6), 0x00F5, [IntPtr]0, [IntPtr]0)   # BM_CLICK on Yes
Start-Sleep -Milliseconds 1500
$p.Refresh(); $t = $p.MainWindowTitle; Write-Output "  title: $t"
Check "  Yes runs it, marked untranslated" ($t -match '\[untranslated\]')
[void][W3]::PostMessage($p.MainWindowHandle, 0x0010, [IntPtr]0, [IntPtr]0)   # WM_CLOSE
$p.WaitForExit(10000) | Out-Null
Check "  closes cleanly (exit $($p.ExitCode))" ($p.HasExited -and $p.ExitCode -eq 0)

# 2. unrecognised ROM: explained, No = not loaded
$p = Start-Process -FilePath "$AppDir\zenobia.exe" -ArgumentList "`"$OtherRom`"" -PassThru
$null = $p.Handle
$d = WaitDialog $p
Check "unknown ROM: dialog shown" ($d -ne [IntPtr]::Zero)
$msg = [W3]::Text([W3]::GetDlgItem($d, 0xFFFF)); Write-Output "  dialog text: $($msg -replace "`r?`n", ' | ')"
Check "  names the expected ROM" ($msg -match '5ac794c0f125bfb97efe9cd06c2aca3afdf549ea')
Check "  says how to get the patch" ($msg -match 'ogre_en.bps')
[void][W3]::PostMessage([W3]::GetDlgItem($d, 7), 0x00F5, [IntPtr]0, [IntPtr]0)   # BM_CLICK on No
Start-Sleep -Milliseconds 1000
$p.Refresh(); $t = $p.MainWindowTitle; Write-Output "  title: $t"
Check "  No leaves the window empty" ($t -eq 'Ogre Battle Gaiden: Prince of Zenobia (English)')
[void][W3]::PostMessage($p.MainWindowHandle, 0x0010, [IntPtr]0, [IntPtr]0)
$p.WaitForExit(10000) | Out-Null
Check "  closes cleanly (exit $($p.ExitCode))" ($p.HasExited -and $p.ExitCode -eq 0)

# 3. F12 asks before resetting; No keeps the game
$p = Start-Process -FilePath "$AppDir\zenobia.exe" -ArgumentList "`"$JapaneseRom`"" -PassThru
$null = $p.Handle
for ($i = 0; $i -lt 50 -and $p.MainWindowHandle -eq [IntPtr]::Zero; $i++) { Start-Sleep -Milliseconds 100; $p.Refresh() }
Start-Sleep -Milliseconds 800
[void][W3]::PostMessage($p.MainWindowHandle, 0x100, [IntPtr]0x7B, [IntPtr]1)   # F12
$d = WaitDialog $p
$msg = if ($d -ne [IntPtr]::Zero) { [W3]::Text([W3]::GetDlgItem($d, 0xFFFF)) } else { '' }
Write-Output "  dialog text: $($msg -replace "`r?`n", ' | ')"
Check "F12 asks for confirmation" ($msg -match 'Reset the game')
[void][W3]::PostMessage([W3]::GetDlgItem($d, 7), 0x00F5, [IntPtr]0, [IntPtr]0)   # No
Start-Sleep -Milliseconds 500
$p.Refresh(); Check "  No keeps playing" (-not ($p.MainWindowTitle -match 'Game reset'))
[void][W3]::PostMessage($p.MainWindowHandle, 0x100, [IntPtr]0x7B, [IntPtr]1)
$d = WaitDialog $p
[void][W3]::PostMessage([W3]::GetDlgItem($d, 6), 0x00F5, [IntPtr]0, [IntPtr]0)   # Yes
Start-Sleep -Milliseconds 500
$p.Refresh(); $t = $p.MainWindowTitle; Write-Output "  title: $t"
Check "  Yes resets" ($t -match 'Game reset')
[void][W3]::PostMessage($p.MainWindowHandle, 0x0010, [IntPtr]0, [IntPtr]0)
$p.WaitForExit(10000) | Out-Null
Check "  closes cleanly (exit $($p.ExitCode))" ($p.HasExited -and $p.ExitCode -eq 0)

$fails = ($results | Where-Object { $_.StartsWith('FAIL') }).Count
Write-Output "checks: $($results.Count), failed: $fails"
