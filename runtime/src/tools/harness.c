/*
 * Headless test harness: runs the game with scripted input, writes
 * screenshots and memory dumps, and can trace executed code.
 *
 *   ngp_harness ROM [--frames N] [--out DIR] [--shot F,F,...] [--shot-every K]
 *               [--input "FRAME:BUTTONS:LEN;..."] [--tps 1|2] [--log N] [--date MM-DD]
 *               [--load-state FILE] [--save-state F FILE]
 *               [--poke ADDR=HEX[,ADDR=HEX...][@FRAME]]
 *               [--save FLASHFILE] [--no-flash-commands] [--dump-flash FILE]
 *               [--dump-ram FILE] [--vram F,F,...] [--text-log FILE]
 *               [--trace FILE] [--vm-log FILE] [--ram-usage FILE] [--prof LO-HI]
 *               [--watch R:LO-HI|W:LO-HI] [--watch-frames F-F] [--watch-log FILE]
 *
 * BUTTONS letters: U D L R A B O (Option).
 * --save FLASHFILE   cartridge save file (same format as the player's .sav),
 *                    loaded before --load-state, written at the end if the
 *                    game wrote to the flash chip.
 * --no-flash-commands  ignore the game's flash chip commands (old behaviour:
 *                    in-game saving fails).
 * --poke             bytes (hex, in memory order) written into the 64 KB low
 *                    memory before frame FRAME (default 0: after
 *                    --load-state); repeatable, e.g. --poke 5490=03.
 * --dump-flash FILE  the cartridge image as the game sees it after the run.
 * --date MM-DD       console date reported by the BIOS clock (default: the
 *                    PC's); the year and time of day stay the PC's.
 * --cheat NAME[@FRAME]  one of the player's cheats (goth, heal, level, rep+,
 *                    rep-; core/cheats.h) before FRAME; repeatable.
 */
#include "../core/ngp.h"
#include "../core/cheats.h"
#include "../core/flashchip.h"
#include "../core/png.h"
#include "../core/state.h"
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

extern uint64_t g_interp_insns;
extern uint32_t g_prof_lo, g_prof_hi;
extern uint64_t g_prof_states;
extern void (*g_trace_hook)(uint32_t pc);
int ngp_shutdown_requested(void);

typedef struct { int frame, len; uint8_t buttons; } InputEvent;
static InputEvent s_events[1024];
static int s_nevents;

static uint8_t *s_trace_bits;   /* one bit per ROM byte */

/* Memory watch: logs data accesses in a range (by the interpreter). */
extern void (*g_mem_hook)(uint32_t pc, uint32_t addr, int bits, int write, uint32_t value);
typedef struct { int write; uint32_t lo, hi; } Watch;
static Watch s_watch[16];
static int s_nwatch;
static int s_watch_from = 0, s_watch_to = 0x7FFFFFFF;
static FILE *s_watch_log;
static long s_watch_log_lines, s_watch_log_max = 2000000;
static int s_cur_frame;

/* Per-address RAM usage (0x4000-0x6FFF) with the PC that touched it, for
   finding unused RAM. Each address keeps a bitmask of read/write and the
   number of distinct accessing PCs is tracked approximately. */
static uint8_t  s_ram_flags[0x3000];
static uint32_t s_ram_lastpc[0x3000];
static int      s_ram_usage_on;

static void ram_usage_hook(uint32_t pc, uint32_t addr, int bits, int write, uint32_t value)
{
    (void)value;
    for (int i = 0; i < bits / 8; i++) {
        uint32_t a = addr + (uint32_t)i;
        if (a < 0x4000 || a >= 0x7000) continue;
        s_ram_flags[a - 0x4000] |= (uint8_t)(write ? 2 : 1);
        s_ram_lastpc[a - 0x4000] = pc;
    }
}

typedef struct { uint32_t pc; uint32_t count; uint32_t lo, hi; uint8_t write; } PcStat;
#define PCSTAT_SIZE 65536
static PcStat s_pcstat[PCSTAT_SIZE];

