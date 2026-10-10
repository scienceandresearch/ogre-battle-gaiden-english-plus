; ===========================================================================
; Message opcode (0x32) per-frame step with incremental drawing.
;
; Replaces the code at 0x2007F8. The original redrew the whole visible text
; every frame and then moved the typewriter terminator; we move the
; terminator first and draw only the newly revealed characters.
;
; Entry (from 0x2007ED): (XSP) = task pointer pushed by the handler,
;   XIY = task, XDE = address of the opcode, XIX = message buffer header
;   (task+32), header[0] != 0. Header layout: [pos][saved word], text at +3.
; ===========================================================================

tw_frame:
        ld.l    XBC, XDE                ; opcode address: run again next frame
        ld.l    XHL, 0
        ld.b    L, (XIX)                ; p = current terminator offset
        ld.w    WA, (XIX+1)             ; the two bytes it replaced
        inc.l   3, XIX                  ; XIX = text start
        or.w    WA, WA
        jr      NZ, tw_more
        ld.b    (XIX-3), 0              ; whole message shown: release buffer
        pop.l   XIY
        ld.l    XDE, 0x202FB6           ; continue with the end-of-message script
        jp      0x20023D
tw_more:
        ld.b    D, L                    ; D = p (first character to draw)
        add.l   XHL, XIX
        ld.w    (XHL), WA               ; restore the saved bytes
        inc.w   1, HL                   ; reveal one more character
        ld.b    A, (0x6F82)             ; A/B held: reveal to the end of the line
        and.b   A, 0x30
        jr      Z, tw_term
        dec.w   1, HL
tw_skip:
        cp.b    (XHL+), 0
        jr      NZ, tw_skip
        dec.w   1, HL
tw_term:
        ld.w    WA, (XHL)
        ld.w    (XHL), 0                ; new terminator
        sub.l   XHL, XIX                ; L = new position p'
        ld.w    (XIX-2), WA
        ld.b    (XIX-3), L
        ld.b    H, D                    ; draw [p, p')
        pop.l   XDE                     ; task pointer
        push.l  XDE
        ld.l    XIY, XIX                ; text start
        ld.l    XIX, 0
        ld.w    IX, (XDE+40)            ; map address of the text area
        ld.w    IZ, (XDE+42)            ; first tile
        call    vwf_range
        pop.l   XIY                     ; task pointer (as the original)
        ld.l    XDE, XBC                ; yield: run this opcode again after E frames
        sll.l   8, XDE
        ld.b    E, 2                    ; E = 3 * (2 - text speed) + 1, as the original
        sub.b   E, (0x469D)
        ld.b    A, E
        add.b   A, A
        add.b   E, A
        inc.b   1, E
        ret

; ---------------------------------------------------------------------------
; End of message initialisation (replaces `inc.w 1,HL ; jrl 0x20084E` at
; 0x2008E3). The original reveals offset 0 on the next frame by redrawing;
; with incremental drawing we draw the first character right away.
;   XIY = task, XIX = XHL = text start, XDE = yield value (kept).
; ---------------------------------------------------------------------------
tw_init_tail:
        inc.w   1, HL                   ; original: terminator after character 0
        push.l  XHL
        push.l  XIX
        push.l  XIY
        push.l  XIZ
        ld.l    XWA, XIY                ; task pointer
        ld.l    XIY, XIX                ; text start
        ld.l    XIX, 0
        ld.w    IX, (XWA+40)
        ld.w    IZ, (XWA+42)
        ld.w    HL, 0x0001              ; draw [0, 1)
        call    vwf_range
        pop.l   XIZ
        pop.l   XIY
        pop.l   XIX
        pop.l   XHL
        jp      0x20084E
