# Independent numerical verification — `encoder/docs/protocol-spec.md` v2

Reviewer: critic (independent re-derivation). Nothing below is taken from the spec on trust.
Every number is either reproduced by a command shown here or marked unverifiable.

Scratch: `/tmp/claude-1000/-home-dev-workspace/38490050-73d7-4d9c-8938-ba86d5c14f65/scratchpad/verify/`

---

## VERDICT SUMMARY

| Claim | Verdict |
|---|---|
| A — fixed-point accuracy §6.4 | **reproduces exactly at N_HARM=3; BLOCKER at the specified N_HARM=5** |
| B — fit-domain §6.2 | **reproduces exactly; the "2.4–2.7×" generalisation is a cherry-pick (MAJOR)** |
| C — harmonic count §6.3 | **reproduces exactly; "six buys nothing" is refuted by the spec's own table (BLOCKER)** |
| D — quantisation floor §6.1 | **verified correct** |
| E — timing §5 | **BLOCKER: the 15 µs compensation estimate is ~6× low (measured 89 µs on the real toolchain)** |
| F — USERROW §4 | **verified correct; one validation gap (MAJOR)** |
| G — resource budget §7 | **baseline reproduces byte-for-byte; the addition estimate is plausible** |

Three BLOCKERs, seven MAJORs, six MINORs. Details below.

---

# A. Fixed-point accuracy (§6.4)

## A.1 Baseline reproduction — PASSES exactly

```
$ cd .../scratchpad/verify && cp ../proto/comp.c . && gcc -O2 -o comp_orig comp.c -lm && ./comp_orig
case 0: max err =    4.110 LSB = 0.000705 deg  (at u=2058046)  PASS
case 1: max err =    4.803 LSB = 0.000824 deg  (at u=953053)   PASS
case 2: max err =    8.489 LSB = 0.001457 deg  (at u=338570)   PASS
case 3: max err =    3.011 LSB = 0.000517 deg  (at u=1837816)  PASS

21-bit LSB = 0.000172 deg ; 15-bit sensor LSB = 0.010986 deg
sine table = 130 bytes flash
```

§6.4's table (0.000705 / 0.000824 / 0.001457 / 0.000517), the "worst case 0.00146°",
and the "130 bytes of flash" all reproduce **exactly**. So does §6.1's 0.0015° row.

## A.2 BLOCKER — the 3.4× margin evaporates at the N_HARM=5 the spec mandates

`comp.c` implements 3 harmonics (`for (uint8_t k = 1; k <= 3; k++)`, comp.c:37). §4 specifies
five slots and §6.3 selects five. I extended the routine to 5 and re-measured
(`verify/comp5.c`, `verify/comp5b.c`, `verify/hunt.c`).

```
=== 2. N_HARM = 5, spec-shaped coefficient sets ===
5H geometric (1.5 deg H1)     n=5 32768rch :    5.729 LSB = 0.000983 deg PASS
5H extreme geometric          n=5 32768rch :    9.891 LSB = 0.001698 deg PASS
5H all-max alternating        n=5 32768rch :   16.166 LSB = 0.002775 deg PASS
5H all INT16_MIN              n=5 32768rch :   22.348 LSB = 0.003836 deg PASS
   delta range observed: [-163835 .. 129819]
```

Directed hill-climb over legal `int16` amplitudes / `uint16` phases, 8 restarts × 20 000 steps,
each evaluation a full 32768-code sweep (`./hunt`, 3 m 39 s):

```
  seed 1 -> 25.819 LSB = 0.004432 deg      seed 5 -> 24.955 LSB = 0.004284 deg
  seed 2 -> 25.793 LSB = 0.004428 deg      seed 6 -> 25.550 LSB = 0.004386 deg
  seed 3 -> 23.375 LSB = 0.004013 deg      seed 7 -> 25.278 LSB = 0.004339 deg
  seed 4 -> 28.333 LSB = 0.004864 deg      seed 8 -> 25.426 LSB = 0.004365 deg

GLOBAL WORST: 28.333 LSB = 0.004864 deg  (budget 0.005) -> still under
  amps: -32723 -32690 -32690 -32709 -32751   phases: 46963 42091 34403 26964 20045
  margin vs 0.005 budget: 1.03x  (spec claims 3.4x)
```

**§6.4's "Requirement 3 is met with 3.4× margin" and §6.1's "fixed-point arithmetic 0.0015°"
are true only for the 3-harmonic prototype, not for the 5-harmonic design being specified.**
At N_HARM=5 with amplitudes at the layout's own declared limit the measured worst case is
**0.004864°** — margin **1.03×**, not 3.4×. My hill-climb is a crude local search; a better
search plausibly crosses 0.005°.

The spec does say *"The sweep is to be re-run at `N_HARM = 5` once the layout is implemented"*
(§6.4, last line) — so the gap is acknowledged. But §6.1's budget table and §6.4's
"3.4× margin" headline are stated unconditionally and are **wrong for the specified design**.

For **realistic** coefficients (|H1| ≤ 1.5°, geometric decay ×1/1.7, 400 random phase sets)
the worst is **0.001099°** — the arithmetic is fine in practice. The failure is in the
*stated margin*, not in the approach.

### Why it scales this way — the dominant term is the `arg >> 5` truncation, not Q15 rounding

```
=== 8. per-harmonic error contribution, amp=32767 (5.63 deg), each harmonic alone ===
  H1 alone: 4.826 LSB = 0.000829 deg      H4 alone: 4.807 LSB = 0.000825 deg
  H2 alone: 4.807 LSB = 0.000825 deg      H5 alone: 5.795 LSB = 0.000995 deg
  H3 alone: 5.517 LSB = 0.000947 deg
```

`a16 = (arg >> (ANG_BITS-16))` (comp.c:39) discards 5 bits of the 21-bit argument, i.e. up to
31/2097152 rev = 9.29e-5 rad of argument error, which becomes `A_k × 9.29e-5` of output error.
That is linear in amplitude and **additive across harmonics**, which is exactly why going
3 → 5 terms costs ~1.7× and why the error tracks `Σ|A_k|`.

