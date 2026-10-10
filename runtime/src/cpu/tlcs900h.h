/*
 * TLCS-900/H CPU state and instruction semantics.
 *
 * This header is shared by the interpreter (tlcs900h_interp.c) and by the
 * statically recompiled game code, so both execute exactly the same
 * arithmetic, flag and register-file logic.
 */
#ifndef NGP_TLCS900H_H
#define NGP_TLCS900H_H

#include <stdint.h>
#include <stdbool.h>

#ifdef _MSC_VER
#define NGP_INLINE static __forceinline
#else
#define NGP_INLINE static inline __attribute__((always_inline))
#endif

typedef union {
    uint32_t l;
    uint16_t w[2];
    uint8_t  b[4];
} TlcsReg;

typedef struct Tlcs900 {
    TlcsReg  bank[4][4];  /* [bank][XWA, XBC, XDE, XHL] */
    TlcsReg  idx[4];      /* XIX, XIY, XIZ, XSP */
    TlcsReg  dummy;       /* target for invalid register codes */
    uint32_t pc;

    /* Flags, each 0 or 1. */
    uint8_t  sf, zf, hf, vf, nf, cf;
    uint8_t  fprime;      /* F' as a packed byte */
    uint8_t  rfp;         /* register file pointer 0..3 */
    uint8_t  iff;         /* interrupt mask 0..7 */
    uint8_t  halted;

    /* Control registers (LDC), raw little-endian bytes in native layout:
       0x00 DMAS0-3, 0x10 DMAD0-3, 0x20+4n {DMAC lo, DMAC hi, DMAM, 0},
       0x3C INTNEST. */
    uint8_t  cr[0x40];
    uint8_t  irq_inhibit;   /* EI/RETI interrupt shadow */

    /* Timing: `cycles` counts CPU states executed; when it reaches
       `cycles_limit` the code must return to the scheduler. */
    int64_t  cycles;
    int64_t  cycles_limit;
} Tlcs900;

extern Tlcs900 g_cpu;

NGP_INLINE uint32_t tlcs_cr32(unsigned off) {
    return (uint32_t)g_cpu.cr[off] | ((uint32_t)g_cpu.cr[off + 1] << 8) |
           ((uint32_t)g_cpu.cr[off + 2] << 16) | ((uint32_t)g_cpu.cr[off + 3] << 24);
}
NGP_INLINE void tlcs_set_cr32(unsigned off, uint32_t v) {
    g_cpu.cr[off] = (uint8_t)v; g_cpu.cr[off + 1] = (uint8_t)(v >> 8);
    g_cpu.cr[off + 2] = (uint8_t)(v >> 16); g_cpu.cr[off + 3] = (uint8_t)(v >> 24);
}
#define DMA_SRC(ch)   tlcs_cr32(0x00 + 4 * (ch))
#define DMA_DST(ch)   tlcs_cr32(0x10 + 4 * (ch))
#define DMA_COUNT(ch) ((uint16_t)(g_cpu.cr[0x20 + 4 * (ch)] | (g_cpu.cr[0x21 + 4 * (ch)] << 8)))
#define DMA_MODE(ch)  (g_cpu.cr[0x22 + 4 * (ch)])

/* ------------------------------------------------------------------ */
/* Register file access by native register code                         */
/* ------------------------------------------------------------------ */

NGP_INLINE TlcsReg *tlcs_reg32p(unsigned code)
{
    code &= 0xFF;
    if (code < 0x40) return &g_cpu.bank[code >> 4][(code >> 2) & 3];
    if (code >= 0xF0) return &g_cpu.idx[(code >> 2) & 3];
    if (code >= 0xE0) return &g_cpu.bank[g_cpu.rfp][(code >> 2) & 3];
    if (code >= 0xD0) return &g_cpu.bank[(g_cpu.rfp - 1) & 3][(code >> 2) & 3];
    return &g_cpu.dummy;
}

NGP_INLINE uint8_t  *tlcs_reg8p(unsigned code)  { return &tlcs_reg32p(code)->b[code & 3]; }
NGP_INLINE uint16_t *tlcs_reg16p(unsigned code) { return &tlcs_reg32p(code)->w[(code >> 1) & 1]; }

