; ===========================================================================
; Chapter title cards in English (graphics target 'cards', tools/gfx/cards.py;
; notes in docs/workstreams/gfx-chapter-cards.md).
;
; The card scene (main state 0x29EC74) shows the card of a chapter (RAM
; 0x5490, 1-20): an emblem on scroll plane 2 and the lettering on plane 1.
; Bit (chapter - 1) of the cleared-stage bits (RAM 0x546E) picks the set:
; clear = story card (first visit), set = area card (a cleared chapter again).
; Originally the scene's task code (0x29ECB3) copied the chapter's 12x4 layout
; record to RAM 0x6080 and loaded the set's 360-tile sheet to VRAM tile 0x44
; onward, and the scene script drew the layout with gfxfe 0x6080, 0x9208.
; Now every card has its own record (generated from translation/en/cards.txt
; into build/gfx/cards/data.asm), whose map block is that same 12x4 block:
;   hook 1 calls card_load, which does what the old code did, with this
;   card's tiles first;
;   hook 2 (a script ncall) runs card_draw, which draws its map on plane 1.
; The old layout records and sheets stay in the ROM.
; ===========================================================================

; Hook 1: the scene's task code, after its push.l XIY (popped again at
; 0x29ED34). The rest of the old code, up to the sheet load, is skipped.
        .org    0x29ECB4                ; was: ld.b B, (0x5490) / ld.l XWA, (0x546E)
        call    card_load
        jr      0x29ED02                ; palette setup, unchanged

; Hook 2: the scene script. Every path (with or without A/B) draws the
; lettering here; ncall keeps XDE (the script pointer) and XIY (the task).
        .org    0x29EDD4                ; was (script): gfxfe 0x6080, 0x9208
        .db     0x2E                    ; ncall card_draw
        .d24    card_draw
        .db     0xCE, 0x20              ; cnt0 0x20: filler, the next op sets the same

; ---------------------------------------------------------------------------
; Card data (GFX_CARDS): card_story at GFX_CARDS and card_area at
; GFX_CARDS + 0x50 (20 record pointers each, chapters 1-20), then the records:
;   .dl tiles, .dw words (8 per tile), .dw plane-1 map address, .db w, h,
;   w*h map entries (tile 0x44 onward; 0 = blank), then the tiles.
        .org    GFX_CARDS
        .include "../../build/gfx/cards/data.asm"

; card_sets: per set (story, then area): its record table, then the original
; tile sheet and layout table of the set (the addresses the old code loads at
; 0x29ECC4-0x29ECD5).
card_sets:
        .dl     card_story, 0x29F34A, 0x29EEA2
        .dl     card_area, 0x2A09CA, 0x29EECA

; ---------------------------------------------------------------------------
; card_find: the current card. Returns XIX = its record, XIY = its set in
; card_sets, XHL = 2 * (chapter - 1). The set test is the original one; a
; chapter outside 1-20 (never seen) shows chapter 1's card. Clobbers XWA, XBC.
card_find:
        ld.l    XHL, 0
        ld.b    L, (0x5490)             ; chapter 1-20
        dec.b   1, L
        cp.b    L, 20
        jr      C, card_find_index
        ld.b    L, 0
card_find_index:
        ld.b    B, L
        inc.b   1, B                    ; B = chapter
        add.w   HL, HL                  ; 2 * (chapter - 1)
        ld.l    XWA, (0x546E)           ; cleared-stage bits
card_find_bit:
        srl.l   1, XWA
        djnz    B, card_find_bit        ; carry = bit (chapter - 1)
        ld.l    XIY, card_sets          ; story set (ld keeps the carry)
        jr      NC, card_find_set
        ld.l    XIY, card_sets + 12     ; area set
card_find_set:
        ld.l    XIX, (XIY)              ; the set's record table
        add.l   XIX, XHL
        add.l   XIX, XHL                ; + 4 * (chapter - 1)
        ld.l    XIX, (XIX)
        ret

; card_load (hook 1): what the old code did, in the same order, with this
; card's tiles. It copies the card's original layout record to RAM 0x6080
; (0x31 words; nothing reads it now, but the RAM stays as the original leaves
; it), then loads 0xB40 words to VRAM tile 0x44 onward with the game's copy
; routine (0x200B37: XIY = source, IX = destination, BC = words; direct, or
; queued for the VBlank copy when the display is on): first the card's own
; tiles, then the rest of the original sheet. So the copy takes as long as
; the old one, and every other tile is the original's.
card_load:
        call    card_find
        push.l  XIX                     ; the record
        ld.l    XWA, (XIY+4)
        push.l  XWA                     ; the original sheet
        ld.l    XIY, (XIY+8)            ; the original layout table
        add.l   XHL, XIY
        ld.l    XWA, 0
        ld.w    WA, (XHL)               ; offset of the card's layout record
        add.l   XIY, XWA
        ld.l    XIX, 0x6080
        ld.w    BC, 0x31
        ldir.w  (XIX+), (XIY+)          ; as the old code at 0x29ECED
        pop.l   XHL                     ; the original sheet
        pop.l   XIX                     ; the record
        ld.l    XIY, (XIX)              ; the card's tiles
        ld.w    BC, (XIX+4)             ; and their words (8 per tile)
        push.w  BC
        ld.w    IX, 0xA440
        call    0x200B37
        pop.w   WA                      ; words loaded
        ld.w    BC, 0xB40
        sub.w   BC, WA                  ; the rest of the old copy
        ret     ULE                     ; (never: a card has at most 48 tiles)
        extz.l  XWA
        ld.l    XIY, XHL
        add.l   XIY, XWA
        add.l   XIY, XWA                ; the sheet from the next tile on
        ld.w    IX, 0xA440
        add.w   IX, WA
        add.w   IX, WA
        jp      0x200B37

; card_draw (hook 2, script ncall): draw the card's map block on plane 1 with
; the game's map routine (0x2009F1: XIY = [w][h] + entries, IX = map address),
; as gfxfe does.
card_draw:
        push.l  XDE
        push.l  XIY
        call    card_find
        ld.w    WA, (XIX+6)             ; plane-1 map address
        ld.l    XIY, XIX
        add.l   XIY, 8                  ; [w][h] and the entries
        ld.w    IX, WA
        call    0x2009F1
        pop.l   XIY
        pop.l   XDE
        ret
