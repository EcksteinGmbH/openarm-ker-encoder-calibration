# OpenArm KER Encoder — Calibrated Branch Protocol Specification

| | |
|---|---|
| Version | **6** |
| Status | **Approved 2026-09-21 and implemented.** The firmware is `encoder/src/ker_*`; what was built, what it costs and where it departs from this document is `encoder/CHANGELOG.md`. Corrections made after building are marked *(v6.1)*. |
| Scope | `encoder/` only. `M5/` untouched and buildable from upstream. |
| Base | upstream `enactic/openarm_ker_firmware` @ `ffd2aa2` |
| Evidence | every number marked *measured* is reproducible from `encoder/docs/evidence/` (Appendix A) |

Spec version 6 leaves the protocol at version **5** (`GET_PROTO_VER`): v6 changes no subcommand, no record
and no USERROW field. Firmware 1.0.0 implements it; no firmware has yet run on hardware.

This document freezes the **CMD=3 diagnostic/factory sub-protocol** and the **USERROW layout**, and
specifies the sensor read path, the compensation arithmetic and the station fitting procedure that
they depend on. CMD=0/1/2 wire format, reply semantics and chain timing are unchanged.

### Revision history

| Version | Reviews | Outcome |
|---|---|---|
| v2 | `reviews/2026-09-19-spec-v2-*.md` | REJECT: 9 blocker, 31 major, 26 minor. Response: `…-spec-v2-review-response.md` |
| v3 | `reviews/2026-09-19-spec-v3-*.md` | REVISE: 1 blocker, 9 major, 27 minor. Response: `…-spec-v3-review-response.md` |
| v4 | `reviews/2026-09-19-spec-v4-verification.md` | REVISE (narrow): 0 blocker, 1 major, 14 minor |
| v5 | `reviews/2026-09-19-spec-v5-verification.md` | ACCEPT WITH MINOR CHANGES: 0 blocker, 0 major; minors fixed in this document — `…-spec-v5-review-response.md` |
| v6 | `reviews/2026-09-20-accuracy-review-*.md` (three perspectives: sensor physics, station metrology, system budget) | 5 blocker, 18 major, 10 minor — none against the protocol, the USERROW layout or the M5. Synthesis and response: `…-accuracy-review-synthesis.md`, `…-accuracy-review-response.md` |
| v6.1 | `reviews/2026-09-21-firmware-review.md` | 2026-09-21: approved and implemented (firmware 1.0.0). Independent firmware review: REQUEST CHANGES, 0 blocker, 3 major, 7 minor — all three majors were conformance defects in the code, not the spec, and are fixed; response `…-firmware-review-response.md`. Three sections corrected against the built firmware: §6.2 (configuration-lock clock count), §10 (measured resources — the estimate was low), §11.1 (one extra term in `main.cpp`'s read condition). Nothing normative changed: no subcommand, record, USERROW field, wire format or arithmetic |
| v6, verification | `reviews/2026-09-20-spec-v6-verification.md` | REVISE (narrow): 0 blocker, 2 major, 6 minor — both majors in the §7.7 commissioning simulation; firmware- and protocol-relevant content verified. Fixed in this document — `…-spec-v6-verification-response.md`. Re-verification `…-spec-v6-reverification.md`: **ACCEPT WITH MINOR CHANGES**, 0 blocker, 0 major, 3 minor (wording), fixed here |

Main changes v5 → v6. **The CMD=3 protocol, the USERROW layout and the wire format are unchanged**; the
changes are to one line of the compensation arithmetic, the station procedure, and what is claimed:

1. **The accuracy claim is restated** (§7.8). 0.02° is the station's grade-A gate — relative to the station
   reference, at station conditions. It is not the joint-angle accuracy in use, which the reviews estimate
   at ≈ 0.1–0.4° and which only a measurement on an assembled arm can establish (§9.6).
2. **Compensated output is rounded to a multiple of 8 LSB** (§7.1, D22). Finer steps make the M5's float32
   incremental unwrap drift; uncalibrated modules never had the problem. Arithmetic worst case 0.003186°.
3. **What is calibrated is defined**: the fully assembled, sealed encoder unit with its own magnet (§7.2, D23).
4. **Two approach directions**, fit on the pooled data, hysteresis recorded and limited (§7.2, D24).
5. **Graded acceptance** A ≤ 0.02°, B ≤ 0.05°, otherwise rework; a rejected unit no longer gets an identity
   page (§7.2, D25).
6. **Station reference chain rewritten** (§7.7, D27): topology with two couplings, stage-side remounting,
   out-and-back sequence, mountings that open H8/H16, horn-side remounting for the second coupling,
   incoming acceptance test, bracketed reference polling, a check standard.
7. **Host-side and arm-level measures** (§9.5–9.7): zero trim, frozen-channel detection, data-age model,
   filtering, verification on the assembled arm. None needs an M5 change.
8. **Sensor facts corrected** (§2.4, §2.7, §2.8): the BOM part is the TLE5012B-**E1000**, whose defaults are
   not what v5 assumed; the magnet, its field and what `D_MAG` can and cannot show.

Main changes v3 → v4:

1. **Station fitting procedure corrected** (§7.2). v3's "no constant term" made the fit fail whenever the
   magnet is mounted at an angle — 0.2° error at 5° offset, rejection near 180°. Now: remove the circular
   mean, fit with a constant column, discard it. Verified end to end through the firmware routine.
2. **Every multi-word read has a defined record** (§4.3 r6); **latency, timeouts, retries and NAK
   precedence are specified** (§4.3); the **write-failure path** is defined (§4.9).
3. **Unlock rules made unambiguous**, including retries and unlock while already unlocked (§4.9).
4. **Single-module station rule is normative** (§3.4): protocol-level duplicate detection is unreliable.
5. **`SET_ID` provisions only virgin pages**; other invalid pages are refused rather than overwritten (§4.9).
6. **Sensor start-up, config-lock retry and fallback** specified (§6.2).
7. Corrected numbers: arithmetic worst case 0.002587° (§7.5), read step ≈ 112 µs (§8.3).

---

## 1. Upstream behaviour this design depends on

Verified against `encoder/src/main.cpp` and every file under `M5/src` and `M5/include`.

### 1.1 Frame format (unchanged)

```
byte 0 : 1 I I I I I C C     header : ID[4:0], CMD[1:0]
byte 1 : 0 d d d d d d d     payload bits [6:0]
byte 2 : 0 d d d d d d d     payload bits [13:7]
byte 3 : 0 d d d d d d d     payload bits [20:14]
```

A receiver accepts a header byte only with MSB = 1, and each of bytes 1–3 only with MSB = 0,
restarting otherwise (`encoder/src/main.cpp:176-208`). Payload is 21 bits. At 2 Mbps 8N1 a frame
occupies **20 µs** on the wire. There is no frame check sequence, and none will be added (brief).

### 1.2 CMD usage today

| CMD | Sent by | Addressing | Encoder action |
|---|---|---|---|
| 0 | — | — | ignored |
| 1 | bench tools only | `ID == device_id` | reply `(device_id, 1, angle)`, then read sensor |
| 2 | M5, and each encoder | `ID == device_id − 1` | reply `(device_id, 2, angle)`, then read sensor |
| 3 | — | — | ignored — free for this design |

### 1.3 The M5 transmits exactly one kind of frame

The M5's RS-485 port is `Serial2`, used only by `rs485nexus` (`M5/src/main.cpp:35`). The host link is
`USBStream` in the default `usb` build (`M5/platformio.ini:26`, `M5/src/main.cpp:25-26`; it writes to the
USB vendor interface, `M5/src/USBStream.cpp:193,275`) or `SerialStream` on `Serial` in the `serial` build
(`M5/src/main.cpp:28-29`). Neither touches `Serial2`. The only RS-485 transmit is `M5/src/main.cpp:146`:

```c
rs485nexus.requestPacket(BULK);   // BULK == 0 is the ID; cmd defaults to 2
```

The M5 emits one `ID=0, CMD=2` frame per millisecond; the modules cascade: ID 1 answers ID 0, ID 2
answers ID 1, and so on to ID 16. Consequences:

- The M5 never sends CMD=1.
- ID 0 is the master address; no module may be provisioned as ID 0.
- The transmit is **not** conditioned on `AppMode` (`M5/src/main.cpp:144-147`): STANDBY does not
  silence the bus. Only powering the M5 down or disconnecting it does.

### 1.4 When the M5 is silent

- **After M5 reset**, for ≈ 0.7 s: `M5.begin()`, an NVS read (`:367-369`), `gui.init()` and
  `delay(500)` (`:431`) all precede creation of `acquisitionTask` (`:434`).
- **During a stall of `acquisitionTask`**, e.g. the NVS commit during zeroing (`:245-247`).
  `last_request_time += 1` (`:145`) makes the task catch up at one frame per loop iteration,
  rate-limited by `vTaskDelay(1)` (`:255`): it goes quiet, it does not burst.

No safety argument in this document relies on bus silence for anything that can do harm.

### 1.5 The M5 ignores the CMD field, and discards ID 0

`M5/src/RSNexus.cpp:76-91`:

```c
uint8_t received_id = (_packet[0] & 0x7C) >> 2;      // CMD bits never read
if (received_id >= 1 && received_id <= JOINTNUM) {   // ID 0 and 17-31 discarded
    _raw_angle[idx] = raw;  ... _valid[idx] = true;
}
```

Any frame with ID 1–16, of any CMD, is written into the angle array. Any frame with ID 0 or 17–31 is
dropped before its payload is looked at. `_valid[]` is set here and never cleared in the class.

### 1.6 What a stray frame does to the M5

A single stray frame with ID *n* ∈ 1–16 replaces joint *n*'s angle for one acquisition cycle.

- In `STREAM` mode with jump detection on, the M5 substitutes the last good angle **only if the stray
  value differs by ≥ 30°** (`M5/src/main.cpp:201-202`, `JUMP_THRESHOLD_DEG`). A stray value within 30° is
  streamed and becomes the new reference (`:215-218`). A fault needs 20 consecutive ≥ 30° deviations.
- Nothing is substituted on channels with `skip_jump_detect` (ch8, ch16 — `M5/include/Common.h:97,106`),
  with jump detection off in the GUI, or in `STANDBY`.
- **Zeroing reads `raw_deg`**, stored at `:155` before jump detection and never substituted, and commits
  it to NVS at `:245-247`. A stray frame at that moment **permanently poisons that joint's jig offset.**

### 1.7 Angle scaling

```c
uint16_t raw15 = raw & 0x7FFF;
latest_angle_21bit = ((uint32_t)raw15 << 6) | (raw15 >> 9);     // main.cpp:367-368
```

Bit replication: `0 → 0`, `0x7FFF → 0x1FFFFF`, average gain 64 + 1/512 rather than exactly 64. Relative to
the sensor's own reading this is a ramp of 0…63 LSB (0…0.0108°) that jumps back at 0°. Uncalibrated
modules keep this mapping bit-exactly; calibrated modules do not (§7.3).

### 1.8 Dead code

`crc8_0x07()` (`encoder/src/main.cpp:92`) is never called and uses polynomial 0x07, not the TLE5012B's
0x1D. Left in place to keep the upstream diff small.

---

## 2. TLE5012B facts

Sources: Infineon's driver `Infineon/TLE5012-Magnetic-Angle-Sensor` @ `72c84e2d` and the TLE5012B user
manual. ❓ marks items still requiring a datasheet or bench check (§12.2 O2).

### 2.1 Command word

```
bit 15     RW     1 = read, 0 = write
bits 14:11 LOCK   0000 = access 0x00–0x04 ; 1010 = write access to configuration registers
bit 10     UPD    0 = current value, 1 = update buffer
bits 9:4   ADDR   first register
bits 3:0   ND     number of data words; consecutive registers from ADDR
```

After every transfer with ND ≥ 1 the sensor appends a 16-bit **safety word**. Upstream's `0x8021` is
`READ | ADDR 0x02 (AVAL) | ND 1`: the sensor already sends a safety word that upstream never clocks in.

### 2.2 Safety word

| Bits | Name | 0 means |
|---|---|---|
| 15 | S_RST | sensor reset or watchdog overflow since the last read |
| 14 | S_ERR | system error |
| 13 | S_ACC | interface access error |
| 12 | S_ANG | invalid angle value |
| 11:8 | RESP | slave response indicator — not an error field |
| 7:0 | CRC | polynomial 0x1D, init 0xFF, MSB first, final value inverted, over the command word then every returned data word, each big-endian |

### 2.3 STAT register (0x00)

| Bit | Name | Bit | Name |
|---|---|---|---|
| 0 | SRST | 8 | reserved |
| 1 | SWD | 9 | SADCT |
| 2 | SVR | 10 | SROM |
| 3 | SFUSE | 11 | NOGMRXY |
| 4 | SDSPU | 12 | NOGMRA |
| 5 | SOV | 14:13 | SNR |
| 6 | SXYOL | 15 | RDST |
| 7 | SMAGOL | | |

**Fault mask** `STAT_FAULT = 0x1EFE` (bits 1–7, 9–12). STAT.SRST (bit 0) is informational only; reset
detection uses the safety word's `S_RST` (§6.2). ❓ Before the mask is final, each bit's clear-on-read
behaviour must be confirmed; a bit that stays set after the condition clears is removed from the mask
rather than allowed to fail every read. ❓ Infineon's table places SRST and SWD both at bit 1; its
comments put SRST at bit 0, as here.

### 2.4 Configuration locked at boot

| Register | Field | Value | Why |
|---|---|---|---|
| MOD_2 (0x08) | AUTOCAL [1:0] | `00` | autocalibration would move the curve under a stored fit |
| | PREDICT [2] | `0` | speed-based extrapolation fights a static calibration |
| | ANGDIR [3] | `0` | upstream assumes factory direction |
| | ANGRANGE [14:4] | `0x080` | unity |
| MOD_1 (0x06) | FIRMD [15:14] | `2` (D16) | lowest noise that keeps the update period under 100 µs; written so every module has identical dynamics |

**This differs from what upstream actually runs.** The part on the OpenArm BOM is the TLE5012B-**E1000**,
which powers up with autocalibration mode 1 **on**, prediction **on** and FIR_MD **1** (data sheet Rev. 2.1
§5.1, as read by the 2026-09-20 sensor-physics review; to be confirmed against the chip marking, O2).
Upstream writes no sensor register (`encoder/src/main.cpp` only reads `0x8021`), so that is upstream's
configuration. The fork changes all three, deliberately:

- **AUTOCAL off is a precondition for a stored fit, not a preference.** Infineon allows autocalibration
  only where the magnet regularly makes a full turn; a joint with a hard stop never does, but the station
  does, so with it on the fit would be made on an adapted curve that the next power cycle discards.
- PREDICT off: extrapolation overshoots at every reversal, and a leader arm reverses constantly.
- FIR_MD 2 rather than upstream's 1: 0.05° instead of 0.08° noise per reading, for ≈ 0.1 ms more sensor
  delay — small against the ≈ 1.8 ms data age of §8.5, and deterministic (decision of 2026-09-20).

v5 called FIR_MD 2 "the default" and D16 "upstream's dynamics"; both were wrong.

Never written; read once per config lock and cached for `GET_TRIM`: MOD_3 (holds `ANG_BASE`), OFFX,
OFFY, SYNCH, IFAB (holds `ORTHO`) — laser-trimmed per part. Writes go to the volatile registers; the
sensor's EEPROM is never programmed.

### 2.5 The parameter CRC

Registers 0x08–0x0F are covered by `CRCPAR`, TCO_Y (0x0F) bits 7:0: CRC-8 (same scheme as §2.2) over
the first 15 bytes of registers 0x08–0x0F. Writing MOD_2 without updating CRCPAR leaves `SFUSE` set,
which §6.2 treats as a fault. MOD_1 (0x06) is outside the block; MOD_2 (0x08) is inside and requires a
CRCPAR update. ❓ Infineon's bitfield table masks CRCPAR as `0x7F`; their write path uses the full byte.

### 2.6 Temperature

`FSYNC` (0x05) bits 8:0 hold `TEMPR`, a **signed 9-bit** offset-compensated temperature.

```
TEMPR = sign_extend_9(FSYNC & 0x1FF)          // bit 8 is the sign bit
T[°C] = (TEMPR + 152.0) / 2.776
```

TEMPR is negative below 54.76 °C, i.e. normally. Example: at 25 °C, TEMPR = −82.6, stored as `0x1AD`;
read as unsigned (429) it would give 209 °C. The device returns the raw register; the host converts.

### 2.7 Datasheet figures that bound the design

From the TLE5012B data sheet (V1.1, 2012-01) — signal processing (Table 10), electrical parameters
(Table 4), angle performance (Table 9):

| FIR_MD | Update period | Angle delay, no prediction | Angle noise (1σ) |
|---|---|---|---|
| 1 | 42.7 µs | 60–70 µs | 0.08° |
| **2** (this design) | 85.3 µs | 80–95 µs | **0.05°** |
| 3 | 170.6 µs | 120–140 µs | 0.04° |

- **Power-on time** `t_pon` ≤ 7 ms with start-up self-test (5 ms typical); write access is not permitted
  within it.
- **Overall angle error without autocalibration** (Table 9): 0.6° typical, **1.6° maximum**. The maximum
  includes temperature drift and the hysteresis between rotation directions. A static fit removes the
  part that is a repeatable function of the module's own angle; drift with temperature and
  direction-dependent hysteresis remain. The station therefore records its conditions (§7.2 step 1), and
  the calibrated accuracy figures in this document apply at calibration conditions.
- **These rows describe the die alone**, in a *homogeneous* field of 30–50 mT with B_z = 0. Magnet and
  mounting error come on top (§2.8) and are the larger part on this hardware.
- **Data sheet revision.** The figures above are from V1.1 (2012). The sensor-physics review read Rev. 2.1
  (2018): 1.3° maximum at 0 h and 1.9° over life without autocalibration, and an SSC angle delay of
  150–165 µs at FIR_MD 2 without prediction (45–50 µs at upstream's FIR_MD 1 with prediction). Neither
  changes the format or the arithmetic; the delay enters §8.5. Reconciling the two revisions is O2.

**Per-reading noise dominates the calibrated accuracy.** At FIR_MD 2 a single reading carries
≈ 0.05° (1σ) of random noise — ten times the 0.0055° quantisation floor and larger than every systematic
residual in §7.6. Compensation removes systematic error only; noise must be filtered downstream or averaged.
This bounds what the station can verify per sample, and is why the station averages on the module (§7.2,
D17). FIR_MD is locked at 2 (D16).

### 2.8 The magnet, the mechanical unit, and what they do to accuracy

Established by the 2026-09-20 sensor-physics review from OpenArm's documentation, BOM and STEP model, and
from the user; **none of it has been measured yet**.

- **The encoder module is a sealed mechanical unit** (BOM `ENC_UNIT`): aluminium housing, horn with the
  magnet embedded, **one** 10 × 15 × 4 mm ball bearing, a printed PA12 spacer, the PCB with the sensor on
  its underside, no voltage regulator. The magnet therefore travels with the module, and a calibration
  can transfer from the station to the arm — provided the unit is calibrated assembled and never reopened
  (§7.2, D23).
- **Magnet**: diametric cylinder **Ø3 × 3 mm** (was Ø3 × 2.5 mm; the pocket was deepened, so the magnet
  face stays flush and the gap to the chip is unchanged; user, 2026-09-20). Grade unknown; BOM says N35.
- **Field at the sensor**: estimated **23–32 mT** at the CAD-derived gap of 2.5–3.0 mm, before the
  bearing's flux shunting — at or below the 30 mT the accuracy rows require. It falls ≈ 6.7 % per 0.1 mm
  of gap; the in-specification window is only ≈ 0.7 mm wide. Below 30 mT Infineon adds 0.1–0.2° of error,
  part of it hysteresis. **Measuring the field at the die position with the bearing in place is the
  first bench item (O6).** The target is 40–50 mT.
- **Assembly error of an Ø3 mm magnet** is large — 0.15–1.5° in simulation for realistic tolerances, mostly
  H1 and H2, H3 ≤ 0.016°, H5 and above < 0.0002°. It is static and belongs to the unit, so six harmonics
  remove it with margin. Raw error of 2–3° is plausible; the format allows ± 5.6° per harmonic.
- **What a static fit cannot remove**, each of them larger than 0.02°:
  - *Stray fields.* A GMR sensor reports the direction of the total field, so a stray in-plane field
    `B_s` adds an H1 error of `atan(B_s / B₀)` whose phase belongs to the world, not to the module:
    Earth's field, up to ≈ 50 µT, is 0.095° at 30 mT; neighbouring modules' magnets 28–37 mm away are
    0.08–0.34° by an upper (dipole) estimate. On the arm it changes with pose and with the neighbours'
    angles. At the station it is constant, so the fit absorbs it and the gate confirms it.
  - *Hysteresis* between rotation directions: 0.10° typical, 0.16° maximum for the same sensor technology
    (TLE5014), more below 33 mT.
  - *Mechanical play*: with this magnet, 3–12 µm of relative motion between rotor and sensor is worth
    0.02°; the unit has one bearing and a printed spacer.
  - *Temperature, self-heating (≈ +11–16 K over the first minutes) and the unregulated supply.* Infineon
    gives no coefficient; unknown until measured.
- **`D_MAG` is not a field-strength or air-gap monitor.** It is the length of the GMR signal vector; a
  saturated bridge follows field direction, not strength. It shows a missing or grossly weak magnet and
  little else.

---

## 3. Safety model

### 3.1 Threats

| # | Threat | Consequence |
|---|---|---|
| T1 | a CMD=3 reply with ID 1–16 reaches an M5 | parsed as a joint angle (§1.5–1.6) |
| T2 | a module transmits while the cascade runs | electrical collision, corrupted cascade |
| T3 | a write executes on a module installed in an arm | wrong ID or curve on a robot |
| T4 | a write reaches the wrong module, or two | mis-provisioned parts |
| T5 | a host CMD=3 **request** (ID 1–16) reaches an M5 | as T1; worst during zeroing (§1.6) |
| T6 | a bit error turns one subcommand into another | unintended state change |

### 3.2 Countermeasures

**C1 — every CMD=3 reply is addressed to ID 0.** The M5 discards ID 0 unconditionally (§1.5). Closes
T1 by addressing rather than timing.

**C2 — read gate.** A module answers CMD=3 only if it has received no CMD=1 and no CMD=2 frame, of any
ID, for `T_IDLE` = 100 ms, and has been running for ≥ 100 ms since its last reset. CMD=3 frames never
reset this timer. When the gate is closed the module stays completely silent. Reduces T2 to the M5
resuming mid-reply after ≥ 100 ms of silence, which costs one corrupted cascade.

**C3 — write eligibility latch.** A module may enter factory mode only if **no CMD=2 frame has been
received since its last reset** *and* it has been running ≥ `T_ARM_WAIT` = 3 s. The first CMD=2 frame
sets `arm_seen`. There is no software clear: the RESET subcommand requires factory mode, which a latched
module cannot enter, and the watchdog and brown-out fuses are off (`encoder/platformio.ini:34-35`). Only a
power cycle clears it.

- On an arm with its M5 running, every module latches before it could accept a write.
- A CMD=2 frame on a bench — from a tool, or a single bit error turning CMD=3 (`11`) into CMD=2 (`10`) —
  latches every module that sees it. This fails safe; recovery is a power cycle.
- CMD=1 does **not** set `arm_seen`, but it does close the read gate and end factory mode (§4.9).

Closes T3 whenever the M5 is present and running. See §3.3 for when it is not.

**C4 — host discipline** (normative for `kercal`, deliverable 4):
- listen ≥ 200 ms before the first transmission; refuse to start if any frame is seen;
- stop transmitting for the rest of the session if any CMD=2 frame is seen, or any CMD=1 frame that is
  neither the host's own request nor the addressed module's reply to it;
- never send CMD=2; send CMD=1 only in the compatibility test, never in a provisioning session;
- never be connected to a bus with an M5 on it.

**C5 — single-module unlock and full page validation.** Unlock is keyed to the chip serial number
(§4.9). Every page is validated before programming and again at boot (§5.2).

**C6 — magics and tags.** Every subcommand that leaves RAM, changes mode or clears state carries a
16-bit magic or an 8-bit tag in `ARG` (§4.6). `STAGE_DATA` cannot — its ARG is data — and a staged word
can therefore equal another subcommand's magic, so a one-bit SUB error can turn it into, e.g., `RESET` or
`STAGE_ADDR`. Every such case fails safe: the resulting action is either harmless in factory mode (`STAGE_ADDR` moves the
index; a mis-decoded `LOCK` ends factory mode and discards the buffer) or is caught by the page CRC at commit.

### 3.3 Residual risks

- **An installed module with no running M5** — M5 unplugged for diagnostics (§9.3), held in reset,
  separately powered, or booting slower than 3 s — becomes write-eligible 3 s after its reset. A write
  still needs a deliberate SERNUM-keyed unlock from a host, which C4 forbids on an arm bus.
- **Host request frames** with ID 1–16 on a live arm (T5) cannot be prevented by the module; C4 is the
  only defence.
- **Duplicate detection is not reliable at protocol level.** Two modules at one ID may give identical
  replies that do not collide visibly, or one transceiver may dominate and mask the other completely.
  SERNUM keying guarantees that **at most one** of them can be unlocked, so nothing is written twice; it
  does not guarantee the **right** one is written. §3.4 closes this procedurally.
- `SERNUM_DIGEST` is 16 bits: two parts collide with probability ≈ 1 / 65 536. Irrelevant under §3.4.
- Diagnostic counters are RAM and are lost when a module loses power (§9.3).

### 3.4 Station bus rule (normative)

**During provisioning (`SET_ID`) and calibration, exactly one module is connected to the station bus.**
The station reads `GET_SERNUM` at the start and records it with every result; the part it fits is then by
construction the part it reads. Benches with several modules may use read-only subcommands and
`LATCH_SYNC` only.

---

## 4. CMD=3 sub-protocol

### 4.1 Payload

```
P[20:16] = SUB     5 bits
P[15:0]  = ARG     request argument / DATA in replies

d0 = P & 0x7F
d1 = (P >> 7) & 0x7F
d2 = ((SUB & 0x1F) << 2) | ((ARG >> 14) & 0x03)          // == (P >> 14) & 0x7F
```

No legal SUB/ARG sets an MSB in d0–d2; the encoding round-trips through `encoder/src/main.cpp:203`.

### 4.2 Addressing

| Frame | Header ID | Acted on by |
|---|---|---|
| addressed request | 1–31 | the module whose `device_id` equals it |
| broadcast request | 0 | every module, **only** for `SUB = LATCH_SYNC` with its magic; anything else at ID 0 is ignored |
| reply | 0 | no module |

No reply carries `SUB = 0x14`, because `LATCH_SYNC` is the only subcommand that never replies. A module
hearing its own reply, or another module's, therefore ignores it.

### 4.3 General rules

1. One request produces **at most one** reply.
2. **Broadcast requests never produce a reply**, including NAKs.
3. A closed read gate produces silence.
4. Otherwise a request is answered by a reply echoing its SUB, or by a NAK — except a correctly formed
   `RESET`, which restarts the module without replying.
5. A non-zero ARG to a subcommand that takes none is ignored.
6. **Records.** `GET_ANGLE_RAW`, `GET_ANGLE_COMP`, `GET_LATCHED`, `GET_ERRCNT` and `GET_SAMPLE` each have a *record*.
   Reading **index 0** captures that subcommand's whole record atomically and returns field 0; every other
   index returns a field of **that subcommand's** last captured record. An index > 0 read before any
   index-0 read of the same subcommand since reset is NAK'd `SEQUENCE`. Records of different subcommands
   are independent. Hosts always read index 0 first. `GET_CAL_WORD` has no record: USERROW changes only
   through the host's own `COMMIT_CAL`/`SET_ID`.
7. **Accepted** means answered with a non-NAK reply, or applied without reply (`LATCH_SYNC`, `RESET`).
   Only accepted requests restart the factory timer.
8. **One request outstanding.** The host sends the next request only after the reply, or after the
   timeout plus a further quiet period of the same length, so that a late reply cannot be attributed to
   the next request.
9. **Latency**, measured at the module's bus pins: a reply starts within **1 ms** of the end of the
   request, except `COMMIT_CAL` and `SET_ID`, within `T_PROG_MAX` = **50 ms** (❓ USERROW programming
   time, O2). Host timeouts are 2 ms and 100 ms **plus the host's own round-trip latency**, which the host
   measures with `PING` at session start (USB–RS-485 adapters typically add milliseconds). Replies echo
   SUB but not the index, so rule 8's quiet period is what protects indexed reads such as `GET_SERNUM`.
10. **Retries.** Reads, `STAGE_ADDR`, `LOCK`, `CLR_ERRCNT` and `UNLOCK_2` in factory mode are idempotent
    and may be retried. `STAGE_DATA` is not: after a timeout, reissue `STAGE_ADDR(i)` then `STAGE_DATA`.
    `COMMIT_CAL` and `SET_ID` must not be retried blindly: probe `PING` at **both** the old and the new ID,
    then at whichever answers read `GET_HEALTH`, `GET_CAL_STATUS` and all 16 `GET_CAL_WORD`s to establish
    the outcome.
11. **NAK precedence.** Checks run in this order and the first failure is reported: SUB known and not
    reserved (`UNSUPPORTED`) → addressing (`BAD_ADDRESSING`) → gate W (`NOT_ELIGIBLE`) → gate F
    (`NOT_UNLOCKED`) → sequence (`SEQUENCE`) → magic or tag (`BAD_ARG`) → index range (`BAD_INDEX`) →
    operation-specific (`STAGING_BUSY`, `CRC_FAIL`, `BAD_PAGE`, `WRITE_FAIL`, `SENSOR_FAIL`).

### 4.4 Gates

| Gate | Meaning |
|---|---|
| **R** | read gate open (§3.2 C2) |
| **W** | R, **and** write-eligible (§3.2 C3), **and** addressed (not broadcast) |
| **F** | W, **and** factory mode active |

Gate R closed → silence. W or F failed while R is open → NAK.

### 4.5 NAK

`ID = 0, CMD = 3, SUB = 0x00, DATA = (rejected_SUB << 8) | reason`

| Reason | Name | When |
|---|---|---|
| 0x01 | *reserved* | would be BUS_BUSY; never transmitted (rule 3) |
| 0x02 | NOT_UNLOCKED | gate F failed: factory mode not active |
| 0x03 | BAD_ARG | wrong magic or tag |
| 0x04 | BAD_INDEX | index or value outside its range |
| 0x05 | CRC_FAIL | page CRC-16 mismatch |
| 0x06 | WRITE_FAIL | USERROW program or read-back verify failed, or VDD below `VDD_MIN_PROG` |
| 0x07 | UNSUPPORTED | unknown or reserved SUB, or SUB 0x00 as a request |
| 0x08 | SENSOR_FAIL | reserved; no v5 subcommand accesses the sensor synchronously |
| 0x09 | BAD_ADDRESSING | broadcast-only SUB sent addressed |
| 0x0A | SEQUENCE | out-of-order request: `UNLOCK_2` not armed, `UNLOCK_1` in factory mode, record index before index 0 |
| 0x0B | NOT_ELIGIBLE | gate W failed: `arm_seen`, or running < 3 s since reset |
| 0x0C | BAD_PAGE | page fails field validation, or `SET_ID` on a non-virgin invalid page |
| 0x0D | STAGING_BUSY | `SET_ID` while the staging buffer holds uncommitted data |

### 4.6 Subcommands

| SUB | Name | ARG | Reply DATA | Gate |
|---|---|---|---|---|
| 0x00 | *NAK* | — | reply only; as a request → NAK UNSUPPORTED | — |
| 0x01 | PING | — | `0xA5A5` | R |
| 0x02 | GET_FW_VER | 0–3 | 0: `major<<8 \| minor`; 1: `patch`; 2: first 4 hex digits of the commit hash; 3: bit 0 = built from a dirty tree | R |
| 0x03 | GET_PROTO_VER | — | `5` — the protocol version, unchanged by spec v6 | R |
| 0x04 | GET_DEVICE_ID | — | §4.7 | R |
| 0x05 | GET_HEALTH | — | §4.7 | R |
| 0x06 | GET_STAT | — | STAT as received in the most recent transaction, whether or not it passed | R |
| 0x07 | GET_DMAG | — | D_MAG, raw (bits 9:0), cached (§6.3) | R |
| 0x08 | GET_ENV | 0–1 | 0: FSYNC raw, cached (§6.3), host converts per §2.6; 1: VDD in mV, measured at start-up and on every housekeeping transaction (§5.5, §6.3) | R |
| 0x09 | GET_SAFETY | — | safety word as received in the most recent transaction | R |
| 0x0A | GET_ANGLE_RAW | 0–4 | record §4.7 | R |
| 0x0B | GET_ANGLE_COMP | 0–1 | record §4.7 | R |
| 0x0C | GET_LATCHED | 0–3 | record §4.7 | R |
| 0x0D | GET_ERRCNT | 0–7 | record §4.7 | R |
| 0x0E | CLR_ERRCNT | `0xC1EA` | `0` — clears counters and sticky health bits | R |
| 0x0F | GET_CAL_WORD | 0–15 | USERROW word *n*, as stored | R |
| 0x10 | GET_CAL_STATUS | — | §4.7 | R |
| 0x11 | GET_SERNUM | 0–4 | `SIGROW.SERNUM[2n] \| SERNUM[2n+1] << 8` | R |
| 0x12 | GET_CFG_VERIFY | — | §4.7 | R |
| 0x13 | GET_TRIM | 0–4 | cached whole register, raw: 0 MOD_3, 1 OFFX, 2 OFFY, 3 SYNCH, 4 IFAB | R |
| 0x14 | LATCH_SYNC | `0x1A7C` | **never replies**; broadcast only (§4.8) | R |
| 0x15 | GET_RUN_WORD | 0–15 | word *n* of the page the module is **running**, CRC included; after a failed write this is the only readable copy of the calibration. On the build default (no page) every word reads `0xFFFF`, as a virgin page does | R |
| 0x16 | SAMPLE_START | `0x5A00 \| e`, e 0–10 | `0`; starts averaging K = 2^e readings (§4.10) | R |
| 0x17 | GET_SAMPLE | 0–11 | record §4.7 | R |
| 0x18 | UNLOCK_1 | `0x5A17` | `0` | W |
| 0x19 | UNLOCK_2 | `0xA5E8 ^ SERNUM_DIGEST` | `0` | W |
| 0x1A | STAGE_ADDR | `0xA500 \| index`, index 0–15 | index | F |
| 0x1B | STAGE_DATA | 16-bit word | next index | F |
| 0x1C | COMMIT_CAL | `0xC0DE` | new effective `device_id` | F |
| 0x1D | SET_ID | `0x5E00 \| id`, id 1–30 | new effective `device_id` | F |
| 0x1E | LOCK | `0x10CC` | `0`; idempotent | R |
| 0x1F | RESET | `0x8EE7` | **no reply**; module restarts. Wrong magic → NAK BAD_ARG | F |

### 4.7 Payload definitions

**GET_DEVICE_ID**: bits 7:0 effective `device_id`; bit 8 = 1 if from USERROW, 0 if the build default;
bits 15:9 zero.

**GET_HEALTH**

| Bit | Name | Kind | Meaning |
|---|---|---|---|
| 0 | CAL_INVALID | live | the **running** identity is not from a valid page (build-default ID, no compensation). Reflects what the module is doing; the stored page is reported by GET_CAL_STATUS |
| 1 | CAL_VER_UNSUPPORTED | live | magic present, `LAYOUT_VER` ≠ 1 |
| 2 | SENSOR_CFG_FAIL | live | last config lock failed; compensation suspended (§6.2) |
| 3 | SAFETY_CRC_ERR | sticky | ≥ 1 safety-word CRC failure |
| 4 | SENSOR_STAT_ERR | sticky | ≥ 1 read with a status fault |
| 5 | SENSOR_NO_RESPONSE | sticky | ≥ 1 read of all-zeros or all-ones |
| 6 | *reserved* | | 0 |
| 7 | ANGLE_STALE | live | the value being sent is **held** from an earlier transaction (§6.2) |
| 8 | FACTORY_MODE | live | factory mode active |
| 9 | USERROW_WRITE_FAIL | sticky | ≥ 1 failed USERROW program |
| 10 | ARM_SEEN | live | a CMD=2 frame has been seen since the last reset |
| 11 | WRITE_ELIGIBLE | live | gate W would pass now |
| 12 | NO_VALID_ANGLE | live | no transaction has been passed or passed through since reset; the module is sending 0 (§6.2) |
| 13 | ANGLE_DEGRADED | live | the angle being sent comes from a transaction that failed a status check, passed through under the persistent-fault rule (§6.2) |
| 15:14 | *reserved* | | 0 |

Live bits reflect current state; sticky bits are set by events and cleared only by `CLR_ERRCNT`.

**GET_ANGLE_RAW record** — captured together from one sensor transaction:

| Index | Field |
|---|---|
| 0 | raw15 in the **upstream mapping**, `(raw15 << 6) \| (raw15 >> 9)`, bits 15:0 |
| 1 | same, bits 20:16 |
| 2 | raw15 — the fit input of §7.2 |
| 3 | sample sequence number: `uint16_t`, wraps, advances on every **angle** transaction (§6.1), successful or not; housekeeping and config-lock transactions do not advance it |
| 4 | bit 0: this transaction passed §6.2; bit 1: compensation active |

**GET_ANGLE_COMP record**: index 0 = the value CMD=1/2 would send now, bits 15:0; index 1 = bits 20:16.

**GET_LATCHED record**: 0 = latched compensated angle, bits 15:0; 1 = bits 20:16; 2 = latched raw15;
3 = bits 7:0 latch count mod 256, bit 8 latched sample valid (neither held nor degraded), bit 9 at least one
latch since reset.

**GET_ERRCNT record** — all fields captured at once, so rates are consistent:

| Index | Field |
|---|---|
| 0 | total angle transactions (§6.1), bits 15:0 (32-bit, wraps after 49 days at 1 kHz) |
| 1 | total angle transactions, bits 31:16 |
| 2 | safety-word CRC failures |
| 3 | reads with a status fault |
| 4 | no-response reads |
| 5 | CMD=3 requests addressed to this module, or LATCH_SYNC broadcasts, dropped by the read gate |
| 6 | CMD=3 requests NAK'd |
| 7 | USERROW program failures |

Indices 2–7 are `uint16_t`, saturating.

**GET_SAMPLE record** — the result of the last `SAMPLE_START` (§4.10):

| Index | Field |
|---|---|
| 0 | status: bit 0 done, bit 1 aborted, bit 2 an accumulator saturated; bits 11:8 = e |
| 1 | readings that passed §6.2 (`n`); only these are accumulated |
| 2 | readings that failed, including any passed through under the persistent-fault rule |
| 3 | raw15 of the first passing reading — the reference `r₀` |
| 4–5 | Σ wrap₁₅(raw15 − r₀), `int32_t` |
| 6–7 | Σ wrap₁₅(raw15 − r₀)², `uint32_t`, saturating (sets status bit 2) |
| 8–9 | compensated output of the reference reading, 21-bit — `c₀` |
| 10–11 | Σ wrap₂₁(output − c₀), `int32_t` |

`wrap₁₅` and `wrap₂₁` map a difference into [−2¹⁴, 2¹⁴) and [−2²⁰, 2²⁰). The mean sensor code is
`r₀ + Σ/n` and the mean output `c₀ + Σ/n`, both fractional; averaging differences keeps the mean correct
across the 0°/360° seam. While status bit 0 is clear the other fields are partial and must not be used.

**GET_CAL_STATUS** — describes the page **as stored in USERROW now**, which after a failed commit may
differ from what the module is running (§4.9):

| Bit | Meaning |
|---|---|
| 0 | page valid (bits 1–4 all set) |
| 1 | magic ok |
| 2 | `LAYOUT_VER` supported |
| 3 | CRC-16 ok |
| 4 | fields ok (§5.2) |
| 5 | compensation active in the running module |
| 6 | stored page is virgin (all `0xFF`) |
| 7 | running identity and coefficients differ from the stored page |
| 15:8 | `LAYOUT_VER` byte as stored |

**GET_CFG_VERIFY** — result of the most recent config lock (§6.2). `0x001F` = pass.

| Bit | Check |
|---|---|
| 0 | MOD_1 written and read back under mask |
| 1 | MOD_2 written and read back under mask |
| 2 | CRCPAR recomputed, written and read back |
| 3 | STAT.SFUSE clear afterwards |
| 4 | every safety word during the sequence had a valid CRC and `S_ERR` = `S_ACC` = 1 (`S_RST` is ignored, §6.2) |
| 15:8 | number of config-lock attempts since reset, saturating at 255 |

### 4.8 Broadcast synchronous latch

`ID = 0, CMD = 3, SUB = 0x14, ARG = 0x1A7C`

Each module whose read gate is open copies its current compensated angle, raw15 and validity into a
holding register and increments its latch count. No module replies. A module with a closed gate ignores
the latch, which silence cannot reveal. Counts start at reset, so modules reset at different times differ;
the host therefore reads index 0 then index 3 of every module **before and after** each latch, and accepts
the snapshot only if every count advanced by exactly one and every valid bit is set. Addressed
`LATCH_SYNC` → NAK BAD_ADDRESSING.

### 4.9 Factory mode

This mechanism prevents **accidents**; it is not security — the magics are public.

**Unlock.**

1. `UNLOCK_1`, `ARG = 0x5A17` — arms the module for 1 s.
2. `UNLOCK_2`, `ARG = 0xA5E8 ^ SERNUM_DIGEST` — must be the **next CMD=3 request whose header ID equals
   this module's `device_id`**, within the 1 s. Replies (ID 0) and frames for other IDs do not count.

`SERNUM_DIGEST` is CRC-16/CCITT-FALSE over the ten bytes `SIGROW.SERNUM0..9`, read by the host with
`GET_SERNUM`. Disarmed by: any other request to this module; any CMD=1 or CMD=2 frame on the bus; a
wrong ARG; the timeout. The offending `UNLOCK_2` is NAK'd `SEQUENCE` (not armed) or `BAD_ARG` (armed,
wrong digest). `UNLOCK_1` while armed re-arms and restarts the 1 s window.

While factory mode is active: `UNLOCK_1` → NAK SEQUENCE, no state change; `UNLOCK_2` with the correct
digest → reply `0`, no state change (so a retry after a lost reply is safe); with a wrong digest → NAK
BAD_ARG, factory mode continues.

**Factory mode ends on** any of: 5 s without an accepted request to this module; `LOCK`; any CMD=1 or
CMD=2 frame on the bus; a successful `COMMIT_CAL` or `SET_ID`; `RESET`. Ending factory mode discards the
staging buffer.

**Staging buffer** — 32 bytes, RAM.

| Event | Effect |
|---|---|
| successful `UNLOCK_2` (entering factory mode) | filled with `0xFF`; index = 0; state CLEAN |
| `STAGE_ADDR(i)` | index = *i* |
| `STAGE_DATA(w)` | word[index] = *w*; index++; state DIRTY. At index 16 → NAK BAD_INDEX, nothing written |
| `COMMIT_CAL`, page fails §5.2 | NAK `CRC_FAIL` or `BAD_PAGE`; buffer, USERROW, running state and factory mode unchanged |
| `COMMIT_CAL`, program or verify fails | see *write failure* below |
| `COMMIT_CAL` or `SET_ID` succeeds | factory mode ends; buffer discarded |
| factory mode ends for any other reason | buffer discarded |

**COMMIT_CAL** on a valid buffer: check VDD ≥ `VDD_MIN_PROG` (§5.5); program USERROW; read back and compare;
on success reload identity and coefficients from USERROW, reply with the new `device_id`, end factory
mode. If the ID changed, the module answers only to the new ID and must be unlocked again for any further
write.

**Write failure** (VDD low, program error, or read-back mismatch): NAK `WRITE_FAIL`; set
`USERROW_WRITE_FAIL` and count it. The module **keeps running its previous identity and coefficients** and
stays in factory mode with the staging buffer intact, so the host can retry `COMMIT_CAL`. USERROW contents
are then unknown; `GET_CAL_STATUS` reports the stored page and bit 7 shows that it differs from what is
running. If the module is reset in this state it boots from whatever USERROW holds — possibly as ID 31
without compensation. The station must not release a part until a commit has succeeded and been read back.

**SET_ID** — test-station path, leaves calibration untouched. It builds its page in a private buffer, not
the staging buffer, from the **running** state:

| Running state | USERROW | Staging buffer | Effect |
|---|---|---|---|
| any | any | DIRTY | NAK STAGING_BUSY |
| from a valid page | any | CLEAN | running page with `DEVICE_ID` replaced, CRC recomputed; commit as above |
| build default | **virgin** (all `0xFF`) | CLEAN | identity page — magic, `LAYOUT_VER` 1, the new ID, `STATION_ID` 0, `N_HARM` 0, `CAL_DAY` 0, zero coefficients, CRC; commit |
| build default | invalid, not virgin | CLEAN | NAK BAD_PAGE; nothing written. The page may hold recoverable data; replacing it takes a deliberate `STAGE_*` / `COMMIT_CAL` |

Because the source is the running state, which a write failure leaves unchanged, a `SET_ID` that fails with
`WRITE_FAIL` can simply be retried.

**RESET** restarts the MCU. Afterwards the read gate is closed for 100 ms and the module is not
write-eligible for 3 s; the host waits ≥ 3.2 s.

### 4.10 Averaged sampling

`SAMPLE_START(e)` makes the module take K = 2^e (1–1024) angle transactions (§6.1), spaced
`SAMPLE_SPACING` = 200 µs — at least two sensor update periods at FIR_MD 2 (§2.7) — and accumulate
`GET_SAMPLE`'s record. Each is an ordinary angle transaction: it updates the cached angle, the sequence
number and the counters. K = 1024 takes ≈ 205 ms.

- It runs inside `loop()` without blocking; CMD=3 requests are still served meanwhile.
- A new `SAMPLE_START` restarts it. Any CMD=1 or CMD=2 frame aborts it (status bit 1).
- Gate R only: it needs no unlock, since it changes nothing persistent, and cannot start on a live arm.
- Whether readings 200 µs apart are independent is not guaranteed by the datasheet. The station therefore
  measures the scatter of repeated averages directly rather than assuming σ/√K (§7.2 step 2); bench
  item §8.4.9.

---

## 5. USERROW layout

### 5.1 Layout version 1

32 bytes at `0x1300`, 16 little-endian words.

| Word | Bytes | Field | Type | Meaning |
|---|---|---|---|---|
| 0 | 00–01 | MAGIC / LAYOUT_VER | u8, u8 | `[7:0]` = `0x4B` (`'K'`); `[15:8]` = `1` |
| 1 | 02–03 | DEVICE_ID / STATION_ID | u8, u8 | `[7:0]` ID 1–30; `[15:8]` calibration station |
| 2 | 04–05 | CAL_DAY / N_HARM | u12, u4 | `[11:0]` days since 2026-01-01 (0 = unknown; last 2037-03-19); `[15:12]` harmonics populated, 0–6 |
| 3 | 06–07 | H1_AMP | i16 | amplitude, 21-bit LSB |
| 4 | 08–09 | H1_PHASE | u16 | phase, 65536 = 360° |
| 5–14 | 0A–1D | H2…H6 | | as H1: harmonic *k* has `AMP` in word 2k + 1, `PHASE` in word 2k + 2 |
| 15 | 1E–1F | CRC16 | u16 | CRC-16/CCITT-FALSE (poly `0x1021`, init `0xFFFF`, no reflection, no final XOR) over bytes 00–1D |

One 21-bit LSB = 360 / 2²¹ = 0.000172°; an `int16` amplitude spans ±5.625°. Every field the brief
requires is present. Calibration temperature, a sequence counter and a 16-bit magic were dropped to fit
six harmonics; the station keeps those in its own records, keyed by `SERNUM`.

### 5.2 Page validation

One function, used at boot and on the staging buffer before `COMMIT_CAL`. Checks in this order; the first
failure determines the NAK:

| # | Check | NAK at commit |
|---|---|---|
| 1 | CRC-16 over bytes 00–1D equals word 15 | CRC_FAIL |
| 2 | `MAGIC == 0x4B` | BAD_PAGE |
| 3 | `LAYOUT_VER == 1` | BAD_PAGE |
| 4 | `1 ≤ DEVICE_ID ≤ 30` | BAD_PAGE |
| 5 | `N_HARM ≤ 6` | BAD_PAGE |
| 6 | harmonic slots `k > N_HARM` are `0x0000` in both words | BAD_PAGE |

Why the ID range matters: a page with ID 33 would transmit as wire ID 1, because `makePacket21` masks it
(`encoder/src/main.cpp:120`), and would answer the M5's own trigger, because
`prev_id = (33 − 1) & 0x1F = 0` (`:336`). ID 0 is the master and reply address; ID 31 is reserved for
unprovisioned modules (§5.4).

A virgin part reads all `0xFF`: CRC fails (`CRC16(30 × 0xFF) = 0x5FBD`) and so does the magic.

### 5.3 Boot

```
valid     → device_id from page; compensation on if N_HARM ≥ 1
not valid → device_id = DEVICE_ID (build flag); compensation off; upstream mapping; CAL_INVALID
            CAL_VER_UNSUPPORTED additionally if MAGIC ok and LAYOUT_VER ≠ 1
```

### 5.4 Build default and ID ranges

The single shared hex is built with `-DDEVICE_ID=31`. *(v6.1: both are now so. Upstream had
`-DDEVICE_ID=3` in `platformio.ini` and a fallback of 1 in `main.cpp` — 1 being the ID that would answer
the M5's own trigger. This paragraph used to say "currently", which after the change invited a reader to
"fix" a non-problem.)*

| ID | Use |
|---|---|
| 0 | M5 / master address; all CMD=3 replies; broadcast |
| 1–16 | joints on an arm |
| 17–30 | provisionable, not used by the M5 |
| 31 | unprovisioned (build default); never written to a page |

An unprovisioned module has `prev_id = 30`: no such module exists on an arm, so it is inert there.

### 5.5 USERROW caveats

- USERROW survives a UPDI chip erase **on an unlocked device**; a chip erase of a locked device clears it.
  Neither upstream nor this design sets lock bits. ❓ datasheet confirmation.
- Brown-out detection is off (`encoder/platformio.ini:35`) and stays off (fuses unchanged). Programming
  is therefore guarded by a VDD measurement before every commit: **`VDD_MIN_PROG` = 4.5 V** (D19). That
  is the ATtiny1616's own minimum for 20 MHz operation (speed grade 0–20 MHz at 4.5–5.5 V), and upstream
  runs at 20 MHz (`encoder/platformio.ini:30,36`), so the module must be on a 5 V supply. A board below 4.5 V
  is running out of specification already; the station sees `WRITE_FAIL` at once, and the measured value
  through `GET_ENV` index 1. VDD is measured with the ADC against the internal reference, whose accuracy
  (a few percent, ❓ O2) is not subtracted: a supply sagging close to 4.5 V — a loaded USB port, say — can
  give a spurious `WRITE_FAIL`. That fails safe; stations supply ≥ 4.75 V at the module.
- Power loss during programming leaves an invalid page; the part then boots as ID 31 without
  compensation. It can only happen at a station, which reads back after every commit.

---

## 6. Sensor read path and health

### 6.1 Per-read transaction

Every read — after each CMD=1/CMD=2 reply, and every `SSC_INTERVAL_MS` otherwise, exactly as upstream
schedules it — is **one** SSC transaction:

```
command  READ | ADDR 0x00 | ND 3   →   STAT, ACSTAT, AVAL, safety word
```

80 SSC clocks in one CS-low window; STAT is checked on every read as the brief requires; one safety word
covers all three registers; the CRC-8 is table-driven (256 bytes of flash).

### 6.2 Start-up, outcome, fallback

**Start-up.** `setup()` completes all of the following **before the first frame is answered**: read and
validate USERROW; wait `t_pon` = 7 ms (§2.7); run the config lock; read until one transaction passes, up
to 10 attempts. Total ≈ 9 ms, against upstream's `setup()` of microseconds. *(v6.1: ≈ 9 ms is the healthy
case; a sensor reporting `S_RST` re-runs the configuration lock on each attempt, so a bad start-up reaches
≈ 12 ms. §8.4 item 7 should be measured on both.)* While it runs the module does
not answer, so **every downstream module receives no trigger**, and the M5 keeps streaming their last
angles as valid (`_valid[]` is never cleared, §1.5). At power-up the M5 is not yet polling (§1.4), so this
costs nothing; on a module reset during operation it freezes the downstream joints for ≈ 9 ms, against
upstream's shorter but similar gap.

