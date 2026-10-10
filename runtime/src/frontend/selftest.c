/*
 * Headless self-test: loads and patches the ROM exactly like the window
 * mode, runs N frames with scripted input using the same frame loop as
 * ngp_harness (so screenshots match it pixel for pixel), and writes the last
 * frame as PNG. No window, no audio device.
 *
 *   zenobia --selftest ROM [--patch FILE] [--frames N] [--input "F:BUTTONS:LEN;..."]
 *           [--png OUT.png] [--png-scale N] [--save FLASHFILE] [--untranslated]
 *           [--load-state FILE] [--load-state-at F FILE] [--save-state F FILE]
 *           [--no-flash-commands] [--write-patched OUT] [--log N]
 */
#include "app.h"
#include "bps.h"
#include "saves.h"
#include "sha1.h"

#include "core/flashchip.h"
#include "core/ngp.h"
#include "core/png.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int ngp_shutdown_requested(void);

typedef struct { int frame, len; uint8_t buttons; } InputEvent;
#define MAX_EVENTS 1024
static InputEvent s_events[MAX_EVENTS];
static int s_nevents;

/* Same syntax and semantics as the harness: "FRAME:BUTTONS:LEN;..." with
   BUTTONS from U D L R A B O; LEN defaults to 1. */
static uint8_t parse_buttons(const char *s)
{
    uint8_t b = 0;
    for (; *s && *s != ':' && *s != ';'; s++) {
        switch (*s) {
        case 'U': b |= 0x01; break;
        case 'D': b |= 0x02; break;
        case 'L': b |= 0x04; break;
        case 'R': b |= 0x08; break;
        case 'A': b |= 0x10; break;
        case 'B': b |= 0x20; break;
        case 'O': b |= 0x40; break;
        default: break;
        }
    }
    return b;
}

static void parse_input(const char *spec)
{
    const char *p = spec;
    while (*p && s_nevents < MAX_EVENTS) {
        int frame = atoi(p);
        const char *c1 = strchr(p, ':');
        if (!c1) break;
        uint8_t b = parse_buttons(c1 + 1);
        const char *c2 = strchr(c1 + 1, ':');
        int len = 1;
        const char *semi = strchr(p, ';');
        if (c2 && (!semi || c2 < semi)) len = atoi(c2 + 1);
        s_events[s_nevents++] = (InputEvent){frame, len, b};
        if (!semi) break;
        p = semi + 1;
    }
}

static uint8_t input_for(int frame)
{
    uint8_t b = 0;
    for (int i = 0; i < s_nevents; i++)
        if (frame >= s_events[i].frame && frame < s_events[i].frame + s_events[i].len) b |= s_events[i].buttons;
    return b;
}

static void print_path(const char *label, const wchar_t *path)
{
    char *u = zen_to_utf8(path);
    printf("%s%s\n", label, u ? u : "?");
    free(u);
}

/* Loads a state like the window mode does, but accepts one made with another
   ROM image after noting it (the window mode asks the user). */
static int load_state_noting_rom(const wchar_t *path)
{
    int r = state_load(path, rom_image_sha1(), 0);
    if (r == STATE_ERR_OTHER_ROM) {
        printf("selftest: note: the state was saved with a different ROM image; loading it anyway\n");
        r = state_load(path, rom_image_sha1(), 1);
    }
    return r;
}

