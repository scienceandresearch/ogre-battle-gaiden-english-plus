# The menu bar and the zip support in the real window: Open game with a .zip
# (Open dialog), the zip remembered for the next start, menu items and
# shortcuts, Alt/F10 not taking keys from the game, Help > Controls / About,
# File > Save English ROM (the dialog opens in the game's folder with the
# proposed name; the saved file is checked; the original game file cannot be
# overwritten; Ctrl+S; the explanations with no game and untranslated), the
# menu bar hidden in fullscreen, the client area at scales 1-4, File > Exit.
# Opens real windows for about a minute.
# AppDir: a scratch folder with a copy of zenobia.exe (any name, see ExeName)
# and ogre_en.bps; the script writes zenobia.ini, game.zip and states there.
# Use a new exe name on machines where a tool such as PersistentWindows
# restores window sizes by program name.
#   powershell -File gui_menu_test.ps1 -AppDir DIR [-ExeName zen_menu_check.exe]
#       -Rom JAPANESE_ROM -English ENGLISH_ROM -Out OUTDIR
param([string]$AppDir, [string]$ExeName = 'zenobia.exe', [string]$Rom, [string]$English, [string]$Out)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
Add-Type @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class W5 {
  public delegate bool CB(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(CB cb, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr p, CB cb, IntPtr l);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder sb, int n);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder sb, int n);
  [DllImport("user32.dll")] public static extern int GetDlgCtrlID(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetDlgItem(IntPtr h, int id);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint msg, IntPtr w, IntPtr l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr w, StringBuilder l);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern IntPtr SendMessage(IntPtr h, uint msg, IntPtr w, string l);
  [DllImport("user32.dll")] public static extern IntPtr GetMenu(IntPtr h);
  [DllImport("user32.dll")] public static extern IntPtr GetSubMenu(IntPtr m, int pos);
  [DllImport("user32.dll")] public static extern int GetMenuItemCount(IntPtr m);
  [DllImport("user32.dll")] public static extern uint GetMenuItemID(IntPtr m, int pos);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetMenuString(IntPtr m, uint item, StringBuilder sb, int n, uint flags);
  [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] public static extern IntPtr MonitorFromWindow(IntPtr h, uint flags);
  [DllImport("user32.dll")] public static extern bool GetMonitorInfo(IntPtr m, ref MONITORINFO mi);
  [DllImport("user32.dll")] public static extern bool GetGUIThreadInfo(uint tid, ref GUITHREADINFO gi);
  [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr ctx);
  [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left, Top, Right, Bottom; }
  [StructLayout(LayoutKind.Sequential)] public struct MONITORINFO { public int cbSize; public RECT rcMonitor, rcWork; public uint dwFlags; }
  [StructLayout(LayoutKind.Sequential)] public struct GUITHREADINFO {
    public int cbSize; public uint flags; public IntPtr hwndActive, hwndFocus, hwndCapture, hwndMenuOwner, hwndMoveSize, hwndCaret; public RECT rcCaret; }
  public static List<IntPtr> Dialogs(uint pid) {
    var r = new List<IntPtr>();
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p);
      if (p == pid && IsWindowVisible(h)) { var sb = new StringBuilder(64); GetClassName(h, sb, 64); if (sb.ToString() == "#32770") r.Add(h); }
      return true; }, IntPtr.Zero);
    return r;
  }
  // the player's own window (class ZenobiaPlayerWindow) of a process
  public static IntPtr Player(uint pid) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p);
      if (p == pid && IsWindowVisible(h)) { var sb = new StringBuilder(64); GetClassName(h, sb, 64); if (sb.ToString() == "ZenobiaPlayerWindow") { found = h; return false; } }
      return true; }, IntPtr.Zero);
    return found;
  }
  public static uint Thread(IntPtr h) { uint p; return GetWindowThreadProcessId(h, out p); }
  public static string Text(IntPtr h) { var sb = new StringBuilder(8192); SendMessage(h, 0x000D, (IntPtr)8192, sb); return sb.ToString(); }
  public static string Title(IntPtr h) { var sb = new StringBuilder(512); GetWindowText(h, sb, 512); return sb.ToString(); }
  // a visible child by class, control ID (-1 = any) and text prefix (null = any)
  public static IntPtr Child(IntPtr d, string cls, int id, string text) {
    IntPtr found = IntPtr.Zero;
    EnumChildWindows(d, (h, l) => { var c = new StringBuilder(64); GetClassName(h, c, 64);
      if (c.ToString() == cls && IsWindowVisible(h) && (id == -1 || GetDlgCtrlID(h) == id) && (text == null || Text(h).StartsWith(text))) { found = h; return false; }
      return true; }, IntPtr.Zero);
    return found;
  }
  public static string MenuText(IntPtr m, int pos) { var sb = new StringBuilder(128); GetMenuString(m, (uint)pos, sb, 128, 0x400); return sb.ToString(); }
  public static uint MenuFlags(uint tid) { var gi = new GUITHREADINFO(); gi.cbSize = Marshal.SizeOf(gi); GetGUIThreadInfo(tid, ref gi); return gi.flags; }
}
"@
[void][W5]::SetThreadDpiAwarenessContext([IntPtr](-4))   # physical pixels, like the per-monitor DPI aware player
$WM_KEYDOWN = 0x100; $WM_KEYUP = 0x101; $WM_SYSKEYDOWN = 0x104; $WM_SYSKEYUP = 0x105
$WM_COMMAND = 0x111; $WM_CLOSE = 0x10; $BM_CLICK = 0xF5; $WM_SETTEXT = 0xC
$IDM_OPEN = 101; $IDM_SAVE_ENGLISH = 102; $IDM_EXIT = 103; $IDM_CONTROLS = 201; $IDM_ABOUT = 202
$ENGLISH_NAME = 'Ogre Battle Gaiden - Prince of Zenobia (English).ngc'
$results = New-Object System.Collections.ArrayList
function Check($name, $cond) { $s = if ($cond) { 'ok  ' } else { 'FAIL' }; [void]$results.Add("$s $name"); Write-Output "$s $name" }
function WaitDialog($p, $title, $ms = 6000) {
  for ($i = 0; $i -lt $ms / 100; $i++) {
    foreach ($d in [W5]::Dialogs([uint32]$p.Id)) { if (-not $title -or [W5]::Title($d) -eq $title) { return $d } }
    Start-Sleep -Milliseconds 100
  }
  return [IntPtr]::Zero
}
function BoxText($d) { if ($d -eq [IntPtr]::Zero) { return '' }; [W5]::Text([W5]::GetDlgItem($d, 0xFFFF)) }
function ClickButton($d, $text) { $b = [W5]::Child($d, 'Button', -1, $text); if ($b -ne [IntPtr]::Zero) { [void][W5]::PostMessage($b, $BM_CLICK, [IntPtr]0, [IntPtr]0) }; Start-Sleep -Milliseconds 400 }
function Key($h, $vk) {
  [void][W5]::PostMessage($h, $WM_KEYDOWN, [IntPtr]$vk, [IntPtr]1); Start-Sleep -Milliseconds 120
  [void][W5]::PostMessage($h, $WM_KEYUP, [IntPtr]$vk, [IntPtr]0xC0000001); Start-Sleep -Milliseconds 250
}
function Command($h, $id) { [void][W5]::PostMessage($h, $WM_COMMAND, [IntPtr]$id, [IntPtr]0) }
function Client($h) { $r = New-Object W5+RECT; [void][W5]::GetClientRect($h, [ref]$r); "$($r.Right)x$($r.Bottom)" }
function WinRect($h) { $r = New-Object W5+RECT; [void][W5]::GetWindowRect($h, [ref]$r); "$($r.Left),$($r.Top),$($r.Right),$($r.Bottom)" }
function Ini($scale, $last) {
  $t = "[video]`r`nscale=$scale`r`n[rom]`r`nlast=$last`r`n"
  [System.IO.File]::WriteAllText("$AppDir\zenobia.ini", $t, [System.Text.Encoding]::Unicode)   # UTF-16 with BOM, as the player writes it
}
function Start-Player($argline) {
  $p = if ($argline) { Start-Process -FilePath $exe -ArgumentList $argline -PassThru } else { Start-Process -FilePath $exe -PassThru }
  $null = $p.Handle
  [void]$script:procs.Add($p)
  return $p
}
function WaitWindow($p) {
  $h = [IntPtr]::Zero
  for ($i = 0; $i -lt 60 -and $h -eq [IntPtr]::Zero; $i++) { Start-Sleep -Milliseconds 100; $h = [W5]::Player([uint32]$p.Id) }
  Start-Sleep -Milliseconds 700
  return $h
}
function Close-Player($p) {
  $p.Refresh()
  if (-not $p.HasExited) { [void][W5]::PostMessage([W5]::Player([uint32]$p.Id), $WM_CLOSE, [IntPtr]0, [IntPtr]0) }
  $p.WaitForExit(10000) | Out-Null
  return ($p.HasExited -and $p.ExitCode -eq 0)
}