If no read passes, the module enters `loop()` with `NO_VALID_ANGLE` set and sends 0 until a transaction is
passed or passed through under the persistent-fault rule below. The M5
does **not** fault on this: it boots in STANDBY (`M5/src/main.cpp:425`), where every frame simply becomes the
reference angle (`:219-223`), so a 0 present from start-up is accepted as a valid angle. This is the same
as upstream with a dead sensor, and is visible only through CMD=3.

**Outcome of each transaction**, evaluated in order:

| Condition | Outcome |
|---|---|
| all words `0x0000` or all `0xFFFF` | **fail**, no-response |
| safety CRC mismatch | **fail**, CRC |
| safety `S_RST = 0` | sensor has reset and lost its volatile configuration: **re-run the config lock**; this read **fails** |
| safety `S_ERR`, `S_ACC` or `S_ANG` = 0, or `STAT & STAT_FAULT` ≠ 0 | **fail**, status |
| otherwise | **ok** |

On **ok**: update the cached angle (compensated if active), clear ANGLE_STALE and NO_VALID_ANGLE.
On **fail**: keep the previous valid value, set ANGLE_STALE, count the cause, set the sticky bit.

**Persistent faults** (D18). Every failed angle transaction, whatever the cause, advances a consecutive-
failure count; a passing one resets it. Once the count has reached **20** (≈ 20 ms on an arm), a failed
transaction whose failure is **only** in the status row — `S_ERR`, `S_ACC`, `S_ANG` or `STAT_FAULT`, with a
valid CRC — is passed through: its angle is sent (compensated if active), ANGLE_DEGRADED is set, and
ANGLE_STALE and NO_VALID_ANGLE are cleared. No-response, CRC failures and `S_RST` (whose configuration may
be lost) are never passed through; for them the last value is still held, with ANGLE_STALE set.
Passed-through readings count as failures in GET_SAMPLE and are not accumulated; a latch taken on one has
its valid bit clear. Rationale: a frozen angle looks healthy to
the M5, which cannot see any flag (§9.2); a live but degraded angle is at least subject to the M5's jump
detection. This departs from the brief's "hold the last valid value" for faults lasting over 20 ms, by
decision of 2026-09-19.

