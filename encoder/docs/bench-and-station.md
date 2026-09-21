# Building the bench and the calibration station

How to actually build the two pieces of hardware this project needs, in the order you would build
them. The **bench** is an afternoon and a USB adapter. The **calibration station** is a week and a
few hundred euros, and most of that week is spent proving the station before it is allowed to
calibrate anything.

This is the practical companion to the specification, not a replacement for it. Every limit and
criterion here comes from `protocol-spec.md` and is cited; **where the two disagree, the
specification wins** and this document is the thing with the bug.

---

## Part 1 — The bench

### 1.1 What it is for

Flashing, `kercal` diagnostics, the timing measurements of `timing-measurements.md`, and every
open question in §12.2 that does not need a rotating stage. It is also where a module is
provisioned with `SET_ID` if it is not going to be calibrated.

### 1.2 Parts

| | |
|---|---|
| USB–RS-485 adapter | half duplex, must reach **2 Mbps**. Many cheap CH340-based adapters do not; check before buying |
| 5 V supply | **≥ 4.75 V at the module.** `COMMIT_CAL` refuses below 4.5 V (D19), and a loaded USB port can sag through that |
| serialUPDI programmer | Adafruit UPDI Friend or equivalent; see `../README.md`. The HV version is only needed to recover a bricked chip |
| 120 Ω resistors ×2 | bus termination at both ends |
| twisted pair | short. At 2 Mbps a long unterminated stub will show edges that are not there |

### 1.3 Wiring

![Bench wiring](img/bench-wiring.svg)

### 1.4 The one rule

**Never connect this bus to a system with an M5 on it.** An unmodified M5 parses *any* frame whose
header ID is 1–16 as a joint angle (§1.5, §1.6) — a `kercal` request to a module on a live arm is,
to the M5, a joint that has just moved. During zeroing it is worse.

`kercal` enforces what it can: it listens for 200 ms before its first transmission, refuses to start
if anything is talking, and permanently stops transmitting if it ever sees a CMD=1 or CMD=2 frame
(§3.2, C4). Those are backstops, not permission. `kercal listen` transmits nothing and is the only
command that is safe to point at an arm.

During provisioning and calibration, **exactly one module is on the bus** (§3.4). The station reads
`GET_SERNUM` and records it with every result, so the part it fits is by construction the part it
read.

### 1.5 Bring-up, in order

```bash
cd encoder
.venv/bin/pio run -t upload --upload-port /dev/ttyUSB0     # one image for every module
cd tools/kercal
python -m kercal --port /dev/ttyUSB1 listen --seconds 2    # must report "quiet -- a bench bus"
python -m kercal --port /dev/ttyUSB1 scan                  # expect exactly [31]
python -m kercal --port /dev/ttyUSB1 info --id 31
```

Read the `info` output in this order:

1. **`cfg_verify.passed` must be `true`**, and `checks` must list all five. This is the first thing
   any board should be asked, because of the failure it can reveal — see §1.6.
2. `health.flags` on a virgin module should be exactly `CAL_INVALID` plus `WRITE_ELIGIBLE`.
   `CAL_INVALID` is correct here: there is no calibration page yet.
3. `environment.vdd_mv` ≥ 4750. If it is near 4500, fix the supply before going further.
4. `environment.temperature_c` should be plausible. If it reads ≈ 209 °C the host is reading
   `TEMPR` as unsigned; that is a tool bug, not a sensor fault (§2.6).
5. `counters` should be near zero apart from `transactions`.

### 1.6 The failure to look for first

If `cfg_verify` reports everything **except** `SFUSE_clear` — that is, `0x0017` instead of `0x001F` —
stop and read §12.2 O2. It means `STAT.SFUSE` did not clear after `CRCPAR` was rewritten. If it
latches until the sensor is reset rather than clearing at run time, then the configuration lock can
never pass, `SENSOR_CFG_FAIL` sticks, compensation stays suspended, and **every module silently
ships the uncalibrated mapping**. `SFUSE` is also inside `STAT_FAULT`, so every angle read would
fail its status check as well and the persistent-fault rule would pass readings through degraded
after 20 ms. Nothing downstream would notice.