## A.3 Overflow / sign / bounds audit — NO overflow found

| Check | Result |
|---|---|
| `k*u` for k=5, u=2097151 | 10 485 755, fits `uint32_t`. **Safe.** |
| `delta` accumulator, 5 terms | observed range `[-163835 .. +163835]`; `int32_t` limit 2.1e9. **Safe.** |
| `(int32_t)u - delta` | max 2 097 151 + 163 835. **Safe.** |
| `(a1-a0)*frac` in `int32_t`, cast to `int16_t` | max `(sinq[1]-sinq[0])*255>>8` = 801. **Safe.** |
| `a0 + interp` as `int16_t` | measured value range pre-negation **`[0 .. 32767]`** over full sweep — never overflows. |
| `-v` for v = 32767 | −32767, in range. (`INT16_MIN` is unreachable because `sinq[64]=32767`.) |
| wrap seam `& ANG_MASK` on a negative `int32_t` | correct two's-complement wrap; sweep is wrap-aware and found no seam anomaly. |

## A.4 MINOR — out-of-bounds table read in `sin_q15`, benign but real UB

`sinq` has 65 entries (comp.c:13). In quadrants 1 and 3 the mirror `x = 0x4000 - x`
(comp.c:24) maps `x == 0` to `x == 0x4000`, giving `idx == 64` and therefore
`a1 = sinq[idx+1] = sinq[65]` — one element past the array.

```
=== 3. table out-of-bounds accounting ===
   sin_q15 calls with idx==64 (reads sinq[65]): 1442
   ... of which frac!=0 (would USE the OOB value): 0
```

It is provably always `frac == 0` in that branch (`idx==64 ⟺ x'==16384 ⟺ frac==0`), so the
poisoned value is multiplied by zero and the result is never wrong. It is still an
out-of-bounds read and undefined behaviour; on the ATtiny the table will be in flash, so it
reads two adjacent flash bytes. Cheap to close (`sinq[66]` or `idx>63` guard).

## A.5 MINOR — the sweep domain is right, but the quoted number is domain-specific

The task asked whether sweeping only the 32768 reachable codes is adversarial enough.
**It is the correct domain** — `main.cpp:368` guarantees the compensator's input is always a
bit-replicated 15-bit code. But for the record, a full 2²¹ sweep is 13 % worse:

```
case2 5.63/2.81/1.41   n=3 32768rch :  8.489 LSB = 0.001457 deg
case2 5.63/2.81/1.41   n=3 ALL 2^21 :  9.632 LSB = 0.001653 deg
5H all INT16_MIN       n=5 32768rch : 22.348 LSB = 0.003836 deg
5H all INT16_MIN       n=5 ALL 2^21 : 23.450 LSB = 0.004026 deg
```

If the compensated output is ever fed back through the compensator, or if a future revision
takes a wider sensor, the quoted figure no longer bounds the error.

## A.6 MAJOR — the spec's formula and the prototype disagree on sign

§6.2: `u_out = ( u_in + Σ(k=1..N_HARM) A_k · sin(k·u_in + φ_k) ) mod 2²¹`

comp.c:42: `return (uint32_t)(((int32_t)u - delta) & (int32_t)ANG_MASK);`   ← **minus**

The double reference (comp.c:53) carries the same minus, so the accuracy sweep cannot detect
the discrepancy — it compares two implementations of the *same wrong-signed* formula.
The error is absorbable by negating stored amplitudes, but §6.2, §6.4's bullet
(`Δ += (A_k · sin_q15(a16)) >> 15`) and D2 (*regress `(θ_true − θ_measured)` against
`θ_measured`*, which implies the correction is **added**) all point the opposite way from the
reference implementation that the calibration station will be written against.

## A.7 Checked and clean — no systematic bias from the `>>15` arithmetic shift

I suspected the truncating right shift (`>>15` rounds toward −∞, comp.c:40) would inject a
~0.5 LSB per-term DC bias. Measured signed mean over the full sweep:

```
  3H 1.5/0.9/0.3     max|e|= 4.110 LSB  mean(e)= +1.496 LSB (+0.000257 deg)
  5H geometric       max|e|= 5.729 LSB  mean(e)= +2.496 LSB (+0.000428 deg)
  5H all +max        max|e|=17.569 LSB  mean(e)= +2.489 LSB (+0.000427 deg)
  5H all INT16_MIN   max|e|=22.348 LSB  mean(e)= -0.001 LSB (-0.000000 deg)
```

A bias of up to +2.5 LSB = **+0.00043°** exists but is ~13× below the quantisation floor and
is a fixed offset the M5's `mech_joint_offset` absorbs. **Not a finding.**

---

# B. Fit-domain claim (§6.2)

## B.1 Reproduction — PASSES exactly

```
$ /home/dev/workspace/.piovenv/bin/python proto/domain.py
case 1: raw 1.6295  A: 0.0382  B(DC): 0.0159  B(noDC): 0.0159  factor 2.4x  DC -0.0000
case 2: raw 2.7000  A: 0.1040  B(DC): 0.0438  B(noDC): 0.0438  factor 2.4x  DC  0.0000
case 3: raw 0.4827  A: 0.0033  B(DC): 0.0013  B(noDC): 0.0013  factor 2.6x  DC -0.0000
case 4: raw 3.4245  A: 0.1683  B(DC): 0.0621  B(noDC): 0.0621  factor 2.7x  DC -0.0000
```

Every cell of §6.2's table and the "2.4–2.7×" band reproduce exactly. So does §6.3's
"the fitted DC coefficient came out 0.0000° in all four cases".

## B.2 MAJOR — "consistently 2.4–2.7×" is an artifact of the four chosen cases

300 random draws of phase (uniform 0–360°, all three harmonics) and amplitude ratio
(H1 ∈ 0.2–2.5°, H2/H1 ∈ 0.05–1.2, H3/H1 ∈ 0.02–0.9), identical methodology otherwise
(`verify/attack_bc.py`):

