/*
 * Keyboard and XInput gamepad input. See input.h.
 */
#include "input.h"
#include "util.h"

#include <string.h>
#include <wchar.h>
#include <Xinput.h>

typedef DWORD (WINAPI *XInputGetStateFn)(DWORD user_index, XINPUT_STATE *state);

static uint8_t s_keys[ACT_COUNT][CFG_MAX_KEYS];
static int     s_nkeys[ACT_COUNT];
static uint8_t s_down[256];

static HMODULE          s_xinput;
static XInputGetStateFn s_get_state;
static const char      *s_xinput_name;
static int              s_pad_connected[XUSER_MAX_COUNT];
static double           s_pad_retry[XUSER_MAX_COUNT];

#define STICK_THRESHOLD 16384   /* half deflection counts as a D-pad press */
#define PAD_RETRY_SECONDS 2.0   /* polling an empty slot is slow; retry rarely */

/* Loads one XInput DLL from System32 (never from the game's folder, so a
   DLL dropped next to the game is not loaded). */
static int try_xinput(const wchar_t *wname)
{
    static char name[64];
    HMODULE m = LoadLibraryExW(wname, NULL, LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!m) return 0;
    FARPROC fn = GetProcAddress(m, "XInputGetState");
    if (!fn) {
        FreeLibrary(m);
        return 0;
    }
    s_xinput = m;
    s_get_state = (XInputGetStateFn)(void (*)(void))fn;
    if (!WideCharToMultiByte(CP_UTF8, 0, wname, -1, name, (int)sizeof(name), NULL, NULL)) strcpy(name, "XInput");
    s_xinput_name = name;
    return 1;
}

static void load_xinput(void)
{
    /* Test hook: ZENOBIA_XINPUT="name.dll[,name.dll...]" replaces the list of
       DLL names tried (still from System32 only); a name that does not exist
       simulates a system without XInput (keyboard only). */
    wchar_t list[256];
    DWORD n = GetEnvironmentVariableW(L"ZENOBIA_XINPUT", list, (DWORD)(sizeof(list) / sizeof(list[0])));
    if (n > 0 && n < sizeof(list) / sizeof(list[0])) {
        wchar_t *ctx = NULL;
        for (wchar_t *tok = wcstok(list, L", ", &ctx); tok; tok = wcstok(NULL, L", ", &ctx)) {
            if (wcschr(tok, L'\\') || wcschr(tok, L'/') || wcschr(tok, L':')) continue;   /* bare names only */
            if (try_xinput(tok)) return;
        }
        return;
    }
    static const wchar_t *dlls[] = {L"xinput1_4.dll", L"xinput9_1_0.dll", L"xinput1_3.dll"};
    for (size_t i = 0; i < sizeof(dlls) / sizeof(dlls[0]); i++)
        if (try_xinput(dlls[i])) return;
}

void input_init(const Config *cfg)
{
    memcpy(s_keys, cfg->keys, sizeof(s_keys));
    memcpy(s_nkeys, cfg->nkeys, sizeof(s_nkeys));
    memset(s_down, 0, sizeof(s_down));
    if (!s_xinput) load_xinput();
    for (int i = 0; i < XUSER_MAX_COUNT; i++) {
        s_pad_connected[i] = 0;
        s_pad_retry[i] = 0;
    }
}

void input_shutdown(void)
{
    if (s_xinput) FreeLibrary(s_xinput);
    s_xinput = NULL;
    s_get_state = NULL;
    s_xinput_name = NULL;
}

void input_key(int vk, int down)
{
    if (vk <= 0 || vk > 255) return;
    s_down[vk] = (uint8_t)(down != 0);
    /* generic modifier codes follow their left/right variants */
    s_down[VK_SHIFT]   = (uint8_t)(s_down[VK_LSHIFT] | s_down[VK_RSHIFT] | (vk == VK_SHIFT && down));
    s_down[VK_CONTROL] = (uint8_t)(s_down[VK_LCONTROL] | s_down[VK_RCONTROL] | (vk == VK_CONTROL && down));
    s_down[VK_MENU]    = (uint8_t)(s_down[VK_LMENU] | s_down[VK_RMENU] | (vk == VK_MENU && down));
}