int run_selftest(const Options *o)
{
    if (!o->rom) {
        fprintf(stderr, "selftest: no ROM given\n");
        return EXIT_USAGE;
    }
    RomPrep p;
    if (!app_prepare_rom(NULL, o->rom, o->patch, o->untranslated, &p)) {
        int code = p.rom_path && p.file ? EXIT_ROM_REFUSED : EXIT_ROM_UNREADABLE;
        rom_prep_free(&p);
        return code;
    }
    char hex[41];
    printf("selftest: process code page %u%s\n", (unsigned)GetACP(), GetACP() == CP_UTF8 ? " (UTF-8)" : "");
    print_path("selftest: rom ", p.rom_path);
    sha1_hex(p.file_sha1, hex);
    printf("selftest: rom sha1 %s crc32 %08x (%s)\n", hex, (unsigned)p.file_crc, rom_kind_name(p.kind));
    if (p.patched) print_path("selftest: patch applied: ", p.patch_path);
    else printf("selftest: running the file as is%s\n", p.untranslated ? " (untranslated)" : "");

    if (o->write_patched) {
        if (!rom_write_image(&p, o->write_patched)) {
            print_path("selftest: cannot write ", o->write_patched);
            rom_prep_free(&p);
            return EXIT_WRITE_FAILED;
        }
        print_path("selftest: wrote image to ", o->write_patched);
    }
    if (!rom_install(&p)) {
        fprintf(stderr, "selftest: out of memory\n");
        rom_prep_free(&p);
        return EXIT_ROM_UNREADABLE;
    }
    rom_prep_free(&p);
    sha1_hex(rom_image_sha1(), hex);
    printf("selftest: image sha1 %s\n", hex);

    g_flash_commands = !o->no_flash_commands;   /* in-game saving works, as in the window */
    ngp_reset();
    char *save_cp = o->save ? zen_core_path(o->save) : NULL;
    if (o->save) {
        int r = saves_load_flash_file(o->save);
        if (r > 0) print_path("selftest: flash save loaded: ", o->save);
        else if (r < 0) print_path("selftest: note: the flash save is damaged; only its complete records were loaded: ",
                                   o->save);
        g_flash_dirty = false;
    }

    int status = EXIT_OK;
    if (o->load_state) {
        int r = load_state_noting_rom(o->load_state);
        printf("selftest: load state before frame 0: %s\n", r == STATE_OK ? "ok" : state_result_string(r));
        if (r != STATE_OK) status = EXIT_STATE_FAILED;
    }
    if (o->input) parse_input(o->input);

    uint64_t audio_frames = 0;
    int audio_peak = 0;
    int frames_run = 0;
    for (int f = 0; f < o->frames; f++) {
        g_input_state = input_for(f);
        ngp_run_frame();
        frames_run++;
        int16_t audio[4096 * 2];
        for (;;) {   /* drain exactly like the harness */
            size_t n = audio_render(audio, 4096, ngp_now());
            audio_frames += n;
            for (size_t i = 0; i < n * 2; i++) {
                int v = audio[i] < 0 ? -(int)audio[i] : audio[i];
                if (v > audio_peak) audio_peak = v;
            }
            if (n != 4096) break;
        }
        if (o->save_state_file && f == o->save_state_at) {
            int r = state_save(o->save_state_file, rom_image_sha1());
            printf("selftest: save state after frame %d: %s\n", f, r == STATE_OK ? "ok" : state_result_string(r));
            if (r != STATE_OK) status = EXIT_STATE_FAILED;
        }
        if (o->load_state_at_file && f == o->load_state_at) {
            int r = load_state_noting_rom(o->load_state_at_file);
            printf("selftest: load state after frame %d: %s\n", f, r == STATE_OK ? "ok" : state_result_string(r));
            if (r != STATE_OK) status = EXIT_STATE_FAILED;
        }
        if (g_cpu.halted && !g_irq_check && ngp_shutdown_requested()) {
            printf("selftest: the game powered off at frame %d\n", f);
            break;
        }
    }

    if (o->png) {
        char *cp = zen_core_path(o->png);
        int ok = cp && png_write_rgb(cp, g_framebuffer, NGP_SCREEN_W, NGP_SCREEN_H, o->png_scale);
        free(cp);
        if (ok) print_path("selftest: wrote ", o->png);
        else { print_path("selftest: cannot write ", o->png); if (status == EXIT_OK) status = EXIT_PNG_FAILED; }
    }
    if (save_cp && g_flash_dirty) {
        if (!flash_store_save(save_cp)) {
            fprintf(stderr, "selftest: cannot write the flash save\n");
            if (status == EXIT_OK) status = EXIT_SAVE_FAILED;
        }
    }
    free(save_cp);
    printf("selftest: ran %d frames, pc=%06X, framebuffer crc32 %08x, audio %llu frames (peak %d)\n",
           frames_run, (unsigned)g_cpu.pc, (unsigned)bps_crc32(0, g_framebuffer, sizeof(g_framebuffer)),
           (unsigned long long)audio_frames, audio_peak);
    printf("selftest: flash commands %s: %llu bytes programmed, %llu blocks erased\n",
           o->no_flash_commands ? "ignored" : "emulated",
           (unsigned long long)flashchip_programs(), (unsigned long long)flashchip_erases());
    printf("selftest: %s\n", status == EXIT_OK ? "OK" : "FAILED");
    fflush(stdout);
    return status;
}
