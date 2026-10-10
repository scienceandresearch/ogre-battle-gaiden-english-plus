/*
 * Window mode: Win32 window with GDI output, waveOut audio, keyboard and
 * XInput input, hotkeys, cartridge saves and save states, and a menu bar
 * (File: Open game, Save English ROM, Exit; Help: Controls, About) that is
 * hidden in fullscreen. The menu bar is for the mouse only: Alt and F10 do
 * not open it, so every key stays with the game and the hotkeys.
 *
 * Frames are paced with QueryPerformanceCounter at the emulated rate
 * (6144000 / (515 * 199) = 59.95 Hz, from the K2GE line count), with a
 * correction of at most 0.3 % from the audio buffer level. The frame step is
 * the harness loop: set g_input_state, ngp_run_frame(), drain audio_render(),
 * show g_framebuffer.
 */
#include "app.h"
#include "audio.h"
#include "config.h"
#include "input.h"
#include "resource.h"
#include "saves.h"
#include "sha1.h"
#include "video.h"

#include "core/flashchip.h"
#include "core/ngp.h"
#include "core/png.h"

#define COBJMACROS
#include <commdlg.h>
#include <mmsystem.h>
#include <objbase.h>
#include <shellapi.h>
#include <shobjidl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int ngp_shutdown_requested(void);

#define WINDOW_CLASS   L"ZenobiaPlayerWindow"
#define FF_FRAMES      5          /* frames per paced step while fast-forwarding */
#define TIMER_SIZEMOVE 1
#define NUM_SLOTS      10

/* menu commands */
#define IDM_OPEN         101
#define IDM_SAVE_ENGLISH 102
#define IDM_EXIT         103
#define IDM_CONTROLS     201
#define IDM_ABOUT        202

/* File > Save English ROM: proposed name, in the game file's folder */
#define ENGLISH_ROM_NAME L"Ogre Battle Gaiden - Prince of Zenobia (English).ngc"

#ifndef CREATE_WAITABLE_TIMER_HIGH_RESOLUTION
#define CREATE_WAITABLE_TIMER_HIGH_RESOLUTION 0x00000002
#endif
#ifndef WM_DPICHANGED
#define WM_DPICHANGED 0x02E0
#endif

typedef BOOL (WINAPI *SetProcessDpiAwarenessContextFn)(HANDLE ctx);
typedef UINT (WINAPI *GetDpiForWindowFn)(HWND hwnd);
typedef BOOL (WINAPI *AdjustWindowRectExForDpiFn)(LPRECT rc, DWORD style, BOOL menu, DWORD ex, UINT dpi);

static const wchar_t k_hint[] =
    L"Drop your Ogre Battle Gaiden game file (.ngc, or the .zip it came in) onto this window, "
    L"or choose File > Open game (Ctrl+O).\n\n"
    L"The original Japanese game is translated while it loads, using ogre_en.bps "
    L"next to zenobia.exe.\n\nF1 shows the controls.";

static const wchar_t k_help[] =
    L"Controls (keys can be changed in zenobia.ini)\n\n"
    L"D-pad: arrow keys\n"
    L"A: Z        B: X        Option: Enter or C\n"
    L"Gamepad: D-pad or left stick, A/X = A, B/Y = B, Start = Option,\n"
    L"    right trigger = fast-forward\n\n"
    L"Tab (hold): fast-forward\n"
    L"P or Pause: pause / resume\n"
    L"F5 / F9: save / load state in the current slot\n"
    L"F6 / F7: previous / next state slot (0-9)\n"
    L"F11 or Alt+Enter: fullscreen (hides the menu bar)\n"
    L"F12: reset the game\n"
    L"Ctrl+O: open a game file, .ngc or .zip (or drop one onto the window)\n"
    L"Ctrl+S: save the English ROM, for other emulators or a flash cart\n"
    L"F1: these controls\n"
    L"Esc: quit (the cartridge save is written first)\n\n"
    L"The File and Help menus have the same commands.";

typedef struct {
    const Options *opt;
    Config   cfg;
    HWND     hwnd;
    HMENU    menu;             /* the menu bar; detached in fullscreen */
    HANDLE   timer;            /* waitable timer for frame pacing */
    int      have_rom;
    int      untranslated;
    int      english;          /* the image running is the English ROM */
    uint32_t english_crc;      /* its CRC32 (the patch's target) */
    wchar_t *rom_path;         /* the game file loaded (or the .zip holding it) */
    int      paused;           /* by the user */
    int      inactive;         /* the application is in the background */
    int      shutdown_seen;    /* the game powered the console off */
    int      fullscreen;
    WINDOWPLACEMENT saved_wp;
    int      slot;
    int      ff;               /* fast-forward this step */
    int      pad_ff;           /* gamepad right trigger */
    int      in_sizemove;
    int      quitting;
    UINT     dpi;              /* the window's current DPI */
    double   next_frame;       /* QPC time of the next step; 0 = resync */
    double   start_time;
    double   stop_time;        /* when quitting began (statistics) */
    uint64_t frames_run;
    wchar_t  status[192];
    double   status_until;
    wchar_t  title[512];
    int      exit_code;
} App;

static App A;

/* ------------------------------------------------------------------ */
/* Helpers                                                              */
/* ------------------------------------------------------------------ */

static void update_title(void)
{
    wchar_t t[512];
    if (!A.have_rom) {
        swprintf(t, 512, L"%ls", ZEN_TITLE);
    } else {
        swprintf(t, 512, L"%ls%ls - Slot %d", ZEN_TITLE, A.untranslated ? L" [untranslated]" : L"", A.slot);
        if (A.shutdown_seen) wcscat_s(t, 512, L" - Powered off (F12 resets)");
        else if (A.paused) wcscat_s(t, 512, L" - Paused");
        else if (A.inactive && A.cfg.pause_when_inactive) wcscat_s(t, 512, L" - Paused (inactive)");
        else if (A.ff) wcscat_s(t, 512, L" - Fast forward");
    }
    if (A.status[0] && zen_seconds() < A.status_until) {
        wcscat_s(t, 512, L" - ");
        wcscat_s(t, 512, A.status);
    } else {
        A.status[0] = 0;
    }
    if (wcscmp(t, A.title) != 0) {
        wcscpy_s(A.title, 512, t);
        if (A.hwnd) SetWindowTextW(A.hwnd, t);
    }
}

static void set_status(const wchar_t *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    _vsnwprintf_s(A.status, sizeof(A.status) / sizeof(A.status[0]), _TRUNCATE, fmt, ap);
    va_end(ap);
    A.status_until = zen_seconds() + 3.0;
    update_title();
    if (!g_zen_interactive) {
        char *u = zen_to_utf8(A.status);
        zen_logf("zenobia: %s\n", u ? u : "");
        free(u);
    }
}

