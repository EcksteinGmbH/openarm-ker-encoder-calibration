# Independent numerical verification: `encoder/docs/protocol-spec.md` v3

Reviewer: critic (independent re-derivation). I did not take any number from the spec on trust.
Every number below was either reproduced by a command shown here or is marked unverifiable.
Scratch directory (build outputs, scripts): `/tmp/claude-1000/-home-dev-workspace/38490050-73d7-4d9c-8938-ba86d5c14f65/scratchpad/v3num/`

**VERDICT: REVISE.** One BLOCKER: the normative station procedure (§7.2) produces a wrong calibration for any real mounting offset. Two MAJORs: the §7.5 "worst case" is not the worst case, and the §11.2 differential test never runs the uncalibrated path. The arithmetic itself (`ref_comp.c`) is sound.

Mode: this review escalated to ADVERSARIAL after the BLOCKER was found. Adjacent material was then checked: sims with an offset, a constant column, and the firmware's bin-floor quantisation.

---

## Verdict summary

| Area | Result |
|---|---|
| A. `ref_comp.c` correctness | **Clean.** No overflow, sign or rounding bug. The `_Static_assert` bound is exact. One ISO-C/`int`-width caveat (MINOR). |
| B. §7.5 accuracy | `acc.c` reproduces byte-identically. **The 0.002341° "adversarial worst" is beaten: 0.002587° constructed, ceiling 0.002605° (MAJOR).** The 0.005° budget still holds, with a 1.92× margin rather than 2.1×. |
| C. §11.2 differential test | Reproduces, and the mutant is caught 14/14. **My own host-invisible mutant in the `n == 0` path passes 0/14 (MAJOR).** |
| D. §8.3 cycles | 1047 reproduces. The true worst case is 1056. The AVRxt transfer holds, but for a different reason than the spec gives. The SSC line is mis-extrapolated: ≈ 48 µs, not 35, so the read step is ≈ 112 µs (MINOR). |
| E. §7.3 / §7.6 simulations | Both reproduce byte-identically. The conclusions follow from the numbers. There is one wording overreach (MINOR). |
| F. Constants | All check except §2.6 "+178 °C", which should be +209 °C (MINOR), and §10's "732 B of code" (MINOR). |
| G. Station procedure | Conversion, phase units and sign are consistent at zero offset. **"No constant term" breaks the fit for any non-zero mounting offset (BLOCKER).** |

---

## BLOCKER

### B-1. §7.2 station procedure: "No constant term" leaks the mounting offset into the harmonics

§7.2 step 2 is `y = wrap(θ_true − θ_s)`, and step 3 says `"Least-squares fit y ≈ Σ (a_k sin kθ_s + b_k cos kθ_s). **No constant term.**"`

The rationale is that the constant part of `y` is the mounting offset. That offset is real and arbitrary: the magnet's zero relative to the stage zero. The spec itself says `"the station cannot know"` it. Leaving the constant out of the regression does not make it go away:

- The sin/cos(kθ_s) columns are not orthogonal to a constant over the actual sample set.
- θ_s is warped by the very error being fitted, so column means are O(k·A_k) even for uniform θ_true.
- The offset therefore projects onto the harmonic coefficients.

**Reproduction.** `station.py` applies §7.2 steps 1–5 verbatim to a synthetic sensor (typical part, H1 = 1.0°, small H4–H6, floor-quantised to 15 bits). It then evaluates the coefficients through the **real `ker_compensate()`** (ctypes on `ref_comp.c`) and reports the residual after mean removal, so the M5 zero absorbs any constant.

```
$ .venv/bin/python station.py
typical part (H1 1.0 deg, small H4-6), 15-bit, worst of 5 phase draws, residual after mean removal (deg)
 offset positions  spec: no const  with const col
    0.0       360         0.00790         0.00807
    1.0       360         0.05162         0.00782
    5.0       360         0.21915         0.00740
   30.0       360         1.30646         0.00750
  100.0       360         4.75397         0.00812
  179.0       360             inf             inf        <- |A_k| > 32767, step 5 rejects
    0.0      4096         0.00689         0.00689
    1.0      4096         0.05109         0.00661
    5.0      4096         0.22979         0.00701
   30.0      4096         1.20204         0.00708
  100.0      4096         4.49545         0.00707
  179.0      4096             inf             inf
```