void input_clear(void)
{
    memset(s_down, 0, sizeof(s_down));
}

int input_key_down(int vk)
{
    return vk > 0 && vk <= 255 && s_down[vk];
}

int input_action_down(int act)
{
    if (act < 0 || act >= ACT_COUNT) return 0;
    for (int i = 0; i < s_nkeys[act]; i++)
        if (s_down[s_keys[act][i]]) return 1;
    return 0;
}

int input_is_bound(int act, int vk)
{
    if (act < 0 || act >= ACT_COUNT) return 0;
    for (int i = 0; i < s_nkeys[act]; i++) {
        int k = s_keys[act][i];
        if (k == vk) return 1;
        /* a generic modifier binding matches either side */
        if (k == VK_SHIFT && (vk == VK_LSHIFT || vk == VK_RSHIFT)) return 1;
        if (k == VK_CONTROL && (vk == VK_LCONTROL || vk == VK_RCONTROL)) return 1;
        if (k == VK_MENU && (vk == VK_LMENU || vk == VK_RMENU)) return 1;
    }
    return 0;
}

uint8_t input_game_bits(int use_gamepad, int *gamepad_ff)
{
    uint8_t bits = 0;
    int ff = 0;
    for (int a = 0; a < ACT_GAME_BUTTONS; a++)
        if (input_action_down(a)) bits |= (uint8_t)(1u << a);

    if (use_gamepad && s_get_state) {
        double now = zen_seconds();
        for (DWORD i = 0; i < XUSER_MAX_COUNT; i++) {
            if (!s_pad_connected[i] && now < s_pad_retry[i]) continue;
            XINPUT_STATE st;
            memset(&st, 0, sizeof(st));
            if (s_get_state(i, &st) != ERROR_SUCCESS) {
                s_pad_connected[i] = 0;
                s_pad_retry[i] = now + PAD_RETRY_SECONDS;
                continue;
            }
            s_pad_connected[i] = 1;
            WORD b = st.Gamepad.wButtons;
            if ((b & XINPUT_GAMEPAD_DPAD_UP) || st.Gamepad.sThumbLY > STICK_THRESHOLD) bits |= 0x01;
            if ((b & XINPUT_GAMEPAD_DPAD_DOWN) || st.Gamepad.sThumbLY < -STICK_THRESHOLD) bits |= 0x02;
            if ((b & XINPUT_GAMEPAD_DPAD_LEFT) || st.Gamepad.sThumbLX < -STICK_THRESHOLD) bits |= 0x04;
            if ((b & XINPUT_GAMEPAD_DPAD_RIGHT) || st.Gamepad.sThumbLX > STICK_THRESHOLD) bits |= 0x08;
            if (b & (XINPUT_GAMEPAD_A | XINPUT_GAMEPAD_X)) bits |= 0x10;
            if (b & (XINPUT_GAMEPAD_B | XINPUT_GAMEPAD_Y)) bits |= 0x20;
            if (b & XINPUT_GAMEPAD_START) bits |= 0x40;
            if (st.Gamepad.bRightTrigger > 128) ff = 1;
        }
    }
    /* The real D-pad cannot press opposite directions together. */
    if ((bits & 0x03) == 0x03) bits &= (uint8_t)~0x03;
    if ((bits & 0x0C) == 0x0C) bits &= (uint8_t)~0x0C;
    if (gamepad_ff) *gamepad_ff = ff;
    return bits;
}

int input_gamepads_connected(void)
{
    int n = 0;
    for (int i = 0; i < XUSER_MAX_COUNT; i++) n += s_pad_connected[i];
    return n;
}

const char *input_xinput_name(void)
{
    return s_xinput_name;
}
