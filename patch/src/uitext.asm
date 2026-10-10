; ===========================================================================
; UI text remapping.
;
; The window renderer (0x200BAC) and the tile-mapped printer (0x200B72) look
; their source pointer (XIY) up in ui_remap, a table sorted by original
; address that tools/patch/build.py generates from translation/en/ui.txt.
; On a match the English string is drawn instead (window text optionally
; with the variable-width renderer), and afterwards XIY, IX and DE are left
; exactly as the original routine would have left them for the original
; string, so callers that draw several consecutive strings keep working.
;
; ui_remap:  u16 entry count, u16 0, then 8-byte entries
;            +0 u24 original address  +3 u8 flags (bit 0 = variable width)
;            +4 u24 English address   +7 u8 0
;
; A window string that is not in the table but starts with UI_VWF_MARK is
; drawn (without the marker) by the variable-width renderer; rebuilt tables
; use this for entries the game copies into a RAM buffer before drawing.
; ===========================================================================

UI_VWF_MARK = 0xDB

; ---------------------------------------------------------------------------
; Window renderer entry (jumped to from 0x200BAC).
;   In: XIY = string, IX = map address, IZ = first tile.
; ---------------------------------------------------------------------------
ui_window:
        call    ui_lookup               ; carry: XIY = English, A = flags, XHL = original
        jr      C, uw_remapped
        ld.b    A, (XIY)                ; strings composed by the game (e.g. item
        cp.b    A, UI_VWF_MARK          ; descriptions copied to RAM) can ask for
        jr      NZ, uw_orig             ; the variable-width font with a marker
        inc.l   1, XIY
        jp      vwf_draw
uw_remapped:
        push.l  XHL                     ; original string
        push.w  IX                      ; caller's map address
        push.w  IZ                      ; caller's first tile
        bit.b   0, A
        jr      Z, uw_fixed
        call    vwf_draw
        jr      uw_done
uw_fixed:
        call    uw_orig                 ; original fixed-cell renderer, English text
uw_done:
        pop.w   WA                      ; first tile
        pop.w   IX
        pop.l   XHL
        ld.l    XDE, 0
        ld.w    DE, WA
        call    ui_after_original       ; XIY/IX/DE as for the original string
        sll.w   4, DE                   ; DE = VRAM address of the next tile
        add.w   DE, 0xA000
        ret
uw_orig:
        push.l  XIY                     ; the instructions replaced by the hook
        ld.w    DE, IZ
        ld.l    XWA, 0
        jp      0x200BB1

; ---------------------------------------------------------------------------
; Tile-mapped printer entry (jumped to from 0x200B72).
;   In: XIY = string, IX = map address. The original keeps DE intact.
; ---------------------------------------------------------------------------
ui_print:
        call    ui_lookup
        jr      NC, up_plain
        push.l  XHL
        push.w  IX
        call    up_orig
        pop.w   IX
        pop.l   XHL
        push.l  XDE
        call    ui_after_original
        pop.l   XDE
        ret
up_plain:                               ; not remapped: a string composed with the
        ld.b    A, (XIY)                ; VWF marker (class change and item messages
        cp.b    A, UI_VWF_MARK          ; reach the organize screen's printer too) is
        jr      NZ, up_orig             ; printed in fixed cells without the marker
        inc.l   1, XIY
up_orig:
        ld.w    IZ, (0x4406)            ; the instruction replaced by the hook
        jp      0x200B76

; ---------------------------------------------------------------------------
; Walk the original string at XHL the way the renderers do.
;   In: XHL = string, IX = map address of its first line, DE = first tile.
;   Out: XIY = address after the 00 00 terminator, IX += 0x40 per line,
;        DE += number of non-space characters. Clobbers A.
; ---------------------------------------------------------------------------
ui_after_original:
        ld.l    XIY, XHL
uao_line:
        ld.b    A, (XIY+)
        or.b    A, A
        jr      Z, uao_end              ; 00 at the start of a line: end
uao_char:
        cp.b    A, 1
        jr      Z, uao_next             ; spaces take no tile
        inc.w   1, DE
uao_next:
        ld.b    A, (XIY+)
        or.b    A, A
        jr      NZ, uao_char
        add.w   IX, 0x40                ; end of line
        jr      uao_line
uao_end:
        ret

; ---------------------------------------------------------------------------
; Look XIY up in ui_remap (binary search).
;   Out: carry set if found: XIY = English string, A = flags,
;        XHL = original string. Carry clear otherwise (XIY unchanged).
;   Clobbers XWA, XHL. Preserves XBC, XDE, XIX, XIZ.
; ---------------------------------------------------------------------------
ui_lookup:
        and.l   XIY, 0xFFFFFF           ; some tables keep flags in the pointer's top byte
        ld.l    XWA, XIY
        cp.l    XWA, 0x200000
        jr      C, ul_none              ; RAM buffers are never remapped
        push.l  XBC
        push.l  XDE
        ld.l    XDE, 0                  ; lo
        ld.l    XBC, 0
        ld.w    BC, (ui_remap)          ; hi = entry count
ul_loop:
        cp.w    DE, BC
        jr      NC, ul_miss             ; lo >= hi
        ld.w    HL, DE
        add.w   HL, BC
        srl.w   1, HL                   ; mid
        push.w  HL
        extz.l  XHL
        sll.l   3, XHL
        add.l   XHL, ui_remap + 4
        ld.l    XWA, (XHL)
        and.l   XWA, 0xFFFFFF
        cp.l    XWA, XIY
        pop.w   WA                      ; WA = mid (flags kept)
        jr      Z, ul_hit
        jr      UGT, ul_upper
        inc.w   1, WA                   ; entry < key: lo = mid + 1
        ld.w    DE, WA
        jr      ul_loop
ul_upper:
        ld.w    BC, WA                  ; entry > key: hi = mid
        jr      ul_loop
ul_hit:
        ld.l    XWA, (XHL+4)            ; English string
        push.l  XIY
        ld.l    XIY, XWA
        and.l   XIY, 0xFFFFFF
        ld.b    A, (XHL+3)              ; flags
        pop.l   XHL                     ; original string
        pop.l   XDE
        pop.l   XBC
        scf
        ret
ul_miss:
        pop.l   XDE
        pop.l   XBC
ul_none:
        rcf
        ret
