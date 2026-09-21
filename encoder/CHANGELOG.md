# Calibrated KER encoder firmware — changelog

Fork of the OpenArm KER encoder firmware. Everything here is under `encoder/`;
`M5/` is untouched and still builds from upstream.

The design is `docs/protocol-spec.md` (**v6**, 2026-09-20). This file records what was
built, what it costs, and where the implementation differs from what the spec says.

---

## 1.0.0 — 2026-09-21

First implementation of spec v6. Protocol version stays **5** (`GET_PROTO_VER`); spec v6
changed the station procedure and the output rounding, not the wire format.

### What a module does that it did not before

| | upstream | this fork, uncalibrated | this fork, calibrated |
|---|---|---|---|
| CMD=1 / CMD=2 reply | cached angle | **identical, bit for bit** | compensated angle |
| angle mapping | `(raw15<<6) \| (raw15>>9)` | **the same** | `(raw15<<6) + round₈(Σ Aₖ sin(kθ+φₖ))` |
| device ID | build flag | USERROW page, build default 31 | USERROW page |
| sensor read | AVAL only | STAT + ACSTAT + AVAL + safety word | as uncalibrated |
| sensor config | whatever it powers up with | AUTOCAL off, PREDICT off, FIR_MD 2, read back | as uncalibrated |
| CMD=3 | ignored | full sub-protocol, bench only | as uncalibrated |

A module with no valid page behaves exactly as upstream on CMD=1 and CMD=2, verified
over all 32768 sensor codes (`test/run_tests.sh`, section 1).

### Files

| File | |
|---|---|
| `src/main.cpp` | **modified**, see below |
| `platformio.ini` | **modified**: `-DDEVICE_ID=31`, `extra_scripts` for the build stamp |
| `src/ker_ssc.h` | SSC pins, fast-I/O wrappers and bit-bang primitives, **moved unchanged** from `main.cpp` |
| `src/ker_comp.{h,c}` | compensation; plain C, also built for the host and AVR tests |
| `src/ker_cal.{h,c}` | page CRC-16 and validation, USERROW read/program, supply measurement |
| `src/ker_sensor.{h,cpp}` | block transaction, outcome evaluation, configuration lock, housekeeping |
| `src/ker_cmd3.{h,cpp}` | gates, `arm_seen`, CMD=3 dispatch, factory mode, staging, records, sampling |
| `src/ker_health.{h,c}` | health bits and counters |
| `src/ker_version.h` | what `GET_FW_VER` reports |
| `src/ker_sinq7.inc`, `src/ker_crc8.inc` | generated tables |
| `tools/gen_sinq.py`, `tools/gen_crc8.py` | their generators |
| `tools/pio_version.py` | stamps the commit into the image |
| `tools/kercal/` | host library and CLI (deliverable 4) |
| `test/` | host, AVR and cross-language tests (deliverable 5) |

### `main.cpp`: what actually changed

Four functional edits plus the move of the SSC primitives:

1. two includes;
2. the `DEVICE_ID` fallback `1` → `31` — 1 is the ID that would answer the M5's own trigger;
3. `device_id = ker_init(DEVICE_ID);` at the end of `setup()`;
4. the read block's body replaced by `latest_angle_21bit = ker_read_angle();`, and
   `ker_read_due()` added to its condition;
5. `ker_on_frame(r_id, r_cmd, r_data);` after the existing dispatch, reached for **every**
   received frame.

`crc8_0x07()` and `signExtend15()` are left in place although unused, as upstream has them.
`CMD_READ_AVAL_FAST` and `tleReadAvalRawFast()` were removed: the block transaction of
§6.1 replaces them, and leaving a dead single-register read would be misleading.

**Deviation from spec §11.1.** The spec describes the read block as "the angle update
replaced by one call". It needed one more term in the condition: `ker_read_due()`, so the
averaged-sampling engine of §4.10 can pace its own readings 200 µs apart without blocking
`loop()`. One expression, no behaviour change when no sample is running.

### Other deviations from the spec, and open points

- **§10's resource estimate was low.** It estimated ≈ 4 KB of flash and ≈ 140 B of RAM
  added, and headroom "> 9 KB". Measured: **+7659 B flash, +280 B RAM**, headroom
  **6147 B flash / 1589 B RAM**. The table below says where it went. The margin is still
  a third of the part, but §10 should be corrected rather than believed.
- **The configuration lock is ≈ 576 SSC clocks, not ≈ 400** (§6.2): one 10-word read of
  MOD_1…TCO_Y, three single-register writes, one read-back of the same ten words, one STAT
  read. At the ≈ 0.44 µs/clock implied by the v2 cycle model that is ≈ 0.25 ms, so the
  "≈ 0.3 ms" the spec budgets still holds; the clock count does not.
- **`S_RST` has no counter of its own.** §4.7 gives counters for CRC, status and
  no-response only, and §6.2 makes `S_RST = 0` a fourth outcome. It is counted as a status
  fault and sets `SENSOR_STAT_ERR`. Nothing in the spec assigns it; this is a choice.
- **VDD is measured in two steps during housekeeping.** A blocking measurement is
  ≈ 0.15 ms, which does not fit the read step of §8.3. `ker_vdd_start()` kicks a conversion
  that runs while the SSC bits are clocked and the next housekeeping transaction collects
  it, so the value is at most one housekeeping slot older than D_MAG and FSYNC — inside
  the "≤ 32 reads" §6.3 already allows. `COMMIT_CAL` and start-up still measure blocking.
