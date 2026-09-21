#!/usr/bin/env bash
# Regenerates every file in results/ that depends on ref_comp.c. Run from this directory.
# Same commands as README.md; harmonics_v3.py and base_mapping.py do not use ker_compensate() and are not re-run.
set -euo pipefail
T=~/.platformio/packages/toolchain-atmelavr/bin
PY=../../../.venv/bin/python
O=$(mktemp -d)
R=results

python3 gen_sinq.py >/dev/null

gcc -O2 -Wall -Wextra -o $O/acc acc.c ref_comp.c -lm && $O/acc > $R/accuracy_host.txt

gcc -O2 -o $O/dh diff_main.c ref_comp.c && $O/dh > $R/host.txt
$T/avr-gcc -mmcu=atmega328p -Os -o $O/da.elf diff_main.c ref_comp.c
simavr -m atmega328p -f 16000000 $O/da.elf 2>&1 | grep -oE "[0-9a-f]{8}" > $R/avr.txt || true
diff $R/host.txt $R/avr.txt && echo "AVR == host"

for m in int16 uncal; do
  cp ref_comp_mutant_$m.c.txt $O/mut_$m.c
  gcc -O2 -I. -o $O/mh diff_main.c $O/mut_$m.c && $O/mh > $R/host_mutant_$m.txt
  diff -q $R/host_mutant_$m.txt $R/host.txt && echo "mutant $m invisible on host"
  $T/avr-gcc -mmcu=atmega328p -Os -I. -o $O/ma.elf diff_main.c $O/mut_$m.c
  simavr -m atmega328p -f 16000000 $O/ma.elf 2>&1 | grep -oE "[0-9a-f]{8}" > $R/avr_mutant_$m.txt || true
  diff -q $R/avr_mutant_$m.txt $R/host.txt >/dev/null || echo "mutant $m caught on AVR ($(diff $R/avr_mutant_$m.txt $R/host.txt | grep -c '^<') of 21 sets differ)"
done

gcc -O2 -I. -o $O/compat uncalibrated_equals_upstream.c ref_comp.c && $O/compat > $R/uncalibrated_equals_upstream.txt

gcc -O2 -shared -fPIC -o $O/libref.so ref_comp.c batch.c
$PY station_fit.py $O/libref.so > $R/station_fit.txt
$PY station_sim.py $O/libref.so 0.05 1024 4000 0 0 0.05    > $R/station_oc_K1024.txt
$PY station_sim.py $O/libref.so 0.05 1024 4000 0 0.01 0.05 > $R/station_oc_K1024_drift0.01.txt
$PY station_sim.py $O/libref.so 0.05 1024 4000 64 0 0.05   > $R/station_oc_K1024_N64.txt
$PY station_sim.py $O/libref.so 0.05 256 4000 0 0 0.05     > $R/station_oc_K256.txt

gcc -O2 -I. -o $O/seam seam_check.c ref_comp.c && $O/seam > $R/diff_sets_seam_coverage.txt

gcc -O2 -I. -o $O/construct ../v3-review-scripts/construct.c ref_comp.c -lm && $O/construct > $R/accuracy_constructed_worst.txt

$T/avr-gcc -mmcu=atmega328p -Os -o $O/cy.elf cyc_main.c ref_comp.c
simavr -m atmega328p -f 16000000 $O/cy.elf 2>&1 | sed 's/\x1b\[[0-9;]*m//g' | grep -oE "N=[0-9]+ min=[0-9]+ max=[0-9]+" > $R/cycles_atmega328p_sim.txt || true
$T/avr-gcc -mmcu=atmega328p -Os -I. -o $O/cw.elf ../v3-review-scripts/cyc_worst.c ref_comp.c
simavr -m atmega328p -f 16000000 $O/cw.elf 2>&1 | sed 's/\x1b\[[0-9;]*m//g' | grep -oE "N=[0-9]+ min=[0-9]+ max=[0-9]+" > $R/cycles_worst_atmega328p_sim.txt || true

gcc -O2 -I. -o $O/wt ../v3-review-scripts/worstterm.c ref_comp.c -lm && $O/wt | python3 ceiling.py > $R/accuracy_analytic_ceiling.txt

$T/avr-gcc -mmcu=attiny1616 -Os -I. -ffunction-sections -Wl,--gc-sections -o $O/s0.elf flash_cost.c ref_comp.c
$T/avr-gcc -mmcu=attiny1616 -Os -I. -DWITH -ffunction-sections -Wl,--gc-sections -o $O/s1.elf flash_cost.c ref_comp.c
$T/avr-size -A $O/s0.elf $O/s1.elf | awk '/^\.(text|rodata)/{s+=$2} /^Total/{print s; s=0}' | paste -sd' ' | \
  awk '{printf "linked flash cost of ker_compensate on attiny1616 (code + libgcc + 260 B table, -Os, gc-sections): %d bytes\n", $2-$1}' > $R/flash_cost_attiny1616.txt
OPENBLAS_NUM_THREADS=1 $PY ref_selfcal.py 100 300 > $R/ref_selfcal.txt
cp ref_comp_mutant_noround.c.txt $O/mut_noround.c && gcc -O2 -I. -shared -fPIC -o $O/libmut.so $O/mut_noround.c batch.c
$PY ../v5-accuracy-review-scripts/author_s3_check.py $O/libref.so $O/libmut.so > ../v5-accuracy-review-scripts/results/author_s3_check.txt
echo "regen done"
