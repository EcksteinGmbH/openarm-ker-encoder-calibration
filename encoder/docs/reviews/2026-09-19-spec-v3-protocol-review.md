# Adversarial review: `encoder/docs/protocol-spec.md` v3

Reviewed against: `encoder/src/main.cpp`, `encoder/platformio.ini`, `M5/src/main.cpp`,
`M5/src/RSNexus.cpp`, `M5/include/RSNexus.h`, `M5/include/Common.h`, `M5/src/SerialStream.cpp`,
`M5/include/SerialStream.h`, the v2 protocol review and the v2 review response. Read-only, with no
exploration beyond those files.

**VERDICT: REVISE.** No blocker was found. The new write gate (C3) does what the brief needs: once an
M5 has streamed since the module's last reset, nothing reopens writes. SERNUM keying does stop two
same-ID modules from **both** being unlocked. What v3 introduced or left open are state-machine and
reading-rule problems. Two of them bring back v2 defects that the response document marks "fixed":

- the snapshot rule (§4.3 r6) can be read so that the latch check (§4.8) and the station procedure
  (§7.2) both fail;
- the unlock "any other frame disarms" rule can be read so that unlock never works.

The duplicate-detection argument in §3.3 is the same one the v2 review refuted in M10. The error path
of COMMIT_CAL/SET_ID is still undefined. Seven MAJOR findings, sixteen MINOR.

Mode: started THOROUGH and escalated to ADVERSARIAL after the third MAJOR (the pattern is systemic
under-specification of state machines, not isolated slips).

Legend: **CONFIRMED** = checked in the text or source. **SUSPECTED** = reasoning only.

---

## Part 0: upstream citations re-verified

Every `file:line` in v3 was checked. All but one are correct:

- `encoder/src/main.cpp:176-208` (framing), `:203` (payload assembly), `:92` (`crc8_0x07`),
  `:120` (`ID &= 0x1F`), `:336` (`prev_id`), `:367-368` (bit replication): correct.
- `M5/src/main.cpp:29`, `:35`, `:144-147`, `:145`, `:146`, `:155`, `:162-168`, `:213`, `:216-218`,
  `:245-247`, `:255`, `:367-369`, `:431`, `:434`: correct.
- `M5/src/RSNexus.cpp:76-91`, `M5/include/Common.h:97,106`: correct.
- `SerialStream` is constructed on `Serial` (`M5/src/main.cpp:29`); `SerialStream.cpp` only uses
  `_serial`. §1.3 is correct for the non-`USE_USB` build. The `USE_USB` build uses `USBStream`,
  which is not in scope and not verified here.
- **Wrong:** §5.2 says `prev_id (:336) is computed unmasked`. `encoder/src/main.cpp:336` is
  `uint8_t prev_id = (device_id - 1) & 0x1F;`, which **is** masked. The unmasked comparison is
  `r_id == device_id` at `:323`. See m1.

---

## MAJOR

### MJ1 — The §4.3 r6 snapshot rule can be read two ways. The literal reading breaks the §4.8 latch check (v2 M7 comes back) and the §7.2 station procedure. (CONFIRMED text)

§4.3 r6 says: `Reading word 0 takes a snapshot of the whole value; higher words return from that
snapshot. A higher word read with no preceding word-0 read returns from the last snapshot.`

The rule never defines which SUBs it covers, what "the whole value" is, or what a "higher word" is.
§4.6 marks only index 0 of GET_ANGLE_RAW, GET_ANGLE_COMP and GET_LATCHED, and index 6 of
GET_ERRCNT, as *(snapshot)*.

**Reading A (literal: every index > 0 of a snapshotting SUB is a "higher word").**
- GET_LATCHED idx 3 (count and valid bits) comes from the last idx-0 snapshot. §4.8 tells the host
  to `read index 3 from every module after each latch`. If the host reads idx 3 before idx 0,
  every module returns the count from the **previous** snapshot. The counts match and the valid bits
  are set, so the check passes. The host then reads idx 0 and gets the new latch from the modules
  that latched and the old latched angle from any module whose gate was closed. A partial latch
  goes undetected, which is exactly v2 M7. The response marks M7 "fixed".