/* Message box with the game muted and the pacing resynchronised afterwards. */
static int modal_message(UINT flags, int default_answer, const wchar_t *fmt, ...)
{
    wchar_t text[4096];
    va_list ap;
    va_start(ap, fmt);
    _vsnwprintf_s(text, sizeof(text) / sizeof(text[0]), _TRUNCATE, fmt, ap);
    va_end(ap);
    audio_set_muted(1);
    int r = zen_message(A.hwnd, flags, default_answer, L"%ls", text);
    input_clear();
    A.next_frame = 0;
    return r;
}

static int emu_running(void)
{
    return A.have_rom && !A.paused && !A.shutdown_seen && !A.quitting &&
           !(A.inactive && A.cfg.pause_when_inactive);
}

static void update_power_request(int running)
{
    static int last = -1;
    if (running == last) return;
    last = running;
    /* keep the display on while playing (gamepad input does not count as
       user activity for the screen saver) */
    SetThreadExecutionState(running ? (ES_CONTINUOUS | ES_DISPLAY_REQUIRED | ES_SYSTEM_REQUIRED)
                                    : ES_CONTINUOUS);
}

static wchar_t *slot_path(int slot)
{
    wchar_t name[32];
    swprintf(name, 32, L"states\\slot%d.state", slot);
    return zen_path_join(zen_exe_dir(), name);
}

/* saves\<name of the game file>.sav; for a zip, the name of the game file in
   it (so the save stays the same when the zip is extracted). */
static wchar_t *save_path_for(const wchar_t *game_name)
{
    wchar_t *stem = zen_path_stem(game_name);
    if (!stem) return NULL;
    /* a name from a zip may hold characters Windows does not allow in file names */
    for (wchar_t *c = stem; *c; c++)
        if (*c < 0x20 || wcschr(L"<>:\"/\\|?*", *c)) *c = L'_';
    if (!stem[0]) {
        free(stem);
        stem = zen_wcsdup(L"game");
        if (!stem) return NULL;
    }
    size_t n = wcslen(stem) + 16;
    wchar_t *name = (wchar_t *)malloc(n * sizeof(wchar_t));
    wchar_t *path = NULL;
    if (name) {
        swprintf(name, n, L"saves\\%ls.sav", stem);
        path = zen_path_join(zen_exe_dir(), name);
    }
    free(name);
    free(stem);
    return path;
}

/* ------------------------------------------------------------------ */
/* DPI and window size                                                  */
/* ------------------------------------------------------------------ */

static void set_dpi_awareness(void)
{
    HMODULE u = GetModuleHandleW(L"user32.dll");
    SetProcessDpiAwarenessContextFn set_ctx = u ?
        (SetProcessDpiAwarenessContextFn)(void (*)(void))GetProcAddress(u, "SetProcessDpiAwarenessContext") : NULL;
    if (set_ctx) {
        /* per-monitor v2, then v1; ACCESS_DENIED = already set by the manifest */
        if (set_ctx((HANDLE)(LONG_PTR)-4) || set_ctx((HANDLE)(LONG_PTR)-3)) return;
        if (GetLastError() == ERROR_ACCESS_DENIED) return;
    }
    SetProcessDPIAware();
}

static UINT window_dpi(HWND hwnd)
{
    HMODULE u = GetModuleHandleW(L"user32.dll");
    GetDpiForWindowFn get = u ? (GetDpiForWindowFn)(void (*)(void))GetProcAddress(u, "GetDpiForWindow") : NULL;
    if (get && hwnd) {
        UINT d = get(hwnd);
        if (d) return d;
    }
    HDC hdc = GetDC(NULL);
    UINT d = hdc ? (UINT)GetDeviceCaps(hdc, LOGPIXELSX) : 96;
    if (hdc) ReleaseDC(NULL, hdc);
    return d ? d : 96;
}

/* Window rectangle for a client rectangle; menu = the window has a menu bar
   (counted as one line). */
static void adjust_rect(RECT *rc, DWORD style, DWORD ex, UINT dpi, BOOL menu)
{
    HMODULE u = GetModuleHandleW(L"user32.dll");
    AdjustWindowRectExForDpiFn adj = u ?
        (AdjustWindowRectExForDpiFn)(void (*)(void))GetProcAddress(u, "AdjustWindowRectExForDpi") : NULL;
    if (adj && adj(rc, style, menu, ex, dpi)) return;
    AdjustWindowRectEx(rc, style, menu, ex);
}

/* Window for a client area of 160x152 times scale (below the menu bar),
   centred on its monitor's work area, with the scale reduced until it fits. */
static void size_window(int scale)
{
    DWORD style = (DWORD)GetWindowLongW(A.hwnd, GWL_STYLE), ex = (DWORD)GetWindowLongW(A.hwnd, GWL_EXSTYLE);
    BOOL menu = GetMenu(A.hwnd) != NULL;
    UINT dpi = window_dpi(A.hwnd);
    MONITORINFO mi;
    mi.cbSize = sizeof(mi);
    GetMonitorInfoW(MonitorFromWindow(A.hwnd, MONITOR_DEFAULTTOPRIMARY), &mi);
    int ww = mi.rcWork.right - mi.rcWork.left, wh = mi.rcWork.bottom - mi.rcWork.top;
    RECT rc;
    for (;;) {
        SetRect(&rc, 0, 0, NGP_SCREEN_W * scale, NGP_SCREEN_H * scale);
        adjust_rect(&rc, style, ex, dpi, menu);
        if (scale <= 1 || (rc.right - rc.left <= ww && rc.bottom - rc.top <= wh)) break;
        scale--;
    }
    int w = rc.right - rc.left, h = rc.bottom - rc.top;
    int x = mi.rcWork.left + (ww - w) / 2, y = mi.rcWork.top + (wh - h) / 2;
    if (x < mi.rcWork.left) x = mi.rcWork.left;
    if (y < mi.rcWork.top) y = mi.rcWork.top;
    SetWindowPos(A.hwnd, NULL, x, y, w, h, SWP_NOZORDER | SWP_NOACTIVATE);
    /* A menu bar that wraps onto a second line (a narrow window with large
       text) takes more height than the one line counted above: add the
       difference, so the client area keeps its exact size. */
    RECT cr;
    if (menu && GetClientRect(A.hwnd, &cr) && cr.bottom > 0 && cr.bottom < NGP_SCREEN_H * scale) {
        h += NGP_SCREEN_H * scale - cr.bottom;
        SetWindowPos(A.hwnd, NULL, x, y, w, h, SWP_NOZORDER | SWP_NOACTIVATE);
    }
}

