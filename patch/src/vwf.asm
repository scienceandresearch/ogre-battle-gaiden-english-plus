; ===========================================================================
; Variable-width font renderer for window text.
;
; Drop-in replacement for the game's window text routine at 0x200BAC.
;   In : XIY = text buffer  (0x00 = new line, 0x00 0x00 = end, 0x01 = space,
;                            other bytes = character codes)
;        IX  = VRAM map address of the first character cell
;        IZ  = first character tile number to use
;   Out: XIY = address after the 0x00 0x00 terminator
;        IX  = advanced by 0x40 (one map row) per line, like the original
;        DE  = next free tile number
;        XBC preserved (the original routine never touches it)
;
; Each line is rendered into consecutive tiles starting at its first cell.
; Tiles are filled with colour 2 (window background) and glyph pixels are set
; to colour 1, matching the original 8x8 font.
; ===========================================================================

vwf_draw:
        push.l  XBC
        ld.w    DE, IZ                  ; next free tile
vwf_line:
        ld.w    IZ, DE                  ; first tile of this line
        ld.b    B, 0                    ; pixel x
        ld.b    C, 0                    ; columns initialised so far
vwf_char:
        ld.b    A, (XIY+)
        cp.b    A, 1
        jr      C, vwf_eol              ; 0x00: end of line
        jr      Z, vwf_space            ; 0x01: space
        call    vwf_glyph
        jr      vwf_char
vwf_space:
        or.b    C, C
        jr      NZ, vwf_space_w
        add.b   B, 8                    ; leading spaces keep whole cells (cursor column)
        jr      vwf_char
vwf_space_w:
        ld.b    A, (vwf_widths+1)
        add.b   B, A
        jr      vwf_char
vwf_eol:
        ld.w    DE, IZ                  ; next line starts after this line's tiles
        ld.l    XHL, 0
        ld.b    L, C
        add.w   DE, HL
        add.w   IX, 0x40
        ld.b    A, (XIY)
        or.b    A, A
        jr      NZ, vwf_line
        inc.l   1, XIY                  ; consume the second 0x00
        pop.l   XBC
        ret

; ---------------------------------------------------------------------------
; Draw glyph A at pixel x = B on the current line.
;   C = columns initialised (updated), B advanced by the glyph's advance.
; ---------------------------------------------------------------------------
vwf_glyph:
        push.l  XDE
        push.l  XHL
        push.l  XIX
        push.l  XIZ
        ld.l    XHL, 0                  ; W = advance of code A. The index must be
        ld.b    L, A                    ; zero-extended: (XHL+A) takes A as signed,
        add.l   XHL, vwf_widths         ; so codes 0x80-0xFF (the blank glyph 0xDC
        ld.b    W, (XHL)                ; of fill= and center) read width 0
        or.b    W, W
        jrl     Z, vwf_g_exit           ; code without a glyph
        push.w  WA                      ; A = code, W = advance

        ; make sure every column holding ink is initialised
        ld.b    L, B
        add.b   L, W
        sub.b   L, 2
        srl.b   3, L                    ; L = last ink column
vwf_g_init:
        cp.b    C, L
        jr      UGT, vwf_g_draw
        call    vwf_init_col
        inc.b   1, C
        jr      vwf_g_init

vwf_g_draw:
        ld.l    XHL, 0                  ; XHL = tile address of column x>>3, row 0
        ld.b    L, B
        srl.b   3, L
        add.w   HL, IZ
        sll.w   4, HL
        add.w   HL, 0xA000
        pop.w   WA
        push.w  WA
        ld.l    XIZ, 0                  ; XIZ = glyph rows
        ld.b    IZL, A
        sll.l   3, XIZ
        add.l   XIZ, vwf_glyphs
        ld.b    D, B                    ; D = shift = 2 * (x & 7)
        and.b   D, 7
        sll.b   1, D
        ld.b    E, 8                    ; row counter
vwf_g_row:
        ld.b    A, (XIZ+)
        or.b    A, A
        jr      Z, vwf_g_next
        ld.l    XIX, 0                  ; IX = 2bpp mask for these 8 pixels
        ld.b    IXL, A
        sll.w   1, IX
        add.l   XIX, vwf_spread
        ld.w    IX, (XIX)
        ld.w    QIX, IX                 ; XIX = mask << 16
        ld.w    IX, 0
        or.b    D, D
        jr      Z, vwf_g_put
        ld.b    A, D
        srl.l   A, XIX                  ; align to x within the tile pair
vwf_g_put:
        ld.w    WA, QIX
        xor.w   (XHL), WA               ; background 10 -> ink 01
        ld.w    WA, IX
        or.w    WA, WA
        jr      Z, vwf_g_next
        xor.w   (XHL+16), WA            ; spill into the next column's tile