- GET_ANGLE_RAW idx 2 (raw15) and idx 3 (sequence) are frozen until idx 0 is read. §7.2 step 1
  says `record ... raw15 (GET_ANGLE_RAW index 2). Use the sample sequence number (index 3) to take
  only fresh samples.` It never tells the host to read index 0. A station written to §7.2 either
  hangs waiting for a sequence number that never changes, or records stale raw15.

**Reading B (only the 21-bit value is snapshotted; idx 2/3 are live).**
- raw15 (idx 2) and the sequence number (idx 3) come from two requests and can come from different
  samples, which is the torn read §4.3 r6 was written to prevent (response, "found during revision"
  #4). The sequence number then cannot vouch for the raw15 it is paired with.
- No index gives the validity of that sample. ANGLE_STALE is only in GET_HEALTH, a third request.
  §7.2 has no way to reject a stale, held raw15 that belongs to a failed read.

**Also undefined:**
- For GET_ERRCNT, the snapshot is marked at idx 6, but r6 says "word 0". Under the literal rule,
  reading idx 0 (CRC failures) snapshots "the whole value", whatever that means for an array of
  counters.
- Whether there is one snapshot slot or one per SUB. With one shared slot, GET_ANGLE_RAW idx 0
  followed by GET_ERRCNT idx 7 returns bits of the angle.
- What a higher word returns before any snapshot exists (power-up).
- Whether GET_CAL_WORD, GET_SERNUM and GET_TRIM are "multi-word values" under r6. If
  GET_CAL_WORD is, the read-back after COMMIT_CAL that §5.5 requires returns the pre-commit page
  unless word 0 is re-read first.

- Confidence: HIGH that the text is ambiguous; HIGH that reading A breaks §4.8.
- Why it matters: calibration data and synchronous snapshots are the whole point of the station
  interface. One reading gives silently wrong data, the other a hang.
- Fix: in §4.6, give each SUB an explicit list of which indices come from its snapshot, and which
  index takes the snapshot. State one snapshot slot per SUB and its power-up value. Put
  raw15, sequence number and a valid bit into one snapshotted group, or define §7.2's read order
  (for example idx 0, then 2, then 3) as normative. State in §4.8 the order in which the host reads
  GET_LATCHED.

### MJ2 — Unlock: "next CMD=3 frame addressed to that module" contradicts "Any other frame ... disarms". One reading makes unlock impossible. (CONFIRMED text; hardware consequence SUSPECTED)

§4.9 step 2 says `UNLOCK_2 ... must be the next CMD=3 frame addressed to that module, within the 1 s.`
A few lines later it says `Any other frame, a wrong ARG, or the timeout disarms`.

**Reading A: any frame on the bus disarms.** A module sees every frame, including ID-0 replies.
- Two modules at ID 31: both reply `0` to UNLOCK_1. Each hears the other's reply, "another frame",
  and disarms. UNLOCK_2 then gets an identical NAK SEQUENCE from both (a clean frame). The host sees
  SEQUENCE and has no way to learn why.
- One module alone: if the transceiver's receiver stays enabled while transmitting (RE not tied to
  DE; the board schematic is not in scope), the module hears its **own** UNLOCK_1 reply and
  disarms. Unlock can then never succeed on any module.
- Replies from other modules at other IDs, or any bench traffic between the two frames, also
  disarm.

**Reading B: only CMD=3 frames addressed to this ID disarm.** This works. But "any other frame" then
also includes a CMD=1 or CMD=2 frame. Those end factory mode, but nothing says they disarm the armed
state. The armed state is a separate state that factory-mode exit rules do not cover.

The spec also leaves open:
- whether UNLOCK_1 received while already in factory mode re-arms, is NAK'd, or ends factory mode;
- whether a successful UNLOCK_2 in factory mode refills a DIRTY staging buffer with `0xFF`, which
  the lifecycle table implies, silently discarding staged data;
- whether a NAK'd UNLOCK_2 (for example a retry after a lost reply) affects a module already in
  factory mode.

A host that retries after a lost UNLOCK_2 reply receives SEQUENCE while the module **is** in factory
mode.