static void toggle_fullscreen(void)
{
    DWORD style = (DWORD)GetWindowLongW(A.hwnd, GWL_STYLE);
    if (!A.fullscreen) {
        MONITORINFO mi;
        mi.cbSize = sizeof(mi);
        A.saved_wp.length = sizeof(A.saved_wp);
        if (!GetWindowPlacement(A.hwnd, &A.saved_wp) ||
            !GetMonitorInfoW(MonitorFromWindow(A.hwnd, MONITOR_DEFAULTTOPRIMARY), &mi)) return;
        SetMenu(A.hwnd, NULL);   /* no menu bar in fullscreen (the menu is kept in A.menu) */
        SetWindowLongW(A.hwnd, GWL_STYLE, (LONG)(style & ~(DWORD)WS_OVERLAPPEDWINDOW));
        SetWindowPos(A.hwnd, HWND_TOP, mi.rcMonitor.left, mi.rcMonitor.top,
                     mi.rcMonitor.right - mi.rcMonitor.left, mi.rcMonitor.bottom - mi.rcMonitor.top,
                     SWP_NOOWNERZORDER | SWP_FRAMECHANGED);
        A.fullscreen = 1;
    } else {
        SetWindowLongW(A.hwnd, GWL_STYLE, (LONG)(style | WS_OVERLAPPEDWINDOW));
        if (A.menu) SetMenu(A.hwnd, A.menu);   /* before the placement: it was saved with the menu bar */
        SetWindowPlacement(A.hwnd, &A.saved_wp);
        SetWindowPos(A.hwnd, NULL, 0, 0, 0, 0,
                     SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_NOOWNERZORDER | SWP_FRAMECHANGED);
        A.fullscreen = 0;
    }
    InvalidateRect(A.hwnd, NULL, FALSE);
}

/* ------------------------------------------------------------------ */
/* Emulation                                                            */
/* ------------------------------------------------------------------ */

static double frame_period(void)
{
    /* one frame = (lines) * 515 master ticks at 6.144 MHz; 199 lines -> 59.95 Hz */
    int lines = g_lowmem[0x8006] + 1;
    if (lines < NGP_SCREEN_H + 1) lines = NGP_SCREEN_H + 1;
    return (double)lines * NGP_LINE_TICKS * (double)zen_qpc_freq() / (double)NGP_MASTER_HZ;
}

static void run_frames(int count, int with_audio)
{
    int16_t audio[4096 * 2];
    int focused = GetForegroundWindow() == A.hwnd;
    for (int i = 0; i < count; i++) {
        int pad_ff = 0;
        g_input_state = input_game_bits(focused, &pad_ff);
        A.pad_ff = pad_ff;
        ngp_run_frame();
        for (;;) {   /* drain the sound rendered for this frame, like the harness */
            size_t n = audio_render(audio, 4096, ngp_now());
            if (with_audio && n) audio_push(audio, n);
            if (n != 4096) break;
        }
        A.frames_run++;
        if (g_cpu.halted && !g_irq_check && ngp_shutdown_requested()) {
            A.shutdown_seen = 1;
            update_title();
            break;
        }
    }
}

static void step_and_present(void)
{
    int ff = input_action_down(ACT_FAST_FORWARD) || A.pad_ff;
    if (ff != A.ff) {
        A.ff = ff;
        update_title();
    }
    audio_set_muted(ff);
    double period = frame_period();
    run_frames(ff ? FF_FRAMES : 1, !ff);
    if (!ff) period *= audio_rate_adjust();
    video_present(A.hwnd, g_framebuffer, NULL);
    int saved = saves_flash_poll();
    if (saved < 0) set_status(L"Could not write the save file!");
    else if (saved > 0) set_status(L"Cartridge save written");

    double now = (double)zen_qpc();
    if (A.next_frame == 0) A.next_frame = now;
    A.next_frame += period;
    if (now - A.next_frame > 4.0 * period) A.next_frame = now;   /* fell behind: resync */
}

/* Waits until the QPC time target or until a message arrives. */
static void wait_until(double target)
{
    double remain = target - (double)zen_qpc();
    if (remain <= 0) return;
    double ms = remain * 1000.0 / (double)zen_qpc_freq();
    if (ms > 1.0) {
        double sleep_ms = ms - (A.timer ? 0.5 : 1.5);
        if (A.timer) {
            LARGE_INTEGER due;
            due.QuadPart = -(LONGLONG)(sleep_ms * 10000.0);   /* relative, 100 ns units */
            if (SetWaitableTimer(A.timer, &due, 0, NULL, NULL, FALSE)) {
                MsgWaitForMultipleObjectsEx(1, &A.timer, (DWORD)ms + 2, QS_ALLINPUT, MWMO_INPUTAVAILABLE);
                return;
            }
        }
        if (sleep_ms >= 1.0) {
            MsgWaitForMultipleObjectsEx(0, NULL, (DWORD)sleep_ms, QS_ALLINPUT, MWMO_INPUTAVAILABLE);
            return;
        }
    }
    while ((double)zen_qpc() < target) YieldProcessor();
}

/* ------------------------------------------------------------------ */
/* Commands                                                             */
/* ------------------------------------------------------------------ */

static int load_rom(const wchar_t *path)
{
    if (A.have_rom && !saves_flash_flush())
        modal_message(MB_OK | MB_ICONWARNING, IDOK, L"The cartridge save could not be written:\n%ls",
                      saves_flash_path() ? saves_flash_path() : L"?");
    audio_set_muted(1);
    RomPrep p;
    int ok = app_prepare_rom(A.hwnd, path, A.opt->patch, A.opt->untranslated, &p);
    input_clear();
    A.next_frame = 0;
    if (!ok) {
        rom_prep_free(&p);
        return 0;
    }
    if (!rom_install(&p)) {
        modal_message(MB_OK | MB_ICONERROR, IDOK, L"Not enough memory to load the ROM.");
        rom_prep_free(&p);
        return 0;
    }
    ngp_reset();   /* also puts the flash chip in read mode and sets the BIOS chip sizes */
    A.have_rom = 1;
    A.untranslated = p.untranslated;
    A.english = rom_prep_is_english(&p);
    A.english_crc = p.patch_info.target_crc;
    free(A.rom_path);
    A.rom_path = zen_wcsdup(p.rom_path);
    A.shutdown_seen = 0;
    A.paused = 0;
    wchar_t *save = save_path_for(p.zip.name ? p.zip.name : p.rom_path);
    int r = saves_flash_attach(save);
    if (r < 0)
        modal_message(MB_OK | MB_ICONWARNING, IDOK,
                      L"The cartridge save file could not be read completely:\n%ls\n\n"
                      L"It is kept, and copied to %ls.bak before the game saves again.",
                      save, zen_path_name(save));
    free(save);
    config_set_last_rom(p.rom_path);
    rom_prep_free(&p);
    audio_clear();
    set_status(r > 0 ? L"Cartridge save loaded" : L"Game started");
    InvalidateRect(A.hwnd, NULL, FALSE);
    return 1;
}

