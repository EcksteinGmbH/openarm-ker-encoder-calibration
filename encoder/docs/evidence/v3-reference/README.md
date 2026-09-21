# Reference evidence (spec v3, updated through v6)

Reference implementation of the compensation arithmetic (spec §7), the station fitting procedure
(§7.2), the station commissioning (§7.7), and the measurements the spec cites. Not firmware: `ref_comp.c` is ported to `encoder/src/ker_comp.c` once the spec is approved.

Prerequisites: `encoder/.venv` (see `encoder/requirements-dev.txt`), host `gcc`, `simavr`
(`apt install simavr`), and the avr-gcc that PlatformIO installs.

```bash
cd encoder/docs/evidence/v3-reference
T=~/.platformio/packages/toolchain-atmelavr/bin
O=$(mktemp -d)

python3 gen_sinq.py                                   # sine tables + 16-bit bound

# §7.5 arithmetic accuracy (≈ 1 min)
gcc -O2 -Wall -Wextra -o $O/acc acc.c ref_comp.c -lm && $O/acc

# §11.2 AVR differential: host and AVR hashes must match line for line
gcc -O2 -o $O/dh diff_main.c ref_comp.c && $O/dh > $O/host.txt
$T/avr-gcc -mmcu=atmega328p -Os -o $O/da.elf diff_main.c ref_comp.c
simavr -m atmega328p -f 16000000 $O/da.elf 2>&1 | grep -oE "[0-9a-f]{8}" > $O/avr.txt
diff $O/host.txt $O/avr.txt && echo "AVR == host"

# §11.2 negative controls: each mutant's host output is unchanged, its AVR output must differ
for m in int16 uncal; do
  cp ref_comp_mutant_$m.c.txt $O/mut_$m.c
  gcc -O2 -I. -o $O/mh diff_main.c $O/mut_$m.c && $O/mh | diff -q - $O/host.txt && echo "mutant $m invisible on host"
  $T/avr-gcc -mmcu=atmega328p -Os -I. -o $O/ma.elf diff_main.c $O/mut_$m.c
  simavr -m atmega328p -f 16000000 $O/ma.elf 2>&1 | grep -oE "[0-9a-f]{8}" | diff -q - $O/host.txt || echo "mutant $m caught on AVR"
done

# §7.1 uncalibrated path equals upstream, all codes
gcc -O2 -I. -o $O/compat uncalibrated_equals_upstream.c ref_comp.c && $O/compat

# §7.2 station procedure, end to end through ker_compensate(), and its operating characteristic
gcc -O2 -shared -fPIC -o $O/libref.so ref_comp.c batch.c
../../../.venv/bin/python station_fit.py $O/libref.so
PY=../../../.venv/bin/python
# arguments: sigma, K, parts, N_FIT=N_VAL (0 = default), offset drift between passes, hysteresis half-difference
$PY station_sim.py $O/libref.so 0.05 1024 4000 0 0 0.05      # default: results/station_oc_K1024.txt
$PY station_sim.py $O/libref.so 0.05 1024 4000 0 0.01 0.05   # offset drift between passes: same grades
$PY station_sim.py $O/libref.so 0.05 1024 4000 64 0 0.05     # below the position minimum: mis-grades appear
$PY station_sim.py $O/libref.so 0.05 256 4000 0 0 0.05       # K = 256: a third 'insufficient data'

# §11.2 seam coverage of the differential-test sets
gcc -O2 -I. -o $O/seam seam_check.c ref_comp.c && $O/seam

# §7.5 constructed worst case (reviewer's constructor)
gcc -O2 -I. -o $O/construct ../v3-review-scripts/construct.c ref_comp.c -lm && $O/construct

# §8.3 cycles
$T/avr-gcc -mmcu=atmega328p -Os -o $O/cy.elf cyc_main.c ref_comp.c
simavr -m atmega328p -f 16000000 $O/cy.elf 2>&1 | grep "N="
$T/avr-gcc -mmcu=atmega328p -Os -I. -o $O/cw.elf ../v3-review-scripts/cyc_worst.c ref_comp.c
simavr -m atmega328p -f 16000000 $O/cw.elf 2>&1 | grep "N="            # worst-case inputs
$T/avr-gcc -mmcu=atmega328p -Os -o $O/crc.elf crc8_cycles.c
simavr -m atmega328p -f 16000000 $O/crc.elf 2>&1 | grep -oE "b[0-9]+ t[0-9]+ e[0-9]"   # bitwise / table / agree

# §7.5 analytic ceiling (per-term worst error) and §10 flash cost
gcc -O2 -I. -o $O/wt ../v3-review-scripts/worstterm.c ref_comp.c -lm && $O/wt | python3 ceiling.py
$T/avr-gcc -mmcu=attiny1616 -Os -I. -ffunction-sections -Wl,--gc-sections -o $O/s0.elf flash_cost.c ref_comp.c
$T/avr-gcc -mmcu=attiny1616 -Os -I. -DWITH -ffunction-sections -Wl,--gc-sections -o $O/s1.elf flash_cost.c ref_comp.c
$T/avr-size -A $O/s0.elf $O/s1.elf | awk '/^\.(text|rodata)/{s+=$2} /^Total/{print s; s=0}'   # difference = cost

# §7.7 station commissioning: results/ref_selfcal.txt (single-threaded BLAS is ~15x faster on these small fits)
OPENBLAS_NUM_THREADS=1 ../../../.venv/bin/python ref_selfcal.py 100 300

# §7.1 / §11.2 item 7: the M5's float32 accumulation is exact for the 8-LSB-rounded output
cp ref_comp_mutant_noround.c.txt $O/mut_noround.c && gcc -O2 -I. -shared -fPIC -o $O/libmut.so $O/mut_noround.c batch.c
../../../.venv/bin/python ../v5-accuracy-review-scripts/author_s3_check.py $O/libref.so $O/libmut.so   # mutant C = negative control

# §7.3, §7.6 simulations
../../../.venv/bin/python base_mapping.py
../../../.venv/bin/python harmonics_v3.py            # several minutes
```

`results/` holds the outputs as cited in spec v6; `./regen_results.sh` regenerates every file there that
depends on `ref_comp.c`. `results-v5/` keeps the v5 outputs (before the rounding to 8 LSB and the
two-direction procedure).
