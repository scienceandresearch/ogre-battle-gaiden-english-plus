/*
 * Player entry points and command-line options.
 */
#ifndef ZEN_APP_H
#define ZEN_APP_H

#include "romload.h"
#include "util.h"

typedef struct {
    wchar_t *rom;                /* ROM path (first non-option argument) */
    wchar_t *patch;              /* --patch FILE */
    int      selftest;           /* --selftest: headless run */
    int      frames;             /* --frames N (selftest) */
    char    *input;              /* --input "FRAME:BUTTONS:LEN;..." (selftest) */
    wchar_t *png;                /* --png FILE: last frame as PNG */
    int      png_scale;          /* --png-scale N (default 2, like the harness) */
    wchar_t *save;               /* --save FLASHFILE (selftest) */
    wchar_t *load_state;         /* --load-state FILE (selftest, before frame 0) */
    int      load_state_at;      /* --load-state-at F FILE (selftest, after frame F) */
    wchar_t *load_state_at_file;
    int      save_state_at;      /* --save-state F FILE (selftest, after frame F) */
    wchar_t *save_state_file;
    int      untranslated;       /* --untranslated: accept the Japanese ROM without the patch */
    int      no_flash_commands;  /* --no-flash-commands: ignore the game's flash commands
                                    (the core's old behaviour; saving then fails) */
    wchar_t *write_patched;      /* --write-patched OUT */
    double   exit_after;         /* --exit-after SECONDS (window mode) */
    int      console;            /* --console */
    int      log_level;          /* --log N (-1 = default) */
    wchar_t *bps_args[3];        /* --bps-apply SOURCE PATCH OUT */
} Options;

/* Identifies, patches and (after asking when needed) accepts a ROM.
   Interactive: message boxes. Non-interactive: an unrecognised ROM runs as
   is with a warning; the Japanese ROM without a usable patch runs only with
   allow_untranslated. Returns 1 when p holds an image to run. */
int app_prepare_rom(HWND owner, const wchar_t *rom_path, const wchar_t *patch,
                    int allow_untranslated, RomPrep *p);

int run_gui(const Options *o, HINSTANCE inst);
int run_selftest(const Options *o);

/* Exit codes */
enum {
    EXIT_OK = 0,
    EXIT_USAGE = 1,
    EXIT_ROM_UNREADABLE = 2,
    EXIT_ROM_REFUSED = 3,
    EXIT_STATE_FAILED = 4,
    EXIT_WRITE_FAILED = 5,
    EXIT_PNG_FAILED = 6,
    EXIT_SAVE_FAILED = 7,
    EXIT_BPS_BASE = 10        /* --bps-apply: 10 + BPS error code */
};

#endif