**Config lock**: write MOD_1; write MOD_2; recompute and write CRCPAR; read back and compare under mask;
confirm `SFUSE` clear; cache the trim registers. Recorded in `GET_CFG_VERIFY`. Within the lock, `S_RST = 0`
is expected (the first transaction after a sensor reset reports it) and is ignored; the row "`S_RST = 0` →
re-run the lock" applies only outside it. Duration *(v6.1, as built)* **576 SSC clocks** plus CRC work — one 10-word read of MOD_1…TCO_Y, three
single-register writes, one read-back of the same ten words, one STAT read — which is ≈ 0.25 ms at the
≈ 0.44 µs/clock the v2 cycle model implies, so the ≈ 0.3 ms budgeted below still holds. (v6 said ≈ 400
clocks; that count was wrong, the duration was not.) In `loop()` a
retry runs in place of a housekeeping transaction, after the reply, so it adds ≤ 0.3 ms to that cycle's
read step (still inside the ≈ 870 µs slack of §8.1) and can delay a CMD=3 reply by the same amount,
inside rule 9's 1 ms.

**If the config lock fails**: set SENSOR_CFG_FAIL, **suspend compensation** — output the upstream mapping,
exactly what an uncalibrated module sends — and retry the lock on every 16th read until it succeeds, then
resume compensation. Rationale: the stored fit is only valid for the locked configuration, while holding
the angle would freeze the joint; the upstream mapping is the known-good fallback. The switch moves the
reported angle by at most Σ|A_k| — well under the M5's 30° jump threshold for any realistic part (§2.8:
a few degrees of raw error at most), though the format itself permits up to 33.75°.

