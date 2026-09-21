# Accuracy review — system error budget and lifecycle control (spec v5)

| | |
|---|---|
| Date | 2026-09-20 |
| Reviewer role | independent; systems engineering / end-to-end error budget and quality control |
| Subject | `encoder/docs/protocol-spec.md` v5 (no firmware exists), against the unmodified upstream `encoder/src/main.cpp` and `M5/` |
| Question | **"Can the current method really control and improve the sensor's system accuracy?"** |
| Files read | `protocol-spec.md`, `station-reference-encoder.md`, `encoder/src/main.cpp`, `M5/src/{main,RSNexus,USBStream,SerialStream}.cpp`, `M5/include/{Common,RSNexus}.h`, `README.md`; with the coordinator's explicit extension: `M5/include/AngleProcessor.h`, and two constants from `M5/include/USBStream.h`. OpenArm docs pages cited in §4. Nothing else. |
| Not covered | TLE5012B / magnet physics and the reference encoder's metrology (two other reviewers). Where the budget needs those magnitudes they are carried as labelled assumptions. |
| Evidence | `encoder/docs/evidence/v5-accuracy-review-scripts/system_budget.py`, `system_float32_unwrap_drift.py`, outputs in `…/results/system_*.txt`. Run with `encoder/.venv/bin/python`. Everything is arithmetic or simulation; **nothing in this review is a bench measurement.** |

---

## 1. Verdict

**Improve — yes, but by about 5–7×, not the 30× that "0.6° → 0.02°" suggests. Control — no, not as designed.**

The harmonic calibration does what it says: it removes the repeatable part of the sensor's systematic
error, and the station gate is statistically sound *relative to the station and at station conditions*.
At system level that term stops mattering the moment it is removed. After calibration the host-side joint
angle is dominated by four terms the design does not touch, each of them 2.5–5× larger than `R_MAX`:
the M5 zeroes each joint on **one** noisy reading (0.05° 1σ frozen in), per-reading noise (0.05° 1σ) reaches
the host unfiltered, the jig's mechanical repeatability and the uncalibrated temperature/hysteresis part
(both unquantified, assumed ≥ 0.05–0.1°), and — whenever the arm moves faster than ≈ 11°/s — ≈ 1.8 ms of
data age that the stream's timestamp does not describe. The calibrated residual is **0.7 % of the
after-calibration variance**; any gate between 0.01° and 0.05° gives the same system number to within 2 %.
Realistic in-use figures: **static 0.61° → ≈ 0.09–0.13°** (1σ-equivalent per joint); **moving at 60°/s
0.62° → 0.17°; at 180°/s 0.70° → 0.35°**. With four cheap host-side/procedural measures and one one-line
module change (§5) the static figure becomes ≈ 0.05° plus whatever the jig contributes, and the moving
figure stops depending on speed. None of those needs a protocol, layout or M5 change.

"Control" is the weak half. Once a module leaves the station **nothing in the running system can observe
its accuracy, its calibration state or its health**: the unmodified M5 forwards only the angle, its
`error_mask` means "never seen since boot" and nothing else, the design's own fallbacks (compensation
suspended, value held) are silent by construction, `D_MAG` has no baseline or threshold, there is no
re-calibration trigger and no field procedure that could detect a lost calibration. One new problem is
*introduced* by calibration: the compensated output, fed through the M5's float32 incremental unwrap,
produces a systematic drift of up to 0.02–0.15°/h in some joint configurations that uncalibrated modules do
not have (finding S3; one-line fix on the module).

### 1.1 Before / after budget

Measurand: joint angle relative to the jig zero, as the host receives it in `angles[]`, against the true
mechanical angle **at the instant given by the frame's `timestamp`**. Per joint, single received sample,
1σ-equivalent, RSS. Source: `system_budget.py` → `results/system_budget.txt`.

| Term | Before | After (v5 as designed) | After + §5 measures R1–R5 | Basis |
|---|---|---|---|---|
| Sensor systematic, seen from a one-point zero | 0.60 (typ) / 1.6 (max) | 0.011 (gate 0.02° half-range; worst case 0.04°) | 0.011 | spec §2.7, §7.2; conversion in script |
| Station reference, as delivered ±50″ | — | 0.014 | 0.014 (0.0014 if §7.7 works) | spec §7.7 |
| Per-reading noise | 0.050 | 0.050 | 0.011 (host filter, 25 Hz noise bandwidth) | spec §2.7; no filter anywhere, S5 |
| Zero: one reading frozen into the offset | 0.050 | 0.050 | 0.002 (host zero-trim) | `M5/src/main.cpp:238-241`, S4 |
| Zero: jig mechanical repeatability | 0.10 **assumed** | 0.10 **assumed** | 0.10 **assumed** | unknown U2 |
| Temperature + hysteresis + ageing not removed by a static fit | 0.05 **assumed** | 0.05 **assumed** (pessimistic 0.20) | same | spec §2.7 gives no split; upper bound 1.6 − 0.6 = 1.0°; owned by the sensor-physics review |
| M5 float32 accumulation | 0 | 0 … 0.15 **per hour**, configuration-dependent | 0 (output rounded to 8 LSB) | `AngleProcessor.h:68-72`, S3 |
| Bit-replication ramp / fixed-point arithmetic | 0.003 | 0.001 | 0.002 | spec §1.7, §7.5 |
| **Static RSS** | **0.61** | **0.13** (0.24 pessimistic) | **0.11** | |
| **Static RSS without the jig term** (relative accuracy) | **0.61** | **0.088** | **0.054** | |
| Unmodelled data age, mean 1.81 ms (module 1: 2.04, module 16: 1.59) | ω × 1.81 ms | same | ω × ±50 µs after host time-alignment | S6 |
| **Moving, 60°/s** | **0.62** | **0.17** | **0.11** | |
| **Moving, 180°/s** | **0.70** | **0.35** | **0.11** | |
| **Moving, 360°/s** | **0.90** | **0.67** | **0.11** | |

