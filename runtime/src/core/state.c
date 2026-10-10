/*
 * Save state files: "NGPSTAT1" followed by every module's state.
 */
#include "ngp.h"
#include "state.h"

#define STATE_MAGIC "NGPSTAT1"

void st_bytes(StateIO *s, void *p, size_t n)
{
    if (!s->ok) return;
    size_t got = s->loading ? fread(p, 1, n, s->f) : fwrite(p, 1, n, s->f);
    if (got != n) s->ok = 0;
}

static void system_state(StateIO *s)
{
    ST(s, g_cpu);
    st_bytes(s, g_lowmem, sizeof(g_lowmem));
    ST(s, g_tick_base);
    ST(s, g_frame_count);
    ST(s, g_current_line);
    io_state(s);
    irq_state(s);
    timers_state(s);
    k2ge_state(s);
    apu_state(s);
    flash_state(s);
    bios_state(s);
}

int ngp_state_save(const char *path)
{
    FILE *f = fopen(path, "wb");
    if (!f) return 0;
    StateIO s = {f, 0, 1};
    fwrite(STATE_MAGIC, 1, 8, f);
    system_state(&s);
    fclose(f);
    return s.ok;
}

int ngp_state_load(const char *path)
{
    FILE *f = fopen(path, "rb");
    if (!f) return 0;
    char magic[8];
    if (fread(magic, 1, 8, f) != 8 || memcmp(magic, STATE_MAGIC, 8) != 0) {
        fclose(f);
        return 0;
    }
    StateIO s = {f, 1, 1};
    system_state(&s);
    fclose(f);
    if (s.ok) g_irq_check = 1;
    return s.ok;
}