This is one board, one command, and it decides whether the calibration works at all. Do it before
building the station.

---

## Part 2 — The calibration station

### 2.1 What it has to do

Provide `θ_true` — the true angle of the horn — at each of ≥ 128 fit positions and ≥ 128 validation
positions, in both directions, good enough that the module's own error is what is being measured
rather than the station's. **Everything in §7.2 is relative to `θ_true`**: whatever error the
station has in harmonics 1–6 is written into every module, and the acceptance gate cannot see it,
because both passes share it.

With encoder-grade couplings and the commissioning below, `θ_true` is good to about **± 14–18″
(0.004–0.005°)**, of which **± 5–10″** can reach a module (§7.7). That is self-consistent but **not
traceable** — every check compares the chain with itself.

### 2.2 The mechanical chain

![Station mechanical chain](img/station-chain.svg)

One precision shaft carries both grating encoders between two bearing blocks. A coupling at each end
isolates the stepper on one side and drives the unit's horn on the other.

Two things to understand before buying anything:

**The unit under test is a sealed assembly with its own bearing** (§2.8). Its horn cannot be made
rigid with the shaft, so C2 is structural, not optional. A station built to calibrate a bare PCB
over a station magnet measures the wrong object: another magnet of the same type, or the same PCB
re-seated by 0.1–0.2 mm, leaves 0.2–1.4° of error, which is no better than not calibrating at all
(D23).

**Only C2 reaches `θ_true`.** C1's error never does — it sits between the stepper and the shaft,
upstream of both encoders. So the coupling budget is not split evenly: C2 is an encoder-grade
diaphragm coupling and C1 can be whatever holds.

### 2.3 Parts, and what actually matters about each

| | Requirement | Why |
|---|---|---|
| **Grating encoders ×2** | through-bore, single-turn, 21–23 bit, Modbus-RTU over RS-485 | the near one defines `θ_true`, the far one is a permanent check — and with a through-bore reference the check is **required**, not optional (§2.6) |
| **Precision shaft** | ground, h6 or better, **runout < 5 µm, measured after assembly** | this, not the encoder's data sheet, sets the installed accuracy — see below |
| **Bearing blocks ×2** | straddling both encoders; nothing cantilevered | |
| **Shaft clamping** | taper or expanding bushings | a set screw pushes the shaft off centre, and off centre is the whole problem |
| **C2** | encoder-grade **diaphragm or flexure** coupling with a *stated* kinematic transfer error; ≥ 150 N·m/rad; **no helical-beam** | the only coupling in the `θ_true` path. HEIDENHAIN K 14: ± 6″; a metal bellows: ± 40″. §7.7's simulation shows a bellows here triples the low-order error *while still passing the commissioning criteria* — a purchasing requirement, not something the station can certify later |
| **C1** | any decent flexure coupling | its error never reaches `θ_true` |
| **Stepper** | **a single shaft is enough.** It sits at the end of the chain, not in the middle | the earlier topology needed a dual shaft; this one does not. Do not pay for step accuracy either — see below |
| **Stepper driver** | automatic standstill current reduction must be **defeatable** | see §2.4 |
| **Second USB–RS-485** | for the encoders' Modbus, separate from the module's 2 Mbps bus | |
| **Dial indicator** | — | shaft runout, and alignment: radial ≤ 0.05 mm, angular ≤ 0.05° |
| **Fixture** | locates the unit's **housing** repeatably | the housing is held; the horn is driven |
| **Hall probe** | reads to ≈ 200 mT | O6. Not part of the chain, but the first bench item of all |

Full selection record and prices: `station-reference-encoder.md`.

