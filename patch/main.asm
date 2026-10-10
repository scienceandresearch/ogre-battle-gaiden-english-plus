; ===========================================================================
; Ogre Battle Gaiden: Prince of Zenobia - English translation patch
; Main assembly file. Assembled by tools/patch/build.py.
;
; The original ROM is 0xFF-filled from 0x36746D. The patch regions are listed
; in tools/patch/layout.py: UI text 0x368000, code 0x370000 (FREE_CODE), fonts
; and the remap table 0x378000 (FREE_DATA), dialogue 0x380000, graphics
; 0x3A0000, tables 0x3F0000. 0x3B0000-0x3EFFFF holds the game's save blocks
; and must never be written; the build refuses any byte there.
; ===========================================================================

FREE_CODE = 0x370000
FREE_DATA = 0x378000

        .include "../build/ui/symbols.asm"  ; named strings from translation/en/ui.txt
        .include "../build/loc/symbols.asm" ; location tables from translation/en/locations.txt

; --------------------------------------------------------------------------
; Hooks into the original program
; --------------------------------------------------------------------------
; Non-dialogue window text keeps the original fixed-cell renderer (menus,
; lists and the name-entry grid depend on one tile per character) but draws
; from the English 8x8 font. Its glyph pointer is font + 16*(code-1).
        .org 0x200BEC
        ld.l    XIZ, font8_tiles - 16

; The tile-mapped UI printer preloads the font into VRAM from codes 2..
        .org 0x200B50
        ld.l    XIY, font8_tiles
        .org 0x200B67
        ld.l    XIY, font8_tiles

        .org 0x2007F8                   ; message opcode: per-frame typewriter step
        jp      tw_frame

        .org 0x2008E3                   ; message init tail: draw the first character
        jp      tw_init_tail
        nop

; Name confirmation "Name: <name> / Is this correct?" (composed at 0x294FE4
; from a 5-byte prefix, the name and a 22-byte suffix).
        .org 0x294FE9
        ld.l    XIY, name_ok_prefix
        ld.w    BC, name_ok_prefix_LEN
        .org 0x294FFD
        ld.l    XIY, name_ok_suffix
        ld.b    C, name_ok_suffix_LEN

; Menu/window strings are looked up in the UI remap table (src/uitext.asm).
        .org 0x200BAC                   ; window renderer entry
        jp      ui_window
        nop
        .org 0x200B72                   ; tile-mapped printer entry
        jp      ui_print

; Location names (src/locname.asm): the town window and the liberated /
; discovered / lost messages take the English names from loc_table.
        .org 0x207AB5                   ; town window: copy of the 8-cell name
        call    loc_win_name
        .db     0, 0, 0, 0, 0, 0, 0, 0  ; nop
        .org 0x207B3A                   ; town window: draw the text
        call    loc_win_draw
        .org 0x208DE6                   ; "<town type><name>" at the start of a message
        jp      loc_compose
        .org 0x208449                   ; "... was liberated." (copied without terminator)
        ld.l    XIY, loc_msg_liberated
        ld.w    BC, loc_msg_liberated_LEN
        .org 0x208D30                   ; "... was discovered."
        ld.l    XIY, loc_msg_found
        ld.w    BC, loc_msg_found_LEN
        .org 0x20A3A7                   ; "... was taken by hostile forces."
        ld.l    XIY, loc_msg_lost
        ld.w    BC, loc_msg_lost_LEN