static int open_rom_dialog(void)
{
    wchar_t file[CFG_PATH_MAX];
    file[0] = 0;
    OPENFILENAMEW ofn;
    memset(&ofn, 0, sizeof(ofn));
    ofn.lStructSize = sizeof(ofn);
    ofn.hwndOwner = A.hwnd;
    ofn.lpstrFilter = L"Neo Geo Pocket games (*.ngc;*.ngp;*.npc;*.zip)\0*.ngc;*.ngp;*.npc;*.zip\0"
                      L"All files (*.*)\0*.*\0";
    ofn.lpstrFile = file;
    ofn.nMaxFile = CFG_PATH_MAX;
    ofn.lpstrTitle = L"Open the Ogre Battle Gaiden ROM";
    ofn.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_HIDEREADONLY | OFN_EXPLORER;
    audio_set_muted(1);
    BOOL ok = GetOpenFileNameW(&ofn);
    input_clear();
    A.next_frame = 0;
    return ok ? load_rom(file) : 0;
}

/* 2097152 -> "2,097,152" */
static const wchar_t *grouped(size_t v)
{
    static wchar_t out[40];
    wchar_t digits[24];
    int n = swprintf(digits, 24, L"%zu", v), o = 0;
    for (int i = 0; i < n; i++) {
        if (i > 0 && (n - i) % 3 == 0) out[o++] = L',';
        out[o++] = digits[i];
    }
    out[o] = 0;
    return out;
}

/* Save As dialog opened in the given folder with the given name. The common
   item dialog is used because it can be told the folder (GetSaveFileName
   opens wherever Windows last saved for this program); GetSaveFileName is
   the fallback. Returns 1 with the chosen path in out. */
static int ask_save_path(wchar_t *out, size_t cap, const wchar_t *folder, const wchar_t *name,
                         const wchar_t *title)
{
    IFileSaveDialog *dlg = NULL;
    if (SUCCEEDED(CoCreateInstance(&CLSID_FileSaveDialog, NULL, CLSCTX_INPROC_SERVER, &IID_IFileSaveDialog,
                                   (void **)&dlg))) {
        static const COMDLG_FILTERSPEC types[] = {
            {L"Neo Geo Pocket Color ROM (*.ngc)", L"*.ngc"},
            {L"All files (*.*)", L"*.*"},
        };
        DWORD opts = 0;
        int ok = 0;
        IFileSaveDialog_GetOptions(dlg, &opts);
        IFileSaveDialog_SetOptions(dlg, opts | FOS_OVERWRITEPROMPT | FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST |
                                            FOS_NOREADONLYRETURN | FOS_NOCHANGEDIR);
        IFileSaveDialog_SetFileTypes(dlg, 2, types);
        IFileSaveDialog_SetDefaultExtension(dlg, L"ngc");
        IFileSaveDialog_SetTitle(dlg, title);
        IFileSaveDialog_SetFileName(dlg, name);
        IShellItem *dir = NULL;
        if (folder && folder[0] &&
            SUCCEEDED(SHCreateItemFromParsingName(folder, NULL, &IID_IShellItem, (void **)&dir))) {
            IFileSaveDialog_SetFolder(dlg, dir);
            IShellItem_Release(dir);
        }
        if (SUCCEEDED(IFileSaveDialog_Show(dlg, A.hwnd))) {
            IShellItem *item = NULL;
            if (SUCCEEDED(IFileSaveDialog_GetResult(dlg, &item))) {
                PWSTR path = NULL;
                if (SUCCEEDED(IShellItem_GetDisplayName(item, SIGDN_FILESYSPATH, &path))) {
                    ok = wcslen(path) < cap;
                    if (ok) wcscpy_s(out, cap, path);
                    CoTaskMemFree(path);
                }
                IShellItem_Release(item);
            }
        }
        IFileSaveDialog_Release(dlg);
        return ok;
    }
    /* no common item dialog: the classic one, with the folder in the name */
    if (!folder || wcslen(folder) + wcslen(name) + 2 > cap) folder = L"";
    swprintf(out, cap, L"%ls%ls%ls", folder,
             folder[0] && folder[wcslen(folder) - 1] != L'\\' ? L"\\" : L"", name);
    OPENFILENAMEW ofn;
    memset(&ofn, 0, sizeof(ofn));
    ofn.lStructSize = sizeof(ofn);
    ofn.hwndOwner = A.hwnd;
    ofn.lpstrFilter = L"Neo Geo Pocket Color ROM (*.ngc)\0*.ngc\0All files (*.*)\0*.*\0";
    ofn.lpstrFile = out;
    ofn.nMaxFile = (DWORD)cap;
    ofn.lpstrTitle = title;
    ofn.lpstrDefExt = L"ngc";
    ofn.Flags = OFN_OVERWRITEPROMPT | OFN_PATHMUSTEXIST | OFN_HIDEREADONLY | OFN_NOREADONLYRETURN |
                OFN_NOCHANGEDIR | OFN_EXPLORER;
    return GetSaveFileNameW(&ofn) ? 1 : 0;
}

/* File > Save English ROM (Ctrl+S): writes the English ROM as it was loaded
   (before any in-game saves, which stay in the save file) where the user
   chooses, by default in the game file's folder, then reads the file back
   and checks its SHA-1 against the running image and its CRC32 against the
   patch's target. Without a game, or with a game that is not the English
   ROM, it explains why there is nothing to save. */