### 6.3 Housekeeping reads

On every 16th read, one additional transaction reads D_MAG or FSYNC, alternately (48 clocks). Cached
values are ≤ 32 reads old: ≤ 32 ms on an arm, ≤ 0.64 s on the bench.

---

## 7. Compensation

### 7.1 Model

```
θ_s    = raw15 × 360° / 32768                      sensor angle
Δ      = Σ_{k=1..N_HARM} A_k · sin(k·θ_s + φ_k)    in 21-bit LSB
u_out  = ( (raw15 << 6) + round₈(Δ) )  mod 2²¹     if compensation is active; round₈ = to a multiple of 8 LSB
u_out  = (raw15 << 6) | (raw15 >> 9)               otherwise (upstream, bit-exact)
```

Compensation is active when the **running** calibration came from a valid page, `N_HARM ≥ 1` and
SENSOR_CFG_FAIL is clear. The correction
is **added**. `mod 2²¹` is a mask on a 32-bit value; it makes the seam correct with no special case, and
`k·θ_s` is reduced modulo a full turn, so each harmonic is continuous across the seam.

**Why the output is a multiple of 8 LSB (D22).** The M5 converts the 21-bit value to float32 degrees and
then **integrates differences** every cycle (`M5/include/AngleProcessor.h:68-72`), re-referencing to the
absolute reading only at boot or zeroing. Upstream's mapping moves in steps whose float32 images add
without accumulating (exactly below 64°; above it with a bounded, non-growing image rounding of
≈ 3 × 10⁻⁵°). A compensated output moving by arbitrary LSB counts does not: when the
sensor angle is below 64° and the joint is far from its zero, the adds round, the rounding is not
symmetric over the back-and-forth that sensor noise produces, and the angle **drifts** until the next
zeroing — more than 0.01° per hour at 128° or more from the zero (0.004–0.025° per hour in the cases
simulated by the review and by the author, up to 0.15° per hour on the review's grid), and
0.002–0.007° per hour between 64° and 128°. A multiple of 8 LSB is a multiple of 45 × 2⁻¹⁵ degrees, exactly
representable in float32 below 512°, so every add is exact and the drift is zero
(`system_float32_unwrap_drift.py`, `author_s3_check.py`). 8 is the smallest step for which this holds.
The cost is ≤ 4 LSB = 0.00069° of rounding, inside the arithmetic budget (§7.5). The payload keeps its
21-bit scale. `GET_ANGLE_COMP` and `GET_SAMPLE` report the rounded value — what ships.

The upstream mapping, which a calibrated module falls back to while compensation is suspended (§6.2), is
not on the 8-LSB grid. It does not need to be: on its own it shows a bounded, non-growing error of at most
≈ 3 × 10⁻⁵° (float32 image rounding above 64°, not accumulation), and one suspension episode costs at most
that, because rounding to nearest returns to the exact grid when the stream does. Only continuous flapping
between the two mappings while the joint moves accumulates — ≈ 0.01° per hour, in a fault state in which
the angle already jumps by Σ|A_k| every 16 reads — and re-zeroing clears it
(`../v6-verification-scripts/m5_float32_transitions.py`).

### 7.2 Station fitting procedure (normative)

Reference implementation: `evidence/v3-reference/station_fit.py` — the constants, and the computational
part of every step; stage motion, settling, reference polling (§7.7), frame I/O and step 1's discard
rules are the station's.

**What is calibrated (D23).** The **fully assembled encoder unit** — its own horn with its own magnet
bonded and cured, bearing, spacer and PCB, screws at final torque with thread-locker — driven through its horn (§7.7), with
its housing held in the fixture. Not a PCB over a station magnet: another magnet of the same type, or the
same PCB re-seated by 0.1–0.2 mm, leaves 0.2–1.4° of error, no better than uncalibrated (§2.8). After
calibration the spacer and PCB screws are paint-marked; **a broken mark voids the calibration**.
Re-flashing through UPDI needs no disassembly. The bare unit turns a full 360° (user, 2026-09-20).

The counts below are **minimums**. The operating characteristic is established only at these values or
more; with 64 fit and 64 validation positions the gate already mis-grades parts.

| Constant | Value | Meaning |
|---|---|---|
| `N_FIT` | ≥ 128 | fit positions, uniform: `i × 360/N_FIT` |
| `N_VAL` | ≥ 128 | validation positions, interleaved: `(i + ½) × 360/N_VAL`; never used in the fit |
| directions | 2 | every position is measured approaching clockwise and counter-clockwise (D24) |
| `K` | ≥ 1024 | readings averaged per position and direction (`SAMPLE_START` e = 10) |
| `R_MAX` | 0.02° | grade **A** limit on the systematic error, defined below |
| `R_MAX_B` | 0.05° | grade **B** limit; above it the unit is reworked (D25) |
| guard band | 0.95 | the **measured** statistic is compared with 0.95 × the limit |
| `σ_MAX` | `R_MAX` / 6 | largest per-position noise of an average for which a grade is given |
| `HYST_MAX` | 0.10°, **provisional** | limit on the hysteresis half-difference; to be set from bench data (O1) |
| `N_HARM` | 6 | always fitted in full |

**Systematic error** of a unit is the half-range, over the whole circle, of the **direction-mean** of
`E[θ_out] − θ_true` — the largest deviation about the best (minimax) constant — where `E[θ_out]` is the
output averaged over sensor noise. It is what a stored static curve can be held responsible for. It is
independent of any constant, which the M5 owns, and it is **relative to `θ_true`**, i.e. to the station's
reference chain (§7.7), at station conditions (§7.8). Note that the M5 zeroes at **one** jig angle, not at
the minimax constant: relative to that zero a unit within `R_MAX` can deviate by up to 2 × `R_MAX`
elsewhere.

The **hysteresis half-difference** is half the largest difference between the two directions' outputs
at the same position. No static curve can remove it: in use the reading lies within ± that value of the
mean curve, depending on the direction of the last motion. It is recorded per unit and limited.

1. **One unit** on the bus (§3.4), powered **≥ 10 minutes** or until `GET_ENV` index 0 is stable to 1 K
   (the die heats itself by ≈ 11–16 K, §2.8). Record `GET_SERNUM`, ambient and module temperature, VDD
   (`GET_ENV` index 1) and `GET_DMAG`. At each position wait until the reference polls are stationary
   (§7.7), *then* issue `SAMPLE_START`; read `GET_SAMPLE` when done. Discard and repeat a sample with
   status bit 1 or 2 set, or with fewer than 90 % of readings passing.
2. **Noise check.** Re-approach one position 8 times, **always clockwise** — alternating would put the
   hysteresis into the result; `σ_mean` = **circular** standard deviation of
   `θ_true − θ_s` over the 8 samples, i.e. of `wrap(xᵢ − circular_mean(x))`, so that the reference, the
   settling and the approach are inside it and it is correct across the 0° seam. If `σ_mean > σ_MAX`,
   stop with verdict *insufficient data* — no grade. Per-reading σ is recorded from `GET_SAMPLE`'s Σd².
3. **Fit passes, clockwise then counter-clockwise.** At each fit position:
   `θ_s = (r₀ + Σ/n) × 360/32768` from `GET_SAMPLE`; `d = θ_true − θ_s`, with `θ_true` the corrected
   reference reading of §7.7.
4. **Remove the mounting offset**: `c = circular_mean(d)`, i.e. `atan2(mean sin d, mean cos d)`, over both
   passes; `y = wrap(d − c)` into [−180°, 180°).
5. Least-squares fit of the **pooled** samples of both passes,
   `y ≈ a₀ + Σ_{k=1..6} (a_k sin kθ_s + b_k cos kθ_s)`, **including the constant column `a₀`**, then
   **discard `a₀`**. Pooling fits the mean curve of the hysteresis loop, which is Infineon's own practice
   for this sensor family (mean of a left and a right turn).
6. **Convert and commit.** `A_k = round(√(a_k² + b_k²) × 2²¹ / 360)`,
   `φ_k = round(atan2(b_k, a_k) × 65536 / 360°) mod 65536` (`a sin x + b cos x = R sin(x + φ)`). Reject if any
   `A_k > 32767`. Stage, `COMMIT_CAL`, read the page back and compare.
7. **Validation passes**, both directions, on the committed unit: at each validation position the mean
   compensated output `θ_out = (c₀ + Σ/n) × 360/2²¹` from `GET_SAMPLE`. With `e = wrap(θ_true − θ_out)` per
   direction: the hysteresis half-difference is `max |e_cw − e_ccw| / 2`; the graded statistic is the
   half-range of the direction mean `(e_cw + e_ccw) / 2`, centred on its circular mean. The half-range
   needs no offset estimate, so a shift of the offset between passes cancels exactly.
8. **Grade** (`station_fit.py`, `grade()`):

   | Result | Condition | Consequence |
   |---|---|---|
   | **A** | statistic ≤ 0.95 × 0.02° | ships |
   | **B** | statistic ≤ 0.95 × 0.05° | ships with its calibration; below the ≈ 0.05° knee the system cannot tell A from B (§7.8) |
   | **rework** | statistic above that, or hysteresis half-difference > `HYST_MAX` | does not ship: re-seat and recalibrate, or scrap |
   | *insufficient data* | step 2 | fix the station; no grade |

   **A rejected unit is never turned into an identity page and shipped** (v5 did that): an identity page
   is 0.6–1.6° or worse, fifteen to eighty times the error it was rejected for, and nothing on the arm can
   tell it from a calibrated unit (§9.2). The grade lives in the station database (§9.7), not on the module.
9. **Centring gate** (provisional, from the sensor-physics review; `station_fit.py`, `centring()` and
   `H2_MAX`): the fitted H2 amplitude measures how
   far the sensor sits off the rotation axis (H2 ≈ 5.0° × e², e in mm, at a 2.5 mm gap), and the
   calibration's sensitivity to later mechanical shift is proportional to that eccentricity. Units with
   H2 above a limit to be set from the first production data (O1; starting value 0.2°, e ≈ 0.2 mm) are
   re-seated and re-run rather than shipped with a fragile calibration.
10. **Record** the items of §9.7 against `SERNUM`.

Station time at the minimums: 2 × 256 positions × (≈ 205 ms sampling + settling) — about two and a half
minutes per unit.

**Why validation is out of sample, averaged, and on the module's output.** The v4 gate measured the
residual at the fit points from single readings. The v4 verification showed it passed parts with true
error up to 0.029° at sparse sampling, and rejected most good parts on a dense, noisy station — the
datasheet's 0.05° per-reading noise (§2.7) is larger than the error being tested. Validation positions
that the fit never saw bound the error between fit points; averaging brings the noise to
≈ 0.0016°; and measuring the committed module's own output tests exactly what ships.

**Operating characteristic, *measured in simulation*** (`station_sim.py`): 4000 simulated parts, spread
deliberately past the datasheet and with unmodelled H7/H8 content so that both sides of both limits are
populated; 0.05° Gaussian noise per reading; a hysteresis loop of ± 0.05° × (1 + 0.3 sin θ) between the
directions; 15-bit quantisation; the real `ker_compensate()` including the rounding to 8 LSB. The reference
systematic error is computed exactly, as defined above, from the expectation of the output over sensor
noise:

| True systematic error | Parts | A | B | Rework |
|---|---|---|---|---|
| < 0.015° | 858 | 100 % | — | — |
| 0.015 – 0.020° | 353 | 69.4 % | 30.6 % | — |
| 0.020 – 0.040° | 1217 | 0 % | 100 % | — |
| 0.040 – 0.050° | 485 | 0 % | 79.0 % | 21.0 % |
| ≥ 0.050° | 1087 | 0 % | 0 % | 100 % |

**No part above 0.02° was graded A, none above 0.05° was shipped, no part below 0.015° missed grade A
and none below 0.0375° was reworked.** The measured hysteresis half-difference reads 0.067° median against
a true maximum of 0.065° at the sensor: ≈ +0.002°, partly from taking a maximum over noisy positions and
partly real — at the output the loop is wider than at the sensor by the compensation's local gain
(1 + Δ′), up to 15–20 % for a 2.5° part. Both act in the safe direction. The same run with the offset shifted by 0.01° between the fit and validation passes gives the
same grades to within 3 parts in 4000. Below the minimums the guarantee fails: with 64 + 64 positions, 4
parts above 0.02° (up to 0.0209°) were graded A and 2 above 0.05° were shipped; with K = 256 the noise
check returns *insufficient data* on a third of parts. The v5 verification additionally attacked the v5
single-direction gate with parts clustered around `R_MAX`, error carried by H7–H16, asymmetric error, and
correlated noise (AR(1), ρ 0.5–0.95), and found no false accept at the minimums; the v6 statistic averages
two directions and is less noisy than the one it attacked. **All of this is relative to `θ_true`**: a
low-order error of the reference chain passes through the gate unseen (§7.7).

**Why steps 4 and 5.**

`a₀` is the mounting offset. It belongs to the M5 (`mech_joint_offset` and jig
zeroing), and the station cannot know it because the unit is not on its joint yet. But the station
samples uniformly in `θ_true`, so the samples are not uniform in `θ_s`, and an offset left in `y` leaks
into the harmonic coefficients. The circular mean keeps the data away from the ±180° seam; the constant
column absorbs what remains. *Measured* end to end — fit, round, then each fit point's code through the firmware's
own `ker_compensate()` (`station_fit.py`), typical part, noise-free:

| Mounting offset | v3 procedure | **v4–v6 procedure** |
|---|---|---|
| 0° | 0.00687° | 0.00687° |
| 1° | 0.04545° | 0.00664° |
| 5° | 0.21343° | 0.00671° |
| 30° | 1.26284° | 0.00644° |
| 100° | 4.19904° | 0.00660° |
| 180° | rejected | 0.00687° |
| 270° | 3.77904° | 0.00687° |

(Noise-free, so the 15-bit steps and the rounding to 8 LSB show in full; with noise the average output has
neither, §7.5.)

The same run confirms the conversion of step 6, the phase units and the sign of the correction against
the firmware routine.

### 7.3 Why the calibrated base is exact

Upstream's bit replication adds a 0…0.0108° ramp that jumps at 0° (§1.7); no harmonic series can
represent a jump. *Measured* — six harmonics, 15-bit quantised sensor, 10 random phase draws, mean
removed: base `raw15 << 6` gives 0.00571° (good part) / 0.00673° (typical); upstream bit replication gives
0.01096° / 0.01171°.

### 7.4 Fixed-point implementation requirements

1. **16-bit harmonic argument.** `raw15 << 1` is θ_s as an exact 16-bit binary angle, so `k·θ_s + φ_k` is
   exact modulo 2¹⁶ by 16-bit addition. No 32-bit variable shift in the per-harmonic loop; avr-gcc emits
   those as software loops (v2 spent 138 cycles per harmonic on them).
2. **Deferred scaling.** Each term accumulates `(A_k · s) >> 8` into an `int32_t` (a byte move); **one**
   rounding at the end, to a multiple of 8 LSB (§7.1): `((acc + 512) >> 10) * 8`. The arithmetic right shift
   of a negative `int32_t` is relied on (gcc, avr-gcc) and is covered by the AVR differential test, whose
   sets wrap below 0 as well as above.
3. **Sine table.** Quarter wave, Q15, 128 segments, 129 points plus 1 pad (260 bytes), rounded linear
   interpolation. Stays in memory-mapped flash on the ATtiny1616 (*measured*: `.data` = 0, table placed in
   `.rodata` in the mapped flash range at data address ≥ `0x8000`; the exact address depends on the
   image); no `PROGMEM` needed.
4. **Explicit integer widths.** On AVR `int` is 16 bits. The 16-bit interpolation product is correct only
   because the table is fine enough; the generator computes the bound from the table (and checks its
   monotonicity assumption), and `_Static_assert` enforces it — a 64-segment table does not compile.
5. **`n` is bounded by the routine itself**: `n > 6` is treated as uncalibrated.
6. **Host tests are not sufficient** (§11.2).

### 7.5 Error budgets

| Source | Magnitude | Status |
|---|---|---|
| arithmetic vs. double reference — the brief's requirement, **including the rounding to 8 LSB** | **0.003186°** worst case; 0.00085° realistic | *measured*; budget 0.005°, margin 1.57× |
| model residual, six harmonics | 0.006° – 0.04°, depends on the part | *measured in simulation*, §7.6 |
| sensor quantisation, ½ LSB of 15 bits | 0.00549° | physical floor |
| **sensor noise per reading** | **0.05° (1σ)** at FIR_MD 2 | datasheet, §2.7 — random, not removed by compensation |

With noise present, the *average* output has no quantisation sawtooth: the noise dithers the 15-bit steps.
The systematic error an averaging user sees is therefore the model residual alone.

Arithmetic worst case: the per-term errors add, and each harmonic's phase is independent, so the worst
case can be **constructed** rather than searched. For each N the construction picks per-term amplitude and
phase to push the error the same way, then confirms with a full 32768-code sweep:

| N | 1 | 2 | 3 | 4 | 5 | 6 |
|---|---|---|---|---|---|---|
| worst, degrees | 0.001102 | 0.001521 | 0.001940 | 0.002352 | 0.002768 | **0.003186** |

Analytic ceiling for N = 6: 6 × 2.4458 LSB (largest per-term error) + 4 LSB (rounding to a multiple of 8) = 18.67 LSB = 0.003206°. It needs six harmonics of ≈ 5.6° at once, which no real part has.
Realistic coefficients (H1 ≤ 1.5°, each harmonic ÷ 1.7, random signs and phases, 300 sets): 0.000845°, of which the rounding is the larger part.
(v5, before the rounding: 0.002587° worst, 0.000274° realistic; `results-v5/`.)

### 7.6 Harmonic count and fit domain

*Measured in simulation* (`harmonics_v3.py`): worst of 20 random phase draws, 15-bit quantised,
measured-domain fit, residual in degrees:

| Part (H1) | Intrinsic H4–H6 | H1–3 | H1–4 | H1–5 | **H1–6** |
|---|---|---|---|---|---|
| good (0.3°) | none | 0.00696 | 0.00607 | 0.00585 | **0.00579** |
| typical (1.0°) | none | 0.02291 | 0.01181 | 0.00729 | **0.00598** |
| typical (1.0°) | small (2 / 1 / 0.5 %) | 0.05338 | 0.02694 | 0.01388 | **0.00701** |
| large (1.5°) | small | 0.07679 | 0.04004 | 0.01904 | **0.00806** |
| typical (1.0°) | moderate (5 / 3 / 2 %) | 0.11069 | 0.06312 | 0.03159 | **0.00953** |
| worst (2.5°) | small | 0.17620 | 0.09755 | 0.04267 | **0.01857** |
| worst (2.5°) | moderate | 0.33777 | 0.20678 | 0.10593 | **0.03872** |

- Six harmonics beat five in every case (the v3 review confirmed 60 of 60 paired draws); six is also the
  most that fits in 32 bytes.
- Only parts with little intrinsic content above H3 reach the 0.0055° floor. With small H4–H6 a typical
  part reaches ≈ 0.007°; poor parts reach 0.02–0.04°. **Achievable accuracy is set by part quality**: O1.
- The simulation reports quantised angles at the bin centre; the firmware uses the bin floor. The
  difference is a constant, removed with the mean, and changes results by ≤ 3 %.

Fit domain: measured-domain, one pass, vs. true-domain with three fixed-point inversion iterations,
typical part, small H4–H6, quantised — 3 harmonics: 0.05574° vs 0.04114°; **6 harmonics: 0.00661° vs
0.00578°, at 6 vs 18 harmonic evaluations.** Iterating buys 13 % for 3× the computation; the
measured-domain fit (D2) stands on cost.

### 7.7 Station reference chain (normative before production)

Selection record and purchasing notes: `station-reference-encoder.md`. Reference simulation:
`evidence/v3-reference/ref_selfcal.py`. Rewritten in v6 after the station-metrology review, which found
that v5's procedure could neither remove nor detect the coupling's error (F1) and that its check could not
verify its own claim (F2).

**Everything in §7.2 is relative to `θ_true`.** Whatever error `θ_true` has in harmonics 1–6 is written
into every module, and the gate cannot see it, because both passes share it. Error above H6 cannot enter
six harmonics; it costs yield, not accuracy.

**Topology.** The unit under calibration has its own bearing (§2.8), so the chain has two couplings:

```
reference encoder ══ C1 ── stage shaft (dual-shaft stepper) ── C2 ── horn of the unit      housing fixed
      ψ                          θ                                   θ_h → module reads θ_s
```

| Element | Requirement |
|---|---|
| reference encoder | solid shaft with its own bearings (a hollow-shaft or kit encoder breaks the method for H1); single-turn; rated ± 50″, unverified until the incoming test below |
| C1, C2 | encoder-grade diaphragm or flexure couplings with a stated kinematic transfer error (HEIDENHAIN K 14: ± 6″ at 0.1 mm / 0.09°; a metal bellows: ± 40″); torsional stiffness ≥ 150 N·m/rad; **no helical-beam couplings** |
| alignment | ≤ 0.05 mm, ≤ 0.05°, checked with a dial indicator; the fixture locates the unit's housing repeatably |
| reference read-out | its own RS-485 port; polled continuously from before `SAMPLE_START` to after `GET_SAMPLE`; `θ_true` is the mean of those polls; **the position counts only if they are stationary** — their standard deviation no more than twice the static noise found in the incoming test, and the means of their first and second halves within 3″ of each other — otherwise wait and repeat. Stepper hold-current reduction is disabled or waited out |
| environment | away from steel and from the stepper's stray field; orientation of the station recorded (§2.8, stray fields) |

**Incoming test of the reference** (station software only): hold a magnet to the housing while reading —
any change means a magnetic encoder, which is not acceptable for a 72″ tolerance; static noise at 8
angles; repeatability over 16 positions × 10 turns; reversal; a fine scan of ≥ 1000 microsteps over a few
degrees, which shows sub-divisional error and tells optical from magnetic by its period; a 30-minute
warm-up log; register width, latching and maximum baud rate.

**Commissioning — once per station build**, and again whenever the reference, either coupling or the
fixture is disturbed. One unit serves as the transfer artefact; it is powered ≥ 30 minutes beforehand and
its temperature (`GET_ENV` index 0) stays within ± 2 counts of `TEMPR` (one count is 0.36 K, §2.6).

- **Set A — reference side.** The reference and C1 stay clamped together **for good** and are remounted
  as one body on the **stage-side hub** of C1, so that C1's transfer error rotates with the reference and
  is calibrated with it. Ten angles: 0, 45, … 315°, plus **22.5° and 11.25°**, which make H8 and H16 of the
  reference observable. Angles need only be within ± 3°.
- **Order.** Set A **out** (0° … 315°, 22.5°, 11.25°) → the **check mounting** at 100°, which is not used in
  the fit → set A **back** (11.25° … 0°). Running out and back equalises the artefact's drift *within* each
  set. It does not remove the offset between the mean of set A and the mean of set B, which the fit books
  to `Ŝ2` — hence the drift rows of the second table below, and the warm-up requirement above. (One more
  fit column for that offset removes the effect in simulation up to 10 % drift,
  `../v6-verification-scripts/selfcal_drift_mechanism.py`; to be adopted and re-verified with `kercal`.) The
  last clamping of set A is the **production mounting and is never touched again** → set B, out and back,
  on that mounting. 37 turns, about two hours including the remounting.
- **Set B — horn side.** With the housing fixed, the horn is re-clocked in C2 at 8 angles, out and back
  (16 turns). The module's error moves with the horn; C2's transfer error `S2` stays with the stage shaft.
- **Joint fit** of `ψ − θ_s = c_turn + R′(ψ) − S2(ψ − γ_turn) − M(θ_s)`, two passes — the second knows each
  turn's `γ` from the first: `R′` = reference + C1, harmonics 1–20; `S2`, harmonics 1–6; `M`, harmonics
  1–20. Condition number 3.0. Because set B runs entirely on the production mounting, that clamping's own
  deviation is **mostly** absorbed into `Ŝ2` (about 70 %; set A constrains `S2` as well).
- **In production** `θ_true = ψ − R̂′(ψ) + Ŝ2(ψ − γ_production)`.
- **Criteria** (provisional until bench data exist): the *remount reproducibility* — rms over all fitted
  turns of the residual H1–H3 amplitudes — **≤ 8″**; and the check mounting's residual H1–H7 amplitudes all
  **≤ 12″**. Their justification is the second table below: pass rates per fault level, and the worst
  error of any station that passes both.
- **What cannot be calibrated** is the part of `S2` that changes from unit to unit with the fixture
  alignment, and the reference's error above the fitted harmonics (sub-divisional error). Both are budget
  lines; the first is the reason C2 must be an encoder-grade coupling.

*Measured in simulation* (`ref_selfcal.py` → `results/ref_selfcal.txt`; reference error 50″ peak with
content to H40, i.e. beyond the fitted model; stage positions scattered by 0.03° rms about the grid, so
that sub-divisional error is not sampled at one phase; error of `θ_true` **at the horn**, on a production
turn with a **fresh, freshly fixtured unit**; half-range, median / maximum of 100 stations; couplings as
H1 + H2 amplitudes). "H1–H6" is the part of that error lying in harmonics 1–6 — **the only part that can
enter a module's coefficients**; the rest costs gate noise and yield.

| Case | Before | After | of which H1–H6 | Reproducibility | Check mounting |
|---|---|---|---|---|---|
| v5 procedure; C1 40″ + 20″ and C2 10″ + 5″, both unmodelled | 72.2″ / 99.9″ | **52.5″ / 66.9″** — no real gain | 49.5″ / 64.4″ | 0.6″ / 0.8″ | 1.2″ / 2.1″ — **sees nothing** |
| v6 procedure, same couplings, nothing else | 62.0″ / 100.3″ | 6.4″ / 9.3″ | 0.8″ / 1.3″ | 0.7″ / 0.8″ | 1.2″ / 1.9″ |
| + per-clamp error 3″ + 2″, artefact drift 1 % | 62.2″ / 102.8″ | 7.9″ / 12.2″ | 3.5″ / 8.3″ | 2.8″ / 5.7″ | 3.5″ / 7.4″ |
| + sub-divisional error 8″ | 66.8″ / 109.1″ | 13.6″ / 17.7″ | 4.2″ / 9.2″ | 2.8″ / 5.8″ | 3.7″ / 7.8″ |
| + C2 differs 30 % with every fixturing | 67.6″ / 107.3″ | 14.9″ / 20.0″ | 5.6″ / 11.6″ | 3.2″ / 6.0″ | 3.7″ / 7.6″ |
| same, but C2 a bellows, 40″ + 20″ | 74.2″ / 138.9″ | 23.4″ / 40.2″ | **14.7″ / 31.0″** | 6.7″ / 9.6″ | 5.0″ / 11.8″ |
| same, C2 a diaphragm, 6″ + 3″ — **the good station** | 67.3″ / 106.1″ | **14.0″ / 17.9″** | **4.7″ / 9.5″** | 3.0″ / 5.6″ | 3.7″ / 7.1″ |

The first row is the station-metrology review's finding F1/F2 reproduced: under the v5 procedure the
coupling error stays in `θ_true` in full and the check reads the same as on a perfect station.

The criteria, on the good station with one fault at a time, 300 stations per row:

| Station | `θ_true` error, all / H1–H6, median | passes reproducibility | passes check | passes both | worst error among those passing, all / H1–H6 |
|---|---|---|---|---|---|
| good | 14.3″ / 4.7″ | 100 % | 100 % | 100 % | 18.3″ / 9.7″ |
| clamping 6″ + 4″ | 14.6″ / 4.9″ | 100 % | 100 % | 100 % | 19.6″ / 10.5″ |
| clamping 10″ + 5″ | 15.0″ / 5.4″ | 100 % | 70.3 % | 70.3 % | 21.1″ / 12.0″ |
| clamping 20″ + 10″ | 17.2″ / 8.1″ | 0 % | 3.3 % | 0 % | — |
| clamping 30″ + 15″ | 20.1″ / 11.2″ | 0 % | 0 % | 0 % | — |
| artefact drift 2 % | 16.3″ / 7.0″ | 91.7 % | 100 % | 91.7 % | 23.9″ / 13.4″ |
| drift 3 % | 18.5″ / 9.5″ | 66.3 % | 97.0 % | 66.3 % | 23.0″ / 13.7″ |
| drift 5 % | 23.7″ / 15.1″ | 28.0 % | 80.0 % | 28.0 % | 23.4″ / 14.9″ |
| drift 10 % | 37.3″ / 29.8″ | 3.3 % | 33.3 % | 3.3 % | 23.7″ / 12.7″ |

The criteria do not separate good from faulty stations cleanly, and do not need to: **over all fault
levels, no station that passed both had a `θ_true` error above ≈ 24″ (0.0066°), or above ≈ 15″ (0.0041°) in
the harmonics that can enter a module — provided C2 is an encoder-grade coupling and the reference's
sub-divisional error is ≤ 8″, neither of which the criteria can see** (the independent re-verification
found 23.5″ / 15.0″ with another seed and combined faults; with a 20″ sub-divisional error 31″ / 13″, and
with a bellows C2 38″ / 32″, both passing the criteria). The incoming test's fine scan measures the
first; the second is a purchasing requirement. They see a poor C2 only weakly — a bellows raises the
reproducibility from 3.0″ to 6.7″ median, mostly still under the limit, while tripling the low-order error —
which is why C2's type is a requirement and not something the commissioning can certify.

So with encoder-grade couplings `θ_true` is good to about **± 14–18″ (0.004–0.005°)**, of which
**± 5–10″ (0.0015–0.003°)** can reach a module — self-consistent, but **not traceable**: every check compares
the chain with itself through a module. Two things close that: a **check standard** — a second identical
reference on its own coupling, read at every calibration, which detects drift, slip and coupling faults —
and, once per station build, one comparison of H1–H3 against an instrument with its own calibration
chart. Until the second exists, `R_MAX` is stated as "relative to the station reference".

The station review's budget for an accepted grade-A module, absolute, at station conditions: ≈ 0.04–0.05°
with the reference as bought; ≈ 0.025–0.03° with the procedure above.

### 7.8 What the accuracy figures mean

| Figure | What it is | Status |
|---|---|---|
| 0.003186° | worst arithmetic error of the firmware against exact arithmetic (§7.5) | *measured* |
| 0.02° / 0.05° | grade A / B: systematic error of the direction-mean curve, **relative to the station reference, at station conditions** — one temperature, one orientation in the room, no load, no neighbouring modules | gate verified in simulation (§7.2) |
| ≈ 0.025–0.03° | the same, absolute, with the reference chain of §7.7 | estimate (station review) |
| ± hysteresis half-difference | recorded per unit; the reading lies within this of the mean curve, whatever the direction | measured per unit at the station |
| **≈ 0.1–0.15°** isolated joint, **≈ 0.2–0.4°** clustered joints (J1/J2, J3/J4, J5–J7) | joint angle **in use**, static, averaged reading; uncalibrated: ≈ 0.7–2° | estimate (sensor-physics review); **to be replaced by the measurement of §9.6** |
| + ω × 1.8 ms | data age not described by the stream's timestamp (§8.5): 0.11° at 60°/s, 0.33° at 180°/s, unless the host time-aligns | arithmetic, unmeasured |
| 0.05° (1σ) | noise of one reading, and of the M5's one-reading zero (§9.5) | data sheet |

**Compensation improves the joint angle about five- to ten-fold. It does not make it a 0.02° sensor.**
After calibration the fitted residual is under 1 % of the error variance; the gate value stops mattering
to the system below ≈ 0.05° (system-budget review, S9). What remains is set by stray fields, hysteresis,
mechanical play, temperature, the zero, noise and data age — none of which the station sees, and all of
which §9.5–9.7 address without touching the M5.

---

## 8. Timing

### 8.1 Per-module timeline

Each module is triggered once per 1 ms cycle; it replies from its cached value, then reads the sensor.

| | module 1 | module 8 | module 16 |
|---|---|---|---|
| trigger arrives (end of frame) | ≈ 20 µs | ≈ 230 µs | ≈ 470 µs |
| reply on the wire | 20 µs | 20 µs | 20 µs |
| read step | ≈ 114 µs | ≈ 114 µs | ≈ 114 µs |
| downstream traffic during its read step | heavy | some | none |
| per-cycle slack | ≈ 870 µs | ≈ 870 µs | ≈ 870 µs |

The read step overlaps the busiest part of the cascade for modules 1–15; UART RX interrupts run during
the CS-low window (§8.4 item 4).

### 8.2 Reply path

Unchanged up to and including `send485()` for CMD=1 and CMD=2. All new per-frame work — gate timestamp,
`arm_seen`, factory-mode exit, CMD=3 dispatch — runs in **one** place after the existing dispatch, for
every received frame (§11.1). Target: **≤ 5 µs added per hop**, measured (§8.4). Per-hop cost adds up along
the cascade: 50 µs per module would give ≈ 500 + 16 × 50 ≈ 1300 µs and miss 1 kHz. The brief's 50 µs is a
ceiling, not an allowance.

### 8.3 Read step

| Step | Cost | Source |
|---|---|---|
| SSC STAT..AVAL + safety: one 16-bit write, four 16-bit reads | ≈ 48 µs | model: upstream's write + read ≈ 14 µs (v2 review's AVRxt cycle model), scaled per word |
| CRC-8, table, 8 bytes | 123 cycles ≈ 6 µs | *measured*, simavr |
| compensation, N_HARM = 6, worst case | 1099 cycles ≈ **55 µs** | *measured*, simavr |
| decode, bookkeeping | ≈ 5 µs | estimate |
| **total** | **≈ 114 µs** | |
| every 16th read: + housekeeping transaction, 48 clocks | + ≈ 33 µs | 48 clocks at the ≈ 0.6 µs/clock rate of the first row, plus CRC |