```
### B1. improvement factor A/B over 300 RANDOM phase sets & amplitude ratios
   A/B factor: min 0.96  p5 1.16  median 1.64  p95 4.26  max 22.48
   fraction inside the spec's quoted 2.4-2.7x band: 5.7%
   fraction where B is WORSE than A (ratio<1): 1.0%
```

The *direction* of D2 survives (measured-domain wins 99 % of the time), but the **quantified
claim does not**: the factor spans 0.96× to 22.5× with a median of 1.64×, and only **5.7 %**
of realistic cases land in the band the spec presents as "consistent". The word
"Consistently" in §6.2 is not supported by the underlying simulation once the four
hand-picked cases are replaced by a sample.

## B.3 MAJOR — Approach A is a strawman; the real trade-off is not stated

`domain.py:17` implements Approach A as `corrA = -Σ A_k sin(k·θ_m + φ_k)` — the exact
true-domain coefficients, negated, evaluated once at the wrong argument. That is a
**single-shot first-order inversion**, and the spec correctly calls it that. But a calibration
station that chooses the true-domain route would invert properly. Three fixed-point iterations
of the same true-domain model:

```
### B2. proper true-domain fit + fixed-point inversion
   typical : A(naive)=0.0382  A(3 fixed-point iters)=0.000052  B(measured-domain)=0.0159
   worst   : A(naive)=0.1683  A(3 fixed-point iters)=0.000955  B(measured-domain)=0.0621
```

The true-domain model, properly inverted, is **65×–735× more accurate than the measured-domain
fit the spec selects**. The information is all there; the entire 0.0159°/0.0621° residual of
Approach B is the cost of forcing the inverse into a 3-term Fourier series so the firmware can
evaluate it in one pass.

D2 may well still be the right call — the ATtiny cannot afford to iterate (see §E, where a
*single* 5-harmonic pass already costs 89 µs). But §6.2 presents measured-domain fitting as
strictly better ("**2.4–2.7× better**, and it removes an inversion step"), when the honest
framing is: measured-domain is 1-pass and ~65× *less* accurate than iterating, and its residual
is what forces the harmonic count up to five. The spec argues the decision on the wrong axis.

## B.4 Checked and clean — `errBn -= np.mean(errBn)`

`domain.py:34` and `nharm.py:13` subtract the residual mean post hoc, granting the model a DC
correction the firmware does not have (D4: no DC term). I measured the effect:

```
### C1. effect of post-hoc mean removal (H1-3 / H1-5, mean-removed vs not)
typical   0.01588 / 0.01588      0.00116 / 0.00116
large     0.04378 / 0.04378      0.00349 / 0.00349
good      0.00127 / 0.00127      0.00007 / 0.00007
worst     0.06211 / 0.06211      0.01424 / 0.01424
```

Identical to five decimal places. The fit residual is already zero-mean. **Not a finding.**

## B.5 MINOR — the least-squares setup itself is sound

Checked: `y = (tt - tm + 180) % 360 - 180` correctly wraps the target; the design matrix uses
sin/cos pairs rather than amplitude/phase, so the problem is linear and `lstsq` is the right
estimator; the DC column is present in `domain.py` (so "DC came out zero" is a real result, not
a constraint); sampling is uniform in θ_true, which matches a rotary stage stepping uniformly,
so the implicit weighting is correct rather than accidental. No defect found here.

---

# C. Harmonic-count claim (§6.3)

## C.1 Reproduction — PASSES exactly

```
$ /home/dev/workspace/.piovenv/bin/python proto/nharm.py
case                          raw      H1-3      H1-4      H1-5      H1-6
typical  1.0/0.5/0.2       1.6295   0.01588   0.00521   0.00116   0.00021
large    1.5/0.9/0.3       2.7000   0.04378   0.01484   0.00349   0.00096
good     0.3/0.15/0.05     0.4827   0.00127   0.00039   0.00007   0.00000
worst    2.5/1.2/0.6       3.4245   0.06211   0.04337   0.01424   0.00192

Fitted amplitude per harmonic, 'large' case (deg):
  H1: 1.49980 (8719.8 LSB)  H2: 0.89954 (5229.9)  H3: 0.30064 (1747.9)
  H4: 0.02981 ( 173.3 LSB)  H5: 0.01183 (  68.8)  H6: 0.00266 (  15.4)
```

Every cell of §6.3's table reproduces exactly.

## C.2 BLOCKER — "Six buys nothing" is refuted by the spec's own table

No simulation is needed for this one. Read the "worst" row:

| | H1–5 | H1–6 | floor |
|---|---|---|---|
| worst (3.42° raw) | **0.01424°** | **0.00192°** | 0.0055° |