- A 1° offset yields a 0.05° residual, 7× the design's own model residual. Offsets of 30° to 100° yield degree-level errors.
- Near 180°, `wrap()` into (−180°, 180°] splits `y` across the seam. Even a fit with a constant column then fails (an amplitude > 32767, which step 5 rejects). If offsets are uniformly distributed, about 1 % of modules have the offset within ±2° of 180°.
- None of `base_mapping.py`, `harmonics_v3.py` or `acc.c` ever simulates a non-zero offset, which is why the evidence did not show this.
- At offset 0, the procedure and firmware agree: 0.0079° / 0.0069°, consistent with §7.6. So the A_k/φ_k conversion, BAM16 phase units and the sign of the correction are right. Only the constant handling is wrong.

Confidence: HIGH. The procedure is normative (`"The station and the firmware must agree exactly on this"`) and needs no other context to refute it.

**Fix (procedure text only):**
1. Remove the offset before wrapping: `y = wrap(θ_true − θ_s − c0)`, where `c0` is the circular mean of `θ_true − θ_s`.
2. Fit **with** a constant column and discard it. It still is not stored, which is what D4 actually needs.
3. Re-run `base_mapping.py` and `harmonics_v3.py` with a random offset to show the tables do not change. With a constant column I measured the same values: `bm_const.py` gives 0.00565 / 0.00656, versus 0.00571 / 0.00673 without it.

---

## MAJOR

### M-1. §7.5 "adversarial worst 0.002341°, margin 2.1×" is not the worst case

The hill-climb in `acc.c` (8 × 4000 steps from all amplitudes = −32768) is a local search. The worst case can be computed directly. For a fixed code r, harmonic k's argument is `(k·a16 + φ_k) mod 2¹⁶`. The phases are free, so every term can be placed independently at its own worst argument, with a consistent sign.

`worstterm.c` does an exhaustive search over all int16 amplitudes × all 65536 arguments of the per-term error `((amp·s)>>8)/128 − amp·sin`, in 3.4 s:

```
max term err +2.4404 LSB at amp=-32768 arg=14389 ; min -2.4458 LSB at amp=-32739 arg=47157
```

- The ceiling for N = 6 is 6 × 2.4458 + 0.5 (final rounding) = **15.175 LSB = 0.002605°**.
- `construct.c` picks per-term candidates and verifies each with a full 32768-code sweep against `acc.c`'s own double reference:

```
N=1 constructed worst: 2.933 LSB = 0.000503 deg
N=2 constructed worst: 5.364 LSB = 0.000921 deg
N=3 constructed worst: 7.792 LSB = 0.001338 deg
N=4 constructed worst: 10.205 LSB = 0.001752 deg
N=5 constructed worst: 12.652 LSB = 0.002172 deg
N=6 constructed worst: 15.071 LSB = 0.002587 deg (full sweep max 15.071 LSB at r=0)
   amps/phases: 32667/14394 -32707/51147 -32751/51147 32491/18379 32625/14389 -32355/47157
```

- **0.002587° beats the spec's 0.002341° by 10.5 %.** The margin is **1.93×** (1.92× at the ceiling), not 2.1×.
- The budget is still met. The worst case scales as ≈ 2.45·N + 0.5 LSB, so it is monotone in N, and N < 6 is never worse.
- For the record, a 1 Q15 unit of the 2.44 per-term error comes from the scale mismatch: the table peak is 32767 but the result is divided by 2¹⁵. Of the Q15 error, 1.459 is against 32767·sin and 2.440 against 32768·sin (`sinchk`). This is information, not a finding.

Confidence: HIGH. This is the same failure class as v2's rejected headline: a search result stated as a worst case. Realist check: no functional impact, and the conclusion is unchanged. It stays MAJOR only because it is a stated worst-case figure in the verification chapter and the exact bound costs 3 s to compute. **Fix:** quote the analytic ceiling (0.0026°, margin 1.9×) and ship `worstterm.c`/`construct.c` in the evidence.

`acc.c` model check: the double reference is §7.1. It uses the base `r<<6` when n ≥ 1, `th = r·2π/32768`, phase `·2π/65536`, adds the correction, and takes mod 2²¹. Clean.

### M-2. §11.2 differential test never exercises `n == 0` (or N = 1, 2, 4, 5); a host-invisible AVR bug passes 14/14

The committed sets are 13 × n = 6 plus 1 × n = 3. The uncalibrated path runs on **every module until it is calibrated** and is never hashed on AVR.

