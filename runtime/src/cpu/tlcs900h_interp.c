/*
 * TLCS-900/H interpreter.
 *
 * Used for code that has not been statically recompiled (and as the
 * reference the recompiler is tested against). Decoding mirrors
 * tools/recomp/tlcs900.py; semantics come from tlcs900h.h.
 */
#include "../core/ngp.h"
#include "tlcs900h_cycles.h"
#include "tlcs900h_interp.h"

Tlcs900 g_cpu;

static const uint8_t R3_8[8]  = {0xE1, 0xE0, 0xE5, 0xE4, 0xE9, 0xE8, 0xED, 0xEC};
static const uint8_t R3_16[8] = {0xE0, 0xE4, 0xE8, 0xEC, 0xF0, 0xF4, 0xF8, 0xFC};

static uint32_t s_insn_pc;   /* address of the instruction being executed */
static int      s_cyc;       /* states for the current instruction */
static int      s_bad;       /* set when an undefined opcode was hit */

/* ------------------------------------------------------------------ */
/* fetch / operand access                                               */
/* ------------------------------------------------------------------ */

static inline uint8_t f8(void)
{
    uint8_t v = mem_read8(g_cpu.pc);
    g_cpu.pc = (g_cpu.pc + 1) & 0xFFFFFF;
    return v;
}
static inline uint16_t f16(void) { uint16_t lo = f8(); return (uint16_t)(lo | (f8() << 8)); }
static inline uint32_t f24(void) { uint32_t lo = f16(); return lo | ((uint32_t)f8() << 16); }
static inline uint32_t f32(void) { uint32_t lo = f16(); return lo | ((uint32_t)f16() << 16); }

static inline uint32_t reg_rd(int bits, unsigned code)
{
    if (bits == 8) return REG8(code);
    if (bits == 16) return REG16(code);
    return REG32(code);
}

static inline void reg_wr(int bits, unsigned code, uint32_t v)
{
    if (bits == 8) REG8(code) = (uint8_t)v;
    else if (bits == 16) REG16(code) = (uint16_t)v;
    else REG32(code) = v;
}

/* Optional data-access hook for debugging/tracing (harness only). */
void (*g_mem_hook)(uint32_t pc, uint32_t addr, int bits, int write, uint32_t value);

static inline uint32_t mem_rd(int bits, uint32_t a)
{
    uint32_t v;
    if (bits == 8) v = mem_read8(a);
    else if (bits == 16) v = mem_read16(a);
    else v = mem_read32(a);
    if (g_mem_hook) g_mem_hook(s_insn_pc, a & 0xFFFFFF, bits, 0, v);
    return v;
}

static inline void mem_wr(int bits, uint32_t a, uint32_t v)
{
    if (g_mem_hook) g_mem_hook(s_insn_pc, a & 0xFFFFFF, bits, 1, v);
    if (bits == 8) mem_write8(a, (uint8_t)v);
    else if (bits == 16) mem_write16(a, (uint16_t)v);
    else mem_write32(a, v);
}

static inline uint32_t imm(int bits)
{
    if (bits == 8) return f8();
    if (bits == 16) return f16();
    return f32();
}

static inline void push_n(int bits, uint32_t v)
{
    if (bits == 8) tlcs_push8((uint8_t)v);
    else if (bits == 16) tlcs_push16((uint16_t)v);
    else tlcs_push32(v);
}

static inline uint32_t pop_n(int bits)
{
    if (bits == 8) return tlcs_pop8();
    if (bits == 16) return tlcs_pop16();
    return tlcs_pop32();
}

static void undefined_op(const char *where, unsigned a, unsigned b)
{
    s_bad = 1;
    ngp_log("interp: undefined opcode %s %02X/%02X at %06X\n", where, a, b, s_insn_pc);
}

/* ------------------------------------------------------------------ */
#define MRD8(a)      ((uint8_t)mem_rd(8, (a)))
#define MRD16(a)     ((uint16_t)mem_rd(16, (a)))
#define MRD32(a)     (mem_rd(32, (a)))
#define MWR8(a, v)   mem_wr(8, (a), (uint8_t)(v))
#define MWR16(a, v)  mem_wr(16, (a), (uint16_t)(v))
#define MWR32(a, v)  mem_wr(32, (a), (uint32_t)(v))

/* shared operation helpers                                             */
/* ------------------------------------------------------------------ */