#define REG8(code)  (*tlcs_reg8p(code))
#define REG16(code) (*tlcs_reg16p(code))
#define REG32(code) (tlcs_reg32p(code)->l)

/* Common current-bank registers. */
#define R_A    REG8(0xE0)
#define R_W    REG8(0xE1)
#define R_WA   REG16(0xE0)
#define R_BC   REG16(0xE4)
#define R_XWA  REG32(0xE0)
#define R_XBC  REG32(0xE4)
#define R_XDE  REG32(0xE8)
#define R_XHL  REG32(0xEC)
#define R_XIX  (g_cpu.idx[0].l)
#define R_XIY  (g_cpu.idx[1].l)
#define R_XIZ  (g_cpu.idx[2].l)
#define R_XSP  (g_cpu.idx[3].l)

/* ------------------------------------------------------------------ */
/* Flags / status register                                              */
/* ------------------------------------------------------------------ */

NGP_INLINE uint8_t tlcs_get_f(void)
{
    return (uint8_t)(g_cpu.cf | (g_cpu.nf << 1) | (g_cpu.vf << 2) | (g_cpu.hf << 4) |
                     (g_cpu.zf << 6) | (g_cpu.sf << 7));
}

NGP_INLINE void tlcs_set_f(uint8_t f)
{
    g_cpu.cf = f & 1;
    g_cpu.nf = (f >> 1) & 1;
    g_cpu.vf = (f >> 2) & 1;
    g_cpu.hf = (f >> 4) & 1;
    g_cpu.zf = (f >> 6) & 1;
    g_cpu.sf = (f >> 7) & 1;
}

/* SR: bit15=SYSM(1) 14-12=IFF 11=MAX(1) 10=0 9-8=RFP 7-0=F */
NGP_INLINE uint16_t tlcs_get_sr(void)
{
    return (uint16_t)(0x8800 | (g_cpu.iff << 12) | (g_cpu.rfp << 8) | tlcs_get_f());
}

void tlcs_irq_mask_changed(void);  /* provided by the interrupt controller */

NGP_INLINE void tlcs_set_sr(uint16_t sr)
{
    tlcs_set_f((uint8_t)sr);
    g_cpu.rfp = (sr >> 8) & 3;
    g_cpu.iff = (sr >> 12) & 7;
    tlcs_irq_mask_changed();
}

NGP_INLINE void tlcs_set_iff(unsigned level)
{
    g_cpu.iff = level & 7;
    tlcs_irq_mask_changed();
}

NGP_INLINE void tlcs_ex_ff(void)
{
    uint8_t f = tlcs_get_f();
    tlcs_set_f(g_cpu.fprime);
    g_cpu.fprime = f;
}

/* Condition codes 0..15 */
NGP_INLINE int tlcs_cond(unsigned cc)
{
    switch (cc & 15) {
    case 0:  return 0;
    case 1:  return g_cpu.sf ^ g_cpu.vf;
    case 2:  return g_cpu.zf | (g_cpu.sf ^ g_cpu.vf);
    case 3:  return g_cpu.cf | g_cpu.zf;
    case 4:  return g_cpu.vf;
    case 5:  return g_cpu.sf;
    case 6:  return g_cpu.zf;
    case 7:  return g_cpu.cf;
    case 8:  return 1;
    case 9:  return !(g_cpu.sf ^ g_cpu.vf);
    case 10: return !(g_cpu.zf | (g_cpu.sf ^ g_cpu.vf));
    case 11: return !(g_cpu.cf | g_cpu.zf);
    case 12: return !g_cpu.vf;
    case 13: return !g_cpu.sf;
    case 14: return !g_cpu.zf;
    default: return !g_cpu.cf;
    }
}

/* ------------------------------------------------------------------ */
/* ALU helpers. `bits` is 8, 16 or 32; values are passed zero-extended.  */
/* ------------------------------------------------------------------ */

NGP_INLINE uint32_t tlcs_mask(int bits) { return bits == 32 ? 0xFFFFFFFFu : ((1u << bits) - 1); }

