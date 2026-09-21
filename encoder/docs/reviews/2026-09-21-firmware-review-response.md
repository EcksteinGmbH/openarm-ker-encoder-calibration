# Response — firmware review of 2026-09-21

Review: `2026-09-21-firmware-review.md`. Verdict **REQUEST CHANGES**, 0 blocker, 3 major, 7 minor,
plus 2 spec defects and 3 bench items. Every finding was checked against the code and the spec
before acting; nothing was taken on the reviewer's word.

## Major — all three accepted and fixed

| # | Finding | What was wrong | Fix |
|---|---|---|---|
| M1 | record index truncated to 8 bits | `record_read((uint8_t)arg, …)` made `GET_ANGLE_RAW` with `ARG = 0x0100` read as index 0. §4.5 says BAD_INDEX covers an "index **or value** outside its range". Worse than a wrong reply: index 0 **re-captures** the record, so a host walking indices 0…4 could get fields from two different transactions, and replies echo SUB but not the index (rule 9), so it could not see it happen | `record_read()` takes `uint16_t` |
| M2 | unlock window survived two requests | `SUB 0x00` and addressed `LATCH_SYNC` were NAK'd with an early `return` that skipped the disarm. `UNLOCK_1 → 0x00 → 0x14 → UNLOCK_2` would have entered factory mode. It still needs the SERNUM digest, so not reachable by accident, but the "next request" rule is exactly what makes a mis-decoded frame (T6) fail safe | both NAKs now fall through to the single disarm |
| M3 | NAK precedence inverted for records | index range tested before sequence; rule 11 orders `SEQUENCE` first | order swapped; `idx != 0 && !*ok` is now the first test |

M3 was the only rule-11 violation in the file — the reviewer checked `SET_ID` and `UNLOCK_1/2`
and found them correct, which matches my own reading.

## Minor — four fixed

| # | Finding | Fix |
|---|---|---|
| m1 | `GET_ANGLE_RAW` mixed two transactions: `raw15` from the last **published** read, sequence and flags from the last **attempted** one, while §4.7 says the record is "captured together from one sensor transaction" | `ker_sensor_raw15_attempted()` added; the record is now one transaction, and field 4 bit 0 is what says whether it passed |
| m2 | `ker_cnt.total` saturated; §4.7 says 32-bit and **wraps** after 49 days | wraps |
| m3 | the supply reading stopped refreshing while `SENSOR_CFG_FAIL` was set — precisely when a station wants it | the ADC pair now runs before the configuration-lock retry |
| m4 | `S_RST` booked to the status counter without saying so in the code | comment added; it was already in `CHANGELOG.md` |

Plus one the reviewer raised as a spec ambiguity: §4.9 times factory mode out after 5 s "without an
accepted request **to this module**", while rule 7 counts `LATCH_SYNC` as accepted. A broadcast is
addressed to no one, so it no longer restarts the timer. §4.9 is the more specific sentence and the
safer reading.

## Minor — three stand, with reasons

- **m5, `config_lock()` overwrites `stat_last` for `GET_STAT`.** §4.6 defines `GET_STAT` as "STAT as
  received in the most recent transaction, whether or not it passed". The lock's own `STAT` read *is*
  the most recent transaction, and after a lock it is the more current answer — which is what a host
  reading `GET_CFG_VERIFY` and `GET_STAT` together wants. No change.
- **m6, the no-response test also requires the safety word uniform.** §6.2's row is "all words `0x0000`
  or all `0xFFFF`", and the transaction returns four words including the safety word. That is the
  literal reading. It makes no practical difference: a sensor that is absent or held in reset reads
  uniform on all four, and a mixed pattern is caught one row later by the CRC. No change.
- **m7, the gated counter counts a broadcast `LATCH_SYNC` with the wrong magic.** Counter 5 is
  "CMD=3 requests addressed to this module, **or `LATCH_SYNC` broadcasts**, dropped by the read gate".
  A broadcast carrying `SUB = 0x14` is a `LATCH_SYNC` broadcast whatever its ARG says, and a gate-closed
  module cannot tell the host anything either way. No change.

## Spec defects — both fixed in `protocol-spec.md`

- **S1** §5.4 still described `platformio.ini` as "currently `-DDEVICE_ID=3`" and the `main.cpp`
  fallback as "currently 1". Both are 31 now. Stale text that invites a reader to "fix" a
  non-problem. Rewritten, marked *(v6.1)*.
- **S2** §6.2's "≈ 9 ms" start-up is the healthy case; a sensor reporting `S_RST` re-runs the
  configuration lock on each of the ten attempts and reaches ≈ 12 ms. Noted, and §8.4 item 7 now
  asks for both.

## Bench items

**V1 is the most valuable thing in this review** and is now the **first** item of §12.2 O2: does
`STAT.SFUSE` clear at run time once `CRCPAR` is rewritten, or does it latch until the sensor is reset?
If it latches, bit 3 of `GET_CFG_VERIFY` can never be set, `SENSOR_CFG_FAIL` sticks, and **every module
silently ships the uncalibrated mapping** — with `GET_CFG_VERIFY` reading `0x0017` as the only sign, and
`SFUSE` being inside `STAT_FAULT` so every angle read fails its status check as well. It would look like
a design that works and is worth nothing.

V2 (the `PAGEERASEWRITE` recipe) and V3 (per-bit clear-on-read of `STAT_FAULT`) were already on O2.
V2 fails safe through the read-back, as the reviewer notes.

## What the review confirmed

Worth recording, because these are the parts that cannot be tested without hardware and were checked
arithmetically rather than assumed: all 8 SSC command words against §2.1's bit layout; the clock counts
80 / 576 / 48; all 256 entries of the regenerated CRC-8 table; that `CRCPAR` covers exactly 15 bytes of
registers 0x08–0x0F **with the newly written `MOD_2` substituted**; the §6.2 outcome order row for row;
the persistent-fault rule's set/clear behaviour; all 12 `GET_SAMPLE` fields including the `int32`
headroom; and a full sweep for 16-bit-`int` defects, which found none — the shifts are safe because on
AVR `uint16_t` *is* `unsigned int` and does not promote. The reviewer also regenerated
`KER_SIN_INTERP_WORST` from the shipped table (402 × 127 + 64 = 51118) and confirmed the
`_Static_assert` is a real guard.