Compensation worst case by N_HARM, cycles: 0 → 156, 1 → 404, 2 → 543, 3 → 682, 4 → 821, 5 → 960,
6 → 1099 (all amplitudes negative, arguments in the third quadrant). The rounding to 8 LSB added 41 cycles.

Cycles were measured on an AVRe core (ATmega328P in simavr), which has no ATtiny1616 model; the object
code is identical for both targets. The ATtiny1616's AVRxt core differs in two ways that roughly cancel:
`push`/`call` are faster, and the 24 sine-table reads per call come from memory-mapped flash rather than
SRAM. Net estimate ≈ −7 cycles. Bench confirmation is §8.4 item 5.

### 8.4 Bench measurements (deliverable 6)

1. Reply latency, trigger stop bit → reply start bit, upstream vs. calibrated build.
2. Full cascade, M5 trigger → last bit of ID 16; expected ≈ 500 µs.
3. Refresh rate over ≥ 60 s, counting dropped and late cascades.
4. CS-low window of the 80-clock read with RX traffic present; error counters over a long run.
5. Compensation and read-step time on the ATtiny1616 (GPIO toggle).
6. **Module reset → first CMD=2 received**, under the worst supply sequencing the arm can produce, to
   confirm `T_ARM_WAIT` = 3 s has ≥ 2× margin.
