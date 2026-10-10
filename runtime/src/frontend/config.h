/*
 * Player settings: zenobia.ini next to the executable (created with defaults
 * when missing). Read and updated through the Win32 profile API, so user
 * comments and formatting are kept.
 */
#ifndef ZEN_CONFIG_H
#define ZEN_CONFIG_H

#include <stdint.h>
#include <wchar.h>

enum {
    /* game buttons, in g_input_state bit order */
    ACT_UP, ACT_DOWN, ACT_LEFT, ACT_RIGHT, ACT_A, ACT_B, ACT_OPTION,
    /* player hotkeys */
    ACT_FAST_FORWARD, ACT_PAUSE, ACT_SAVE_STATE, ACT_LOAD_STATE,
    ACT_PREV_SLOT, ACT_NEXT_SLOT, ACT_RESET, ACT_QUIT, ACT_FULLSCREEN,
    ACT_COUNT
};
#define ACT_GAME_BUTTONS 7
#define CFG_MAX_KEYS 4
#define CFG_PATH_MAX 2048

typedef struct {
    int scale;                 /* window size multiple, 1..12 */
    int fullscreen;            /* start in borderless fullscreen */
    int integer_scaling;       /* whole-number zoom when resized */
    int volume;                /* 0..100 */
    int pause_when_inactive;
    uint8_t keys[ACT_COUNT][CFG_MAX_KEYS];
    int nkeys[ACT_COUNT];
    wchar_t last_rom[CFG_PATH_MAX];
} Config;

const wchar_t *config_ini_path(void);
/* Loads settings (creating the file with defaults if missing). Returns 1 if
   the file was created. */
int  config_load(Config *c);
void config_set_last_rom(const wchar_t *rom_path);

/* Parses "Enter, C" style key lists into virtual-key codes. Returns the
   number of keys, or -1 if a non-empty list contains no valid key. */
int  config_parse_keys(const wchar_t *spec, uint8_t *out, int max);
/* Display name of a virtual key ("F5", "Enter", "0x41"...). */
const wchar_t *config_key_name(int vk);
const wchar_t *config_action_key(int act);

#endif