Drift from S3 is not included in the RSS rows because it grows with time; it is listed separately.

Assumptions, stated once:

- **Joint speeds** (assumption, not measured): fine positioning ≤ 10°/s; careful manipulation 30–60°/s;
  transit 180°/s; fast reach 360°/s. Derivation: a minimum-jerk move peaks at 1.875 × its mean speed, so a
  90° reach in 0.5 s peaks at 340°/s and a 30° adjustment in 1 s at 56°/s. The user can replace this with
  a histogram from any recorded session, since the host already receives 1 kHz angles (U8).
- **M5 loop period 1 ms**: `vTaskDelay(pdMS_TO_TICKS(1))` at `M5/src/main.cpp:255` is one tick only if
  `CONFIG_FREERTOS_HZ` = 1000, the Arduino-ESP32 default; I did not read the SDK configuration. If the tick
  were slower the delay degenerates to a yield and the age drops to ≈ 1.1 ms (U6).
- Cascade timing (20 µs frame, ≈ 30 µs per hop) is the spec's §8.1 model, itself unmeasured.
- 1σ-equivalent of a systematic curve with half-range *h*, seen from a zero at an arbitrary point: *h* for a
  single dominant harmonic (uncalibrated), 0.57 *h* for a broadband fit residual.
- The host applies no filter, no zero trim and no time alignment. The host software is not in this
  repository, so this is the conservative default (U3).

---

## 2. Findings

| ID | Severity | Title |
|---|---|---|
| S1 | **BLOCKER** (for the "control" half of the claim) | In-use accuracy is unverifiable and loss of calibration is invisible: no status reaches anyone, no field check exists, and the design's fallbacks are silent |
| S2 | **MAJOR** — BLOCKER if the answer to U1 is "no" | The spec never states that the unit calibrated at the station (sensor + magnet + bearing seat) is the unit that runs on the joint |
| S3 | **MAJOR** | Calibrated output × the M5's float32 incremental unwrap = systematic drift, up to 0.02–0.15°/h; uncalibrated modules are immune. One-line module-side fix |
| S4 | **MAJOR** | Jig zero is a single noisy reading: 0.05° 1σ (2.5 × `R_MAX`) frozen into every joint until the next zeroing |
| S5 | **MAJOR** | Per-reading noise (2.5 × `R_MAX`) is unfiltered end to end; after calibration the received sample is noise-limited |
| S6 | **MAJOR** | ≈ 1.6–2.0 ms of data age is not described by the stream's timestamp; above ≈ 11°/s it exceeds `R_MAX` |
| S7 | **MAJOR** | No lifecycle control: `D_MAG`/temperature have no baseline or threshold, no re-calibration trigger, records miss the quantities needed later |
| S8 | **MAJOR** | A rejected part is reverted to an identity page — 15–80× worse for the system than the calibration it was rejected for, and indistinguishable in the field |
| S9 | MINOR | `R_MAX` = 0.02° is below the knee: 0.7 % of the variance; the 8-mount reference self-calibration buys < 1 % at system level |
| S10 | MINOR | Inter-module sampling skew: 450 µs end to end, 180 µs within one arm |
| S11 | MINOR | No frame check on the bus: sub-30° corrupt values pass to the host for one frame |
| S12 | MINOR | Traceability is adequate only while the station database survives and is reachable from where service happens |

---

## 3. Findings in detail

### S1 — In-use accuracy is unverifiable; loss of calibration is invisible  (BLOCKER for "control")

**Spec.** §9.2 states it plainly: "The M5 cannot see calibration or sensor state … visible only through
CMD=3, off-arm." §9.3: CMD=3 needs the M5 off the bus *with the modules still powered*; whether that is
possible is open (O4). §6.2 defines three silent fallbacks. No section defines a field verification.

**Issue.** Accuracy is established once, at the station, under station conditions. After that the system
has no observer:

1. *The only status the host gets is meaningless after boot.* `error_mask` is built from
   `snapshot.sensors[i].error` (`M5/src/main.cpp:479-487`), which is `!rs485nexus.isValid()`
   (`:151,171,175`). `_valid[idx]` is set on the first frame (`M5/src/RSNexus.cpp:87`) and never cleared
   anywhere in the class; `_last_seen` is written (`RSNexus.cpp:88`) but `getLastSeen()` is never called
   in `main.cpp`. A module that dies, or a cascade that breaks at module *n*, leaves modules *n*…16
   streaming their last value forever with `error = 0`.
2. *The design's own fallbacks are silent.* (a) Config-lock failure → compensation suspended, output
   reverts to the raw mapping (§6.2): the angle steps by up to Σ|A_k| (0.6–1.6° for a datasheet part),
   accuracy silently reverts to "before", and steps back when the lock succeeds. (b) Failed read → previous
   value held (`ANGLE_STALE`): at 180°/s a 20 ms hold is a 3.6° error. (c) No valid read since reset →
   module sends 0. (d) Invalid page → module boots as ID 31, is inert, and the cascade stops there. The
   flags for all four exist (`GET_HEALTH` bits 0, 2, 7, 12, 13) and nobody on an assembled arm can read
   them.
