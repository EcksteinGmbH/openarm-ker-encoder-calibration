# Accuracy review — sensor physics and transferability of the calibration (spec v5)

| | |
|---|---|
| Date | 2026-09-20 |
| Reviewer angle | magnetic angle sensor physics / metrology; independent of the design |
| Question | "Can the current method really control and improve the sensor's system accuracy?" — in use, on the arm |
| Reviewed | `encoder/docs/protocol-spec.md` v5 (§2, §6, §7, §9, §12), `station-reference-encoder.md`, `encoder/src/main.cpp`, `README.md`, `evidence/v3-reference/{harmonics_v3,station_sim,station_fit}.py` |
| External | Infineon TLE5012B data sheet, user manual, three application notes, TLE5014 data sheet; OpenArm KER docs, BOM and STEP assembly (source list at the end) |
| Own evidence | `evidence/v5-accuracy-review-scripts/physics_magnet_model.py` → `physics_magnet_model.txt` (numpy only, ≈ 1 min) |
| Not covered | the station's reference encoder; system timing / M5 (other reviewers) |
| Files changed | none. New: this file and the two `physics_*` files |

Evidence types are marked **[DS]** datasheet, **[AN]** application note, **[HW]** OpenArm hardware documentation/CAD,
**[SIM]** my simulation, **[R]** reasoning / order-of-magnitude estimate. Nothing here was measured on hardware.

---

## 1. Verdict

**Improve: yes. Control to 0.02° in use: no — and as designed the in-use figure is neither true nor checkable.**

The method removes the error that is a fixed function of the module's own angle. On this hardware that part is
large — an Ø3 mm magnet facing a sensor whose die may sit ±0.2 mm off the package centre gives 0.15–1.5° of pure
assembly error **[SIM]** on top of the die's 0.6° typical **[DS]** — and it *does* travel with the module, because
the KER encoder module is a self-contained unit with its own bearing, horn and embedded magnet **[HW]**. So a
calibrated module on the arm will be markedly better than an uncalibrated one.

But 0.02° is a **station repeatability figure**, not a joint-angle accuracy. With an Ø3 mm magnet the working
field is only ≈ 20–45 mT, and every error source that is *not* a fixed function of the module's own angle then
lands far above 0.02°: the Earth's field alone is worth ±0.06–0.14° depending on how the joint is oriented;
neighbouring modules' magnets (28–37 mm away in the CAD) ±0.05–0.3°; GMR hysteresis ±0.05–0.13° on a device that
reverses direction constantly; and 3–12 µm of relative motion between rotor and sensor — the order of a single
ball bearing's internal clearance — uses up the whole 0.02°. None of these can be represented by
`Σ A_k sin(kθ_s+φ_k)`, none is present or exercised at the station, and nothing on the arm can observe them
(the M5 sees no status, CMD=3 is off-arm only).

**Realistic expectation in use** (assumptions: unit calibrated fully assembled and never reopened; B₀ ≈ 25–35 mT;
ambient within ±10 K of calibration after warm-up; averaged reading, i.e. without the 0.05° per-reading noise):

| | Uncalibrated (today) | Calibrated per spec v5 |
|---|---|---|
| isolated joint, careful build | ≈ 0.7–1° | **≈ 0.1–0.15°** |
| clustered joints (J1/J2, J3/J4, J5–J7), ordinary build | ≈ 1–2° | **≈ 0.2–0.4°**, pose dependent |
| what the station gate certifies | — | 0.02° at the station, one direction, one temperature, one orientation, no load, no neighbours |

A 5–10× improvement is a good result. The claim has to be restated to match it, and the gap between the two
rows has to be *measured once on an assembled arm* — which needs no change to the protocol, the USERROW layout
or the M5 firmware (§5 of this review).

---

## 2. Findings

| ID | Severity | Title |
|---|---|---|
| P1 | **BLOCKER** | Low working field of the Ø3 mm magnet makes stray fields (Earth, neighbouring modules) a 0.05–0.3° pose-dependent error that no per-module static fit can remove |
| P2 | **BLOCKER** | The accuracy claim is verified only at the station; nothing verifies or monitors it on the arm |
| P3 | MAJOR (BLOCKER if violated) | The spec never says *what* is calibrated: it must be the fully assembled unit with its **own** magnet, sealed afterwards |
| P4 | MAJOR | An Ø3 mm magnet demands 3–12 µm mechanical stability between rotor and sensor; the unit has one ball bearing and a printed nylon spacer |
| P5 | MAJOR | Single-direction fit on a hysteretic sensor; Infineon's own procedure averages both directions |
| P6 | MAJOR | The field at the sensor is probably at or below the 30 mT specification minimum; the in-spec gap window is only ≈ 0.7 mm wide |
| P7 | MAJOR (unquantified) | Temperature, self-heating and supply voltage differ between station and arm; no figure exists for any of them |
| P8 | MINOR | Datasheet facts in §2.4, §2.7, O1 and D16 are wrong for the part on the BOM (TLE5012B-**E1000**) |
| P9 | MINOR | `D_MAG` cannot serve as a field-strength or air-gap monitor |
| P10 | MINOR | §7.7's reason for not turning the module is, read correctly, an admission of P1 |

None of these forces a change to the USERROW layout, the CMD=3 subcommand set or the M5 firmware. All fixes are
in the station procedure (`kercal`, host side), in assembly practice, in one arm-level verification, and in the
wording of the claim. Two optional hardware changes (bigger magnet, shielding) are outside the frozen items.

---

## 3. What the hardware actually is

This had to be established first, because the spec does not describe it.

**The module is a complete mechanical unit and the magnet travels with it. [HW]** OpenArm's encoder-module page:
"This advanced module design integrates a hardware limit, bearings, a magnetic encoder, and a driver"; its
exploded view shows horn ("Embedded Magnet — Radially Magnetized Magnet"), one bearing, housing, PCB bracket and
PCB. The BOM's `ENC_UNIT` (×16): `ENC_HOUSING` A7075 CNC, `ENC_HORN` A7075 CNC, `PCB_SPACER` **PA12 nylon,
HP-MJF printed**, `ENC_PCB`, **one** bearing MISUMI `C-FL6700ZZ` (10 × 15 × 4 mm, flanged, stainless), magnet
"Neodymium Magnet Disk Sensor **N35 D3mm(A) x 2.5mm**", Radial Magnets Inc. #9098, "100% sorted with a max
3-degree angle deviation". Unit screws are `SCB2-4` "SUS304/SUS316 — Non-magnetic"; the material of the M2-10
frame screws (6 per unit) is not given. The encoder PCB carries **TLE5012B-E1000**, ATtiny1616, an RS-485
transceiver, three 100 nF capacitors and a TVS — **no voltage regulator**; the sensor is on the **bottom** side.