static void pcstat_add(uint32_t pc, uint32_t addr, int write)
{
    uint32_t h = (pc * 2654435761u ^ (uint32_t)write) & (PCSTAT_SIZE - 1);
    for (int i = 0; i < PCSTAT_SIZE; i++) {
        PcStat *e = &s_pcstat[(h + i) & (PCSTAT_SIZE - 1)];
        if (e->count == 0) { e->pc = pc; e->write = (uint8_t)write; e->count = 1; e->lo = e->hi = addr; return; }
        if (e->pc == pc && e->write == write) {
            e->count++;
            if (addr < e->lo) e->lo = addr;
            if (addr > e->hi) e->hi = addr;
            return;
        }
    }
}

static void mem_watch(uint32_t pc, uint32_t addr, int bits, int write, uint32_t value)
{
    if (s_ram_usage_on) ram_usage_hook(pc, addr, bits, write, value);
    if (s_cur_frame < s_watch_from || s_cur_frame > s_watch_to) return;
    for (int i = 0; i < s_nwatch; i++) {
        if (s_watch[i].write != write) continue;
        if (addr < s_watch[i].lo || addr > s_watch[i].hi) continue;
        pcstat_add(pc, addr, write);
        if (s_watch_log && s_watch_log_lines < s_watch_log_max) {
            fprintf(s_watch_log, "%d %06X %c%d %06X %X\n", s_cur_frame, pc, write ? 'W' : 'R', bits, addr, value);
            s_watch_log_lines++;
        }
        return;
    }
}

static int pcstat_cmp(const void *a, const void *b)
{
    const PcStat *x = (const PcStat *)a, *y = (const PcStat *)b;
    if (x->pc != y->pc) return x->pc < y->pc ? -1 : 1;
    return x->write - y->write;
}

/* VM entry log: script addresses entered from outside the VM dispatcher. */
static FILE *s_vm_log;
static uint32_t s_last_pc;
static uint32_t s_vm_seen[65536];
static int s_vm_nseen;

static void vm_entry_check(uint32_t pc)
{
    if (pc == 0x20023D && !(s_last_pc >= 0x20023C && s_last_pc < 0x200A00)) {
        uint32_t xde = REG32(0xE8) & 0xFFFFFF;
        uint32_t key = xde;
        int seen = 0;
        for (int i = 0; i < s_vm_nseen; i++) if (s_vm_seen[i] == key) { seen = 1; break; }
        if (!seen && s_vm_nseen < 65536) {
            s_vm_seen[s_vm_nseen++] = key;
            fprintf(s_vm_log, "%06X from %06X\n", xde, s_last_pc);
        }
    }
    s_last_pc = pc;
}

/* Text log: every string handed to the window renderer (0x200BAC) or the
   tile-mapped UI printer (0x200B72), once per (renderer, source, caller). */
static FILE *s_text_log;
static uint32_t s_text_seen[65536][2];
static int s_text_nseen;

static void text_check(uint32_t pc)
{
    if (pc != 0x200BAC && pc != 0x200B72) return;
    uint32_t src = REG32(0xF4) & 0xFFFFFF;
    uint32_t caller = mem_read32(R_XSP) & 0xFFFFFF;
    uint32_t key0 = (pc == 0x200BAC ? 0x80000000u : 0) | src, key1 = caller;
    for (int i = 0; i < s_text_nseen; i++)
        if (s_text_seen[i][0] == key0 && s_text_seen[i][1] == key1) {
            if (src < 0x200000) break;      /* RAM buffers: log every new content */
            return;
        }
    if (s_text_nseen < 65536) {
        s_text_seen[s_text_nseen][0] = key0;
        s_text_seen[s_text_nseen][1] = key1;
        s_text_nseen++;
    }
    fprintf(s_text_log, "%d %s src=%06X caller=%06X ix=%04X iz=%04X ", s_cur_frame,
            pc == 0x200BAC ? "window" : "uiprint", src, caller,
            REG32(0xF0) & 0xFFFF, REG32(0xF8) & 0xFFFF);
    for (int i = 0; i < 256; i++) {
        uint8_t b = mem_read8(src + (uint32_t)i);
        fprintf(s_text_log, "%02X", b);
        if (b == 0 && i > 0 && mem_read8(src + (uint32_t)i - 1) == 0) break;
    }
    fputc('\n', s_text_log);
}