/* The eight ALU ops in table order: add adc sub sbc and xor or cp. */
static uint32_t alu8(int which, uint32_t a, uint32_t b, int bits)
{
    switch (which & 7) {
    case 0: return alu_add(a, b, 0, bits);
    case 1: return alu_add(a, b, g_cpu.cf, bits);
    case 2: return alu_sub(a, b, 0, bits);
    case 3: return alu_sub(a, b, g_cpu.cf, bits);
    case 4: return alu_and(a, b, bits);
    case 5: return alu_xor(a, b, bits);
    case 6: return alu_or(a, b, bits);
    default: alu_sub(a, b, 0, bits); return a;   /* cp: no store */
    }
}

static uint32_t shift8(int which, uint32_t v, unsigned n, int bits)
{
    switch (which & 7) {
    case 0: return alu_rlc(v, n, bits);
    case 1: return alu_rrc(v, n, bits);
    case 2: return alu_rl(v, n, bits);
    case 3: return alu_rr(v, n, bits);
    case 4: return alu_sla(v, n, bits);
    case 5: return alu_sra(v, n, bits);
    case 6: return alu_sll(v, n, bits);
    default: return alu_srl(v, n, bits);
    }
}

/* MUL/MULS/DIV/DIVS on register R (8/16-bit code), result in expanded register. */
static void muldiv_reg(int which, int bits, unsigned rcode, uint32_t src)
{
    unsigned wide = bits == 8 ? (rcode & ~1u) : (rcode & ~3u);
    switch (which & 3) {
    case 0: reg_wr(bits * 2, wide, alu_mulu(reg_rd(bits, rcode), src, bits)); break;
    case 1: reg_wr(bits * 2, wide, alu_muls(reg_rd(bits, rcode), src, bits)); break;
    case 2: reg_wr(bits * 2, wide, alu_divu(reg_rd(bits * 2, wide), src, bits)); break;
    default: reg_wr(bits * 2, wide, alu_divs(reg_rd(bits * 2, wide), src, bits)); break;
    }
}

/* Bit-to-carry ops. which: 0 andcf 1 orcf 2 xorcf 3 ldcf 4 stcf. Returns new value for stcf. */
static uint32_t carry_bit_op(int which, uint32_t v, unsigned n, int bits)
{
    unsigned bit = (v >> n) & 1;
    switch (which) {
    case 0: g_cpu.cf &= (uint8_t)bit; break;
    case 1: g_cpu.cf |= (uint8_t)bit; break;
    case 2: g_cpu.cf ^= (uint8_t)bit; break;
    case 3: g_cpu.cf = (uint8_t)bit; break;
    default:
        v = (v & ~(1u << n)) | ((uint32_t)g_cpu.cf << n);
        break;
    }
    (void)bits;
    return v;
}

static uint32_t cr_read(int bits, unsigned code)
{
    code &= 0x3F;
    if (bits == 8) return g_cpu.cr[code];
    if (bits == 16) { code &= ~1u; return (uint32_t)(g_cpu.cr[code] | (g_cpu.cr[code + 1] << 8)); }
    return tlcs_cr32(code & ~3u);
}

static void cr_write(int bits, unsigned code, uint32_t v)
{
    code &= 0x3F;
    if (bits == 8) g_cpu.cr[code] = (uint8_t)v;
    else if (bits == 16) { code &= ~1u; g_cpu.cr[code] = (uint8_t)v; g_cpu.cr[code + 1] = (uint8_t)(v >> 8); }
    else tlcs_set_cr32(code & ~3u, v);
    /* DMAS/DMAD are 24-bit addresses; INTNEST is 16-bit. */
    g_cpu.cr[0x3E] = g_cpu.cr[0x3F] = 0;
}

/* ------------------------------------------------------------------ */
/* control flow helpers                                                 */
/* ------------------------------------------------------------------ */

static inline void do_jump(uint32_t target) { g_cpu.pc = target & 0xFFFFFF; }

static inline void do_call(uint32_t target)
{
    tlcs_push32(g_cpu.pc);
    g_cpu.pc = target & 0xFFFFFF;
}

static void do_reti(void)
{
    uint16_t sr = tlcs_pop16();
    uint32_t pc = tlcs_pop32();
    tlcs_set_sr(sr);
    g_cpu.pc = pc & 0xFFFFFF;
    uint16_t nest = (uint16_t)(g_cpu.cr[0x3C] | (g_cpu.cr[0x3D] << 8));
    nest--;
    g_cpu.cr[0x3C] = (uint8_t)nest;
    g_cpu.cr[0x3D] = (uint8_t)(nest >> 8);
    g_cpu.irq_inhibit = 1;
}