I tested a plausible mutant, `mutA.c`, which moves the cast in the `n == 0` path: `return (uint32_t)(raw15 << 6) | (raw15 >> 9);`. On AVR, `raw15 << 6` is a 16-bit `unsigned int` and truncates. On the host it does not.

```
mutA: invisible on host (diff_main)
mutA: AVR differs on 0 of 14 sets                         <- passes §11.2 as specified
```

With the harness extended by sets 14..19 (n = 0..5), `diff_ext.c`:

```
ref_comp: sets differing from host (0-based):             <- reference clean for n=0..5 on AVR too
mutA: sets differing from host (0-based): 14              <- caught only by the new n=0 set
mutB: sets differing from host (0-based): 1 2 5 6 7 9 11 13
ref_comp_mutant_int16.c: ... 0..13 15 16 17 18 19
```

- `mutB` is a seam-only mutant: a hand-written wrap using `(1 << 21)`. It is wrong only for the few codes near 0° where `u + Δ < 0`. It is caught by 8/14 sets.
- This shows that full-sweep hashing does detect few-code bugs, but only when a set drives that path. 6 of the 14 sets would miss this one.
- Hashing 3 bytes per output covers bits 0–23, which includes all 21 output bits plus the 3 that must be zero. FNV-1a collision risk is negligible. That part is sound.

§11.2 item 3's `"This proves the differential test detects the class of bug that host tests cannot"` is overstated: it proves this only for the code path the sets exercise. Realist check: an AVR-only `n == 0` bug would show up quickly on the bench as wildly wrong angles on every uncalibrated module. It is still MAJOR, because the spec presents §11.2 as the gate for exactly this class of bug. **Fix:** make the fixed set include n = 0, 1, …, 6 and at least one set with negative `u + Δ` at the seam. State this in §11.2 item 2.

---

## MINOR

1. **§8.3 SSC line mis-extrapolates.** The spec computes `"upstream's 32-clock read ≈ 14 µs"` × 80/32 = 35 µs. The v2 model it cites splits the 14 µs into a constant-folded `sscWrite16` (≈ 48 cy) and a 16-clock `sscRead16` (224 cy, 11.2 µs). See v2 numerics review, lines 467–480.
   - The new transaction is 1 write + 4 reads, so ≈ 48 + 4 × 224 + ≈ 8 = 952 cy ≈ **48 µs**.
   - The read step becomes ≈ 48 + 6 + 52.8 + 5 ≈ **112 µs**, not ≈ 100 µs. The slack is ≈ 868 µs, and the CS-low window is ≈ 48 µs rather than 35, which is relevant to §8.4 item 4.
   - Housekeeping at +27 µs is consistent (≈ 25 µs).
   - Only compensation and CRC are *measured*, and both on the wrong core. The conclusion holds.
2. **§8.3 "worst case 1047 cycles" is the worst for one coefficient set.** The per-harmonic branches are: odd quadrant +3, quadrant ≥ 2 +2, s < 0 +1 in `__mulhisi3`, and amp < 0 +3 in `__usmulhisi3_tail`. With all amplitudes negative and all arguments in Q3 at r = 0 (`cyc_worst.c`), the worst is `N=6 min=1029 max=1056`, so the true worst is 1056 cy = 52.8 µs.
3. **§8.3 AVRxt reasoning is right for the wrong reason.** `"faster push/call, slower lds"`: there is no `lds` in the hot path. My instruction-timing tally for the N = 6 worst path on the attiny1616 build is below. The object code is byte-identical to the atmega328p build (`diff` of the disassembly is empty). The AVRe/AVRxt timings are from the AVR Instruction Set Manual.

   | Instruction (count, N = 6) | AVRe | AVRxt | Δ |
   |---|---|---|---|
   | `push` × 18 | 2 | 1 | −18 |
   | `call` × 13 (outer, 6 × `__mulhisi3`, 6 × `__umulhisi3`) | 4 | 3 | −13 |
   | `ld` from `ker_sinq` × 24 (4 per harmonic) | 2 (SRAM on 328P: `.data` 288 B, `ker_sinq` @ `0x80010c`) | ≥ 3 (memory-mapped flash via NVMCTRL, "minimum one extra cycle") | ≥ +24 |
   | `pop`, `ret`, `jmp`, `ld`/`ldd` SRAM, `mul`, `adiw`, `sts` | same | same | 0 |

   The net is ≈ −7 cycles, so ≈ 1049 cy ≈ 52.5 µs. N = 0: 154 → ≈ 135. "Within a few percent" holds.
   - The flash-read penalty, which is the one AVRxt term that makes the loop *slower*, is not in the simavr number at all, because on the 328P the table sits in SRAM.
   - The penalty can exceed +1 under NVM contention, so §8.4 item 5 is the real confirmation.
   - Hot-loop structure is confirmed: one libgcc call per harmonic (`R_AVR_CALL __mulhisi3`), with no shift loops inside the loop. The only shift loops are `<<6` (6 iterations) and `>>7` (7 iterations), once per call, outside the loop.
