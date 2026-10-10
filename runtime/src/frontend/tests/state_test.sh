#!/bin/bash
# Save-state tests for zenobia.exe --selftest: resuming matches an
# uninterrupted run, states move between the player and ngp_harness, and bad
# files loaded mid-run are rejected with the game state left byte-identical.
#   bash state_test.sh ZENOBIA_EXE HARNESS_EXE ENGLISH_ROM JAPANESE_ROM WORKDIR
# WORKDIR must be a new or empty folder.
Z="$1"; H="$2"; ROM="$3"; JP="$4"; W="$5"
if [ -z "$W" ] || { [ -d "$W" ] && [ -n "$(ls -A "$W")" ]; }; then
    echo "usage: state_test.sh ZENOBIA_EXE HARNESS_EXE ENGLISH_ROM JAPANESE_ROM NEW_EMPTY_WORKDIR"; exit 2
fi
mkdir -p "$W"
pass=0; fail=0
check() {  # check NAME CONDITION...
    local name="$1"; shift
    if "$@"; then echo "ok   $name"; pass=$((pass+1)); else echo "FAIL $name"; fail=$((fail+1)); fi
}
same() { cmp -s "$1" "$2"; }

q() { "$@" > "$W/last.log" 2>&1; echo $?; }

# 1. baseline: 1200 frames, state after the last frame
r=$(q "$Z" --selftest "$ROM" --frames 1200 --png "$W/base.png" --save-state 1199 "$W/base.state")
check "baseline run (exit $r)" test "$r" = 0
# 2. state after frame 599
r=$(q "$Z" --selftest "$ROM" --frames 600 --save-state 599 "$W/mid.state")
check "mid state saved (exit $r)" test "$r" = 0
echo "     mid.state size $(stat -c %s "$W/mid.state")"
# 3. resume from it: 600 more frames give the baseline picture and state
r=$(q "$Z" --selftest "$ROM" --load-state "$W/mid.state" --frames 600 --png "$W/resumed.png" --save-state 599 "$W/resumed.state")
check "resume run (exit $r)" test "$r" = 0
check "resumed picture == baseline" same "$W/resumed.png" "$W/base.png"
check "resumed state == baseline state" same "$W/resumed.state" "$W/base.state"
# 4. the harness loads player states (trailer ignored)
mkdir -p "$W/h"
"$H" "$ROM" --load-state "$W/mid.state" --frames 600 --shot 599 --out "$W/h" > /dev/null 2>&1
check "harness loads player state" same "$W/h/frame_00599.png" "$W/base.png"
# 5. the player loads a harness state
"$H" "$ROM" --frames 600 --save-state 599 "$W/harness_mid.state" --out "$W/h" > /dev/null 2>&1
r=$(q "$Z" --selftest "$ROM" --load-state "$W/harness_mid.state" --frames 600 --png "$W/from_harness.png")
check "player loads harness state (exit $r)" test "$r" = 0
check "harness state resumes to baseline" same "$W/from_harness.png" "$W/base.png"
# 6. valid load mid-run (its own state at the same point) changes nothing
r=$(q "$Z" --selftest "$ROM" --frames 1200 --load-state-at 599 "$W/mid.state" --png "$W/reload.png" --save-state 1199 "$W/reload.state")
check "reload at 599 (exit $r)" test "$r" = 0
check "reload picture == baseline" same "$W/reload.png" "$W/base.png"

# 7. bad files loaded after frame 599: rejected, game continues unchanged
size=$(stat -c %s "$W/mid.state"); core=$((size - 44))
head -c 40000 "$W/mid.state" > "$W/truncated.state"
# long enough to pass validation: the core fails part-way, after overwriting memory
head -c 66000 "$W/mid.state" > "$W/truncated_late.state"
cp "$W/mid.state" "$W/flipped.state"
printf '\x55' | dd of="$W/flipped.state" bs=1 seek=30000 conv=notrunc 2> /dev/null
head -c 100 /dev/urandom > "$W/garbage.state"
printf 'NGPSTAT1' > "$W/header_only.state"
# core part only (no trailer), with flash block 33 marked as saved: the core
# then reads past the end into the ROM image before failing
head -c "$core" "$W/mid.state" > "$W/touched.state"
printf '\x01' | dd of="$W/touched.state" bs=1 seek=$((core - 1 - 70 + 33)) conv=notrunc 2> /dev/null
for bad in truncated truncated_late flipped garbage header_only touched missing; do
    r=$(q "$Z" --selftest "$ROM" --frames 1200 --load-state-at 599 "$W/$bad.state" --png "$W/after_$bad.png" --save-state 1199 "$W/after_$bad.state")
    msg=$(grep "load state" "$W/last.log" | sed 's/^selftest: //')
    check "bad state '$bad' rejected (exit $r: $msg)" test "$r" = 4
    check "  picture unchanged" same "$W/after_$bad.png" "$W/base.png"
    check "  game state unchanged" same "$W/after_$bad.state" "$W/base.state"
done

# 8. a state saved with another ROM image is detected
r=$(q "$Z" --selftest "$JP" --untranslated --patch "$W/no_such_patch.bps" --frames 300 --save-state 299 "$W/japanese.state")
check "untranslated run saves a state (exit $r)" test "$r" = 0
r=$(q "$Z" --selftest "$ROM" --load-state "$W/japanese.state" --frames 10)
check "other-ROM state detected" grep -q "different ROM image" "$W/last.log"

echo "passed $pass, failed $fail"
test "$fail" = 0
