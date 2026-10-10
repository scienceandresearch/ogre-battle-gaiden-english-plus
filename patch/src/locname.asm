; ===========================================================================
; Location names (see tools/text/locations.py for the data layout).
;
; While a stage is loaded, (0x608E) points at its location table: a count
; byte, then 16-byte records [type][8-cell name][flag][6 data bytes]. The
; game copies the 8-cell name into the town window text (0x207AB5) and,
; after a town-type word, into the liberated / discovered / lost messages
; (routine 0x208DE6). English names are longer than 8 cells, so both paths
; take them from loc_table and draw them with the variable-width font:
;
; * Town window: loc_win_name puts LOC_MARK and a 24-bit pointer to the
;   English name in the name field; loc_win_draw blanks the field again,
;   draws the window text with the original renderer (the numbers stay in
;   the fixed font) and then the name with the VWF on the first row.
; * Messages: loc_compose writes UI_VWF_MARK, the type phrase and a new line
;   (locations with a town type) and the name; the callers then append the
;   English endings (ui.txt symbols loc_msg_*).
;
; loc_table:  [u32 record address][u32 English name] per record, sorted,
;             ended by a zero record address (generated).
; loc_types:  9 x u32 pointers to the type phrases (generated).
; Names and phrases end with 00 00.
; ===========================================================================

LOC_MARK = 0xFF

; ---------------------------------------------------------------------------
; Town window name field (called from 0x207AB5 instead of two 4-byte copies).
;   In: XHL = record, XIX = text buffer. Out: XIX += 8. Clobbers XWA.
; ---------------------------------------------------------------------------
loc_win_name:
        push.l  XIY
        call    loc_find                ; XIY = English name
        ld.l    XWA, XIY
        sll.l   8, XWA
        ld.b    A, LOC_MARK             ; marker + 24-bit pointer
        ld.l    (XIX+), XWA
        ld.l    XWA, 0x01010101         ; rest of the 8-cell field: spaces
        ld.l    (XIX+), XWA
        pop.l   XIY
        ret

; ---------------------------------------------------------------------------
; Town window text (called from 0x207B3A instead of the window renderer).
;   In: XIY = text, IX = map address of the first row, IZ = first tile.
;   Out: XIY, IX, DE as the renderer leaves them for the window text.
; ---------------------------------------------------------------------------
loc_win_draw:
        ld.b    A, (XIY)
        cp.b    A, LOC_MARK
        jp      NZ, 0x200BAC
        ld.l    XWA, (XIY)
        srl.l   8, XWA
        push.l  XWA                     ; English name
        ld.l    XWA, 0x01010101
        ld.l    (XIY), XWA              ; blank the name field again
        push.w  IX                      ; name row
        call    0x200BAC                ; rest of the window, original font
        pop.w   WA
        pop.l   XHL
        push.l  XIY                     ; the renderer's results
        push.w  IX
        push.w  DE
        ld.w    IX, WA
        ld.l    XIY, XHL
        ld.w    WA, DE                  ; DE = VRAM address of the next free tile
        sub.w   WA, 0xA000
        srl.w   4, WA
        ld.w    IZ, WA
        call    vwf_draw
        pop.w   DE
        pop.w   IX
        pop.l   XIY
        ret

; ---------------------------------------------------------------------------
; Message start: "<type phrase>\n<name>" (jumped to from 0x208DE6).
;   In: W = location index, XIX = message buffer. Out: XIX advanced.
; ---------------------------------------------------------------------------
loc_compose:
        ld.l    XDE, (0x608E)           ; location table
        ld.b    A, UI_VWF_MARK
        ld.b    (XIX+), A
        ld.b    A, (XDE+)               ; count
        cp.b    W, A
        jr      NC, lc_church           ; past the last record: Roshfol Church
        ld.l    XHL, 0
        ld.b    L, W
        sll.w   4, HL
        add.l   XHL, XDE                ; record
        ld.l    XWA, 0
        ld.b    A, (XHL)                ; town type
        sll.w   2, WA
        add.l   XWA, loc_types
        ld.l    XIY, (XWA)
        ld.b    A, (XIY)
        or.b    A, A
        jr      Z, lc_name              ; castles, forts: no type phrase
        call    loc_copy
        ld.b    A, 0
        ld.b    (XIX+), A               ; new line
lc_name:
        call    loc_find
        jr      loc_copy
lc_church:
        ld.l    XIY, 0x208E22           ; the church name (remapped in ui.txt)
        call    ui_lookup
loc_copy:                               ; copy (XIY) to (XIX) up to the 00
        ld.b    A, (XIY+)
        or.b    A, A
        ret     Z
        ld.b    (XIX+), A
        jr      loc_copy

; ---------------------------------------------------------------------------
; English name of a record.
;   In: XHL = record (top byte ignored). Out: XIY = name. Preserves the rest.
; ---------------------------------------------------------------------------
loc_find:
        push.l  XWA
        push.l  XBC
        ld.l    XBC, XHL
        and.l   XBC, 0xFFFFFF
        ld.l    XIY, loc_table
lf_loop:
        ld.l    XWA, (XIY)
        cp.l    XWA, 0
        jr      Z, lf_none
        cp.l    XWA, XBC
        jr      Z, lf_hit
        add.l   XIY, 8
        jr      lf_loop
lf_hit:
        ld.l    XIY, (XIY+4)
        jr      lf_done
lf_none:
        ld.l    XIY, loc_none
lf_done:
        pop.l   XBC
        pop.l   XWA
        ret
loc_none:
        .db     0, 0
