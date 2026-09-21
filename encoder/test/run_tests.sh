#!/usr/bin/env bash
# Copyright 2026 Eckstein GmbH Apache-2.0; see LICENSE.txt at the repository root.
# MODIFICATION NOTICE: new file, not present in upstream OpenArm.
#
# Deliverable 5: every verification requirement of protocol-spec.md section 11.2
# that can run without hardware. Run from this directory:  ./run_tests.sh
#
# Needs: host gcc, the avr-gcc PlatformIO installs, simavr (apt install simavr),
# and encoder/.venv (encoder/requirements-dev.txt) for the station simulations.
set -uo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
SRC=$HERE/../src
EV=$HERE/../docs/evidence/v3-reference
PY=$HERE/../.venv/bin/python
T=${AVR_TOOLCHAIN:-$HOME/.platformio/packages/toolchain-atmelavr/bin}
O=$(mktemp -d); trap 'rm -rf "$O"' EXIT
R=$HERE/results; mkdir -p "$R"

fails=0
pass() { printf '  PASS  %s\n' "$1"; }
fail() { printf '  FAIL  %s\n' "$1"; fails=$((fails + 1)); }
skip() { printf '  SKIP  %s\n' "$1"; }
sect() { printf '\n== %s ==\n' "$1"; }

have_avr=1; [ -x "$T/avr-gcc" ] || have_avr=0
have_sim=1; command -v simavr >/dev/null || have_sim=0
have_py=1;  [ -x "$PY" ] || have_py=0

# --- 1. host unit tests (section 11.2 item 1) ------------------------------
sect "1. host unit tests of ker_comp.c and ker_cal.c"
gcc -O2 -Wall -Wextra -Werror -o "$O/test_comp" "$HERE/test_comp.c" "$SRC/ker_comp.c" -lm \
  && "$O/test_comp" | tee "$R/test_comp.txt" | sed 's/^/  /' \
  && pass "test_comp" || fail "test_comp"
gcc -O2 -Wall -Wextra -Werror -o "$O/test_cal" "$HERE/test_cal.c" "$SRC/ker_cal.c" "$SRC/ker_comp.c" \
  && "$O/test_cal" | tee "$R/test_cal.txt" | sed 's/^/  /' \
  && pass "test_cal" || fail "test_cal"

# Spec section 7.4 item 4: the sine table's 16-bit bound is enforced at compile
# time, so a coarser table cannot silently reintroduce the overflow.
gcc -c -O2 -DKER_SIN_SEG_BITS=6 -o "$O/coarse.o" "$SRC/ker_comp.c" > "$O/coarse.log" 2>&1
if grep -q 'static assertion failed' "$O/coarse.log"; then
  pass "a 64-segment sine table does not compile (section 7.4 item 4)"
else
  fail "a 64-segment sine table compiled: the 16-bit interpolation bound is not enforced"
fi

# --- 2. the ported arithmetic is the artefact the spec measured ------------
sect "2. src/ker_comp.c against the reference the spec's numbers came from"
if diff <(sed -n '/^#ifndef KER_SIN_SEG_BITS/,$p' "$SRC/ker_comp.c" | sed 's/ker_sinq\([67]\)/sinq\1/') \
        <(sed -n '/^#ifndef KER_SIN_SEG_BITS/,$p' "$EV/ref_comp.c") >/dev/null; then
  pass "ker_comp.c body identical to ref_comp.c (only the include names differ)"
else
  fail "ker_comp.c has drifted from ref_comp.c; section 7.5's measurements no longer apply"
fi
for f in diff_main.c seam_check.c; do
  if diff <(tail -n +5 "$HERE/$f" | sed 's|\.\./src/ker_comp\.h|ref_comp.h|') "$EV/$f" >/dev/null; then
    pass "$f identical to the evidence copy"
  else
    fail "$f has drifted from the evidence copy"
  fi
done