static void save_english_rom(void)
{
    if (!A.have_rom) {
        modal_message(MB_OK | MB_ICONINFORMATION, IDOK,
                      L"No game is loaded yet.\n\n"
                      L"Open your Ogre Battle Gaiden game file first (File > Open game, or Ctrl+O). This "
                      L"command then saves the English version of it as a new file, for other emulators "
                      L"or a flash cartridge.");
        return;
    }
    if (!A.english) {
        if (A.untranslated)
            modal_message(MB_OK | MB_ICONINFORMATION, IDOK,
                          L"The game is running untranslated: the English patch (ogre_en.bps) was not found "
                          L"or could not be used, so there is no English ROM to save.\n\n"
                          L"Put ogre_en.bps in the same folder as zenobia.exe, then open the game again "
                          L"(File > Open game).");
        else
            modal_message(MB_OK | MB_ICONINFORMATION, IDOK,
                          L"The game file running now is not the original Japanese game that the English "
                          L"patch was made for, so no English ROM can be made from it.\n\n"
                          L"Open your original game file (File > Open game), then try again.");
        return;
    }
    size_t size = 0;
    const uint8_t *image = rom_image(&size);
    if (!image || !size || !A.rom_path) return;

    /* proposed: the English name in the game file's folder */
    wchar_t folder[CFG_PATH_MAX], file[CFG_PATH_MAX];
    size_t dirlen = (size_t)(zen_path_name(A.rom_path) - A.rom_path);
    if (dirlen >= CFG_PATH_MAX) dirlen = 0;
    wmemcpy(folder, A.rom_path, dirlen);
    folder[dirlen] = 0;
    audio_set_muted(1);
    int ok = ask_save_path(file, CFG_PATH_MAX, folder, ENGLISH_ROM_NAME, L"Save the English ROM");
    input_clear();
    A.next_frame = 0;
    if (!ok) return;

    wchar_t *out = zen_full_path(file);
    if (!out) return;
    if (_wcsicmp(out, A.rom_path) == 0) {
        modal_message(MB_OK | MB_ICONWARNING, IDOK,
                      L"This is the game file you opened:\n%ls\n\n"
                      L"Choose another name, so that it stays as it is.", out);
        free(out);
        return;
    }
    int written = zen_write_file_atomic(out, image, size) == ZEN_FILE_OK;
    int verified = 0;
    uint8_t digest[20];
    uint8_t *back = NULL;
    size_t back_size = 0;
    if (written && zen_read_file(out, &back, &back_size, size + 1) == ZEN_FILE_OK && back_size == size) {
        sha1(back, back_size, digest);
        verified = memcmp(digest, rom_image_sha1(), 20) == 0 && bps_crc32(0, back, back_size) == A.english_crc;
    }
    free(back);
    if (!written) {
        modal_message(MB_OK | MB_ICONERROR, IDOK,
                      L"The English ROM could not be saved here:\n%ls\n\n"
                      L"Choose another folder (for example Documents) and try again.", out);
    } else if (!verified) {
        DeleteFileW(out);
        modal_message(MB_OK | MB_ICONERROR, IDOK,
                      L"The English ROM was written here:\n%ls\n\nbut reading it back gave different data, so "
                      L"the file was deleted. The drive may be full or failing; try another folder.", out);
    } else {
        char hex[41];
        sha1_hex(digest, hex);
        set_status(L"English ROM saved");
        modal_message(MB_OK | MB_ICONINFORMATION, IDOK,
                      L"The English ROM was saved:\n%ls\n\n"
                      L"Play it with another Neo Geo Pocket Color emulator or on a flash cartridge. Your "
                      L"original game file was not changed, and your saved games stay with this player "
                      L"(in its saves folder).\n\n"
                      L"Checked after saving: %ls bytes, CRC32 %08X, SHA-1 %hs.",
                      out, grouped(size), (unsigned)A.english_crc, hex);
    }
    free(out);
}

static void show_controls(void)
{
    modal_message(MB_OK | MB_ICONINFORMATION, IDOK, L"%ls", k_help);
}

/* "MAJOR.MINOR.PATCH" from the program's version resource (zenobia.rc). */
static void version_string(wchar_t *out, size_t cap)
{
    swprintf(out, cap, L"(unknown)");
    HRSRC r = FindResourceW(NULL, MAKEINTRESOURCEW(1), MAKEINTRESOURCEW(16));   /* VS_VERSION_INFO, RT_VERSION */
    HGLOBAL g = r ? LoadResource(NULL, r) : NULL;
    const uint8_t *d = g ? (const uint8_t *)LockResource(g) : NULL;
    DWORD n = d ? SizeofResource(NULL, r) : 0;
    for (DWORD i = 0; i + 16 <= n; i += 4) {
        uint32_t w[4];
        memcpy(w, d + i, sizeof(w));   /* VS_FIXEDFILEINFO: signature, struct version, version MS, LS */
        if (w[0] == 0xFEEF04BDu) {
            swprintf(out, cap, L"%u.%u.%u", (unsigned)(w[2] >> 16), (unsigned)(w[2] & 0xFFFF),
                     (unsigned)(w[3] >> 16));
            return;
        }
    }
}

static void show_about(void)
{
    wchar_t version[32], game[CFG_PATH_MAX + 64];
    version_string(version, 32);
    if (!A.have_rom || !A.rom_path)
        swprintf(game, sizeof(game) / sizeof(game[0]), L"none loaded");
    else
        swprintf(game, sizeof(game) / sizeof(game[0]), L"%ls\n(%ls)", A.rom_path,
                 A.english ? L"running in English" : A.untranslated ? L"running untranslated" : L"running as is");
    modal_message(MB_OK | MB_ICONINFORMATION, IDOK,
                  L"%ls\nVersion %ls\n\n"
                  L"An unofficial English fan translation of Densetsu no Ogre Battle Gaiden: Zenobia no Ouji "
                  L"(Neo Geo Pocket Color, 2000). It plays your own copy of the original Japanese game, "
                  L"translated while it loads with the English patch (ogre_en.bps); your game file is never "
                  L"changed.\n\n"
                  L"Game: %ls\n\nSettings, saves and states are kept in:\n%ls\n\n"
                  L"Free software under the MIT License (LICENSE.txt, THIRD_PARTY_NOTICES.txt). Not "
                  L"affiliated with the owners of the game.",
                  ZEN_TITLE, version, game, zen_exe_dir());
}

static HMENU create_menu(void)
{
    HMENU bar = CreateMenu(), file = CreatePopupMenu(), help = CreatePopupMenu();
    if (!bar || !file || !help) {
        if (bar) DestroyMenu(bar);
        if (file) DestroyMenu(file);
        if (help) DestroyMenu(help);
        return NULL;
    }
    /* Exit shows the first key bound to quit (Esc unless changed in zenobia.ini) */
    wchar_t exit_label[64];
    int quit = A.cfg.nkeys[ACT_QUIT] > 0 ? A.cfg.keys[ACT_QUIT][0] : 0;
    if (quit) swprintf(exit_label, 64, L"E&xit\t%ls", quit == VK_ESCAPE ? L"Esc" : config_key_name(quit));
    else swprintf(exit_label, 64, L"E&xit");
    AppendMenuW(file, MF_STRING, IDM_OPEN, L"&Open game...\tCtrl+O");
    AppendMenuW(file, MF_STRING, IDM_SAVE_ENGLISH, L"&Save English ROM...\tCtrl+S");
    AppendMenuW(file, MF_SEPARATOR, 0, NULL);
    AppendMenuW(file, MF_STRING, IDM_EXIT, exit_label);
    AppendMenuW(help, MF_STRING, IDM_CONTROLS, L"&Controls\tF1");
    AppendMenuW(help, MF_STRING, IDM_ABOUT, L"&About");
    AppendMenuW(bar, MF_POPUP, (UINT_PTR)file, L"&File");
    AppendMenuW(bar, MF_POPUP, (UINT_PTR)help, L"&Help");
    return bar;
}

