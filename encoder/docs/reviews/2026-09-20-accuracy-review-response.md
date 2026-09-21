# Response to the accuracy reviews of spec v5

Reviews (2026-09-20, three independent perspectives on one question — *can the method really control and
improve the sensor's system accuracy?*):

| Review | File | Findings |
|---|---|---|
| sensor physics and transferability | `2026-09-20-accuracy-review-sensor-physics.md` | 2 B / 5 M / 3 m |
| station metrology | `2026-09-20-accuracy-review-station-metrology.md` | 2 B / 6 M / 3 m |
| system error budget and lifecycle control | `2026-09-20-accuracy-review-system-budget.md` | 1 B / 7 M / 4 m |

Merged reading and plan: `2026-09-20-accuracy-review-synthesis.md` (Chinese). Resolved in
`../protocol-spec.md` **v6**; § references are to v6. **No finding required a change to the USERROW layout,
the CMD=3 subcommand set, the wire format or the M5, and none was made.**

Status: **fixed** (spec, procedure or reference code changed), **accepted** (stated, not removable by this
design), **bench** (needs a measurement; listed in O1/O2/O3/O6), **declined**, **decided** (user, 2026-09-20).

User decisions of 2026-09-20: the bare unit turns a full 360°; graded acceptance A / B / rework (D25);
FIR_MD 2 with prediction off, re-confirmed after the E1000 correction (D16); revise to v6 now with the bench
work in parallel. Hardware facts from the user: magnet Ø3 × 3 mm diametric (was Ø3 × 2.5), pocket deepened,
gap to the chip unchanged, grade unknown.

## Sensor physics

| # | Finding | Status | Resolution |
|---|---|---|---|
| P1 | Low field of the Ø3 mm magnet: stray fields give a pose-dependent 0.05–0.3° no static fit removes | accepted + bench | Stated in §2.8 and §7.8; the claim is restated (D26). Station placed away from steel and the stepper, orientation recorded (§7.7). 180°-yaw and cross-talk tests in O1 and §9.6. Raising B₀ is hardware: O6. |
| P2 | Accuracy verified at the station only; nothing on the arm | fixed (procedure) | §9.6 multi-pose, cross-talk and return-to-jig checks through the normal stream; §9.7 service read-out. The multi-pose figure, not 0.02°, is declared the product's accuracy (§9.6, §7.8). |
| P3 | Unit under calibration undefined | fixed | §7.2 "What is calibrated", D23: assembled sealed unit, own magnet, paint marks, disassembly voids. Full 360° confirmed by the user. Station record fields in §9.7. |
| P4 | 3–12 µm stability from one bearing and a printed spacer | accepted + bench | §2.8; centring gate on H2 (§7.2 step 9, provisional limit); load test in O1. Hardware options not pursued here. |
| P5 | One approach direction on a hysteretic sensor | fixed | Two directions, pooled fit of the mean curve, hysteresis half-difference recorded and limited (§7.2, D24); reference implementation and operating characteristic re-done with a hysteresis loop. `HYST_MAX` provisional until the CW/CCW bench run (O1). |
| P6 | B₀ probably ≤ 30 mT; window 0.7 mm | bench | §2.8, O6. Hall-probe measurement first; then gap or grade. |
| P7 | Temperature, self-heating, supply: unquantified | fixed (procedure) + bench | Warm-up step and recorded VDD (§7.2 step 1); characterisation in O1. No temperature-dependent coefficients (would need LAYOUT_VER 2). |
| P8 | Data sheet facts wrong for the E1000 | fixed | §2.4 (E1000 defaults; what the fork changes and why), §2.7 (field condition, Rev. 2.1 figures), O1 premise, D16 reworded; revision reconciliation and chip marking in O2. |
| P9 | `D_MAG` is not a field or gap monitor | fixed | §2.8. The system review's proposal to use it as an air-gap sentinel (S7) is **not** adopted for that reason. |
| P10 | §7.7's reason for not turning the module was wrong | fixed | §7.7 rewritten; `station-reference-encoder.md` §5 now gives the real reason (ambient-field direction), and uses horn-side re-clocking deliberately. |

## Station metrology

| # | Finding | Status | Resolution |
|---|---|---|---|
| F1 | Coupling transfer error invisible to encoder-side remounting | fixed | Stage-side remounting of reference + C1 as one body (§7.7, D27). Reproduced: v5 procedure 52.5″ with the check reading 1.2″; v6, couplings only, 6.4″ (`ref_selfcal.py`). |
| F2 | Step 5 has no statistic, a noise floor above its claim, blind spots; nothing independent | fixed / accepted | Two defined criteria (8″ reproducibility, 12″ check mounting at the turning point of set A), justified by pass rates per fault level and by the worst error of any passing station — ≈ 24″, ≈ 15″ in H1–H6, given an encoder-grade C2 and a sub-divisional error ≤ 8″ (§7.7, revised after the v6 verification, V1/V5); mountings at 22.5° and 11.25° open H8/H16. Non-traceability is **accepted and stated**: "relative to the station reference" until a check standard and one independent comparison exist (§7.7, §7.8, O3). |
| F3 | "As delivered 0.034°" unfounded; gate blind to low-order reference error; no incoming test; no guard band for U(θ_true) | fixed | Figures replaced by the review's budget (§7.7, §7.8, reference note §4); incoming test in §7.7 and the reference note §3; the statement that the gate cannot see reference error is in §7.2 and §7.7. ISO 14253 guard-banding **declined** in favour of stating `R_MAX` relative to the reference — with U ≈ 14–18″ it would cost even more yield for a figure the system cannot resolve (S9). |
| F4 | Per-clamp error; production mounting undefined; hollow-shaft reference | fixed | Executable order stated: the check mounting sits at the turning point of set A, the last set-A clamping is the production mounting and is never touched, set B runs on it; its own deviation is *mostly* (≈ 70 %, per the v6 verification) absorbed by the S2 term; reproducibility criterion; solid-shaft requirement (§7.7). |
| F5 | Transfer artefact drifts | fixed / accepted | Warm-up, ± 2 `TEMPR` counts, out-and-back sequence (§7.7). Out-and-back equalises drift within a set but not between set A and set B (re-verification W1), so drift still costs accuracy: H1–H6 error 4.7″ at 1 %, 15.1″ at 5 %. Simulated: at 10 % drift 3.3 % of stations still pass both criteria, with a worst `θ_true` error of ≈ 24″. A one-column refinement of the fit that removes the effect is noted in §7.7 for `kercal`. |
| F6 | Favourable spectrum; SDE and H8/H16 irreducible | fixed / accepted | Extra mountings; fine scan in the incoming test. The simulation now has reference content to H40 and an 8″ SDE that is actually sampled (stage scatter; the first v6 draft's SDE was inert — v6 verification V2): it raises the good station from 7.9″ to 13.6″, almost all of it above H6. Stated that only H1–H6 of any reference error can enter a module, and reported separately (4.7″ / 9.5″). |
| F7 | Dynamics and read timing | fixed | Bracketed polling with a stationarity criterion (standard deviation ≤ twice the static noise of the incoming test; first- and second-half means within 3″), hold-current note (§7.7); noise check over re-approaches including the reference (§7.2 step 2). |
| F8 | Errors common to both passes end up in the module | accepted + bench | As P1/P5/P7; station siting and orientation (§7.7); yaw test (O1). |
| F9 | Wind-up; coupling type | fixed | Stiffness ≥ 150 N·m/rad; helical-beam couplings forbidden (§7.7). |
| F10 | Topology unspecified | fixed | §7.7 topology, including the **second coupling** that neither review budgeted: the unit has its own bearing. Horn-side remounting (set B) separates its repeatable part; its unit-to-unit part is a budget line (good station 14.0″ / 17.9″ with a diaphragm, 23.4″ / 40.2″ with a bellows; H1–H6 part 4.7″ / 9.5″ against 14.7″ / 31.0″). |
| F11 | Resolution is not accuracy | fixed | Register width, latching, baud rate in the incoming test. |

## System budget

| # | Finding | Status | Resolution |
|---|---|---|---|
| S1 | In-use accuracy unverifiable; loss of calibration invisible | fixed (procedure) / open | §9.5 frozen-channel detector and `seq` check; §9.6 return-to-jig; §9.7 service read-out. Tripping the M5's jump detector on persistent faults would reverse D18: **not adopted**, recorded as O5 for the user. |
| S2 | What is calibrated is unspecified | fixed | As P3. |
| S3 | Compensated output makes the M5's float32 unwrap drift | fixed | Output rounded to a multiple of 8 LSB (§7.1, D22) in `ref_comp.c`; all dependent evidence regenerated: worst arithmetic error 0.003186° (ceiling 0.003206°, budget 0.005°), 1099 cycles, 662 B, AVR = host on 21/21 sets, mutants A and B still caught. Confirmed independently by the author with the real routine and other coefficients (`author_s3_check.py`): upstream 0, v6 exactly 0, negative control mutant C (rounding to 1 LSB, as v5) +0.004…+0.013°/h. The review's 0.148°/h grid maximum was not reproduced by the author; the mechanism and the fix were. New verification item §11.2-7 and bench item §8.4-11. |
| S4 | Zero is one noisy reading | fixed (host) | Zero trim, §9.5. |
| S5 | Noise unfiltered end to end | fixed (host) + record | Filter recommendation §9.5; per-reading σ recorded per unit (§7.2 step 2, §9.7). Module-side oversampling **declined** for now (reply-latency risk; §8 untouched). |
| S6 | ≈ 1.8 ms data age not described by the timestamp | fixed (documented) + bench | §8.5 model; §8.4 item 10; host time alignment §9.5. Late-read option declined. |
| S7 | No lifecycle control | fixed (procedure) | §9.7 records, service check, re-calibration triggers. The `D_MAG` sentinel is dropped (P9); H1/H2, σ and return-to-jig take its place. |
| S8 | Reject → identity page is the worst outcome | decided | Graded acceptance, D25; rejected units are reworked or scrapped, never shipped with an identity page. Grade in the database, not on the module. |
| S9 | 0.02° is below the knee; §7.7 buys < 1 % at system level | accepted / partly declined | §7.8 says so. 0.02° stays as the grade-A process gate — it costs a minute and monitors assembly quality. §7.7 is kept, but as a **one-time commissioning**, not a per-unit step: it is the only thing that catches a badly out-of-rating reference. |
| S10 | Sampling skew | fixed (documented) | §8.5; covered by time alignment. |
| S11 | No frame check | accepted | Out of scope by the brief; host outlier rejection recommended (§9.5). |
| S12 | Traceability depends on one database | fixed (procedure) | Per-arm export (§9.7). |

## Conflicts between the reviews, and one gap

1. `D_MAG`: S7 wanted it as an air-gap sentinel; P9 shows it cannot be one. P9 stands.
2. Value of §7.7: S9 (negligible at system level) against F1–F6 (needed for an honest station figure). Kept
   as one-time commissioning.
3. Gap found when merging: the second coupling between stage shaft and horn (F10 row above).

## What was not verified by the author

The E1000 marking and BOM (from OpenArm's drive), the CAD-derived gap, the TLE5014 hysteresis figures as a
proxy, the Rev. 2.1 data sheet numbers, and the HEIDENHAIN coupling figures (consistent with the author's
memory, PDF not re-read). All nine review scripts were re-run and reproduce their recorded output.

## Still to do before this response can be called closed

The v6 verification (`2026-09-20-spec-v6-verification.md`, REVISE narrow) is answered in
`2026-09-20-spec-v6-verification-response.md`. Remaining: the bench items of O1, O2, O3 and O6.