- Confidence: HIGH on the contradiction.
- Fix: one normative sentence: "the armed state is cleared by: the next CMD=3 frame whose header ID
  equals `device_id` (whatever its SUB), any CMD=1/CMD=2 frame, or 1 s elapsing. Frames at other
  IDs, including ID-0 replies, do not affect it." Add explicit rows for UNLOCK_1 and UNLOCK_2
  received in factory mode.

### MJ3 — §3.3's duplicate detection relies on the collision behaviour that v2 M10 already refuted. The response marks M10 and B6 "fixed". (CONFIRMED text)

§3.3 says: `Two modules with identical IDs that give identical replies ... produce a clean frame ...
The station procedure therefore reads GET_SERNUM, which differs between parts`. §4.9 adds: `requires
one clean GET_SERNUM read before unlocking`.

v2 M10 had already pointed out that two RS-485 drivers sending **different** data do not reliably
produce a framing error. Drive strength, cable position and receiver fail-safe bias can give a
well-formed frame. That frame can be one module's data (one driver dominates) or a bitwise mixture.
v3 relies on the case M10 said cannot be relied on, and never defines "clean".

Walk-through with modules A and B at ID 31, where A's driver dominates:

1. `GET_SERNUM` idx 0–4: the host receives A's words, all "clean", and accepts one module.
2. `UNLOCK_1`: both modules arm and send the same reply `0`. The frame is clean.
3. `UNLOCK_2 = 0xA5E8 ^ D(A)`: A replies SUB 0x19 DATA 0. B NAKs BAD_ARG (`DATA 0x1903`). The
   replies collide, A dominates, and the host sees success. B is disarmed.
4. Every STAGE_*, and COMMIT_CAL: A replies; B NAKs NOT_UNLOCKED every time. The host sees A.
   Only A is written. **The one-module-only safety property holds.**
5. The host has no indication that B exists. Its SERNUM-keyed record describes A, but the station
   believes it has worked on *the* module on the fixture. `GET_ANGLE_RAW` (§7.2) replies are
   collisions too, so if B is the part on the fixture, B's angle data has been fitted and written to
   A (T4, "write reaches the wrong module").

If instead the reads return a bitwise mixture, D(mixture) matches neither part. Both modules then
send the same NAK BAD_ARG (a clean frame), and the host gets a misleading BAD_ARG rather than
"duplicate present".

The residual that v2 B6 asked to be stated, "exactly one unprovisioned module on the bus at a time",
is still not stated anywhere.

- Confidence: HIGH on the text. MEDIUM on how often the dominance case happens on real hardware.
- Fix: state the single-unprovisioned-module rule as a normative station requirement (C4 or §9).
  Downgrade §3.3's detection claim to "not guaranteed". Mark the M10 and B6 response rows as
  partially fixed.

### MJ4 — The failure path of COMMIT_CAL and SET_ID is undefined. "The staging buffer has a full lifecycle" (§What changed, item 8) is false. (CONFIRMED text)

§4.9 defines the success path of COMMIT_CAL and the validation-failure path
(`buffer and USERROW untouched, factory mode kept`). NAK WRITE_FAIL (0x06) exists, but no text says
what happens after it:

- USERROW state: erase and write are one page operation, so after a failure the page is most likely
  invalid.
- Live `device_id`: the module keeps answering at the old ID from RAM while USERROW is invalid, and
  falls back to ID 31 at the next reset. Nothing tells the host that the ID will change.
- Live coefficients: reloaded or not? Health bits: CAL_INVALID set at once, or only at boot?
- Factory mode: kept or ended? Staging buffer: kept (DIRTY) or discarded? The lifecycle table has no
  WRITE_FAIL row.
- For SET_ID: where the copied or identity page is built (in the staging buffer or not), and hence
  what a retry sees. If it is built in the staging buffer and factory mode is kept, the buffer is
  now DIRTY and a SET_ID retry is refused with STAGING_BUSY.

§5.5 relies on the station reading back after every commit, but gives it nothing to recover with.

- Confidence: HIGH.
- Why it matters: the one hardware-failure path of the only persistent write is left to each
  implementer. A module that answers at ID *n* but will boot as 31 is the kind of latent fault the
  station exists to catch.