; Composed messages (src/msgcompose.asm). Lengths above 7 keep the 3-byte
; "ld.w BC, imm16" form of the originals; a 2-byte form would leave a 00 (nop).
; Leader name first: "<leader>'s unit ..."
        .org 0x208316                   ; unit finished moving
        call    msg_name_moved          ; was: calr 0x20CC9A ; ldir.b
        .db     0
        .org 0x20831B
        ld.l    XIY, msg_moved
        ld.w    BC, msg_moved_LEN
        .org 0x20846E                   ; "Recall <leader>'s unit to headquarters?"
        call    msg_name_recall
        .db     0
        .org 0x208473
        ld.l    XIY, msg_recall
        ld.w    BC, msg_recall_LEN
        .org 0x2090B8                   ; encountered a neutral character
        call    msg_name_enc            ; was: calr 0x20CC9A ; ld.l XIX, 0x6000 ; ldir.b
        .db     0, 0, 0, 0, 0, 0
        .org 0x2090C2
        ld.l    XIY, msg_met_neutral
        ld.w    BC, msg_met_neutral_LEN
        .org 0x2091C1                   ; encountered an enemy unit
        call    msg_name_enc
        .db     0, 0, 0, 0, 0, 0
        .org 0x2091CB
        ld.l    XIY, msg_met_enemy
        ld.w    BC, msg_met_enemy_LEN
; Item names in quotes: head up to {FF}, the game copies the name, then "”."
        .org 0x2086F8                   ; found an item
        ld.l    XIY, msg_found_item
        call    msg_copy_ff             ; was: ld.w BC, 5 ; ldir.b
        .org 0x208705
        ld.l    XIY, msg_close_quote
        call    msg_copy_term           ; was: ld.w BC, 0xE ; ldir.b
        .db     0
        .org 0x208E96                   ; buried treasure
        ld.l    XIY, msg_treasure
        call    msg_copy_ff
        .db     0
        .org 0x208EA4
        ld.l    XIY, msg_close_quote
        call    msg_copy_term
        .org 0x20938D                   ; spoils of war
        ld.l    XIY, msg_spoils
        call    msg_copy_ff
        .db     0
        .org 0x2093B8
        ld.l    XIY, msg_close_quote
        call    msg_copy_term
        .db     0
        .org 0x215D7F                   ; obtained an item
        ld.l    XIY, msg_obtained
        .org 0x215CD0                   ; gave up an item
        ld.l    XIY, msg_gaveup
        .org 0x215D8C
        call    msg_quote_open          ; was: ldi.b ; ld.l XIZ, XIY
        .org 0x215DB3
        ld.w    BC, msg_close_quote_LEN
        .org 0x208C97                   ; drew a tarot card
        ld.l    XIY, msg_drew_card
        call    msg_quote_open
        .org 0x208CB1
        ld.b    C, msg_close_quote_LEN
; Costs: head, number, tail
        .org 0x205A5A                   ; revive
        ld.l    XIY, msg_revive_cost
        call    msg_copy_ff             ; was: ld.w BC, 6 ; ldir.b
        .org 0x205A82
        call    msg_copy_term           ; was: ld.w BC, 0x17 ; ldir.b
        .db     0
        .org 0x206EA0                   ; deploy: leader cannot fight
        ld.l    XIY, msg_deploy_leader_down
        ld.w    BC, msg_deploy_leader_down_LEN
        .org 0x206ED1                   ; deploy: not enough funds
        ld.l    XIY, msg_deploy_no_funds
        ld.b    C, msg_deploy_no_funds_LEN
        .org 0x206EDF                   ; deploy: cost (0x206EF5 is also a jump target)
        ld.l    XIY, msg_deploy_cost
        call    msg_copy_ff             ; was: ld.w BC, 7 ; ldir.b
        .org 0x206EF2
        ld.w    BC, msg_deploy_cost_TAIL
        .org 0x215BB1                   ; shop: "<price> goth. Is that OK?" (fixed font)
        ld.l    XIY, msg_price
        ld.w    BC, msg_price_LEN
        .org 0x20761D
        ld.l    XIY, msg_price
        ld.w    BC, msg_price_LEN
