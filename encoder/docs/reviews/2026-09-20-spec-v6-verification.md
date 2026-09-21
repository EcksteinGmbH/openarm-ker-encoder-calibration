# Spec v6 verification — the v5 → v6 changes only

| | |
|---|---|
| Subject | `encoder/docs/protocol-spec.md` v6, `evidence/v3-reference/` as regenerated for v6, `reviews/2026-09-20-accuracy-review-response.md` |
| Verifier | independent agent, 2026-09-20; did not write any of the above |
| Method | read the v5→v6 diff and the affected v6 sections; re-ran every cheap evidence command in a `mktemp` directory; wrote four new attack scripts |
| Rules kept | no existing file edited, nothing committed. New files only here and in `evidence/v6-verification-scripts/` (+ `results/`). A `__pycache__` that my Python imports created in `v3-reference/` was removed again |

## 1. Verdict

**REVISE (narrow): 0 blocker, 2 major, 6 minor.** Everything that the firmware and the protocol depend on is
verified and can go ahead: §3 and §5 are byte-identical to v5, §4 differs in one explanatory note, no v6 text needs a
subcommand, record field or USERROW word that does not exist, and the M5 is untouched. The one arithmetic change
(D22, output rounded to a multiple of 8 LSB) is correct in `ref_comp.c` for negative corrections, at the seam and on a
16-bit-`int` AVR, the uncalibrated path is still bit-exact upstream (its golden hash is unchanged from v5), and the
float32 argument holds: I get exactly zero accumulation error on an 81-cell sensor × joint grid with five coefficient
sets, moving joints, the 0/360 seam and the `_invert` path, while steps of 1, 2 and 4 LSB all drift. Every v6 number in
§7.1, §7.2, §7.5, §7.7, §8.3, §10 and §11.2 matches its results file, and every results file I re-ran reproduces bit for
bit — with one exception (V3). The two-direction graded gate survived a new attack (error in H7–H16 clustered at both
limits, part-specific hysteresis shape, correlated noise): no false A, no false ship in 1600 parts. The two majors are
both in the new §7.7 commissioning simulation and procedure, not in the firmware: the check mounting cannot be taken
where the simulation takes it without destroying the production mounting the text says is never touched again (V1), and
the "sub-divisional error 8″" that six table rows and the response to F6 rely on is numerically inert in
`ref_selfcal.py` (V2). Both are an hour's work to fix and only `ref_selfcal.py`, §7.7 and the reference note need
re-checking afterwards.

## 2. Findings

| ID | Severity | Title |
|---|---|---|
| V1 | MAJOR | §7.7: the 100° check mounting and "the last set-A mounting is the production mounting and is not touched again" cannot both hold in the simulated order; executed literally, the error doubles and both criteria still pass |
| V2 | MAJOR | `ref_selfcal.py`: the sub-divisional-error term is inert (aliased to a per-turn constant), and the simulated reference has no content outside the fitted model; rows 3–8 and the F6 response overclaim |
| V3 | MINOR | `author_s3_check.txt` does not reproduce from its documented command; the script has lost its negative control; `regen_results.sh` would silently erase it; §11.2 item 7 is worded too strongly |
| V4 | MINOR | §7.4 item 2 still specifies "one rounded `>> 7` at the end" — stale v5, contradicts §7.1 and `ref_comp.c` |
| V5 | MINOR | "The production mounting's own deviation is absorbed by the S2 term" is ≈ 72 % true; "limits set between good and faulty stations" is true of the reproducibility limit, not of the check limit |
| V6 | MINOR | Suspended compensation (§6.2) leaves the multiple-of-8 grid: harmless per episode (≤ 3 × 10⁻⁵°), but not stated, not in §11.2 item 7, and continuous flapping does accumulate |
| V7 | MINOR | Small inconsistencies (nine items): table break, `station_fit.py` docstrings and missing step 9, §9.7 service list, ± 0.5 K vs sensor resolution, 3″ spread vs assumed noise, two explanatory sentences, Appendix A path, two P3 items |

## 3. Findings in detail

### V1 — MAJOR — The check mounting and the production mounting exclude each other as simulated

**Where.** Spec §7.7, bullets "Set A" ("The last mounting is the **production mounting** and is not touched again") and
"Criteria" ("one further set-A mounting at 100°, **not used in the fit**"); `station-reference-encoder.md` §5 steps 2 and
5; `ref_selfcal.py:161-173`.