At five harmonics the worst part sits **2.6× above** the quantisation floor the spec says the
model should be sized against (§6.1: *"The quantisation floor is the target the model residual
is sized against"*). Six harmonics takes it **7.4× lower**, to well below the floor. That is
the opposite of "buys nothing"; it is the difference between meeting and missing the stated
sizing target on the worst simulated part.

§6.3's actual sentence — *"Five harmonics puts **typical and large** parts at or below the
0.0055° quantisation floor"* — is carefully hedged and is true. But the very next sentence,
*"Six buys nothing physical"*, is a generalisation the table does not support, and §6.1
repeats the unqualified framing.

## C.3 What the simulation does and does not prove

**What `nharm.py` proves.** Given a sensor whose forward error `e(θ_true)` is *exactly* three
sinusoids, and given that the firmware evaluates its correction at θ_measured in a single pass,
a 5-term measured-domain Fourier series captures the composed inverse to 0.00007–0.01424°.
That is a statement about **the inversion artifact only**. `nharm.py:30` builds `e` from
exactly `range(3)` harmonics and `tm = tt + e` with nothing else added.

**What it does not prove.** It contains no intrinsic harmonics above 3, no noise, no
quantisation, no temperature term, no eccentricity/mounting error. The spec's §6.3 opening
sentence is candid about the first point (*"Even a sensor whose intrinsic error is exactly
three harmonics has an inverse containing higher orders"*), but the conclusion drawn — five
slots are sufficient — rests entirely on that assumption holding for real parts.

## C.4 MAJOR — the conclusion does not survive any intrinsic harmonic above the 3rd

```
### C2. same methodology, but the SENSOR itself carries higher harmonics
intrinsic model                        raw      H1-3      H1-4      H1-5      H1-6      H1-8
3 harmonics (nharm.py assumption)   2.7000   0.04378   0.01484   0.00349   0.00096   0.00007
5 harmonics (1.5/.9/.3/.15/.08)     2.5940   0.24205   0.08135   0.00894   0.00651   0.00130
6 harmonics (adds H6=0.05)          2.6392   0.29160   0.12139   0.05315   0.00596   0.00368
3H + H7=0.02 (mounting)             2.6910   0.05823   0.03411   0.02333   0.02296   0.00210
3H + H11=0.015                      2.7143   0.05392   0.03012   0.01941   0.01684   0.01613
   floor = 0.0055 deg
```

- An intrinsic **H5 of 0.08°** (0.5 % of H1) already pushes H1–5 to **0.00894°**, above the floor.
- An intrinsic **H6 of 0.05°** pushes H1–5 to **0.05315°** — 10× the floor — and here
  **six harmonics is worth 9×** (0.00596°).
- An intrinsic **H7 of only 0.02°** leaves 0.02333° at five harmonics, and six barely helps
  (0.02296°) — you would need eight.

O1 in §9.2 (*"measured raw angle error of your modules"*) is correctly flagged as open, but it
is stronger than "determines how many slots the station populates": **it determines whether
five slots are enough at all.** The layout is frozen at five and cannot be extended without a
LAYOUT_VER bump, so O1 is a layout-freezing risk, not a station-configuration detail.

## C.5 MAJOR — with real 15-bit quantisation in the loop, six harmonics does buy something

`nharm.py` fits against a continuous `tm`. The firmware sees 15-bit codes. Re-running with
θ_measured quantised to 32768 codes before fitting:

```
### C3. with 15-bit sensor quantisation actually applied
   large 1.5/.9/.3     H1-3=0.04929  H1-5=0.00960  H1-6=0.00703
   worst 2.5/1.2/.6    H1-3=0.06761  H1-5=0.01976  H1-6=0.00828
```

H1–5 for the "large" part degrades from 0.00349° to **0.00960°** (2.8×) and lands above the
floor, and the sixth harmonic measurably improves it (0.00703°). §6.3's numbers are
best-case figures for an unquantised sensor.

## C.6 MAJOR — §6.1's budget table quotes the residual of a design the spec rejects

§6.1: *"harmonic model residual | **0.0013 – 0.062 °** | controlled by number of harmonics — §6.3"*

Those two endpoints are the min and max of the **H1–3** column of §6.3 (0.00127 and 0.06211).
The design uses **five** harmonics (D4), for which the same table gives **0.00007 – 0.01424°**.
The top-line error budget therefore describes a 3-harmonic design while §6.3 mandates 5. The
error is in the conservative direction, but §6.1 is the table a reader will quote, and it is
not self-consistent with D4.

## C.7 Checked and clean — "no DC term" is correct

Verified independently: `domain.py`'s design matrix includes a DC column, the fitted DC comes
out ≤ 1e-4° in all four cases, and forcing it to zero changes the residual by nothing (§B.4).
A zero-mean sum of sinusoids composed with its own inverse has no identifiable constant term.
D4's arithmetic justification holds. The operational justification (the M5 owns the zero point
via `mech_joint_offset`) is a design statement I did not attempt to verify.

---

# D. Quantisation floor (§6.1)

**Verified correct.**

```
15-bit step  360/2^15 = 0.010986 deg  (spec 0.0110) OK
half step             = 0.005493 deg  (spec 0.0055) OK
21-bit step  360/2^21 = 0.000171661 deg (spec 0.000172) OK
ratio 15b/21b LSB     = 64.0000 (spec 64x) OK
```

**Is "hard floor" the right characterisation given the 21-bit output?** Yes, and §6.5 already
says so correctly. The bit-replication at `main.cpp:368` is an information-preserving
relabelling, not an interpolation — I confirmed it is strictly monotonic over all 32768 codes
and that it emits only 32768 distinct values out of 2²¹:

```
bit-replication monotonic over all 32768 codes? yes
output step sizes present: [64, 65] -> NOT a uniform x64
```

Two caveats, both MINOR:

- **§1.5's "64.0000305" is wrong.** The map is `f(r) = 64r + floor(r/512)`, whose slope is
  `64 + 1/512 = 64.001953`, and whose full-scale ratio is `2097151/32767 = 64.0019227`.
  The figure 64.0000305 appears to be `1 + 2⁻¹⁵ = 1.0000305` with the 64 spliced into the wrong
  decimal place. Off by ~64× in the correction term. Cosmetic, but it is a wrong number.
- "Hard floor" is right for a **single static reading**. Because the quantisation error is a
  deterministic function of shaft angle, it is not a floor for a moving joint or for averaged
  readings; §6.5's *"Output steps remain sensor-quantised"* is the precise statement and §6.1's
  *"nothing; hard physical floor"* is the loose one. The spec's use is defensible.

---

# E. Timing arithmetic (§5)

## E.1 Arithmetic that checks out

```
4 bytes 8N1 @2Mbps      = 4*10/2e6 = 20.0 us   (spec 20)     OK
16 x (20+10)            = 480 us               (spec 480)    OK
480 + 16*50             = 1280 us              (spec 1280)   OK ; 1280 > 1000 -> misses 1 ms: TRUE
read step 16+8+5+15     = 44 us                (spec ~45)    OK
design target 480+16*5  = 560 us               (spec ~560)   OK
```

The frame time, the cascade-does-not-compose argument, and the conclusion that a full 50 µs/hop
would break 1 kHz are all **correct**.

## E.2 BLOCKER — "5-harmonic fixed-point compensation ≈ 15 µs" is ~6× low

I compiled the compensation routine for the actual target with the actual toolchain and counted
cycles from the emitted code (`verify/ker_comp_avr.c`, `verify/cycles.py`):

```
$ ~/.platformio/packages/toolchain-atmelavr/bin/avr-gcc -mmcu=attiny1616 -O2 \
      -DF_CPU=20000000L -c ker_comp_avr.c -o ker_comp_avr.o
$ avr-objdump -dr ker_comp_avr.o
  ... 152 instructions, 310 bytes, three libgcc calls:
      0x56: R_AVR_CALL __muluhisi3    (32x32  k*u)
      0xbc: R_AVR_CALL __usmulhisi3   (16x16  (a1-a0)*frac)
      0xde: R_AVR_CALL __mulhisi3     (16x16  amp * sin_q15)

$ python cycles.py
== ker_compensate, avr-gcc 7.3.0 -O2 -mmcu=attiny1616, one harmonic iteration ==
  0x42-0x54 setup (k*u operand marshalling)       :   10 cy
  0x56 call __muluhisi3  (32x32 k*u)              :   40 cy
  0x5a-0x5e                                       :    3 cy
  0x60-0x6a SOFTWARE >>5 loop (5 iters x 7 cy)    :   34 cy   <-- (arg>>5)
  0x6c-0xba sin_q15 inlined (2x lpm, quad, interp):   57 cy
  0xbc call __usmulhisi3 (interp (a1-a0)*frac)    :   31 cy
  0xc0-0xdc sign/mirror fixups                    :   20 cy
  0xde call __mulhisi3   (16x16 amp*sin_q15)      :   31 cy
  0xe2-0xee SOFTWARE >>15 loop (15 iters x 7 cy)  :  104 cy   <-- ((amp*sin)>>15)
  0xf0-0xfe accumulate + loop tail                :   10 cy
  ------------------------------------------------------
  PER HARMONIC                                    :  340 cy = 17.00 us @20MHz
  prologue+epilogue (18 push/pop pairs)           :   84 cy =  4.20 us
  N_HARM=3:  1104 cy =  55.20 us
  N_HARM=5:  1784 cy =  89.20 us   (spec 5.1 says 15 us for N_HARM=5)

  HARD LOWER BOUND using ONLY the two compiler-emitted shift loops and the three
  libgcc multiply calls (no inline code counted at all):
    240 cy/harmonic -> N_HARM=5: 1200 cy = 60.0 us
```

**Measured ≈ 89 µs, spec says 15 µs. Even the hard lower bound — counting only the two
compiler-emitted shift loops and the three libgcc multiply calls, ignoring all 152 inline
instructions — is 60 µs, 4× the estimate.**

The two costs the estimate misses are that avr-gcc emits **software shift loops** for
`arg >> 5` (34 cy) and `(amp*sin) >> 15` (104 cy) on 32-bit operands — 138 cycles per harmonic,
6.9 µs, from shifts alone — and that every multiply is an out-of-line libgcc call.

### Method validation against the spec's own baseline

My cycle model is calibrated against a figure the spec itself asserts. Compiling the
`sscRead16` bit-bang for the same target (`verify/ssc_avr.c`):

```
00000032 <sscRead16>:   loop body = add,adc,sbi,cbi,in,bst,eor,bld,ldi,or,or,subi,brne = 14 cy
                        x 16 iterations = 224 cy = 11.2 us
```

Plus a constant-folded `sscWrite16` (~48 cy) and CS overhead gives **≈ 14 µs** for a 32-clock
read, against the spec's stated baseline of **≈ 16 µs**. The model agrees with the spec where
the spec is right, which is why I trust it where the spec is wrong.

Same measurement also gives the safety-word cost: another 16-clock `sscRead16` = 224 cy =
**11.2 µs**, against §5.1's "≈ +8 µs" — **MINOR**, ~40 % low.

### Consequence

§5.1's read-step table should read approximately:

| Step | spec | measured/derived |
|---|---|---|
| 16 extra SSC clocks | +8 µs | **+11 µs** |
| CRC-8 + STAT/safety decode | +5 µs | not measured (plausible) |
| 5-harmonic compensation | +15 µs | **+89 µs** |
| total read step | **≈45 µs** | **≈118 µs** |

The **conclusion still holds** — 118 µs fits comfortably in the per-module slack (below) — but
the number in the table is wrong by 2.6× and the compensation line by 6×, and it is the number
a reader would use to argue the ≤5 µs/hop target in §5.2 is safe.

## E.3 MAJOR — the "≥500 µs idle window" conflates two different periods

§5.1: *"Added work in the read step, executed **while downstream modules are still
transmitting** and with **≥ 500 µs before the next trigger**."*

These two clauses describe different intervals and cannot both characterise the same window.

Per-module timeline, `main.cpp:317-371` (reply from cache, *then* read):

| | module 1 | module 8 | module 16 |
|---|---|---|---|
| own trigger arrives | t ≈ 20 µs | t ≈ 230 µs | t ≈ 470 µs |
| replies (20 µs, `Serial.flush()` blocks) | 20→40 | 230→250 | 470→490 |
| read step runs | 40→158 | 250→368 | 490→608 |
| bus busy during that read? | **yes**, modules 2–16 | **yes**, modules 9–16 | **no** |
| own next trigger | t = 1020 µs | t = 1230 µs | t = 1470 µs |
| true per-module slack | ≈ 862 µs | ≈ 862 µs | ≈ 862 µs |

```
per-module slack/cascade = 1000-(20 reply + 45 read) = 935 us   [with the spec's 45 us]
                                                     = 862 us   [with the measured 118 us]
```

Findings:

1. **The ≥500 µs number is true but for the wrong reason, and only under one reading.** Each
   module is triggered exactly once per 1 ms and does ~118 µs of work per trigger, so its real
   slack is ~862 µs — far more than 500. Nothing in the chain position changes that.
2. **The read step is NOT executed in an idle window for modules 1–15.** It runs *during* the
   busiest part of the cascade, with up to 15 downstream replies (60 bytes) arriving on the
   UART. That is exactly the condition §2.7's third open question is about — *"Reading the
   safety word extends the CS-low window from 32 to 48 SSC clocks while UART RX interrupts are
   active."* §5.1's "≥500 µs" phrasing makes that window sound quiet when it is the loudest
   moment on the bus, and the measured 118 µs read step means the exposure is 2.6× longer than
   the spec's own risk assessment assumes. Module 1 is the worst case and module 16 the best —
   the opposite of what "idle window" suggests.
3. **Under the other reading, §5.1 and §5.2 contradict each other.** If "next trigger" means
   the next M5 cascade start (t = 1000 µs), then at §5.2's own design target of a 560 µs chain
   the last module finishes at 560 µs and has **440 µs**, not ≥500 µs:
   ```
   end of a 560 us cascade -> next M5 trigger = 440 us  <-- BELOW the claimed 500 us
   ```

## E.4 MINOR — the 480 µs cascade figure omits the M5's own trigger frame

```
16 x (20+10)            = 480 us   (spec's figure)
incl. M5 trigger frame  = 20 + 16*(10+20) = 500 us
```

§1.3 correctly describes the M5 emitting one frame per millisecond and the encoders replying,
so the cascade is 17 frames and 16 turnarounds, not 16 of each. 4 % understatement; it does not
change any conclusion, and the 10 µs turnaround is itself an unmeasured assumption
(correctly deferred to §5.3 item 1).

## E.5 Unverifiable by construction

The 10 µs per-hop turnaround and the 5 µs CRC-8/STAT-decode line are estimates with no backing
artifact. §5.3 correctly schedules all of this for a logic analyser. I flag them as
**unverified**, not as wrong.

---

# F. USERROW layout (§4)

## F.1 Byte/word accounting — verified EXACT

```
16 words x 2 bytes = 32 bytes; every byte 0x00-0x1F covered exactly once? YES
CRC input 0x00-0x1D = 30 bytes = words 0..14; CRC field at 0x1E-0x1F, self-excluded: YES
CAL_DATE: year[6:0]=7b month[10:7]=4b day[15:11]=5b -> 7+4+5=16 exactly, no gap/overlap
ranges: year-2000 0..127 OK; month 1..12 in 0..15 OK; day 1..31 in 0..31 OK (exactly full)
```

No overlap, no gap, no field too narrow for its declared range. The CRC domain is exactly
bytes 0x00–0x1D as claimed, and the CRC word is correctly excluded from its own input.

`N_HARM` gets 8 bits for a 0–5 range and `DEVICE_ID` 8 bits for a 1–31 range — both
over-provisioned, which is harmless.

## F.2 Unit claims — verified

```
21-bit LSB            = 0.000171661 deg  (spec 0.000172)   OK
int16 amp span        = -5.62500 .. +5.62483 deg  (spec +/-5.63)  OK
ratio 15b/21b LSB     = 64.0000  (spec "64x finer")        OK
15-bit LSB            = 0.010986 deg  (spec 0.0110)        OK
```

Phase resolution (`65536 = 360°`) contributes `A_k × 2π/65536`; at the largest realistic
`A_1 = 8738 LSB` that is 0.84 LSB = 0.00014° — 40× below the quantisation floor. Adequate,
and the spec does not overclaim it.

## F.3 MAJOR — §4.1's validation list has no `device_id` range check

§4.1:
```
magic ok AND layout_ver supported AND n_harm <= 5 AND crc16 ok
    -> device_id from USERROW, compensation enabled
```

`n_harm` is range-checked; **`device_id` is not**. §3.9 explicitly rejects `SET_ID` with
`ARG = 0` (*"because ID 0 is the master and reply address"*), and §1.3 states *"No encoder may
be provisioned with ID 0"* — but a page that is byte-corrupt in word 1 yet CRC-valid (a mis-burn
at the station, or a page written by an older/buggier tool) will be accepted with
`device_id = 0` or `device_id > 31`.

