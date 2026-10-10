; ===========================================================================
; Move types ("MOVE: <type>").
;
; The original table at 0x20EB61 has ten 4-cell names, preceded by the
; 4-byte suffix "type" + 00 at 0x20EB5D; code copies them with 32-bit moves,
; name and suffix together (8 bytes ending in 00) or the name alone. The
; English names (ui.txt symbols move_0..move_9, up to 7 letters) are copied
; by these helpers instead:
;
;   mt_copy8_*   name padded to 7 cells with the blank glyph 0xDC, then 00
;                (same 8-byte shape as name + suffix; the blank glyph
;                overwrites what a longer name left behind)
;   mt_copy_d    short name only (5 letters at most), no padding: the deploy
;                list, drawn in a fresh window, has 5 cells (columns 14-18)
; ===========================================================================

MT_PAD = 0xDC

; In: D = index * 4 (0x21338D), B = index * 4 (0x20D5A5), A = index (0x20631A).
; Out: XIX += 8. Clobbers XWA; keeps BC, DE, XHL (0x20D5A5 reads XHL after).
mt_copy8_d4:
        ld.b    A, D
        srl.b   2, A
        jr      mt_copy8_a
mt_copy8_b4:
        ld.b    A, B
        srl.b   2, A
mt_copy8_a:
        push.l  XIY
        push.l  XHL
        call    mt_name                 ; XIY = name
        ld.b    H, 7
mt_c8:
        ld.b    A, (XIY+)
        or.b    A, A
        jr      Z, mt_pad
        ld.b    (XIX+), A
        dec.b   1, H
        jr      NZ, mt_c8
        jr      mt_end
mt_pad:
        ld.b    A, MT_PAD
mt_p:
        ld.b    (XIX+), A
        dec.b   1, H
        jr      NZ, mt_p
mt_end:
        ld.b    A, 0
        ld.b    (XIX+), A
        pop.l   XHL
        pop.l   XIY
        ret

; In: D = index (0x206DCF). Out: short name at (XIX+). Clobbers XIY, XWA;
; keeps BC, XIZ.
mt_copy_d:
        ld.b    A, D
        call    mt_name                 ; XWA = movetype_names + 4 * index
        ld.l    XIY, (XWA+40)           ; the same entry of movetype_short
        jp      loc_copy

; A = index -> XIY = English name. Clobbers XWA.
mt_name:
        and.l   XWA, 0xFF
        cp.b    A, 10
        jr      C, mt_ok
        ld.b    A, 0
mt_ok:
        sll.w   2, WA
        add.l   XWA, movetype_names
        ld.l    XIY, (XWA)
        ret

movetype_names:
        .dl     move_0, move_1, move_2, move_3, move_4
        .dl     move_5, move_6, move_7, move_8, move_9
movetype_short:                         ; must follow movetype_names (offset 40)
        .dl     move_0, move_1, move_2s, move_3, move_4
        .dl     move_5, move_6s, move_7s, move_8, move_9