; Class change: text before the class name
        .org 0x206253
        call    msg_class_pre           ; was: call 0x201B77
        .org 0x206259
        ld.l    XIY, msg_classchange
        ld.b    C, msg_classchange_LEN
        .org 0x213134
        call    msg_class_pre
        .org 0x21313A
        ld.l    XIY, msg_classchange
        ld.b    C, msg_classchange_LEN
; Stat changes after a tarot card (whole message rebuilt)
        .org 0x208620
        call    stat_msg
        jr      0x208666
        .org 0x2087C9                   ; Chaos Frame
        call    stat_msg_chaos
        jp      0x208666
; Move types (src/movetype.asm): English names up to 7 letters
        .org 0x21338D                   ; status screen: name + "type" (19 bytes of 32-bit moves)
        call    mt_copy8_d4
        .db     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
        .org 0x20D5A5                   ; unit status: name + "type"
        call    mt_copy8_b4
        .db     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
        .org 0x20631A                   ; unit window: name + "type"
        call    mt_copy8_a
        .db     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
        .org 0x206DCF                   ; list of units' move types: name only
        call    mt_copy_d
        .db     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0
; Link battle settings: English values are up to 7 cells, so they start one
; cell further left (settings screen) or 2-6 cells further left (overview,
; right-aligned to column 17 like the original).
        .org 0x2E1770
        ld.w    IX, 0x9058              ; was 0x905A (column 13 -> 12)
        .org 0x2E1795
        ld.w    IX, 0x9058
        .org 0x2E17DB
        ld.w    IX, 0x9058
        .org 0x2E1806
        ld.w    IX, 0x9058
        .org 0x2E182B
        ld.w    IX, 0x9058
        .org 0x2E1859
        ld.w    IX, 0x9058
        .org 0x2E1872
        ld.w    IX, 0x9058
        .org 0x2E189A
        ld.w    IX, 0x9058
        .org 0x2E18B6
        ld.w    IX, 0x9058
        .org 0x2E21FA
        ld.w    IX, 0x9198              ; overview spoils (was 0x919C)
        .org 0x2E2212
        ld.w    IX, 0x91D6              ; overview victory condition (was 0x91DC)
        .org 0x2E222A
        ld.w    IX, 0x9218              ; overview terrain picker (was 0x921A)
        .org 0x2E2242
        ld.w    IX, 0x9258              ; overview time picker (was 0x925A)
        .org 0x2E2272
        ld.w    IX, 0x92D8              ; overview gauge speed (was 0x92DE)
; Stock label: 5-byte head ("Stock"), two digits, 13-byte tail (the original
; lengths; the copy keeps the original ld.w BC, 5 at 0x213649)
        .org 0x213644
        ld.l    XHL, msg_stock_label

; Text fixes found by play-testing (round 2 on): their hooks and their code
; (placed at TEXTFIX_CODE) live together in one file.
TEXTFIX_CODE = FREE_CODE + 0x4000
        .include "src/textfix.asm"

; --------------------------------------------------------------------------
; New code
; --------------------------------------------------------------------------
        .org FREE_CODE
        .include "src/vwf.asm"
        .include "src/textop.asm"
        .include "src/uitext.asm"
        .include "src/locname.asm"
        .include "src/msgcompose.asm"
        .include "src/movetype.asm"

; --------------------------------------------------------------------------
; Font data (generated by tools/text/fontc.py)
; --------------------------------------------------------------------------
        .org FREE_DATA
vwf_spread:
        .incbin "../build/font/spread.bin"
vwf_glyphs:
        .incbin "../build/font/vwf_glyphs.bin"
vwf_widths:
        .incbin "../build/font/vwf_widths.bin"
font8_tiles:
        .incbin "../build/font/font8.bin"

; UI remap table (generated from translation/en/ui.txt by tools/text/uitext.py)
        .org FREE_DATA + 0x4000
ui_remap:
        .incbin "../build/ui/remap.bin"

; Graphics (tools/gfx): sub-regions, and each target's hooks, code and data
        .include "../build/gfx/gfx.asm"