Consequences are concrete, from `main.cpp`:
- `device_id == 0` → `r_id == device_id` matches the M5's own `ID=0, CMD=2` trigger frames.
- `device_id > 31` → `makePacket21` masks `ID &= 0x1F` (main.cpp:120) so the module replies
  under an aliased identity, while `prev_id = (device_id - 1) & 0x1F` (main.cpp:336) uses the
  unmasked value — the module can answer for one ID and be addressed as another.

The check the spec already applies to `n_harm` should apply to `device_id`.

## F.4 Verified — virgin-part behaviour

```
CRC-16/CCITT-FALSE(30 x 0xFF) = 0x5FBD; virgin word15=0xFFFF -> CRC alone would FAIL
```

A virgin page fails both the magic check and (independently) the CRC. §4.1's claim that it
"degrades exactly to upstream behaviour" holds with two layers of protection, not one.
`CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF)` is correctly named for the parameters given.

`SYSCFG0 = 0xC4` was confirmed in `encoder/platformio.ini`; bit 0 (EESAVE) = 0, so EEPROM
*is* erased on upload — the stated reason for preferring USERROW is correct. I did not verify
against a datasheet that USERROW lives at 0x1300, is 32 bytes, or survives a UPDI chip erase;
those are datasheet facts outside what I can reproduce here.