static void save_state_slot(void)
{
    wchar_t *path = slot_path(A.slot);
    int r = path ? state_save(path, rom_image_sha1()) : STATE_ERR_IO;
    free(path);
    if (r == STATE_OK) set_status(L"State %d saved", A.slot);
    else set_status(L"State %d not saved: %hs", A.slot, state_result_string(r));
}

static void load_state_slot(void)
{
    wchar_t *path = slot_path(A.slot);
    if (!path) return;
    saves_flash_flush();   /* the cartridge save on disk stays current */
    int r = state_load(path, rom_image_sha1(), 0);
    if (r == STATE_ERR_OTHER_ROM) {
        if (modal_message(MB_YESNO | MB_ICONWARNING | MB_DEFBUTTON2, IDNO,
                          L"State %d was saved with a different version of the game "
                          L"(another ROM or patch). Loading it may crash the game.\n\nLoad it anyway?",
                          A.slot) == IDYES)
            r = state_load(path, rom_image_sha1(), 1);
        else {
            free(path);
            set_status(L"State %d not loaded", A.slot);
            return;
        }
    }
    free(path);
    if (r == STATE_OK) {
        A.shutdown_seen = 0;
        audio_clear();
        A.next_frame = 0;
        set_status(L"State %d loaded", A.slot);
    } else if (r == STATE_ERR_FATAL) {
        audio_clear();
        modal_message(MB_OK | MB_ICONERROR, IDOK, L"State %d could not be loaded and the game had to be reset.", A.slot);
        set_status(L"Game reset");
    } else {
        set_status(L"State %d: %hs", A.slot, state_result_string(r));
    }
}

static void reset_game(void)
{
    if (modal_message(MB_YESNO | MB_ICONQUESTION | MB_DEFBUTTON2, IDNO,
                      L"Reset the game?\n\nProgress since your last in-game save will be lost.") != IDYES)
        return;
    saves_flash_flush();
    ngp_reset();
    audio_clear();
    A.shutdown_seen = 0;
    A.next_frame = 0;
    set_status(L"Game reset");
}

static void write_exit_png(void)
{
    if (!A.opt->png) return;
    char *cp = zen_core_path(A.opt->png);
    int ok = cp && png_write_rgb(cp, g_framebuffer, NGP_SCREEN_W, NGP_SCREEN_H, A.opt->png_scale);
    free(cp);
    char *u = zen_to_utf8(A.opt->png);
    zen_logf(ok ? "zenobia: wrote %s\n" : "zenobia: cannot write %s\n", u ? u : "?");
    free(u);
    if (!ok && A.exit_code == EXIT_OK) A.exit_code = EXIT_PNG_FAILED;
}

static void app_close(void)
{
    if (A.quitting) return;
    if (A.have_rom && !saves_flash_flush()) {
        if (modal_message(MB_YESNO | MB_ICONERROR | MB_DEFBUTTON2, IDYES,
                          L"The cartridge save could not be written to:\n%ls\n\n"
                          L"Quit anyway? Your latest in-game save would be lost.",
                          saves_flash_path() ? saves_flash_path() : L"?") != IDYES)
            return;
        A.exit_code = EXIT_SAVE_FAILED;
    }
    A.quitting = 1;
    A.stop_time = zen_seconds();
    audio_set_muted(1);
    write_exit_png();
    DestroyWindow(A.hwnd);
}

static void handle_hotkey(int vk)
{
    if (input_is_bound(ACT_QUIT, vk)) { app_close(); return; }
    if (input_is_bound(ACT_FULLSCREEN, vk)) toggle_fullscreen();
    if (vk == VK_F1) {
        show_controls();
        return;
    }
    if (!A.have_rom) return;
    if (input_is_bound(ACT_PAUSE, vk)) {
        A.paused = !A.paused;
        A.next_frame = 0;
        if (A.paused) {             /* the title already says "Paused" */
            A.status[0] = 0;
            update_title();
            if (!g_zen_interactive) zen_logf("zenobia: Paused\n");
        } else {
            set_status(L"Resumed");
        }
    }
    if (input_is_bound(ACT_SAVE_STATE, vk)) save_state_slot();
    if (input_is_bound(ACT_LOAD_STATE, vk)) load_state_slot();
    if (input_is_bound(ACT_PREV_SLOT, vk)) {
        A.slot = (A.slot + NUM_SLOTS - 1) % NUM_SLOTS;
        set_status(L"Slot %d selected", A.slot);
    }
    if (input_is_bound(ACT_NEXT_SLOT, vk)) {
        A.slot = (A.slot + 1) % NUM_SLOTS;
        set_status(L"Slot %d selected", A.slot);
    }
    if (input_is_bound(ACT_RESET, vk)) reset_game();
}

/* Left/right variants for Shift, Ctrl and Alt. */
static int normalize_vk(WPARAM wp, LPARAM lp)
{
    int vk = (int)wp;
    UINT sc = (UINT)((lp >> 16) & 0xFF);
    int ext = (int)((lp >> 24) & 1);
    switch (vk) {
    case VK_SHIFT: {
        UINT m = MapVirtualKeyW(sc, MAPVK_VSC_TO_VK_EX);
        return m ? (int)m : vk;
    }
    case VK_CONTROL: return ext ? VK_RCONTROL : VK_LCONTROL;
    case VK_MENU:    return ext ? VK_RMENU : VK_LMENU;
    default:         return vk;
    }
}

/* ------------------------------------------------------------------ */
/* Window procedure                                                     */
/* ------------------------------------------------------------------ */