7. Module start-up time to first answered frame (§6.2), expected ≈ 9 ms, against upstream.
8. CMD=3 reply latency, and `COMMIT_CAL` / `SET_ID` duration against `T_PROG_MAX` (§4.3 r9).
9. Independence of readings 200 µs apart: scatter of repeated K = 1024 averages at one position against
   0.05°/√1024 ≈ 0.0016°. If they are correlated, `SAMPLE_SPACING` is raised.
10. **Data age** (§8.5): sensor update → reply on the wire → M5 parse → host, with the M5's tick rate and
    loop jitter; one logic-analyser session plus a host timestamp.
11. **Float32 accumulation on a real M5** (§7.1): a calibrated module clamped ≥ 128° from its zero with the
    sensor angle below 64°; the 10 s mean of the host angle logged for one hour must not move.

### 8.5 Data age

The angle the host receives is older than the frame's `timestamp` says (system-budget review, S6;
arithmetic on the unmeasured cascade model of §8.1):

| Contribution | Size |
|---|---|
| reply from cache, then read (§8.1) | ≈ 0.98 ms |
| replies wait in the M5's UART buffer: the M5 stamps `micros()`, parses the replies to the **previous** trigger, then sends the next (`M5/src/main.cpp:139-147`) | 0.46 ms (module 16) – 0.91 ms (module 1) |
| sensor filter delay and register-update phase (§2.7) | ≈ 0.1–0.25 ms |
| **age relative to `timestamp`** | **≈ 1.6 ms (module 16) – 2.0 ms (module 1), mean 1.8 ms** |