**Do not buy step accuracy.** The procedure never uses the stepper's position: `θ_true` is always
the encoder reading. §7.2's positions are nominal targets, and §7.7's simulation deliberately
scatters them by 0.03° rms. What matters in the motor is bearing quality and shaft runout, not
microstep accuracy.

**Do buy shaft accuracy.** A through-bore encoder's quoted accuracy is its graduation under ideal
mounting. Installed, its eccentricity `e` at grating radius `r` adds an H1 error of about `e/r`:

> `e` = 10 µm at `r` = 25 mm → 10 µm / 25 mm = 4 × 10⁻⁴ rad ≈ **82 arcseconds**

against a graduation figure of a few arcseconds. The order of magnitude the through-bore part wins
on paper is lost immediately to a mediocre shaft. **Measure the runout with a dial indicator after
assembly** — that number, not the data sheet, is what you have.

### 2.4 Assembly, and two traps

1. Mount the bearing blocks and the shaft first; everything else is aligned to it. Measure the
   runout now.
2. Clamp both encoders on the shaft, **90° apart** — see §2.6 for why that angle is not arbitrary.
   Anchor each stator so it cannot creep.
3. Fit C1 to the stepper, C2 to the far end. Align with the dial indicator: ≤ 0.05 mm radial,
   ≤ 0.05° angular.
4. Mount the fixture so a unit's housing seats repeatably with its horn in C2. Align again.
5. Keep the whole thing away from steel, and **record the station's orientation** — Earth's field
   alone is 0.095° of H1 error at 30 mT, and it belongs to the world, not to the module (§2.8).

**Trap 1 — standstill current reduction.** Sampling takes 205 ms, during which the reference polls
must be stationary to **3 arcseconds** (0.00083°). Many drivers drop to half current shortly after
motion stops, and the shaft moves a little as they do — precisely while you are sampling. On a
TMC2209/TMC5160, disable standstill and freewheel and hold full current; on a TB6600-style driver,
set the half-current DIP off. An A4988 or DRV8825 has no such feature, which here is a virtue.
Microstepping of 1/16 or 1/32 is worth having, not for accuracy but because a smoother approach
rings less and settles sooner — and that cost is paid 512 times per unit.

**Trap 2 — the stepper's own field.** A stepper is a permanent magnet and live coils, and the sensor
it is pointed at measures field *direction*. Worse, the leakage field changes with coil current,
which changes with microstep phase, which correlates with position — a systematic error that would
be written into every calibration, and one the acceptance gate cannot see because both passes share
it. Putting the stepper at the far end of the chain is the first defence. **Test it**: with the unit
stationary, step the driver through microstep phases *without moving the shaft* (or energise and
de-energise) and watch the module's reading. If it moves, lengthen the chain, shield, or de-energise
during sampling — and if you de-energise, check that the shaft stays put.

### 2.5 Incoming test of the encoders — before they are trusted

Station software only; no extra instruments (§7.7):

| Test | What it tells you |
|---|---|
| Hold a magnet to the housing while reading | any change means a **magnetic** encoder — not acceptable at a 72″ tolerance |
| Static noise at 8 angles | the number the stationary-poll criterion is set against |
| Repeatability, 16 positions × 10 turns | whether it returns to the same reading |
| Reversal | its own hysteresis |
| Fine scan, ≥ 1000 microsteps over a few degrees | **sub-divisional error** — and its period tells optical from magnetic. The 24″/15″ guarantee of §7.7 assumes this is ≤ 8″ |
| 30-minute warm-up log | how long before it is stable |
| Register width, latching, maximum baud | so the polling code is right |
| **enc 1 against enc 2, one full turn** | they are on one rigid shaft and see the same mechanical angle, so their difference is the sum of their two errors. If they were independent, it is √2 × the single-unit error — the only direct estimate of installed accuracy you can get without a traceable instrument |

### 2.6 Commissioning — and why it is not §7.7's procedure any more

