# KER encoder firmware — independent review against protocol-spec.md (frozen)
Date: 2026-09-21. Reviewer pass only; no build run, no hardware.

Files read: encoder/src/{ker_cmd3.cpp,ker_cmd3.h,ker_sensor.cpp,ker_sensor.h,ker_cal.c,
ker_cal.h,ker_health.h,ker_health.c,ker_comp.c,ker_ssc.h,main.cpp} plus the generated
tables ker_crc8.inc / ker_sinq7.inc / ker_sinq7_bound.inc, ker_comp.h and ker_version.h
(constants only), and platformio.ini (one line, §5.4).
Spec sections read: 1, 2.1–2.6, 3.2–3.4, 4.1–4.10, 5, 6, 7.1, 7.4.

## Verdict

**REQUEST CHANGES.** No BLOCKER found. 3 MAJOR (wire-level conformance deviations,
none unsafe on an arm), 7 MINOR. The parts of the design that can hurt — ID-0 reply
addressing, the read gate, `arm_seen`, the gate R/W/F assignment per SUB, the SSC command
words, both CRCs, the compensation fixed-point path and the upstream bit-exactness
fallback — are all correct as far as static reading can establish.

| Sev | # | Title | Location |
|---|---|---|---|
| MAJOR | M1 | Record index truncated to 8 bits: out-of-range ARG answered as index 0 | ker_cmd3.cpp:464-472 |
| MAJOR | M2 | Unlock window survives two addressed requests that NAK before `dispatch()` | ker_cmd3.cpp:609-610, 617 |
| MAJOR | M3 | Record NAK precedence inverted: BAD_INDEX returned where spec demands SEQUENCE | ker_cmd3.cpp:323-325 |
| MINOR | m1 | GET_ANGLE_RAW record mixes two transactions | ker_cmd3.cpp:264-273 |
| MINOR | m2 | `ker_cnt.total` saturates; spec says it wraps | ker_sensor.cpp:254 |
| MINOR | m3 | VDD stops being refreshed while SENSOR_CFG_FAIL is set | ker_sensor.cpp:233-247 |
| MINOR | m4 | S_RST failures counted as `stat_err` / SENSOR_STAT_ERR, undocumented | ker_sensor.cpp:270-275 |
| MINOR | m5 | `config_lock()` overwrites `stat_last` seen by GET_STAT | ker_sensor.cpp:183 |
| MINOR | m6 | no-response test also requires the safety word to be all-0/all-1 | ker_sensor.cpp:209-212 |
| MINOR | m7 | gated counter counts broadcast LATCH_SYNC with a wrong magic | ker_cmd3.cpp:593 |

Plus 2 items where the **spec**, not the code, is stale (S1, S2) and 3 bench-verification
items that static review cannot settle (V1–V3).

---

## 1. Protocol conformance, subcommand by subcommand

### 1.1 SUB numbering
`ker_cmd3.cpp:39-47` — the enum is sequential from `SUB_NAK = 0`. Walked against §4.6:
0x00 NAK … 0x14 LATCH_SYNC, 0x15 GET_RUN_WORD, 0x16 SAMPLE_START, 0x17 GET_SAMPLE,
0x18 UNLOCK_1, 0x19 UNLOCK_2, 0x1A STAGE_ADDR, 0x1B STAGE_DATA, 0x1C COMMIT_CAL,
0x1D SET_ID, 0x1E LOCK, 0x1F RESET. **All 32 match.** NAK reasons at `:49-54` match §4.5
(0x01 correctly absent). Magics at `:56-65` match §4.6 exactly.

### 1.2 Gates, per SUB
`ker_cmd3.cpp:406-409`:
```c
if (sub >= SUB_UNLOCK_1 && sub != SUB_LOCK) {
  if (!write_eligible()) { nak(sub, NAK_NOT_ELIGIBLE); return 0; }
  if (sub >= SUB_STAGE_ADDR && !factory_mode) { nak(sub, NAK_NOT_UNLOCKED); return 0; }
}
```
This yields R for 0x01–0x17 and 0x1E, W for 0x18/0x19, F for 0x1A–0x1D and 0x1F.
**Exactly §4.6.** The LOCK carve-out is the right call and is commented (`:404-405`);
§4.6 does list LOCK as gate R.

Gate W's "and addressed (not broadcast)" component (§4.4) is satisfied structurally:
broadcasts return at `ker_cmd3.cpp:606` before `dispatch()` is reached.