Sampling skew between modules is 30 µs per hop: 180 µs within one arm. At angular speed ω the error is
ω × age: 0.018° at 10°/s, 0.11° at 60°/s, 0.33° at 180°/s; it equals 0.02° at 11°/s. It is the same before
and after calibration, and it is a deterministic delay, not noise: with AUTOCAL and PREDICT off (§2.4) a
host that knows the model can remove it (§9.5). The numbers are replaced by §8.4 item 10 when measured.

---

## 9. Consequences for the M5 workflow

The M5's code needs no change and `ENCODER_CONFIG` needs no edit. Its **data and procedures** do.

### 9.1 Re-zero after installing calibrated modules

Compensation changes each module's reported angle by up to several degrees, so every stored
`jig_angle_offsets` value (NVS namespace `ker-cal`, `M5/src/main.cpp:245-247`, reloaded at `:367-369`)
becomes wrong. **Zeroing must be redone** whenever a module is installed or recalibrated. A channel near a
mechanical limit may also flip across the ±360° correction (`:162-168`) until re-zeroed.

### 9.2 The M5 cannot see calibration or sensor state

CMD=1/2 carry no status and `_valid[]` is never cleared (§1.5). Mixed calibrated/uncalibrated chains,
invalid pages, suspended compensation and stale angles are all invisible to the M5; they are visible only
through CMD=3, off-arm. The station records per-module calibration state. What a host can still detect
from the stream alone is in §9.5; how accuracy is verified and kept is in §9.6–9.7.

### 9.3 Diagnostics on an assembled arm

CMD=3 needs the M5 off the bus; STANDBY is not enough (§1.3). The M5 must be powered down or its RS-485
connector unplugged, with the modules still powered. RAM diagnostics do not survive a module power cycle.
Whether module power can be kept with the M5 disconnected is O4.

### 9.4 Never run CMD=3 tools on a bus with an M5

A stray request frame during zeroing permanently corrupts a jig offset (§1.6). Hard operating rule; C4.

### 9.5 Host-side measures (recommended; no M5 change)

After calibration these terms dominate the joint angle (§7.8), and each has a host-side remedy that uses
only what the stream already carries — float32 degrees, `timestamp`, `seq`:

| Measure | What it removes |
|---|---|
| **Zero trim.** Right after zeroing, arm still in the jig, average each `angles[i]` for ≥ 1 s; its expected value is exactly `mech_joint_offset[i]`; store and subtract the difference | the M5 zeroes on **one** reading (`M5/src/main.cpp:238-241`): 0.05° (1σ) frozen into every joint — the worst of 14 joints is off by ≈ 0.10° |
| **Frozen-channel detector.** A channel bit-identical for > 50 frames is dead: a live sensor's noise dithers the value. Also check `seq` for gaps | a dead module, a broken cascade, a held (`ANGLE_STALE`) value, a module sending 0 — all of which the M5 reports as valid, because `_valid[]` is never cleared (§1.5) |
| **Time alignment** with the data-age model of §8.5 | 0.11° at 60°/s, 0.33° at 180°/s |
| **Low-pass filter**, e.g. 25 Hz second order (≈ 9 ms group delay, to be accounted for like the data age) | per-reading noise 0.05° → ≈ 0.011°; nothing between sensor and host filters it |
| **Outlier rejection**, 3-sample median or rate limit | a corrupt frame moving a sample by < 30° passes the M5's jump detector (§1.6) |

They are outside this fork's deliverables; the brief's PC library is the CMD=3 tool. They are listed
because without them the calibration's gain is not visible at the host.

### 9.6 Verification on the assembled arm

The station verifies the fit. Nothing verifies the joint angle unless it is measured on the arm:

1. **Multi-pose check**, once per design on ≥ 2 arms, then on samples: a second and third jig pose, or a
   fixture that sets a known angle difference on each joint, approached from both directions, read through
   the normal CMD=2 stream with the M5 unmodified. Reported per joint: reading minus known difference.
   **This number, not 0.02°, is the product's joint-angle accuracy.**
2. **Cross-talk check**: clamp joint A, sweep neighbour B through its range, log A. Expected up to
   0.1–0.3° on J1/J2, J3/J4 and J5–J7 (§2.8).
3. **Return-to-jig check** at the start and end of a session: with the arm back in the jig, the 1 s mean of
   each joint must equal `mech_joint_offset` plus the zero trim, within the jig's repeatability. It
   catches drift, a slipped magnet, a forgotten re-zero and a persistent suspended compensation.

### 9.7 Records, service and re-calibration

- **Station database, per `SERNUM` and calibration**: the 16 page words; grade and validation statistic;
  hysteresis half-difference; fitted H1…H6 before rounding; per-reading σ (from `GET_SAMPLE` Σd²);
  `GET_ENV` temperature and VDD; `GET_DMAG`; firmware version; station ID and commissioning revision
  (§7.7); mechanical revision (magnet size and lot, pocket depth). Exported with each arm, so that a service site
  does not depend on the factory's database.
- **Arm assembly and every service visit**: with the M5 off the bus (§9.3, O4), read `GET_SERNUM`,
  `GET_HEALTH`, `GET_CAL_STATUS`, `GET_CFG_VERIFY`, `GET_ERRCNT`, `GET_ENV` and the 16 `GET_RUN_WORD`s of
  every module. Confirm that the page is valid and not an identity page (`GET_CAL_STATUS`), and that its
  16 words equal those stored against that `SERNUM` in the database, whose record carries the grade, A
  or B. The M5 cannot tell.
- **Re-calibration is required** after any disassembly of the unit (broken paint mark, §7.2), a magnet or
  mechanical revision, a failed return-to-jig check that re-zeroing does not cure, and a firmware change
  to the compensation arithmetic.

---

## 10. Resources

*(v6.1 — the figures below are now measured on the built firmware. What v6 estimated is kept in the last
row, because it was wrong by nearly a factor of two and that is worth remembering.)*

Upstream baseline, *measured* with the project venv (PlatformIO 6.2.0, megaTinyCore 2.6.11, avr-gcc 7.3.0,
`-Os -flto`), `-DDEVICE_ID=3`: RAM 179 / 2048 B (8.7 %), flash 2578 / 16384 B (15.7 %). The fork's
figures are from a clean checkout; a dirty tree is a few bytes larger, because the build stamps a
different commit hash and sets the dirty flag of `GET_FW_VER`.

| | flash | RAM |
|---|---|---|
| upstream | 2578 B (15.7 %) | 179 B (8.7 %) |
| **this fork, `-DDEVICE_ID=31`** | **10237 B (62.5 %)** | **459 B (22.4 %)** |
| added | **+7659 B** | **+280 B** |
| free | **6147 B (37.5 %)** | **1589 B (77.6 %)** |
| *v6 estimated* | *≈ +4 KB, headroom "> 9 KB"* | *≈ +140 B* |

Where it goes — per translation unit, compiled without LTO so the parts can be told apart; the sum exceeds
the linked image because LTO then removes the overlap:

| Unit | code | tables | RAM |
|---|---|---|---|
| `ker_cmd3.cpp` — CMD=3 dispatch, factory mode, records, sampling | 4072 B | — | 221 B |
| `ker_sensor.cpp` — block transaction, config lock, housekeeping | 2070 B | 281 B (CRC-8 table 256 B) | 36 B |
| `ker_cal.c` — CRC-16, page validation, USERROW, ADC | 924 B | — | 1 B |
| `ker_comp.c` — compensation | 496 B | 260 B (sine table) | 0 B |
| `ker_health.c` | 58 B | — | 0 B |
| `main.cpp` | 836 B | — | 22 B |

The largest single item is the CMD=3 dispatch, which is bench-only code: if flash is ever needed, that is
where it is. `.data` is 8 B — both tables are `const` and stay in the memory-mapped flash of the tinyAVR
1-series, as §7.4 item 3 requires. The linked image contains no floating-point runtime routine at all
(*measured*, `avr-nm`). The earlier standalone figure stands: linking the compensation routine into an
ATtiny1616 program costs **662 bytes** in total (`flash_cost.c`).

---

## 11. Implementation plan and verification

### 11.1 Files

| File | Contents |
|---|---|
| `encoder/src/main.cpp` | **modified** — see below |
| `encoder/platformio.ini` | **modified** — `-DDEVICE_ID=31` |
| `encoder/src/ker_ssc.h` | SSC bit-bang primitives, **moved** from `main.cpp` unchanged, `static inline` |
| `encoder/src/ker_sensor.{h,cpp}` | block read, outcome evaluation, config lock and retry, CRC-8 |
| `encoder/src/ker_comp.{h,c}` | compensation — plain C, also built for host and AVR tests |
| `encoder/src/ker_cal.{h,c}` | page validation, CRC-16, USERROW read/program, VDD check — plain C |
| `encoder/src/ker_cmd3.{h,cpp}` | gates, `arm_seen`, CMD=3 dispatch, factory mode, staging, records |
| `encoder/src/ker_health.{h,c}` | flags, counters |
| `encoder/tools/kercal/` | Python library and CLI (deliverable 4); its fit and grading are `station_fit.py`'s, its station commissioning is `ref_selfcal.py`'s (§7.7) |
| `encoder/test/` | host and AVR tests (deliverable 5) |

C headers carry `extern "C"` guards.

**`main.cpp` changes.** The SSC primitives move to `ker_ssc.h` unchanged (≈ 60 lines), because the safety
word must be clocked inside the existing CS-low window and the config lock needs the same primitives.
What remains: includes; the `DEVICE_ID` fallback 1 → 31; `device_id = ker_init(DEVICE_ID);` in `setup()`
(which also performs the start-up of §6.2; `device_id` stays file-static); the angle update in the read
block replaced by one call; and **one** call `ker_on_frame(r_id, r_cmd, r_data)` after the existing
`if/else` dispatch, reached for **every** received frame — including CMD=2 or CMD=3 frames carrying the
module's own ID, which the upstream addressed branch otherwise ignores (`encoder/src/main.cpp:323-333`).
About 20 changed lines plus the move. An upstream change to the SSC primitives will conflict.

