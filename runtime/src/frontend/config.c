/*
 * Player settings (zenobia.ini). See config.h.
 */
#include "config.h"
#include "util.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wctype.h>

static const wchar_t *k_action_keys[ACT_COUNT] = {
    L"up", L"down", L"left", L"right", L"a", L"b", L"option",
    L"fast_forward", L"pause", L"save_state", L"load_state",
    L"prev_slot", L"next_slot", L"reset", L"quit", L"fullscreen",
};

static const wchar_t *k_action_defaults[ACT_COUNT] = {
    L"Up", L"Down", L"Left", L"Right", L"Z", L"X", L"Enter, C",
    L"Tab", L"P, Pause", L"F5", L"F9",
    L"F6", L"F7", L"F12", L"Escape", L"F11",
};

static const wchar_t k_default_ini[] =
    L"; Ogre Battle Gaiden: Prince of Zenobia (English) - player settings.\r\n"
    L"; Created with default values when missing. Delete it to restore the defaults.\r\n"
    L"\r\n"
    L"[video]\r\n"
    L"; Window size as a whole-number multiple of the 160x152 screen (1-12).\r\n"
    L"scale=4\r\n"
    L"; 1 = start in borderless fullscreen (toggle with F11 or Alt+Enter).\r\n"
    L"fullscreen=0\r\n"
    L"; 1 = keep whole-number zoom levels when the window is resized (sharpest),\r\n"
    L"; 0 = fill as much of the window as the aspect ratio allows.\r\n"
    L"integer_scaling=1\r\n"
    L"\r\n"
    L"[audio]\r\n"
    L"; Volume from 0 (silent) to 100.\r\n"
    L"volume=100\r\n"
    L"\r\n"
    L"[input]\r\n"
    L"; Keys by name (A-Z, 0-9, F1-F24, Up, Down, Left, Right, Enter, Space, Tab,\r\n"
    L"; Escape, Backspace, Shift, Ctrl, Alt, Insert, Delete, Home, End, PageUp,\r\n"
    L"; PageDown, Pause, Numpad0-Numpad9, Comma, Period, ...) or by virtual-key\r\n"
    L"; code (65 or 0x41). Several keys may share an action (option=Enter, C);\r\n"
    L"; an empty value disables the action.\r\n"
    L"; Gamepads (XInput): D-pad or left stick = D-pad, A or X = A, B or Y = B,\r\n"
    L"; Start = Option, right trigger = fast-forward.\r\n"
    L"up=Up\r\n"
    L"down=Down\r\n"
    L"left=Left\r\n"
    L"right=Right\r\n"
    L"a=Z\r\n"
    L"b=X\r\n"
    L"option=Enter, C\r\n"
    L"fast_forward=Tab\r\n"
    L"pause=P, Pause\r\n"
    L"save_state=F5\r\n"
    L"load_state=F9\r\n"
    L"prev_slot=F6\r\n"
    L"next_slot=F7\r\n"
    L"reset=F12\r\n"
    L"quit=Escape\r\n"
    L"fullscreen=F11\r\n"
    L"\r\n"
    L"[rom]\r\n"
    L"; The last ROM opened; used when no ROM is given on the command line.\r\n"
    L"last=\r\n"
    L"\r\n"
    L"[general]\r\n"
    L"; 1 = pause the game while the window is in the background.\r\n"
    L"pause_when_inactive=0\r\n"
    L"; The date the game sees, as MM-DD (for example 12-25), or empty for the\r\n"
    L"; PC's date. The game checks it for two secrets after the ending (see the\r\n"
    L"; Player's Guide). Also in the Options menu.\r\n"
    L"console_date=\r\n"
    L"; When the player starts: ask = offer to continue where you left off,\r\n"
    L"; yes = continue without asking, no = start at the title screen.\r\n"
    L"resume=ask\r\n";

typedef struct { const wchar_t *name; uint8_t vk; } KeyName;