void cpu_swi(unsigned n);

/* ------------------------------------------------------------------ */
/* effective address decoding for C0-C5 / D0-D5 / E0-E5 / F0-F5           */
/* ------------------------------------------------------------------ */

static uint32_t ext_ea(unsigned first, int *extra)
{
    switch (first & 7) {
    case 0: *extra = 1; return f8();
    case 1: *extra = 2; return f16();
    case 2: *extra = 3; return f24();
    case 3: {
        uint8_t b = f8();
        if ((b & 3) == 0) { *extra = 1; return REG32(b) & 0xFFFFFF; }
        if ((b & 3) == 1) { *extra = 3; int16_t d = (int16_t)f16(); return (REG32(b) + (uint32_t)(int32_t)d) & 0xFFFFFF; }
        if (b == 0x03) {
            uint8_t base = f8(), idx = f8();
            *extra = 3;
            return (REG32(base) + (uint32_t)(int32_t)(int8_t)REG8(idx)) & 0xFFFFFF;
        }
        if (b == 0x07) {
            uint8_t base = f8(), idx = f8();
            *extra = 3;
            return (REG32(base) + (uint32_t)(int32_t)(int16_t)REG16(idx)) & 0xFFFFFF;
        }
        if (b == 0x13) {
            int16_t d = (int16_t)f16();
            *extra = 3;
            return (g_cpu.pc + (uint32_t)(int32_t)d) & 0xFFFFFF;
        }
        undefined_op("ea", first, b);
        *extra = 0;
        return 0;
    }
    case 4: case 5: {
        uint8_t b = f8();
        unsigned step = 1u << (b & 3);
        if ((b & 3) == 3) { undefined_op("prepost", first, b); step = 0; }
        uint32_t *r = &tlcs_reg32p(b)->l;
        *extra = 1;
        if ((first & 7) == 4) { *r -= step; return *r & 0xFFFFFF; }
        uint32_t a = *r & 0xFFFFFF;
        *r += step;
        return a;
    }
    default:
        undefined_op("prefix", first, 0);
        *extra = 0;
        return 0;
    }
}

/* ------------------------------------------------------------------ */
/* source-memory instructions                                           */
/* ------------------------------------------------------------------ */