User update 2026-09-20 (via the coordinator): the magnet is now **Ø3 × 3 mm**, diametric, because 2.5 mm parts are
unobtainable; the magnet-face-to-chip distance is kept as designed; grade unknown. The change itself is small
(+6–7 % field at equal gap **[SIM]**, confirming the coordinator's closed-form estimate to four digits). What
matters is the property that did not change: **the magnet is only 3 mm in diameter.** Infineon: "The smaller the
magnet's diameter the bigger the assembly error. With diameters above 10mm the assembly error becomes
relatively small" **[AN-MDT §3.2, p. 12]**.

**Geometry read from the published STEP assembly [HW]** (unit frame, rotation axis = y, mm; the STEP has no
magnet or PCB model, and pre-dates the magnet change):

| Feature | Value |
|---|---|
| magnet pocket in the horn | Ø3.0, y = 1.5 … 4.0 (2.5 deep, 0.2 chamfer); face flush with the horn face at y = 4.0 |
| bearing on the horn's Ø10 journal | y = 0 … 4.0 — the magnet sits **inside the bearing's axial span**, steel rings at r = 5–7.5 mm around it |
| PCB spacer (1.2 thick) on the housing shelf | y = 6.7 … 7.9; held by two M2 screws at x = ±7.5 in Ø2.2 clearance holes; no locating pins found |
| PCB underside (sensor side) | y = 7.9 → **3.9 mm from the magnet face** |
| magnet face → package top | ≈ 3.9 − (1.55…1.75 package incl. stand-off) ≈ **2.15–2.35 mm** |
| magnet face → sensitive plane ("gap" below) | ≈ 2.2–2.35 + die depth. Die depth is given only in data-sheet Fig. 39 (a drawing I could not extract): **unknown**, assumed 0.3–0.7 mm → **gap ≈ 2.5–3.0 mm** |
| nearest other magnet → this sensor, CAD pose (joint numbers inferred from position along the chain) | J7←J6 28.3, J4←J3 28.8, J3←J4 31.2, J6←J7 33.6, J2←J1 34.6, J1←J2 36.8, other pairs within J5–J7 42–53, J8←J7 78.9 |
| VRIG magnetic quick-release mount | 75 mm from both J1 sensors, 107 mm from J2 |

Whether a bare `ENC_UNIT` can turn a full 360° at the station is **not established**: the stop features I found
are in the housing at r ≈ 9.3–11.8 mm, outside the horn flange (r = 7.5), and `STOPPER` is a separate top-level
part (×4), which suggests the limit acts on the attached link and not on the bare unit. To confirm (U13).

---

## 4. Answers to the five scope questions

### 4.1 What generates the error, and at which harmonic

| Source | Belongs to | Harmonic of the angle | Typical size | Evidence |
|---|---|---|---|---|
| X/Y offset | die | 1 | trimmed at Infineon, temperature-compensated on chip (`OFFX/OFFY`, `TCO_X/Y`); residual inside the 0.6° typ | **[DS]** Table 10, 11; **[UM]** §5 |
| X/Y amplitude mismatch ("synchronicity") | die | 2 | trimmed; as above | **[DS]** Table 10 |
| non-orthogonality | die | 2 | trimmed; as above | **[DS]** Table 10 |
| GMR anisotropy; reference-layer rotation at high field | die × field strength | 2, 4 | +0.1° at 25–30 mT, +0.2° at 20–25 mT; life-time drift adder above 50 mT at high T | **[AN-GMR]** Fig. 2, 3 |
| GMR hysteresis | die × field strength | **none — depends on direction/history** | 0.1° typ, 0.16° max between directions at ≥ 33 mT; +0.1° at 25–33 mT (TLE5014, same iGMR technology; the TLE5012B sheet folds it into the overall error, Table 11 note 2) | **[DS-5014]** Tables 3-11/3-12 |
| **all of the die, overall** | die, in a *homogeneous* field, B_z = 0, 30–50 mT | — | 0.6° typ @ 25 °C/30 mT; without autocal **1.3° max** over T at 0 h, **1.9° max** over T and life | **[DS]** Table 11, Table 4 note 2 |
| sensor off the rotation axis by *e* | mounting | **2**, ∝ e² | Ø3×3, gap 2.5: e = 0.1/0.2/0.3/0.5 mm → 0.05/0.20/0.45/1.25° | **[SIM]** B |
| magnet off-axis, or magnetisation tilted | mounting | **1**, only as a product with *e* (alone: exactly 0 for a point sensor — the on-axis field is fixed in the rotor frame) | "loose" build (e 0.3 mm, magnet 0.1 mm off, tilts 3°/3°): H1 ≈ 1.1°, H2 ≈ 0.5°, total 1.2–1.6°; "tight" (0.1 mm, 0.04 mm, 1°/1°): 0.14–0.19° | **[SIM]** B; tolerances **[DS]** Table 30 (die ±200 µm, tilt ±3°), **[HW]** BOM (3°) |
| higher harmonics from geometry | mounting | 3, 4, 5+ | ≤ 0.016°, ≤ 0.005°, < 0.0002° | **[SIM]** B |
| air gap | mounting | scales all of the above mildly; sets B₀ steeply (−6.7 %/0.1 mm) | see 4.2a | **[SIM]** A |
| ferromagnetic parts fixed to the stator | mounting / arm | 2 | unknown; unit screws are non-magnetic **[HW]**; frame screws unspecified | **[R]** |
| stray field fixed in the world or in a neighbour | **arm / environment** | 1, with amplitude and phase that change with pose | atan(B_s/B₀): 50 µT → 0.095° at 30 mT, 0.14° at 20 mT | **[SIM]** F |

Infineon's assembly-error tool assumes "no influence of other magnetic fields or magnetic materials such as iron
or magnetic steels … shafts of non magnetic materials such as aluminum are assumed" **[AN-MDT §3, p. 11]**. The
KER magnet sits inside a steel ball bearing, so neither Infineon's tool nor my model describes the real field
exactly; both overestimate B₀.

### 4.2 Does the station fit survive installation? — the three items the coordinator asked for

**(a) Field magnitude of an Ø3 mm magnet versus the specified range. [SIM] A, [DS] Table 4, [AN-GMR]**

On-axis field, Ø3 × 3, no bearing steel; "gap" = magnet face → sensitive plane:

| Grade (B_r) | 50 mT at | 30 mT at | 25 mT at | 20 mT at | in-spec window | slope at the 30 mT point |
|---|---|---|---|---|---|---|
| N35 (1.20 T) | 1.93 mm | 2.60 mm | 2.86 mm | 3.20 mm | **0.66 mm** | −6.9 % per +0.1 mm |
| N42 (1.30 T) | 2.03 | 2.71 | 2.98 | 3.32 | 0.68 mm | −6.7 % |
| N52 (1.45 T) | 2.17 | 2.87 | 3.14 | 3.50 | 0.70 mm | −6.5 % |

(Ø3 × 2.5 N35: 1.86 / 2.50 / 2.75 / 3.08 mm. The 3 mm part buys ≈ 0.1 mm of gap. The coordinator's closed form
`B = B_r/4·[(g+L)/√(R²+(g+L)²) − g/√(R²+g²)]` reproduces my surface-charge integration to 0.01 mT: 47.35, 32.18,
22.71 mT at 2.0, 2.5, 3.0 mm.)

- Specified: **30–50 mT** at 25 °C (up to 60/70 mT if T_J is limited to 100/85 °C); 25–30 mT "additional angle
  error of 0.1°" **[DS]** Table 4. Below that, **[AN-GMR]** Fig. 2: +0.1° down to 25 mT, **+0.2° down to 20 mT**,
  "due to anisotropy and hysteresis effects … completely reversible". Below 20 mT Infineon gives nothing.
- At the CAD-derived gap of ≈ 2.5–3.0 mm an N35 Ø3 × 3 gives **≈ 23–32 mT before the bearing's flux shunting**,
  i.e. at the bottom edge of the range or under it (P6). This rests on the die depth and on a CAD that pre-dates
  the change: **parametric until U1–U3 are measured.**
- Falling under 30 mT does three things. (i) Anisotropy error grows — a fixed function of angle, so the fit absorbs
  it *provided B₀ stays what it was at the station* (it moves −0.12 %/K with NdFeB and −6.7 %/0.1 mm of gap).
  (ii) Hysteresis grows — not fittable (P5). (iii) Stray-field error grows as 1/B₀ (P1). **Noise:** Infineon gives
  no noise-versus-field figure; a saturated GMR bridge's amplitude is nearly field-independent, so I expect little
  change down to ≈ 20 mT — **unknown, needs the bench** (`GET_SAMPLE` already returns Σx², so the station can
  report σ per reading for every unit at no protocol cost).

**(b) What tolerance an Ø3 mm magnet demands. [SIM] C, D**

Two different questions hide in "survive installation":

*If installation leaves the unit untouched* (unit calibrated as assembled, P3), the demand is on **stability** —
how far rotor and sensor may move relative to each other afterwards before a *perfect* fit is off by 0.02°:

| Change after calibration | loose build, gap 2.0 / 2.5 / 3.0 | tight build, gap 2.0 / 2.5 / 3.0 |
|---|---|---|
| radial shift that uses up 0.02° | **3.1 / 3.6 / 4.2 µm** | **9.3 / 10.6 / 12.3 µm** |
| radial 10 µm | 0.064 / 0.055 / 0.047° | 0.022 / 0.019 / 0.016° |
| rotor tilt 0.1° | 0.025 / 0.024 / 0.022° | 0.009 / 0.008 / 0.008° |
| axial +0.05 mm | 0.015 / 0.016 / 0.015° | 0.002° |
| axial +0.20 mm | 0.062 / 0.064 / 0.057° | 0.007° |

The sensitivity is ≈ 2·H2/e + H1/e, so it is proportional to how far off-axis the sensor already is — a well
centred unit is three times more forgiving — and it falls with magnet diameter. At equal B₀ = 40 mT, loose build:

| Magnet | gap for 40 mT | static error | H2 at e = 0.2 mm | residual per 10 µm | shift for 0.02° |
|---|---|---|---|---|---|
| Ø3 × 3 | 2.21 mm | 1.45° | 0.220° | 0.060° | **3.3 µm** |
| Ø4 × 3 | 2.78 | 1.01° | 0.135° | 0.039° | 5.1 µm |
| Ø6 × 3 | 3.74 | 0.63° | 0.068° | 0.022° | 9.3 µm |
| Ø8 × 3 | 4.53 | 0.46° | 0.041° | 0.014° | 14.0 µm |
| Ø10 × 3 | 5.19 | 0.36° | 0.027° | 0.010° | 19.5 µm |

(roughly ∝ D^−1.5; the larger magnets also work at a larger, more tolerant gap.)

*If installation re-seats anything between magnet and die* — PCB off and on, spacer re-torqued, magnet re-glued —
the demand is on **repositioning**, and it is hopeless: M2 screws in Ø2.2 holes on a printed nylon spacer
reposition to ±0.1–0.2 mm, which leaves **0.17–0.59° (0.1 mm) or 0.40–1.26° (0.2 mm)**. The calibration is void.

**(c) Must the station use the same magnet? [SIM] E** — It must use the unit's **own** magnet, in its own seat,
on its own bearing. "Same type" is not enough, because H1 is set by the individual magnet's magnetisation tilt
and seating, and H2 by where this unit's die sits relative to this unit's axis. Unit with 1.36° raw error, gap 2.5:

| Fit made with … | Residual in use |
|---|---|
| another Ø3 × 3 of the same type, tilt 3° at the opposite azimuth | **1.38°** — no better than uncalibrated |
| same type, tilt at 90° azimuth / tilt 1° instead of 3° | 0.68° / 0.46° |
| the same magnet seated 0.2 mm elsewhere (0.1 mm either side of the axis) | 0.85° |
| a perfect Ø6 × 3 station "master" magnet | 1.16° |
| an Ø3 × 2.5 in the identical pose (i.e. only the length differs) | 0.027° |

The last row says the *length* change is nearly harmless; every other row says a station magnet is useless.
Because the KER unit carries its magnet, the natural station — drive the unit's horn through a coupling — does
the right thing. The spec must make it normative (P3).

**What is left once (a)–(c) are satisfied** is what the arm adds and the station never sees: stray fields (P1),
bearing play under real load (P4), direction reversals (P5), temperature and supply (P7).

### 4.3 AUTOCAL off — temperature, hysteresis, life, supply, stray fields

- **Turning AUTOCAL off is right, and for a stronger reason than §2.4 gives.** Infineon: "autocalibration should
  only be used in applications where the magnet regularly rotates by at least one full turn (internal TLE5012B
  check of full turn requires maximum 1.5 revolutions) at a temperature which is constant within 5 Kelvin"
  **[UM] §4, p. 23**; with it off "the default calibration parameters stored in the laser fuses will be used …
  and the angle error will fulfill the specifications" (p. 25). A joint with a hard stop never makes 1.5 turns, so
  on the arm autocalibration can never update. But the **E1000 ships with autocalibration mode 1 enabled**
  **[DS] §5.1, p. 45**, and upstream never writes a register (`main.cpp` only reads `0x8021`): at the *station*,
  where the unit does turn, it would adapt its volatile parameters, the fit would be made on the adapted curve,
  and the next power cycle on the arm would restore the fuse values. Forcing `AUTOCAL = 00` is therefore a
  precondition for transferability, not a trade. The price is the specification row that applies: **1.3° max over
  temperature at 0 h, 1.9° over temperature and life**, against 1.0° **[DS]** Table 11.
- **Temperature.** Infineon gives no coefficient, only that span (0.6° typ at 25 °C → 1.3° max over −40…150 °C).
  I will not scale it. Mechanisms: residual offset drift after the on-chip `TCO` correction (H1); GMR amplitude
  and anisotropy (H2); B₀ at ≈ −0.12 %/K (**[AN-GMR]** assumes −0.13 %/K) — harmless in itself, it only moves P1
  and P6; differential expansion Al 23 ppm/K vs PA12 ≈ 100 ppm/K over the ±7.5 mm screw span ≈ 0.6 µm/K — symmetric
  unless a screw slips, and then it is P4. Separately, the die heats itself: 14–16 mA × 5 V ≈ 75 mW × R_thJA
  150–200 K/W **[DS]** Tables 4, 29 ≈ **+11…16 K** above ambient, reached over minutes. A unit fitted 20 s after
  power-up at the station and used 30 min after power-up on the arm has already moved by more than 5 K.
  **Size relative to 0.02°: unknown — needs the bench (U9).**
- **Hysteresis.** ±0.05° typ, ±0.08° max about the mean at ≥ 33 mT, ±0.13° at 25–33 mT (TLE5014 proxy) — 2.5 to
  6.5 × R_MAX, present at every reversal (P5). The 6700 bearing's rings are stainless (martensitic grades are
  magnetically semi-hard) and the stationary outer ring sees the magnet's rotating field; its rotational
  hysteresis adds a lagging field component. My order-of-magnitude estimate is 0.02–0.1° **[R]**; it is measured
  together with the GMR's by U5.
