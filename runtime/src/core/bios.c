/*
 * High-level emulation of the Neo Geo Pocket Color BIOS.
 *
 * No SNK code is used. We build a small synthetic BIOS image containing
 * the system-call vector table at 0xFFFE00; each entry points at a stub
 * address that the dispatcher intercepts and services in C.
 *
 * System calls are made by the game's trampoline (0x366CC9 in this game):
 * it switches to register bank 3, takes the function number from RW3 and
 * calls the address stored at 0xFFFE00 + 4*n. Arguments and results use
 * bank-3 registers (RA3, RB3, RC3, RBC3, XDE3, XHL3).
 */
#include "ngp.h"
#include "state.h"
#include <time.h>

#define BIOS_STUB_BASE   0xFF1000u
#define BIOS_STUB_STRIDE 0x10u
#define BIOS_NUM_CALLS   0x1B
#define BIOS_RETI_ADDR   0xFF23DFu   /* default interrupt handler (RETI) */

/* Bank-3 register codes */
#define RA3   REG8(0x30)
#define RW3   REG8(0x31)
#define RC3   REG8(0x34)
#define RB3   REG8(0x35)
#define RBC3  REG16(0x34)
#define XDE3  REG32(0x38)
#define XHL3  REG32(0x3C)

static const char *k_call_names[BIOS_NUM_CALLS] = {
    "SHUTDOWN", "CLOCKGEARSET", "RTCGET", "?03", "INTLVSET", "SYSFONTSET",
    "FLASHWRITE", "FLASHALLERS", "FLASHERS", "ALARMSET", "?0A", "ALARMDOWNSET",
    "?0C", "FLASHPROTECT", "GEMODESET", "?0F", "COMINIT", "COMSENDSTART",
    "COMRECEIVESTART", "COMCREATEDATA", "COMGETDATA", "COMONRTS", "COMOFFRTS",
    "COMSENDSTATUS", "COMRECEIVESTATUS", "COMCREATEBUFDATA", "COMGETBUFDATA",
};

uint8_t g_clock_gear;

void bios_build_image(void)
{
    memset(g_bios, 0xFF, sizeof(g_bios));
    for (unsigned n = 0; n < BIOS_NUM_CALLS; n++) {
        uint32_t stub = BIOS_STUB_BASE + n * BIOS_STUB_STRIDE;
        uint32_t off = 0xFE00 + n * 4;
        g_bios[off + 0] = (uint8_t)stub;
        g_bios[off + 1] = (uint8_t)(stub >> 8);
        g_bios[off + 2] = (uint8_t)(stub >> 16);
        g_bios[off + 3] = 0;
        g_bios[stub & 0xFFFF] = 0x1F;          /* HLE trap (undefined opcode) */
        g_bios[(stub & 0xFFFF) + 1] = 0x0E;    /* RET */
    }
    g_bios[BIOS_RETI_ADDR & 0xFFFF] = 0x07;    /* RETI */
    /* Reset vector area: park at an infinite loop if ever reached. */
    g_bios[0xFFFE] = 0x68;   /* JR T,-2 */
    g_bios[0xFFFF] = 0xFE;
}

static uint8_t bcd(int v) { return (uint8_t)(((v / 10) << 4) | (v % 10)); }

/*
 * Flash chip size codes. The BIOS identifies each cartridge flash chip at
 * power-on and records its size in the work area: 0x6C58 for the chip at
 * 0x200000 (CS0), 0x6C59 for a second chip at 0x800000 (CS1). Code 0 = no
 * chip, 1 = 4 Mbit (512 KB, 11 blocks), 2 = 8 Mbit (1 MB, 19 blocks),
 * 3 = 16 Mbit (2 MB, 35 blocks). The encoding is the one games depend on:
 * this game's flash routines index a table of three block-address tables
 * with code - 1 (0x36700E -> 0x36701A / 0x367046 / 0x367092), and those hold
 * the start offsets of the 11, 19 and 35 blocks of 4, 8 and 16 Mbit boot
 * block chips (n x 64 KB, then 32, 8, 8 and 16 KB). With the 1 we used to
 * store (copied from older emulators), a 2 MB cartridge's block 28 (save
 * file 1, 0x3C0000) was looked up past the end of the 4 Mbit table and the
 * game erased offset 0xFA000, i.e. game data in block 15, instead.
 *
 * The code follows from the cartridge size: the smallest chip that holds the
 * data (a 512 KB or smaller ROM is a 4 Mbit chip, up to 1 MB an 8 Mbit chip,
 * up to 2 MB a 16 Mbit chip). Cartridges above 2 MB carry a second chip for
 * the bytes beyond 2 MB, sized the same way; a 32 Mbit cartridge is two
 * 16 Mbit chips (3 and 3). So: 2 MB -> 3, 0; 4 MB -> 3, 3; 1 MB -> 2, 0;
 * 512 KB -> 1, 0. Only the game's flash routines read these bytes.
 */