vwf_g_next:
        inc.l   2, XHL
        dec.b   1, E
        jr      NZ, vwf_g_row
        pop.w   WA
        add.b   B, W                    ; x += advance
vwf_g_exit:
        pop.l   XIZ
        pop.l   XIX
        pop.l   XHL
        pop.l   XDE
        ret

; ---------------------------------------------------------------------------
; Initialise column C of the current line: fill tile IZ+C with background
; and point the map cell at it (keeping the cell's palette/flip attributes).
;   IX = map address of the line's first cell. Preserves all registers.
; ---------------------------------------------------------------------------
vwf_init_col:
        push.l  XWA
        push.l  XHL
        push.l  XDE
        ld.l    XHL, 0
        ld.b    L, C
        add.w   HL, IZ                  ; tile number
        ld.w    DE, HL
        sll.w   4, HL
        add.w   HL, 0xA000
        ld.w    WA, 0xAAAA              ; colour 2 = window background
        ld.w    (XHL+0), WA
        ld.w    (XHL+2), WA
        ld.w    (XHL+4), WA
        ld.w    (XHL+6), WA
        ld.w    (XHL+8), WA
        ld.w    (XHL+10), WA
        ld.w    (XHL+12), WA
        ld.w    (XHL+14), WA
        ld.l    XHL, 0                  ; map cell = row base | ((IX + 2C) & 0x3F)
        ld.w    HL, IX
        ld.b    A, C
        sll.b   1, A
        add.b   A, L
        and.b   A, 0x3F
        and.b   L, 0xC0
        or.b    L, A
        ld.b    A, (XHL+1)              ; keep palette/flip bits, set tile bit 8
        and.b   A, 0xFE
        or.b    A, D
        ld.b    (XHL+1), A
        ld.b    (XHL), E
        pop.l   XDE
        pop.l   XHL
        pop.l   XWA
        ret

; ---------------------------------------------------------------------------
; Draw only characters [p0, p1) of a window buffer; characters before p0 are
; only measured (they were drawn on earlier frames). Used by the typewriter.
;   In: XIY = text start, IX = map address of line 0, IZ = tile of line 0,
;       H = p0, L = p1 (byte offsets into the buffer).
;   Preserves all registers except flags.
; ---------------------------------------------------------------------------
vwf_range:
        push.l  XWA
        push.l  XBC
        push.l  XDE
        push.l  XHL
        push.l  XIX
        push.l  XIY
        push.l  XIZ
        ld.l    XWA, 0                  ; push p1 pointer, then p0 pointer
        ld.b    A, L
        add.l   XWA, XIY
        push.l  XWA
        ld.l    XWA, 0
        ld.b    A, H
        add.l   XWA, XIY
        push.l  XWA
        ld.w    DE, IZ
        ld.b    B, 0
        ld.b    C, 0
vr_char:
        cp.l    XIY, (XSP+4)            ; reached p1?
        jrl     Z, vr_done
        ld.b    A, (XIY+)
        cp.b    A, 1
        jr      C, vr_eol
        jr      Z, vr_space
        cp.l    XIY, (XSP)              ; XIY now = char address + 1
        jr      UGT, vr_draw            ; char address >= p0: draw it
        ; measure only: x += advance, columns covered by its ink
        ld.l    XHL, 0                  ; W = advance (index zero-extended, see vwf_glyph)
        ld.b    L, A
        add.l   XHL, vwf_widths
        ld.b    W, (XHL)
        or.b    W, W
        jr      Z, vr_char
        ld.b    L, B
        add.b   L, W
        sub.b   L, 2
        srl.b   3, L
        inc.b   1, L                    ; columns needed = last + 1
        cp.b    C, L
        jr      NC, vr_m_adv
        ld.b    C, L
vr_m_adv:
        add.b   B, W
        jr      vr_char
vr_draw:
        call    vwf_glyph
        jr      vr_char
vr_space:
        ld.b    A, (vwf_widths+1)
        add.b   B, A
        jr      vr_char
vr_eol:
        ld.w    DE, IZ                  ; next line's first tile = IZ + columns
        ld.l    XHL, 0
        ld.b    L, C
        add.w   DE, HL
        ld.w    IZ, DE
        add.w   IX, 0x40
        ld.b    B, 0
        ld.b    C, 0
        jrl     vr_char
vr_done:
        inc.l   8, XSP                  ; drop the two limit pointers
        pop.l   XIZ
        pop.l   XIY
        pop.l   XIX
        pop.l   XHL
        pop.l   XDE
        pop.l   XBC
        pop.l   XWA
        ret