- **Life.** 1.3° → 1.9° is Infineon's adder for automotive stress; **[AN-GMR]** Fig. 1 shows 0° life-time adder
  for ≤ 50 mT at ≤ 85 °C. For a hand-held device at room temperature I expect it to be small; unknown.
  Mechanical ageing (nylon creep under screw preload, moisture swelling of PA12) is the more likely drift: P4.
- **Supply.** No regulator on the PCB **[HW]**: the sensor's V_DD is the chain voltage minus the cable drop, so it
  differs between station and arm and along the chain (16 modules). The bridge/ADC are ratiometric and Infineon
  specifies no angle-vs-V_DD term inside 3.0–5.5 V. **Unknown — one bench sweep settles it (U10).**
- **Stray fields and ferromagnetic parts.** P1.

### 4.4 Is a static 6-harmonic function of the measured angle the right model?

**For everything that is static, yes — with margin.** Die errors are H1/H2 (+H4); misalignment of an Ø3 magnet
is H1/H2 with H3 ≤ 0.016°, H4 ≤ 0.005°, H5+ < 0.0002° **[SIM]** B. §7.6's test spectra (H3 = 20 %, H4–H6 up to
5 % of H1) are *more* pessimistic than the geometry produces, so the simulations' conclusion "six harmonics
reach the quantisation floor" is, if anything, conservative on that side (the die's own H4 remains O1).
**For everything else, no — and no number of harmonics would help**, because the missing inputs are not the
angle: rotation direction/history (P5), the pose of the arm and the neighbours' angles (P1), load (P4),
temperature and supply (P7). The model form is not the weakness; the claim attached to it is.