- Fix: add a WRITE_FAIL row to the lifecycle table covering factory mode, buffer, live ID and
  coefficients (recommended: live identity reloaded from what was actually read back, i.e. from the
  boot validation of the read-back page), and state what the host must do next.

### MJ5 — A failed sensor config lock has no retry and does not fail reads. A calibrated module can run with the sensor's default dynamics (possibly autocalibration) under a stored fit. (CONFIRMED gap; consequence SUSPECTED)

§6.2 runs the config lock `at boot and after any detected sensor reset`. On failure it only
`sets SENSOR_CFG_FAIL`. Nothing retries it, and SENSOR_CFG_FAIL is not a read-fail condition in the
§6.2 outcome table, so reads report **ok** and are compensated.

Case: the boot lock runs before the TLE5012B has finished its own start-up. The MCU start-up delay is
8 ms (`platformio.ini:39`, `SYSCFG1 = 0x06`), and `setup()` does no wait
(`encoder/src/main.cpp:297-315`). The lock fails. Its own transfers have already read out the
sensor's reset indication (safety `S_RST` "since last read"), so no later read triggers a retry. The
module then runs with AUTOCAL, PREDICT and FIRMD at whatever the sensor's EEPROM holds. §2.4 explains
why that is wrong under a stored fit.

The only symptom is a live GET_HEALTH bit, which cannot be read while an M5 is on the bus (§9.2).

A related unstated assumption: §6.2 row 3 re-runs the lock and **fails the read** whenever
`STAT.SRST = 1`. If SRST does not clear on read (the spec never says it does; O2 lists only its bit
position), every read fails, the module sends its first valid angle forever, and the lock is
re-run on every read.

The spec also does not say what CMD=1/2 send **before the first valid read**. `latest_angle_21bit`
starts at 0 (`encoder/src/main.cpp:83`). v3 fails the first read whenever S_RST is still set. The
brief's "hold last valid" is undefined when there is no last valid value, and the M5 will mark 0° as
valid (`M5/src/RSNexus.cpp:87`).

- Confidence: MEDIUM. Sensor timing and SRST clear semantics are datasheet facts outside scope.
- Fix: specify the retry policy for a failed lock (for example, retry on every read while
  SENSOR_CFG_FAIL is set, with those reads failing), SRST clear-on-read semantics (add to O2), and
  the value transmitted before the first valid read.

### MJ6 — `SET_ID` on any "invalid" page overwrites it with an identity page, destroying recoverable calibration. (CONFIRMED text)

§4.9 says: `USERROW page invalid (e.g. virgin) → build an identity page ... and commit it.`

"Invalid" in §5.2 covers far more than virgin:
- a page with one flipped bit (CRC fail);
- a page written by a future layout (`MAGIC` ok, `LAYOUT_VER ≠ 1`, CAL_VER_UNSUPPORTED), for example
  after a firmware downgrade;
- a page where a single field fails the field checks.

In each case SET_ID silently replaces a page whose coefficients were still readable through
GET_CAL_WORD with zeros. The reply is a success (the new ID). The response to v2 B2 addresses only
the virgin case.

- Confidence: HIGH.
- Why it matters: calibration requires the reference fixture (O3). Losing it means re-calibrating
  the part, and the station gets no warning.
- Rating: MAJOR rather than MINOR because it destroys data with no error. Mitigated partly because
  the station keeps records keyed by SERNUM (§5.1).
- Fix: build the identity page only when the page is fully erased (all `0xFF`). For any other
  invalid page, NAK BAD_PAGE and require an explicit COMMIT_CAL of a full page.

### MJ7 — v2 M6 is marked "fixed" but the spec still gives no response latency or host timeout for any subcommand. The host cannot tell "gate closed" from "slow" from "reset". (CONFIRMED text)

A search of v3 finds only the factory timeout, the unlock window, T_IDLE and T_ARM_WAIT. There is
nothing on:
- the maximum reply latency of PING or GET_*;
- the latency of GET_TRIM, which by implication performs live SSC reads;
- COMMIT_CAL and SET_ID latency (programming time is ❓ O2);
- the minimum gap between host requests.