**What is wrong.** A set-A mounting means unclamping reference + C1 from the stage hub. The spec gives no position for the
check mounting in the sequence. The simulation takes it **after set B** with the artefact's full drift
(`mscale=1 + drift`, l. 169) and then evaluates production on the **untouched** last set-A clamp (`c_last`, l. 163). That
sequence cannot be executed: after the check the reference sits at 100° and must be re-clamped, so production runs on a
clamping that was never in set B. This is exactly the gap the metrology review named in F4 ("after step 5 the encoder
sits at the check angle"). If instead the check is moved before the production mounting, it sees a third of the drift or
less, and the check column of the §7.7 table (9.5″/23.7″ good, 94.3″/217.7″ at 10 % drift) no longer describes it.

**Evidence.** `evidence/v6-verification-scripts/selfcal_criteria_oc.py 300` (uses `ref_selfcal.py` unmodified; `trial()`
re-implemented with a `reclamp` switch) → `results/selfcal_criteria_oc.txt`, arcsec, 300 stations per row:

| Station (C2 diaphragm 6″+3″, drift 1 %, C2 ± 30 % per unit) | `θ_true` error med / max | pass both criteria | worst error among passing |
|---|---|---|---|
| clamp 3″+2″, production on the set-B clamp (as simulated) | 6.9 / 12.5 | 99.7 % | 12.5 |
| clamp 3″+2″, production re-clamped after the check | 9.1 / 16.5 | 100 % | 16.5 |
| clamp 10″+5″, production on the set-B clamp | 8.0 / 14.6 | 96.0 % | 12.4 |
| clamp 10″+5″, production re-clamped after the check | **18.3 / 29.3** | **94.0 %** | **29.3** |

**Fix.** State the order. Either (a) take the check mounting at the turning point of set A (…, 22.5°, 11.25°, **100°**,
11.25°, 22.5°, …, 0° = production, then set B) and re-derive its limit for the smaller drift it then sees; or (b) drop the
separate check mounting and use what the palindrome already contains: the last set-A turn, the first set-B turn and the
last set-B turn are the same configuration (same γ, same δ, same clamp) 1 and 16 turns apart — their residual difference
is the closure test the review asked for in F2(a), and it costs no remount. Re-run `ref_selfcal.py` with the executable
order and update the table and the reference note §5.

### V2 — MAJOR — The simulated sub-divisional error does nothing

**Where.** `ref_selfcal.py:88-90`; spec §7.7 table rows 3–8 ("+ … sub-divisional error 8″"); response row F6 ("8″ SDE in the
simulated cases"); the summary "`θ_true` is good to about ± 10–15″".

**What is wrong.** The term is `sde·sin(2048·enc + φ)` and a turn samples `enc = i·360/256 + offset + γ`. 2048 × 360/256 =
2880° = 8 whole periods, so all 256 positions of a turn see the **same** SDE phase. The term is a per-turn constant,
absorbed by `c_turn` and removed by `half_range()`. A real stepper does not land on exact multiples of 1.40625° (± 3′ is a
large part of the 633″ line period), so on hardware the SDE appears in full as position-to-position scatter of `θ_true`.
In addition `random_reference()` still contains exactly H1–H20 — the fitted model — so apart from the inert SDE the
simulated reference has no unmodelled content at all; F6 ("favourable spectrum") is answered for H8/H16 observability
(the 22.5° and 11.25° mountings, which do work) but not for the spectrum.

**Evidence.** `selfcal_sde_alias.py 60` → `results/selfcal_sde_alias.txt` (spec row 4; `Station.turn` re-implemented only to
add stage scatter):

```
as in ref_selfcal.py: SDE 8, exact 360/256 grid            after med/max   7.9/ 12.6   repro  2.9/ 5.8   check  9.8/23.7
SDE 0, exact grid                                          after med/max   7.9/ 12.6   repro  2.9/ 5.8   check  9.8/23.7
SDE 80 (absurd), exact grid  -> still no effect = inert    after med/max   7.9/ 12.6   repro  2.9/ 5.8   check  9.8/23.7
SDE 8, stage position error 0.03 deg rms                   after med/max  13.9/ 17.6   repro  2.8/ 5.8   check  9.3/23.8
SDE 0, stage position error 0.03 deg rms (control)         after med/max   8.2/ 11.7   repro  2.7/ 5.7   check  9.4/24.1
```

**Consequence.** Bounded: SDE is far above H6, so it cannot enter a module's coefficients (the spec says so); it costs
gate noise (8″ amplitude ≈ 0.0016° rms per position, the same size as the module's averaged noise) and the honest total
for the good station is ≈ ± 14–18″, not ± 10–15″. The two criteria do not see it (as they should not).

**Fix.** Add stage position scatter to `turn()` (one line), give `random_reference()` some content above H20 that is not
a multiple of the sampling grid, regenerate `ref_selfcal.txt`, update the table, the ± figure, the reference note §4/§5
and the F6 row.

### V3 — MINOR — The S3 evidence file is stale and its script has lost its negative control

**Where.** `evidence/v5-accuracy-review-scripts/author_s3_check.py`, `results/author_s3_check.txt` (14:13),
`v3-reference/ref_comp.c` (14:17), `regen_results.sh` last line, spec §11.2 item 7, response row S3.

**What is wrong.** The stored file was produced with the v5 library. With the v6 `ref_comp.c` the documented command
gives zero on the "calibrated" rows too, because `ker_compensate()` now rounds by itself; the script's "q8" branch
re-rounds an already rounded value. So (i) the file does not reproduce, (ii) the numbers the response cites
("calibrated +0.004…+0.013°/h") cannot be regenerated from the repository, (iii) running `regen_results.sh` overwrites
the only record of them, (iv) §11.2 item 7's "It fails for any output that is not a multiple of 8 LSB" has nothing that
demonstrates it. The timestamps show the last line of `regen_results.sh` was never executed.

**Evidence.**
```
$ python ../v5-accuracy-review-scripts/author_s3_check.py $O/libref.so | diff - ../v5-accuracy-review-scripts/results/author_s3_check.txt
< calibrated sensor  20 joint  140  drift after 1 h: +0.00000  +0.00000  +0.00000
> calibrated sensor  20 joint  140  drift after 1 h: +0.01302  +0.01274  +0.00396      (and two more rows)
```
The v6 claim itself is sound: `m5_float32_transitions.py` (new; negative controls computed in double from the
coefficients, independent of the library) → `results/m5_float32_transitions_0.5h.txt`: q8 **0 in 81/81 cells** stationary,
moving ± 60°, and through `_invert`; q1 0.0137°, q2 0.0120°, q4 0.00096° after 0.5 h and growing; upstream ≤ 0.000031°,
not growing (image rounding above 64°, not accumulation).

**Fix.** Give `ref_comp.c` a test-only switch (or keep `ref_comp_v5.c.txt` beside the mutants) so the script builds its own
unrounded control; label the rows "unrounded (v5)", "v6"; regenerate. Reword §11.2 item 7: the v6 output must show
**exactly zero** on a sensor × joint grid including motion and `_invert`; the uncalibrated mapping must show **no growth
and ≤ 1 × 10⁻⁴°** (it is not exactly zero: 13–21 of 81 cells read 1.5–3.1 × 10⁻⁵°); an unrounded build must show non-zero
drift in the sensitive cells (negative control). The author's check covers 3 stationary cells and one coefficient set.

### V4 — MINOR — §7.4 item 2 is stale

`protocol-spec.md:1068-1069`: "Each term accumulates `(A_k · s) >> 8` into an `int32_t` (a byte move); one rounded `>> 7` at
the end." v6 code and §7.1: `((acc + 512) >> 10) * 8`. §7.4 is titled "implementation requirements"; an implementer who
follows it produces exactly the output D22 forbids. Not in the diff, i.e. missed. **Fix:** "one rounding at the end, to a
multiple of 8 LSB: `((acc + 512) >> 10) * 8`; an arithmetic right shift of a negative `int32_t` is relied on (gcc, avr-gcc)
and is covered by the AVR differential (sets 1, 2, 5–7, 9, 11, 13, 15, 19 wrap below 0)".

### V5 — MINOR — Two statements about the commissioning are stronger than the simulation

1. *Response F4: "its own deviation is absorbed by the S2 term because set B runs entirely on it."* Partly. `S2` is
   constrained by set A as well (19 turns on other clamps), so least squares splits the difference. E2 of
   `selfcal_criteria_oc.py` — only the production clamp bad (30″+15″), everything else perfect: H1–H6 of the remaining
   `θ_true` error 9.2″ rss, against 32.7″ when set B runs on fresh clamps (control) and 0.6″ with no clamp error:
   **≈ 72 % absorbed, 28 % remains**, and both criteria pass (repro 7.2″, check 8.0″). At the 3″+2″ the spec assumes
   this is ≈ 1″ and irrelevant; the sentence should say "mostly".
2. *Spec §7.7: "the limits are set between the simulated good and faulty stations."* True of the 8″ reproducibility limit:
   good stations pass 100 % (max 6.1″), clamp fault 30″+15″ passes 0 % (min 13.3″), 10 % drift passes 2.3 % (min 5.4″).
   Not true of the 25″ check limit as a separator: 0.3 % of good stations fail it (max 27.2″ in 300; the table's 23.7″ is
   the max of 100) and **24.7 % of clamp-fault stations pass it**. What does hold, and is the better statement: over all
   ten fault levels I ran (clamp 3…30″, drift 1…10 %), the worst `θ_true` error of any station that passed **both**
   criteria was 16.9″. Quote that, and quote pass rates rather than medians ("caught" in the response F5 row and the
   reference note §5 is 97.7 %, not 100 %).

### V6 — MINOR — Suspended compensation leaves the 8-LSB grid

§6.2 switches a calibrated module to the upstream mapping while the config lock fails; those values are not multiples
of 8, so D22's exactness argument does not cover the transition. It does not matter in practice, but the spec should say
why. `m5_float32_transitions.py`, Q2/Q3, 0.5 h per cell: 5 s suspended in every minute → ≤ 0.000027° (bounded: rounding
to nearest returns to the exact grid when the stream does); a jig offset stored from an uncalibrated reading → ≤ 0.000019°;
**flapping every 16 reads while moving → 0.0060° after 0.5 h and growing** (0.00027° after 72 s) — a fault state in which
the angle already jumps by Σ|A_k| every 16 ms. **Fix:** one sentence in §7.1 or §6.2 ("a suspension episode costs at most
one float32 step, ≈ 3 × 10⁻⁵°; only continuous flapping accumulates, ≈ 0.01°/h, cleared by re-zeroing") and a transition
case in §11.2 item 7.

### V7 — MINOR — Small inconsistencies

1. `protocol-spec.md:26-27`: a blank line detaches the v6 row from the revision-history table; it renders as text.
2. `station_fit.py`: `grade()` docstring and module docstring say "Step 7"; the spec grades in step 8. The demo prints
   "v5 procedure", the spec table says "v4–v6". `noise_check()` documents "averaged angles at one position"; spec step 2
   now feeds it `θ_true − θ_s` over re-approaches. Step 2 does not say the 8 re-approaches come from **one** direction;
   alternating would put the hysteresis into σ_mean.
3. §7.2 calls `station_fit.py` the reference for "the constants, and the computational part of every step"; step 9
   (centring gate, H2 limit 0.2°) has neither a constant nor a function there.
4. §9.7 service check lists `GET_HEALTH`, `GET_CAL_STATUS`, `GET_CFG_VERIFY`, `GET_ERRCNT`, `GET_ENV` and asks to confirm
   "a valid, non-identity page of grade A or B". The grade is only in the database, so the list needs `GET_SERNUM` and
   `GET_RUN_WORD`/`GET_CAL_WORD` (to match the 16 stored words) and should say that "non-identity" is `GET_CAL_STATUS`
   bit 5. All exist; no protocol change.
5. §7.7 "temperature (`GET_ENV`) stays within ± 0.5 K": TEMPR resolves 1/2.776 = 0.36 K per count (§2.6), so this is
   "± 1 count". Say it in counts.
6. §7.7 "the position counts only if their spread is ≤ 3″": `ref_selfcal.py` assumes 1.5″ rms reference noise; the
   expected range of 8 such polls is 4.3″, so a stationary stage would fail most positions. Tie the limit to the static
   noise measured in the incoming test (item 2) or use a trend/σ statistic.
7. §7.2 "taking a maximum over noisy positions biases it upwards by ≈ 0.003°": the file says 0.0670° against 0.0650°
   (+0.002°), maximum over parts 0.0762°. Part of it is not noise: the output-side loop is 2h·(1 + Δ′(θ_s)), up to
   ≈ 15–20 % wider than the sensor-side loop for a 2.5° part. Still the safe direction.
8. §7.1 "when the sensor angle is below 64° and the joint is 128° or more from its zero": that is where the review found
   > 0.01°/h; its grid also shows 0.002–0.007°/h at 64–128° from zero (e.g. sensor 5°, joint 75°: −0.0069°).
9. Appendix A sends `physics_*` output to `…/results/`; `physics_magnet_model.txt` lies beside its script. From P3's
   recommendation, the magnet **lot** and the thread-locker did not make it into §7.2/§9.7 (magnet size did).

## 4. What I re-ran

All builds in `mktemp -d`; commands from `README.md` / `regen_results.sh`. "Reproduced" = `diff` against the stored file is empty.

| Item | Spec | Result |
|---|---|---|
| `diff -u protocol-spec-v5-final.md protocol-spec.md` vs the supplied diff | — | identical |
| `## 3`, `## 5` extracted from v5 and v6, md5 | frozen | equal; `## 4` differs in one line (`GET_PROTO_VER` note) |
| `acc.c` → `accuracy_host.txt` | §7.5 realistic 0.000845° | reproduced |
| `construct.c` → `accuracy_constructed_worst.txt` | §7.5 N = 1…6, 0.003186° | reproduced; all six table values match |
| `worstterm.c \| ceiling.py` | §7.5 ceiling 18.67 LSB = 0.003206° | reproduced; true worst case is bracketed 0.003186–0.003206°, margin ≥ 1.56× |
| `diff_main.c` host vs simavr | §11.2, 21/21 | reproduced; AVR == host, both files equal the stored ones |
| mutants `int16`, `uncal` | §11.2, 20/21 and 1/21, invisible on host | reproduced; both mutant files carry the same rounding line as `ref_comp.c` |
| v5 vs v6 golden hashes | D10 | 20 of 21 changed; set 14 (N = 0) unchanged `9515f5c5` |
| `uncalibrated_equals_upstream.c` | §7.1 | 0 mismatches over 32768 codes |
| `seam_check.c` | §11.2 | reproduced; wraps in both directions with the new rounding |
| `cyc_main.c`, `cyc_worst.c` on simavr | §8.3 1099 cycles; 404/543/682/821/960; +41 | reproduced; 1099 / 20 MHz = 54.95 µs; 48 + 6 + 55 + 5 = 114 µs |
| `flash_cost.c`, attiny1616 | §10 662 B | 900 − 238 = 662, reproduced |
| `station_fit.py` | §7.2 offset table | reproduced; all seven rows match |
| `station_sim.py … 4000 0 0 0.05` | §7.2 OC table | reproduced (full 4000 parts); table rows are correct sums of the file's bins |
| `station_sim.py … 4000 64 0 0.05` | §7.2 "4 parts … 0.0209°, 2 above 0.05°" | reproduced (full 4000 parts) |
| `station_sim.py … 400 0 0 0.05` | — | consistent: 0 false A, 0 false ship |
| drift-0.01 and K = 256 files | §7.2 "within 3 parts", "a third" | read, not re-run: A/B/rework 1103/1708/1189 → 1102/1711/1187; 1356/4000 = 33.9 % |
| `ref_selfcal.py 100`, `OPENBLAS_NUM_THREADS=1`, 70 s | §7.7 table, cond 3.0 | reproduced; all eight rows match |
| `author_s3_check.py` | §7.1, §11.2-7 | **not reproduced** (V3); the v6 rows are zero as claimed |
| new: `m5_float32_transitions.py`, 0.5 h × 81 cells × 18 configurations | D22 | q8 exactly 0 everywhere; q1/q2/q4 drift; transitions bounded (V6) |
| new: `gate_attack_v6.py`, 800 parts × ρ 0 and 0.5 | §7.2 assertion about the v5 attacks | 0 of 622/629 parts above 0.02° graded A; 0 of 225/226 above 0.05° shipped; at ρ 0.8 step 2 answers *insufficient data* for ≈ 80 % |
| new: `selfcal_criteria_oc.py 300`, `selfcal_sde_alias.py 60` | §7.7 criteria | V1, V2, V5 |

`ref_comp.c`, by reading: `512` and `8` promote to `int32_t` on a 16-bit-`int` target; |acc| ≤ 6 × 2²² < 2³¹; `(int32_t)u + delta`
cannot overflow; the mask on a negative two's-complement value gives the correct residue mod 2²¹; rounding the
correction rounds the output because `u` is a multiple of 64. The float32 chain: `raw/2²¹` is exact; `× 360` =
(raw/8) × 45 × 2⁻¹⁵ with (raw/8) × 45 < 2²⁴, exact; `360 − fmod(x, 360)` exact; jig offsets are stored readings
(`main.cpp:238-241`), so on the same grid; every difference and every add is a multiple of 2⁻¹⁵° below 512°, exact.

Frozen-item check for new requirements: §7.2 and §9.7 need `GET_SAMPLE` indices 1, 3–5 (raw mean), 6–7 (Σd², per-reading
σ), 8–11 (output mean), `GET_ENV` 0/1, `GET_DMAG`, `GET_SERNUM`, `GET_CAL_WORD`, `GET_FW_VER` — all in the v5 table. Two
directions are two station passes, nothing on the module. The reference, the check standard and the polling are on the
station's own port. Nothing in v6 asks the M5 for anything.

## 5. Sampled response rows

| Row | Status | Note |
|---|---|---|
| P3 | **resolved** | §7.2 "What is calibrated", D23, §9.7 record fields; 360° confirmed by the user. Magnet lot and thread-locker omitted (V7-9) |
| P5 | **resolved** | two passes, pooled fit, half-difference limited, both directions validated against the mean, §7.8 row; reference code and OC redone and reproduced; my attack found no false grade. `HYST_MAX` is provisional, and says so |
| P8 | **resolved** | §2.4, §2.7 (field condition, Rev. 2.1 figures), §6.2 reference, O1 premise, D16, O2 — all three bullets of the finding |
| F1 | **resolved** (procedure + simulation) | stage-side remount as the review recommended; 50.4″ with check 1.3″ → 4.3″ reproduced. Bench-unconfirmed, as stated |
| F2 | **partly** | criteria now defined, 22.5°/11.25° mountings added and effective, non-traceability stated honestly. But the check mounting has no place in the sequence (V1), its 25″ limit barely separates (V5-2), and the closure turn the review asked for was replaced by the palindrome without using the closure it contains |
| F4 | **partly** | production mounting named, solid shaft required, reproducibility criterion added. "Absorbed by S2" is ≈ 72 % (V5-1); the production mounting is undone by the check as simulated (V1) |
| F7 | **resolved** (text) | bracketed polling, mean, spread limit, hold current, step-2 over re-approaches incl. the reference. The 3″ limit is inconsistent with the simulation's own noise (V7-6) |
| F10 | **resolved** | topology with both couplings; C2's unit-to-unit part is a stated budget line and the table shows the criteria cannot see it |
| S3 | **resolved**, evidence file stale | code, numbers, §11.2-7, §8.4-11 all in place and verified independently; `author_s3_check.txt` does not reproduce (V3); §7.4 still says `>> 7` (V4) |
| S8 | **resolved** | option (b) of the review, D25; assembly/service check in §9.7 (needs two more subcommands named, V7-4) |
| F6 (not in the requested sample) | **asserted only**, for the SDE part | V2 |

No statement attributed to a review was found that the review does not make: the 5 / 18 / 10 finding count, 0.1–0.15° /
0.2–0.4° / "5–10×", 0.025–0.03° and 0.04–0.05°, 0.46–0.91 ms and 1.8 ms, the ≈ 0.05° knee and "< 1 %", 0.10° worst of 14
joints, 0.011° at 25 Hz with ≈ 9 ms, H2 ≈ 5.0°·e², and the 8-LSB recommendation are all in the cited reviews. §2.8 and
§7.8 label estimates as estimates. The only "measured" labels that do not hold are V2 (a simulated term that is not
there) and V3 (a file that is not what its command produces).

## 6. Not verified

- That `protocol-spec-v5-final.md` is the v5 that was approved: the repository has no commits, the copy is the author's.
- `../v3-review-scripts/{construct,worstterm,cyc_worst}.c`: run, not read (outside the permitted reading list).
- `harmonics_v3.py`, `base_mapping.py`: not re-run; they do not call `ker_compensate()` and their outputs are identical to
  the v5 copies. The drift-0.01 and K = 256 station runs: read, not re-run.
- The physics, the metrology of a real station and the system budget — covered by the three reviews. In particular
  whether C2's error really stays with the stage shaft when the horn is re-clocked, whether 30 % unit-to-unit variation
  and 3″+2″ per clamp are realistic, and every §2.8 figure.
- Real hardware: the ESP32's float path is assumed IEEE-754 single, round-to-nearest-even (the exactness argument also
  survives evaluation in double followed by one rounding); §8.4 item 11 is the bench confirmation.
- My E3 quantifies re-clamping after the check; I did not simulate the check moved to the turning point of set A
  (the recommended fix), so its new limit is the author's to derive.