### 4.5 What would have to change — see the recommendations under each finding and the summary in §7.

---

## 5. Findings in detail

### P1 — BLOCKER — Stray fields at low B₀: a pose-dependent error of 0.05–0.3° that the method cannot remove

**Spec claim.** §7.2 (l. 826): `R_MAX` 0.02° is the "limit on the **true** systematic error of an accepted
part"; l. 883 "No part with true error above `R_MAX` was accepted"; §7.7 (l. 994) "a part accepted at `R_MAX` can
be off by up to about 0.02° + 0.014° ≈ 0.034° **absolute**"; `station-reference-encoder.md` §4 "模块真实系统误差上限
≈ 0.0215°". §2.7 (l. 233–236) limits the figures to "calibration conditions" but names only temperature and
direction.

**Issue.** A GMR sensor reports the direction of the *total* in-plane field. A stray field B_s adds
`atan(B_s/B₀)·sin(θ − θ_stray)` — an H1 term whose amplitude and phase belong to the world, not to the module.
At the station it is constant, the fit absorbs it into H1, and the out-of-sample gate *confirms* it. On the arm
it is different and keeps changing. The size is set by B₀, which an Ø3 mm magnet at ≈ 2.5–3 mm makes small.

**Quantification. [SIM] F, [HW], [R]**

| Stray in-plane field | B₀ 20 mT | 25 mT | 30 mT | 40 mT | 50 mT |
|---|---|---|---|---|---|
| 20 µT | 0.057° | 0.046° | 0.038° | 0.029° | 0.023° |
| 50 µT | 0.143° | 0.115° | 0.095° | 0.072° | 0.057° |
| 75 µT | 0.215° | 0.172° | 0.143° | 0.107° | 0.086° |
| 150 µT | 0.430° | 0.344° | 0.286° | 0.215° | 0.172° |
| **budget for 0.02°** | **7 µT** | | **10 µT** | | **17 µT** |