Silence has at least four meanings:
- read gate closed (rule 3);
- RESET (no reply);
- the reply is still being programmed;
- the reply was lost.

The v2 M10 late-reply problem (a timed-out reply from module A attributed to module B) has no
protocol rule either, such as "the host must not send the next request until the previous one's
timeout has expired".

- Confidence: HIGH.
- Mitigated by: `kercal` can pick generous timeouts and read back state. This is MAJOR only because
  the interface is being frozen for a separately implemented host library.
- Fix: a latency table per SUB class, with an upper bound for COMMIT/SET_ID derived from the O2
  datasheet value, plus a normative one-outstanding-request rule for the host.

---

## MINOR

**m1 — Wrong claim about `:336` (§5.2).** CONFIRMED. `prev_id` **is** masked
(`encoder/src/main.cpp:336`). The ID-33 hazard comes from `makePacket21` masking the transmitted ID
(`:120`) and `prev_id = (33-1)&0x1F = 0`. The conclusion stands; the sentence is wrong.

**m2 — §2.6 worked example gives the wrong misread temperature.** CONFIRMED arithmetic. `0x1AD` is
429 unsigned, and (429 + 152) / 2.776 = **209 °C**, not "+178 °C". The number was copied from v2 M4,
which was also wrong.

**m3 — §1.6 "one stray frame is fully suppressed" is true only for outliers ≥ 30°.** CONFIRMED.
Substitution happens only when `diff >= JUMP_THRESHOLD_DEG` (`M5/src/main.cpp:202`, `Common.h:47`).
A stray frame within 30° of the true angle takes the `else` branch at `:215-218`: it is streamed and
becomes `last_good_angle`. The same mistake was in v2 M11.

**m4 — C3 "Closes T3" overstates.** CONFIRMED text; hardware SUSPECTED.
- What C3 does prove: nothing reopens writes while an M5 streams, because only a reset clears
  `arm_seen`, RESET is F-gated, and WDT and BOD are off (`platformio.ini:34-35`).
- What it does not prove: a module on an **installed** arm is write-eligible whenever it has been up
  for 3 s without seeing CMD=2. Cases:
  - the M5 is unplugged or unpowered during §9.3 diagnostics, with modules power-cycled;
  - separate supplies where the modules come up well before the M5;
  - the M5 held in reset, or its boot taking longer than 3 s.
- The §8.4 item 6 criterion measures the wrong interval. It measures the M5's power-up to its first
  frame, but the relevant interval is the **module's** power-up to its first received CMD=2, under
  the worst supply sequencing.
- "Power-up" is used where "any reset" is meant (C3, GET_HEALTH bit 10).
- Mitigated by: exploiting it still needs the full SERNUM-keyed unlock from a host that C4 forbids on
  an arm bus, and the brief's "refused during normal streaming" is met. Fix: list this as a residual
  in §3.3 and measure the right interval.

**m5 — A single bit error on any frame can permanently disable provisioning until power-cycle.**
SUSPECTED.
- CMD=3 is `11`; one flipped bit gives CMD=2 (`10`). Examples: an ID-0 reply read as ID 0 / CMD=2,
  or a host request to ID *n* read as a CMD=2 trigger for module *n*+1.
- Either starts a real cascade on the bench. Every module latches `arm_seen` and leaves factory mode,
  the host must stop (C4), and RESET is unavailable (F-gated).
- This is the safe direction but is not documented. The same applies to any bench fixture that sends
  CMD=2.
- Fix: state that recovery is a power cycle.

**m6 — C3 contradicts C4 on CMD=1.** C3: `a bench tool may use CMD=1 without disabling provisioning`.
C4: `if any CMD=1 ... frame is seen at any time, stop transmitting`. Also, §4.9 ends factory mode on
any CMD=1. In practice CMD=1 does disable provisioning.

**m7 — C6 says every mode-changing SUB carries a magic; `LOCK` (0x1E) does not.** Other gaps:
- COMMIT_CAL `11100` → LOCK `11110` is one bit.
- STAGE_DATA carries arbitrary data, so a staged word equal to `0x8EE7` becomes RESET with one SUB
  bit flipped (`11011`→`11111`).