NGP_INLINE uint8_t tlcs_parity(uint32_t v, int bits)
{
    if (bits == 32) return 0;  /* undefined on hardware */
    v ^= v >> 8;
    v ^= v >> 4;
    v ^= v >> 2;
    v ^= v >> 1;
    return (uint8_t)(~v & 1);
}

NGP_INLINE void tlcs_szp(uint32_t r, int bits)
{
    g_cpu.sf = (uint8_t)((r >> (bits - 1)) & 1);
    g_cpu.zf = (r & tlcs_mask(bits)) == 0;
}

NGP_INLINE uint32_t alu_add(uint32_t a, uint32_t b, uint32_t c, int bits)
{
    uint64_t r64 = (uint64_t)a + b + c;
    uint32_t m = tlcs_mask(bits);
    uint32_t r = (uint32_t)r64 & m;
    g_cpu.cf = (uint8_t)((r64 >> bits) & 1);
    g_cpu.vf = (uint8_t)((((a ^ r) & (b ^ r)) >> (bits - 1)) & 1);
    g_cpu.hf = bits == 32 ? 0 : (uint8_t)(((a ^ b ^ r) >> 4) & 1);
    g_cpu.nf = 0;
    tlcs_szp(r, bits);
    return r;
}

NGP_INLINE uint32_t alu_sub(uint32_t a, uint32_t b, uint32_t c, int bits)
{
    uint64_t r64 = (uint64_t)a - b - c;
    uint32_t m = tlcs_mask(bits);
    uint32_t r = (uint32_t)r64 & m;
    g_cpu.cf = (uint8_t)((r64 >> bits) & 1);
    g_cpu.vf = (uint8_t)((((a ^ b) & (a ^ r)) >> (bits - 1)) & 1);
    g_cpu.hf = bits == 32 ? 0 : (uint8_t)(((a ^ b ^ r) >> 4) & 1);
    g_cpu.nf = 1;
    tlcs_szp(r, bits);
    return r;
}

NGP_INLINE uint32_t alu_and(uint32_t a, uint32_t b, int bits)
{
    uint32_t r = a & b;
    g_cpu.cf = 0; g_cpu.nf = 0; g_cpu.hf = 1;
    g_cpu.vf = tlcs_parity(r, bits);
    tlcs_szp(r, bits);
    return r;
}

NGP_INLINE uint32_t alu_or(uint32_t a, uint32_t b, int bits)
{
    uint32_t r = a | b;
    g_cpu.cf = 0; g_cpu.nf = 0; g_cpu.hf = 0;
    g_cpu.vf = tlcs_parity(r, bits);
    tlcs_szp(r, bits);
    return r;
}

NGP_INLINE uint32_t alu_xor(uint32_t a, uint32_t b, int bits)
{
    uint32_t r = a ^ b;
    g_cpu.cf = 0; g_cpu.nf = 0; g_cpu.hf = 0;
    g_cpu.vf = tlcs_parity(r, bits);
    tlcs_szp(r, bits);
    return r;
}

/* INC/DEC with flags (byte registers, byte/word memory). C is unaffected. */
NGP_INLINE uint32_t alu_inc(uint32_t a, uint32_t n, int bits)
{
    uint32_t r = (a + n) & tlcs_mask(bits);
    g_cpu.vf = (uint8_t)((((a ^ r) & (n ^ r)) >> (bits - 1)) & 1);
    g_cpu.hf = (uint8_t)(((a ^ n ^ r) >> 4) & 1);
    g_cpu.nf = 0;
    tlcs_szp(r, bits);
    return r;
}

NGP_INLINE uint32_t alu_dec(uint32_t a, uint32_t n, int bits)
{
    uint32_t r = (a - n) & tlcs_mask(bits);
    g_cpu.vf = (uint8_t)((((a ^ n) & (a ^ r)) >> (bits - 1)) & 1);
    g_cpu.hf = (uint8_t)(((a ^ n ^ r) >> 4) & 1);
    g_cpu.nf = 1;
    tlcs_szp(r, bits);
    return r;
}