- *Earth's field*, ≈ 25–65 µT total (NOAA NCEI). Each of the 16 sensor planes points somewhere else and the
  operator moves them all, so the in-plane component runs from ≈ 0 to the full value. The error relative to the
  station fit is the *vector difference* between station and use: up to twice the rows above, typically about
  one row: **≈ 0.05–0.15°** at 25–30 mT. Indoors, steel furniture and tooling distort it further.
- *Neighbouring modules.* Dipole moment of an Ø3 × 3 N35 ≈ 0.020 A·m² (it rose 20 % with the new magnet, B₀ only
  7 %). At the CAD distances: 28.3 mm → 89–179 µT (equatorial…axial), 34.6 mm → 49–98 µT, 36.8 mm → 41–81 µT,
  42–53 mm → 14–53 µT, 79 mm → 4–8 µT. At B₀ = 30 mT that is **0.17–0.34°, 0.09–0.19°, 0.08–0.15°,
  0.03–0.10°, < 0.02°**. Where the neighbour's magnet is rigid relative to this sensor the term is a static H1
  that an *in-situ* fit could absorb; where a joint lies between them it varies with that joint's angle and
  cannot be fitted per module at all. Either way the single-module station (§3.4) never sees it. *Against:* each
  magnet sits inside a steel bearing that shunts part of its far field; these dipole figures are upper
  estimates — hence U7.
- *VRIG magnetic quick-release mount*, 75 mm from both J1 sensors: moment unknown. 1 A·m² (≈ 1 cm³ of NdFeB)
  would give ≈ 240 µT → 0.45° at 30 mT. **Unknown — needs a gaussmeter (U12).**

**Cross-check with the station-metrology review.** That reviewer's finding F8a (`2026-09-20-accuracy-review-station-metrology.md`;
figures as sent to me in a message — I have not read that file, it is outside my reading scope) assumes the same
mechanism: a lab-fixed in-plane field gives an H1 term of amplitude B_ext/B_magnet, fitted into the module at the
station, invisible to the gate because both passes see it, and up to 2× on the arm. **I confirm the mechanism and
the arithmetic**: 20 µT → 0.038° at 30 mT and 0.023° at 50 mT; 48 µT → 0.092° / 0.055° — identical to section F of
my script (`atan(B_s/B₀)`, which equals B_s/B₀ to four digits here). Two things this review adds, and which
should override F8a's open parameter: (i) **B_magnet is not 30–50 mT on this hardware but probably ≈ 23–32 mT**
(§4.2a, P6; bearing shunting would lower it further), so F8a's 30 mT column is the *optimistic* end — at 25 mT
the same 48 µT is 0.110°, at 20 mT 0.138°; (ii) the Earth's field is not the largest stray source on the arm —
the neighbouring modules' magnets are (bullet above), and they are absent at a single-module station altogether.
The two reviews do not contradict each other; read F8a's numbers with B_magnet from this review.

**Recommendation.**
1. Restate the claim (§7): 0.02° is the station's fit-repeatability gate; the in-use figure is what the arm-level
   check of P2 measures.
2. Measure B₀-sensitivity once per design at the station: repeat the validation pass with unit and fixture yawed
   180°, or with a known ±50 µT applied. The H1 change *is* `2·B_s/B₀`; it costs one extra pass (U6).
3. Calibrate in a field-quiet spot, away from steel and the stepper; record the station's orientation.
4. Hardware, if ≈ 0.1° is not good enough: raise B₀ to 45–50 mT (gap ≈ 2.0 mm for N35 — halves P1 and brings
   P6 into specification), or a larger magnet (also relaxes P4), or a soft-magnetic cup around magnet and sensor.

**Frozen items:** none affected.

### P2 — BLOCKER — Verified at the station only; nothing verifies or monitors accuracy on the arm

**Spec claim.** §7.2 step 7 validates "exactly what ships" (l. 866); §9.2 "The M5 cannot see calibration or
sensor state"; §9.3 CMD=3 "needs the M5 off the bus".

**Issue.** The user asks whether accuracy is *kept under control*. Control needs a measurement in the condition
of use. Every contribution in P1, P4, P5 and P7 is absent or frozen at the station by construction — one module,
one orientation, one approach direction, one temperature, no link load — and on the arm no reference exists and
no status reaches the M5. The M5's zero is taken at **one** jig pose, so whatever P1/P4/P5 amount to at that
instant is frozen into `jig_angle_offsets` as a constant per joint.

**Quantification.** The unverified part is 5–20 × the verified part (§1 table).

**Recommendation — no frozen item changes.**
1. **Arm-level verification through the normal CMD=2 stream, M5 untouched:** a second and third known jig pose
   (or a fixture that sets a known angle difference on each joint), approached from both sides. Report per joint
   `reading − known difference`. This is the only number that answers the user's question. Do it once per design
   on ≥ 2 arms, then on a sample.
2. Cross-talk and orientation tests on an assembled arm: U7, U6.
3. Periodic off-line health read with the M5 unplugged (§9.3) against the station record keyed by `SERNUM`:
   `GET_CAL_STATUS`, `GET_TRIM`, `GET_ENV`, `GET_DMAG` (gross faults only, P9). All subcommands exist.
4. Put the honest sentence into §7: *calibrated modules are verified to 0.02° against the station reference
   under station conditions; joint-angle accuracy on the arm is ≈ X°, measured by the multi-pose check.*

**Frozen items:** none. On-line monitoring (temperature or status in CMD=2 frames) *would* need the M5 and the
wire format to change; I do not recommend it.

### P3 — MAJOR (BLOCKER if violated) — The unit under calibration is undefined

**Spec claim.** §7.2 (l. 894) "the module is not on its joint yet"; `station-reference-encoder.md` §1 "与模块的磁铁轴
同轴刚性连接". Nowhere does the spec say whose magnet the sensor faces at the station, in what state of assembly,
or what voids a calibration. §7.7 step 1 and the station note §6 say turning the module "changes its own error",
which is not true of a sealed unit's geometry (P10) and suggests "module" was pictured as a PCB over a magnet.

**Issue / quantification.** §4.2(c): another magnet of the same type → 0.46–1.38°; a perfect master magnet →
1.16°; re-seating PCB or spacer by 0.1–0.2 mm → 0.17–1.26°. All indistinguishable from an uncalibrated unit, yet
the page still reads "valid, `N_HARM` = 6" and the M5 cannot tell. Any unit calibrated before the magnet change
would be void; none exists yet — keep it so.

