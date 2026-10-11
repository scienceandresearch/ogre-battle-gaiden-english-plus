# The player's extras in the real window: the menu bar (File, Options,
# Cheats, Help), Options > Console date and When the player starts (check
# marks and zenobia.ini), the Cheats menu (refused without a game; applied to
# a game in progress, checked in a save state made afterwards), File >
# Continue where I left off (nothing yet; the question at the next start; the
# menu command), File > Import saved game (the dialog opens in the Chapter
# saves folder; the question; the backup; the message) and Help > Player's
# guide when the guide is missing (the found case only starts the browser).
# Opens real windows for about a minute.
# AppDir: a scratch folder with a copy of zenobia.exe (any name, see ExeName)
# and ogre_en.bps; the script writes zenobia.ini, "Chapter saves", saves and
# states there.
#   powershell -File gui_extras_test.ps1 -AppDir DIR [-ExeName zen_extras_check.exe]
#       -Rom JAPANESE_ROM -State GAME_STATE -Save CHAPTER_SAVE -Out OUTDIR
# GAME_STATE: a state of a game in progress made with this build, for example
# build/states/r2-story-early-s6_cleared_scenario_map.state (its Chaos Frame
# must be 10-90). CHAPTER_SAVE: a save from build/catalog.
param([string]$AppDir, [string]$ExeName = 'zenobia.exe', [string]$Rom, [string]$State, [string]$Save, [string]$Out)
$ErrorActionPreference = 'Stop'
Add-Type @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
public static class W6 {
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
  [DllImport("user32.dll")] public static extern uint GetMenuState(IntPtr m, uint id, uint flags);
  [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetMenuString(IntPtr m, uint item, StringBuilder sb, int n, uint flags);
  public static List<IntPtr> Dialogs(uint pid) {
    var r = new List<IntPtr>();
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p);
      if (p == pid && IsWindowVisible(h)) { var sb = new StringBuilder(64); GetClassName(h, sb, 64); if (sb.ToString() == "#32770") r.Add(h); }
      return true; }, IntPtr.Zero);
    return r;
  }
  public static IntPtr Player(uint pid) {
    IntPtr found = IntPtr.Zero;
    EnumWindows((h, l) => { uint p; GetWindowThreadProcessId(h, out p);
      if (p == pid && IsWindowVisible(h)) { var sb = new StringBuilder(64); GetClassName(h, sb, 64); if (sb.ToString() == "ZenobiaPlayerWindow") { found = h; return false; } }
      return true; }, IntPtr.Zero);
    return found;
  }
  public static string Text(IntPtr h) { var sb = new StringBuilder(8192); SendMessage(h, 0x000D, (IntPtr)8192, sb); return sb.ToString(); }
  public static string Title(IntPtr h) { var sb = new StringBuilder(512); GetWindowText(h, sb, 512); return sb.ToString(); }
  public static IntPtr Child(IntPtr d, string cls, int id, string text) {
    IntPtr found = IntPtr.Zero;
    EnumChildWindows(d, (h, l) => { var c = new StringBuilder(64); GetClassName(h, c, 64);
      if (c.ToString() == cls && IsWindowVisible(h) && (id == -1 || GetDlgCtrlID(h) == id) && (text == null || Text(h).StartsWith(text))) { found = h; return false; }
      return true; }, IntPtr.Zero);
    return found;
  }
  public static string MenuText(IntPtr m, int pos) { var sb = new StringBuilder(128); GetMenuString(m, (uint)pos, sb, 128, 0x400); return sb.ToString(); }
}
"@
$WM_KEYDOWN = 0x100; $WM_KEYUP = 0x101; $WM_COMMAND = 0x111; $WM_CLOSE = 0x10; $BM_CLICK = 0xF5; $WM_SETTEXT = 0xC
$IDM_IMPORT_SAVE = 104; $IDM_CONTINUE = 105; $IDM_GUIDE = 203
$IDM_DATE_PC = 301; $IDM_DATE_DEC25 = 302; $IDM_DATE_JUN6 = 303
$IDM_RESUME_ASK = 311; $IDM_RESUME_YES = 312; $IDM_RESUME_NO = 313; $IDM_CHEAT_FIRST = 401
$STATE_RAM = 0xC0; $FUNDS = 0x468E; $REPUTATION = 0x4694; $COUNT = 0x4692; $CHARS = 0x46AA
$results = New-Object System.Collections.ArrayList
function Check($name, $cond) { $s = if ($cond) { 'ok  ' } else { 'FAIL' }; [void]$results.Add("$s $name"); Write-Output "$s $name" }
function WaitDialog($p, $title, $ms = 6000) {
  for ($i = 0; $i -lt $ms / 100; $i++) {
    foreach ($d in [W6]::Dialogs([uint32]$p.Id)) { if (-not $title -or [W6]::Title($d) -eq $title) { return $d } }
    Start-Sleep -Milliseconds 100
  }
  return [IntPtr]::Zero
}
function BoxText($d) { if ($d -eq [IntPtr]::Zero) { return '' }; [W6]::Text([W6]::GetDlgItem($d, 0xFFFF)) }
function ClickButton($d, $text) { $b = [W6]::Child($d, 'Button', -1, $text); if ($b -ne [IntPtr]::Zero) { [void][W6]::PostMessage($b, $BM_CLICK, [IntPtr]0, [IntPtr]0) }; Start-Sleep -Milliseconds 400 }
function Key($h, $vk) {
  [void][W6]::PostMessage($h, $WM_KEYDOWN, [IntPtr]$vk, [IntPtr]1); Start-Sleep -Milliseconds 120
  [void][W6]::PostMessage($h, $WM_KEYUP, [IntPtr]$vk, [IntPtr]0xC0000001); Start-Sleep -Milliseconds 300
}
function Command($h, $id) { [void][W6]::PostMessage($h, $WM_COMMAND, [IntPtr]$id, [IntPtr]0); Start-Sleep -Milliseconds 300 }
function Checked($h, $id) { ([W6]::GetMenuState([W6]::GetMenu($h), [uint32]$id, 0) -band 0x8) -ne 0 }
function IniText { [System.IO.File]::ReadAllText("$AppDir\zenobia.ini") }
function Start-Player {
  $p = Start-Process -FilePath $exe -PassThru
  $null = $p.Handle
  [void]$script:procs.Add($p)
  return $p
}
function WaitWindow($p) {
  $h = [IntPtr]::Zero
  for ($i = 0; $i -lt 60 -and $h -eq [IntPtr]::Zero; $i++) { Start-Sleep -Milliseconds 100; $h = [W6]::Player([uint32]$p.Id) }
  Start-Sleep -Milliseconds 900
  return $h
}
function Close-Player($p) {
  $p.Refresh()
  if (-not $p.HasExited) { [void][W6]::PostMessage([W6]::Player([uint32]$p.Id), $WM_CLOSE, [IntPtr]0, [IntPtr]0) }
  $p.WaitForExit(10000) | Out-Null
  return ($p.HasExited -and $p.ExitCode -eq 0)
}
function Ram($path) { $b = [System.IO.File]::ReadAllBytes($path); return $b[$STATE_RAM..($STATE_RAM + 0xFFFF)] }
function U32($m, $a) { [uint32]$m[$a] + ([uint32]$m[$a + 1] -shl 8) + ([uint32]$m[$a + 2] -shl 16) + ([uint32]$m[$a + 3] -shl 24) }