---

# G. Resource budget (§7)

## G.1 Baseline — reproduces byte-for-byte

```
$ cd /home/dev/workspace/openarm_ker_firmware/encoder && /home/dev/workspace/.piovenv/bin/pio run
PLATFORM: Atmel megaAVR (1.10.0) > ATtiny1616
HARDWARE: ATTINY1616 20MHz, 2KB RAM, 16KB Flash
PACKAGES: framework-arduino-megaavr-megatinycore @ 2.6.11, toolchain-atmelavr @ 7.3.0
RAM:   [=         ]   8.7% (used 179 bytes from 2048 bytes)
Flash: [==        ]  15.7% (used 2578 bytes from 16384 bytes)
========================= [SUCCESS] Took 0.22 seconds =========================
```

RAM 179/2048 (8.7 %), Flash 2578/16384 (15.7 %) — **exact match**. Headroom 13806 flash /
1869 RAM — **exact**. `build_flags = -DDEVICE_ID=3` confirmed in `encoder/platformio.ini`;
PlatformIO reports 6.1.19 rather than the spec's "6.2.0", which is immaterial to the sizes.

## G.2 The ~2.5 KB / ~100 B addition estimate — plausible, slightly optimistic on flash

I have one hard datapoint: the compensation routine alone, compiled for this exact target at
-O2, is **310 bytes of text** plus 130 bytes of table, plus the three libgcc multiply helpers
(~80 bytes, likely already linked) = **≈ 440–520 bytes** for `ker_comp.c` alone.