NGP_INLINE uint32_t alu_cpl(uint32_t a, int bits)
{
    g_cpu.hf = 1; g_cpu.nf = 1;
    return ~a & tlcs_mask(bits);
}

NGP_INLINE uint32_t alu_neg(uint32_t a, int bits) { return alu_sub(0, a, 0, bits); }

NGP_INLINE void tlcs_shift_flags(uint32_t r, int bits)
{
    g_cpu.hf = 0; g_cpu.nf = 0;
    g_cpu.vf = tlcs_parity(r, bits);
    tlcs_szp(r, bits);
}

/* n: shift count 1..16 */
NGP_INLINE uint32_t alu_rlc(uint32_t a, unsigned n, int bits)
{
    uint32_t m = tlcs_mask(bits);
    for (unsigned i = 0; i < n; i++) {
        uint32_t c = (a >> (bits - 1)) & 1;
        a = ((a << 1) | c) & m;
        g_cpu.cf = (uint8_t)c;
    }
    tlcs_shift_flags(a, bits);
    return a;
}

NGP_INLINE uint32_t alu_rrc(uint32_t a, unsigned n, int bits)
{
    for (unsigned i = 0; i < n; i++) {
        uint32_t c = a & 1;
        a = (a >> 1) | (c << (bits - 1));
        g_cpu.cf = (uint8_t)c;
    }
    tlcs_shift_flags(a, bits);
    return a;
}

NGP_INLINE uint32_t alu_rl(uint32_t a, unsigned n, int bits)
{
    uint32_t m = tlcs_mask(bits);
    for (unsigned i = 0; i < n; i++) {
        uint32_t c = (a >> (bits - 1)) & 1;
        a = ((a << 1) | g_cpu.cf) & m;
        g_cpu.cf = (uint8_t)c;
    }
    tlcs_shift_flags(a, bits);
    return a;
}

NGP_INLINE uint32_t alu_rr(uint32_t a, unsigned n, int bits)
{
    for (unsigned i = 0; i < n; i++) {
        uint32_t c = a & 1;
        a = (a >> 1) | ((uint32_t)g_cpu.cf << (bits - 1));
        g_cpu.cf = (uint8_t)c;
    }
    tlcs_shift_flags(a, bits);
    return a;
}

NGP_INLINE uint32_t alu_sla(uint32_t a, unsigned n, int bits)
{
    uint32_t m = tlcs_mask(bits);
    for (unsigned i = 0; i < n; i++) {
        g_cpu.cf = (uint8_t)((a >> (bits - 1)) & 1);
        a = (a << 1) & m;
    }
    tlcs_shift_flags(a, bits);
    return a;
}

NGP_INLINE uint32_t alu_sra(uint32_t a, unsigned n, int bits)
{
    uint32_t sign = a & (1u << (bits - 1));
    for (unsigned i = 0; i < n; i++) {
        g_cpu.cf = (uint8_t)(a & 1);
        a = (a >> 1) | sign;
    }
    tlcs_shift_flags(a, bits);
    return a;
}

NGP_INLINE uint32_t alu_srl(uint32_t a, unsigned n, int bits)
{
    for (unsigned i = 0; i < n; i++) {
        g_cpu.cf = (uint8_t)(a & 1);
        a >>= 1;
    }
    tlcs_shift_flags(a, bits);
    return a;
}

#define alu_sll alu_sla

NGP_INLINE uint8_t alu_daa(uint8_t a)
{
    uint8_t in = a;
    unsigned v = a;
    if (g_cpu.cf || in > 0x99) {
        v = g_cpu.nf ? v - 0x60 : v + 0x60;
    }
    if (g_cpu.hf || (in & 0x0F) > 0x09) {
        v = g_cpu.nf ? v - 0x06 : v + 0x06;
    }
    uint8_t r = (uint8_t)v;
    if (!g_cpu.nf) g_cpu.cf |= r < in || in > 0x99;
    else           g_cpu.cf |= r > in || in > 0x99;
    g_cpu.vf = tlcs_parity(r, 8);
    g_cpu.hf = (uint8_t)(((r ^ in) >> 4) & 1);
    tlcs_szp(r, 8);
    return r;
}