static void exec_src(unsigned first, int bits, uint32_t ea, const uint8_t *tbl, int extra)
{
    uint8_t op = f8();
    s_cyc = tbl[op] + extra;
    const uint8_t *r3 = bits == 8 ? R3_8 : R3_16;
    int L = bits == 32;

    if (op == 0x04 && !L) { push_n(bits, mem_rd(bits, ea)); return; }
    if ((op == 0x06 || op == 0x07) && bits == 8) {
        uint8_t a = R_A, m = MRD8(ea);
        uint8_t na, nm;
        if (op == 0x06) {          /* RLD */
            na = (uint8_t)((a & 0xF0) | (m >> 4));
            nm = (uint8_t)((m << 4) | (a & 0x0F));
        } else {                   /* RRD */
            na = (uint8_t)((a & 0xF0) | (m & 0x0F));
            nm = (uint8_t)((a << 4) | (m >> 4));
        }
        R_A = na;
        MWR8(ea, nm);
        g_cpu.hf = 0; g_cpu.nf = 0;
        g_cpu.vf = tlcs_parity(na, 8);
        tlcs_szp(na, 8);
        return;
    }
    if (op >= 0x10 && op <= 0x13 && bits != 32) {
        /* LDI/LDIR/LDD/LDDR: (XDE+-),(XHL+-) or (XIX+-),(XIY+-) */
        unsigned dcode = (first & 7) == 5 ? 0xF0 : 0xE8;
        unsigned scode = (first & 7) == 5 ? 0xF4 : 0xEC;
        int step = (bits / 8) * ((op & 2) ? -1 : 1);
        uint32_t s = REG32(scode), d = REG32(dcode);
        mem_wr(bits, d, mem_rd(bits, s));
        REG32(scode) = s + (uint32_t)step;
        REG32(dcode) = d + (uint32_t)step;
        R_BC = (uint16_t)(R_BC - 1);
        g_cpu.hf = 0; g_cpu.nf = 0;
        g_cpu.vf = R_BC != 0;
        if ((op & 1) && R_BC != 0) {   /* repeat: re-execute this instruction */
            g_cpu.pc = s_insn_pc;
            s_cyc = 7;
        }
        return;
    }
    if (op >= 0x14 && op <= 0x17 && bits != 32) {
        /* CPI/CPIR/CPD/CPDR: compare A/WA with (R+-) */
        unsigned pcode = R3_16[first & 7];
        int step = (bits / 8) * ((op & 2) ? -1 : 1);
        uint32_t p = REG32(pcode);
        uint8_t cf = g_cpu.cf;
        alu_sub(reg_rd(bits, 0xE0), mem_rd(bits, p), 0, bits);
        g_cpu.cf = cf;
        REG32(pcode) = p + (uint32_t)step;
        R_BC = (uint16_t)(R_BC - 1);
        g_cpu.vf = R_BC != 0;
        if ((op & 1) && R_BC != 0 && !g_cpu.zf) {
            g_cpu.pc = s_insn_pc;
            s_cyc = 6;
        }
        return;
    }
    if (op == 0x19 && !L) { uint32_t dst = f16(); mem_wr(bits, dst, mem_rd(bits, ea)); return; }
    if (op >= 0x20 && op <= 0x27) { reg_wr(bits, r3[op & 7], mem_rd(bits, ea)); return; }
    if (op >= 0x30 && op <= 0x37 && !L) {
        uint32_t m = mem_rd(bits, ea), r = reg_rd(bits, r3[op & 7]);
        mem_wr(bits, ea, r);
        reg_wr(bits, r3[op & 7], m);
        return;
    }
    if (op >= 0x38 && op <= 0x3F && !L) {
        uint32_t v = imm(bits);
        uint32_t r = alu8(op - 0x38, mem_rd(bits, ea), v, bits);
        if (op != 0x3F) mem_wr(bits, ea, r);
        return;
    }
    if (op >= 0x40 && op <= 0x5F && !L) { muldiv_reg((op - 0x40) >> 3, bits, r3[op & 7], mem_rd(bits, ea)); return; }
    if (op >= 0x60 && op <= 0x6F && !L) {
        unsigned n = op & 7; if (!n) n = 8;
        uint32_t v = mem_rd(bits, ea);
        mem_wr(bits, ea, op < 0x68 ? alu_inc(v, n, bits) : alu_dec(v, n, bits));
        return;
    }
    if (op >= 0x78 && op <= 0x7F && !L) { mem_wr(bits, ea, shift8(op - 0x78, mem_rd(bits, ea), 1, bits)); return; }
    if (op >= 0x80) {
        int which = (op - 0x80) >> 4;
        unsigned rc = r3[op & 7];
        if (op & 8) {     /* op (mem), R */
            uint32_t r = alu8(which, mem_rd(bits, ea), reg_rd(bits, rc), bits);
            if (which != 7) mem_wr(bits, ea, r);
        } else {          /* op R, (mem) */
            uint32_t r = alu8(which, reg_rd(bits, rc), mem_rd(bits, ea), bits);
            if (which != 7) reg_wr(bits, rc, r);
        }
        return;
    }
    undefined_op("src", first, op);
}

/* ------------------------------------------------------------------ */
/* destination-memory instructions                                      */
/* ------------------------------------------------------------------ */