static void trace_pc(uint32_t pc)
{
    if (s_text_log) text_check(pc);
    if (s_vm_log) vm_entry_check(pc);
    if (!s_trace_bits) return;
    if (pc >= NGP_ROM_BASE && pc < NGP_ROM_BASE + 0x400000) {
        uint32_t o = pc - NGP_ROM_BASE;
        s_trace_bits[o >> 3] |= (uint8_t)(1u << (o & 7));
    }
}

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
    while (*p && s_nevents < 1024) {
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
    for (int i = 0; i < s_nevents; i++) {
        if (frame >= s_events[i].frame && frame < s_events[i].frame + s_events[i].len) b |= s_events[i].buttons;
    }
    return b;
}

/* --poke ADDR=HEX[,ADDR=HEX...][@FRAME]: each HEX is one or more bytes in
   memory order ("03", "30750000"; a single digit is one byte), written into
   g_lowmem at ADDR before FRAME runs. Plain stores: RAM 0x4000-0x7FFF and
   video memory 0x8000-0xBFFF take them as is; the I/O registers 0x00-0xFF
   are not read from this array. */
typedef struct { int frame; uint32_t addr, len; uint8_t data[256]; } Poke;
#define MAX_POKES 256
static Poke s_pokes[MAX_POKES];
static int s_npokes;

static int hex_digit(int c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    return -1;
}

static int parse_poke(const char *spec)
{
    char buf[2048];
    if (strlen(spec) >= sizeof(buf)) return 0;
    strcpy(buf, spec);
    int frame = 0;
    char *at = strchr(buf, '@');
    if (at) {
        *at = 0;
        char *end;
        long f = strtol(at + 1, &end, 10);
        if (end == at + 1 || *end || f < 0 || f > INT_MAX) return 0;
        frame = (int)f;
    }
    for (char *item = buf; item;) {
        char *next = strchr(item, ',');
        if (next) *next++ = 0;
        char *eq = strchr(item, '=');
        if (!eq || s_npokes >= MAX_POKES) return 0;
        *eq = 0;
        char *end;
        unsigned long addr = strtoul(item, &end, 16);
        if (end == item || *end || item[0] == '-' || addr > 0xFFFF) return 0;
        const char *h = eq + 1;
        if (h[0] == '0' && (h[1] == 'x' || h[1] == 'X')) h += 2;
        size_t nd = strlen(h);
        if (nd == 0 || (nd > 1 && nd % 2) || nd > 2 * sizeof(s_pokes[0].data)) return 0;
        Poke *p = &s_pokes[s_npokes];
        p->frame = frame;
        p->addr = (uint32_t)addr;
        p->len = 0;
        if (nd == 1) {
            int v = hex_digit(h[0]);
            if (v < 0) return 0;
            p->data[p->len++] = (uint8_t)v;
        }
        for (size_t i = 0; nd > 1 && i < nd; i += 2) {
            int hi = hex_digit(h[i]), lo = hex_digit(h[i + 1]);
            if (hi < 0 || lo < 0) return 0;
            p->data[p->len++] = (uint8_t)(hi << 4 | lo);
        }
        if (p->addr + p->len > 0x10000) return 0;
        s_npokes++;
        item = next;
    }
    return 1;
}

/* --cheat NAME[@FRAME]: one of the player's cheats (cheats.h), applied before
   FRAME like a poke. */
typedef struct { int frame, id; } CheatAt;
#define MAX_CHEATS 64
static CheatAt s_cheats[MAX_CHEATS];
static int s_ncheats;

static int parse_cheat(const char *spec)
{
    char buf[64];
    if (strlen(spec) >= sizeof(buf) || s_ncheats >= MAX_CHEATS) return 0;
    strcpy(buf, spec);
    int frame = 0;
    char *at = strchr(buf, '@');
    if (at) {
        *at = 0;
        char *end;
        long f = strtol(at + 1, &end, 10);
        if (end == at + 1 || *end || f < 0 || f > INT_MAX) return 0;
        frame = (int)f;
    }
    int id = cheat_lookup(buf);
    if (id < 0) return 0;
    s_cheats[s_ncheats].frame = frame;
    s_cheats[s_ncheats].id = id;
    s_ncheats++;
    return 1;
}

static void apply_cheats(int frame)
{
    for (int i = 0; i < s_ncheats; i++) {
        if (s_cheats[i].frame != frame) continue;
        int ok = cheat_apply(s_cheats[i].id);
        fprintf(stderr, "cheat before frame %d: %s %s\n", frame, cheat_name(s_cheats[i].id),
                ok ? "applied" : "not applied (no game in progress)");
    }
}