/* MUL/DIV. Byte forms operate on a 16-bit destination, word forms on 32-bit. */
NGP_INLINE uint32_t alu_mulu(uint32_t a, uint32_t b, int bits)
{
    uint32_t m = tlcs_mask(bits);
    return (a & m) * (b & m);
}

NGP_INLINE uint32_t alu_muls(uint32_t a, uint32_t b, int bits)
{
    int32_t sa = bits == 8 ? (int8_t)a : (int16_t)a;
    int32_t sb = bits == 8 ? (int8_t)b : (int16_t)b;
    uint32_t r = (uint32_t)(sa * sb);
    return bits == 8 ? (r & 0xFFFF) : r;
}

/* Returns remainder<<bits | quotient. Sets V on divide by zero / overflow.
   Divide-by-zero results and the large-quotient behaviour of 8-bit DIV
   follow MAME/NeoPop (which agree with each other). */
NGP_INLINE uint32_t alu_divu(uint32_t dividend, uint32_t divisor, int bits)
{
    uint32_t m = tlcs_mask(bits);
    divisor &= m;
    if (bits == 8) dividend &= 0xFFFF;
    if (divisor == 0) {
        g_cpu.vf = 1;
        uint32_t q = ~(dividend >> bits) & m;
        uint32_t r = dividend & m;
        return (r << bits) | q;
    }
    uint32_t q, r;
    if (bits == 8 && dividend >= 0x200u * divisor) {
        uint32_t diff = dividend - 0x200u * divisor;
        uint32_t range = 0x100u - divisor;
        q = 0x1FFu - diff / range;
        r = diff % range + divisor;
    } else {
        q = dividend / divisor;
        r = dividend % divisor;
    }
    g_cpu.vf = q > m;
    return ((r & m) << bits) | (q & m);
}

NGP_INLINE uint32_t alu_divs(uint32_t dividend, uint32_t divisor, int bits)
{
    uint32_t m = tlcs_mask(bits);
    int64_t sd = bits == 8 ? (int16_t)dividend : (int32_t)dividend;
    int64_t sv = bits == 8 ? (int8_t)divisor : (int16_t)divisor;
    if (sv == 0) {
        g_cpu.vf = 1;
        uint32_t q = ~((uint32_t)sd >> bits) & m;
        uint32_t r = (uint32_t)sd & m;
        return (r << bits) | q;
    }
    int64_t q = sd / sv;
    int64_t r = sd % sv;
    g_cpu.vf = q > (int64_t)m;
    return (((uint32_t)r & m) << bits) | ((uint32_t)q & m);
}

/* Bit operations on registers/memory values. */
NGP_INLINE void alu_bit(uint32_t v, unsigned n)
{
    g_cpu.zf = !((v >> n) & 1);
    g_cpu.hf = 1;
    g_cpu.nf = 0;
}

NGP_INLINE uint32_t alu_tset(uint32_t v, unsigned n)
{
    alu_bit(v, n);
    return v | (1u << n);
}

NGP_INLINE uint16_t alu_mirr(uint16_t v)
{
    uint16_t r = 0;
    for (int i = 0; i < 16; i++) r |= (uint16_t)(((v >> i) & 1) << (15 - i));
    return r;
}

/* MINC/MDEC: modulo increment/decrement used for ring buffers.
   The immediate is encoded as (ring size - step). Semantics follow the
   Toshiba manual (MAME/ares use the MINC test for MDEC as well). */
NGP_INLINE uint16_t alu_minc(uint16_t v, uint16_t imm, unsigned step)
{
    uint32_t num = (uint32_t)imm + step;
    if (num == 0 || num > 0xFFFF) return (uint16_t)(v + step);
    if (v % num == num - step) return (uint16_t)(v - (num - step));
    return (uint16_t)(v + step);
}

NGP_INLINE uint16_t alu_mdec(uint16_t v, uint16_t imm, unsigned step)
{
    uint32_t num = (uint32_t)imm + step;
    if (num == 0 || num > 0xFFFF) return (uint16_t)(v - step);
    if (v % num == 0) return (uint16_t)(v + (num - step));
    return (uint16_t)(v - step);
}

#endif