static void exec_dst(unsigned first, uint32_t ea, const uint8_t *tbl, int extra)
{
    uint8_t op = f8();
    s_cyc = tbl[op] + extra;

    switch (op) {
    case 0x00: { uint8_t v = f8(); MWR8(ea, v); return; }
    case 0x02: { uint16_t v = f16(); MWR16(ea, v); return; }
    case 0x04: MWR8(ea, tlcs_pop8()); return;
    case 0x06: MWR16(ea, tlcs_pop16()); return;
    case 0x14: { uint32_t s = f16(); MWR8(ea, MRD8(s)); return; }
    case 0x16: { uint32_t s = f16(); MWR16(ea, MRD16(s)); return; }
    default: break;
    }
    if (op >= 0x20 && op <= 0x27) { REG16(R3_16[op & 7]) = (uint16_t)ea; return; }
    if (op >= 0x28 && op <= 0x2C) {
        unsigned n = R_A & 0x0F;
        if (n & 8) return;    /* undefined for byte operands: no effect */
        uint8_t v = MRD8(ea);
        uint32_t r = carry_bit_op(op - 0x28, v, n, 8);
        if (op == 0x2C) MWR8(ea, (uint8_t)r);
        return;
    }
    if (op >= 0x30 && op <= 0x37) { REG32(R3_16[op & 7]) = ea; return; }
    if (op >= 0x40 && op <= 0x47) { MWR8(ea, REG8(R3_8[op & 7])); return; }
    if (op >= 0x50 && op <= 0x57) { MWR16(ea, REG16(R3_16[op & 7])); return; }
    if (op >= 0x60 && op <= 0x67) { MWR32(ea, REG32(R3_16[op & 7])); return; }
    if (op >= 0x80 && op <= 0xCF) {
        int grp = (op - 0x80) >> 3;
        unsigned n = op & 7;
        uint8_t v = MRD8(ea);
        switch (grp) {
        case 0: case 1: case 2: case 3: carry_bit_op(grp, v, n, 8); return;
        case 4: MWR8(ea, (uint8_t)carry_bit_op(4, v, n, 8)); return;
        case 5: MWR8(ea, (uint8_t)alu_tset(v, n)); return;
        case 6: MWR8(ea, (uint8_t)(v & ~(1u << n))); return;
        case 7: MWR8(ea, (uint8_t)(v | (1u << n))); return;
        case 8: MWR8(ea, (uint8_t)(v ^ (1u << n))); return;
        default: alu_bit(v, n); return;
        }
    }
    if (op >= 0xD0 && op <= 0xDF) {
        if (tlcs_cond(op & 15)) { do_jump(ea); s_cyc += 3; }
        return;
    }
    if (op >= 0xE0 && op <= 0xEF) {
        if (tlcs_cond(op & 15)) { do_call(ea); s_cyc += 8; }
        return;
    }
    if (op >= 0xF0) {
        if (tlcs_cond(op & 15)) { g_cpu.pc = tlcs_pop32() & 0xFFFFFF; s_cyc += 8; }
        return;
    }
    undefined_op("dst", first, op);
}

/* ------------------------------------------------------------------ */
/* register instructions                                                */
/* ------------------------------------------------------------------ */