static LRESULT CALLBACK wndproc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp)
{
    switch (msg) {
    case WM_CREATE:
        DragAcceptFiles(hwnd, TRUE);
        return 0;
    case WM_ERASEBKGND:
        return 1;
    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint(hwnd, &ps);
        video_draw(hwnd, hdc, A.have_rom ? g_framebuffer : NULL, k_hint);
        EndPaint(hwnd, &ps);
        return 0;
    }
    case WM_SIZE:
        InvalidateRect(hwnd, NULL, FALSE);
        return 0;
    case WM_GETMINMAXINFO: {
        MINMAXINFO *mm = (MINMAXINFO *)lp;
        RECT rc;
        SetRect(&rc, 0, 0, NGP_SCREEN_W, NGP_SCREEN_H);
        adjust_rect(&rc, WS_OVERLAPPEDWINDOW, 0, window_dpi(hwnd), GetMenu(hwnd) != NULL);
        mm->ptMinTrackSize.x = rc.right - rc.left;
        mm->ptMinTrackSize.y = rc.bottom - rc.top;
        return 0;
    }
    case WM_DPICHANGED:
        if (!A.fullscreen) {
            /* Windows suggests a rectangle scaled by the DPI ratio. When the
               picture is at an exact zoom level, keep a whole-number zoom
               (closest to the same apparent size) instead, so it stays sharp. */
            const RECT *r = (const RECT *)lp;
            UINT new_dpi = HIWORD(wp);
            RECT cr, wr;
            GetClientRect(hwnd, &cr);
            int z = cr.right / NGP_SCREEN_W;
            SetRect(&wr, r->left, r->top, r->right, r->bottom);
            if (z >= 1 && cr.right == NGP_SCREEN_W * z && cr.bottom == NGP_SCREEN_H * z && A.dpi && new_dpi) {
                int nz = (int)((double)z * new_dpi / A.dpi + 0.5);
                if (nz < 1) nz = 1;
                RECT nr;
                SetRect(&nr, 0, 0, NGP_SCREEN_W * nz, NGP_SCREEN_H * nz);
                adjust_rect(&nr, (DWORD)GetWindowLongW(hwnd, GWL_STYLE), (DWORD)GetWindowLongW(hwnd, GWL_EXSTYLE),
                            new_dpi, GetMenu(hwnd) != NULL);
                SetRect(&wr, r->left, r->top, r->left + (nr.right - nr.left), r->top + (nr.bottom - nr.top));
            }
            SetWindowPos(hwnd, NULL, wr.left, wr.top, wr.right - wr.left, wr.bottom - wr.top,
                         SWP_NOZORDER | SWP_NOACTIVATE);
        }
        A.dpi = HIWORD(wp);
        return 0;
    case WM_SETCURSOR:
        if (A.fullscreen && LOWORD(lp) == HTCLIENT) {
            SetCursor(NULL);
            return TRUE;
        }
        break;
    case WM_ACTIVATEAPP:
        A.inactive = !wp;
        if (!wp) input_clear();
        A.next_frame = 0;
        update_title();
        return 0;
    case WM_KILLFOCUS:
        input_clear();
        break;
    case WM_KEYDOWN:
    case WM_SYSKEYDOWN: {
        int vk = normalize_vk(wp, lp);
        int repeat = (lp & (1L << 30)) != 0;
        int alt = (HIWORD(lp) & KF_ALTDOWN) != 0;
        if (msg == WM_SYSKEYDOWN && wp == VK_RETURN && alt) {
            if (!repeat) toggle_fullscreen();
            return 0;
        }
        if (msg == WM_SYSKEYDOWN && wp == VK_F4 && alt) break;   /* Alt+F4 closes */
        input_key(vk, 1);
        if (!repeat) {
            int ctrl = (GetKeyState(VK_CONTROL) & 0x8000) != 0 || input_key_down(VK_CONTROL);
            if (ctrl && wp == 'O') open_rom_dialog();
            else if (ctrl && wp == 'S') save_english_rom();
            else handle_hotkey(vk);
        }
        return 0;   /* no menu activation by F10 or Alt: the keys stay with the game */
    }
    case WM_KEYUP:
    case WM_SYSKEYUP:
        input_key(normalize_vk(wp, lp), 0);
        return 0;
    case WM_SYSCHAR:
        if (wp == ' ') break;   /* Alt+Space: system menu */
        return 0;               /* no beep for other Alt+key combinations */
    case WM_SYSCOMMAND:
        if ((wp & 0xFFF0) == SC_KEYMENU && lp == 0) return 0;
        break;
    case WM_COMMAND:
        if (HIWORD(wp) == 0 && lp == 0) {   /* a menu item */
            switch (LOWORD(wp)) {
            case IDM_OPEN:         open_rom_dialog(); return 0;
            case IDM_SAVE_ENGLISH: save_english_rom(); return 0;
            case IDM_EXIT:         app_close(); return 0;
            case IDM_CONTROLS:     show_controls(); return 0;
            case IDM_ABOUT:        show_about(); return 0;
            default:               break;
            }
        }
        break;
    case WM_ENTERMENULOOP:
        /* the game waits while a menu is open (the main loop does not run) */
        audio_set_muted(1);
        input_clear();
        return 0;
    case WM_EXITMENULOOP:
        input_clear();
        A.next_frame = 0;
        return 0;
    case WM_DROPFILES: {
        HDROP drop = (HDROP)wp;
        UINT n = DragQueryFileW(drop, 0, NULL, 0);
        wchar_t *file = (wchar_t *)malloc(((size_t)n + 1) * sizeof(wchar_t));
        if (file && DragQueryFileW(drop, 0, file, n + 1)) {
            DragFinish(drop);
            SetForegroundWindow(hwnd);
            load_rom(file);
        } else {
            DragFinish(drop);
        }
        free(file);
        return 0;
    }
    case WM_ENTERSIZEMOVE:
        A.in_sizemove = 1;
        SetTimer(hwnd, TIMER_SIZEMOVE, 10, NULL);
        return 0;
    case WM_EXITSIZEMOVE:
        A.in_sizemove = 0;
        KillTimer(hwnd, TIMER_SIZEMOVE);
        return 0;
    case WM_TIMER:
        /* keep playing while the window is dragged or resized (modal loop) */
        if (wp == TIMER_SIZEMOVE && emu_running()) {
            for (int i = 0; i < 3 && (A.next_frame == 0 || (double)zen_qpc() >= A.next_frame); i++)
                step_and_present();
        }
        return 0;
    case WM_CLOSE:
        app_close();
        return 0;
    case WM_DESTROY:
        PostQuitMessage(0);
        return 0;
    default:
        break;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

/* ------------------------------------------------------------------ */
/* Entry                                                                */
/* ------------------------------------------------------------------ */

/* With a console attached (--console): Ctrl+C, Ctrl+Break or closing the
   console quit like the window's close button, so the save is written. */
static BOOL WINAPI console_ctrl(DWORD type)
{
    if (!A.hwnd) return FALSE;
    PostMessageW(A.hwnd, WM_CLOSE, 0, 0);
    if (type == CTRL_CLOSE_EVENT || type == CTRL_LOGOFF_EVENT || type == CTRL_SHUTDOWN_EVENT)
        Sleep(4000);   /* the process ends when this returns: give the main thread time */
    return TRUE;
}

static void print_stats(void)
{
    AudioStats as;
    audio_get_stats(&as);
    double secs = (A.stop_time > 0 ? A.stop_time : zen_seconds()) - A.start_time;
    if (secs <= 0) secs = 1e-9;
    zen_logf("zenobia: %llu frames in %.2f s (%.2f frames/s)\n", (unsigned long long)A.frames_run, secs,
             (double)A.frames_run / secs);
    zen_logf("zenobia: audio %s: %llu frames pushed, %llu played, %llu device buffers done, "
             "%llu underruns, %llu trims, peak %d\n",
             as.opened ? "waveOut 48000 Hz stereo" : "unavailable",
             (unsigned long long)as.frames_pushed, (unsigned long long)as.frames_played,
             (unsigned long long)as.buffers_done, (unsigned long long)as.underruns,
             (unsigned long long)as.trims, as.peak);
    zen_logf("zenobia: XInput %s, %d gamepad(s) connected\n",
             input_xinput_name() ? input_xinput_name() : "not available", input_gamepads_connected());
    zen_logf("zenobia: flash: %llu bytes programmed, %llu blocks erased\n",
             (unsigned long long)flashchip_programs(), (unsigned long long)flashchip_erases());
}

int run_gui(const Options *o, HINSTANCE inst)
{
    memset(&A, 0, sizeof(A));
    A.opt = o;
    A.exit_code = EXIT_OK;

    set_dpi_awareness();
    HRESULT com = CoInitializeEx(NULL, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE);
    timeBeginPeriod(1);

    config_load(&A.cfg);
    if (o->log_level >= 0) g_log_level = o->log_level;
    else g_log_level = o->console ? 1 : 0;
    g_flash_commands = !o->no_flash_commands;   /* the core emulates the flash chip: in-game saving works */
    input_init(&A.cfg);
    video_set_integer_scaling(A.cfg.integer_scaling);

    WNDCLASSEXW wc;
    memset(&wc, 0, sizeof(wc));
    wc.cbSize = sizeof(wc);
    wc.style = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc = wndproc;
    wc.hInstance = inst;
    /* The program icon (zenobia.rc); a build without Python has none, so fall
       back to the stock icon. */
    wc.hIcon = LoadIconW(inst, MAKEINTRESOURCEW(IDI_ZENOBIA));
    wc.hIconSm = (HICON)LoadImageW(inst, MAKEINTRESOURCEW(IDI_ZENOBIA), IMAGE_ICON,
                                   GetSystemMetrics(SM_CXSMICON), GetSystemMetrics(SM_CYSMICON), 0);
    if (!wc.hIcon) wc.hIcon = LoadIconW(NULL, (LPCWSTR)IDI_APPLICATION);
    wc.hCursor = LoadCursorW(NULL, (LPCWSTR)IDC_ARROW);
    wc.lpszClassName = WINDOW_CLASS;
    RegisterClassExW(&wc);
    A.menu = create_menu();
    A.hwnd = CreateWindowExW(0, WINDOW_CLASS, ZEN_TITLE, WS_OVERLAPPEDWINDOW, CW_USEDEFAULT, CW_USEDEFAULT,
                             NGP_SCREEN_W * 4, NGP_SCREEN_H * 4, NULL, A.menu, inst, NULL);
    if (!A.hwnd) {
        if (A.menu) DestroyMenu(A.menu);
        zen_message(NULL, MB_OK | MB_ICONERROR, IDOK, L"Cannot create the window.");
        timeEndPeriod(1);
        return EXIT_USAGE;
    }
    A.dpi = window_dpi(A.hwnd);
    size_window(A.cfg.scale);
    ShowWindow(A.hwnd, SW_SHOW);
    UpdateWindow(A.hwnd);
    update_title();
    SetConsoleCtrlHandler(console_ctrl, TRUE);   /* no effect without a console */

    A.timer = CreateWaitableTimerExW(NULL, NULL, CREATE_WAITABLE_TIMER_HIGH_RESOLUTION, TIMER_ALL_ACCESS);
    if (!A.timer) A.timer = CreateWaitableTimerW(NULL, FALSE, NULL);

    if (!audio_open(A.cfg.volume)) set_status(L"No audio device; playing without sound");

    /* ROM: command line, else the last one, else ask */
    const wchar_t *rom = o->rom;
    if (!rom && A.cfg.last_rom[0] && zen_file_exists(A.cfg.last_rom)) rom = A.cfg.last_rom;
    if (rom) load_rom(rom);
    else if (g_zen_interactive) open_rom_dialog();
    if (!A.have_rom && !g_zen_interactive) {
        zen_logf("zenobia: no ROM could be loaded\n");
        A.exit_code = rom ? EXIT_ROM_REFUSED : EXIT_ROM_UNREADABLE;
        A.quitting = 1;
        DestroyWindow(A.hwnd);
    }
    if (A.cfg.fullscreen && !A.quitting) toggle_fullscreen();

    A.start_time = zen_seconds();
    MSG m;
    for (;;) {
        while (PeekMessageW(&m, NULL, 0, 0, PM_REMOVE)) {
            if (m.message == WM_QUIT) goto done;
            TranslateMessage(&m);
            DispatchMessageW(&m);
        }
        if (o->exit_after > 0 && !A.quitting && zen_seconds() - A.start_time >= o->exit_after) {
            app_close();
            continue;
        }
        int running = emu_running();
        update_power_request(running);
        update_title();
        if (!running) {
            audio_set_muted(1);
            A.next_frame = 0;
            MsgWaitForMultipleObjectsEx(0, NULL, 50, QS_ALLINPUT, MWMO_INPUTAVAILABLE);
            continue;
        }
        double now = (double)zen_qpc();
        if (A.next_frame != 0 && now < A.next_frame) {
            wait_until(A.next_frame);
            continue;
        }
        step_and_present();
    }
done:
    update_power_request(0);
    print_stats();
    audio_close();
    input_shutdown();
    if (A.menu && A.fullscreen) DestroyMenu(A.menu);   /* detached: not destroyed with the window */
    free(A.rom_path);
    A.rom_path = NULL;
    if (A.timer) CloseHandle(A.timer);
    timeEndPeriod(1);
    if (SUCCEEDED(com)) CoUninitialize();
    return A.exit_code;
}