New-Item -ItemType Directory -Force $Out | Out-Null
$AppDir = (Resolve-Path $AppDir).Path.TrimEnd('\')
$Out = (Resolve-Path $Out).Path.TrimEnd('\')
$exe = Join-Path $AppDir $ExeName
$zip = Join-Path $AppDir 'game.zip'
$procs = New-Object System.Collections.ArrayList
$enSha1 = (Get-FileHash -Algorithm SHA1 $English).Hash.ToLower()
try {
  # the test zip: the original ROM, compressed by .NET's own zip writer
  if (Test-Path $zip) { Remove-Item $zip }
  $za = [System.IO.Compression.ZipFile]::Open($zip, 'Create')
  [void][System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($za, $Rom, 'Ogre Battle Gaiden (Japan).ngc', 'Optimal')
  $za.Dispose()
  $zipHash = (Get-FileHash $zip).Hash
  foreach ($f in 'saves', 'states') { if (Test-Path "$AppDir\$f") { Remove-Item -Recurse -Force "$AppDir\$f" } }

  # 1. no game yet: the Open dialog takes the zip
  Ini 3 ''
  $p = Start-Player $null
  $d = WaitDialog $p 'Open the Ogre Battle Gaiden ROM'
  Check "no game: the Open dialog appears" ($d -ne [IntPtr]::Zero)
  [void][W5]::SendMessage([W5]::Child($d, 'Edit', 1148, $null), $WM_SETTEXT, [IntPtr]0, $zip)
  ClickButton $d '&Open'
  $h = WaitWindow $p
  Start-Sleep -Milliseconds 800
  $t = [W5]::Title($h); Write-Output "  title: $t"
  Check "  the .zip opens and runs (title shows the slot)" ($t -match 'Slot 0' -and -not ($t -match 'untranslated'))
  $ini = [System.IO.File]::ReadAllText("$AppDir\zenobia.ini")
  Check "  the zip is remembered as the last game" ($ini -match [regex]::Escape("last=$zip"))

  # 2. the menu bar
  $m = [W5]::GetMenu($h)
  Check "menu bar present" ($m -ne [IntPtr]::Zero)
  $file = [W5]::GetSubMenu($m, 0); $help = [W5]::GetSubMenu($m, 1)
  $bar = "$([W5]::MenuText($m, 0)) | $([W5]::MenuText($m, 1))"
  $fileItems = (0..([W5]::GetMenuItemCount($file) - 1) | ForEach-Object { [W5]::MenuText($file, $_) }) -join ' | '
  $helpItems = (0..([W5]::GetMenuItemCount($help) - 1) | ForEach-Object { [W5]::MenuText($help, $_) }) -join ' | '
  Write-Output "  menus: [$bar] File: [$fileItems] Help: [$helpItems]"
  Check "  File and Help" ($bar -eq '&File | &Help')
  Check "  File: Open game (Ctrl+O), Save English ROM (Ctrl+S), Exit (Esc)" ($fileItems -eq "&Open game...`tCtrl+O | &Save English ROM...`tCtrl+S |  | E&xit`tEsc")
  Check "  Help: Controls (F1), About" ($helpItems -eq "&Controls`tF1 | &About")
  $size = Client $h; Write-Output "  client $size"
  Check "  client area 480x456 at scale 3 (menu bar outside it)" ($size -eq '480x456')

  # 3. Alt and F10 do not open the menu; the keys stay with the game and the hotkeys
  $tid = [W5]::Thread($h)
  [void][W5]::PostMessage($h, $WM_SYSKEYDOWN, [IntPtr]0x12, [IntPtr]0x20380001); Start-Sleep -Milliseconds 100
  [void][W5]::PostMessage($h, $WM_SYSKEYUP, [IntPtr]0x12, [IntPtr]0xC0380001); Start-Sleep -Milliseconds 300
  $f1 = [W5]::MenuFlags($tid)
  [void][W5]::PostMessage($h, $WM_SYSKEYDOWN, [IntPtr]0x79, [IntPtr]0x00440001); Start-Sleep -Milliseconds 100
  [void][W5]::PostMessage($h, $WM_SYSKEYUP, [IntPtr]0x79, [IntPtr]0xC0440001); Start-Sleep -Milliseconds 300
  $f2 = [W5]::MenuFlags($tid)
  Check "Alt and F10 do not enter the menu (thread flags $f1, $f2)" ((($f1 -band 0x14) -eq 0) -and (($f2 -band 0x14) -eq 0))
  # had either opened the menu bar, Down + Enter would now choose File > Open game
  Key $h 0x28; Key $h 0x0D   # Down, Enter (game buttons)
  Check "  then Down + Enter go to the game: no menu, no dialog" ((([W5]::MenuFlags($tid) -band 0x14) -eq 0) -and (WaitDialog $p $null 800) -eq [IntPtr]::Zero)
  Key $h 0x74   # F5
  $t = [W5]::Title($h); Check "  F5 still saves a state" ($t -match 'State 0 saved')
  Key $h 0x78   # F9
  $t = [W5]::Title($h); Check "  F9 still loads it" ($t -match 'State 0 loaded')

  # 4. Help: Controls (F1 and the menu), About
  Key $h 0x70   # F1
  $d = WaitDialog $p $null; $msg = BoxText $d
  Check "F1 shows the controls, with Ctrl+S" ($msg -match 'Controls' -and $msg -match 'Ctrl\+S: save the English ROM')
  ClickButton $d 'OK'
  Command $h $IDM_CONTROLS
  $d = WaitDialog $p $null; $msg2 = BoxText $d
  Check "Help > Controls shows the same text" ($msg2 -eq $msg -and $msg2 -ne '')
  ClickButton $d 'OK'
  Command $h $IDM_ABOUT
  $d = WaitDialog $p $null; $msg = BoxText $d
  Write-Output "  about: $(($msg -split "`n")[0..1] -join ' | ')"
  Check "Help > About: version, the game file, the folder" ($msg -match 'Version \d+\.\d+\.\d+' -and $msg.Contains($zip) -and $msg -match 'running in English' -and $msg.Contains($AppDir))
  ClickButton $d 'OK'

  # 5. File > Save English ROM
  Command $h $IDM_SAVE_ENGLISH
  $d = WaitDialog $p 'Save the English ROM'
  Check "File > Save English ROM opens a Save dialog" ($d -ne [IntPtr]::Zero)
  $edit = [W5]::Child($d, 'Edit', 1001, $null)
  $name = [W5]::Text($edit); $addr = [W5]::Text([W5]::Child($d, 'ToolbarWindow32', -1, 'Address: '))
  Write-Output "  proposed: '$name' in '$addr'"
  Check "  proposed name" ($name -eq $ENGLISH_NAME)
  Check "  in the game file's folder" ($addr -eq "Address: $AppDir")
  $saved = Join-Path $Out 'saved english.ngc'
  if (Test-Path $saved) { Remove-Item $saved }
  [void][W5]::SendMessage($edit, $WM_SETTEXT, [IntPtr]0, $saved)
  ClickButton $d '&Save'
  $d = WaitDialog $p $null; $msg = BoxText $d
  Write-Output "  message: $($msg -replace "`r?`n", ' | ')"
  Check "  confirmation names the file and the checked SHA-1" ($msg -match 'The English ROM was saved' -and $msg.Contains($saved) -and $msg.Contains($enSha1))
  ClickButton $d 'OK'
  Check "  the file is the English ROM" ((Test-Path $saved) -and (Get-FileHash -Algorithm SHA1 $saved).Hash.ToLower() -eq $enSha1)
  # Ctrl+S opens it too; Cancel saves nothing
  [void][W5]::PostMessage($h, $WM_KEYDOWN, [IntPtr]0x11, [IntPtr]0x001D0001); Start-Sleep -Milliseconds 80
  [void][W5]::PostMessage($h, $WM_KEYDOWN, [IntPtr]0x53, [IntPtr]0x001F0001)
  $d = WaitDialog $p 'Save the English ROM'
  Check "Ctrl+S opens the Save dialog" ($d -ne [IntPtr]::Zero)
  ClickButton $d 'Cancel'
  [void][W5]::PostMessage($h, $WM_KEYUP, [IntPtr]0x53, [IntPtr]0xC01F0001); [void][W5]::PostMessage($h, $WM_KEYUP, [IntPtr]0x11, [IntPtr]0xC01D0001)
  Start-Sleep -Milliseconds 800
  Check "  Cancel: no message, nothing written" ((WaitDialog $p $null 600) -eq [IntPtr]::Zero)
  # the original game file is never overwritten, even after "Replace? Yes"
  Command $h $IDM_SAVE_ENGLISH
  $d = WaitDialog $p 'Save the English ROM'
  [void][W5]::SendMessage([W5]::Child($d, 'Edit', 1001, $null), $WM_SETTEXT, [IntPtr]0, $zip)
  ClickButton $d '&Save'
  $c = WaitDialog $p 'Confirm Save As'
  Check "  saving over the zip: Windows asks to replace it" ($c -ne [IntPtr]::Zero)
  ClickButton $c '&Yes'
  $d = WaitDialog $p $null; $msg = BoxText $d
  Check "  then the player refuses: the game file you opened" ($msg -match 'This is the game file you opened')
  ClickButton $d 'OK'
  Check "  the zip is unchanged" ((Get-FileHash $zip).Hash -eq $zipHash)

  # 6. fullscreen hides the menu bar
  $before = WinRect $h
  Key $h 0x7A; Start-Sleep -Milliseconds 700   # F11
  $mi = New-Object W5+MONITORINFO; $mi.cbSize = [System.Runtime.InteropServices.Marshal]::SizeOf($mi)
  [void][W5]::GetMonitorInfo([W5]::MonitorFromWindow($h, 1), [ref]$mi)
  $mon = "$($mi.rcMonitor.Right - $mi.rcMonitor.Left)x$($mi.rcMonitor.Bottom - $mi.rcMonitor.Top)"
  $size = Client $h; Write-Output "  fullscreen client $size, monitor $mon"
  Check "fullscreen: no menu bar, the picture fills the monitor" ([W5]::GetMenu($h) -eq [IntPtr]::Zero -and $size -eq $mon)
  Key $h 0x7A; Start-Sleep -Milliseconds 700
  Check "  F11 again: menu bar back, same window and client area" ([W5]::GetMenu($h) -eq $m -and (WinRect $h) -eq $before -and (Client $h) -eq '480x456')

  # 7. File > Exit
  Command $h $IDM_EXIT
  $p.WaitForExit(10000) | Out-Null
  Check "File > Exit quits (exit code $($p.ExitCode))" ($p.HasExited -and $p.ExitCode -eq 0)

  # 8. the next start opens the remembered zip by itself
  $p = Start-Player $null
  $h = WaitWindow $p
  Start-Sleep -Milliseconds 500
  $t = [W5]::Title($h)
  Check "next start: the remembered zip runs, no dialog ($t)" ($t -match 'Slot 0' -and (WaitDialog $p $null 300) -eq [IntPtr]::Zero)
  Check "  closes cleanly" (Close-Player $p)

  # 9. Save English ROM explains itself without a game and untranslated
  Ini 3 ''
  $p = Start-Player $null
  $d = WaitDialog $p 'Open the Ogre Battle Gaiden ROM'
  ClickButton $d 'Cancel'
  $h = WaitWindow $p
  Command $h $IDM_SAVE_ENGLISH
  $d = WaitDialog $p $null; $msg = BoxText $d
  Check "no game: Save English ROM explains (no Save dialog)" ($msg -match 'No game is loaded' -and [W5]::Title($d) -ne 'Save the English ROM')
  ClickButton $d 'OK'
  Check "  closes cleanly" (Close-Player $p)
  $p = Start-Player "`"$zip`" --patch `"$AppDir\no_such.bps`""
  $d = WaitDialog $p $null
  ClickButton $d '&Yes'   # run untranslated
  $h = WaitWindow $p
  Command $h $IDM_SAVE_ENGLISH
  $d = WaitDialog $p $null; $msg = BoxText $d
  Check "untranslated: Save English ROM explains why there is none" ($msg -match 'running untranslated' -and $msg -match 'ogre_en.bps')
  ClickButton $d 'OK'
  Check "  closes cleanly" (Close-Player $p)

  # 10. client area at scales 1-4 (the menu bar is outside it). Each start
  # uses a copy of the exe under a new name: window managers that restore
  # sizes by program name would otherwise bring back the size seen above.
  # At scale 1 Windows may make the window wider than asked (its minimum
  # width for a title bar), as before the menu bar existed.
  foreach ($s in 1, 2, 4) {
    Ini $s $zip
    $copy = Join-Path $AppDir ("zen_scale{0}_{1}.exe" -f $s, (Get-Random -Maximum 999999))
    Copy-Item $exe $copy
    $p = Start-Process -FilePath $copy -ArgumentList "--exit-after 4" -PassThru
    $null = $p.Handle
    [void]$procs.Add($p)
    $h = WaitWindow $p
    $r = New-Object W5+RECT; [void][W5]::GetClientRect($h, [ref]$r)
    $exact = $r.Right -eq 160 * $s -or ($s -eq 1 -and $r.Right -ge 160 -and $r.Right -le 200)
    Check "scale $s`: client $($r.Right)x$($r.Bottom) (asked $(160 * $s)x$(152 * $s)), menu bar present" ($exact -and $r.Bottom -eq 152 * $s -and [W5]::GetMenu($h) -ne [IntPtr]::Zero)
    $p.WaitForExit(15000) | Out-Null
    Remove-Item $copy -ErrorAction SilentlyContinue
  }
} finally {
  foreach ($q in $procs) { $q.Refresh(); if (-not $q.HasExited) { Stop-Process -Id $q.Id -Force -ErrorAction SilentlyContinue } }
}
$fails = ($results | Where-Object { $_.StartsWith('FAIL') }).Count
Write-Output "checks: $($results.Count), failed: $fails"