3. *Reading them needs a capability that is an open question.* §9.3/O4: M5 powered down or unplugged,
   modules still powered. If the modules take power through the M5, on-arm diagnostics do not exist, and
   the RAM counters are lost on the power cycle anyway (§3.3).
4. *No field procedure.* Nothing in the spec says how a user or service technician would find out that a
   joint is no longer within any tolerance — 0.02° or 2°.

**Quantification.** Undetected states and their size: suspended compensation 0.6–1.6° (step); wrong or
missing zero after a module swap: the compensation value at the jig pose, up to 0.6–1.6° (§9.1 requires
re-zeroing but nothing checks it); identity page after rejection 0.6–1.6° (S8); frozen channel: unbounded.
All are 30–80 × `R_MAX`.

**What the unmodified M5 *does* offer, for free:**

- **The sensor's noise is a heartbeat.** A live channel dithers: with 0.05° noise on a 0.011° code the
  probability that two consecutive readings are the same code is ≈ 0.06, so 50 identical consecutive values
  have probability ≈ 10⁻⁵⁹ (still < 10⁻²⁴ if the real noise were five times lower). A host-side rule "channel bit-identical for > 50 frames ⇒ frozen" detects a dead
  module, a broken cascade, a held (`ANGLE_STALE`) value and a module sending 0 — with zero firmware change.
  (Threshold > 20 because the M5 itself substitutes the last good angle for up to 19 frames,
  `M5/src/main.cpp:203-213`.)
- **The jump detector is an in-band fault channel.** 20 consecutive frames ≥ 30° away from the last good
  angle put the M5 into STANDBY with "Jump Detected CHn" on the screen (`main.cpp:201-211,284-309`), and the
  M5 substitutes the last good angle meanwhile (`:213`), so the follower never sees the excursion. A module
  that adds 180° to its output while a fault *persists* therefore stops the stream and names the channel.
  Caveats: not on ch8/ch16 (`Common.h:97,106`), not with jump detection toggled off, not in STANDBY; and it
  reverses decision D18 (pass a degraded angle through). This is a product decision — a leader arm that
  stops on a persistent sensor fault is arguably the right behaviour — and I only note that it is the one
  signalling path that exists.
- **A status side-channel in the angle's low bits is *not* viable**: the M5 accumulates float32 increments
  (`AngleProcessor.h:68-72`) and subtracts a float offset, so low-order bits do not survive.

**Recommended change.**

1. Define a **field verification** (new §9.5, procedure only): *return-to-jig residual*. With the arm back
   in the jig, the host averages 1 s per joint; the value must equal `mech_joint_offset` (`Common.h:90-106`)
   plus the stored zero trim (S4) within a tolerance set from U2. Logged at the start and end of a session
   this catches S3 drift, thermal drift, a slipped magnet, a forgotten re-zero and a suspended compensation
   (if it persists). It verifies to the jig's repeatability (≈ 0.1°?), **not** to 0.02° — and that is the
   honest in-use claim.
2. Host-side frozen-channel detector and `seq`-gap check (the stream already carries `seq`,
   `main.cpp:395,488`).
3. Close O4 with a service adapter that powers the modules without an M5, and make "read `GET_HEALTH`,
   `GET_CAL_STATUS`, `GET_CFG_VERIFY`, `GET_DMAG`, `GET_ENV`, `GET_ERRCNT` of every module" a step of
   arm assembly and of every service visit. Note that the sticky bits and counters are RAM: they describe
   only the time since the last power-up.
4. Decide deliberately whether persistent faults should trip the M5's jump detector.

**Frozen items.** None forced. Items 1–3 are procedure, host software and a cable. Item 4 changes §6.2/D18
behaviour only, not the wire format.

---

### S2 — What exactly is calibrated is never specified  (MAJOR; BLOCKER if U1 = "no")

**Spec.** §7.2 step 1: "One module on the bus." §7.2 "Why steps 4 and 5": "the module is not on its joint
yet." §7.7: the module "is **not** turned, because turning it changes its own error";
`station-reference-encoder.md:7` couples the reference to "the module's magnet shaft", and `:79` says
turning the module "changes the relative position of sensor and magnet, the module's own error changes."