### 1.3 ARG/index checks, per SUB — correct
GET_FW_VER `>3` (:415), GET_ENV `>1` (:437), GET_TRIM `>4` (:441), GET_SERNUM `>4` (:445),
GET_CAL_WORD / GET_RUN_WORD `>15` (:452), SAMPLE_START tag `0x5A` then `e>10` (:480-481),
STAGE_ADDR tag `0xA5` then `i>15` (:507-508), SET_ID tag `0x5E` then `1..30` (:532-534),
CLR_ERRCNT `0xC1EA` (:475), COMMIT_CAL `0xC0DE` (:520), LOCK `0x10CC` (:542),
RESET `0x8EE7` (:547), UNLOCK_1 `0x5A17` (:487), UNLOCK_2 `0xA5E8 ^ digest` (:493),
LATCH_SYNC `0x1A7C` (:602). All match §4.6. Rule 5 ("non-zero ARG to a subcommand that
takes none is ignored") holds for PING/GET_PROTO_VER/GET_DEVICE_ID/GET_HEALTH/GET_STAT/
GET_DMAG/GET_SAFETY/GET_CFG_VERIFY/GET_CAL_STATUS (`:412`, `:424-434`).

`SERNUM_DIGEST` is CRC-16/CCITT-FALSE over `SIGROW.SERNUM0..9` (`ker_cmd3.cpp:251-256`
with `ker_crc16`, `ker_cal.c:151-160`, poly 0x1021 / init 0xFFFF / no reflection / no
final XOR) — §4.9 as written.

### M1 — MAJOR. Record index truncated to 8 bits; out-of-range ARG answered as index 0
`ker_cmd3.cpp:464-472`
```c
r = record_read((uint8_t)arg, 4, rec_raw, &rec_raw_ok, capture_raw, &v); break;
```
`arg` is the full 16-bit ARG; the cast discards bits 15:8 **before** the range test in
`record_read()` (`:323`).

Concrete failure: `GET_ANGLE_RAW` with `ARG = 0x0100`. §4.6 gives the index range as 0–4,
and §4.5 defines BAD_INDEX as "index **or value** outside its range", so the module must
NAK `BAD_INDEX`. Instead it computes `idx = 0`, **captures a fresh record** and replies
`SUB = 0x0A, DATA = rec_raw[0]` — a perfectly plausible answer. Same for
`GET_ANGLE_COMP 0x0200`, `GET_LATCHED 0x0400`, `GET_ERRCNT 0x0800`, `GET_SAMPLE 0x0C00`,
and for any ARG whose low byte is in range.

Why it matters beyond conformance: §4.3 rule 9 says "Replies echo SUB but not the index",
so the host cannot detect the substitution from the reply. A single bit error in the ARG
high byte (carried in wire bytes d1/d2) therefore turns a request for field *k* into a
silent, *side-effecting* re-capture of field 0 — and for GET_ANGLE_RAW / GET_SAMPLE the
re-capture destroys the atomic snapshot the host was part-way through reading (§4.3 rule
6), so fields read after it belong to a different transaction than fields read before.
That is a data-integrity hazard for the §7.2 fit, not merely a wrong NAK.

Fix: test the 16-bit value before narrowing, e.g. make `record_read`'s first parameter
`uint16_t` and keep `if (idx > last) return 0;`.

### M2 — MAJOR. Two addressed requests do not disarm the unlock window
`ker_cmd3.cpp:609-610` and `:617`
```c
if (sub == SUB_NAK)        { nak(sub, NAK_UNSUPPORTED);    return; }   // :609
if (sub == SUB_LATCH_SYNC) { nak(sub, NAK_BAD_ADDRESSING); return; }   // :610
...
uint8_t accepted = dispatch(sub, arg);
if (!(sub == SUB_UNLOCK_1 && accepted)) unlock_armed = 0;              // :617
```
Both early returns bypass `:617`.

§4.9 is explicit: `UNLOCK_2` "must be the **next** CMD=3 request whose header ID equals
this module's `device_id`", and the window is "Disarmed by: **any other request to this
module**". Concrete failing sequence, all addressed to `device_id`, gate W open:
`UNLOCK_1(0x5A17)` → `SUB 0x00` (NAK UNSUPPORTED) → `SUB 0x14` (NAK BAD_ADDRESSING) →
`UNLOCK_2(correct digest)`. Spec requires the last one to be NAK `SEQUENCE`; the code
enters factory mode.

Not exploitable on its own — the SERNUM digest is still required and C4 forbids a host
transmitting on an arm bus — but it is a documented property of a safety gate (C5) that
a conformance test will fail, and the "next request" rule is precisely what makes a
mis-decoded intervening frame (T6) fail safe.

Fix: move the disarm to the top of the CMD=3 path, or replicate it in both early returns.

### M3 — MAJOR. Record NAK precedence inverted
`ker_cmd3.cpp:321-328`
```c
if (idx > last) return 0;    // -> BAD_INDEX
if (idx == 0) capture();
else if (!*ok) return 2;     // -> SEQUENCE
```
§4.3 rule 11 fixes the order as "… → **sequence** (`SEQUENCE`) → magic or tag (`BAD_ARG`)
→ **index range** (`BAD_INDEX`) → …". Sequence precedes index range.

Concrete failure: after reset, with no index-0 read of `GET_ANGLE_RAW` yet, send
`GET_ANGLE_RAW(9)`. Spec: NAK `SEQUENCE` (0x0A). Code: NAK `BAD_INDEX` (0x04). Same for
every record subcommand. A host that keys its recovery on `SEQUENCE` (reissue index 0)
versus `BAD_INDEX` (a bug in the host's own index table) is steered to the wrong recovery.

Fix: check `*ok` for `idx != 0` before the range test. (Note this is the *only* place the
rule-11 order is violated; SET_ID's `BAD_ARG → BAD_INDEX → STAGING_BUSY` at `:532-535,366`
and UNLOCK_1/2's `SEQUENCE → BAD_ARG` at `:486-493` are both correct.)

### Correct precedence elsewhere — confirmed
- UNSUPPORTED first: `:609` (SUB 0x00 as a request) precedes everything. No SUB is
  reserved in v5, so "unknown SUB" cannot arise after the 5-bit mask at `:587`.
- Addressing second: `:610`.
- Gate R closed → silence, ahead of all NAKs (rule 3): `:592-595`.
- Rule 2 (broadcasts never reply, not even NAKs): `:600-607`.
- Rule 4 (correctly formed RESET does not reply): `:546-549`.

---

## 2. Gates and factory mode

### 2.1 Correct
- **C1 / T1.** `reply()` and `nak()` both call `makePacket21(0, 3, …)`
  (`ker_cmd3.cpp:130, 136`). Every CMD=3 reply is ID 0. `device_id` can never be 0
  (build default 31, page validation `1 ≤ id ≤ 30` at `ker_cal.c:188,204`), so
  `main.cpp:253` never matches a broadcast and `main.cpp:266,270` only ever replies to a
  CMD=**2** frame from `prev_id`.
- **C2.** `ker_cmd3.cpp:592`: `if (!run_100ms || (now - last_arm_frame) < T_IDLE_MS)`.
  `last_arm_frame` is set for CMD=1 **and** CMD=2 of **any** ID (`:572-576`), never for
  CMD=3. `run_100ms`/`run_3s` are also advanced from the read path (`:231-232`) so they
  progress on a bus with no traffic at all. Unsigned `millis()` differences wrap
  correctly. `last_arm_frame = 0` at reset gives gate-open at exactly 100 ms.
- **C3.** `write_eligible()` = `!arm_seen && run_3s` (`:333`); `arm_seen` set only by
  CMD=2 (`:577`) and cleared by nothing (no software clear — and a latched module cannot
  reach RESET because RESET is gate F, so §3.2's argument holds).
- **The 5 s factory timeout** (`:597`) and **the 1 s unlock window** (`:598`) are both
  evaluated before dispatch on every gate-open CMD=3 frame, including broadcasts. Both
  use unsigned `millis()` deltas.
- **What ends factory mode.** `:578` (any CMD=1/CMD=2), `:597` (5 s), `:527` (COMMIT_CAL),
  `:537` (SET_ID), `:543` (LOCK), MCU restart (`:548`). Exactly §4.9's list.
- **UNLOCK_1 while in factory mode** → `SEQUENCE`, no state change (`:486`). **UNLOCK_2
  with the correct digest while in factory mode** → reply 0, no state change (`:497-504`)
  so a retry after a lost reply is safe. **Wrong digest while armed** → disarms, NAK
  `BAD_ARG`, factory mode continues (`:493-496`). **UNLOCK_1 while armed** re-arms and
  restarts the window (`:488` + `:617`). All four match §4.9.
- **Staging buffer state table (§4.9).** Entering factory mode fills 0xFF, index 0, CLEAN
  (`:499-500`); `STAGE_ADDR(i)` sets index (`:509`); `STAGE_DATA` writes, increments,
  marks DIRTY (`:514-516`) and NAKs `BAD_INDEX` with nothing written at index 16 (`:513`);
  a page that fails §5.2 leaves buffer, USERROW, running state and factory mode untouched
  (`:523-524`, checks run on `staging` before any programming); a program/verify failure
  returns `WRITE_FAIL` and **stays** in factory mode with the buffer intact (`:526`);
  success ends factory mode and discards the buffer (`:527`/`:537` → `end_factory_mode()`
  clears `staging_dirty`/`staging_index`, and re-entry memsets 0xFF at `:499`, so no stale
  word can ever be committed).
- **Write failure leaves the running state alone.** `commit_page` (`:170-182`) returns
  before `adopt_page` on any failure, sets `USERROW_WRITE_FAIL` and bumps `wr_fail`.
  I traced the concern that `commit_page` adopts the read-back without comparing it to
  the page it programmed — it is **not** a defect: `ker_userrow_program`
  (`ker_cal.c:263-266`) does a full byte-for-byte read-back compare and returns 0 on
  mismatch, so `commit_page` can only reach `adopt_page` with `back == page`.
- **SET_ID source table (§4.9).** `do_set_id` (`:363-383`): DIRTY → `STAGING_BUSY` first
  (`:366`); running-from-valid-page → copy `running_page`, `page[2] = new_id` (byte 2 is
  DEVICE_ID per §5.1), reseal (`:368-371`); build-default + virgin → `ker_page_build_identity`
  (`:380`, and `ker_cal.c:226-233` writes magic 0x4B, LAYOUT_VER 1, id, everything else 0,
  sealed — exactly §4.9); build-default + invalid-non-virgin → `BAD_PAGE` (`:379`).
  All four rows correct, and because the source is the running state a `WRITE_FAIL`ed
  SET_ID is retryable as §4.9 claims.
- **VDD guard.** `ker_vdd_mv() < 4500` before programming (`:171`, `ker_cal.h:42`). §5.5.

### 2.2 Findings — none beyond M2.

---

## 3. Records

### 3.1 Correct
- Five independent records with five independent `*_ok` flags (`ker_cmd3.cpp:112-116`),
  zero-initialised at reset and never cleared. §4.3 rule 6's independence and
  "since reset" both hold.
- Index 0 captures atomically then returns field 0 (`:324-326`).
- `GET_CAL_WORD` has no record and reads USERROW live each time (`:456-458`). §4.3 rule 6.

### 3.2 Field layouts, checked bit by bit
**GET_ANGLE_RAW** (`:264-273`): [0]/[1] = `(raw15<<6)|(raw15>>9)` split 15:0 / 20:16 ✓;
[2] = raw15 ✓; [3] = `seq_no`, advanced once per angle transaction only
(`ker_sensor.cpp:253`; housekeeping and config-lock transactions do not touch it) ✓;
[4] = bit 0 passed, bit 1 compensation active (`ker_sensor.cpp:330-331`) ✓.

**GET_ANGLE_COMP** (`:275-280`): 15:0 / 20:16 of `ker_sensor_angle()` ✓.

**GET_LATCHED** (`:282-290`): [0]/[1]/[2] ✓; [3] = `latch_count` (uint8, wraps mod 256) |
bit 8 valid | bit 9 any-latch-since-reset ✓. `do_latch` (`:388-396`) computes validity as
"neither held nor degraded" from `ANGLE_STALE | ANGLE_DEGRADED | NO_VALID_ANGLE` ✓ (§4.7,
and §6.2's "a latch taken on [a passed-through reading] has its valid bit clear").

**GET_ERRCNT** (`:292-302`): 0/1 = total split; 2 crc, 3 status, 4 no-response, 5 gated,
6 NAKs, 7 write failures ✓. Indices 2–7 saturate via `ker_cnt_bump` (`ker_health.h:227`) ✓.
Counter 5 is bumped only for frames this module would otherwise have acted on
(`ker_cmd3.cpp:593`) ✓ §4.7.

**GET_SAMPLE** (`:304-318`, accumulation at `:200-222`) — the one I checked hardest:
- [0] `smp_status | (e<<8)`: bit 0 done, bit 1 aborted, bit 2 saturated, bits 11:8 = e ✓
  (`e ≤ 10`, so it cannot spill past bit 11).
- [1] passing readings, [2] failing readings ✓; only `flags & 0x01` (i.e. `KER_RD_OK`) is
  accumulated, so a persistent-fault pass-through counts as a **failure** and is not
  accumulated — §6.2 as written ✓.
- [3] `r₀` = raw15 of the first passing reading ✓.
- [4]/[5] `Σ wrap₁₅(raw15 − r₀)` as int32. `:207-209`:
  `d = (int16_t)((uint16_t)(raw15 - smp_r0) & 0x7FFF); if (d >= 0x4000) d -= 0x8000;`
  maps into [−2¹⁴, 2¹⁴) ✓. Worst case |Σ| = 1024 × 16384 = 1.7e7, fits int32 ✓.
- [6]/[7] `Σ d²` as uint32 saturating; `:211` `if (smp_sum_d2 > 0xFFFFFFFF - dd)` is the
  correct pre-add test and sets status bit 2 ✓ (it genuinely can saturate: 1024 × 16384²
  = 2.7e11).
- [8]/[9] `c₀` = compensated output of the reference reading ✓.
- [10]/[11] `Σ wrap₂₁(output − c₀)` as int32: `:213-215` masks 21 bits then folds at
  2²⁰ ✓. Worst case |Σ| = 1024 × 2²⁰ = 1.07e9 < 2³¹ — fits, with ~2× margin ✓.
- Abort: `sample_abort()` (`:187-189`) sets bit 1 and leaves bit 0 **clear**, and is a
  no-op on an already-finished run so it cannot clobber a completed result ✓.
  `SAMPLE_START` restarts cleanly (`:191-198`) ✓. §4.10.

**GET_HEALTH** (`ker_health.h:188-201` vs §4.7): bits 0,1,2,3,4,5,7,8,9,10,11,12,13 all
at the specified positions; bit 6 and 15:14 never written ✓. Sticky mask is exactly
{3,4,5,9} (`:203-204`) ✓. `CLR_ERRCNT` zeroes the counters and clears the sticky bits
(`ker_health.c:261-270`) ✓ §4.6. Live bits recomputed at reply time (`ker_cmd3.cpp:335-340`).
Initial value `NO_VALID_ANGLE` (`ker_health.c:258`) ✓ §6.2.

**GET_CAL_STATUS** (`ker_cmd3.cpp:342-358`): bit 0 = bits 1–4 all set (`:353`,
`(v & 0x1E) == 0x1E`) ✓; bits 1–4 from the four independent flags ✓; bit 5 comp active ✓;
bit 6 virgin ✓; bit 7 `memcmp(stored, running_page)` ✓; bits 15:8 LAYOUT_VER as stored ✓.
Describes USERROW **now**, not the running page ✓ §4.7.

**GET_CFG_VERIFY** (`ker_sensor.cpp:174-193`): bit 0 MOD_1 under mask, bit 1 MOD_2 under
mask, bit 2 CRCPAR read back, bit 3 SFUSE clear, bit 4 every safety word clean with S_RST
ignored, bits 15:8 attempts saturating at 255 ✓. `0x001F` = pass ✓.

### m1 — MINOR. GET_ANGLE_RAW record mixes two transactions
`ker_cmd3.cpp:264-273`. `ker_sensor_raw15()` returns `last_raw15`, which is written only
inside `publish()` (`ker_sensor.cpp:226-229`), i.e. only on an OK read or a persistent-fault
pass-through. `seq_no` and `last_flags` describe the *last attempted* transaction. So when
the last transaction failed and was held, fields 0–2 come from transaction *N−k* while
fields 3–4 come from transaction *N*. §4.7 says the record is "captured together from one
sensor transaction".

Benign in practice — field 4 bit 0 is clear, so a §7.2 station discards the sample — but
the sequence number returned is not the sequence number of the returned raw15, which is
the one thing the host uses to tell two samples apart. Either hold a `last_raw15_seq`
alongside `last_raw15`, or state the mixing in §4.7.

### m7 — MINOR. Gated counter counts a malformed broadcast
`ker_cmd3.cpp:593`: `if (!bcast || sub == SUB_LATCH_SYNC) ker_cnt_bump(&ker_cnt.gated);`
bumps for a broadcast with SUB 0x14 even when ARG ≠ `0x1A7C`, which is not a LATCH_SYNC.
Cosmetic; the counter is diagnostic only.

---

## 4. Sensor path

### 4.1 SSC command words — arithmetic, against §2.1 (RW·LOCK·UPD·ADDR[9:4]·ND[3:0])
| Constant | Hex | RW | LOCK | UPD | ADDR | ND | Verdict |
|---|---|---|---|---|---|---|---|
| `CMD_READ_ANGLE_BLOCK` | 0x8003 | 1 | 0000 | 0 | 0x00 | 3 | ✓ §6.1 STAT/ACSTAT/AVAL |
| `CMD_READ_CFG_BLOCK` | 0x806A | 1 | 0000 | 0 | 0x06 | 10 | ✓ MOD_1…TCO_Y |
| `CMD_READ_STAT` | 0x8001 | 1 | 0000 | 0 | 0x00 | 1 | ✓ |
| `CMD_READ_FSYNC` | 0x8051 | 1 | 0000 | 0 | 0x05 | 1 | ✓ §2.6 |
| `CMD_READ_DMAG` | 0x8141 | 1 | 0000 | 0 | 0x14 | 1 | ✓ D_MAG |
| `CMD_WRITE_MOD_1` | 0x5061 | 0 | **1010** | 0 | 0x06 | 1 | ✓ §2.1 config write |
| `CMD_WRITE_MOD_2` | 0x5081 | 0 | 1010 | 0 | 0x08 | 1 | ✓ |
| `CMD_WRITE_TCO_Y` | 0x50F1 | 0 | 1010 | 0 | 0x0F | 1 | ✓ |
(`ker_sensor.cpp:30-37`.) The `CB_*` enum at `:40-41` indexes the 0x06-based block
correctly: MOD_2 = +2, MOD_3 = +3, OFFX +4, OFFY +5, SYNCH +6, IFAB +7, TCO_Y +9.

Clock counts match §6.2/§6.1 exactly: angle 16+48+16 = **80**; config lock
192 + 3×48 + 192 + 48 = **576**; housekeeping 16+16+16 = **48**.

MOD_1 FIRMD mask/value `0xC000` / `0x8000` = FIRMD 2 ✓ §2.4. MOD_2 mask/value
`0x7FFF` / `0x0800` = AUTOCAL 00, PREDICT 0, ANGDIR 0, ANGRANGE[14:4] = 0x080 ✓ §2.4,
with bit 15 preserved.

### 4.2 Safety-word CRC — §2.2
`crc8_frame` (`ker_sensor.cpp:84-93`): init 0xFF, command word big-endian first, then each
data word big-endian, final inverted ✓. For a write, the "data word" passed is the word
written (`&v, 1` at `:146,150,166`) ✓ — that is the subtle one and it is right.
I regenerated `ker_crc8.inc` from poly 0x1D MSB-first: **all 256 entries match.**
Only the low byte of the safety word is compared (`(uint8_t)safety`) ✓ §2.2 bits 7:0.

### 4.3 CRCPAR — §2.5
`ker_sensor.cpp:157-164`:
```c
for (uint8_t i = CB_MOD_2; i <= CB_TCO_Y; i++) {
  crc = crc8_feed(crc, (uint8_t)(cb[i] >> 8));
  if (i != CB_TCO_Y) crc = crc8_feed(crc, (uint8_t)cb[i]);   // 15 bytes, not 16
}
```
That is registers 0x08–0x0F big-endian, dropping the final low byte = the CRCPAR byte
itself: **exactly 15 bytes** ✓. `cb[CB_MOD_2] = v;` at `:151` substitutes the **newly
written** MOD_2 before the CRC is computed ✓ — §2.5's key requirement. MOD_1 (0x06) is
correctly outside the block ✓. Final inversion `(uint8_t)~crc` ✓, written into TCO_Y[7:0]
only ✓.

### 4.4 Outcome table — §6.2 evaluation ORDER
`ker_sensor.cpp:209-219`, in this order: all-zeros/all-ones → no-response; safety CRC
mismatch → CRC; `S_RST == 0` → RESET; `S_ERR|S_ACC|S_ANG` not all set **or**
`STAT & 0x1EFE` → status; else OK. **Matches §6.2 row for row, in order.**
`KER_STAT_FAULT = 0x1EFE` (`ker_sensor.h:130`) = bits 1–7 and 9–12 ✓ §2.3, SRST excluded ✓.

### 4.5 Persistent-fault rule (D18) — §6.2
`ker_sensor.cpp:256-291`. On OK: `consec_fail = 0`, publish, clear
`ANGLE_STALE | NO_VALID_ANGLE | ANGLE_DEGRADED` ✓. On failure: increment `consec_fail`
(saturating at 255 so it cannot wrap back below the threshold ✓), count the cause, set the
sticky bit. Pass-through condition is `r == KER_RD_STATUS && consec_fail >= 20`
(`KER_PERSIST_FAIL`, `ker_sensor.h:142`) — **status-only, never no-response, never CRC,
never S_RST** ✓. On pass-through: publish, set `ANGLE_DEGRADED`, clear `ANGLE_STALE` and
`NO_VALID_ANGLE` ✓. Otherwise set `ANGLE_STALE` and hold ✓. A pass-through does not reset
`consec_fail`, so the state is self-sustaining while the fault persists ✓.

### 4.6 Config lock sequence — §6.2
`ker_sensor.cpp:133-195`: read the block; write MOD_1; write MOD_2; recompute and write
CRCPAR; read back and compare under mask; read STAT and confirm SFUSE clear; cache the
five trim registers from the **read-back** copy. §6.2's order exactly. `safety_clean`
(`:123-127`) requires a valid CRC and `S_ERR = S_ACC = 1` and **ignores S_RST** ✓ §6.2's
"within the lock, S_RST = 0 is expected". Outside the lock, S_RST is a failure (`:214`) ✓.
Failure sets `SENSOR_CFG_FAIL` (`:194`), which suspends compensation
(`ker_sensor_comp_active()`, `:222-224`) and triggers a retry in place of every 16th
housekeeping read (`:234`) ✓ §6.2. An S_RST outcome re-runs the lock immediately rather
than waiting (`:274`) ✓ §6.2's "re-run the config lock".

Housekeeping alternation: `housekeeping()` runs at `(read_tick & 0x0F) == 0`, and
`read_tick & 0x10` therefore alternates 0/0x10 across successive housekeeping slots
(16 → DMAG, 32 → FSYNC, 48 → DMAG …) ✓ §6.3. D_MAG masked to bits 9:0 (`:240`) ✓ §4.6.

### m2 — MINOR. `ker_cnt.total` saturates instead of wrapping
`ker_sensor.cpp:254`: `if (ker_cnt.total != 0xFFFFFFFFUL) ker_cnt.total++;`
§4.7 index 0/1: "32-bit, **wraps** after 49 days at 1 kHz". Saturating changes the
documented behaviour (and the host's rate arithmetic across the boundary). The note in
`ker_health.h:206-207` claims saturation applies to "2..7"; the code applies it to `total`
as well. Either wrap `total` or amend §4.7.

### m3 — MINOR. VDD freezes while the config lock is failing
`ker_sensor.cpp:233-234`: `if (ker_health & KER_H_SENSOR_CFG_FAIL) { config_lock(); return; }`
returns before `ker_vdd_start()`/`ker_vdd_ready()` at `:244-246`. So a module with a
permanently failing lock reports the start-up VDD for ever, while §4.6 index 1 promises
"measured at start-up **and on every housekeeping transaction**". This is exactly the
state in which a station wants the live supply. Move the VDD pair above the early return.

### m4 — MINOR. S_RST failures counted as status faults
`ker_sensor.cpp:270-275` bumps `ker_cnt.stat_err` and sets `SENSOR_STAT_ERR` for
`KER_RD_RESET`. §6.2 makes S_RST its own outcome row and §4.7 defines counter 3 / bit 4 as
"reads with a status fault". A sensor that resets repeatedly is indistinguishable from one
with a STAT fault. Defensible (there is no spec'd counter for it), but it should be said
somewhere — and sensor resets are the one fault a bench needs to see separately.

### m5 — MINOR. `config_lock()` overwrites `stat_last`
`ker_sensor.cpp:183`. §4.6 GET_STAT: "STAT as received in the most recent transaction".
A config lock is a transaction, so this is arguably in scope — but it means GET_STAT can
report a STAT read during a lock rather than the one the last *angle* transaction was
judged on, which is what a host correlating GET_STAT with GET_SAFETY / GET_ANGLE_RAW[4]
will assume. Note it in §4.6 or keep a separate `stat_last_angle`.

### m6 — MINOR. No-response test also requires the safety word to be all-0/all-1
`ker_sensor.cpp:209-212` requires `w[0..2]` **and** `safety` to be uniform. §6.2 says
"all words `0x0000` or all `0xFFFF`". Stricter than the spec; a bus stuck such that the
three data words are uniform but the safety word is not falls through to the CRC test and
is reported as a CRC failure instead of no-response, which changes the classification
(and, materially, whether the persistent-fault rule may pass it through — it may not
either way, so no safety impact). Either widen the test or pin the wording in §6.2.

---

## 5. Integer and C correctness on a 16-bit-`int` target

I walked every arithmetic expression in the five compiled files against `int` = 16 bits.
**No defect found.** The cases worth recording because they look wrong and are not:

- `ker_comp.c:81` `uint16_t a16 = (uint16_t)(raw15 << 1);` — on AVR `uint16_t` **is**
  `unsigned int`, so it does not integer-promote to `int`; the shift is unsigned modulo
  2¹⁶ and yields 0xFFFE at raw15 = 0x7FFF. On a 32-bit host it promotes to `int`, gives
  65534, and the cast truncates to the same value. Identical.
- `ker_comp.c:60` `(uint16_t)(a1 - a0) * (uint16_t)frac + (1u << 6)` — same reasoning; the
  comment at `:57-59` is correct. I regenerated the bound: worst product over the shipped
  `ker_sinq7.inc` is `max(step) × 127 + 64 = 402 × 127 + 64 = 51118`, which is exactly
  `KER_SIN_INTERP_WORST` in `ker_sinq7_bound.inc`, and `< 0xFFFF`, so the
  `_Static_assert` at `ker_comp.c:48-49` really does guard the only unsafe thing here.
  The table is monotone (checked, all 129 points) — the other assumption the bound needs.
- `ker_cal.c:154,156` CRC-16 inner loop — same; unsigned throughout on AVR.
- `ker_cmd3.cpp:207-208` — `(uint16_t)(raw15 - smp_r0)` is unsigned mod 2¹⁶ on AVR and
  reaches the same value via `int` on the host (the difference is bounded by ±32767
  because raw15 is masked to 15 bits at `ker_sensor.cpp:207` and `ker_comp.c:76`);
  `d - 0x8000` works out identically because `0x8000` is `unsigned int` on AVR and `int`
  on the host, and both paths land on the same `int16_t`. Fragile-looking, correct.
- `ker_cmd3.cpp:310,316` correctly cast the **signed** accumulators to `uint32_t` before
  `>> 16`, avoiding an implementation-defined arithmetic shift.
- `ker_comp.c:87,93` rely on an arithmetic right shift of a negative `int32_t` — stated in
  §7.4 item 2 as a deliberate, tested dependency. `acc` worst case is
  6 × (32767 × 32767 >> 8) ≈ 2.5e7, well inside int32 ✓. `delta = ((acc + 512) >> 10) * 8`
  is §7.4 item 2 verbatim, and the 8-LSB grid of §7.1/D22 ✓.
- `ker_comp.c:79` `if (c->n == 0 || c->n > KER_NHARM_MAX)` → §7.4 item 5 ✓, and prevents
  indexing past `amp[]`/`phase[]` if validation is ever bypassed.
- `ker_cal.c:193-198` slot-zero loop indexes words `2k+3` / `2k+4` for
  `k = n_harm … 5` → harmonics n_harm+1 … 6, and `ker_page_to_cal` (`:216-219`) reads
  `2k+3` / `2k+4` for `k = 0 … n_harm−1` → H1 at words 3/4 … H6 at words 13/14.
  Matches §5.1 ("harmonic *k* has AMP in word 2k+1, PHASE in word 2k+2", 1-based) ✓.
  Neither loop can leave the 16-word page.
- `ker_cal.c:182` CRC over `KER_PAGE_BYTES - 2` = bytes 00–1D, compared with word 15 ✓ §5.1.
- Page validation order (`ker_cal.c:201-209`) is §5.2's order 1…6, and only
  `KER_PAGE_ERR_CRC` maps to `CRC_FAIL` (`ker_cmd3.cpp:523-524`) ✓.
- Stack: the deepest path is `dispatch → SUB_SET_ID → do_set_id (page[32] + stored[32] +
  info) → commit_page (back[32] + info)`, ≈ 110 bytes of locals on a 2 KB part. Fine.

`ker_ssc.h` is a verbatim move; `sscWrite16`/`sscRead16` use `int8_t i` loop counters and
`(v >> i) & 1` on a `uint16_t`, which is fine on both targets.

---

## 6. Anything that could make an unmodified M5 misbehave

- **Never transmits unasked.** The only calls to `send485()` are `main.cpp:259` (CMD=1
  addressed to `device_id`), `main.cpp:273` (CMD=2 from `prev_id`) and
  `ker_cmd3.cpp:131,137` (CMD=3 reply/NAK, both behind the read gate). Nothing is driven
  by a timer. ✓
- **Every CMD=3 reply is ID 0.** ✓ (see §2.1 above). A module hearing its own CMD=3 reply
  takes the broadcast path and ignores it, because no reply carries SUB 0x14 — NAK replies
  carry SUB 0x00 (`ker_cmd3.cpp:136`) ✓ §4.2.
- **A module with no valid page is bit-exact with upstream on CMD=1/CMD=2.**
  `adopt_page`'s failure branch (`ker_cmd3.cpp:150-157`) forces `running_cal.n = 0`;
  `ker_sensor_comp_active()` then returns 0; `publish()` calls `ker_compensate` with
  `cal_uncalibrated`; `ker_comp.c:79` returns `((uint32_t)raw15 << 6) | (raw15 >> 9)` —
  literally §1.7's expression, from the same AVAL register (`w[2] & 0x7FFF`,
  `ker_sensor.cpp:207`) ✓. The two documented departures are that a failed read holds the
  previous value instead of sending garbage, and that a module that has never read sends 0
  — both §6.2, and §6.2 explains why the M5 tolerates the latter.
- **Build default is 31.** `main.cpp:42` and `platformio.ini:46` (`-DDEVICE_ID=31`).
  `prev_id = (31 − 1) & 0x1F = 30` (`main.cpp:266`), so an unprovisioned module is inert on
  an arm ✓ §5.4. Page validation refuses ID 31 and ID > 30 (`ker_cal.c:188,204`), which is
  what closes §5.2's "ID 33 transmits as wire ID 1" hole ✓.
- **Frame parsing is upstream's**, unmodified (`main.cpp:151-199`), and `makePacket21`
  masks ID/CMD/data as before (`:103-122`) ✓.
- **Sampling cannot run on an arm**: `SAMPLE_START` is gate R, and gate R needs 100 ms with
  no CMD=1/2 ✓. A CMD=1/2 frame aborts a run before the subsequent read is taken
  (`ker_on_frame` → `sample_abort()` at `:579` runs before loop's read at
  `main.cpp:295-301`), so no reading is ever consumed after an abort ✓ §4.10.
- **`device_id` cannot desynchronise** between main.cpp's cascade dispatch and CMD=3:
  `set_device_id` writes both through `device_id_slot` (`ker_cmd3.cpp:85-88, 243`) ✓.

---

## Where I think the SPEC is wrong, not the code

**S1 — §5.4 is stale.** It says the shared hex "requires changing `encoder/platformio.ini:46`
(currently `-DDEVICE_ID=3`) and the fallback in `encoder/src/main.cpp:38` (currently 1)".
Both are already 31 (`platformio.ini:46`, `main.cpp:42`). The requirement is met; the
sentence should become a statement of fact, or a reader will "fix" a non-problem.

**S2 — §6.2's "≈ 9 ms" start-up is optimistic in the failure case.** `ker_sensor_start`
(`ker_sensor.cpp:302-311`) is 7 ms + one lock (≈0.25 ms) + up to 10 × (80 clocks + 200 µs),
and each failing read whose cause is S_RST re-runs the lock (`:274`), adding ≈0.25 ms
apiece. A sensor that reports S_RST on every attempt gives ≈ 7 + 0.25 + 10 × (0.25 + 0.24)
≈ 12 ms, not 9. It still costs nothing at power-up (§1.4) and is still comparable to
upstream on a mid-operation reset, but the number in §6.2 should carry the worst case.

**Also worth noting, not a defect:** §4.9's "Factory mode ends on any of: 5 s without an
accepted request **to this module**" versus §4.3 rule 7's "Only accepted requests restart
the factory timer", where `LATCH_SYNC` is explicitly an accepted request. The code lets a
broadcast `LATCH_SYNC` restart the timer (`ker_cmd3.cpp:604`). Both readings are available
from the text; pick one and say so.

---

## Bench-verification items (static review cannot settle these)

**V1 — does SFUSE clear at run time after CRCPAR is rewritten?** `ker_sensor.cpp:184`
requires `!(st & STAT_SFUSE)` for `GET_CFG_VERIFY` bit 3, and §2.5 says a wrong CRCPAR
leaves SFUSE set. If the TLE5012B evaluates the parameter CRC only at reset/startup and
latches SFUSE, then writing MOD_2 (which invalidates CRCPAR) followed by a corrected
CRCPAR will still leave SFUSE set until the next sensor reset. The consequence is not
subtle: `SENSOR_CFG_FAIL` sticks, compensation is suspended permanently (§6.2), and every
module ships behaving like an uncalibrated one while reporting `GET_CFG_VERIFY = 0x0017`.
This is the single highest-value thing to put on the first bench session.

**V2 — `NVMCTRL_CMD_PAGEERASEWRITE_gc` + `EEBUSY` is the right USERROW recipe for the
ATtiny1616**, and the 32 mapped byte writes at `ker_cal.c:258` really do land in the NVM
page buffer. `ker_cal.c:246-267` is the megaTinyCore EEPROM idiom and `BOOTEND = 0x00`
(`platformio.ini:42`) makes the whole flash BOOT so `_PROTECTED_WRITE_SPM` is legal
anywhere — but the page-buffer path for USERROW specifically should be confirmed against
the datasheet before the first station run, since a silent failure here is a bricked
provisioning step. The read-back compare at `:263-266` means it fails safe either way.

**V3 — `STAT_FAULT = 0x1EFE` bit-by-bit clear-on-read behaviour**, already flagged ❓ in
§2.3. A bit that stays set after its condition clears will make every read fail, and after
20 reads the persistent-fault rule will start passing the angle through with
`ANGLE_DEGRADED` permanently set — which is survivable but would be mistaken for a magnet
or wiring fault.

---

## Positive observations

- The §4.6 gate column is implemented as a single ordered pair of range tests
  (`ker_cmd3.cpp:406-409`) rather than 32 per-case checks. It is the kind of thing that is
  usually wrong; here it maps onto the table exactly, including the LOCK carve-out.
- `commit_page` / `do_set_id` get the hard part right: the running state is never touched
  until a byte-for-byte read-back has succeeded, and the SET_ID page is built from the
  *running* state, which is what makes §4.9's "a `SET_ID` that fails with `WRITE_FAIL` can
  simply be retried" actually true.
- The CRCPAR construction (`ker_sensor.cpp:157-164`) substitutes the just-written MOD_2
  and stops after 15 bytes. Both halves of that are easy to get wrong and neither is.
- `ker_comp.c` is disciplined about the 16-bit target in exactly the places §7.4 demands,
  and the `_Static_assert` on the generated bound is a real guard, not decoration — I
  recomputed the bound from the shipped table and it is tight and correct.
- The health model cleanly separates live from sticky bits and recomputes the live ones at
  reply time, so `GET_HEALTH` cannot report a stale gate state.
- Comments mark the deliberate departures (`ker_cmd3.cpp:404-405, 494, 574-576`;
  `ker_sensor.cpp:271-273, 280-283`) and each one I checked is sound.