New-Item -ItemType Directory -Force $Out | Out-Null
$AppDir = (Resolve-Path $AppDir).Path.TrimEnd('\')
$Out = (Resolve-Path $Out).Path.TrimEnd('\')
$Rom = (Resolve-Path $Rom).Path
$exe = Join-Path $AppDir $ExeName
$procs = New-Object System.Collections.ArrayList
$catalog = Join-Path $AppDir 'Chapter saves'
$saveFile = Join-Path $AppDir ('saves\' + [System.IO.Path]::GetFileNameWithoutExtension($Rom) + '.sav')
try {
  foreach ($f in 'saves', 'states', 'Chapter saves') { if (Test-Path "$AppDir\$f") { Remove-Item -Recurse -Force "$AppDir\$f" } }
  if (Test-Path "$AppDir\Player's Guide.html") { Remove-Item "$AppDir\Player's Guide.html" }
  New-Item -ItemType Directory -Force $catalog, "$AppDir\saves", "$AppDir\states" | Out-Null
  $chapter = Join-Path $catalog 'test chapter save.sav'
  Copy-Item $Save $chapter
  $new = [System.IO.File]::ReadAllBytes($Save)
  $old = [byte[]]$new.Clone(); $old[$old.Length - 1] = $old[$old.Length - 1] -bxor 0xFF   # another save: last byte changed
  [System.IO.File]::WriteAllBytes($saveFile, $old)
  $t = "[video]`r`nscale=3`r`n[rom]`r`nlast=$Rom`r`n[general]`r`nresume=ask`r`n"
  [System.IO.File]::WriteAllText("$AppDir\zenobia.ini", $t, [System.Text.Encoding]::Unicode)

  # 1. first start: nothing to continue yet, so no question; the menus
  $p = Start-Player
  $h = WaitWindow $p
  Check "first start: the game runs, no question ($([W6]::Title($h)))" ($h -ne [IntPtr]::Zero -and (WaitDialog $p $null 800) -eq [IntPtr]::Zero)
  $m = [W6]::GetMenu($h)
  $bar = (0..([W6]::GetMenuItemCount($m) - 1) | ForEach-Object { [W6]::MenuText($m, $_) }) -join ' | '
  $opt = [W6]::GetSubMenu($m, 1)
  $optItems = (0..([W6]::GetMenuItemCount($opt) - 1) | ForEach-Object { [W6]::MenuText($opt, $_) }) -join ' | '
  $dateItems = (0..2 | ForEach-Object { [W6]::MenuText([W6]::GetSubMenu($opt, 0), $_) }) -join ' | '
  $startItems = (0..2 | ForEach-Object { [W6]::MenuText([W6]::GetSubMenu($opt, 1), $_) }) -join ' | '
  $cheat = [W6]::GetSubMenu($m, 2)
  $cheatItems = (0..([W6]::GetMenuItemCount($cheat) - 1) | ForEach-Object { [W6]::MenuText($cheat, $_) }) -join ' | '
  Write-Output "  [$bar] Options: [$optItems] [$dateItems] [$startItems] Cheats: [$cheatItems]"
  Check "  menu bar: File, Options, Cheats, Help" ($bar -eq '&File | &Options | &Cheats | &Help')
  Check "  Options: Console date (PC, 25 December, 6 June), When the player starts (ask, continue, title)" (
    $optItems -eq 'Console &date | &When the player starts' -and $dateItems -eq "The &PC's date | 25 &December | 6 &June" -and
    $startItems -eq '&Ask to continue where I left off | &Continue where I left off | Start at the &title screen')
  Check "  Cheats: the five" ($cheatItems -eq 'Add 100,000 &goth | &Heal every character | &Level up after the next battle | Reputation &+10 | Reputation &-10')
  Check "  check marks: the PC's date, ask" ((Checked $h $IDM_DATE_PC) -and -not (Checked $h $IDM_DATE_DEC25) -and (Checked $h $IDM_RESUME_ASK) -and -not (Checked $h $IDM_RESUME_NO))

  # 2. Options > Console date
  Command $h $IDM_DATE_DEC25
  Check "Console date > 25 December: checked, in zenobia.ini, shown ($([W6]::Title($h)))" (
    (Checked $h $IDM_DATE_DEC25) -and -not (Checked $h $IDM_DATE_PC) -and (IniText) -match 'console_date=12-25' -and [W6]::Title($h) -match '25 December')
  Command $h $IDM_DATE_JUN6
  Check "  6 June" ((Checked $h $IDM_DATE_JUN6) -and -not (Checked $h $IDM_DATE_DEC25) -and (IniText) -match 'console_date=06-06')
  Command $h $IDM_DATE_PC
  Check "  the PC's date again: an empty value" ((Checked $h $IDM_DATE_PC) -and (IniText) -match "console_date=\r?\n")

  # 3. Options > When the player starts
  Command $h $IDM_RESUME_YES
  Check "When the player starts > Continue: checked, resume=yes" ((Checked $h $IDM_RESUME_YES) -and -not (Checked $h $IDM_RESUME_ASK) -and (IniText) -match 'resume=yes')
  Command $h $IDM_RESUME_NO
  Check "  Start at the title screen: resume=no" ((Checked $h $IDM_RESUME_NO) -and (IniText) -match 'resume=no')
  Command $h $IDM_RESUME_ASK
  Check "  Ask: resume=ask" ((Checked $h $IDM_RESUME_ASK) -and (IniText) -match 'resume=ask')

  # 4. no game in progress yet (power-on): cheats and Continue explain; the guide is missing
  Command $h $IDM_CHEAT_FIRST
  $d = WaitDialog $p $null; $msg = BoxText $d
  Check "Cheats before a game is in progress: explained" ($msg -match 'Start a new game or load a saved game first')
  ClickButton $d 'OK'
  Command $h $IDM_CONTINUE
  $d = WaitDialog $p $null; $msg = BoxText $d
  Check "File > Continue where I left off, nothing yet: explained" ($msg -match 'There is no earlier session of this game to continue yet')
  ClickButton $d 'OK'
  Command $h $IDM_GUIDE
  $d = WaitDialog $p $null; $msg = BoxText $d
  Check "Help > Player's guide without the file: explained" ($msg -match "The Player's Guide was not found next to zenobia.exe")
  ClickButton $d 'OK'

  # 5. a game in progress (state 0, F9), paused (P); each cheat; then a state (F5) to check them
  Copy-Item $State "$AppDir\states\slot0.state"
  $before = Ram $State
  Key $h 0x78   # F9
  Check "F9 loads the game in progress ($([W6]::Title($h)))" ([W6]::Title($h) -match 'State 0 loaded')
  Key $h 0x50   # P
  $titles = @()
  for ($i = 0; $i -lt 5; $i++) { Command $h ($IDM_CHEAT_FIRST + $i); $titles += [W6]::Title($h) }
  Write-Output "  $($titles -join ' / ')"
  Check "  each cheat says what it did, no message box" ($titles[0] -match '\+100,000 goth' -and $titles[1] -match 'healed' -and
    $titles[2] -match 'levels up' -and $titles[3] -match 'reputation \+10' -and $titles[4] -match 'reputation -10' -and (WaitDialog $p $null 300) -eq [IntPtr]::Zero)
  Key $h 0x74   # F5
  $after = Ram "$AppDir\states\slot0.state"
  $n = $before[$COUNT]
  Check "  in the saved state: +100,000 goth, reputation back where it was, experience 99" (
    (U32 $after $FUNDS) -eq [Math]::Min(99999999, (U32 $before $FUNDS) + 100000) -and $after[$REPUTATION] -eq $before[$REPUTATION] -and
    @(0..($n - 1) | Where-Object { $after[$CHARS + 18 * $_ + 16] -ne 99 }).Count -eq 0)
  Key $h 0x50   # P: run again
  Check "  quits cleanly" (Close-Player $p)
  Check "  quitting wrote states\resume.state" (Test-Path "$AppDir\states\resume.state")

  # 6. the next start asks; Yes continues
  $p = Start-Player
  $d = WaitDialog $p $null 8000; $msg = BoxText $d
  Check "next start: asks to continue where you left off" ($msg -match 'Continue where you left off last time\?')
  ClickButton $d '&Yes'
  $h = WaitWindow $p
  Check "  Yes: continued ($([W6]::Title($h)))" ([W6]::Title($h) -match 'Continued where you left off')
  Command $h $IDM_CONTINUE
  $d = WaitDialog $p $null; $msg = BoxText $d
  Check "  File > Continue where I left off asks first" ($msg -match 'Go back to where you were when you last quit the player\?')
  ClickButton $d '&No'

  # 7. File > Import saved game
  Command $h $IDM_IMPORT_SAVE
  $d = WaitDialog $p 'Import a saved game'
  $addr = [W6]::Text([W6]::Child($d, 'ToolbarWindow32', -1, 'Address: '))
  Check "File > Import saved game: the dialog opens in the Chapter saves folder ($addr)" ($d -ne [IntPtr]::Zero -and $addr -eq "Address: $catalog")
  [void][W6]::SendMessage([W6]::Child($d, 'Edit', 1148, $null), $WM_SETTEXT, [IntPtr]0, $chapter)
  ClickButton $d '&Open'
  $q = WaitDialog $p $null; $msg = BoxText $q
  Check "  asks first, naming the file" ($msg -match 'Import this saved game\?' -and $msg.Contains($chapter))
  ClickButton $q '&Yes'
  $d = WaitDialog $p $null; $msg = BoxText $d
  Write-Output "  message: $($msg -replace "`r?`n", ' | ')"
  Check "  done: Load on the title screen; the backup named" ($msg -match 'Choose Load on the title screen' -and $msg -match 'before import')
  ClickButton $d 'OK'
  $backup = @(Get-ChildItem "$AppDir\saves" -Filter '*(before import *).sav')
  Check "  the save is the chapter save; the previous one is in the backup" (
    [System.Linq.Enumerable]::SequenceEqual([byte[]][System.IO.File]::ReadAllBytes($saveFile), [byte[]]$new) -and $backup.Count -eq 1 -and
    [System.Linq.Enumerable]::SequenceEqual([byte[]][System.IO.File]::ReadAllBytes($backup[0].FullName), [byte[]]$old))
  Check "  the game restarted ($([W6]::Title($h)))" ([W6]::Title($h) -match 'Saved game imported')
  Check "  quits cleanly" (Close-Player $p)
} finally {
  foreach ($q in $procs) { $q.Refresh(); if (-not $q.HasExited) { Stop-Process -Id $q.Id -Force -ErrorAction SilentlyContinue } }
}
$fails = ($results | Where-Object { $_.StartsWith('FAIL') }).Count
Write-Output "checks: $($results.Count), failed: $fails"