Repeat this whenever the shaft, either coupling, or the fixture is disturbed. One assembled unit is
the **transfer artefact**; power it ≥ 30 minutes beforehand and keep `GET_ENV` index 0 within ± 2
`TEMPR` counts (one count is 0.36 K) for the whole run.

**The change.** §7.7's set A re-clamps the reference at ten angles. That is fine for a solid-shaft
encoder with its own bearings, whose error is a fixed curve being rotated. It is **not** fine for a
through-bore encoder clamped on a shaft: every re-clamp changes its eccentricity, and the fit's
assumption fails. This is what §7.7 meant by *"a hollow-shaft or kit encoder breaks the method for
H1"*.

*Measured* (`evidence/v7-throughbore/`, 200 simulated stations per row):

| Re-clamp error | ≈ eccentricity at r = 25 mm | §7.7's procedure, passes both criteria | B-only |
|---|---|---|---|
| 3″+2″ | 0.4 µm | 100 % | 100 % |
| 8″+4″ | 1.0 µm | 93.5 % | 100 % |
| 16″+8″ | 1.9 µm | **2.5 %** | 100 % |
| 25″+12″ and worse | ≥ 3 µm | **0 %** | 100 % |

**So: clamp the encoders once and never re-clamp them. Run set B only** — the horn re-clocked at
eight angles (twelve is slightly better), out and back, on the one mounting. `R′` and `S2` can then
not be separated, and do not need to be: production always runs on that mounting, and the fit
absorbs their sum. `θ_true` comes out at **13.4″ median, 17.2″ worst**, of which **3.4″ median,
6.5″ worst** can reach a module — flat against re-clamp error, and slightly *better* than §7.7's
procedure even at zero clamp error.

**What this gives up, and what covers it.** Nothing in a B-only commissioning can detect the
reference's mounting shifting *afterwards* — the criteria were computed before it happened. A
**1 µm shift triples the error that can reach a module** (H1–H6 from 3.4″ to 10.7″) while
reproducibility and check both stay green.

That is what the second encoder is for, and it is why it is a requirement here rather than a
recommendation: two encoders on one rigid shaft see the same mechanical angle, so their difference
is the only thing in the station that can notice one of them moving. **Read both at every
calibration and log the difference.** Clock them 90° apart, or their sub-divisional errors may
cancel in exactly the comparison that is meant to catch this.

Criteria are unchanged and still provisional: reproducibility ≤ **8″** rms in H1–H3, check mounting
≤ **12″** in H1–H7. Read §7.7's second table before trusting a pass — they do not separate good
stations from faulty ones cleanly.

> **Status.** This departs from the normative §7.7 and has not been independently verified. The
> simulation is `evidence/v7-throughbore/reclamp_sweep.py` and can be re-run in a minute.

### 2.7 In production

`θ_true = ψ − R̂′(ψ)`, where `ψ` is the near encoder's reading and `R̂′` the fitted curve — which
now carries the reference's own error, its clamping, C2's mean transfer error and everything else
fixed in that mounting. The far encoder is read at the same time and its difference from the near
one logged against the commissioning value.

---

## Part 3 — Calibrating a unit

The computational half is `evidence/v3-reference/station_fit.py`, which `kercal` loads rather than
reimplementing. The physical half is below. Normative detail: §7.2.

**What is calibrated is the fully assembled, sealed unit** — its own horn with its own magnet bonded
and cured, bearing, spacer, PCB, screws at final torque with thread-locker — driven through its horn
with its housing in the fixture. After calibration the spacer and PCB screws are paint-marked; **a
broken mark voids the calibration** (D23). Re-flashing through UPDI needs no disassembly.

### 3.1 The minimums

These are **minimums, not defaults**. The operating characteristic of §7.2 is only established at
these values or above; with 64 + 64 positions the gate already mis-grades parts.

| | |
|---|---|
| fit positions | ≥ 128, uniform |
| validation positions | ≥ 128, interleaved half-way between fit positions, never used in the fit |
| directions | 2 — every position approached clockwise **and** counter-clockwise (D24) |
| readings averaged | ≥ 1024 per position and direction (`SAMPLE_START` e = 10) |