**Issue.** The spec itself says the error curve belongs to the *sensor–magnet geometry*, not to the chip.
The six harmonics fitted at the station are therefore valid on the arm only if the **same magnet in the
same seat at the same air gap and eccentricity** goes with the PCB to the joint. OpenArm's documentation
describes the module as integrating "a hardware limit, bearings, a magnetic encoder, and a driver"
(https://docs.openarm.dev/hardware/openarm-ker/encoder-module), which suggests a captive shaft and magnet —
but the user also refers to a "joint magnet" (Ø3 mm diametric, thickness recently changed 2.5 → 3 mm, air
gap unchanged), and nothing in the spec requires, records or checks captivity. If the magnet is mounted on
the joint and the PCB is calibrated against a station magnet, the correction written to USERROW is that of
the station's geometry: the magnet-related part of the error on the joint is uncorrected, and a wrong
correction of similar size is added to it (RSS up to √2 × the uncalibrated magnet-related error). I cannot
size the magnet-related share — that is the sensor-physics reviewer's — but at system level the outcome is
binary: either the calibration transfers, or the "after" column above is void.

Even with a captive magnet two things break the transfer: (a) any later disassembly of PCB, magnet or
bearing (repair, magnet revision such as the 2.5 → 3 mm change) — modules calibrated before such a change
must be treated as uncalibrated; (b) joint loads carried through the module's own bearings ("hardware
limit, bearings") shifting the magnet relative to the sensor by the bearing clearance, which the unloaded
station never sees.

**Recommended change.** State in §7.2 step 1 that the calibrated unit is the assembled module including
its magnet and that the calibration is void after any disassembly; have the station record the mechanical
revision; add one station experiment: calibrate, apply a radial load to the shaft comparable to arm use,
re-run the validation pass only (≈ 30 s) and record the change (U1b). Use `D_MAG` (S7) as the tamper / shift
indicator.

**Frozen items.** None.

---

### S3 — Calibrated output makes the M5's float32 unwrap drift  (MAJOR)

**Spec.** §7.1: `u_out = ((raw15 << 6) + Δ) mod 2²¹`. §9: "The M5's code needs no change."

**Issue.** The M5 converts the 21-bit value to float32 degrees (`M5/src/RSNexus.cpp:85`) — harmless, the
float32 step below 360° is ≤ 3.05 × 10⁻⁵° against an LSB of 1.72 × 10⁻⁴° — and then **integrates
differences** every cycle: `diff = raw − _last_raw; … _unwrapped += diff` (`M5/include/AngleProcessor.h:68-72`).
`_unwrapped` is re-referenced to the absolute reading only on the first call after boot or zeroing
(`:57-66`, `reset()` at `:80-84`). Every rounding of that `+=` therefore stays.

With the **upstream** mapping consecutive readings differ by multiples of 64 LSB, i.e. multiples of
45/4096°, which are exact in float32 at any magnitude below 512°: every add is exact and there is no drift.
The **calibrated** output differs by arbitrary LSB counts. When the magnet angle at the sensor is small
(raw < 64°) and the joint is far from its zero (|angle − zero| ≥ 128°), increments carry fractions of ¼, ½,
¾ of the accumulator's float step; round-half-to-even is not symmetric over the back-and-forth paths that
sensor noise produces, and the result is a **bias**, not a random walk.

**Quantification** (`system_float32_unwrap_drift.py`; bit-faithful float32 model; drift of the worst case
reproduced with an independent scalar loop, −0.0032° in 10 min):

| Mapping | Stationary, 8 × 8 grid, after 1 h | Moving ±25°, after 1 h | 8 h, worst case tried |
|---|---|---|---|
| upstream (uncalibrated) | 0 in 64/64 cells | ≤ 0.00003° | 0.00003° |
| calibrated, spec §7.1 | > 0.005° in 9/64, > 0.02° in 6/64, **max 0.148°** | > 0.005° in 11/64, max 0.031° | **−0.18°** (stationary at 140° from zero, sensor at 20°), same sign in every trial |
| calibrated, output rounded to a multiple of 8 LSB | 0 in 64/64 | 0 in 64/64 | 0 |

Grid (`results/system_float32_unwrap_drift_grid.txt`): all drift > 0.01°/h sits at sensor angle < 64° **and**
|joint − zero| ≥ 128°; 0.002–0.007°/h at sensor < 64° and |joint − zero| 64–128°; zero elsewhere. Exposure:
`_unwrapped` is the angle before `mech_joint_offset` is added (`main.cpp:156-159`), so from `Common.h:90-106`
(range minus `mech_joint_offset`) the joints that reach ≥ 128° from their zero are: right J1 and J2 (to
160°), right J3 (above +38°, zero at −90°), right J4 (below 7°, zero at 134.95°), left J2 (to −160°), left
J3 (below −55°, zero at 73.41°) and marginally left J1; ch5–8 and ch12–16 never do. For each of those
joints the chance that the magnet's sensor angle falls in the sensitive 0–64° sector while it is out there
is roughly 1 in 5 (magnet mounting phase is arbitrary). The error persists after the joint leaves that region, until the M5 reboots or the joint is
re-zeroed.

**Recommended change.** Round the compensated output to a multiple of 8 LSB before transmission:
`u_out = (((raw15 << 6) + Δ + 4) & ~7) mod 2²¹`. Then `u_out × 360/2²¹ = (u_out/8) × 45 × 2⁻¹⁵` with
`(u_out/8) × 45 < 2²⁴`: every value is exactly representable and a multiple of 2⁻¹⁵°, every difference and
every add is exact while |angle| < 512°. 8 is the smallest step for which this holds (4 fails above 256°).
Cost: ≤ 0.00069° of rounding against an arithmetic budget of 0.005° (§7.5), a handful of cycles. The
uncalibrated path stays bit-exact upstream (D10) and is immune anyway.

**Frozen items.** None: wire format, USERROW layout and CMD=3 are untouched. §7.1 formula, the §7.5 budget
row (+0.0007°) and the §11.2 golden hashes change. `GET_ANGLE_COMP` / `GET_SAMPLE` should report the
rounded value, since that is "what ships"; the station statistics are unaffected (symmetric rounding,
dithered by noise).

**Bench confirmation** (cheap, U9): calibrated module on a real M5, joint clamped > 128° from zero with the
magnet in the 0–64° sector, log the 10 s mean of the host angle for one hour; repeat with the rounded
output.

---

### S4 — The zero is one noisy reading  (MAJOR)

**Spec.** §7.2 notes that from the M5's one-point zero a part within `R_MAX` can deviate by 2 × `R_MAX`.
§9.1 requires re-zeroing after installation. Neither mentions noise.

**Issue.** Zeroing copies `snapshot.sensors[i].raw_deg` — the latest single frame (`M5/src/main.cpp:155`) —
into `jig_angle_offsets[i]` and commits it to NVS (`:238-247`). No averaging. That reading carries the
sensor's per-reading noise, and the offset then stays for the life of the zero (months).

**Quantification.** 0.05° 1σ per joint as a *constant* bias = 2.5 × `R_MAX`. Over the 14 arm joints: at
least one joint off by > 0.10° with probability 0.48; expected worst joint 0.10°, 95th percentile 0.145°
(`results/system_budget.txt` §3). Before calibration this is hidden under 0.6°; after calibration it is the
largest well-defined term in the static budget, together with S5.

**Recommended change** (no firmware): *host zero-trim*. Immediately after zeroing, arm still in the jig,
the host averages ≥ 1 s (1000 samples → 0.0016°) of each `angles[i]`; the expected value is exactly
`mech_joint_offset[i]`; the difference is the frozen zero noise; the host stores and subtracts it. The same
measurement is the baseline for S1's return-to-jig check.

**Frozen items.** None. (A module-side alternative — a motion-adaptive output filter so that a stationary
arm presents a low-noise value to the M5 at zeroing time — also needs no protocol change but adds lag
behaviour that has to be designed; not recommended first.)

---

### S5 — Noise is unfiltered end to end  (MAJOR)

**Spec.** §2.7: "Per-reading noise dominates the calibrated accuracy … noise must be filtered downstream
or averaged." §7.5 lists it. No requirement on anyone follows.

**Issue.** The chain has no filter: the module sends one reading per trigger (`encoder/src/main.cpp:362-371`;
spec §6.1 keeps "one SSC transaction" per read), the M5 only unwraps and offsets
(`AngleProcessor.h:49-77`, `main.cpp:150-170`), and the stream carries the raw float (`main.cpp:478-489`).
The host software is outside this repository (U3). So as far as this design can guarantee, a received
sample after calibration is accurate to ±0.10° (95 %), of which the calibrated residual is a fifth.

**Quantification.** Filtered to a noise bandwidth *B* the noise is 0.05° × √(B/500 Hz): 0.022° at 100 Hz,
0.011° at 25 Hz, 0.007° at 10 Hz. Only below ≈ 50 Hz does the 0.02° systematic gate become visible at all. A
follower's position loop is such a filter, so for *tele-operation* the noise is probably benign; for
*recorded demonstrations* and for any host-side velocity estimate it is not (0.05° × √2 / 1 ms = 70°/s 1σ
of velocity noise at 1 kHz).

The per-reading σ is already measurable for free: `GET_SAMPLE` indices 4–7 give Σd and Σd² over 1024
readings. The station should record σ per module and flag outliers — σ depends on the field at the sensor,
hence on air gap and magnet (the recent magnet change, 2.5 → 3 mm thickness at unchanged gap, should raise
the field slightly by the coordinator's unreviewed estimate, so no adverse effect is expected; the
sensor-physics review owns that number). 0.05° is a datasheet figure; the real one is U4.

**Recommended change.** (1) Write the host-side filter requirement into §9 (a recommended low-pass and its
lag, e.g. a 25 Hz 2nd-order filter ≈ 9 ms group delay — which the host must then account for like S6).
(2) Record per-module σ at the station and gate it (e.g. reject or investigate above 0.08°). (3) *Optional,
only if the bench shows the need:* use the ≈ 870 µs of idle time per cycle (§8.1) for 4 reads spaced
200 µs and send their mean — noise ÷ 2 if independent (§8.4 item 9 decides) and mean age −300 µs. This
touches §6.1 and §8 and risks reply latency if a read overlaps the next trigger; it does not touch the
frozen items.

**Frozen items.** None.

---

### S6 — Data age is ≈ 1.8 ms and the timestamp does not say so  (MAJOR for accuracy in motion)

**Spec.** §8.1: "replies from its cached value, then reads the sensor." §2.7: sensor delay 80–95 µs. No
statement of the age of the value the host receives.

**Issue / mechanism**, cycle *k* starting at M5 tick *T_k*:

1. Module *i* receives trigger *k* at *T_k* + ≈ (50 + 20 + 30 (*i* − 1)) µs, replies with the angle it read
   one cycle earlier (`encoder/src/main.cpp:340-344`), *then* reads the sensor (`:362-371`). Reply-from-cache
   costs ≈ 975 µs.
2. The M5 loop stamps `snapshot.timestamp = micros()` (`M5/src/main.cpp:139`), parses whatever has arrived
   (`:141`) — the replies to the *previous* trigger — and only then sends the next trigger (`:144-147`),
   then sleeps one tick (`:255`). Replies wait 0.46 ms (module 16) to 0.91 ms (module 1) in the UART buffer.
3. Sensor: 80–95 µs filter delay plus 0–85 µs register-update phase.

Age relative to `timestamp`: **2.04 ms (module 1) … 1.59 ms (module 16), mean 1.81 ms**
(`results/system_budget.txt` §1). The USB hop adds ≈ 1–2 ms more (77-byte frame = two 64-byte packets, the
second waits for the first to complete, `USBStream.cpp:29-31,192-218`, `USBStream.h:72`), but that is
common to all joints and visible to the host as transport latency.

**Quantification.** Error = ω × age: 0.018° at 10°/s, 0.11° at 60°/s, 0.33° at 180°/s, 0.65° at 360°/s. The
age equals `R_MAX` at **11°/s**. This is identical before and after calibration; it is why the improvement
ratio falls from 4.6× (static) to 2.0× at 180°/s and 1.3× at 360°/s. It is a deterministic delay, not
noise: a consumer that knows it can remove it; one that treats `timestamp` as the sample time cannot. For
live tele-operation 2 ms is negligible against the follower's own lag; for recorded data and for any claim
of "0.02°" outside quasi-static poses it is decisive.

**Recommended change.** (1) Measure trigger → reply → host once with a logic analyser (U6) and publish the
model `t_sample(i) = timestamp − 1.9 ms + 30 µs × (i − 1) − 0.13 ms` (my arithmetic; replace with the
   measured numbers) in §8, so the host can time-align;
the residual uncertainty of ≈ ±50 µs is 0.009° at 180°/s. No firmware change. (2) *Optional, module-side:*
read late in the cycle (predict the 1 ms trigger period) instead of right after the reply — up to −0.7 ms —
at the cost of reply-latency risk along the cascade (§8.2's ≤ 5 µs per hop target); only worth it if the
host cannot time-align.

**Frozen items.** None.

---

### S7 — No lifecycle control: no baselines, thresholds or re-calibration triggers  (MAJOR)

**Spec.** `GET_DMAG` returns the raw field magnitude, `GET_ENV` temperature and VDD (§4.6, §6.3). §7.2
step 1 records SERNUM, ambient and module temperature. §5.1: calibration temperature was dropped from
USERROW; "the station keeps those in its own records, keyed by SERNUM." §2.7: accuracy figures "apply at
calibration conditions."

**Issue.** The design *exposes* the right observables and then does nothing with them:

- `D_MAG` is never compared with anything: no calibration-time value is recorded by §7.2, no threshold is
  defined, the firmware never acts on it (only the sensor's own coarse `SMAGOL` bit is in `STAT_FAULT`,
  §2.3). With a Ø3 mm magnet the field falls steeply with air gap (coordinator's unreviewed estimate for
  N35: ≈ 47 / 32 / 23 mT at 2.0 / 2.5 / 3.0 mm, i.e. ≈ −0.8 per mm in log terms), so a 5 % change in `D_MAG`
  corresponds to only ≈ 0.07 mm of gap — `D_MAG` is potentially a sensitive sentinel for a loosened magnet, a
  shifted PCB or a wrong magnet revision, and it is going unused. It must be temperature-normalised (magnet
  remanence drifts ≈ −0.1 %/K, so 20 K ≈ 2 %), which needs the calibration-time `TEMPR` next to it.
  **Caveat for the sensor-physics review to settle:** a GMR bridge works in saturation, so its vector
  magnitude may follow the field only weakly. If `D_MAG` turns out not to track the air gap, the design has
  *no* air-gap observable at all, and the per-module σ record (S5) and the return-to-jig check (S1) are the
  only sentinels left — which makes them more important, not less.
- Temperature: accuracy applies "at calibration conditions", but no operating envelope is stated, and
  nothing compares `TEMPR` in service with `TEMPR` at calibration.
- No re-calibration trigger exists: not by time, not by event (disassembly, drop, magnet change, firmware
  change of the compensation), not by a failed check.
- The station record as specified lacks what a later check needs: `D_MAG`, VDD, per-reading σ, the
  achieved validation half-range, the fitted page, firmware version, reference self-calibration revision.

**Recommended change.** (1) Extend §7.2 step 1/7 so the station database stores, per SERNUM and per
calibration: `D_MAG`, `TEMPR`, VDD, σ per reading, validation half-range, the 16 page words, firmware
version, station ID and reference self-cal revision, mechanical revision. (2) Define the service check:
`|D_MAG/D_MAG_cal × (1 + 0.001 × ΔT) − 1|` > 5 %, ΔT = T_now − T_cal in K (starting values, to be set from
bench scatter and the magnet grade) ⇒ recalibrate.
(3) Define re-calibration triggers: any disassembly; failed return-to-jig (S1) not cured by re-zeroing;
`D_MAG` shift; and a time-based audit of a sample of arms until ageing data exists. (4) State an operating
temperature envelope for the accuracy claim, from the sensor-physics review's drift figure.

**Frozen items.** None if the baselines live in the station database (recommended). Putting `D_MAG_cal` or
`T_cal` *on the module* would force a USERROW layout change — the layout is full — and I do not recommend
it; the database is sufficient provided S12 is addressed.

---

### S8 — Reject → identity page is the worst outcome for the system  (MAJOR)

**Spec.** §7.2: "A rejected part must not ship with its calibration; the station may recalibrate once, then
commits an identity page (`N_HARM` 0) and records the rejection against SERNUM."

**Issue.** A part rejected at, say, 0.03° is turned into a part with its raw error, 0.6° typical / 1.6°
maximum — 20–50× worse — and if it then ships, nothing on the arm distinguishes it from a calibrated one
(§9.2). §7.6 itself expects poor parts to land at 0.02–0.04°, i.e. this path will be exercised. From S9,
0.03° or even 0.05° is indistinguishable from 0.02° at system level.

**Recommended change.** Either (a) rejected modules are **scrapped or reworked, never shipped** — say so
explicitly; or (b) graded acceptance: commit the fit whenever validation shows it improves on raw, record
the grade in the station database, and gate *grade A* at 0.02° and *grade B* at, e.g., 0.05°. Whichever is
chosen, make "every module on this arm has a valid, non-identity page" a checked step of arm assembly (S1
item 3), since the M5 cannot tell.

**Frozen items.** None for (a) or for (b) with the grade in the database. Encoding the grade on the module
would need a field; a value convention on `STATION_ID` (e.g. bit 7) would avoid a layout change but is a
semantic change to a frozen field — flagged, not recommended.

---

### S9 — 0.02° is below the knee  (MINOR)

Static RSS after calibration against the gate value (`results/system_budget.txt` §6):

| Scenario \ `R_MAX` | 0.01° | 0.02° | 0.03° | 0.05° | 0.10° | 0.20° |
|---|---|---|---|---|---|---|
| as designed (noise 0.05, zero 0.05, jig 0.10, T/H 0.05) | 0.132 | 0.133 | 0.133 | 0.135 | 0.144 | 0.174 |
| + zero-trim + 25 Hz host filter | 0.113 | 0.113 | 0.114 | 0.116 | 0.126 | 0.159 |
| same, perfect jig | 0.052 | 0.052 | 0.054 | 0.059 | 0.076 | 0.124 |
| same, perfect jig, T/H only 0.02° | 0.024 | 0.026 | 0.029 | 0.036 | 0.061 | 0.115 |

The knee is at ≈ 0.05° in every row: tighter buys < 5 % until *all* of noise, zero, jig and
temperature/hysteresis are below ≈ 0.02° — the last row, which nothing in hand supports. Going from raw to
0.05° captures > 95 % of the achievable gain. 0.02° costs little per module (≈ 1 min) and may stay as the
station's *process* target, but (a) it must not be quoted as system accuracy, (b) it should not decide
scrap (S8), and (c) the 8-mount reference self-calibration (§7.7) moves the system number by < 1 %
(reference 0.014° → 0.0014° changes the after-RSS from 0.1335° to 0.1328°). What *is* worth doing of §7.7
is its step 5 alone — one extra mounting — as a check that the reference is within its ±50″ rating at all
(the metrology review's subject).

### S10 — Sampling skew along the cascade  (MINOR)

Module *i* samples ≈ 30 µs after module *i* − 1 (§8.1; `encoder/src/main.cpp:340-345`). Module 1 to 16:
450 µs (0.081° at 180°/s) — but those are two different arms. Within one arm (7 joints): 180 µs, ±90 µs
about the arm's mean → ±0.016° at 180°/s, equal to `R_MAX` at 222°/s. Covered by the same host time
alignment as S6; no separate action.

### S11 — No frame check  (MINOR)

Frames carry no check sequence (§1.1) and the M5 accepts any well-formed frame (`RSNexus.cpp:75-91`). A
bit error in payload bits 0–16 moves one sample by < 30° and passes the jump detector (`main.cpp:201-218`);
because the M5 integrates differences the next good frame restores the angle, so the damage is one frame,
except across a ±180° difference where a permanent 360° slip is possible (`AngleProcessor.h:69-70`).
The bus error rate is unknown. Recommendation: host-side 3-sample median or rate-limit outlier rejection.
No frozen-item impact.

### S12 — Traceability depends on one database  (MINOR)

The module carries `STATION_ID`, `CAL_DAY`, `N_HARM`, coefficients and CRC (§5.1); the chip's SERNUM is the
key to everything else. That is enough to recall all modules of a faulty station/day — good — but
residual, temperature, `D_MAG`, σ and mechanical revision exist only in the station database. Recommend:
the database is backed up and exported with each shipped arm (a JSON per arm listing SERNUM → record), so
that a service site can do the S7 check without access to the factory. No frozen-item impact.

---

## 4. Unknowns — bench measurements or information needed

| # | Unknown | Why it matters | How to settle it |
|---|---|---|---|
| U1 | Is the magnet captive in the module (same magnet, seat, gap at station and on the joint)? Does any assembly step after calibration disturb it? Were modules calibrated before the 2.5 → 3 mm magnet change? | S2: decides whether the "after" column exists at all | user / mechanical drawing |
| U1b | Shift of the error curve under joint load through the module's bearings | S2 | station: validation pass with and without radial load |
| U2 | Jig repeatability per joint | largest assumed static term (0.10°) | re-seat the arm in the jig 10×, host-average 1 s each, per-joint scatter |
| U3 | What the host does: filter, use of `timestamp`, outlier handling, velocity estimation | S5, S6, S11 | user |
| U4 | Real per-reading σ with the actual magnet and gap | S4, S5; 0.05° is a datasheet figure | already in `GET_SAMPLE` Σd² — record it |
| U5 | Temperature coefficient and direction hysteresis of the calibrated output | largest *unsized* term; if ≥ 0.1° it dominates everything | sensor-physics review, plus station runs at two temperatures and with both approach directions on a few modules |
| U6 | Real age: trigger → reply → M5 parse → host; M5 tick rate; loop jitter | S6 model is arithmetic on §8.1's unmeasured cascade timing | logic analyser on the bus + GPIO or USB timestamp, one session |
| U7 | O4: module power with the M5 disconnected | S1: on-arm diagnostics exist or not | user / schematic |
| U8 | Joint-speed histogram in real use | converts S6 into a number for this product | any recorded session |
| U9 | S3 on real hardware | simulation is bit-faithful IEEE-754 single with round-to-nearest-even; ESP32-S3 FPU should match, compiler flags unverified | clamp test described in S3 |
| U10 | Bus bit-error rate | S11 | §8.4 item 3 long run, count implausible samples |

Sources consulted outside the repository: https://docs.openarm.dev/hardware/openarm-ker/general (1.7 kg,
links scaled to 70 % of OpenArm 2.0), https://docs.openarm.dev/hardware/openarm-ker/encoder-module (module
"integrates a hardware limit, bearings, a magnetic encoder, and a driver"),
https://docs.openarm.dev/hardware/openarm-ker/calibration-workflow (jig locates pipe P1, J8 and the body;
no tolerance, no verification pose, no zeroing accuracy stated). None gives joint speeds, latency or
accuracy figures. A literature search for human joint speeds returned nothing citable; the speeds in §1.1
are my assumption.