static const KeyName k_key_names[] = {
    {L"Up", VK_UP}, {L"Down", VK_DOWN}, {L"Left", VK_LEFT}, {L"Right", VK_RIGHT},
    {L"Enter", VK_RETURN}, {L"Return", VK_RETURN}, {L"Space", VK_SPACE}, {L"Tab", VK_TAB},
    {L"Escape", VK_ESCAPE}, {L"Esc", VK_ESCAPE}, {L"Backspace", VK_BACK}, {L"Back", VK_BACK},
    {L"Shift", VK_SHIFT}, {L"LShift", VK_LSHIFT}, {L"RShift", VK_RSHIFT},
    {L"Ctrl", VK_CONTROL}, {L"Control", VK_CONTROL}, {L"LCtrl", VK_LCONTROL}, {L"RCtrl", VK_RCONTROL},
    {L"Alt", VK_MENU}, {L"LAlt", VK_LMENU}, {L"RAlt", VK_RMENU},
    {L"Insert", VK_INSERT}, {L"Ins", VK_INSERT}, {L"Delete", VK_DELETE}, {L"Del", VK_DELETE},
    {L"Home", VK_HOME}, {L"End", VK_END},
    {L"PageUp", VK_PRIOR}, {L"PgUp", VK_PRIOR}, {L"PageDown", VK_NEXT}, {L"PgDn", VK_NEXT},
    {L"Pause", VK_PAUSE}, {L"CapsLock", VK_CAPITAL}, {L"NumLock", VK_NUMLOCK}, {L"ScrollLock", VK_SCROLL},
    {L"Multiply", VK_MULTIPLY}, {L"Add", VK_ADD}, {L"Subtract", VK_SUBTRACT},
    {L"Decimal", VK_DECIMAL}, {L"Divide", VK_DIVIDE},
    {L"Comma", VK_OEM_COMMA}, {L"Period", VK_OEM_PERIOD}, {L"Minus", VK_OEM_MINUS},
    {L"Plus", VK_OEM_PLUS}, {L"Equals", VK_OEM_PLUS}, {L"Semicolon", VK_OEM_1},
    {L"Slash", VK_OEM_2}, {L"Backquote", VK_OEM_3}, {L"Grave", VK_OEM_3},
    {L"LBracket", VK_OEM_4}, {L"Backslash", VK_OEM_5}, {L"RBracket", VK_OEM_6}, {L"Quote", VK_OEM_7},
};

const wchar_t *config_action_key(int act)
{
    return (act >= 0 && act < ACT_COUNT) ? k_action_keys[act] : L"?";
}

const wchar_t *config_ini_path(void)
{
    static wchar_t *path;
    if (!path) path = zen_path_join(zen_exe_dir(), L"zenobia.ini");
    return path ? path : L"zenobia.ini";
}

static int parse_one_key(const wchar_t *tok)
{
    size_t n = wcslen(tok);
    if (n == 0) return -1;
    for (size_t i = 0; i < sizeof(k_key_names) / sizeof(k_key_names[0]); i++)
        if (_wcsicmp(tok, k_key_names[i].name) == 0) return k_key_names[i].vk;
    if (n == 1) {
        wchar_t c = (wchar_t)towupper(tok[0]);
        if ((c >= L'A' && c <= L'Z') || (c >= L'0' && c <= L'9')) return (int)c;
    }
    if ((tok[0] == L'F' || tok[0] == L'f') && n >= 2 && n <= 3 && iswdigit(tok[1]) && (n == 2 || iswdigit(tok[2]))) {
        int f = _wtoi(tok + 1);
        if (f >= 1 && f <= 24) return VK_F1 + f - 1;
    }
    if (_wcsnicmp(tok, L"Numpad", 6) == 0 && n == 7 && iswdigit(tok[6])) return VK_NUMPAD0 + (tok[6] - L'0');
    if (_wcsnicmp(tok, L"Num", 3) == 0 && n == 4 && iswdigit(tok[3])) return VK_NUMPAD0 + (tok[3] - L'0');
    if (iswdigit(tok[0])) {
        wchar_t *end = NULL;
        long v = wcstol(tok, &end, 0);   /* decimal or 0x hex */
        if (end && *end == 0 && v >= 1 && v <= 254) return (int)v;
    }
    return -1;
}

int config_parse_keys(const wchar_t *spec, uint8_t *out, int max)
{
    int count = 0, nonempty = 0;
    wchar_t tok[64];
    const wchar_t *p = spec;
    while (*p) {
        while (*p == L' ' || *p == L'\t' || *p == L',') p++;
        if (!*p) break;
        size_t n = 0;
        while (*p && *p != L',') {
            if (n + 1 < sizeof(tok) / sizeof(tok[0])) tok[n++] = *p;
            p++;
        }
        while (n > 0 && (tok[n - 1] == L' ' || tok[n - 1] == L'\t')) n--;
        tok[n] = 0;
        if (!n) continue;
        nonempty = 1;
        int vk = parse_one_key(tok);
        if (vk < 0) {
            char *u = zen_to_utf8(tok);
            zen_logf("zenobia.ini: unknown key name '%s' ignored\n", u ? u : "?");
            free(u);
            continue;
        }
        int dup = 0;
        for (int i = 0; i < count; i++) if (out[i] == vk) dup = 1;
        if (!dup && count < max) out[count++] = (uint8_t)vk;
    }
    if (nonempty && count == 0) return -1;
    return count;
}

const wchar_t *config_key_name(int vk)
{
    static wchar_t buf[16];
    for (size_t i = 0; i < sizeof(k_key_names) / sizeof(k_key_names[0]); i++)
        if (k_key_names[i].vk == vk) return k_key_names[i].name;
    if ((vk >= 'A' && vk <= 'Z') || (vk >= '0' && vk <= '9')) { buf[0] = (wchar_t)vk; buf[1] = 0; return buf; }
    if (vk >= VK_F1 && vk <= VK_F24) { swprintf(buf, 16, L"F%d", vk - VK_F1 + 1); return buf; }
    if (vk >= VK_NUMPAD0 && vk <= VK_NUMPAD9) { swprintf(buf, 16, L"Numpad%d", vk - VK_NUMPAD0); return buf; }
    swprintf(buf, 16, L"0x%02X", vk);
    return buf;
}