Extrapolating the rest against §8's file list:

| Item | Estimate |
|---|---|
| `ker_comp.c` + sine table | **440 B (measured 310 + 130)** |
| CRC-16 bitwise (`0x1021`) | ~50 B |
| CRC-8 bitwise (`0x1D`) | ~50 B |
| NVMCTRL USERROW erase/program/verify | ~150–250 B |
| `ker_cmd3.c` — 32-entry dispatch, idle gate, factory mode, staging | ~700–1000 B |
| `ker_sensor.c` — config writes, CRCPAR recompute, safety/STAT decode | ~300–500 B |
| `ker_health.c` — flags + 8 saturating counters | ~150–250 B |
| **total** | **≈ 1.9–2.6 KB** |

**~2.5 KB is a reasonable and mildly conservative estimate**, and against 13806 bytes of
headroom the conclusion ("Constraint 6 is comfortable") is safe by ~5×. Two caveats: the
32-subcommand dispatch is the item most likely to be underestimated, and the estimate assumes
no floating point is pulled in anywhere (constraint 3) — a single stray `float` in the
diagnostic path would add ~1–2 KB of avr-gcc soft-float.

**RAM ~100 B** is arithmetically consistent: 32 B staging + 20 B live coefficients
(5 × (int16 amp + uint16 phase) — exactly the "20 bytes" the spec states, confirming it is
sized for five harmonics) + 8 × uint16 counters (16 B) + health word (2 B) + `t_last_chain`
(4 B) + 4 latched angle words (8 B) + factory-mode state (~4 B) ≈ **86 B**, leaving little
room for stack growth in the CMD=3 dispatch but comfortably inside 1869 B of headroom.

---

# FINDINGS, RANKED

## BLOCKER (a headline number is wrong)

**B1. §5.1 — "5-harmonic fixed-point compensation ≈ 15 µs" is ~6× low; measured 89 µs.**
Evidence: §E.2. avr-gcc 7.3.0 -O2 for attiny1616 emits 340 cycles/harmonic (17.0 µs at 20 MHz);
5 harmonics + prologue = 1784 cycles = **89.2 µs**. Hard lower bound counting only the two
compiler-emitted shift loops and three libgcc calls: 60 µs. The read-step total is **≈118 µs**,
not 45 µs. Method validated against the spec's own 16 µs SSC baseline (I get 14 µs).
The *conclusion* (it fits) survives; the *number* does not, and it is the number the ≤5 µs/hop
argument in §5.2 leans on.

**B2. §6.4 / §6.1 — the 0.00146° / "3.4× margin" figure does not hold at the specified N_HARM=5.**
Evidence: §A.2. The prototype implements 3 harmonics (`comp.c:37`). Extended to 5 and
hill-climbed over legal int16/uint16 coefficients, the worst case is **0.004864°** against a
0.005° budget — margin **1.03×**. §6.4 flags the re-run as pending; §6.1's budget table and
§6.4's "3.4× margin" headline do not.

**B3. §6.3 — "Six buys nothing" is contradicted by the spec's own table.**
Evidence: §C.2. `worst` row: H1–5 = **0.01424°**, H1–6 = **0.00192°**, floor = 0.0055°. Five
harmonics leaves the worst part 2.6× *above* the floor the spec says to size against; six takes
it 7.4× below. Simulation (§C.4) shows the same for any sensor with an intrinsic harmonic above
the 3rd, and quantisation (§C.5) widens the gap further.

## MAJOR (causes significant rework)

**M1. §6.2 — "Consistently 2.4–2.7× better" is a four-case cherry-pick.** §B.2. Over 300 random
phase/ratio draws the factor spans 0.96×–22.5×, median 1.64×; only **5.7 %** fall in the quoted
band. The direction of D2 survives; the quantification does not.

**M2. §6.2 — Approach A is a strawman and the real trade-off is unstated.** §B.3. A true-domain
fit with 3 fixed-point inversion iterations reaches 0.000052°/0.000955°, i.e. **65×–735× better**
than the measured-domain fit the spec selects. Measured-domain wins on *runtime*, not accuracy;
its residual is precisely what forces the harmonic count to five. §6.2 argues the decision on
the wrong axis.

**M3. §6.3 — the simulation measures only the inversion artifact.** §C.3/§C.4. `nharm.py:30`
hard-codes a 3-harmonic intrinsic error. An intrinsic H5 of 0.08° (0.5 % of H1) already puts
H1–5 at 0.00894°, above the floor; an intrinsic H6 of 0.05° puts it at 0.05315°. O1 is
therefore a **layout-freezing** risk, not the station-configuration detail §9.2 describes.

**M4. §6.3 numbers are unquantised best cases.** §C.5. With θ_measured quantised to 15 bits
before fitting, the "large" part's H1–5 residual goes 0.00349° → **0.00960°**, and six
harmonics measurably helps (0.00703°).

**M5. §6.1's budget table quotes the H1–3 residual for a 5-harmonic design.** §C.6.
"0.0013 – 0.062°" is the min/max of §6.3's **H1–3** column; the H1–5 range is 0.00007–0.01424°.

