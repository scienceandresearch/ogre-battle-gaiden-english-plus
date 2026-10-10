; ===========================================================================
; Composed messages.
;
; Many messages are built in RAM (usually 0x6000) from fixed fragments plus a
; name or a number, in Japanese word order. Most fragments are copied with
; fixed lengths, so their copies are repointed to English strings
; (ui.txt symbols msg_*); where English needs text before the name or more
; bytes than the original instruction can hold, small helpers take over:
;
;   msg_copy_ff     copy a "head{FF}tail" string up to its {FF}: XIY = tail
;   msg_copy_term   copy a string including its 00 00 terminator
;   msg_quote_open  msg_copy_ff, then XIZ = msg_close_quote (for code that
;                   copies its closing fragment from XIZ)
;   msg_name_*      leader name messages: VWF marker, optional text, name
;   msg_class_pre   class change: VWF marker and text before the class name
;   stat_msg        stat change after a tarot card: whole message
;
; English messages start with UI_VWF_MARK so the window renderer draws them
; with the variable-width font.
; ===========================================================================

MSG_SPLIT = 0xFF

; ---------------------------------------------------------------------------
; Copy (XIY) to (XIX) up to MSG_SPLIT (not copied). Out: XIY = after it.
; ---------------------------------------------------------------------------
msg_copy_ff:
        ld.b    A, (XIY+)
        cp.b    A, MSG_SPLIT
        ret     Z
        ld.b    (XIX+), A
        jr      msg_copy_ff

; ---------------------------------------------------------------------------
; Copy (XIY) to (XIX) up to and including the 00 00 terminator.
; ---------------------------------------------------------------------------
msg_copy_term:
        ld.b    A, (XIY+)
        ld.b    (XIX+), A
        or.b    A, A
        jr      NZ, msg_copy_term
        cp.b    (XIY), 0
        jr      NZ, msg_copy_term
        ld.b    A, (XIY+)
        ld.b    (XIX+), A
        ret

; ---------------------------------------------------------------------------
; Opening part of a quoted name ("...{00}“{FF}"); the caller then copies the
; name and the closing fragment from XIZ (replaces "ldi.b ; ld.l XIZ, XIY").
; ---------------------------------------------------------------------------
msg_quote_open:
        call    msg_copy_ff
        ld.l    XIZ, msg_close_quote
        ret

; ---------------------------------------------------------------------------
; Leader name messages (replace "calr 0x20CC9A ; ldir.b").
;   In: A = character, XIX = buffer. Writes [VWF mark][text][name].
; ---------------------------------------------------------------------------
msg_name_moved:
        push.l  XHL
        ld.l    XHL, loc_none
        jr      msg_name
msg_name_recall:
        push.l  XHL
        ld.l    XHL, msg_recall_pre
        jr      msg_name
msg_name_enc:                           ; encounters: the buffer is set here
        ld.l    XIX, 0x6000
        push.l  XHL
        ld.l    XHL, loc_none
msg_name:
        call    0x20CC9A                ; XIY = name, BC = length (keeps XHL)
        push.l  XIY
        ld.b    A, UI_VWF_MARK
        ld.b    (XIX+), A
        ld.l    XIY, XHL
        call    loc_copy
        pop.l   XIY
        ldir.b  (XIX+), (XIY+)
        pop.l   XHL
        ret

; ---------------------------------------------------------------------------
; Class change confirmation: text before the class name (replaces the
; "call 0x201B77" that looks the class name up).
; ---------------------------------------------------------------------------
msg_class_pre:
        push.l  XIY
        push.l  XWA
        ld.l    XIY, msg_classchange_pre
        call    msg_copy_ff
        pop.l   XWA
        pop.l   XIY
        jp      0x201B77

; ---------------------------------------------------------------------------
; Stat change message (tarot card effects), at 0x6000:
;   "<subject><stat>" NEWLINE "went up/down by N point(s)."
;   In: XIY = task: +32 stat code (6 = HP and max HP, 7 = max HP, 8.. =
;   STR AGI INT CHA ALI LUK), +33 signed change (one digit).
; stat_msg_chaos: the same for the Chaos Frame.
; ---------------------------------------------------------------------------
stat_msg:
        push.l  XIX
        call    sm_start
        push.l  XIY
        ld.l    XIY, msg_stat_subject
        call    loc_copy
        pop.l   XIY
        ld.l    XWA, 0
        ld.b    A, (XIY+32)
        sub.b   A, 6
        sll.w   2, WA
        add.l   XWA, stat_names
        push.l  XIY
        ld.l    XIY, (XWA)
        call    loc_copy
        pop.l   XIY
        jr      sm_tail
stat_msg_chaos:
        push.l  XIX
        call    sm_start
        push.l  XIY
        ld.l    XIY, msg_stat_chaos
        call    loc_copy
        pop.l   XIY
sm_tail:
        ld.b    A, (XIY+33)
        push.l  XIY
        ld.l    XIY, msg_stat_up
        or.b    A, A
        jr      PL, sm_up
        neg.b   A
        ld.l    XIY, msg_stat_down
sm_up:
        push.w  WA
        call    msg_copy_ff
        pop.w   WA
        add.b   A, 2                    ; digit code
        ld.b    (XIX+), A
        ld.l    XIY, msg_stat_points
        cp.b    A, 3                    ; "1"
        jr      NZ, sm_plural
        ld.l    XIY, msg_stat_point
sm_plural:
        call    msg_copy_term
        pop.l   XIY
        pop.l   XIX
        ret
sm_start:
        ld.l    XIX, 0x6000
        ld.b    A, UI_VWF_MARK
        ld.b    (XIX+), A
        ret

stat_names:
        .dl     msg_stat_6, msg_stat_7, msg_stat_8, msg_stat_9
        .dl     msg_stat_10, msg_stat_11, msg_stat_12, msg_stat_13