- A staged word `0xA50x` becomes STAGE_ADDR (`11011`→`11010`).

All of these fail safe (commit CRC, buffer discard), but C6's statement is false as written.

**m8 — NAK reasons are not unique, and precedence is undefined.**
- STAGE_ADDR with tag ok and index > 15: BAD_ARG or BAD_INDEX?
- GET_* index out of range: BAD_INDEX, but BAD_ARG's definition "value out of range" also fits.
- F-gated SUB when W fails: NOT_ELIGIBLE or NOT_UNLOCKED?
- UNLOCK_2 not armed **and** wrong ARG: SEQUENCE or BAD_ARG?
- A page failing both magic and CRC: BAD_PAGE or CRC_FAIL? §5.2 gives no evaluation order.

**m9 — Rule 4 contradicts RESET.** §4.3 r4 says every non-silenced request is answered. RESET
(addressed, F) never replies. r1 and r2 cover LATCH_SYNC; nothing exempts RESET. Also undefined:
whether RESET with a wrong magic NAKs BAD_ARG.

**m10 — "Accepted" in r7 and in the factory timeout is undefined.** Does a NAK'd request (for
example BAD_INDEX) restart the 5 s timer? Do UNLOCK frames count?

**m11 — §11.1 hook placement misses frames with `r_id == device_id` and CMD ≠ 1.** The plan puts
hooks "after `send485()` in each reply branch and on non-matching frames". A CMD=2 frame whose ID
equals the module's own ID goes to the addressed branch, where "cmd=0, cmd=2, cmd=3: do nothing"
(`encoder/src/main.cpp:323-333`). It then neither sets `arm_seen`, resets the read gate, nor ends
factory mode, contradicting §3.2 and §4.9 (`any CMD=1 or CMD=2 frame on the bus`). Reachable on the
bench from a tool addressing the module itself, or from a duplicate-ID module.

**m12 — The 16-bit SERNUM digest means "two modules sharing an ID cannot both unlock" is
probabilistic.** CRC-16 collides for about 1 in 65536 pairs. State it.

**m13 — GET_ANGLE_RAW is under-defined.**
- idx 0 "uncompensated 21-bit": on a calibrated module, is it `raw15<<6` (D10) or the upstream bit
  replication?
- The sequence number (idx 3): width, wrap, and whether it advances on failed reads.
- GET_STAT and GET_SAFETY after a failed or no-response read: raw garbage, or the last valid value?

**m14 — GET_FW_VER idx 2 "low 16 bits of the git commit"** cannot be matched against the usual
short-hash **prefix**. It should say "first 4 hex digits" or similar, and say what a dirty tree
reports.

**m15 — The build default is not in the file plan.** §5.4 requires the shared hex to be built with
`-DDEVICE_ID=31`. `platformio.ini:46` has `-DDEVICE_ID=3`, and §11.1 does not list `platformio.ini`
as modified. `encoder/src/main.cpp:38` defaults to 1 if the flag is missing, which is the ID that
answers the M5 trigger.

**m16 — BOD is disabled (`platformio.ini:35`), and the spec performs USERROW writes without a supply
check.** §5.5 covers power loss mid-write, but not a slow brown-out corrupting the programming
sequence or the page contents at low VDD. Either state that the station supply is assumed stable or
add a VDD check before programming.

---

## What's missing

- A normative station rule: exactly one unprovisioned (ID 31) module on the bus (MJ3).
- A host retry and idempotency policy. STAGE_DATA is not idempotent: a retry after a lost reply
  writes the next slot. COMMIT_CAL retries after a lost reply meet NOT_UNLOCKED, or silence at the
  old ID if the ID changed. The host needs a defined recovery (read GET_HEALTH, GET_DEVICE_ID and
  GET_CAL_WORD).
- A fit-quality acceptance criterion in §7.2. It rejects only `|A_k| > 32767`: no residual threshold
  and no angular coverage requirement. This is partly O3.
