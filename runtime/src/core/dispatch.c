/*
 * CPU execution loop: runs recompiled blocks when available, otherwise the
 * interpreter; services interrupts at block/instruction boundaries.
 */
#include "ngp.h"
#include "../cpu/tlcs900h_interp.h"
#include "recomp.h"

uint64_t g_interp_insns;      /* statistics */
uint64_t g_recomp_calls;
int      g_use_recomp = 1;

/* Optional hook for recording every address executed by the interpreter
   (used to feed newly discovered code back into the recompiler). */
void (*g_trace_hook)(uint32_t pc);

/* Optional profiling: CPU states spent with PC inside [g_prof_lo, g_prof_hi). */
uint32_t g_prof_lo, g_prof_hi;
uint64_t g_prof_states;

void cpu_interrupt(uint32_t handler, unsigned level)
{
    tlcs_push32(g_cpu.pc);
    tlcs_push16(tlcs_get_sr());
    g_cpu.iff = (uint8_t)(level < 7 ? level + 1 : 7);
    g_cpu.pc = handler & 0xFFFFFF;
    uint16_t nest = (uint16_t)(g_cpu.cr[0x3C] | (g_cpu.cr[0x3D] << 8));
    nest++;
    g_cpu.cr[0x3C] = (uint8_t)nest;
    g_cpu.cr[0x3D] = (uint8_t)(nest >> 8);
    g_cpu.halted = 0;
    g_cpu.cycles += 18;
}

void cpu_swi(unsigned n)
{
    if (n >= 3 && n <= 6) {
        uint32_t handler = mem_read32(0x6FB8 + 4u * (n - 3)) & 0xFFFFFF;
        cpu_interrupt(handler, g_cpu.iff ? g_cpu.iff - 1 : 0);
        g_cpu.iff = g_cpu.iff;   /* SWI does not change the mask on hardware beyond push */
        return;
    }
    if (n == 1) {
        /* System call via RW3 (bank 3): emulate CALL to the vector table entry. */
        uint32_t entry = mem_read32(0xFFFE00 + 4u * REG8(0x31)) & 0xFFFFFF;
        tlcs_push32(g_cpu.pc);
        g_cpu.pc = entry;
        return;
    }
    ngp_log("SWI %u at %06X ignored\n", n, g_cpu.pc);
}

void cpu_run_until(int64_t limit)
{
    while (g_cpu.cycles < limit) {
        if (g_cpu.irq_inhibit) g_cpu.irq_inhibit = 0;
        else if (g_irq_check) irq_service();

        if (g_cpu.halted) { g_cpu.cycles = limit; return; }

        uint32_t pc = g_cpu.pc;
        if (pc >= 0xFF0000 && bios_hle_call(pc)) continue;

        if (g_use_recomp) {
            RecompFn fn = recomp_lookup(pc);
            if (fn) {
                g_cpu.cycles_limit = limit;
                g_recomp_calls++;
                fn();
                continue;
            }
        }
        if (g_trace_hook) g_trace_hook(pc);
        int st = tlcs_interp_step();
        g_cpu.cycles += st;
        if (pc - g_prof_lo < g_prof_hi - g_prof_lo) g_prof_states += (uint64_t)st;
        g_interp_insns++;
        if (tlcs_interp_last_bad()) {
            ngp_log("CPU stopped: bad instruction at %06X\n", pc);
            g_cpu.halted = 1;
            return;
        }
    }
}