static void exec_reg(unsigned first, int bits, unsigned rc, const uint8_t *tbl, int extra)
{
    uint8_t op = f8();
    s_cyc = tbl[op] + extra;
    const uint8_t *r3 = bits == 8 ? R3_8 : R3_16;
    int B = bits == 8, W = bits == 16, L = bits == 32;

    switch (op) {
    case 0x03: reg_wr(bits, rc, imm(bits)); return;
    case 0x04: push_n(bits, reg_rd(bits, rc)); return;
    case 0x05: reg_wr(bits, rc, pop_n(bits)); return;
    case 0x06: if (L) break; reg_wr(bits, rc, alu_cpl(reg_rd(bits, rc), bits)); return;
    case 0x07: if (L) break; reg_wr(bits, rc, alu_neg(reg_rd(bits, rc), bits)); return;
    case 0x08: case 0x09: case 0x0A: case 0x0B:
        if (L) break;
        muldiv_reg(op - 0x08, bits, rc, imm(bits));
        return;
    case 0x0C: {
        if (!L) break;
        int16_t d = (int16_t)f16();
        tlcs_push32(REG32(rc));
        REG32(rc) = R_XSP;
        R_XSP += (uint32_t)(int32_t)d;
        return;
    }
    case 0x0D:
        if (!L) break;
        R_XSP = REG32(rc);
        REG32(rc) = tlcs_pop32();
        return;
    case 0x0E: case 0x0F: {
        if (!W) break;
        uint16_t v = REG16(rc);
        if (!v) { g_cpu.vf = 1; return; }
        g_cpu.vf = 0;
        if (op == 0x0E) { int i = 0; while (!((v >> i) & 1)) i++; R_A = (uint8_t)i; }
        else { int i = 15; while (!((v >> i) & 1)) i--; R_A = (uint8_t)i; }
        return;
    }
    case 0x10: if (!B) break; REG8(rc) = alu_daa(REG8(rc)); return;
    case 0x12:
        if (B) break;
        if (W) REG16(rc) &= 0x00FF; else REG32(rc) &= 0xFFFF;
        return;
    case 0x13:
        if (B) break;
        if (W) REG16(rc) = (uint16_t)(int16_t)(int8_t)REG16(rc);
        else REG32(rc) = (uint32_t)(int32_t)(int16_t)REG32(rc);
        return;
    case 0x14:
        if (B) break;
        if (reg_rd(bits, rc) & 1) reg_wr(bits, rc, reg_rd(bits, rc) + 1);
        return;
    case 0x16: if (!W) break; REG16(rc) = alu_mirr(REG16(rc)); return;
    case 0x19: {
        if (!W) break;
        unsigned wide = rc & ~3u;
        int32_t prod = (int32_t)(int16_t)MRD16(R_XDE) * (int32_t)(int16_t)MRD16(R_XHL);
        uint32_t a = REG32(wide), r = a + (uint32_t)prod;
        REG32(wide) = r;
        R_XHL -= 2;
        g_cpu.sf = (uint8_t)(r >> 31);
        g_cpu.zf = r == 0;
        g_cpu.vf = (uint8_t)(((~(a ^ (uint32_t)prod)) & (a ^ r)) >> 31);
        return;
    }
    case 0x1C: {
        if (L) break;
        int8_t d = (int8_t)f8();
        uint32_t v = (reg_rd(bits, rc) - 1) & tlcs_mask(bits);
        reg_wr(bits, rc, v);
        if (v) { do_jump(g_cpu.pc + (uint32_t)(int32_t)d); s_cyc += 2; }
        return;
    }
    case 0x20: case 0x21: case 0x22: case 0x23: case 0x24: {
        if (L) break;
        unsigned n = f8() & 15;
        if (B && n > 7) return;
        uint32_t r = carry_bit_op(op - 0x20, reg_rd(bits, rc), n, bits);
        if (op == 0x24) reg_wr(bits, rc, r);
        return;
    }
    case 0x28: case 0x29: case 0x2A: case 0x2B: case 0x2C: {
        if (L) break;
        unsigned n = R_A & 15;
        if (B && n > 7) return;
        uint32_t r = carry_bit_op(op - 0x28, reg_rd(bits, rc), n, bits);
        if (op == 0x2C) reg_wr(bits, rc, r);
        return;
    }
    case 0x2E: { uint8_t c = f8(); cr_write(bits, c, reg_rd(bits, rc)); return; }
    case 0x2F: { uint8_t c = f8(); reg_wr(bits, rc, cr_read(bits, c)); return; }
    case 0x30: case 0x31: case 0x32: case 0x33: case 0x34: {
        if (L) break;
        unsigned n = f8() & 15;
        if (B) n &= 7;
        uint32_t v = reg_rd(bits, rc);
        switch (op) {
        case 0x30: reg_wr(bits, rc, v & ~(1u << n)); break;
        case 0x31: reg_wr(bits, rc, v | (1u << n)); break;
        case 0x32: reg_wr(bits, rc, v ^ (1u << n)); break;
        case 0x33: alu_bit(v, n); break;
        default:   reg_wr(bits, rc, alu_tset(v, n)); break;
        }
        return;
    }
    case 0x38: case 0x39: case 0x3A: case 0x3C: case 0x3D: case 0x3E: {
        if (!W) break;
        uint16_t num = f16();
        unsigned step = (op & 3) == 0 ? 1 : (op & 3) == 1 ? 2 : 4;
        REG16(rc) = op < 0x3C ? alu_minc(REG16(rc), num, step) : alu_mdec(REG16(rc), num, step);
        return;
    }
    default: break;
    }

    if (op >= 0x40 && op <= 0x5F) { if (L) goto bad; muldiv_reg((op - 0x40) >> 3, bits, r3[op & 7], reg_rd(bits, rc)); return; }
    if (op >= 0x60 && op <= 0x6F) {
        unsigned n = op & 7; if (!n) n = 8;
        uint32_t v = reg_rd(bits, rc);
        if (B) reg_wr(bits, rc, op < 0x68 ? alu_inc(v, n, 8) : alu_dec(v, n, 8));
        else reg_wr(bits, rc, op < 0x68 ? v + n : v - n);   /* word/long: no flags */
        return;
    }
    if (op >= 0x70 && op <= 0x7F) { if (L) goto bad; reg_wr(bits, rc, (uint32_t)tlcs_cond(op & 15)); return; }
    if (op >= 0x80 && op <= 0xC7) {
        unsigned R = r3[op & 7];
        switch ((op - 0x80) >> 3) {
        case 0: reg_wr(bits, R, alu_add(reg_rd(bits, R), reg_rd(bits, rc), 0, bits)); return;
        case 1: reg_wr(bits, R, reg_rd(bits, rc)); return;
        case 2: reg_wr(bits, R, alu_add(reg_rd(bits, R), reg_rd(bits, rc), g_cpu.cf, bits)); return;
        case 3: reg_wr(bits, rc, reg_rd(bits, R)); return;
        case 4: reg_wr(bits, R, alu_sub(reg_rd(bits, R), reg_rd(bits, rc), 0, bits)); return;
        case 5: reg_wr(bits, rc, op & 7); return;
        case 6: reg_wr(bits, R, alu_sub(reg_rd(bits, R), reg_rd(bits, rc), g_cpu.cf, bits)); return;
        case 7: {
            if (L) goto bad;
            uint32_t a = reg_rd(bits, R), b = reg_rd(bits, rc);
            reg_wr(bits, R, b);
            reg_wr(bits, rc, a);
            return;
        }
        default: reg_wr(bits, R, alu_and(reg_rd(bits, R), reg_rd(bits, rc), bits)); return;
        }
    }
    if (op >= 0xC8 && op <= 0xCF) {
        uint32_t v = imm(bits);
        uint32_t r = alu8(op - 0xC8, reg_rd(bits, rc), v, bits);
        if (op != 0xCF) reg_wr(bits, rc, r);
        return;
    }
    if (op >= 0xD0 && op <= 0xD7) { unsigned R = r3[op & 7]; reg_wr(bits, R, alu_xor(reg_rd(bits, R), reg_rd(bits, rc), bits)); return; }
    if (op >= 0xD8 && op <= 0xDF) { if (L) goto bad; alu_sub(reg_rd(bits, rc), op & 7, 0, bits); return; }
    if (op >= 0xE0 && op <= 0xE7) { unsigned R = r3[op & 7]; reg_wr(bits, R, alu_or(reg_rd(bits, R), reg_rd(bits, rc), bits)); return; }
    if (op >= 0xE8 && op <= 0xEF) {
        unsigned n = f8() & 15; if (!n) n = 16;
        reg_wr(bits, rc, shift8(op - 0xE8, reg_rd(bits, rc), n, bits));
        s_cyc += (int)(n >> 2);
        return;
    }
    if (op >= 0xF0 && op <= 0xF7) { unsigned R = r3[op & 7]; alu_sub(reg_rd(bits, R), reg_rd(bits, rc), 0, bits); return; }
    if (op >= 0xF8) {
        unsigned n = R_A & 15; if (!n) n = 16;
        reg_wr(bits, rc, shift8(op - 0xF8, reg_rd(bits, rc), n, bits));
        s_cyc += (int)(n >> 2);
        return;
    }
bad:
    undefined_op("reg", first, op);
}