- The value sent before the first valid sensor read (MJ5).
- What GET_ERRCNT idx 3 counts when a module drops ID-0 non-LATCH frames (other modules' replies):
  are those "requests dropped"?
- An explicit statement that `arm_seen` has no software clear. With RESET F-gated, recovery is a
  power cycle only (m5).

## Ambiguity risks

- `higher words return from that snapshot` (§4.3 r6): A = every index > 0; B = only the upper bits
  of the same value. A breaks §4.8 and §7.2; B tears raw15 from the sequence number (MJ1).
- `Any other frame ... disarms` (§4.9): A = any bus frame, so unlock is impossible with self-echo or
  duplicates; B = only frames addressed to it (MJ2).
- `USERROW page invalid` in SET_ID: A = virgin only; B = any §5.2 failure, which destroys data
  (MJ6).
- `accepted CMD=3 request` (§4.3 r7, §4.9): with or without NAKs (m10).

## Multi-perspective notes

- **Executor:** state machines for the armed state, factory mode and the staging buffer cannot be
  coded to one answer (MJ1, MJ2, MJ4). §11.1's hook points miss one frame class (m11).
- **Stakeholder:** the brief's hard requirements (CMD=1/2 unchanged, no CRC, unlock plus factory
  mode, refused during streaming, hold last valid) are met in intent. "Hold last valid" is undefined
  at boot (MJ5), and O5 remains open, correctly.
- **Skeptic:** the strongest remaining failure is a station that silently calibrates the wrong
  module or records a partial latch as consistent. Both come from reading-rule ambiguity, not from
  the safety design.

## Response document audit

| v2 # | Response | Actual |
|---|---|---|
| B1 | fixed | **Fixed** for the brief. The residual is overstated as closed (m4). |
| B2 | fixed | **Fixed** for virgin parts. The identity page passes §5.2 (magic, ver 1, ID 1–30, N_HARM 0, all slots zero, CRC). It over-applies to non-virgin invalid pages (MJ6). |
| B3 | fixed | **Fixed.** The citation text is wrong (m1). |
| B4 | fixed | **Fixed.** Some fields are still undefined (m13). |
| B5 | fixed | **Fixed.** |
| B6 | fixed | **Partial.** Two modules can no longer both unlock, but duplicate detection is unsound and the one-virgin-module rule is still unstated (MJ3). |
| M1 | fixed | **Fixed** in the spec text. The §11.1 hook plan misses one case (m11). |
| M2 | fixed | Fixed in effect. The C3 wording contradicts C4 (m6). |
| M6 | fixed | **Not fixed.** No response times (MJ7). |
| M7 | fixed | **Only under one reading of r6** (MJ1). |
| M8 | fixed | **Partial.** WRITE_FAIL row and re-UNLOCK rows are missing (MJ4, MJ2). |
| M10 | fixed | **Partial.** Only identical replies are covered, and late-reply attribution is not (MJ3, MJ7). |
| M11 | fixed | Fixed, but repeats the ≥ 30° slip (m3). |
| M20 | fixed | **Partial.** LOCK has no magic, and STAGE_DATA can alias magic-bearing SUBs (m7). |
| M4 | fixed | Fixed. The worked number is wrong (m2). |
| minor 10 | fixed | Partial (m14). |

## Open questions (unscored)

- Whether the RS-485 transceiver's receiver is enabled during transmit (decides how bad MJ2 reading A
  is).
- The TLE5012B start-up time after power, relative to the MCU reaching the boot config lock, and SRST
  clear-on-read semantics (MJ5).
- Whether USERROW programming on the ATtiny1616 stalls the CPU or interrupts. This decides whether
  CMD=2 frames can be missed during a commit.
- `USE_USB` builds: `USBStream` was not checked for RS-485 use (§1.3 is verified only for
  `SerialStream`).
- Whether the M5's actual time to first frame, including a `USE_USB` enumeration path, is below
  1.5 s (§8.4 item 6).

## v2 findings checked and genuinely closed

B2 (virgin case), B3, B4, B5, M1, M3, M4 (apart from the number), M5, M9, M12, M13/M14 (accepted,
correctly), M15, M17, M18, M19, M21, M22, M23 (accepted), minor 3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 18,
19, 20.