- **`ker_init()` takes the ID by address, not by return value.** §11.1 specifies
  `device_id = ker_init(DEVICE_ID);`, which is a latent bug: `main.cpp` reads its own
  `device_id` on every frame to decide what to answer and to compute `prev_id`, while a
  successful `COMMIT_CAL` or `SET_ID` changes the module's ID **without a reset** (§4.9). The
  returned form leaves the two copies to diverge, and the module would answer the cascade at
  its old ID and CMD=3 at its new one until the next power cycle. `ker_init(&device_id, …)`
  keeps them in step; `main.cpp` is no larger for it.
- **ADC0 is reconfigured on every supply measurement, not only when disabled.** megaTinyCore's
  `init_ADC0()` enables ADC0 for `analogRead()` before `setup()` runs
  (`cores/megatinycore/wiring.c:550`), so "configure it only if it is disabled" would have left
  the multiplexer and reference on the core's settings and measured the wrong thing. Nothing
  else uses the ADC, so the fork takes it over outright.
- **Independent review, 2026-09-21** (`docs/reviews/2026-09-21-firmware-review.md`):
  REQUEST CHANGES — 0 blocker, 3 major, 7 minor. All three majors were conformance defects in
  `ker_cmd3.cpp` and are fixed here: a record index truncated to 8 bits (ARG `0x0100` read as
  index 0, silently re-capturing the record under a host that cannot see the substitution);
  the unlock window surviving a NAK'd `SUB 0x00` or addressed `LATCH_SYNC`, against §4.9's
  "next request" rule; and `BAD_INDEX` returned where §4.3 rule 11 orders `SEQUENCE` first.
  Four minors were real and are fixed — the `GET_ANGLE_RAW` record mixing two transactions,
  `total` saturating where §4.7 says it wraps, the supply reading freezing exactly while the
  configuration lock is failing, and a broadcast restarting the factory-mode timer that §4.9
  keys to requests "to this module". Three stand as written, with reasons in the response file.
- **The first thing to check on a board is `STAT.SFUSE`.** If it latches until reset rather than
  clearing once `CRCPAR` is rewritten, the configuration lock can never pass, `SENSOR_CFG_FAIL`
  sticks, and **every module silently ships the uncalibrated mapping** while `GET_CFG_VERIFY`
  reads `0x0017`. Raised by the review; now the first item of §12.2 O2.
- **Unverified on hardware.** Nothing in this release has run on a board. The SSC command
  words, the CRCPAR width (§2.5), the `STAT` fault-bit behaviour (§2.3), the USERROW
  programming time and the reset behaviour are all as the datasheet and Infineon's driver
  describe them, and all are on the open list (§12.2 O2). Bench measurement is
  `docs/timing-measurements.md`.

### Resources — *measured*

PlatformIO 6.2.0, megaTinyCore 2.6.11, avr-gcc 7.3.0, `-Os -flto`, `-DDEVICE_ID=31`, from a clean
checkout. A build from a dirty tree is a few bytes larger: `tools/pio_version.py` stamps a different
commit hash and sets the dirty flag.

| | flash | RAM |
|---|---|---|
| upstream baseline | 2578 B (15.7 %) | 179 B (8.7 %) |
| **this fork** | **10237 B (62.5 %)** | **459 B (22.4 %)** |
| added | +7659 B | +280 B |
| **free** | **6147 B (37.5 %)** | **1589 B (77.6 %)** |

Where it goes (per translation unit, compiled without LTO so the parts can be told apart;
the sum is larger than the linked image because LTO then removes the overlap):

| Unit | code | tables | RAM |
|---|---|---|---|
| `ker_cmd3.cpp` — CMD=3 dispatch, factory mode, records, sampling | 4072 B | — | 221 B |
| `ker_sensor.cpp` — transaction, config lock, housekeeping | 2070 B | 281 B (CRC-8 table 256 B) | 36 B |
| `ker_cal.c` — CRC-16, validation, USERROW, ADC | 924 B | — | 1 B |
| `ker_comp.c` — compensation | 496 B | 260 B (sine table) | 0 B |
| `ker_health.c` | 58 B | — | 0 B |
| `main.cpp` | 836 B | — | 22 B |

The CMD=3 dispatch is the largest single item and is bench-only code; if flash is ever
needed, that is where it is. `.data` is 8 B: both tables are `const` and stay in the
memory-mapped flash of the tinyAVR 1-series, as §7.4 item 3 requires.

### Verification — *measured*, `test/run_tests.sh`

All of §11.2 that can run without hardware, against the shipping sources:

| | result |
|---|---|
| host unit tests, `ker_comp.c` | 18 checks, 0 failures |
| host unit tests, `ker_cal.c` | 70 checks, 0 failures |
| `src/ker_comp.c` identical to the reference §7.5 was measured on | yes |
| AVR differential, all 32768 codes × 21 coefficient sets | 21/21 identical to host |
| seam coverage of those sets | 10 wrap below 0, 9 above 2²¹−1 |
| negative control A (missing `int32_t` cast) | invisible on host, 20/21 differ on AVR |
| negative control B (uncalibrated `(uint32_t)(raw15 << 6)`) | invisible on host, 1/21 differs on AVR |
| constructed worst case, N=6 | 0.003186° — budget 0.005°, margin 1.57× |
| realistic coefficients | 0.000835° |
| station operating characteristic, 4000 parts | 0 graded A above 0.02°, 0 shipped above 0.05° |
| M5 float32 accumulation over 1 h | calibrated **exactly 0**; upstream 0; mutant C drifts 0.004–0.013°/h |
| `kercal` against the firmware's own C | 13 tests, including page validation over a corpus |
| firmware build | clean, no warnings with `-Wall -Wextra` |

Mutants are generated from `src/ker_comp.c` by the test script, so a negative control
cannot go stale against the code it is supposed to catch.

Not covered here, by construction: everything needing a board or a bus
(`docs/timing-measurements.md`, `docs/compatibility-checklist.md`).