4. **§2.6 TEMPR example.** `0x1AD` = 429 when read unsigned gives (429 + 152)/2.776 = **+209.3 °C**, not "+178 °C". The rest of the example is correct: −82.6 → −83 → `0x1AD`, and the zero crossing is 54.76 °C.
5. **§10 "732 bytes of code plus the 260-byte table" is not reproducible.** `avr-gcc -mmcu=attiny1616 -Os`: `.text` is 0x1e0 = 480 B (`ker_compensate` 362, `ker_sin_q15` 118) and `.rodata` is 260. The linked libgcc multiply adds 60 B (`__mulhisi3` 16, `__umulhisi3` 30, `__usmulhisi3` 4, tail 10), for ≈ 540 B of code. 732 looks like a whole test image's `.text` (my minimal image is 742). It errs high, and the headroom conclusion is unaffected. `.data = 0` and the table in mapped flash are confirmed (`ker_sinq` at `0x82E6` in my image; the address depends on the image).
6. **Evidence without generators.** No source in `evidence/v3-reference/` produces `results/uncalibrated_equals_upstream.txt` or `results/crc8_cycles_atmega328p_sim.txt`. The spec header says every *measured* number is reproducible.
   - I reproduced the first independently: `uncal.c` gives `n=0 vs main.cpp:367-368 over all 65536 raw words: 0 mismatches`.
   - The CRC-8 "123 cycles" is **unverifiable** as shipped.
7. **§7.4 item 4 "Integer widths are explicit everywhere" is not quite true.** In `ref_comp.c:54`, `(uint16_t)(raw15 << 1)` shifts a promoted signed `int`. On AVR (16-bit `int`) with raw15 ≥ 0x4000, that is signed-shift overflow, which ISO C leaves undefined. GCC documents that it does not exploit this, so it is harmless with avr-gcc. It is still a residual `int`-width dependence that host UBSan cannot see. The same applies to the `n == 0` line's `raw15 >> 9`, which is fine. `(uint16_t)(arg + a16)` is fine on both targets.
8. **`gen_sinq.py` bound assumes a monotone table without asserting it.** `worst = max_step·(2^shift−1) + 2^(shift−1)` is exactly the maximum of the C expression, rounding constant included. I confirmed this exhaustively: max product 51118, the static assert fires for 6-bit on host and avr-gcc, and the regenerated tables are byte-identical. It is only valid if every step `a1 − a0 ≥ 0`, and a negative step would be cast to ≈ 65535 without the assert noticing. That is true for both shipped tables (checked), so it is a latent hole only. Separately, the response doc's "205 020" omits the +128 rounding constant (the bound file says 205148).
9. **§7.6 wording.** `"Good and typical parts reach the quantisation floor"` holds only for the H1–3-only rows. Typical with small H4–H6 is 0.00701 = 1.28× the 0.00549 floor, and typical-moderate is 1.7×. Also, §7.5 says model residual "0.006° – 0.04°" while O1 says "≈ 0.02° for poor ones". The 0.04 is the worst-moderate row (0.03872), which the §7.6 table omits.
10. **`harmonics_v3.py` quantises to the bin centre with neither a constant column nor mean removal. The firmware uses the bin floor.**
    - Bin floor without demeaning gives 0.01248, which is wrong. Bin floor with the mean removed gives 0.00745. Bin floor with a constant column gives 0.00723, identical to the bin-centre result (`hcheck.py`, 60 fresh draws).
    - So the bin-centre shortcut stands in for the mean removal the M5 zero performs, and the difference is ≤ 3 %.
    - It is only exactly equivalent with a constant column, which ties back to B-1.
11. **`ker_compensate()` indexes `amp[k]` / `phase[k]` for `k < c->n` without bounding n ≤ 6.** Safety rests entirely on §5.2 validation. This is acceptable for a reference, but worth a line in §7.4, since the file is to be ported verbatim.

---

## What's missing