---

## 5. Recommendations, ranked by accuracy gained per unit of effort

| # | Measure | Gain | Effort | Frozen items |
|---|---|---|---|---|
| R0 | Answer U1 (captive magnet, calibration void after disassembly); write it into §7.2 | precondition for any gain | a question | none |
| R1 | Host zero-trim: average 1 s at the jig right after zeroing, subtract (S4) | removes 0.05° 1σ bias per joint; worst joint of 14 ≈ 0.10° → ≈ 0.002° | hours, host only | none |
| R2 | Round the compensated output to a multiple of 8 LSB (S3) | removes 0.02–0.15°/h drift on J1/J2/J4; costs ≤ 0.0007° | one line + regenerated golden vectors | none (spec §7.1, §7.5, §11.2 text) |
| R3 | Host frozen-channel detector + `seq` gap check (S1) | turns unbounded silent errors into alarms | hours, host only | none |
| R4 | Publish the latency model after one logic-analyser session; host time-aligns (S6, S10) | 0.11° at 60°/s, 0.33° at 180°/s → < 0.01° | one bench day + host code | none |
| R5 | Host low-pass requirement in §9; record and gate per-module σ at the station (S5) | 0.05° → ≈ 0.011° per sample | hours | none |
| R6 | Return-to-jig check at session start/end as the field verification (S1) | the only in-use evidence that accuracy holds; detects ≥ ≈ 0.1° | procedure + host script | none |
| R7 | Station database: `D_MAG`, `TEMPR`, VDD, σ, residual, page, versions; service check and re-calibration triggers; per-arm export (S7, S12) | makes "control" real | station software | none (a layout change only if baselines were to live on the module — not recommended) |
| R8 | Service adapter closing O4; health read-out as an assembly and service step (S1) | access to every flag the design already has | cable + procedure | none |
| R9 | Reject policy: scrap, or graded acceptance instead of an identity page (S8) | avoids 0.6–1.6° joints on shipped arms | decision | none with the grade in the database |
| R10 | Decide whether persistent faults trip the M5 jump detector (S1) | fault becomes visible on the M5 screen and stops the stream | §6.2 behaviour change; reverses D18 | none |
| R11 | Size U2 and U5 before investing further in the station (S9) | tells whether the next 2× is in the jig, in temperature, or nowhere | two bench days | none |
| R12 | *Optional:* module-side 4× oversampling or late read (S5, S6) | noise ÷ 2, age −0.3…−0.7 ms | medium; reply-latency risk | none (touches §6.1, §8) |
| — | De-prioritise the 8-mount reference self-calibration as a production gate; keep its step-5 check | < 1 % at system level (S9) | saves effort | none |