`python -m kercal limits` prints them, and which file they come from.

### 3.2 The run

1. **One unit on the bus.** Power it **≥ 10 minutes**, or until `GET_ENV` index 0 is stable to 1 K —
   the die heats itself by 11–16 K. Record `GET_SERNUM`, ambient and module temperature, VDD and
   `GET_DMAG`.
2. **Noise check.** Re-approach one position 8 times, **always clockwise** — alternating would put
   the hysteresis into the result. If `σ_mean` > `R_MAX`/6 = 0.0033°, stop: the verdict is
   *insufficient data*, the station needs fixing, and **the part gets no grade**.
3. **Fit passes**, clockwise then counter-clockwise. At each position: move, wait until the
   reference polls are stationary, *then* `SAMPLE_START`, then `GET_SAMPLE`. Never overshoot an
   approach, or the hysteresis measurement is void. Discard and repeat any sample with status bit 1
   or 2 set, or with fewer than 90 % of readings passing.
4. **Fit and commit.** The fit is of the **pooled** samples of both directions — the mean curve of
   the hysteresis loop. Stage, `COMMIT_CAL`, read the page back and compare. **Do not release a unit
   until a commit has succeeded and been read back.**
5. **Validation passes**, both directions, on the committed unit, at the interleaved positions —
   measuring what actually ships.
6. **Grade** (§7.2 step 8): **A** ≤ 0.02°, **B** ≤ 0.05°, otherwise **rework**. A rejected unit is
   re-seated and re-run, or scrapped. It is **never** given an identity page and shipped: an
   identity page is 0.6–1.6° of error and nothing on the arm can tell it from a calibrated unit.
7. **Centring gate.** Fitted H2 above 0.2° means the sensor sits ≈ 0.2 mm off the rotation axis, and
   the calibration is fragile to later mechanical shift. Re-seat and re-run rather than ship it.
8. **Record** against `SERNUM` (§9.7). The grade lives in the station database, not on the module.

About **two and a half minutes per unit** at the minimums, plus the warm-up.

---

## Part 4 — When something looks wrong

| Symptom | Where to look |
|---|---|
| `cfg_verify` = `0x0017` | §1.6. Stop everything until it is understood |
| `kercal` refuses to transmit | it heard a frame. Something else is on the bus — find it before overriding anything |
| `scan` finds more than one ID | §3.4 is violated. The part you fit may not be the part you read |
| *insufficient data* at step 2 | the station, not the part. Settling, coupling slip, stray field, or the stepper's hold current |
| grades cluster at B | expected on poor parts; check the fitted H2 first (centring), then the magnet gap (O6) |
| hysteresis above 0.10° | may be the field at the die rather than the mechanics — §12.2 O6 explains why, and why the CW/CCW curve is the indirect test when there is no Hall probe |
| `WRITE_FAIL` on commit | VDD first (`GET_ENV` index 1), then §5.5. The module keeps running its previous calibration and stays unlocked, so retry is safe |
| a unit was reopened | its calibration is void. Re-run it |

---

## Part 5 — What this station cannot tell you

Worth saying plainly, because it is the difference between a number and a claim:

- **It is not traceable.** Every check compares the chain with itself through a module. Closing that
  needs a check standard read at every calibration, plus one comparison of H1–H3 against an
  instrument with its own calibration chart. Until then, `R_MAX` means "relative to this station's
  reference" (D26).
- **A grade is at station conditions.** Temperature, supply and the local stray field are recorded
  because they are part of the result, not context for it.
- **It does not predict accuracy on the arm.** The station removes what is a repeatable function of
  the module's own angle. Stray fields from neighbouring joints, hysteresis, mechanical play and
  temperature remain, and the reviews estimate 0.1–0.4° in use. Only a measurement on an assembled
  arm settles that (§9.6).
