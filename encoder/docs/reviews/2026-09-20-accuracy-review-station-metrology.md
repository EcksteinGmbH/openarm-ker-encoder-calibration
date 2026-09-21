# Accuracy review — calibration-station metrology: is `θ_true` trustworthy? (spec v5, §7.2 / §7.7)

| | |
|---|---|
| Date | 2026-09-20 |
| Reviewer angle | dimensional / angle metrology, calibration stations, uncertainty budgets; independent of the design |
| Reviewed | `protocol-spec.md` v5 §2.7, §4.10, §7, §11.2, §12; `station-reference-encoder.md`; `evidence/v3-reference/{ref_selfcal,station_fit,station_sim}.py`, `README.md`, `results/ref_selfcal.txt`, `results/station_oc_*.txt`; `reviews/2026-09-19-spec-v5-verification.md` |
| Not reviewed | TLE5012B / magnet physics on the arm, system timing (other reviewers); the gate's statistics under sensor noise (verified 2026-09-19, not repeated) |
| Scripts | `evidence/v5-accuracy-review-scripts/station_*.py`, outputs in `…/results/` (numpy only). Nothing else in the repo was touched. |
| Status | **COMPLETE** |

Units: 1″ = 1/3600° ; `R_MAX` = 0.02° = 72″ ; ±50″ = ±0.0139°. "Half-range" is the spec's statistic (§7.2).

---

## 1. Verdict