**Recommendation (normative text for §7.2 and an assembly instruction).**
1. Calibrate only the **fully assembled `ENC_UNIT`** — its own horn, magnet (bonded, cured), bearing, spacer and
   PCB, screws at final torque with thread-locker — driven through its horn.
2. After calibration the four parts between magnet and die are not loosened. Paint-mark the spacer and PCB
   screws; a broken mark means recalibrate. UPDI re-flashing uses the connector and needs no disassembly.
3. Record in the station database (keyed by `SERNUM`, as §5.1 already does for temperature): magnet lot/size,
   H1…H6 before rounding, `GET_DMAG`, `GET_ENV`, V_DD, σ per reading, the CW–CCW difference (P5).
4. Confirm that the bare unit turns 360° at the station (U13). If it does not, §7.2's uniform full-circle grid
   is impossible and the procedure needs a partial-arc variant with its own operating characteristic.

**Frozen items:** none; `STATION_ID` and `CAL_DAY` already tie a page to a station record.

### P4 — MAJOR — 3–12 µm stability demanded of one ball bearing and a printed nylon spacer

**Spec claim.** None: the spec treats the error curve as a property of the part (O1: "measured raw error of real
modules").

**Issue.** §4.2(b): 3–4 µm (loose) or 9–12 µm (tight) of relative radial motion uses up 0.02°. The rotor runs in
a **single** 10 × 15 × 4 mm deep-groove bearing **[HW]** that also carries the link's moment loads. Radial
internal clearance for this size is typically 2–13 µm (ISO normal group — quoted from memory; MISUMI's page was
not retrievable: U11), plus the journal and seat fits if they are slip fits; a single-row bearing tilts freely by
several arc-minutes within its clearance (≈ ±0.1° by my estimate from a 47 µm axial play over a 12.5 mm pitch
circle **[R]**). At the station the rotor sits where the coupling pushes it; on the arm it sits where gravity and
the operator's hand push it, and it moves as they change. The sensor side is a PA12 printed spacer clamped by
two M2 screws in clearance holes: creep, moisture swelling (a few 10 µm over 7.5 mm, symmetric until one screw
slips) and thermal cycling all act at the µm level.

**Quantification. [SIM] C** Load-dependent error ≈ 0.01–0.06° (5–10 µm radial) plus 0.01–0.025° (0.1° tilt).
*In favour of the design:* the magnet sits inside the bearing's axial span, so tilt produces almost no lateral
magnet motion — the lever arm is < 1 mm.

**Recommendation.** (i) Measure it: at the station, hang 1–5 N on a 50 mm arm from the horn in four directions
at a fixed reference angle and read the change (U8). (ii) Centre the sensor: the sensitivity is proportional to
the existing eccentricity, and the station already measures it for free — H2 of the fit ≈ 5.0°·e² (e in mm, gap
2.5). Add an **H2 acceptance limit** (e.g. H2 ≤ 0.05° ⇔ e ≤ 0.1 mm) so that loose builds are re-seated and
re-run rather than shipped with a fragile calibration; likewise an H1 limit for magnet seating. (iii) Locating
pins or a machined spacer, and a preloaded bearing pair, are hardware options. **Frozen items:** none.

### P5 — MAJOR — One approach direction on a hysteretic sensor

**Spec claim.** §7.2 step 1 (l. 837) "Approach **every** position from the same rotation direction (§2.7:
hysteresis)"; §2.7 (l. 233) "direction-dependent hysteresis remain[s]".

**Issue.** The spec names the effect and then calibrates one branch of the loop. A leader arm reverses
constantly, so in use the reading wanders between both branches while the correction (and the M5 zero) sit on
one: the error is the *full* hysteresis width one way and zero the other, instead of ± half. Infineon's own
end-of-line procedure for the same iGMR bridges turns 360° left, 360° right, and takes the **mean** of the two
parameter sets **[AN-CAL] §2, p. 9**.

**Quantification.** TLE5014 (same iGMR technology): 0.10° typ / 0.16° max between directions at 33–80 mT, +0.1°
at 25–33 mT **[DS-5014]** Tables 3-11/3-12, p. 20; **[AN-GMR]** attributes the low-field adder partly to
hysteresis. The TLE5012B sheet does not separate it (Table 11 note 2). Bearing-ring hysteresis comes on top
(§4.3). Expect **0.1–0.25° between directions**, i.e. 5–12 × R_MAX. Backlash in the station's coupling looks the
same, which is why `station-reference-encoder.md` §7 rightly demands a bellows coupling.

**Recommendation (host side only).** Two fit passes, CW and CCW; fit the mean curve; record the CW–CCW
half-difference as a per-unit figure with its own acceptance limit; validate both directions against the mean.
State the in-use claim as "± half the recorded hysteresis". Costs one more minute per unit. **Frozen items:**
none. Compensating hysteresis in firmware would need direction state and a coefficient — LAYOUT_VER 2 — and works
poorly for small reversals; not recommended.

### P6 — MAJOR — B₀ probably at or under the 30 mT minimum; the in-spec window is 0.7 mm wide

**Spec claim.** None; §2.7 quotes the accuracy rows without their field condition.

**Issue / quantification.** §4.2(a). Table 11 "refers to B_Z = 0 mT and the operating conditions given in
Table 4", and Table 4's values "refer to a homogeneous magnetic field" of 30–50 mT **[DS]**. For Ø3 × 3 that
means a gap of 1.93–2.60 mm (N35) … 2.17–2.87 mm (N52), −6.7 %/0.1 mm. My CAD-derived gap of 2.5–3.0 mm gives
23–32 mT before the bearing's shunting. If true, the unit runs in Infineon's +0.1…+0.2° region, the part of that
which is hysteresis cannot be fitted, and P1 is a third worse than it has to be.

**Recommendation.** Measure B₀ once (U3). If it is under ≈ 35 mT, close the gap toward ≈ 2.0–2.2 mm (thinner
spacer — the 0.5 mm the new magnet added could have gone this way) or specify N48–N52; the target is the upper
half of the range, ≈ 40–50 mT at 25 °C, which leaves margin for −0.12 %/K and for gap tolerance. Let O1 include
it. **Frozen items:** none.