**M6. §6.2 formula and the reference implementation disagree on sign.** §A.6. Spec:
`u_out = u_in + Σ A_k sin(...)`. `comp.c:42`: `u - delta`. The double reference carries the same
sign, so the accuracy sweep cannot catch it. The calibration station and the firmware will be
written from these two documents.

**M7. §5.1's "≥500 µs idle window" conflates two periods and understates a risk §2.7 already
flags.** §E.3. The read step runs during the *busiest* part of the cascade for modules 1–15
(up to 60 bytes of downstream traffic arriving on the UART during a 48-clock CS-low window),
and is quiet only for module 16. Real per-module slack is ~862 µs, not 500. Under the other
reading of "next trigger", §5.2's own 560 µs design target leaves **440 µs**, below the claimed
500.

**M8. §4.1 omits a `device_id` range check.** §F.3. `n_harm` is validated, `device_id` is not,
despite §1.3 ("No encoder may be provisioned with ID 0") and §3.9 (SET_ID rejects ARG=0).
`device_id == 0` matches the M5's own trigger frames; `device_id > 31` is masked in
`makePacket21` (main.cpp:120) but not in `prev_id` (main.cpp:336).

## MINOR

**m1. §1.5 — "64.0000305" is wrong.** §D. Actual slope `64 + 1/512 = 64.001953`; full-scale
ratio 64.0019227. Looks like `1.0000305` with the 64 spliced in wrongly.

**m2. §5.1 — "16 extra SSC clocks ≈ +8 µs".** §E.2. A 16-clock `sscRead16` compiles to
224 cycles = **11.2 µs**.

**m3. §5.2 — the 480 µs cascade omits the M5's own trigger frame.** §E.4. True ≈ 500 µs.

**m4. `sin_q15` reads one element past its 65-entry table.** §A.4. Hit 1442× per sweep, always
with `frac == 0`, so the value never affects a result. Benign, but undefined behaviour.

**m5. §6.4's sweep domain (32768 reachable codes) is correct but the number is domain-specific.**
§A.5. A full 2²¹ sweep is 13 % worse.

**m6. §7 cites PlatformIO 6.2.0; the installed toolchain reports 6.1.19.** Immaterial to the
sizes, which match exactly.

## Checked and found clean (explicitly not findings)

- **No integer overflow anywhere in the 5-harmonic path.** `delta` range measured
  `[-163835, +163835]`; `k*u` max 10 485 755; interpolation and `int16_t` accumulation never
  exceed range (measured `[0, 32767]` pre-negation). §A.3.
- **The `>>15` truncation introduces at most +2.5 LSB (+0.00043°) of DC**, 13× below the
  quantisation floor and absorbed by `mech_joint_offset`. §A.7.
- **The post-hoc `-= np.mean()` in both Python scripts changes nothing** — verified identical
  to 5 dp. §B.4.
- **The least-squares setup in both scripts is correct** — wrapped target, linear sin/cos basis,
  sampling uniform in θ_true matching a rotary stage. §B.5.
- **"No DC term" (D4) is arithmetically justified.** §C.7.
- **USERROW byte accounting is exactly 32 bytes, no gap/overlap, CRC domain exactly 0x00–0x1D.**
  §F.1. A virgin page fails magic *and* CRC independently. §F.4.
- **All of §6.1/§4's unit arithmetic** (0.0110, 0.0055, 0.000172, ±5.63, 64×) is correct. §D/§F.2.
- **The baseline build reproduces byte-for-byte**, as does every cell of §6.2's, §6.3's and
  §6.4's tables. §G.1.

## Unverifiable here (not findings, but not verified either)

- The 10 µs per-hop turnaround and the 5 µs CRC-8/STAT-decode line (§5.1/§5.2) — correctly
  deferred to §5.3.
- ATtiny1616 USERROW address/size/chip-erase survival (§4) — datasheet facts.
- All of §2 (TLE5012B register semantics, CRCPAR block boundary, FSYNC.TEMPR scaling) — outside
  the files in scope; §2.7/O2 already flags the three shakiest items.

---

# APPENDIX — B1 robustness check: the real build uses `-Os`, not `-O2`

The obvious refutation of finding B1 is "you measured `-O2`; the firmware builds at `-Os`".
Checked:

```
$ cd /home/dev/workspace/openarm_ker_firmware/encoder && pio run -t clean && pio run -v \
    | grep -m2 'avr-g++' | tr ' ' '\n' | grep -E '^-O|^-mmcu|^-DF_CPU' | sort -u
-DF_CPU=20000000L
-mmcu=attiny1616
-Os
```

Recompiling the compensation routine at all three levels:

```
-Os : text=304 bytes, 149 instructions, 8 shift ops, 3 libgcc calls
-O2 : text=310 bytes, 152 instructions, 8 shift ops, 3 libgcc calls
-O3 : text=350 bytes, 171 instructions, 12 shift ops, 4 libgcc calls
```

The `-Os` disassembly has the **identical cost structure**:

```
  8a: call __muluhisi3                              (32x32 k*u)
  94: lsr/ror/ror/ror/dec/brne  -> 0x94             SOFTWARE >>5 loop, 32-bit
  f0: call __usmulhisi3                             (interp)
 112: call __mulhisi3                               (amp * sin_q15)
 118: asr/ror/ror/ror/dec/brne  -> 0x118            SOFTWARE >>15 loop, 32-bit
```

Same two software shift loops on 32-bit operands, same three out-of-line libgcc multiply
calls. **The ~340 cycles/harmonic and ~89 µs for N_HARM=5 apply to the build as configured.**
B1 stands.

(What would *not* be refuted but is worth saying plainly: a hand-optimised routine — byte-wise
`>>15`, `fmuls`, a 16-bit accumulator — could plausibly get well under 89 µs. The finding is
that the spec's 15 µs is not what the described implementation costs, not that 15 µs is
unreachable in principle.)
