# Response to the spec v2 reviews

Reviews: `2026-09-19-spec-v2-protocol-review.md` (6 B / 23 M / 20 m) and
`2026-09-19-spec-v2-numerics-review.md` (3 B / 8 M / 6 m). Both: REJECT.
Resolved in `../protocol-spec.md` **v3**. § references below are to v3.

Status: **fixed** — changed in v3; **accepted** — finding correct, handled by documenting it;
**disputed** — finding checked and not upheld, with evidence; **open** — needs a decision (§12.2).

## Protocol review

### Blockers

| # | Finding | Status | Resolution |
|---|---|---|---|
| B1 | Idle gate opens during M5 power-up silence (`delay(500)`, `M5/src/main.cpp:431`) | fixed | Writes now need the `arm_seen` power-up latch + 3 s uptime (§3.2 C3). Reads stay behind the idle gate; their replies are at ID 0 and invisible to the M5. M5 silence modes documented (§1.4). |
| B2 | `SET_ID` on a virgin page burns `0xFFFF` magic with a valid CRC, reports ok | fixed | Invalid page → `SET_ID` builds and commits an identity page (§4.9). |
| B3 | No `device_id` range check; ID 33 → wire ID 1 and answers the M5 trigger | fixed | One validation function at boot and before commit; `DEVICE_ID` 1–30 (§5.2). |
| B4 | GET_DEVICE_ID / GET_CAL_STATUS / GET_CFG_VERIFY payloads undefined | fixed | §4.7. |
| B5 | Gate `any` undefined; `LOCK` could transmit mid-cascade | fixed | Gates R/W/F defined (§4.4); `LOCK` is R. |
| B6 | ID-31 default + ID-keyed unlock → all virgin modules share one unlock pair | fixed | Unlock keyed to `SERNUM_DIGEST` (§4.9); duplicate identical replies addressed in §3.3. |

### Major

| # | Finding | Status | Resolution |
|---|---|---|---|
| M1 | Gate trigger set ≠ factory-exit trigger set | fixed | Both are "any CMD=1 or CMD=2 frame, any ID" (§3.2, §4.9). |
| M2 | CMD=1 bench polling locks out CMD=3 | fixed | CMD=1 does not set `arm_seen`; the station reads angles through CMD=3 (`GET_ANGLE_RAW` idx 2/3), so it needs no CMD=1. |
| M3 | Read counter u16 saturates in 65 s | fixed | 32-bit, indices 6–7, wraps (§4.7). |
| M4 | TEMPR sign extension not stated | fixed | §2.6, with worked example. |
| M5 | Gate bookkeeping missing from reply-path budget | fixed | All new work placed after `send485()` or on non-matching frames (§8.2). |
| M6 | "Writes stop immediately" unhonourable; no response times | fixed | Factory exit rules and USERROW programming caveat stated (§4.9); programming time is O2. |
| M7 | Partial latch undetectable | fixed | Latch count + valid bits, host verifies all equal (§4.8). |
| M8 | Staging buffer lifecycle unspecified; `SET_ID` clobbers it | fixed | Lifecycle table; `SET_ID` NAKs STAGING_BUSY when dirty; reads reset the factory timer (§4.3 r7, §4.9). |
| M9 | `COMMIT_CAL` changing own ID leaves session undefined | fixed | Commit ends factory mode; new ID effective at once; reply returns it (§4.9). |
| M10 | Cost of ID-0 replies unacknowledged | fixed | Stated, including that identical replies from duplicates do not collide visibly (§3.3). |
| M11 | Stray-frame impact misstated; zeroing path uses unsubstituted `raw_deg` | fixed | §1.6, §9.4, host rule C4. |
| M12 | Calibration invalidates stored jig offsets | fixed | Re-zero requirement (§9.1). |
| M13 | Mixed calibrated/uncalibrated chains invisible | accepted | Documented (§9.2); unfixable without an M5 change. |
| M14 | RAM diagnostics unreachable; STANDBY does not silence the bus | accepted | §1.3, §9.3; module power separability is **open** (O4). |
| M15 | "~15 lines in main.cpp" not achievable | fixed | SSC primitives move to `ker_ssc.h`; honest sizing (§11.1). |
| M16 | Accuracy measured at 3 harmonics, claimed for 5 | fixed | Re-measured at 6 on the v3 implementation (§7.5). |
| M17 | §6.3 prose contradicts its own table | fixed | Six harmonics (§7.6). |
| M18 | Health bit classes contradict definitions | fixed | live/sticky per bit (§4.7). |
| M19 | GET_TRIM "5 registers" ambiguous | fixed | Whole registers, raw, listed (§4.6). |
| M20 | No per-SUB protection against bit errors | fixed | Tags/magics on every mode-changing SUB; STAGE_DATA covered by page CRC (§3.2 C6). |
| M21 | Broadcast NAK undefined → 16-way collision | fixed | Broadcasts never reply (§4.3 r2); addressed LATCH_SYNC → BAD_ADDRESSING. |
| M22 | "Magic makes accidental match impossible regardless" false | fixed | Claim rests on the SUB field only (§4.2). |
| M23 | Residual exposure closed by a host convention | accepted | Stated as a residual risk (§3.3). |

### Minor

