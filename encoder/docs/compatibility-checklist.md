# Compatibility checklist

Deliverable 7. Every way this fork could break an unmodified M5, and how each one is closed.
A ✅ that is only reasoned is marked *desk*; a ✅ backed by a run is marked *measured*. The
hardware rows are open until the bench work is done.

The rule this list defends: **`M5/` is untouched, and an arm with upstream modules, forked
uncalibrated modules or forked calibrated modules behaves the same way at the M5.**

---

## A. The wire

| # | Claim | How it is closed | State |
|---|---|---|---|
| A1 | Frame format unchanged: `[1\|ID5\|CMD2][d0][d1][d2]`, 7 bits per data byte | `makePacket21()` and `receivePacket21()` are untouched in `main.cpp` | ✅ *desk* — diff |
| A2 | CMD=1 semantics unchanged | the addressed branch of `loop()` is untouched; `ker_on_frame()` runs after it and never replies to CMD=1 | ✅ *desk* — diff |
| A3 | CMD=2 cascade semantics unchanged | the `prev_id` branch is untouched | ✅ *desk* — diff |
| A4 | Baud rate, framing, and the RS-485 EN timing unchanged | `Serial.begin(2000000)` and `send485()` untouched | ✅ *desk* — diff |
| A5 | No new frame is ever sent that an M5 could parse as an angle | every CMD=3 reply is addressed to **ID 0**, which the M5 discards unconditionally (§1.5, C1) | ✅ *desk* — code review; needs A11 |
| A6 | A module never transmits unasked | the only transmit paths are the two upstream replies and CMD=3, which needs a request and an open gate | ✅ *desk* — code review |
| A7 | 21-bit payload range unchanged | `ker_compensate()` masks with `0x1FFFFF`; checked over all 32768 codes for 21 coefficient sets | ✅ *measured* — `test/run_tests.sh` §1, §3 |
| A8 | A CMD=3 request on a live bus cannot reach a module | not closable in the module: a host request with ID 1–16 is parsed by the M5 as an angle (T5). Closed only by host discipline C4, which `kercal` enforces and refuses to bypass | ⚠️ **residual** — §3.3 |
| A9 | Read gate keeps modules silent while a cascade runs | `T_IDLE` = 100 ms since the last CMD=1/CMD=2 frame of any ID, plus 100 ms since reset | ✅ *desk*; ⬜ bench item 8 |
| A10 | A bit error turning CMD=3 into CMD=2 fails safe | it latches `arm_seen` on every module that hears it; recovery is a power cycle (C3) | ✅ *desk* |
| A11 | The M5 really does discard ID 0 | `M5/src/RSNexus.cpp` — re-read against the shipping M5 before production | ⬜ **to re-confirm** |

## B. The angle an uncalibrated module reports

| # | Claim | How it is closed | State |
|---|---|---|---|
| B1 | With no valid USERROW page the output is upstream's mapping, bit for bit | `ker_compensate()` with `n = 0` compared with `(raw15<<6)\|(raw15>>9)` over all 32768 codes | ✅ *measured* — `test_comp`, check 1 |
| B2 | A corrupt or virgin page gives the uncalibrated path, not rubbish | page validation (§5.2) at boot; 70 checks over virgin, bit-flipped, wrong-magic, wrong-version, out-of-range-ID, bad-`N_HARM` and populated-unused-slot pages | ✅ *measured* — `test_cal` |
| B3 | An out-of-range `N_HARM` cannot index past the coefficients | `n > 6` is treated as uncalibrated inside `ker_compensate()` itself, not only by the validator | ✅ *measured* — `test_comp`, check 2 |
| B4 | A build default cannot answer the M5's trigger | default ID is 31; `prev_id` = 30, which no arm uses. Upstream's default was 1, which *would* have answered | ✅ *desk* — §5.4 |
| B5 | An ID outside 1–30 can never be stored | rejected by page validation at commit **and** at boot; ID 33 would transmit as wire ID 1 | ✅ *measured* — `test_cal` |

## C. The angle a calibrated module reports

| # | Claim | How it is closed | State |
|---|---|---|---|
| C1 | The correction never exceeds what the format allows | `int16` amplitude = ±5.625° per harmonic; the sum is masked to 21 bits and wraps correctly at the seam | ✅ *measured* — seam coverage, 10 sets wrap below 0 and 9 above 2²¹−1 |
| C2 | Fixed-point error inside the brief's 0.005° | constructed worst case N=6: **0.003186°**; analytic ceiling 0.003206°; realistic 0.000835° | ✅ *measured* — `test_comp` |
| C3 | AVR arithmetic equals host arithmetic | 21 coefficient sets × 32768 codes, hashed, identical | ✅ *measured* — `test/run_tests.sh` §3 |
| C4 | The M5's float32 integration does not drift | output is always a multiple of 8 LSB = 45 × 2⁻¹⁵ degrees, exact in float32 below 512°; simulated accumulation over 1 h is **exactly zero** | ✅ *measured* in simulation; ⬜ bench item 11 on a real M5 |
| C5 | Switching to the uncalibrated fallback cannot trip the M5's jump detector | the step is Σ\|Aₖ\|, at most a few degrees on any real part, against a 30° threshold — but the **format** permits 33.75° | ⚠️ **bounded by part quality, not by the design** — §6.2 |
| C6 | The station cannot ship a part it rejected | a rejected unit is never given an identity page; the grade lives in the station database | ✅ *desk* — §7.2 step 8 (D25); process, not firmware |