- No simulation with a non-zero mounting offset or a sparse station. The §7.6 sims use 131072 uniformly spaced reference positions (4 per code). With 360 positions I get 0.0079° against 0.0069° at 4096 (typical, offset 0). §7.6 figures are therefore for an ideal dense station, which O3 has not decided on.
- No worst-case (as opposed to worst-found) statement for cycles or accuracy. Both are cheaply computable, as shown above.
- No AVRxt timing of memory-mapped flash reads. This is the only term in which the target is slower than the simulated core.

## Checked and found clean (reproduced)

- `ref_comp.c` overflow audit:
  - |amp·s| ≤ 1,073,709,056 < 2³¹; per term after `>>8` ≤ 4,194,176; six terms ≤ 25,165,056; δ ≤ 196,602.
  - `u + δ` ∈ [−196,602, 2,294,690] in int32. The mask on a negative two's-complement value is correct on both the 32-bit and 64-bit `long` hosts.
  - Interpolation ≤ 51,118 < 2¹⁶; the sine range is exactly ±32767 and odd-symmetric over all 65536 arguments; `idx + 1` ≤ 129 = pad; `x == 0x4000` gives `idx` 128, `frac` 0, value 32767.
  - raw15 ≥ 32768 is masked as §1.7 specifies. `raw15 << 1` is the exact BAM16 of θ_s.
- `acc.c`: byte-identical to `results/accuracy_host.txt` (1 m 02 s). Realistic 0.000274° is confirmed.
- AVR differential: 14/14 identical to host and to `results/host.txt`. The int16 mutant is invisible on the host and differs on 14/14 on AVR, identical to `results/avr_bug.txt`. The reference also matches on AVR for n = 0..5 (my extension).
- Cycles: `cyc_main.c` output is byte-identical to `results/cycles_atmega328p_sim.txt`. The object code is identical for atmega328p and attiny1616. There is no 32-bit shift loop in the per-harmonic loop, and exactly one libgcc call per harmonic.
- `base_mapping.py` and `harmonics_v3.py`: byte-identical to the results files (72 s with 12 cores). The §7.3 "roughly doubles" claim survives a constant column. "Six better than five in every case": every table row, and paired 60/60 in fresh draws. "13 % at 3×": 0.00661 → 0.00578 is 12.6 %, with 6 vs 18 evaluations. Worst-of-20 varies by ±4 % across disjoint batches (0.00694 / 0.00723 / 0.00690), which is fair for comparison but is not a bound.
- §1.7: gain 64 + 1/512 (full-scale ratio 64.00192), ramp 0–63 LSB = 0.01081°.
- §5.1: field widths, word/byte offsets, `2k+1` / `2k+2`, LSB 0.000172°, span ±5.625°, CAL_DAY 4095 → 2037-03-19.
- §5.2: CRC-16/CCITT-FALSE check value 0x29B1, and `CRC16(30 × 0xFF) = 0x5FBD` ≠ 0xFFFF.
- §8.1 / §8.4 timeline: 20 µs frame at 2 Mbps 8N1; 30 µs/hop gives 20 / 230 / 470 µs; cascade ≈ 500 µs; 500 + 16 × 50 ≈ 1300 µs.
- §10 baseline rebuilt with the project venv (PlatformIO 6.2.0): `RAM 179 / 2048 (8.7 %)`, `Flash 2578 / 16384 (15.7 %)`. The headroom arithmetic follows from the stated estimates, which are not verifiable.
- §7.2 conversion A_k / φ_k (BAM16, sign of the correction) is consistent with `ker_compensate()` at zero offset.

## Verdict

**REVISE.** B-1 must be fixed before the station tool (deliverable 4) is written, or every module with a non-zero magnet offset will be calibrated wrong by 0.05° to several degrees. M-1 and M-2 are text and test-set changes. The minors are corrections to numbers whose conclusions all stand. After those fixes, the numerics I checked would support ACCEPT.

Realist-check recalibrations:
- M-1 is kept at MAJOR, not raised, because the budget is still met.
- M-2 was not raised to BLOCKER, because bench bring-up would expose an `n == 0` AVR bug quickly.
- The SSC mis-extrapolation was downgraded to MINOR because the slack is about 8× the discrepancy.

Open questions (unscored):
- Does the flash-mapped table read penalty on ATtiny1616 exceed +1 cycle under NVMCTRL contention? This needs §8.4 item 5.
- Is the station's rotary-stage zero aligned to the magnet at all? If it is aligned to < 0.01°, B-1's impact shrinks, but nothing in the spec requires or assumes that.