| # | Status | Resolution |
|---|---|---|
| 1 "only transmit" not established | fixed | Checked all M5 sources: `SerialStream` is on `Serial`; RS-485 is `Serial2` (§1.3). |
| 2 no worst-case M5 silence analysis | fixed | §1.4; writes no longer depend on silence. |
| 3 field order differs storage vs protocol | fixed | `LAYOUT_VER` in [15:8] in both; `DEVICE_ID` in [7:0] in both. |
| 4 when CAL_VER_UNSUPPORTED is set | fixed | §5.3. |
| 5 ID_FROM_BUILD redundant | fixed | Removed; bit 6 reserved; source in GET_DEVICE_ID bit 8. |
| 6 `id` undefined in UNLOCK_2; armed state unbounded | fixed | SERNUM_DIGEST; 1 s window, next-frame rule (§4.9). |
| 7 no reason code for sequence violation | fixed | SEQUENCE 0x0A. |
| 8 SUB 0x00 as request | fixed | NAK UNSUPPORTED. |
| 9 non-zero ARG on no-ARG SUBs | fixed | Ignored (§4.3 r5). |
| 10 build id encoding | fixed | Low 16 bits of git commit. |
| 11 RESET post-conditions | fixed | §4.9. |
| 12 STAT_ERR names two things | fixed | Safety bits prefixed `S_`; health bit renamed SENSOR_STAT_ERR. |
| 13 STAT read not in timing; cached vs live unclear | fixed | Block read every read (§6.1); caching rules (§6.3); timing (§8.3). |
| 14 15 µs compensation optimistic | fixed | Measured 52 µs (§8.3). |
| 15 sine table needs PROGMEM | **disputed** | On ATtiny1616 (avrxmega3) `const` data stays in memory-mapped flash: measured `.data` = 0, table at `0x82FE`. Stated in §7.4. |
| 16 USERROW erased on locked devices | accepted | §5.5; datasheet check in O2. |
| 17 power loss mid-burn | accepted | §5.5; station reads back after every commit. |
| 18 CMD=3 must not reset the gate timer | fixed | §3.2 C2. |
| 19 missing decision rows | fixed | §12.1 D8–D12. |
| 20 framing rule weaker than code | fixed | §1.1. |

## Numerics review

| # | Finding | Status | Resolution |
|---|---|---|---|
| B1 | Compensation ≈ 89 µs, not 15 µs | fixed | Rewritten in 16 bits; measured 1047 cycles ≈ 52 µs at N=6 on an AVR core (§8.3). |
| B2 | 3.4× margin gone at N=5 (0.004864°) | fixed | Dominant term (`arg >> 5`) eliminated; table doubled and rounded; adversarial worst at N=6 **0.002341°**, 2.1× (§7.5). |
| B3 | "Six buys nothing" refuted by own table | fixed | Six harmonics adopted (D4). |
| M1 | 2.4–2.7× is a four-case artifact | fixed | Figure withdrawn. |
| M2 | Approach A a strawman; iterated true-domain far better | fixed, partly disputed | Re-run with 15-bit quantisation and higher intrinsic harmonics: iterating gains 13% at 3× cost (§7.6). The 65–735× figure holds only without quantisation. D2 kept, on cost. |
| M3 | Simulation assumed 3-harmonic intrinsic error | fixed | `harmonics_v3.py` adds intrinsic H4–H6 (§7.6). |
| M4 | Figures unquantised best cases | fixed | Quantised throughout (§7.6). |
| M5 | Budget quoted H1–3 range for a design that rejects it | fixed | §7.5 quotes the six-harmonic design. |
| M6 | Formula sign (+) vs prototype (−) | fixed | Correction is added, in spec, reference code and double reference; station procedure fixed (§7.2). |
| M7 | "Idle window" conflates two periods | fixed | Per-module timeline (§8.1). |
| M8 | No `device_id` check at boot | fixed | §5.2 (same as protocol B3). |
| m1 | gain 64.0000305 wrong | fixed | 64 + 1/512 (§1.7). |
| m2 | safety word +8 µs → 11.2 µs | superseded | Block read, §8.3. |
| m3 | cascade omits M5 trigger frame | fixed | ≈ 500 µs (§8.4). |
| m4 | `sinq[65]` read past the table | fixed | Padded table (§7.4). |
| m5 | 32768-code sweep vs full 2²¹ domain | resolved by design | v3 compensation takes `raw15`; its whole input domain is the 32768 codes swept. |
| m6 | PlatformIO version mismatch | fixed | Project venv pinned to 6.2.0 (`requirements-dev.txt`). |

## Found during revision, not raised by either review

1. **16-bit `int` overflow in the first v3 draft.** `(uint16_t)(a1 - a0) * frac` with a 64-segment
   table reaches 205 020 and wraps on AVR, while passing every host test. Caught by the new AVR
   differential test; now prevented by `_Static_assert` (§7.4).
2. **Bit-replication ramp.** Upstream's base mapping doubles the calibrated residual (§7.3); fixed by
   D10.
3. **Sensor reset loses the volatile configuration.** Now detected via `S_RST` / `STAT.SRST` and
   re-applied (§6.2).
4. **Torn multi-word reads.** `GET_ANGLE_*` read in two requests could combine two samples; snapshot
   rule added (§4.3 r6).
5. **Persistent-fault freeze.** Holding the last value indefinitely is invisible to the M5 — open, O5.