*(v6.1, as built.)* The read block needed **one more term in its condition**, not only the replaced body:

```c
if (do_ssc_read || ker_read_due() || (millis() - last_ssc_time >= SSC_INTERVAL_MS)) {
  latest_angle_21bit = ker_read_angle();
  ...
```

`ker_read_due()` is how the averaged-sampling engine of §4.10 paces its own readings 200 µs apart without
blocking `loop()`; it is false whenever no sample is running, so nothing else changes.

**`ker_init` takes the ID by address**, `ker_init(&device_id, DEVICE_ID)`, not by return value as written
above. `main.cpp` reads its own `device_id` on every frame, both to decide what to answer and to compute
`prev_id`, while a successful `COMMIT_CAL` or `SET_ID` changes the module's ID **without a reset** (§4.9).
With the returned form the two copies diverge and the module answers the cascade at its old ID and CMD=3
at its new one until the next power cycle. This was a defect in the spec, found while building. Two further points
of fact: `CMD_READ_AVAL_FAST` and `tleReadAvalRawFast()` were **removed** rather than left dead, because
§6.1's block transaction replaces them and a dead single-register read would mislead; `crc8_0x07()` and
`signExtend15()` are left in place, as §1.8 says.

### 11.2 Verification requirements

1. **Host unit tests** of `ker_comp.c` and `ker_cal.c` against double-precision and independent Python
   references, including the constructed worst cases of §7.5 and the page-validation cases of item 5.
2. **AVR differential test.** The same sources built for an AVR core and run in simavr; outputs over all
   32768 codes hashed per coefficient set and compared with the host build, bit for bit. The sets must
   cover **every `N_HARM` from 0 to 6**, and include sets whose output wraps across the seam in **both**
   directions — below 0 and above 2²¹ − 1. The reference sets do: 10 wrap below, 9 above, 2 do not
   (`seam_check.c`).
3. **Negative controls.** Two mutants, each invisible to host tests, must fail the AVR differential test:
   A — `(c->amp[k] * s)` without its `int32_t` cast; B — the uncalibrated path computing
   `(uint32_t)(raw15 << 6)`.
4. **Station procedure** end to end through `ker_compensate()`, with mounting offsets covering the full
   circle, and its **operating characteristic** under 0.05° noise and a hysteresis loop (`station_sim.py`):
   no part above `R_MAX` graded A, none above `R_MAX_B` shipped.
5. Page validation with virgin, truncated, bit-flipped, wrong-version and out-of-range pages, and the
   `SET_ID` cases of §4.9.
6. Bench measurements (§8.4) and the compatibility checklist (deliverable 7).
7. **M5 accumulation test.** A float32 model of `RSNexus.cpp:85` and `AngleProcessor.h:57-72`, fed with the
   outputs of `ker_compensate()` under sensor noise over a grid of sensor angle × distance from the zero,
   stationary and moving, with and without `_invert`. The calibrated output must show **exactly zero**
   accumulation error; the uncalibrated mapping **no growth, and ≤ 1 × 10⁻⁴°**; a suspension episode
   (§6.2) ≤ 1 × 10⁻⁴°. **Negative control, mutant C** — the routine rounding to 1 LSB as in spec v5 — must
   drift in the sensitive cells (`author_s3_check.py`: 0.004–0.013° per hour;
   `../v6-verification-scripts/m5_float32_transitions.py`: 81 cells, motion, `_invert`, transitions, and
   steps of 1, 2 and 4 LSB, all of which drift).

Items 2–4 and 7 already pass for the reference implementation, re-run in v6 with the rounding to 8 LSB:
21 of 21 sets identical between host and AVR; mutant A differs on 20 of 21 on AVR, mutant B on 1 of 21
(the N = 0 set), both identical to the correct build on the host; the station procedure holds at every
offset tested; the accumulation error is zero. `regen_results.sh` regenerates them; the v5 results are
kept in `results-v5/`.

---

## 12. Decisions and open questions

### 12.1 Decisions

| # | Decision | Since |
|---|---|---|
| D1 | CMD=3 is bench-only: replies at ID 0 (C1), read gate 100 ms (C2), host discipline (C4). | v2 |
| D1a | Writes gated by an `arm_seen` latch plus 3 s since reset (C3); cleared only by power cycle. | v3 |
| D2 | Measured-domain fit, one pass — chosen for cost (§7.6). | v2 |
| D3 | Shared hex built with `-DDEVICE_ID=31`; provisionable IDs 1–30. | v2/v3 |
| D4 | Six harmonic slots, `N_HARM` 0–6; no stored constant term. | v3 |
| D5 | Sensor configuration per §2.4; re-applied after reset; compensation suspended while unlocked. | v2/v4 |
| D6 | Chain of 16 modules, IDs 1–16. | v2 |
| D7 | Temperature from `FSYNC.TEMPR`, sign-extended, converted on the host. | v2 |
| D8 | Unlock keyed to `SERNUM_DIGEST`. | v3 |
| D9 | USERROW layout version 1, §5.1. | v3 |
| D10 | Calibrated base `raw15 << 6`; uncalibrated stays upstream bit-exact. | v3 |
| D11 | Per-read block transaction STAT..AVAL with one safety word. | v3 |
| D12 | SUB 5 / ARG 16; `T_IDLE` 100 ms; `T_ARM_WAIT` 3 s; factory timeout 5 s; unlock window 1 s; reply ≤ 1 ms, commit ≤ 50 ms. | v2–v4 |
| D13 | Station fit §7.2: circular-mean offset removal, constant column fitted and discarded. (Its v4 acceptance criteria are superseded by D20.) | v4 |
| D14 | One module on the station bus during provisioning and calibration (§3.4). | **v4** |
| D15 | `SET_ID` writes an identity page only over a virgin page. | v4 |
| D16 | FIR_MD locked at 2, PREDICT and AUTOCAL off. **Not** upstream's configuration — the E1000 part powers up with FIR_MD 1, prediction and autocalibration on, and upstream writes nothing (§2.4). Re-confirmed by the user on 2026-09-20 with that corrected. | v5, **v6** |
| D17 | On-module averaging: `SAMPLE_START` / `GET_SAMPLE` (§4.10). | **v5** |
| D18 | Persistent faults: hold for 20 consecutive failures, then pass CRC-valid readings through, flagged (§6.2). | **v5** |
| D19 | `VDD_MIN_PROG` = 4.5 V, from the 20 MHz speed grade. | **v5** |
| D20 | Station acceptance: out-of-sample, averaged, on the committed output, half-range statistic; minimums of §7.2. | **v5** |
| D21 | The SUB space is now fully allocated; any further subcommand needs a new protocol version. | v5 |
| D22 | Compensated output rounded to a multiple of 8 LSB, so that the M5's float32 accumulation is exact (§7.1). | **v6** |
| D23 | The unit under calibration is the fully assembled, sealed encoder unit with its own magnet; disassembly voids the calibration (§7.2). | **v6** |
| D24 | Two approach directions; pooled fit of the mean curve; hysteresis half-difference recorded and limited (§7.2). | **v6** |
| D25 | Graded acceptance: A ≤ 0.02°, B ≤ 0.05°, otherwise rework. Rejected units are not shipped with an identity page. Grade in the station database, not on the module (§7.2). Supersedes the accept/reject part of D20. | **v6** |
| D26 | Accuracy is claimed as in §7.8: 0.02° is a station gate relative to the station reference; the in-use figure is the one measured on the assembled arm (§9.6). | **v6** |
| D27 | Station reference chain per §7.7: two encoder-grade couplings, stage-side and horn-side remounting out and back, mountings at 22.5° and 11.25°, stationary-poll criterion, incoming test, check standard. | **v6** |
| D28 | Host-side measures, arm-level verification and records (§9.5–9.7) are recommended practice; they need no M5 change and are outside the fork's deliverables. | **v6** |

### 12.2 Open

**O1 — Measured behaviour of real units.** Raw error curves of ≥ 10 assembled units (H1…H8): sets the
achievable accuracy (§7.6) and the centring limit (§7.2 step 9). The data sheet bounds only the die
(§2.7); with an Ø3 mm magnet 2–3° raw is plausible (§2.8). Plus the characterisation the 2026-09-20 reviews
ask for, in this order: clockwise against counter-clockwise curve (sets `HYST_MAX`); validation repeated
with unit and fixture yawed 180° (ambient-field sensitivity: the H1 change is 2 × B_stray / B₀); cross-talk
between neighbouring joints on an assembled arm; 1–5 N on the horn in four directions; warm-up curve and
validation at ≈ 15 °C and ≈ 40 °C; VDD sweep 4.5–5.5 V; jig repeatability.

**O2 — Datasheet and bench checks.** *(v6.1, raised by the firmware review of 2026-09-21 and now the
**first** item to check on a board.)* **Does `STAT.SFUSE` clear at run time once `CRCPAR` is rewritten, or
does it latch until the sensor is reset?** If it latches, the configuration lock can never set bit 3 of
`GET_CFG_VERIFY`, so `SENSOR_CFG_FAIL` sticks and **compensation is permanently suspended on every
module** — every part silently shipping the uncalibrated mapping, with `GET_CFG_VERIFY` reading `0x0017`
as the only sign. `SFUSE` is also inside `STAT_FAULT`, so every angle read would fail its status check too
and the persistent-fault rule would pass readings through degraded after 20 ms. Nothing downstream would
notice. Also: CRCPAR width (§2.5); SRST/SWD positions and clear-on-read of every
`STAT_FAULT` bit (§2.3); USERROW on locked devices (§5.5); USERROW programming time and whether it stalls
the CPU (§4.3 r9). `t_pon` is now taken from the datasheet (§2.7). **Added in v6:** the chip marking on
the boards (E1000, as the BOM says?), and the data sheet revision differences of §2.7 (1.6° against
1.3°/1.9°; angle delay 80–95 µs against 150–165 µs at FIR_MD 2).

**O3 — Calibration reference.** *Decided (2026-09-19/20):* the reference encoder, the chain and its
commissioning are in §7.7 and `station-reference-encoder.md`. Still open: the seller's confirmation of the
± 50″ rating, the technology (optical or magnetic) and the shaft type; the Modbus register map and
latching; the couplings actually bought and their rated transfer error; the commissioning results
(reproducibility, check mounting); whether a check standard and one independent comparison are bought.

**O4 — Can module power be kept with the M5 disconnected?** If not, on-arm diagnostics cannot read RAM
counters (§9.3).

*(The v5 items O5 and O6 were decided on 2026-09-19 as D18 and D19; the module's supply was inferred rather
than confirmed — if the boards are not 5 V, D19 must be revisited. The numbers are reused below.)*

**O5 — Should a persistent fault trip the M5's jump detector?** The only in-band fault channel an
unmodified M5 offers: a module that adds 180° to its output while a fault persists makes the M5 stop the
stream and name the channel (not on ch8/ch16, not with jump detection off). It would reverse D18 (pass a
degraded angle through). Raised by the system-budget review (S1); **not adopted**; D18 stands until the
user decides otherwise.

**O6 — Field at the sensor.** Estimated 23–32 mT, unmeasured (§2.8). A Hall-probe reading at the die
position with the bearing in place decides whether the gap should be reduced (≈ 2.0–2.2 mm) or the magnet
grade raised (N48–N52) to reach 40–50 mT. Hardware only; no effect on the protocol or the firmware.

---

## Appendix A — Evidence index

Paths relative to `encoder/docs/`. Python runs in `encoder/.venv` (`encoder/requirements-dev.txt`).
`evidence/v3-reference/README.md` gives the commands.

| Claim | Evidence |
|---|---|
| review trail | `reviews/2026-09-19-spec-v{2,3,4,5}-*.md`; accuracy reviews `reviews/2026-09-20-accuracy-review-{sensor-physics,station-metrology,system-budget,synthesis,response}.md` |
| reference compensation | `evidence/v3-reference/ref_comp.{c,h}`, `gen_sinq.py`, `sinq7*.inc` |
| §7.7 station commissioning | `ref_selfcal.py` → `results/ref_selfcal.txt` (run with `OPENBLAS_NUM_THREADS=1`) |
| §7.1 rounding to 8 LSB; §11.2 item 7 | `../v5-accuracy-review-scripts/system_float32_unwrap_drift.py` (review), `../v5-accuracy-review-scripts/author_s3_check.py` with `ref_comp_mutant_noround.c.txt` (mutant C) → `…/results/` |
| §2.8, §7.7, §7.8, §8.5 figures taken from the accuracy reviews | `evidence/v5-accuracy-review-scripts/physics_magnet_model.py` → `physics_magnet_model.txt` beside it; `{station_*,system_*}.py` → `…/results/` |
| v6 verification | `evidence/v6-verification-scripts/` → `…/results/` |
| §7.2 station procedure and its operating characteristic | `station_fit.py` → `results/station_fit.txt`; `station_sim.py`, `batch.c` → `results/station_oc_K1024{,_drift0.01,_N64}.txt`, `results/station_oc_K256.txt` |
| §7.5 realistic / constructed worst case / ceiling | `acc.c` → `results/accuracy_host.txt`; `../v3-review-scripts/construct.c` → `results/accuracy_constructed_worst.txt`; `../v3-review-scripts/worstterm.c` \| `ceiling.py` → `results/accuracy_analytic_ceiling.txt` |
| §11.2 AVR differential, mutants, seam coverage | `diff_main.c`, `ref_comp_mutant_{int16,uncal}.c.txt` → `results/{host,avr,host_mutant_*,avr_mutant_*}.txt`; `seam_check.c` → `results/diff_sets_seam_coverage.txt` |
| §7.1 uncalibrated = upstream | `uncalibrated_equals_upstream.c` → `results/uncalibrated_equals_upstream.txt` |
| §8.3 cycles | `cyc_main.c`, `../v3-review-scripts/cyc_worst.c` → `results/cycles_*`; `crc8_cycles.c` → `results/crc8_cycles_atmega328p_sim.txt` |
| §10 flash cost | `flash_cost.c` → `results/flash_cost_attiny1616.txt` |
| §7.3, §7.6 simulations | `base_mapping.py`, `harmonics_v3.py` → `results/` |
| earlier prototypes and review scripts | `evidence/v2-prototype/`, `evidence/v2-review-scripts/`, `evidence/v3-review-scripts/` |
| v5 results, before the rounding and the two-direction procedure | `evidence/v3-reference/results-v5/`; regenerate the current ones with `evidence/v3-reference/regen_results.sh` |