## D. Timing

| # | Claim | How it is closed | State |
|---|---|---|---|
| D1 | Added reply latency ≤ 50 µs (brief), target ≤ 5 µs | all new per-frame work runs after `send485()`; the reply path is upstream's | ⬜ **bench item 1** |
| D2 | The chain still holds 1 kHz with 16 modules | per-cycle slack ≈ 870 µs against a read step of ≈ 114 µs | ⬜ **bench items 2, 3** |
| D3 | No floating point in the real-time path | no `float` or `double` appears in any fork source, and the linked image contains no floating-point runtime routine at all (`avr-nm` on `firmware.elf`). `main.cpp` still includes `math.h`, unused, as upstream does | ✅ *measured* |
| D4 | The read step never overruns its slot | worst case is a configuration-lock retry in the housekeeping slot: ≈ 114 + 250 µs | ⬜ **bench item 5** |
| D5 | A module reset does not fault the M5 | ≈ 9 ms of silence; the M5 keeps streaming the last angles as valid (`_valid[]` is never cleared) | ⬜ **bench item 7** |
| D6 | Sampling cannot run while an arm is polling | any CMD=1 or CMD=2 frame aborts it, and it needs an open read gate to start | ✅ *desk* — §4.10 |

## E. Provisioning and safety

| # | Claim | How it is closed | State |
|---|---|---|---|
| E1 | A write cannot execute on a module in a running arm | `arm_seen` latches on the first CMD=2 frame and only a power cycle clears it (C3) | ✅ *desk*; ⬜ **bench item 6** for the 3 s margin |
| E2 | A write cannot reach the wrong module | unlock is keyed to `SERNUM_DIGEST`, and §3.4 puts exactly one module on the station bus | ✅ *desk* |
| E3 | A failed write leaves the module running its previous calibration | `commit_page()` only adopts after the read-back matches; on failure the staging buffer and factory mode survive so the host can retry | ✅ *measured* — `test_cal`, program-fail and verify-corrupt paths |
| E4 | A half-written page cannot look valid | the USERROW is a single 32-byte NVM page, written by one erase-write, and carries a CRC-16 | ✅ *desk*; ⬜ confirm the page size on silicon (O2) |
| E5 | Programming cannot run on a sagging supply | VDD measured against the 1.1 V reference before every commit; `VDD_MIN_PROG` = 4.5 V (D19) | ✅ *measured* on the host stub; ⬜ ADC accuracy on silicon (O2) |
| E6 | `kercal` cannot be pointed at an arm by accident | it listens ≥ 200 ms before its first transmission and refuses to start if anything is talking; any CMD=2 frame poisons the session permanently | ✅ *desk* — `link.py`; not yet exercised against real traffic |

## F. Build and repository

| # | Claim | How it is closed | State |
|---|---|---|---|
| F1 | `M5/` is byte-identical to upstream | `git diff HEAD -- M5/` is empty | ✅ *measured* |
| F2 | Fuses unchanged | `platformio.ini` fuse lines untouched; only `build_flags` and `extra_scripts` changed | ✅ *measured* — diff |
| F3 | Apache-2.0 headers kept, modifications noted | every new file carries the licence and a MODIFICATION NOTICE; `main.cpp`'s header is untouched | ✅ *desk* |
| F4 | The upstream build is still reproducible | `pio run` on upstream's `main.cpp` and `platformio.ini`: 2578 B flash, 179 B RAM | ✅ *measured* |
| F5 | Flash and RAM margin | 6147 B flash (37.5 %) and 1589 B RAM (77.6 %) free | ✅ *measured* — `CHANGELOG.md` |
| F6 | A module can be identified after the fact | `GET_FW_VER` carries the commit and a dirty flag, stamped by `tools/pio_version.py` | ✅ *desk* |

---

## What is not closed

Three things, stated plainly:

1. **No hardware has run this.** Every ⬜ above is a bench item, and the firmware's
   interaction with the real TLE5012B — command words, CRCPAR, `STAT` bits, USERROW timing —
   is as documented, not as observed.
2. **A6 and A8 together are the safety argument**, and A8 has a residual: nothing in the
   module can stop a host from putting a CMD=3 *request* with ID 1–16 on a live arm bus. The
   defence is procedural (C4) and is implemented in `kercal`, which is the only tool that
   should ever be used.
3. **C5 is bounded by the parts, not by the design.** The fallback step is small for any
   realistic module, but the format allows a step that would trip the M5's jump detector. The
   first ten measured units (O1) settle it.