static uint8_t chip_size_code(uint32_t bytes)
{
    if (bytes == 0) return 0;
    if (bytes <= 0x80000u) return 1;
    if (bytes <= 0x100000u) return 2;
    return 3;
}

static void set_chip_sizes(void)
{
    uint32_t size = g_rom_data_size ? g_rom_data_size : g_rom_size;
    if (size > g_rom_size) size = g_rom_size;
    g_lowmem[0x6C58] = chip_size_code(size < 0x200000u ? size : 0x200000u);
    g_lowmem[0x6C59] = chip_size_code(size > 0x200000u ? size - 0x200000u : 0);
}

void bios_boot(void)
{
    const uint8_t *hdr = g_rom;
    uint32_t entry = (uint32_t)hdr[0x1C] | ((uint32_t)hdr[0x1D] << 8) | ((uint32_t)hdr[0x1E] << 16);

    /* CPU state at cartridge entry (values observed on hardware / NeoPop). */
    memset(&g_cpu.bank, 0, sizeof(g_cpu.bank));
    g_cpu.idx[0].l = 0xFF23C3;
    g_cpu.idx[1].l = 0xFF23DF;
    g_cpu.idx[2].l = 0x006480;
    g_cpu.idx[3].l = 0x006C00;
    g_cpu.pc = entry & 0xFFFFFF;
    tlcs_set_sr(0xF800);
    g_cpu.fprime = 0;
    g_cpu.halted = 0;

    /* BIOS work area 0x6C00-0x6FFF */
    memset(g_lowmem + 0x6C00, 0, 0x400);
    mem_write32(0x6C00, entry);
    mem_write16(0x6C04, (uint16_t)(hdr[0x20] | (hdr[0x21] << 8)));
    mem_write16(0x6E82, (uint16_t)(hdr[0x20] | (hdr[0x21] << 8)));
    mem_write8(0x6C06, hdr[0x22]);
    mem_write8(0x6E84, hdr[0x22]);
    for (int i = 0; i < 12; i++) mem_write8(0x6C08 + i, hdr[0x24 + i]);
    set_chip_sizes();               /* 0x6C58, 0x6C59 */
    mem_write8(0x6C55, 0x01);       /* commercial game */
    mem_write8(0x6F80, 0xFF);       /* battery level */
    mem_write8(0x6F81, 0x03);
    mem_write8(0x6F84, 0x40);       /* power-on start */
    mem_write8(0x6F85, 0x00);       /* no shutdown request */
    mem_write8(0x6F86, 0x00);
    mem_write8(0x6F87, 0x00);       /* system language: Japanese (game is JP-only) */
    mem_write8(0x6F91, hdr[0x23]);  /* 0x10 = colour */
    mem_write8(0x6F95, hdr[0x23]);
    for (int i = 0; i < 0x12; i++) mem_write32(0x6FB8 + 4u * (unsigned)i, BIOS_RETI_ADDR);

    /* Interrupt priorities the BIOS leaves behind: INT0=2, INT4=2, INT5=3 */
    io_write(0x70, 0x02);
    io_write(0x71, 0x32);
    io_write(0x6F, 0x4E);
    g_clock_gear = 0;
}

void bios_vblank_hook(void)
{
    /* The BIOS VBlank handler latches the controller into 0x6F82. */
    g_lowmem[0x6F82] = g_input_state;
}

static void call_rtcget(void)
{
    uint32_t dst = XHL3 & 0xFFFFFF;
    time_t now = time(NULL);
    struct tm tmv;
#ifdef _WIN32
    localtime_s(&tmv, &now);
#else
    localtime_r(&now, &tmv);
#endif
    int year = tmv.tm_year % 100;
    if (dst < 0xC000) {
        mem_write8(dst + 0, bcd(year));
        mem_write8(dst + 1, bcd(tmv.tm_mon + 1));
        mem_write8(dst + 2, bcd(tmv.tm_mday));
        mem_write8(dst + 3, bcd(tmv.tm_hour));
        mem_write8(dst + 4, bcd(tmv.tm_min));
        mem_write8(dst + 5, bcd(tmv.tm_sec));
        mem_write8(dst + 6, (uint8_t)(((year & 3) << 4) | (tmv.tm_wday & 0x0F)));
    }
}