/* ------------------------------------------------------------------ */
/* main decoder                                                         */
/* ------------------------------------------------------------------ */

int tlcs_interp_step(void)
{
    s_insn_pc = g_cpu.pc;
    s_bad = 0;
    uint8_t op = f8();
    s_cyc = k_cyc_main[op];

    if (op >= 0x80) {
        if (op <= 0xAF) {
            int bits = op < 0x90 ? 8 : op < 0xA0 ? 16 : 32;
            uint32_t ea = REG32(R3_16[op & 7]);
            int extra = 0;
            if (op & 8) { ea += (uint32_t)(int32_t)(int8_t)f8(); extra = 1; }
            ea &= 0xFFFFFF;
            const uint8_t *tbl = bits == 8 ? ((op & 8) ? k_cyc_88 : k_cyc_80)
                               : bits == 16 ? ((op & 8) ? k_cyc_98 : k_cyc_90) : k_cyc_a0;
            exec_src(op, bits, ea, tbl, extra);
        } else if (op <= 0xBF) {
            uint32_t ea = REG32(R3_16[op & 7]);
            int extra = 0;
            if (op & 8) { ea += (uint32_t)(int32_t)(int8_t)f8(); extra = 1; }
            exec_dst(op, ea & 0xFFFFFF, (op & 8) ? k_cyc_b8 : k_cyc_b0, extra);
        } else {
            unsigned grp = op & 0xF0;   /* C0 D0 E0 F0 */
            unsigned lo = op & 0x0F;
            if (lo <= 5) {
                int extra = 0;
                uint32_t ea = ext_ea(op, &extra) & 0xFFFFFF;
                if (grp == 0xF0) exec_dst(op, ea, k_cyc_f0, extra);
                else {
                    int bits = grp == 0xC0 ? 8 : grp == 0xD0 ? 16 : 32;
                    exec_src(op, bits, ea, grp == 0xC0 ? k_cyc_c0 : grp == 0xD0 ? k_cyc_d0 : k_cyc_e0, extra);
                }
            } else if (lo == 6) {
                undefined_op("main", op, 0);
            } else if (grp == 0xF0) {
                if (op == 0xF7) {        /* LDX (n), n */
                    f8();
                    uint8_t a = f8();
                    f8();
                    uint8_t v = f8();
                    f8();
                    MWR8(a, v);
                } else {                 /* SWI */
                    cpu_swi(op & 7);
                }
            } else {
                int bits = grp == 0xC0 ? 8 : grp == 0xD0 ? 16 : 32;
                unsigned rc;
                int extra = 0;
                if (lo == 7) { rc = f8(); extra = 1; }
                else rc = (bits == 8 ? R3_8 : R3_16)[op & 7];
                exec_reg(op, bits, rc, grp == 0xC0 ? k_cyc_c8 : grp == 0xD0 ? k_cyc_d8 : k_cyc_e8, extra);
            }
        }
        return s_cyc;
    }

    switch (op) {
    case 0x00: break;
    case 0x02: tlcs_push16(tlcs_get_sr()); break;
    case 0x03: tlcs_set_sr(tlcs_pop16()); break;
    case 0x05: g_cpu.halted = 1; break;
    case 0x06: tlcs_set_iff(f8() & 7); g_cpu.irq_inhibit = 1; break;
    case 0x07: do_reti(); break;
    case 0x08: { uint8_t a = f8(); uint8_t v = f8(); MWR8(a, v); break; }
    case 0x09: tlcs_push8(f8()); break;
    case 0x0A: { uint8_t a = f8(); uint16_t v = f16(); MWR16(a, v); break; }
    case 0x0B: tlcs_push16(f16()); break;
    case 0x0C: g_cpu.rfp = (g_cpu.rfp + 1) & 3; break;
    case 0x0D: g_cpu.rfp = (g_cpu.rfp - 1) & 3; break;
    case 0x0E: g_cpu.pc = tlcs_pop32() & 0xFFFFFF; break;
    case 0x0F: { int16_t d = (int16_t)f16(); g_cpu.pc = tlcs_pop32() & 0xFFFFFF; R_XSP += (uint32_t)(int32_t)d; break; }
    case 0x10: g_cpu.cf = 0; g_cpu.nf = 0; g_cpu.hf = 0; break;
    case 0x11: g_cpu.cf = 1; g_cpu.nf = 0; g_cpu.hf = 0; break;
    case 0x12: g_cpu.cf ^= 1; g_cpu.nf = 0; break;
    case 0x13: g_cpu.cf = !g_cpu.zf; g_cpu.nf = 0; break;
    case 0x14: tlcs_push8(R_A); break;
    case 0x15: R_A = tlcs_pop8(); break;
    case 0x16: tlcs_ex_ff(); break;
    case 0x17: g_cpu.rfp = f8() & 3; break;
    case 0x18: tlcs_push8(tlcs_get_f()); break;
    case 0x19: tlcs_set_f(tlcs_pop8()); break;
    case 0x1A: do_jump(f16()); break;
    case 0x1B: do_jump(f24()); break;
    case 0x1C: { uint32_t t = f16(); do_call(t); break; }
    case 0x1D: { uint32_t t = f24(); do_call(t); break; }
    case 0x1E: { int16_t d = (int16_t)f16(); do_call(g_cpu.pc + (uint32_t)(int32_t)d); break; }
    default:
        if (op >= 0x20 && op <= 0x27) { REG8(R3_8[op & 7]) = f8(); break; }
        if (op >= 0x28 && op <= 0x2F) { tlcs_push16(REG16(R3_16[op & 7])); break; }
        if (op >= 0x30 && op <= 0x37) { REG16(R3_16[op & 7]) = f16(); break; }
        if (op >= 0x38 && op <= 0x3F) { tlcs_push32(REG32(R3_16[op & 7])); break; }
        if (op >= 0x40 && op <= 0x47) { REG32(R3_16[op & 7]) = f32(); break; }
        if (op >= 0x48 && op <= 0x4F) { REG16(R3_16[op & 7]) = tlcs_pop16(); break; }
        if (op >= 0x58 && op <= 0x5F) { REG32(R3_16[op & 7]) = tlcs_pop32(); break; }
        if (op >= 0x60 && op <= 0x6F) {
            int8_t d = (int8_t)f8();
            if (tlcs_cond(op & 15)) { do_jump(g_cpu.pc + (uint32_t)(int32_t)d); s_cyc += 2; }
            break;
        }
        if (op >= 0x70 && op <= 0x7F) {
            int16_t d = (int16_t)f16();
            if (tlcs_cond(op & 15)) { do_jump(g_cpu.pc + (uint32_t)(int32_t)d); s_cyc += 2; }
            break;
        }
        undefined_op("main", op, 0);
        break;
    }
    return s_cyc;
}

int tlcs_interp_last_bad(void) { return s_bad; }