**No finding forces a change to the USERROW layout, the CMD=3 subcommand space, the wire protocol or the
M5 firmware.** Two places where a reader might be tempted to change a frozen item are flagged and
recommended against: on-module calibration baselines (S7) and an on-module grade bit (S8).

---

## 6. What the design gets right

- It never claims more than it can show: accuracy is stated as *relative to the reference* (§7.7) and *at
  calibration conditions* (§2.7), and per-reading noise is named as dominant (§2.7, §7.5). The gap this
  review describes is between those careful statements and the system-level question, not inside the spec.
- The constant term is left to the M5's zero and the fit is independent of mounting offset (§7.2 steps
  4–5); the re-zero requirement after installing calibrated modules is explicit (§9.1).
- Validation is out of sample, averaged, and on the committed module's own output — it tests what ships.
- AUTOCAL and PREDICT are locked off (§2.4), so the sensor's dynamics are deterministic and a latency model
  (R4) is possible at all.
- The uncalibrated path stays bit-exact upstream (D10), which — as S3 shows — also happens to be the mapping
  the M5's float32 unwrap handles exactly.
- The M5's float32 *conversion* preserves the 21-bit resolution (step ≤ 3.05 × 10⁻⁵° vs. LSB 1.72 × 10⁻⁴°,
  `RSNexus.cpp:85`); the stream carries float32 degrees untouched (`main.cpp:386,486`,
  `USBStream.cpp:140-143`) with a timestamp and a sequence counter (`main.cpp:385,395`) — everything a host
  needs for R1, R3, R4 and R6 is already on the wire.
- The observables needed for lifecycle control already exist (`GET_DMAG`, `GET_ENV`, `GET_HEALTH`,
  `GET_CFG_VERIFY`, `GET_SAMPLE` Σd²), and SERNUM + `STATION_ID` + `CAL_DAY` give recall capability. What is
  missing is procedure and records, not protocol.