**Does the method control and improve accuracy? Relative to the station's `θ_true`, yes — and by a lot (raw 0.6° typ / 1.6° max →
a few hundredths of a degree). In absolute terms it controls only what `θ_true` controls, and `θ_true` as designed is not trustworthy
below roughly ±0.02–0.03°.** The §7.2 gate is blind, by construction, to every error that is the same in the fit and validation
passes; I measured that a low-order `θ_true` error transfers 1 : 1 into the shipped coefficients while the gate statistic does not
move (E2: with a 50″ H1 reference error, 350 of 550 accepted parts are above `R_MAX` against the real angle; with 200″, all of them).
The §7.7 self-calibration is mathematically sound and well conditioned (condition number 1.31; I reproduce 3.0″/4.3″ against the
author's 3.01″/4.55″) — it is the standard multi-position method — **but its 4.55″ is a property of the simulation's assumptions, not
of a station**: (i) the kinematic transfer error of the shaft coupling (±6″ for the best diaphragm coupling, **±40″ for a metal
bellows**, at 0.1 mm / 0.09° misalignment — HEIDENHAIN figures) is tied to the coupling body, is identical at every encoder-side
remount, is therefore booked as "module error", stays in `θ_true` in full, and is invisible to step 5 (E1: err 50.8″, step-5 reading
unchanged); (ii) error that changes with each re-clamping arrives undiminished on the production mounting; (iii) content above H20
(sub-divisional error) and H8/H16 is irreducible and depends on a technology nobody has identified yet; (iv) step 5, the only check,
has no statistic, no threshold, a noise floor of ≈ 20″ (raw) / 6–10″ (harmonic), and is confounded by module drift.

**What the station can honestly certify** — absolute systematic error of an accepted module, *at station conditions* (one
temperature, one approach direction, the station's magnet/mount and magnetic environment), `station_budget.py`:

| Configuration | `θ_true` half-width (rss … linear) | Accepted module, absolute | Status of the claim |
|---|---|---|---|
| A. as bought, no §7.7 (spec: 0.034°) | 65″ … 112″ (0.018–0.031°) | **≈ 0.04–0.05°** | only if the reference meets an unverified rating; unbounded otherwise |
| B. §7.7 as written (spec: 0.0215°) | 44″ … 85″ (0.012–0.024°) | **≈ 0.03–0.045°** | dominated by the coupling, which §7.7 cannot see |
| C. with the station-only changes of §3 below | 13″ … 33″ (0.004–0.009°) | **≈ 0.025–0.03°** | self-consistent; **not traceable** until one independent check exists (F2) |

Off-station effects (temperature, reversal hysteresis, different magnet/mount, ambient field) are outside these figures and, by my
estimate for the ambient field alone (F8), can exceed all of them. None of my recommendations touches the 32-byte layout, the
protocol, or the M5.

---

## 2. Findings

| ID | Severity | Title |
|---|---|---|
| F1 | **BLOCKER** | Coupling transfer error is missing from the model, the budget and the simulation; encoder-side remounting can neither remove nor detect it (±6…±40″ and more) |
| F2 | **BLOCKER** | Step 5 cannot verify the claim: no statistic or threshold, 20″ / 6–10″ noise floor, blind to F1 and H16, false alarms from module drift; no non-self-referential check exists anywhere |
| F3 | MAJOR | "As delivered ≈ 0.034°" rests on an unverified rating and omits the coupling; the gate gives no protection (1 : 1 transfer); no incoming acceptance test is specified; `R_ACCEPT` has no guard band for `U(θ_true)` |
| F4 | MAJOR | Error that changes with each re-clamping reaches the production mounting undiminished; the production mounting is not defined; a kit / hollow-shaft reference breaks the method for H1 |
| F5 | MAJOR | The module is the transfer artefact and is assumed stable for 8 turns plus 7 remounts; 1 % drift → 5–8″ in R̂ and a false step-5 alarm |
| F6 | MAJOR | The simulated reference spectrum is favourable; SDE / pole-pitch error and H8/H16 are irreducible (8–30″) and set by an unknown technology |
| F7 | MAJOR | Station dynamics and read timing are uncontrolled: "in position plus settling time" is undefined, one Modbus read against a 205 ms average, hold-current events; the step-2 noise check excludes the reference and the approach |
| F8 | MAJOR | Errors common to both passes that end up inside shipped coefficients: station ambient magnetic field (Earth + stepper) as H1, station magnet/mount, single approach direction, temperature |
| F9 | MINOR | Torsional wind-up: coupling type and stiffness unspecified (helical-beam "bellows" look-alikes: 10–100″) |
| F10 | MINOR | Station topology unspecified: motor, reference and magnet each need a shaft end |
| F11 | MINOR | Resolution is not accuracy: register width, latching, baud rate and low-bit activity unverified |

### F1 — BLOCKER — The coupling's transfer error is invisible to §7.7 and stays in `θ_true`

- **Spec claim.** §7.7 l. 1004: `ψ − θ_s = c_j + R(ψ) − M(θ_s)`, with R "the reference error"; l. 1014–1017: 49.98″ → 4.55″;
  `station-reference-encoder.md` §4: "≈ 0.02° + 5″ ≈ 0.0215°"; §7 (l. 93): "use a bellows coupling". `ref_selfcal.py` l. 85–86: the only
  error between shaft and reading is `series(ref_angle, R)`.
- **Issue.** The method separates errors by *which body they rotate with*, not by whether they belong to the reference chain. A
  flexible coupling under lab-fixed misalignment has a kinematic transfer error (misalignment × the coupling's own asymmetry — single
  clamp screw, slot, convolution tolerances) that is a function of the **coupling body's** angle. Step 1 (l. 1000) turns the encoder
  shaft *inside* the coupling, so the coupling stays on the stage shaft: this error has the same phase at all 8 mountings, is absorbed
  into `M̂`, and remains in `θ_true = ψ − R̂(ψ)` in full. The same holds for anything else synchronous with the stage shaft (e.g. a
  hollow-shaft reference's torque-arm error from shaft runout). Step 5 re-uses `M̂` and sees nothing.
- **Magnitude (external).** HEIDENHAIN *Rotary Encoders* 11/2017, p. 24 "Shaft couplings", kinematic transfer error "with radial
  misalignment λ = 0.1 mm, angular error α = 0.09°": K 14 diaphragm **±6″**, K 17 **±10″**, C 19/C 212 **±13″**, metal bellows
  18 EBN 3 **±40″** (text extracted from the PDF; table columns read in order). These are purpose-built encoder couplings; a
  marketplace bellows coupling on a self-built stage at 0.1–0.3 mm is unlikely to be better.
  <https://www.heidenhain.us/wp-content/uploads/2018/03/349529-2H_Rotary_Encoders_en.pdf>. EURAMET cg-23 *Guidelines on the
  Calibration of Angular Encoders* treats coupling and installation eccentricity as decisive contributions (search abstract only; the
  PDF could not be parsed here) <https://www.euramet.org/Media/news/I-CAL-GUI-023_Calibration_Guide_No._23_web.pdf>.
- **Quantification (simulation).** `station_selfcal_attacks.py 200`, §2 of its output, arcsec median/max:

  | Coupling-body error S | remount side | err of `θ_true` | step-5 raw | step-5 harmonic |
  |---|---|---|---|---|
  | none (baseline) | encoder | 3.0 / 4.3 | 19.8 / 43.2 | 6.0 / 9.7 |
  | 6″ H1 + 3″ H2 | encoder (spec) | 9.1 / 11.3 | 19.6 / 32.8 | 6.0 / 9.3 |
  | 13″ + 6″ | encoder (spec) | 17.5 / 19.6 | 19.6 / 32.8 | 6.0 / 9.3 |
  | 40″ + 20″ | encoder (spec) | **50.8 / 54.2** | 19.6 / 32.8 | 6.0 / 9.3 |
  | 40″ + 20″ | **stage side** | **3.0 / 4.5** | 19.6 / 32.8 | 6.0 / 9.3 |

  And in the gate (`station_gate_ref_error.py 2000`): S = H2 40″ + H1 20″ → 349 of 542 accepted parts above `R_MAX` against the real
  angle, worst 0.0323°, median true error of accepted parts 2.04× what a perfect station would give.
- **Evidence type.** Analysis + simulation + manufacturer data. The size of S on this station is unknown (bench item U3).
- **Recommended change (station procedure only).** Do the 8 remounts at the **stage-shaft hub** of the coupling, leaving the
  encoder–coupling joint clamped for good: coupling and encoder then rotate together relative to the magnet shaft, `R + S` becomes one
  function of ψ and is calibrated as a unit (last row above). Add a coupling requirement: encoder-grade diaphragm / flexure coupling
  or bellows with a stated transfer error, alignment ≤ 0.05 mm / 0.05° verified with a dial indicator, and treat "coupling touched" as
  "self-calibration void" (already in step l. 998, but for the right side). Put a coupling line in every budget.
- **Frozen items.** None.

### F2 — BLOCKER — Step 5 cannot verify the claim, and nothing else does

- **Spec claim.** §7.7 l. 1009 "Check the result by one more mounting at an angle that was not used in the fit"; l. 1019–1020 "the
  residual on a real reference depends on its actual spectrum; step 5 measures it"; doc §6 step 5: the corrected residual "should agree
  with the module error and not vary with the mounting angle". O3 lists "the residual measured by the §7.7 step-5 check" as the closing item.
- **Issue and quantification** (`station_selfcal_attacks.py 200`; `station_budget.py`):
  1. *No statistic, no threshold.* Nothing says what is computed or what passes.
  2. *Noise floor.* Per-position σ = √(5.6² + 1.5²) = 5.8″; the expected half-range of 256 such points is ≈ 16.5″. Simulated on the
     author's own ideal model: raw 19.8″ median / 43.2″ max; harmonic (H1–H20 fit of the residual, 8 and 16 excluded) 6.0″ / 9.7″ — so a
     *perfect* self-calibration reads 6–10″ at best; a 4.55″ claim cannot be confirmed this way. (That floor is noise: 36 parameters
     fitted to one 256-position turn, 0.51″ per coefficient, give a curve of ≈ 2.2″ rms ≈ 6″ half-range. Individual low-order
     amplitudes, at 0.51″ each, are the usable statistic.)
  3. *Blind spots.* F1's S: err 50.8″, step-5 identical to baseline. Reference H16: `e^{i·16·22.5°} = 1`, invisible at 22.5° (H8 shows
     doubled, but superposed on the module's own H8 unless compared with the fit mountings' residual). Pole-pitch error at 32/rev of 20″: err 27.2″, harmonic
     statistic 6.0″ (raw rises to 38.5″ — the only hint).
  4. *False alarms.* 1 % module drift: R̂ still good (err 4.9″/8.5″) but step-5 harmonic 17.0″/41.3″, because step 5 tests `M̂` as much as `R̂`.
  5. *Self-referential.* Every check in §7 compares the reference chain with itself via the module. No artefact or method with an
     independent error structure is ever consulted, so the absolute claim has no traceability path at all.
- **Recommended change.** (a) Define step 5 as: harmonic amplitudes H1–H7 of `ρ = ψ − R̂(ψ) − θ_s + M̂(θ_s)` on the check mounting,
  each ≤ 3″ (6σ of 0.51″), plus a *closure* turn on mounting 0 at the end with the same limit (separates module drift from
  reference error), plus the scatter of the per-mounting low-order residuals reported as the Type-A remount reproducibility (F4).
  (b) Add mountings at 22.5° **and 11.25°** to the *fit* (H8 and H16 become observable: xMR-like spectrum 10.9/16.7″ → 5.4/7.4″ with
  the 22.5° mounting and H8 fitted), keeping one further odd angle (e.g. 100°) as the check. (c) One independent check, once per
  station build, of H1–H3 at least: a borrowed/rented encoder with a calibration chart, a calibration-lab run of reference + coupling
  (polygon + autocollimator is the cg-23 method), or — cheapest — a second identical reference (≈ ¥227) mounted by a *different*
  coupling as a permanent check standard: it does not give traceability but it detects drift, slip and coupling faults in production.
  Until (c) exists the claim should read "self-consistent to …", not "accurate to …".
- **Frozen items.** None.

### F3 — MAJOR — The "as delivered" figure, the gate's blindness, and the missing incoming test

- **Spec claim.** §7.7 l. 994–995: "Used as delivered, a part accepted at `R_MAX` can be off by up to about 0.02° + 0.014° ≈ 0.034°";
  §7.2 l. 826: `R_MAX` is the "limit on the **true** systematic error of an accepted part"; l. 883 "No part with true error above
  `R_MAX` was accepted".
- **Issue.** (1) 0.014° is a marketplace rating of unknown technology; HEIDENHAIN's ROC 400 absolute encoders are rated ±20″ (2048
  lines) / ±60″ (512 lines) — ±50″ for ≈ ¥227 is possible for an optical unit, doubtful for a magnetic one (MagnTek MT6835, a typical
  21-bit low-cost magnetic IC: INL target < ±0.07° = ±250″ *after* user calibration
  <https://www.magntek.com.cn/upload/pdf/202407/MT6835_Rev.1.3.pdf>; "resolution customisable to any power of two" on the listing
  points to interpolated resolution). (2) The figure omits the coupling (F1): budget A gives 65″ rss / 112″ linear → 0.038–0.051°.
  (3) `R_MAX`'s definition (true error) and l. 883 are true only for a perfect `θ_true`; `R_ACCEPT = 0.95·R_MAX` guards against sensor
  noise only.
- **Quantification** (`station_gate_ref_error.py 2000`; float model of §7.2, same population as `station_sim.py`; 534 accepted with
  a perfect reference, 0 false accepts, worst 0.0192° — consistent with the verified OC):

  | `θ_true` error (same in both passes) | false accepts / accepted | worst accepted true error | median true ÷ ideal | good parts rejected |
  |---|---|---|---|---|
  | none | 0 / 534 | 0.0192° | 1.00 | 0 / 450 |
  | H1 5″ | 1 / 550 | 0.0200° | 1.02 | 0 / 447 |
  | H1 15″ + H2 8″ | 12 / 541 | 0.0221° | 1.26 | 0 / 426 |
  | H1 35″ + H2 15″ | 222 / 541 | 0.0279° | 1.79 | 0 / 426 |
  | H1 50″ | 350 / 550 | 0.0293° | 2.01 | 0 / 447 |
  | H1 200″ (magnetic, mis-rated) | **550 / 550** | 0.0705° | 5.84 | 0 / 447 |
  | H32 20″ only | 0 / 399 | 0.0153° | 1.00 | **51 / 447** |

  Two lessons: low-order error goes straight into the coefficients and the gate never notices; high-order error cannot enter six
  harmonics, so it costs yield (11 % of good parts) instead of accuracy.
- **Incoming acceptance test (no extra equipment; all station software).** (1) Technology: hold a small magnet to the housing while
  reading — any change means magnetic. (2) Static noise: 1000 reads at 8 angles; σ and which low bits move. (3) Multi-turn
  repeatability: 16 positions × 10 turns, same direction, scatter of `ψ − θ_s` (module K = 1024): must support "±3″"; bearing
  non-repeatable runout of 0.3 / 1 / 2 µm at r = 15 mm would give 4 / 14 / 28″. (4) Reversal: the same from the other direction
  (reference + wind-up + module hysteresis together). (5) Fine scan: ≥ 1000 positions at the smallest microstep over a few degrees
  against the (smooth) module — any periodic structure finer than ≈ 10° belongs to the reference; its period tells optical (360°/2ⁿ
  lines) from pole-pitch magnetic (11.25° / 5.6°), its amplitude is budget line 1. (6) 30 min warm-up log at two positions. (7) The
  §7.7 map itself: reject the unit if the *uncorrected* half-range exceeds the rating or if closure fails. If magnetic: expect
  hysteresis and temperature dependence of the curve at the 10–40″ level, sensitivity to the stepper's field, and a re-calibration
  interval; I would not accept it as the reference for a 72″ tolerance.
- **Decision rule.** Either state `R_MAX` as "relative to the station reference" everywhere, or guard-band per ISO 14253-1:
  `R_ACCEPT = R_MAX − U(θ_true)` (`station_budget.py`: U = 50″ → 0.0061°, which rejects most good parts; U = 13″ → 0.0164°; ratio
  tolerance : reference is 1.4 : 1 as bought against the customary ≥ 4 : 1).
- **Frozen items.** None (`R_MAX`, `R_ACCEPT` are station constants).

### F4 — MAJOR — Per-clamp error, and which mounting is the production mounting

- **Spec claim.** Doc §6 step 6: "done once … redo after remounting". `ref_selfcal.py`: R identical at every mounting.
- **Issue.** Each re-clamping can change the error by a low-order term (hub seating, clamp distortion; for a **kit or hollow-shaft
  reference** the disc/rotor eccentricity itself: 5 µm at r = 15 mm = 69″). The joint fit averages these over 8 clampings, but
  production runs on **one** clamping — the last one — whose own term is not in R̂ at all. The spec does not say which mounting
  production uses (after step 5 the encoder sits at the check angle).
- **Quantification** (`station_selfcal_attacks.py 200`, §3): C_j = 3″+2″ → err 5.8/7.8; 10″+5″ → **14.3/19.8**; 30″+15″ → 39.1/55.6;
  kit-type E_j = 70″ → 71.4/119.2 (no improvement over "before"). Step 5 does respond here (harmonic 16.2/24.2 at 10″, floor 6.0/9.7)
  but at 3″ it is inside its floor (8.2/12.9). Folding H1–H3 of the production mounting's own residual back into the correction
  (`err_T`) recovers 14.3 → 6.2 and 39.1 → 13.4, **but only if the module has not drifted** (1 % drift: 12.6/28.9).
- **Recommended change.** Confirm the reference is a solid-shaft unit with its own bearings (U1) — otherwise the method does not apply
  to H1. Make the production mounting explicit and last; report the scatter of per-mounting H1/H2 residuals as the remount
  reproducibility and carry it in the budget; fold the production mounting's H1–H3 residual back only when the closure turn (F5)
  passes. **Frozen items.** None.

### F5 — MAJOR — The transfer artefact is a TLE5012B

- **Spec claim.** §7.7 step 1: "The module is not turned, because turning it changes its own error" — M is assumed constant over
  8 turns and 7 manual remounts (realistically 30–60 min). §2.7 l. 232–236 itself says the raw error drifts with temperature.
- **Quantification** (§4 of the output; drift as a fraction of M over the session, M up to 1°): 0.3 % → err 3.3/4.9; **1 % → 4.9/8.5**;
  3 % → 9.6/21.1 (analytically, a linear drift d per mounting biases r̂_k by d/(2 sin(πk/8)), 1.3·d at H1). A palindromic sequence
  0…7, 7…0 cancels linear drift exactly: 2.6/3.8 at both 1 % and 3 %. Step 5 meanwhile reads 17–45″ and would wrongly condemn R̂.
- **Recommended change.** Power the module ≥ 30 min before the session; log `GET_ENV` temperature per turn and require ± 0.5 K;
  palindromic or at least closed sequence; closure criterion as in F2. **Frozen items.** None.

### F6 — MAJOR — The spectrum assumption

- **Spec claim.** l. 1011–1012 "reference error of 50″ peak, dominated by H1, with a heavy tail up to H20"; doc §6 "blind-spot residue
  is small".
- **Issue.** `random_reference()` has *no* content above H20 and only 0.15/k^0.7 at H8/H16. Real encoders have sub-divisional error
  at the line or pole frequency (HEIDENHAIN: system accuracy ≈ 1/20 grating period for incremental units) and xMR units have H4/H8/H16.
- **Quantification** (§1 of the output): optical-like 8″ SDE at 2048/rev → 8.5/11.7; pole-pitch 20″ at 32/rev → 27.2/29.6; xMR-like
  H1,2,4,8,16 → 10.9/16.7 (5.4/7.4 with the 22.5° mounting in the fit); a mis-rated 200″ reference with the author's spectrum →
  7.9/12.6 (the method itself copes well with a *large* low-order error — a point in its favour).
- **Side note.** l. 1019 "Noise is not the limit" is half right: with a pure H1/H2 reference (nothing unfittable) the result is
  still 1.9/2.8″ of the baseline's 3.0/4.3″ (row "noise only").
- **Mitigating fact the spec should state.** Only H1–H6 of the `θ_true` error can enter a module; none of 1–6 is a multiple of 8 and
  all are resolved to < 1″ by the fit. H8/H16/SDE matter only for the gate (yield, and the honesty of `R_MAX`).
- **Recommended change.** Fine scan (F3 item 5) to measure the SDE; mountings at 22.5° and 11.25° in the fit; budget what remains.
  **Frozen items.** None.

### F7 — MAJOR — Dynamics and read timing

- **Spec claim.** §7.2 step 1 l. 838–839: "wait for the stage to report in position plus its settling time, *then* issue
  `SAMPLE_START`"; doc §2: "read only after standstill, so low baud rate does not matter"; step 2: σ from 8 module samples at one
  position; O3 "the stage's settling time" open.
- **Issue.** A stepper "in position" means pulses ended, not motion ended. The module integrates 204.8 ms; the reference is one
  31.5 ms Modbus poll at 9600 bps (8 + 9 bytes, 8E1, two 3.5-char gaps; +16 ms with an FTDI adapter at default latency) at an
  unspecified instant. Hold-current reduction (default on most drivers, ≈ 0.5–1 s after the last step) and stick-slip move the rotor
  *during or between* the two readings. Step 2 involves neither the reference nor an approach, so none of this is ever measured, and
  the gate's verified OC assumed σ_mean = module noise only.
- **Quantification** (`station_dynamics.py`; worst case over ring phase): ring-down A₀ = 0.05°, 100 Hz, τ = 100 ms — single read
  before the window: 91″ at 100 ms wait, 12″ at 300 ms, 1.7″ at 500 ms; mean of polls bracketing the window: 12.8″ / 1.7″ / 0.2″.
  One 0.01° step inside the window: 36″ with a single read, 4″ with the bracket mean, and the bracket *spread* (36″) detects it.
- **Recommended change (station software).** Poll the reference continuously from before `SAMPLE_START` to after `GET_SAMPLE`
  (≈ 8 polls at 9600, more at a higher baud rate); use the mean; **settle/stationarity criterion: spread of those polls ≤ 2–3″, else
  wait and repeat**; disable hold-current reduction or wait it out; run the step-2 noise check on `θ_true − θ_s` over 8 *re-approaches*
  of one position, so that reference, settle and repeatability are inside σ_mean. **Frozen items.** None — `SAMPLE_START`/`GET_SAMPLE`
  suffice as they are.

### F8 — MAJOR — What is common to both passes ends up in the module

The gate cancels anything identical in the fit and validation passes; whatever of it lies in H1–H6 is written into the module.
Besides F1/F3: (a) **Ambient magnetic field.** A lab-fixed in-plane field B_ext adds an H1 error of B_ext/B_magnet to a field-direction
sensor: Earth's horizontal 20 µT → 0.038° at 30 mT, 0.023° at 50 mT; total 48 µT → 0.092° / 0.055° (`station_budget.py`; small-angle
physics, B_magnet from the TLE5012B's 30–50 mT range — my assumption). **Cross-check, received 2026-09-20 from the sensor-physics
reviewer by message (I did not read their file; their figures are simulation + published CAD, nothing measured):** mechanism and
arithmetic confirmed to four digits; for this hardware (Ø3 × 3 mm diametric magnet, gap ≈ 2.5–3.0 mm) they estimate B_magnet ≈
23–32 mT, lower still with the steel bearing around the magnet, so my 30 mT column is the *optimistic* end: 48 µT → 0.110° at 25 mT,
0.138° at 20 mT (20 µT → 0.046° at 25 mT). B_magnet is unmeasured; read this finding with the B_magnet of their finding P1 / U3
(`2026-09-20-accuracy-review-sensor-physics.md`). They also note that on the arm neighbouring modules' magnets, which a single-module
station never sees, are a larger stray source than the Earth's field — outside my scope, but it means F8a is a lower bound. The station
calibrates this H1 *in*; on the arm the field direction differs per joint and pose, so up to twice that amplitude appears as error —
comparable to or larger than `R_MAX`, before any stepper or steel stray field. Cheap test (agreed with the sensor-physics reviewer):
repeat the validation pass with unit + fixture yawed 180° on the bench — the H1 change is 2·B_ext/B_magnet directly; and once more
with motor current on/off. (b) **Station magnet and mount**: if the module is not calibrated with the
magnet, gap and centring it will have on the arm, M is a property of the station (U4; other reviewer). (c) **Single approach
direction** (§7.2 step 1): hides the module's reversal hysteresis and the station's wind-up reversal; the arm moves both ways. One
reversed validation pass per module type measures it at no hardware cost. (d) **Temperature**: recorded, not controlled; the
reference's own curve also moves. The claim must carry "at station conditions" wherever it is quoted. **Frozen items.** None forced;
the conditions live in the station database keyed by SERNUM.

### F9–F11 — MINOR

- **F9 wind-up.** T/C with encoder starting torque 1–10 mN·m (HEIDENHAIN: 0.001–0.01 N·m): C = 60 N·m/rad (18 EBN 3) → 3.4–34″;
  150 → 1.4–14″; a helical-beam "bellows" at ≈ 20 → 10–103″ (`station_dynamics.py`). Constant under a single approach direction; its
  variation around the turn (friction ±30 %) is the budget line. Require C ≥ 150 N·m/rad, forbid beam couplings by name.
- **F10 topology.** Doc §1 and §7 put the reference, the stepper "at the other end" and the magnet on one shaft; a solid-shaft
  encoder, a motor and an on-axis magnet need three shaft ends. Whether a second coupling or the motor's own shaft lies between
  reference and magnet changes F1 and F9. Draw it and put it in the spec.
- **F11 resolution.** Confirm the register returns all 21/23 bits, that the value is a latched sample rather than a filtered one, the
  highest baud rate, and which low bits are noise; 23 bits (0.15″) says nothing about ±50″.

---

## 2a. Evidence and exact commands

All run from the repo root; outputs are stored verbatim next to the scripts. Seeds are fixed in the scripts.

| Tag | Command | Output file | Runtime |
|---|---|---|---|
| E1 | `encoder/.venv/bin/python encoder/docs/evidence/v5-accuracy-review-scripts/station_selfcal_attacks.py 200` | `…/results/station_selfcal_attacks.txt` | ≈ 4 min |
| E2 | `encoder/.venv/bin/python encoder/docs/evidence/v5-accuracy-review-scripts/station_gate_ref_error.py 2000` | `…/results/station_gate_ref_error.txt` | ≈ 40 s |
| E3 | `encoder/.venv/bin/python encoder/docs/evidence/v5-accuracy-review-scripts/station_dynamics.py` | `…/results/station_dynamics.txt` | < 10 s |
| E4 | `encoder/.venv/bin/python encoder/docs/evidence/v5-accuracy-review-scripts/station_budget.py` | `…/results/station_budget.txt` | < 1 s |

E1 is an extended copy of `ref_selfcal.py` (same generators, noise, jitter and fit; adds coupling-body error S, per-clamp errors
C_j/E_j, module drift, stage-side remount, alternative reference spectra, the step-5 statistics and a production mounting). All E1
columns are arcsec half-range, median/max over 200 random reference+module pairs; `err` is the true error of `θ_true = ψ − R̂(ψ)` on
the production mounting. E2 is a float model of §7.2 (arithmetic and quantisation, verified on 2026-09-19, left out) with
`station_sim.py`'s part population. HEIDENHAIN figures were extracted from the brochure PDF's text streams; the EURAMET cg-23 PDF
could not be parsed and is cited from its abstract only. Limits of this review: no hardware was available, every magnitude for the
real station (S, C_j, drift, SDE, settle) is an assumption bracketed from manufacturer data, and the ambient-field figure in F8 rests
on an assumed B_magnet (since cross-checked by the sensor-physics reviewer, see F8a: mechanism confirmed, B_magnet likely lower).

## 3. Comparison with standard practice — is there a simpler or more robust method with the same hardware?

§7.7 *is* the standard multi-position ("multi-step", equal-division-averaging carried out in time rather than with N heads) method:
N equal divisions determine everything except multiples of N (Masuda/Kajitani EDA; NMIJ SelfA; e.g.
<https://pmc.ncbi.nlm.nih.gov/articles/PMC11434417/>). I checked it: condition number 1.31 column-normalised; tolerant of ±3°
mounting; with H8/H16 included it is still solvable through the jitter alone (cond 8.4, err 2.7/5.1). No simpler estimator does
better — plain averaging of the 8 difference curves is the same thing for exactly equal angles and worse for unequal ones. What
standard practice adds, all with the same hardware: **(1)** break the joint that carries *all* of the chain you want calibrated
(stage-side hub, F1); **(2)** closure and time-symmetric ordering against drift of the artefact (F5); **(3)** two division sets or
extra odd angles to open the blind harmonics (F2b); **(4)** a Type-A remount-reproducibility figure from the data already taken (F4);
**(5)** for a synchro-flange encoder, rotating the *housing* in its pilot is an alternative way to shift R without touching any
shaft clamp; **(6)** a check standard in permanent use (F2c). Reversal methods add nothing here beyond (1)–(3).

## 4. Uncertainty budget

`station_budget.py` → `results/station_budget.txt`. Half-widths of systematic, angle-dependent error, arcsec.

| Component | A as bought | B §7.7 as written | C recommended | Source |
|---|---|---|---|---|
| reference intrinsic / residual after R̂ | 50 (rating, unverified) | 9 | 9 | listing; E1 §1 (8″ SDE case) |
| coupling transfer error | 40 | **40** | 4 | HEIDENHAIN p. 24; E1 §2 |
| per-clamp error on the production mounting | (in the above) | 8 | 5 | E1 §3; to be measured |
| module drift during self-calibration | – | 6 | 3 | E1 §4 |
| reference repeatability, bearing NRRO | 3 | 3 | 3 | rating; to be measured |
| wind-up variation | 4 | 4 | 2 | `station_dynamics.py` |
| settle / timing | 10 | 10 | 2 | `station_dynamics.py` |
| thermal change of the reference curve | 5 | 5 | 5 | estimate |
| **`θ_true`: rss / linear** | **65 / 112″** | **44 / 85″** | **13 / 33″** | |
| **accepted module, absolute, station conditions (72″ + …)** | **0.038 / 0.051°** | **0.032 / 0.044°** | **0.024 / 0.029°** | |

Lines marked "estimate / to be measured" are my judgement, not data; replace them with the bench results of §5. A combined
simulation with milder inputs than column B (S 20″+10″, C_j 5″+2.5″, 1 % drift, 8″ SDE) gives err 31.5/43.4″ for §7.7 as written
and 13.6/18.1″ with stage-side remount + palindrome (E1 §5), bracketing columns B and C.
**Cheapest changes, by effect:** stage-side remount and a better-aligned encoder-grade coupling (−35″); bracketed reference polling
with a spread criterion (−8″ and it removes an unbounded failure mode); closure + palindrome + temperature log (−3″ and makes step 5
meaningful); fine scan + two extra mountings (turns line 1 from an assumption into a measurement); one independent check (turns
"self-consistent" into "verified").

## 5. Unknowns that need a bench measurement or an answer

- **U1** Reference: optical or magnetic; solid shaft with own bearings vs hollow-shaft/kit; line or pole count; per-unit test report;
  register map and latching; maximum baud rate (doc §5 already asks most of this — add shaft/bearing type and line count).
- **U2** Station topology and the coupling's make, rated transfer error and torsional stiffness; achievable alignment (mm, °).
- **U3** Size of S on the real station: difference between an encoder-side and a stage-side self-calibration gives it directly.
- **U4** Is each module calibrated with the magnet, gap and centring it will have on the arm? B_magnet at the sensor?
- **U5** Bench series, all software-only: remount reproducibility (scatter of per-mounting H1/H2); module drift over 45 min
  (closure); reference multi-turn repeatability; reversal difference; fine-scan SDE; bracket spread vs wait time; driver hold-current
  behaviour; station turned 180° and motor current on/off (F8a).
- **U6** Temperature coefficient of the reference's error curve (repeat the self-calibration at a second room temperature).

## 6. What the design gets right

- It says plainly that every §7.2 figure is relative to the reference and that the gate cannot see reference error (l. 992–995).
- The gate is out of sample, averaged, on the committed module's own output, with a constant-free statistic; its noise statistics
  survive a real reference in the safe direction — extra random or high-order `θ_true` error only costs yield (F3 table, last row).
- The self-calibration method is the right one, well conditioned, needs no accurate mounting angles, turns the reference rather
  than the module, and copes with a reference far worse than its rating as long as the error is repeatable and low-order (200″ → 8″).
- Only six harmonics are stored, so only H1–H6 of any `θ_true` error can reach a module, and §7.7 resolves exactly those best.
- Same approach direction, separate RS-485 bus, on-module averaging, recorded conditions, bellows-not-jaw: all correct instincts;
  they need numbers (F7, F9) rather than replacement.