static void write_default_ini(const wchar_t *path)
{
    HANDLE h = CreateFileW(path, GENERIC_WRITE, 0, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
    if (h == INVALID_HANDLE_VALUE) return;
    /* UTF-16LE with a byte order mark: the profile API then reads and
       writes Unicode, so ROM paths with any characters are kept intact. */
    static const uint8_t bom[2] = {0xFF, 0xFE};
    DWORD w;
    WriteFile(h, bom, 2, &w, NULL);
    WriteFile(h, k_default_ini, (DWORD)(wcslen(k_default_ini) * sizeof(wchar_t)), &w, NULL);
    CloseHandle(h);
}

static int clampi(int v, int lo, int hi) { return v < lo ? lo : v > hi ? hi : v; }

int config_load(Config *c)
{
    const wchar_t *ini = config_ini_path();
    int created = 0;
    if (!zen_file_exists(ini)) {
        write_default_ini(ini);
        created = zen_file_exists(ini);
    }
    memset(c, 0, sizeof(*c));
    c->scale = clampi((int)GetPrivateProfileIntW(L"video", L"scale", 4, ini), 1, 12);
    c->fullscreen = GetPrivateProfileIntW(L"video", L"fullscreen", 0, ini) != 0;
    c->integer_scaling = GetPrivateProfileIntW(L"video", L"integer_scaling", 1, ini) != 0;
    c->volume = clampi((int)GetPrivateProfileIntW(L"audio", L"volume", 100, ini), 0, 100);
    c->pause_when_inactive = GetPrivateProfileIntW(L"general", L"pause_when_inactive", 0, ini) != 0;

    wchar_t buf[256];
    for (int a = 0; a < ACT_COUNT; a++) {
        GetPrivateProfileStringW(L"input", k_action_keys[a], k_action_defaults[a], buf,
                                 (DWORD)(sizeof(buf) / sizeof(buf[0])), ini);
        int n = config_parse_keys(buf, c->keys[a], CFG_MAX_KEYS);
        if (n < 0) {
            char *u = zen_to_utf8(k_action_keys[a]);
            zen_logf("zenobia.ini: no valid key for '%s', using the default\n", u ? u : "?");
            free(u);
            n = config_parse_keys(k_action_defaults[a], c->keys[a], CFG_MAX_KEYS);
        }
        c->nkeys[a] = n < 0 ? 0 : n;
    }
    GetPrivateProfileStringW(L"rom", L"last", L"", c->last_rom, CFG_PATH_MAX, ini);

    GetPrivateProfileStringW(L"general", L"console_date", L"", buf, (DWORD)(sizeof(buf) / sizeof(buf[0])), ini);
    if (!config_parse_date(buf, &c->rtc_month, &c->rtc_day)) {
        zen_logf("zenobia.ini: console_date is not MM-DD, using the PC's date\n");
        c->rtc_month = c->rtc_day = 0;
    }
    GetPrivateProfileStringW(L"general", L"resume", L"ask", buf, (DWORD)(sizeof(buf) / sizeof(buf[0])), ini);
    c->resume = config_parse_resume(buf);
    if (c->resume < 0) {
        zen_logf("zenobia.ini: resume is not ask, yes or no, using ask\n");
        c->resume = RESUME_ASK;
    }
    return created;
}

void config_set_last_rom(const wchar_t *rom_path)
{
    WritePrivateProfileStringW(L"rom", L"last", rom_path ? rom_path : L"", config_ini_path());
}

int config_parse_date(const wchar_t *s, int *month, int *day)
{
    while (*s == L' ') s++;
    if (!*s || !_wcsicmp(s, L"pc")) {
        *month = *day = 0;
        return 1;
    }
    int m = 0, d = 0;
    wchar_t extra = 0;
    if (swscanf(s, L"%d-%d%lc", &m, &d, &extra) != 2) return 0;
    static const int days[12] = {31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
    if (m < 1 || m > 12 || d < 1 || d > days[m - 1]) return 0;
    *month = m;
    *day = d;
    return 1;
}

int config_parse_resume(const wchar_t *s)
{
    while (*s == L' ') s++;
    if (!_wcsicmp(s, L"ask")) return RESUME_ASK;
    if (!_wcsicmp(s, L"yes")) return RESUME_YES;
    if (!_wcsicmp(s, L"no")) return RESUME_NO;
    return -1;
}

void config_set_console_date(int month, int day)
{
    wchar_t v[16];
    if (month >= 1 && month <= 12 && day >= 1 && day <= 31) swprintf(v, 16, L"%02d-%02d", month, day);
    else v[0] = 0;
    WritePrivateProfileStringW(L"general", L"console_date", v, config_ini_path());
}

void config_set_resume(int mode)
{
    WritePrivateProfileStringW(L"general", L"resume",
                               mode == RESUME_YES ? L"yes" : mode == RESUME_NO ? L"no" : L"ask", config_ini_path());
}
