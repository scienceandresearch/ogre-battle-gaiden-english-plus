; ---------------------------------------------------------------------------
; Text fixes found by play-testing (round 2 on).
;
; Each fix keeps its hooks (.org inside the original program, with the
; original instruction in a comment) next to its routine. Routines go at
; TEXTFIX_CODE (patch code region, see tools/patch/layout.py), after the
; code included at FREE_CODE.
; ---------------------------------------------------------------------------

; Status / new-unit top bar: the leader's name is copied and padded to 11
; cells by an 8-bit loop (A = 11 - length). English names of 11 or more
; letters made A wrap and wrote about 256 spaces over RAM from 0x6000 (map
; state, camera). The box shows 8 cells, so copy at most 8 letters.
        .org 0x21337D                   ; was: ld.b A, 0xB / sub.b A, C / ldir.b
        call    name_top8
        .db     0, 0                    ; nop, nop; the original pad loop follows

; Items list lines "<name><pad><qty>" (map Items command, organize Item list):
; the name is padded to 10 cells by an 8-bit loop (A = 10 - length), which
; wrapped for English item names of 10 or more letters and overran RAM from
; 0x6000 in normal play. Copy at most 10 letters and pad to 10 cells.
        .org 0x215816                   ; was: ld.b A, 0xA / sub.b A, C / ldir.b /
        call    item_name10             ;      ld.b (XIX+), E / djnz A, 0x21581C
        jr      T, 0x215822
        .db     0, 0, 0, 0, 0, 0

; Lists composed at 0x6000 and drawn by the window renderer: a leading VWF
; marker makes the whole list variable-width, so long English names fit.
        .org 0x208A58                   ; tarot card list (command bar, stock full);
        call    list_vwf_start          ; was: lda XIX, (0x6000)
        .org 0x207447                   ; shop list names (prices are drawn from the
        call    list_vwf_start          ; end pointer, after the names);
        .db     0                       ; was: ld.l XIX, 0x6000
        .org 0x2057A9                   ; recruit list (class names and costs): full
        call    list_vwf_start          ; class names fit in the VWF (at most 36 tiles
        .db     0                       ; from 0xC0); was: ld.l XIX, 0x6000
        .org 0x206195                   ; unit window class-change list: full class
        call    list_vwf_start          ; names; was: lda XIX, (0x6000)
        .org 0x204A1B                   ; NEXT menu, UNIT list (composer 0x20D610, drawn
        call    list_vwf_start          ; at map 0x9108): same font as the CITY list;
                                        ; was: lda XIX, (0x6000)

; NEXT menu, CITY list (composer 0x204C68; drawn by the window renderer from
; 0x6000 at map 0x910A): each line printed the location record's 8-cell name
; field, which holds the English name cut to 8 letters ("Lichtflo",
; "Kamicros"). The list is drawn with the VWF now (marker at 0x6000) and each
; line gets the full English name from loc_table (src/locname.asm).
        .org 0x204C8D                   ; was: lda XIX, (0x6000)
        call    list_vwf_start
        .org 0x204CCC                   ; was: ld.l XWA, (XIY+1) / ld.l (XIX+), XWA /
        call    city_name               ;      ld.l XWA, (XIY+5) / ld.l (XIX+), XWA
        jr      T, 0x204CD8
        .db     0, 0, 0, 0, 0, 0

; Link battle screen (0x2E3708): the tarot card name (0x20F134 + 10 * card)
; is printed by the tile-mapped printer in fixed cells from column 10. Through
; the remap lookup it got the variable-width entries' long text ("Priestess",
; "Hierophant", "Hanged Man", "Temperance": 9-10 cells, up to the screen
; edge); print the 8-cell in-place text instead.
        .org 0x2E3720                   ; was: call 0x200B72
        call    up_orig                 ; the printer without the remap lookup (src/uitext.asm)

        .org TEXTFIX_CODE
textfix_start:

; In: XIX = destination, XIY = name, BC = length. Copies at most 8 letters;
; returns A = 11 - copied (at least 3) for the original pad loop.
name_top8:
        cp.w    BC, 8
        jr      ULE, nt8_copy
        ld.w    BC, 8
nt8_copy:
        ld.b    A, 11
        sub.b   A, C
        ldir.b  (XIX+), (XIY+)
        ret

; In: XIX = destination, XIY = name, BC = length, E = pad byte. Copies at most
; 10 letters, then pads with E to 10 cells.
item_name10:
        cp.w    BC, 10
        jr      ULE, in10_copy
        ld.w    BC, 10
in10_copy:
        ld.b    A, 10
        sub.b   A, C
        ldir.b  (XIX+), (XIY+)
        or.b    A, A
        ret     Z
in10_pad:
        ld.b    (XIX+), E
        djnz    A, in10_pad
        ret

; Out: XIX = 0x6001 after a VWF marker at 0x6000. Keeps WA.
list_vwf_start:
        ld.l    XIX, 0x6000
        push.w  WA
        ld.b    A, 0xDB                 ; UI_VWF_MARK (src/uitext.asm)
        ld.b    (XIX+), A
        pop.w   WA
        ret

; NEXT menu CITY list line (hook at 0x204CCC): the English name of a location.
;   In: XIY = location record, XIX = list buffer. Out: XIX advanced.
;   Clobbers XWA, BC (the caller reloads BC right after).
; A record without an English name keeps its 8-cell field. The game then
; appends two spaces and an 'S' when the record's flag byte (+9) is set; that
; line is padded with spaces to 56 px first, so the marker stays in one
; column (every name is at most 54 px).
city_name:
        push.l  XHL
        push.l  XIY
        ld.l    XHL, XIY
        call    loc_find                ; XIY = English name (ends with 00)
        ld.b    A, (XIY)
        or.b    A, A
        jr      Z, cn_field
        ld.b    B, (vwf_widths+1)       ; B = width of a space
        ld.b    C, 0                    ; C = width of the line so far
cn_copy:
        ld.b    A, (XIY+)
        or.b    A, A
        jr      Z, cn_pad
        ld.b    (XIX+), A
        ld.l    XHL, 0
        ld.b    L, A
        add.l   XHL, vwf_widths
        add.b   C, (XHL)
        jr      cn_copy
cn_pad:
        ld.l    XIY, (XSP)              ; the record
        cp.b    (XIY+9), 0
        jr      Z, cn_done              ; no marker on this line
        ld.b    A, 1
cn_pad_loop:
        cp.b    C, 56
        jr      NC, cn_done
        ld.b    (XIX+), A
        add.b   C, B
        jr      cn_pad_loop
cn_field:
        ld.l    XIY, (XSP)
        ld.l    XWA, (XIY+1)
        ld.l    (XIX+), XWA
        ld.l    XWA, (XIY+5)
        ld.l    (XIX+), XWA
cn_done:
        pop.l   XIY
        pop.l   XHL
        ret