### P7 — MAJOR (unquantified) — Temperature, self-heating and supply

**Spec claim.** §2.7 (l. 236) "the calibrated accuracy figures in this document apply at calibration conditions";
§7.2 step 1 records ambient and module temperature; §5.1 dropped calibration temperature from USERROW into the
station's records.

**Issue.** That is honest, but the arm is never at calibration conditions: die self-heating ≈ +11–16 K over the
first minutes, ambient 15–35 °C, V_DD unregulated and different at each chain position (§4.3). Infineon
publishes no coefficient for either. I cannot say whether this is 0.005° or 0.05°.

**Recommendation (host side).** (i) Warm up ≥ 10 min, or until `GET_ENV` index 0 is stable to 1 K, before the
fit; make it a normative step. (ii) Characterise ≥ 5 units once: validation pass at ≈ 15 °C and ≈ 40 °C, and a
V_DD sweep 4.5–5.5 V at fixed angle (U9, U10). (iii) State the claim with the measured window. **Frozen items:**
none. Temperature-dependent coefficients would not fit the full USERROW; do not go there unless U9 forces it.

### P8 — MINOR — Datasheet facts that do not match the part on the BOM

- **O1 (l. 1210) "The datasheet bounds it at 1.6°"** and §6.2 (l. 788) "≤ 1.6° raw error". The datasheet bounds
  the *die in a homogeneous 30–50 mT field*; magnet and mounting are explicitly additional (**[AN-MDT]** p. 6:
  "The assembly error can be calculated in the tool and be added to the specified angle error from the data
  sheet"). With an Ø3 magnet the assembly term alone reaches ≈ 1.5°; 2–3° raw is plausible. Harmless for the
  format (±5.6°) and already covered by the 2.5° case in `station_sim.py`, but O1's premise is wrong. The current
  sheet (Rev. 2.1, 2018-06) also reads **1.3° (0 h) / 1.9° (life)**, not 1.6° (V1.1, 2012).
- **§2.4 "FIRMD 2 — the default (D16)" and D16 "(upstream's dynamics)".** The BOM part is the **E1000**:
  "preconfigured for … fast angle update period (42.7 µs) … Autocalibration mode 1 enabled. Prediction enabled"
  **[DS] §5.1, p. 45**, and upstream writes nothing. Upstream therefore runs FIR_MD 1 + prediction + autocal; the
  fork changes all three. Writing them explicitly is right; calling it the default is not. Rev. 2.1 Table 12
  gives the SSC angle delay as 150–165 µs at FIR_MD 2 without prediction (45–50 µs for upstream's setting), not
  §2.7's 80–95 µs: ≈ 0.03° of lag at 180°/s — a system-timing matter, passed to that reviewer.
- §2.7 should quote the field condition (30–50 mT, homogeneous, B_Z = 0) next to the accuracy rows.

### P9 — MINOR — `D_MAG` is not a field or air-gap monitor

`MAG = SQRT(X·X + Y·Y)/64` after error compensation **[UM] p. 98–99**: the length of the GMR *signal* vector. A
spin-valve bridge in saturation responds to field direction, not strength, so `D_MAG` tracks GMR amplitude
(mainly temperature) and collapses only when the magnet is missing or far too weak (`S_MAGOL`). It will not show
0.1 mm of gap or a 10 % change of B₀. Keep it as a gross-fault indicator; use H2/H1 from the fit (P4) and a
gaussmeter (U3) for what the brief hoped `D_MAG` would do.

### P10 — MINOR — §7.7 step 1 contradicts a sealed unit, and thereby concedes P1

§7.7 (l. 1001) "The module is **not** turned, because turning it changes its own error";
`station-reference-encoder.md` §6 "转动模块会改变传感器与磁铁的相对位置". For a sealed unit driven through its horn,
re-clocking it changes no sensor–magnet geometry. What *does* change is the direction of the ambient field in the
sensor's frame and the direction of the coupling's side load — P1 and P4. The instruction is sound; the reason
should be corrected, because as written it says the module's error depends on its orientation in the room, which
on an arm changes continuously.

---

## 6. Unknowns — each needs a measurement or an answer

| # | Unknown | How to settle it |
|---|---|---|
| U1 | Magnet as built: grade, diameter/length tolerance, magnetisation-tilt sorting, pocket depth after the change (published CAD: 2.5 mm — a 3 mm part would stand 0.5 mm proud), adhesive | user / supplier data; callipers |
| U2 | Gap, magnet face → package top, as built; die depth below the package top | feeler or CAD of the current revision; TLE5012B data sheet Fig. 39 (p. 48, drawing) |
| U3 | **B₀ at the die, with the bearing in place** | Hall probe on a dummy PCB at the die position; or FEM with the 6700 rings. Decides P1 and P6 |
| U4 | Raw error curves of ≥ 10 assembled units, H1…H8 (this is O1) | first station runs; tells whether builds are "loose" or "tight" |
| U5 | CW versus CCW curve at the station | one extra pass; expect 0.1–0.25° between directions |
| U6 | Sensitivity to ambient field | validation pass repeated with unit + fixture yawed 180°, or ±50 µT from a coil; expect ΔH1 ≈ 2·B_s/B₀ |
| U7 | Cross-talk on an assembled arm | clamp joint A, sweep neighbour B through its range, log A through the normal stream; expect up to 0.1–0.3° on J1/J2, J3/J4, J5–J7 |
| U8 | Load sensitivity | 1–5 N at 50 mm on the horn, four directions, fixed reference angle; expect 0.01–0.08° |
| U9 | Temperature and warm-up | validation at ≈ 15 °C and ≈ 40 °C; log output at a fixed angle for 15 min from power-on |
| U10 | Supply sensitivity; real V_DD at chain positions 1 and 16 | 4.5–5.5 V sweep at fixed angle; multimeter on the arm |
| U11 | Bearing clearance class and ring material; journal/seat fits (press, slip, bonded?) | MISUMI data sheet for C-FL6700ZZ; drawings |
| U12 | Stray field of the VRIG magnetic mount at J1/J2; material of the M2-10 frame screws | gaussmeter; a magnet on a screw |
| U13 | Can a bare `ENC_UNIT` turn 360° at the station? | try one |
| U14 | The in-use figure itself | multi-pose check of P2 on ≥ 2 arms |

## 7. What would make the claim hold — summary

| Change | Where | Frozen items |
|---|---|---|
| Define the unit under calibration; seal it; void on disassembly (P3) | §7.2 text, assembly instruction | none |
| CW + CCW passes, fit the mean, record and gate hysteresis (P5) | `kercal` / §7.2 | none |
| Warm-up step; record V_DD, `D_MAG`, σ, H1…H6 per `SERNUM` (P7, P3) | `kercal` / station DB | none |
| H2 (and H1) acceptance limits as a centring gate (P4) | `kercal` / §7.2 | none |
| One-off characterisation U5–U10; B₀ measurement U3 | bench | none |
| Multi-pose verification on the assembled arm via the normal stream (P2) | jig + host script | none — M5 unmodified |
| Restate the claim: 0.02° = station gate; in-use = measured figure (P1, P2) | §2.7, §7.2, §7.7, reference note §4 | none |
| Correct §2.4, §2.7, O1, D16, §7.7 step 1 wording (P8, P10) | spec text | none |
| *Optional hardware:* B₀ → 40–50 mT, larger magnet, shield cup, spacer with locating pins, bearing pair | mechanics | none (not protocol) |
| *Not recommended:* temperature- or direction-dependent coefficients; status in CMD=2 frames | — | would force LAYOUT_VER 2 / M5 change |

## 8. What the design gets right

- **AUTOCAL forced off** — required by Infineon's own guidance for a joint that never makes a full turn, and
  required for transferability because the E1000 ships with it on (§4.3).
- **The model form.** Static error of this hardware is H1/H2 with a rapidly vanishing tail; six harmonics of the
  measured angle are ample, and the simulated spectra are more pessimistic than the geometry.
- **The hardware it rests on.** The magnet travels with the unit; the magnet sits inside the bearing's span so
  tilt barely moves it; the unit's screws are specified non-magnetic; housing and horn are aluminium.
- **Out-of-sample, averaged validation on the committed output** is the right station gate, and the half-range
  statistic with the offset left to the M5 is correct. It certifies the fit, which is worth certifying.
- §2.7 already says the figures "apply at calibration conditions" and names temperature and hysteresis. The
  finding is not that the spec hides this; it is that the conditions it names are a small part of what differs
  on the arm, and that the number carried forward into §7.7 and the reference note is called "true"/"absolute".
- `GET_SAMPLE` carries Σx² and `GET_ENV`/`GET_DMAG`/`GET_TRIM` exist, so every station-side recommendation
  above needs **no new subcommand**.

## 9. Limits of this review

Point-sensor model; no soft-magnetic parts (bearing) in the field model — B₀ is overestimated and neighbour
fields are upper estimates; the gap comes from a published CAD that pre-dates the magnet change plus an assumed
die depth; TLE5014 hysteresis is used as a proxy for the TLE5012B; bearing clearance is quoted from memory;
"loose" and "tight" builds are my tolerance guesses bracketing data-sheet and BOM limits. Every number tagged
**[R]** is an order of magnitude. The direction of the conclusions does not depend on any one of them: P1 holds
for any B₀ the TLE5012B permits — even at 70 mT, its absolute upper limit, 50 µT of stray field is 0.04°.

## Sources

| Tag | Document | Used |
|---|---|---|
| [DS] | Infineon TLE5012B Data Sheet Rev. 2.1, 2018-06-20 — https://www.infineon.com/assets/row/public/documents/24/49/infineon-tle5012b-exxxx-datasheet-en.pdf?fileId=db3a304334fac4c601350f31c43c433f | Table 4 + notes (p. 16–17); Table 10 (p. 20); §4.3.4, Table 11 + notes (p. 21); §4.3.5 (p. 22); Table 12 (p. 24); §5.1 (p. 45); Table 29 (p. 47); Table 30 (p. 48) |
| [UM] | TLE5012B User's Manual Rev. 1.2, 2018-02 — https://www.farnell.com/datasheets/2700287.pdf | §4 autocalibration (p. 23, 25); `D_MAG` register (p. 98–99) |
| [AN-GMR] | "GMR Accuracy Extension", AN V1.0, 2011-04-21 — http://comm.eefocus.com/media/download/index/id-201832 | §1.1–1.2, Fig. 1–2 (p. 6–7); Fig. 3 (p. 9) |
| [AN-MDT] | "Magnetic Design Tool — Angle Sensors", AN V1.0, 2014-12-03 — https://design.infineon.com/sensor/anglesim/pdf/AppNote_MagneticDesignTool-AngleSensors.pdf | §1 (p. 6); §2.3 (p. 9–10); §3 (p. 11); §3.2 (p. 12); refs to Ausserlechner, IEEE Trans. Magn. 45(5), 2009 (p. 13) |
| [AN-CAL] | "TLE5009 Calibration", AN V1.0, 2010-12-21 — https://www.farnell.com/datasheets/2254286.pdf | §2 calibration routine (p. 9) |
| [DS-5014] | TLE5014 Final Datasheet Rev. 1.0, 2018-04-04 — https://www.infineon.com/assets/row/public/documents/24/49/infineon-tle5014c-p-s-datasheet-en.pdf?fileId=5546d46276fb756a01771a9695b43a08 | Tables 3-11, 3-12 (p. 20) |
| [HW] | OpenArm KER docs — https://docs.openarm.dev/hardware/openarm-ker/general , …/encoder-module (text and exploded-view image), …/calibration-workflow | module composition; single jig pose |
| [HW] | OpenArm KER Google Drive (linked from the page above; file ids in `enactic/openarm_hardware` `dev/google-drive-files/file-ids.tsv`): `OpenArm KER BOM.xlsx`, `OpenArm KER.STEP` (2026-06-04), `Elec/PCB/Encoder/TLE_BOM.xlsx`, `TLE_V3_BOM.csv` | BOM rows; geometry of §3; PCB parts |
| — | MISUMI C-FL6700ZZ, product title "Small Ball Bearing/Double Shielded/Stainless with Flange" — https://sg.misumi-ec.com/vona2/detail/110302590820/?HissuCode=C-FL6700ZZ (page body returned HTTP 403) | bearing type only |
| — | NOAA NCEI Geomagnetism FAQ — https://www.ncei.noaa.gov/products/geomagnetism-frequently-asked-questions | Earth's field ≈ 25–65 µT |
| [SIM] | `encoder/docs/evidence/v5-accuracy-review-scripts/physics_magnet_model.py`, output `physics_magnet_model.txt`, sections A–F | all simulated numbers |