static void apply_pokes(int frame)
{
    for (int i = 0; i < s_npokes; i++) {
        const Poke *p = &s_pokes[i];
        if (p->frame != frame) continue;
        memcpy(g_lowmem + p->addr, p->data, p->len);
        fprintf(stderr, "poke before frame %d: %04X <-", frame, (unsigned)p->addr);
        for (uint32_t j = 0; j < p->len && j < 16; j++) fprintf(stderr, " %02X", p->data[j]);
        fprintf(stderr, "%s\n", p->len > 16 ? " ..." : "");
    }
}

/* Blocks recorded in a save file (for the report). */
static void list_save_blocks(const char *path, char *out, size_t n)
{
    out[0] = 0;
    FILE *f = fopen(path, "rb");
    if (!f) return;
    uint8_t h[8];
    size_t used = 0;
    if (fread(h, 1, 8, f) == 8) {
        while (fread(h, 1, 8, f) == 8 && used + 16 < n) {
            uint32_t len = h[4] | (h[5] << 8) | (h[6] << 16) | ((uint32_t)h[7] << 24);
            used += (size_t)snprintf(out + used, n - used, "%s%s%d", used ? " " : "", h[0] ? "1:" : "", h[1]);
            if (fseek(f, (long)len, SEEK_CUR) != 0) break;
        }
    }
    fclose(f);
}

static void print_flash_summary(void)
{
    uint64_t programs = flashchip_programs(), erases = flashchip_erases();
    if (!programs && !erases) return;
    fprintf(stderr, "flash: %llu bytes programmed, %llu blocks erased", (unsigned long long)programs,
            (unsigned long long)erases);
    const char *sep = " (";
    for (int c = 0; c < 2; c++)
        for (int b = 0; b < FLASH_BLOCKS; b++) {
            uint32_t n = flashchip_block_erases(c, b), off, len;
            if (!n) continue;
            flash_block_range(b, &off, &len);
            fprintf(stderr, "%schip %d block %d at %06X: %u", sep, c, b,
                    (unsigned)((c ? 0x800000u : NGP_ROM_BASE) + off), n);
            sep = ", ";
        }
    fprintf(stderr, "%s\n", erases ? ")" : "");
}

static int in_list(int frame, const char *list)
{
    if (!list) return 0;
    const char *p = list;
    while (*p) {
        if (atoi(p) == frame) return 1;
        p = strchr(p, ',');
        if (!p) break;
        p++;
    }
    return 0;
}