static void call_intlvset(void)
{
    static const int8_t map[10] = {
        IRQ_INT0, IRQ_INT5, IRQ_INTT0, IRQ_INTT1, IRQ_INTT2, IRQ_INTT3,
        IRQ_INTTC0, IRQ_INTTC1, IRQ_INTTC2, IRQ_INTTC3,
    };
    unsigned which = RC3, level = RB3 & 7;
    if (which < 10) irq_set_priority(map[which], level);
}

static uint32_t flash_bank_base(unsigned bank) { return bank == 1 ? 0x800000u : NGP_ROM_BASE; }

static void call_flashwrite(void)
{
    uint32_t base = flash_bank_base(RA3);
    uint32_t dst = base + (XDE3 & 0x1FFFFF);
    uint32_t src = XHL3 & 0xFFFFFF;
    uint32_t len = (uint32_t)RBC3 * 256u;
    uint8_t buf[256];
    for (uint32_t off = 0; off < len; off += 256) {
        for (uint32_t i = 0; i < 256; i++) buf[i] = mem_read8(src + off + i);
        flash_write_block(dst + off, buf, 256);
    }
    ngp_log("BIOS FLASHWRITE bank=%u dst=%06X src=%06X len=%u\n", RA3, dst, src, len);
    RA3 = 0;   /* SYS_SUCCESS */
}

static void call_flasherase(void)
{
    ngp_log("BIOS FLASHERS bank=%u block=%u\n", RA3, RB3);
    flash_erase_block(RA3, RB3);
    RA3 = 0;
}

static void call_flashallerase(void)
{
    ngp_log("BIOS FLASHALLERS bank=%u\n", RA3);
    for (int b = 0; b < 35; b++) flash_erase_block(RA3, b);
    RA3 = 0;
}

extern void ngp_request_shutdown(void);

int bios_hle_call(uint32_t pc)
{
    if (pc < BIOS_STUB_BASE || pc >= BIOS_STUB_BASE + BIOS_NUM_CALLS * BIOS_STUB_STRIDE) return 0;
    if ((pc - BIOS_STUB_BASE) % BIOS_STUB_STRIDE) return 0;
    unsigned n = (pc - BIOS_STUB_BASE) / BIOS_STUB_STRIDE;
    if (g_log_level > 1 && n < 0x10) ngp_log("BIOS %s\n", k_call_names[n]);

    switch (n) {
    case 0x00: ngp_request_shutdown(); break;
    case 0x01: g_clock_gear = RB3 & 7; break;
    case 0x02: call_rtcget(); break;
    case 0x04: call_intlvset(); break;
    case 0x05: ngp_log("BIOS SYSFONTSET (not supported)\n"); break;
    case 0x06: call_flashwrite(); break;
    case 0x07: call_flashallerase(); break;
    case 0x08: call_flasherase(); break;
    case 0x09: case 0x0B: case 0x0D: RA3 = 0; break;     /* alarms, protect: success */
    case 0x0E: break;                                    /* GEMODESET: colour mode stays */
    /* Link cable: behave as if no cable is connected. */
    case 0x10: RA3 = 0; break;                           /* COMINIT: COM_BUF_OK */
    case 0x11: case 0x12: break;                         /* send/receive start */
    case 0x13: RA3 = 0; break;                           /* COMCREATEDATA: queued */
    case 0x14: RA3 = 1; break;                           /* COMGETDATA: buffer empty */
    case 0x15: mem_write8(0xB2, 0); break;               /* COMONRTS */
    case 0x16: mem_write8(0xB2, 1); break;               /* COMOFFRTS */
    case 0x17: REG16(0x30) = 0; break;                   /* COMSENDSTATUS: nothing pending */
    case 0x18: REG16(0x30) = 0; break;                   /* COMRECEIVESTATUS: nothing received */
    case 0x19: RB3 = 0; break;                           /* COMCREATEBUFDATA: all sent */
    case 0x1A: break;                                    /* COMGETBUFDATA: nothing */
    default: break;
    }
    /* RET */
    g_cpu.pc = tlcs_pop32() & 0xFFFFFF;
    g_cpu.cycles += 40;
    return 1;
}

void bios_state(StateIO *s)
{
    ST(s, g_clock_gear);
    /* States made before the chip size fix hold code 1 for this 2 MB game,
       which would make the game erase the wrong block: the codes describe
       the cartridge, so they are always set from the loaded one. (Runs after
       the 64 KB of memory is loaded; the file format is unchanged.) */
    if (s->loading && s->ok) set_chip_sizes();
}