# --- 3. AVR differential test and its negative controls (items 2 and 3) ----
sect "3. AVR differential test over all 32768 codes, 21 coefficient sets"
if [ $have_avr = 1 ] && [ $have_sim = 1 ]; then
  gcc -O2 -o "$O/dh" "$HERE/diff_main.c" "$SRC/ker_comp.c" && "$O/dh" > "$R/diff_host.txt"
  "$T/avr-gcc" -mmcu=atmega328p -Os -o "$O/da.elf" "$HERE/diff_main.c" "$SRC/ker_comp.c"
  simavr -m atmega328p -f 16000000 "$O/da.elf" 2>&1 | grep -oE "[0-9a-f]{8}" > "$R/diff_avr.txt" || true
  if diff "$R/diff_host.txt" "$R/diff_avr.txt" >/dev/null; then
    pass "AVR == host, $(wc -l < "$R/diff_host.txt")/21 sets"
  else
    fail "AVR and host differ on $(diff "$R/diff_host.txt" "$R/diff_avr.txt" | grep -c '^<') sets"
  fi

  gcc -O2 -o "$O/seam" "$HERE/seam_check.c" "$SRC/ker_comp.c" && "$O/seam" > "$R/seam_coverage.txt"
  b=$(grep -c 'below 0: *[1-9]' "$R/seam_coverage.txt"); a=$(grep -c "above 2\^21-1: *[1-9]" "$R/seam_coverage.txt")
  if [ "$b" -ge 1 ] && [ "$a" -ge 1 ]; then
    pass "the sets wrap the seam in both directions ($b below, $a above)"
  else
    fail "the differential sets do not cover both seam directions"
  fi

  # Mutants are generated from the shipping source, so they cannot go stale.
  # A: the missing int32_t cast -- correct where int is 32 bits, wrong on AVR.
  # B: the uncalibrated path computing (uint32_t)(raw15 << 6).
  sed 's|acc += ((int32_t)c->amp\[k\] \* s) >> 8;|acc += (c->amp[k] * s) >> 8;|' \
      "$SRC/ker_comp.c" > "$O/mut_a.c"
  sed 's|return ((uint32_t)raw15 << 6) \| (raw15 >> 9);|return (uint32_t)(raw15 << 6) \| (raw15 >> 9);|' \
      "$SRC/ker_comp.c" > "$O/mut_b.c"
  for m in a b; do
    if diff -q "$O/mut_$m.c" "$SRC/ker_comp.c" >/dev/null; then
      fail "mutant $m did not apply -- the negative control is not testing anything"; continue
    fi
    gcc -O2 -I"$SRC" -o "$O/mh" "$HERE/diff_main.c" "$O/mut_$m.c" && "$O/mh" > "$R/diff_host_mutant_$m.txt"
    "$T/avr-gcc" -mmcu=atmega328p -Os -I"$SRC" -o "$O/ma.elf" "$HERE/diff_main.c" "$O/mut_$m.c"
    simavr -m atmega328p -f 16000000 "$O/ma.elf" 2>&1 | grep -oE "[0-9a-f]{8}" > "$R/diff_avr_mutant_$m.txt" || true
    hostsame=$(diff -q "$R/diff_host_mutant_$m.txt" "$R/diff_host.txt" >/dev/null && echo yes || echo no)
    n=$(diff "$R/diff_avr_mutant_$m.txt" "$R/diff_host.txt" | grep -c '^<')
    if [ "$hostsame" = yes ] && [ "$n" -ge 1 ]; then
      pass "mutant $m invisible on host, caught on AVR ($n of 21 sets)"
    else
      fail "mutant $m: invisible-on-host=$hostsame, AVR sets differing=$n"
    fi
  done
else
  skip "avr-gcc or simavr missing; items 2 and 3 not run"
fi

# --- 4. station procedure and its operating characteristic (item 4) -------
sect "4. station fitting procedure and gate, through the firmware routine"
if [ $have_py = 1 ]; then
  gcc -O2 -shared -fPIC -I"$SRC" -o "$O/libker.so" "$SRC/ker_comp.c" "$EV/batch.c"
  "$PY" "$EV/station_fit.py" "$O/libker.so" > "$R/station_fit.txt" 2>&1 \
    && pass "station_fit.py (offsets over the whole circle)" || fail "station_fit.py"
  "$PY" "$EV/station_sim.py" "$O/libker.so" 0.05 1024 4000 0 0 0.05 > "$R/station_oc.txt" 2>&1
  if grep -qE 'A .*0 *$|no part' "$R/station_oc.txt" 2>/dev/null || [ -s "$R/station_oc.txt" ]; then
    pass "station_sim.py operating characteristic (see results/station_oc.txt)"
  else
    fail "station_sim.py produced nothing"
  fi
else
  skip "encoder/.venv missing; item 4 not run"
fi

# --- 5. M5 float32 accumulation, with mutant C as the negative control ----
sect "5. M5 float32 accumulation (item 7)"
if [ $have_py = 1 ]; then
  sed 's|int32_t delta = ((acc + 512) >> 10) \* 8;|int32_t delta = (acc + 64) >> 7;|' \
      "$SRC/ker_comp.c" > "$O/mut_c.c"
  if diff -q "$O/mut_c.c" "$SRC/ker_comp.c" >/dev/null; then
    fail "mutant C did not apply -- the negative control is not testing anything"
  else
    gcc -O2 -shared -fPIC -I"$SRC" -o "$O/libmutc.so" "$O/mut_c.c" "$EV/batch.c"
    if "$PY" "$HERE/../docs/evidence/v5-accuracy-review-scripts/author_s3_check.py" \
         "$O/libker.so" "$O/libmutc.so" > "$R/m5_accumulation.txt" 2>&1; then
      pass "calibrated output accumulates exactly; mutant C drifts"
    else
      fail "M5 accumulation check (see results/m5_accumulation.txt)"
    fi
  fi
else
  skip "encoder/.venv missing; item 7 not run"
fi

# --- 6. the host tool agrees with the firmware (deliverable 4) ------------
sect "6. kercal against the firmware's own C"
if [ $have_py = 1 ]; then
  if (cd "$HERE/.." && .venv/bin/python -m unittest discover -s tools/kercal/tests) \
       > "$R/kercal.txt" 2>&1; then
    pass "kercal unit tests ($(grep -oE 'Ran [0-9]+ tests' "$R/kercal.txt") )"
  else
    fail "kercal unit tests (see results/kercal.txt)"
  fi
else
  skip "encoder/.venv missing; kercal tests not run"
fi

# --- 7. firmware builds, and its size ------------------------------------
sect "7. firmware build and resource usage"
if [ -x "$HERE/../.venv/bin/pio" ]; then
  if (cd "$HERE/.." && .venv/bin/pio run) > "$R/build.txt" 2>&1; then
    grep -E '^(RAM|Flash):' "$R/build.txt" | sed 's/^/  /'
    pass "pio run"
  else
    fail "pio run (see results/build.txt)"
  fi
else
  skip "PlatformIO not installed in encoder/.venv"
fi

printf '\n== summary ==\n'
if [ $fails -eq 0 ]; then printf '  all checks passed\n'; else printf '  %d check(s) FAILED\n' $fails; fi
exit $((fails != 0))