int main(int argc, char **argv)
{
    if (argc < 2) {
        fprintf(stderr, "usage: %s ROM [options]\n", argv[0]);
        return 1;
    }
    const char *rom = argv[1];
    int frames = 600, shot_every = 0, tps = 1;
    const char *out = ".", *shots = NULL, *trace = NULL, *dump_ram = NULL, *save = NULL;
    const char *vram_frames = NULL;
    const char *ram_usage = NULL;
    const char *vm_log = NULL;
    const char *load_state = NULL, *save_state = NULL;
    const char *dump_flash = NULL;
    int save_state_frame = -1;
    for (int i = 2; i < argc; i++) {
        if (!strcmp(argv[i], "--frames") && i + 1 < argc) frames = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--no-flash-commands")) g_flash_commands = false;
        else if (!strcmp(argv[i], "--dump-flash") && i + 1 < argc) dump_flash = argv[++i];
        else if (!strcmp(argv[i], "--poke") && i + 1 < argc) {
            if (!parse_poke(argv[++i])) {
                fprintf(stderr, "bad --poke %s (want ADDR=HEX[,ADDR=HEX...][@FRAME], ADDR below 10000)\n", argv[i]);
                return 1;
            }
        }
        else if (!strcmp(argv[i], "--out") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "--shot") && i + 1 < argc) shots = argv[++i];
        else if (!strcmp(argv[i], "--shot-every") && i + 1 < argc) shot_every = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--input") && i + 1 < argc) parse_input(argv[++i]);
        else if (!strcmp(argv[i], "--tps") && i + 1 < argc) tps = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--cheat") && i + 1 < argc) {
            if (!parse_cheat(argv[++i])) {
                fprintf(stderr, "bad --cheat %s (want goth, heal, level, rep+ or rep-, optionally @FRAME)\n", argv[i]);
                return 1;
            }
        }
        else if (!strcmp(argv[i], "--date") && i + 1 < argc) {
            if (sscanf(argv[++i], "%d-%d", &g_rtc_month, &g_rtc_day) != 2 ||
                g_rtc_month < 1 || g_rtc_month > 12 || g_rtc_day < 1 || g_rtc_day > 31) {
                fprintf(stderr, "bad --date %s (want MM-DD)\n", argv[i]);
                return 1;
            }
        }
        else if (!strcmp(argv[i], "--log") && i + 1 < argc) g_log_level = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--trace") && i + 1 < argc) trace = argv[++i];
        else if (!strcmp(argv[i], "--dump-ram") && i + 1 < argc) dump_ram = argv[++i];
        else if (!strcmp(argv[i], "--save") && i + 1 < argc) save = argv[++i];
        else if (!strcmp(argv[i], "--vram") && i + 1 < argc) vram_frames = argv[++i];
        else if (!strcmp(argv[i], "--ram-usage") && i + 1 < argc) ram_usage = argv[++i];
        else if (!strcmp(argv[i], "--vm-log") && i + 1 < argc) vm_log = argv[++i];
        else if (!strcmp(argv[i], "--text-log") && i + 1 < argc) s_text_log = fopen(argv[++i], "w");
        else if (!strcmp(argv[i], "--load-state") && i + 1 < argc) load_state = argv[++i];
        else if (!strcmp(argv[i], "--save-state") && i + 2 < argc) {
            save_state_frame = atoi(argv[++i]);
            save_state = argv[++i];
        }
        else if (!strcmp(argv[i], "--prof") && i + 1 < argc) {
            unsigned lo, hi;
            if (sscanf(argv[++i], "%x-%x", &lo, &hi) != 2) return 1;
            g_prof_lo = lo; g_prof_hi = hi;
        }
        else if (!strcmp(argv[i], "--watch") && i + 1 < argc && s_nwatch < 16) {
            const char *w = argv[++i];
            unsigned lo = 0, hi = 0;
            char kind = w[0];
            if (sscanf(w + 2, "%x-%x", &lo, &hi) != 2) { fprintf(stderr, "bad --watch %s\n", w); return 1; }
            s_watch[s_nwatch++] = (Watch){kind == 'W' || kind == 'w', lo, hi};
        }
        else if (!strcmp(argv[i], "--watch-frames") && i + 1 < argc) {
            if (sscanf(argv[++i], "%d-%d", &s_watch_from, &s_watch_to) != 2) return 1;
        }
        else if (!strcmp(argv[i], "--watch-log") && i + 1 < argc) s_watch_log = fopen(argv[++i], "w");
        else { fprintf(stderr, "unknown option %s\n", argv[i]); return 1; }
    }
    g_ticks_per_state = tps;
    if (!ngp_load_rom(rom)) { fprintf(stderr, "cannot load ROM %s\n", rom); return 1; }
    ngp_reset();
    uint8_t *pristine = NULL;
    if (save) {
        if (load_state) {   /* to keep the save file's blocks after the state replaced the block record */
            pristine = (uint8_t *)malloc(g_rom_size);
            if (pristine) memcpy(pristine, g_rom, g_rom_size);
        }
        if (flash_load_save(save) < 0)
            fprintf(stderr, "warning: flash save %s is damaged or unreadable; only its complete records were loaded\n",
                    save);
    }
    if (load_state && !ngp_state_load(load_state)) {
        fprintf(stderr, "cannot load state %s\n", load_state);
        return 1;
    }
    if (pristine) {
        flash_mark_changed_blocks(pristine);
        free(pristine);
    }
    for (int i = 0; i < s_npokes; i++)
        if (s_pokes[i].frame > 0 && s_pokes[i].frame >= frames)
            fprintf(stderr, "warning: --poke at frame %d is never applied (%d frames run)\n", s_pokes[i].frame, frames);
    apply_pokes(0);   /* right after --load-state (also with --frames 0) */
    apply_cheats(0);
    if (trace) {
        s_trace_bits = (uint8_t *)calloc(0x400000 / 8, 1);
        g_trace_hook = trace_pc;
    }
    if (vm_log) {
        s_vm_log = fopen(vm_log, "w");
        g_trace_hook = trace_pc;
    }
    if (s_text_log) g_trace_hook = trace_pc;

    if (ram_usage) { s_ram_usage_on = 1; g_mem_hook = mem_watch; }
    if (s_nwatch) g_mem_hook = mem_watch;

    char path[1024];
    for (int f = 0; f < frames; f++) {
        s_cur_frame = f;
        if (s_npokes && f > 0) apply_pokes(f);
        if (s_ncheats && f > 0) apply_cheats(f);
        g_input_state = input_for(f);
        uint64_t prof_before = g_prof_states;
        ngp_run_frame();
        if (g_prof_hi) {
            uint64_t used = g_prof_states - prof_before;
            static uint64_t prof_max; static int prof_max_frame;
            if (used > prof_max) { prof_max = used; prof_max_frame = f; }
            if (f == frames - 1)
                fprintf(stderr, "profile: max %llu states in one frame (frame %d), total %llu\n",
                        (unsigned long long)prof_max, prof_max_frame, (unsigned long long)g_prof_states);
        }
        int16_t audio[4096 * 2];
        while (audio_render(audio, 4096, ngp_now()) == 4096) {}
        if ((shot_every && f % shot_every == 0) || in_list(f, shots)) {
            snprintf(path, sizeof(path), "%s/frame_%05d.png", out, f);
            png_write_rgb(path, g_framebuffer, NGP_SCREEN_W, NGP_SCREEN_H, 2);
        }
        if (save_state && f == save_state_frame) {
            if (!ngp_state_save(save_state)) fprintf(stderr, "state save failed\n");
        }
        if (in_list(f, vram_frames)) {
            snprintf(path, sizeof(path), "%s/mem_%05d.bin", out, f);
            FILE *fp = fopen(path, "wb");
            if (fp) { fwrite(g_lowmem, 1, 0x10000, fp); fclose(fp); }
        }
        if (g_cpu.halted && !g_irq_check && ngp_shutdown_requested()) break;
    }
    snprintf(path, sizeof(path), "%s/final.png", out);
    png_write_rgb(path, g_framebuffer, NGP_SCREEN_W, NGP_SCREEN_H, 2);
    fprintf(stderr, "ran %d frames, pc=%06X, interp insns=%llu\n", frames, g_cpu.pc,
            (unsigned long long)g_interp_insns);

    if (dump_ram) {
        FILE *fp = fopen(dump_ram, "wb");
        if (fp) { fwrite(g_lowmem, 1, 0x10000, fp); fclose(fp); }
    }
    if (trace) {
        FILE *fp = fopen(trace, "wb");
        if (fp) { fwrite(s_trace_bits, 1, 0x400000 / 8, fp); fclose(fp); }
    }
    int status = 0;
    print_flash_summary();
    if (save && g_flash_dirty) {
        if (flash_store_save(save)) {
            char blocks[512];
            list_save_blocks(save, blocks, sizeof(blocks));
            fprintf(stderr, "flash save written: %s (blocks %s)\n", save, blocks);
        } else {
            fprintf(stderr, "cannot write flash save %s\n", save);
            status = 1;
        }
    }
    if (dump_flash) {
        uint32_t n = g_rom_data_size && g_rom_data_size <= g_rom_size ? g_rom_data_size : g_rom_size;
        FILE *fp = fopen(dump_flash, "wb");
        if (!fp || fwrite(g_rom, 1, n, fp) != n) {
            fprintf(stderr, "cannot write %s\n", dump_flash);
            status = 1;
        }
        if (fp) fclose(fp);
    }
    if (s_nwatch) {
        int n = 0;
        for (int i = 0; i < PCSTAT_SIZE; i++) if (s_pcstat[i].count) s_pcstat[n++] = s_pcstat[i];
        qsort(s_pcstat, (size_t)n, sizeof(PcStat), pcstat_cmp);
        for (int i = 0; i < n; i++)
            printf("%06X %c count=%-8u range=%06X-%06X\n", s_pcstat[i].pc, s_pcstat[i].write ? 'W' : 'R',
                   s_pcstat[i].count, s_pcstat[i].lo, s_pcstat[i].hi);
    }
    if (s_watch_log) fclose(s_watch_log);
    if (s_vm_log) fclose(s_vm_log);
    if (s_text_log) fclose(s_text_log);
    if (ram_usage) {
        FILE *fp = fopen(ram_usage, "wb");
        if (fp) {
            fwrite(s_ram_flags, 1, sizeof(s_ram_flags), fp);
            fwrite(s_ram_lastpc, 4, 0x3000, fp);
            fclose(fp);
        }
    }
    return status;
}
