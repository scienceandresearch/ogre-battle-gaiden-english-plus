#!/bin/bash
# ROM identification policy, --write-patched and non-ASCII paths, through the
# headless modes (where questions get their default answers).
#   bash rom_test.sh ZENOBIA_EXE JAPANESE_ROM PATCH ENGLISH_ROM WORKDIR
# ENGLISH_ROM must be the PATCH's target (e.g. build/ogre_en.ngc + build/ogre_en.bps).
Z="$1"; JP="$2"; PATCH="$3"; EN="$4"; W="$5"
mkdir -p "$W"
pass=0; fail=0
check() { local name="$1"; shift; if "$@"; then echo "ok   $name"; pass=$((pass+1)); else echo "FAIL $name"; fail=$((fail+1)); fi; }
run() { "$@" > "$W/last.log" 2>&1; echo $?; }
has() { grep -q "$1" "$W/last.log"; }

# Japanese ROM + patch: patched in memory
r=$(run "$Z" --selftest "$JP" --patch "$PATCH" --frames 60)
check "Japanese ROM + patch runs patched (exit $r)" test "$r" = 0
check "  patch applied" has "patch applied"
# Japanese ROM without the patch
r=$(run "$Z" --selftest "$JP" --patch "$W/missing.bps" --frames 60)
check "missing patch refused (exit $r)" test "$r" = 3
check "  message names the patch" has "English patch was not found"
r=$(run "$Z" --selftest "$JP" --patch "$W/missing.bps" --untranslated --frames 60)
check "--untranslated runs it (exit $r)" test "$r" = 0
check "  as is, untranslated" has "untranslated"
# damaged patch
cp "$PATCH" "$W/damaged.bps"
printf '\x00' | dd of="$W/damaged.bps" bs=1 seek=5000 conv=notrunc 2> /dev/null
r=$(run "$Z" --selftest "$JP" --patch "$W/damaged.bps" --frames 60)
check "damaged patch refused (exit $r)" test "$r" = 3
check "  says it is damaged" has "damaged"
# English ROM (CRC32 = the patch's target): runs as is
r=$(run "$Z" --selftest "$EN" --patch "$PATCH" --frames 60)
check "English ROM runs as is (exit $r)" test "$r" = 0
check "  recognised as English" has "(English ROM)"
# unknown ROM: one byte changed
cp "$JP" "$W/other.ngc"
printf '\x42' | dd of="$W/other.ngc" bs=1 seek=1048576 conv=notrunc 2> /dev/null
r=$(run "$Z" --selftest "$W/other.ngc" --patch "$PATCH" --frames 60)
check "unrecognised ROM runs as is with a warning (exit $r)" test "$r" = 0
check "  warning printed" has "not a ROM the patch knows"
# unreadable / tiny files
r=$(run "$Z" --selftest "$W/no_such.ngc" --frames 10)
check "missing ROM file (exit $r)" test "$r" = 2
printf 'tiny' > "$W/tiny.ngc"
r=$(run "$Z" --selftest "$W/tiny.ngc" --frames 10)
check "too small file refused (exit $r)" test "$r" = 3

# --write-patched
r=$(run "$Z" "$JP" --patch "$PATCH" --write-patched "$W/written.ngc")
check "--write-patched (exit $r)" test "$r" = 0
check "  output equals the English ROM" cmp -s "$W/written.ngc" "$EN"
r=$(run "$Z" "$W/other.ngc" --patch "$PATCH" --write-patched "$W/written2.ngc")
check "--write-patched refuses an untranslated result (exit $r)" test "$r" = 3
check "  nothing written" test ! -e "$W/written2.ngc"
r=$(run "$Z" --selftest "$JP" --patch "$PATCH" --frames 10)
check "no patched ROM written without the option" test ! -e "${JP%.*}_en.ngc"

# non-ASCII paths (Greek and Cyrillic: outside the Windows-1252 code page)
U="$W/тест Ωμέγα"
mkdir -p "$U"
cp "$JP" "$U/ром Ω.ngc"
cp "$PATCH" "$U/патч Ω.bps"
r=$(run "$Z" --selftest "$U/ром Ω.ngc" --patch "$U/патч Ω.bps" --frames 120 --png "$U/кадр Ω.png" --save-state 100 "$U/состояние Ω.state")
check "non-ASCII paths: run (exit $r)" test "$r" = 0
check "  PNG written" test -s "$U/кадр Ω.png"
check "  state written" test -s "$U/состояние Ω.state"
r=$(run "$Z" --selftest "$U/ром Ω.ngc" --patch "$U/патч Ω.bps" --frames 20 --load-state "$U/состояние Ω.state" --save "$U/сейв Ω.sav")
check "  state loaded back (exit $r)" test "$r" = 0
check "  process code page is UTF-8" has "65001"

# usage
r=$(run "$Z" --help)
check "--help prints usage (exit $r)" test "$r" = 0
check "  usage text" has "Usage: zenobia"
r=$(run "$Z" --bogus-option)
check "unknown option (exit $r)" test "$r" = 1

echo "passed $pass, failed $fail"
test "$fail" = 0
