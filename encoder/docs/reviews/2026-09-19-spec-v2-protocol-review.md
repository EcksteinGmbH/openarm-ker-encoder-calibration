# Adversarial review — `encoder/docs/protocol-spec.md` v2

Reviewed against: `encoder/src/main.cpp`, `M5/src/RSNexus.cpp`, `M5/src/main.cpp`,
`M5/include/RSNexus.h`, `M5/include/Common.h`. Read-only, no repo exploration beyond these.

**VERDICT: REJECT.** Six blocker-class defects. The safety argument in §3.2/§3.3/§3.4 is
one-sided (it protects the M5 from the module but not the module from the M5's own boot),
the primary provisioning path (`SET_ID` on a virgin part) silently does nothing while
reporting success, `COMMIT_CAL` has no field validation so a bad page can put a module on
the arm impersonating joint 1, and three reply payloads referenced by name are never
defined at all — the interface cannot be implemented independently as frozen.

Escalated to adversarial mode after the first blocker.

---

## Part 0 — Factual claims about upstream: what checks out

These are CONFIRMED and I do not discuss them further:

- §1.4 "the M5 ignores the CMD field" — `M5/src/RSNexus.cpp:76`
  `uint8_t received_id = (_packet[0] & 0x7C) >> 2;` — the two CMD bits are never read.
- §3.3 `received_id >= 1` discards ID 0 — `M5/src/RSNexus.cpp:81`.
- §3.4 cascade safety — `encoder/src/main.cpp:340`
  `if (r_id == prev_id && (r_cmd & 0x03) == 2)`; an ID=0/CMD=3 frame fails the CMD test.
- §4.2 `prev_id` arithmetic — `encoder/src/main.cpp:336` `(device_id - 1) & 0x1F`;
  ID 1 → 0, ID 31 → 30. Both as stated.
- §1.5 bit replication — `encoder/src/main.cpp:367-368`; 0x7FFF→0x1FFFFF, strictly
  monotonic, gain 2097151/32767 = 64.0000305. Exact.
- §1.2 CMD dispatch table — `encoder/src/main.cpp:321-352`, including "cmd=0, cmd=2,
  cmd=3: do nothing" at line 332.
- §1.3 `requestPacket(BULK)` = ID 0 / CMD 2 — `M5/include/Common.h:29` `#define BULK 0`,
  `M5/include/RSNexus.h:27` `uint8_t cmd = 2`.
- §1.1 20 µs/frame at 2 Mbps 8N1. §5.2 chain arithmetic (480/1280/560 µs). §7 resource
  arithmetic (13806/1869 headroom). §4 LSB arithmetic (0.000172°, ±5.63°, 0.0110°).
  All exact.
- §6.3's "the M5 already owns the zero point" — `M5/include/Common.h:83`,
  `M5/src/main.cpp:159, 231-249`. Correct.

Everything below is a defect.

---

## BLOCKERS

### B1 — The bus-idle gate is defeated by the M5's own power-up. Both countermeasures fail in the same window. (CONFIRMED)

§3.2: *"`t_last_chain` is initialised to the boot instant, so the gate starts closed and
opens only after 100 ms of observed silence. A freshly powered module never assumes an
idle bus."*

The M5 does not transmit for well over half a second after power-on:

- `M5/src/main.cpp:431` — `delay(500);`
- `M5/src/main.cpp:434` — `xTaskCreatePinnedToCore(acquisitionTask, ...)` comes *after* it
- `M5/src/main.cpp:133` — the task then calls `rs485nexus.begin(...)` before its first
  `requestPacket` at line 146

Preceding that `delay(500)` are `M5.begin(cfg)` (display/panel init), a `Preferences`
open/read/close (`M5/src/main.cpp:367-369`) and `gui.init()`. Realistic first-frame time
is 700 ms – 1 s from power-on.

The encoder, by contrast, reaches `loop()` after `Serial.begin()` and six GPIO writes
(`encoder/src/main.cpp:297-315`) — single-digit milliseconds.

So on a normal arm power-up every module's gate is **open** from t≈100 ms until the M5's
first frame at t≈700 ms. The invariant the spec states is inverted: a freshly powered
module *does* assume an idle bus, and does so for ~600 ms every single power cycle.

Worse, the §3.4 host-side mirror — *"the PC tool must listen and confirm 100 ms of bus
silence before transmitting any CMD=3 frame"* — passes in exactly the same window. D1's
two "independent" countermeasures are not independent with respect to this failure: they
share the same trigger condition and fail together.

Consequence: any host on the bus during arm power-up (calibration rig left connected,
tool retrying a timed-out request) gets a ~600 ms window in which `UNLOCK_1` → `UNLOCK_2`
→ `SET_ID`/`COMMIT_CAL`/`RESET` all succeed. Six frames at 20 µs each fit trivially. If
the M5 then starts streaming mid-`COMMIT_CAL`, the USERROW page write halts the ATtiny
CPU for ~10 ms (see M6), the module drops chain frames, and — because `_valid[idx]` is
set once at `M5/src/RSNexus.cpp:87` and **never cleared anywhere in the class** — the M5
keeps streaming the stale angle rather than flagging the channel.

Fix required: the spec must either derive `T_IDLE_GATE` from a measured bound on M5
startup silence and boot-silence of the module relative to it, or gate on a
positive event ("at least one CMD=2 frame observed since boot") rather than on elapsed
silence alone. As written the 100 ms number is asserted, never derived against any M5
behaviour, and the one M5 behaviour that matters contradicts it.

### B2 — `SET_ID` on a virgin or invalid USERROW silently does nothing and reports success. (CONFIRMED from the spec's own text)

§3.9: *"`SET_ID` is a convenience path for the test station: it reads the current USERROW
into the staging buffer, replaces the ID field, recomputes the CRC and commits — leaving
calibration data intact."*

§4.1 says a virgin part *"reads back all `0xFF`, which fails the magic check"*.

Compose the two. On a virgin part, `SET_ID(n)`:
1. loads `0xFF × 32` into the staging buffer,
2. writes `n` into word 1 `[15:8]`,
3. computes a **valid** CRC-16 over bytes 0x00–0x1D,
4. commits.

Word 0 (MAGIC) is still `0xFFFF`, not `0x524B`. On the reload, §4.1's first clause fails,
`CAL_INVALID` is set, and `device_id` reverts to the build-time default of 31 (D3). The
module's ID did not change. §3.6 nonetheless specifies `SET_ID`'s reply as `0 = ok`.

Additional damage: word 2 `[15:8]` N_HARM is now `0xFF` and word 1 `[7:0]` LAYOUT_VER is
`0xFF` — both are permanently burned into a page that now carries a *valid* CRC, which is
the one property that would otherwise have distinguished "never provisioned" from
"provisioned wrongly".

This is the single most obvious workflow at a calibration station (flash → assign ID →
calibrate) and the spec defines it to fail silently. §3.9 never states a precondition;
§3.6's table gives `SET_ID` no `BAD_*` reason for this case; §3.5's reason table has no
code that fits.

### B3 — `COMMIT_CAL` validates only the CRC-16, and §4.1's boot validation never range-checks DEVICE_ID. A mis-staged page puts a module on the arm impersonating joint 1. (CONFIRMED)

§3.9: *"`COMMIT_CAL` verifies the CRC-16 in word 15 before touching USERROW"* — that is
the **only** stated check. §4.1's boot validation is `magic ok AND layout_ver supported AND
n_harm <= 5 AND crc16 ok`. **DEVICE_ID is not validated at either end.**

Word 1 `[15:8]` is a `u8` (§4 table), so a staged value of 0 or 17–255 passes both checks.
Then:

- `encoder/src/main.cpp:118-122` — `makePacket21` does `ID &= 0x1F`. A committed
  `device_id = 33` transmits on the wire as **ID 1**.
- `encoder/src/main.cpp:336` — `prev_id = (33 - 1) & 0x1F` = **0**.
- `encoder/src/main.cpp:340` — it therefore answers the M5's own `ID=0 CMD=2` trigger,
  every millisecond, colliding on a half-duplex bus with the real joint 1.

That is *precisely* the failure mode §4.2 was written to prevent ("A virgin module built
with ID 1 has `prev_id == 0` and would answer the M5's own trigger frame"), and D3's
mitigation is bypassed by the protocol's own sanctioned write path.

`device_id = 0` is likewise committable: §1.3 states *"No encoder may be provisioned with
ID 0"* and §3.9 rejects `SET_ID(0)` with `BAD_ARG`, but the `STAGE_DATA`×16 → `COMMIT_CAL`
path has no such check, and §4.1 does not enforce it at boot either. So the one rule the
spec calls out as inviolable is enforced in exactly one of the two paths that can violate it.

Fix required: §4.1's validation list and `COMMIT_CAL`'s pre-burn check must both include
`1 <= device_id <= 31` (and a decision on 17–31 given D6 says the chain is 1–16).

### B4 — Three reply payloads are named but never defined. The interface is not implementable as frozen. (CONFIRMED)

§3.6 specifies these return values and no section anywhere defines their contents:

| SUB | DATA as specified | Defined where? |
|---|---|---|
| 0x04 `GET_DEVICE_ID` | "`[15:8]` source flags" | nowhere |
| 0x10 `GET_CAL_STATUS` | "`[7:0]` status bits" | nowhere |
| 0x12 `GET_CFG_VERIFY` | "per-register readback verify bitmap" | nowhere |

§3.7 enumerates `GET_HEALTH` bits and `GET_ERRCNT` indices in full, so the omission is not
a stylistic convention — these three were simply left out. The document's own status line
says "Freezes ... the CMD=3 diagnostic/factory sub-protocol", and the whole point of the
freeze is that deliverable 4 (the Python library) can be written against it. It cannot.

`GET_CFG_VERIFY` is the worst of the three: it is the only readback of the D5 sensor
configuration, so the bitmap's bit-to-register mapping is the contract between
`ker_sensor.c` and the calibration station's pass/fail criterion.

### B5 — `LOCK`'s gate is `"any"`, a value the §3.6 legend never defines; the permissive reading transmits a frame into a live cascade. (CONFIRMED)

§3.6's legend defines exactly two values: *"`idle` = bus-idle gate only; `factory` =
bus-idle gate **and** factory mode."* The table then uses four more:

- `0x1E LOCK` → **`any`**
- `0x18 UNLOCK_1` → `idle, addressed only`
- `0x19 UNLOCK_2` → `idle, must follow UNLOCK_1`

`any` has two defensible readings:
- **A:** "any lock state, bus-idle gate still applies" — harmless.
- **B:** "any bus state, no gate" — `LOCK` is then honoured while the chain is streaming,
  and §3.6 specifies it replies `0 = ok`. That reply is a module driving a half-duplex
  RS485 bus in the middle of a 16-frame cascade: a guaranteed collision that corrupts
  whichever chain frame it lands on, and the collision is between two *encoders*, not
  encoder-and-M5, so §3.3's ID=0 protection is irrelevant to it.

Reading B is the natural one given that `idle` and `factory` are both defined *as* gates
and `any` is offered as a third member of that same set. A one-word ambiguity in a frozen
spec that decides whether the protocol can transmit during live arm operation is a blocker
regardless of which reading the author intended.

### B6 — D3 makes every virgin module ID 31, which breaks §3.9's replay protection against the project's own default and allows silent duplicate provisioning. (CONFIRMED by composition)

§3.9 justifies the two-step unlock: *"The device-ID term means a captured unlock pair
cannot be replayed against a different module."*

D3 / §4.2: *"The shared hex is built with `-DDEVICE_ID=31`."*

Therefore **every unprovisioned module in the building accepts the identical unlock pair**
(`UNLOCK_1 ARG=0x5A17`, `UNLOCK_2 ARG = 0xA5E8 ^ (31 × 0x0101) = 0xBAF7`). The
device-ID term provides zero discrimination in the only situation where unlock is ever
used — a virgin part at the calibration station.

Concretely: two virgin modules on the bench bus. `UNLOCK_1`/`UNLOCK_2` addressed to 31
unlock **both**. A subsequent `STAGE_*`/`COMMIT_CAL`/`SET_ID` is executed by **both**.
Both burn the same ID into USERROW. The host observes only a garbled reply (two
transmitters) and retries — but the writes already completed. Result: two modules with the
same device_id and the same calibration curve, no error reported, discovered later as a
chain collision on an assembled arm.

§3.3 hand-waves this as *"duplicate IDs show up as two modules replying at once — a bus
collision and a framing error, which is detectable"*. That detects the *reply*; it does
not undo the *write*, and it arrives after the damage.

The spec never states the constraint this implies — **exactly one unprovisioned module may
be on the bus at a time** — anywhere, despite §4.2 asserting that ID 31 leaves a module
"still addressable at the test station".

---

## MAJOR

### M1 — §3.2's gate trigger set and §3.9's factory-exit trigger set contradict each other. (CONFIRMED)

- §3.2: *"`t_last_chain`, the time of the last received **CMD=1 addressed to it** or any
  CMD=2 frame."*
- §3.9: factory mode ends on *"**any CMD=1** or CMD=2 frame appearing on the bus"*.

`CMD=1 addressed to it` ≠ `any CMD=1`. A bench tool polling modules 1–8 with CMD=1 leaves
module 9's gate **open** (§3.2) while simultaneously kicking module 9 **out of factory
mode** (§3.9). Two different rules, two different implementations in `ker_cmd3.c`, and
the spec presents them as one mechanism ("This is the mechanism behind 'writes are refused
during normal operation'").

### M2 — CMD=1 bench tooling and CMD=3 diagnostics are mutually exclusive, and the spec does not say so. (CONFIRMED)

§1.3 establishes CMD=1 *"exists only for bench tooling"*. §3.2 then makes every CMD=1
addressed to a module close that module's gate for 100 ms.

So a bench session cannot interleave angle reads (CMD=1) with diagnostics (CMD=3) without
a 100 ms dead time before every single CMD=3 frame — a `GET_CAL_WORD` sweep of 16 words
becomes 1.6 s minimum. The two mechanisms the spec preserves for bench use are designed to
lock each other out, and §3.2's cost claim (*"a one-time 100 ms at station start-up and
nothing thereafter"*) is only true if the station never uses CMD=1 at all.

### M3 — `GET_ERRCNT[6]` cannot serve its stated purpose. (CONFIRMED)

§3.7: index 6 = *"total angle reads attempted (denominator for an error rate)"*, and the
counters are *"saturating `uint16_t`"*.

One SSC read is triggered per reply (`encoder/src/main.cpp:330, 344` set
`do_ssc_read = true`), i.e. ~1000/s at the ≥1 kHz chain rate. 65535 / 1000 = **65 seconds
to saturation**. After a minute of operation the denominator is pinned and every error
rate computed from it is wrong in an unbounded direction.

Every other counter saturating is fine — they count exceptions. This one counts the norm
and was given the same type.

### M4 — `GET_TEMP` will be misread at every normal temperature: the spec never says to sign-extend. (CONFIRMED arithmetic)

§2.6 defines `TEMPR` as *"a **signed 9-bit**, already offset-compensated temperature"*,
hands the host `T[°C] = (TEMPR + 152.0) / 2.776`, and §3.6 specifies `GET_TEMP` returns
*"FSYNC, raw (`TEMPR` in bits 8:0)"*.

Invert the formula: TEMPR = 2.776·T − 152. At **+25 °C, TEMPR = −82.6**. At 0 °C,
TEMPR = −152. TEMPR only becomes positive above **+54.75 °C**.

So the negative branch is the *normal* case, not an edge case. A host that masks bits 8:0
and applies the formula to the unsigned result reports +184 °C for a module at 0 °C and
+178 °C at room temperature. The spec passes a raw register to the host, states the width
and signedness in a different section (§2.6) from the subcommand definition (§3.6), and
never states the sign-extension step in either. Deliverable 4 will get this wrong.

### M5 — §5.1's reply-path budget omits the gate bookkeeping, which is the only new work that *is* on the critical path. (CONFIRMED against the code structure)

§5.1: *"Added work on the reply path is one comparison to route CMD=3 away from the
CMD=1/CMD=2 branches. Budget: **≤ 2 µs**."*

§3.2 requires `t_last_chain` to be refreshed on *every* received CMD=2 frame — including
the very frame that triggers this module's reply. §3.9 requires the same frame to be
tested for factory-mode exit. Both land in `encoder/src/main.cpp:321-352`, upstream of
`send485()`.

On an 8-bit AVR a `millis()` read is not a comparison: it disables interrupts and reads a
volatile 32-bit counter. Against a **≤ 5 µs per-hop** design target that §5.2 derives as
the actual constraint (not the 50 µs ceiling), a `millis()` call plus the store is a
material fraction of the entire budget, and it is invisible in §5.1's accounting.

The spec also never fixes the **ordering** — refresh `t_last_chain` before replying (adds
latency to every hop) or after (the gate is one frame stale). Two implementers will choose
differently and only one will hit the timing target.

### M6 — §3.9's "writes stop immediately" guarantee cannot be honoured, and no subcommand has a specified response time. (CONFIRMED for the second half; SUSPECTED for the first)

§3.9: *"**any CMD=1 or CMD=2 frame appearing on the bus** — if the arm starts streaming,
writes stop immediately."*

A USERROW page erase+write on the ATtiny1616 halts the CPU for ~10 ms (NVMCTRL). During
that window the module cannot observe the bus at all, so a write already in flight cannot
be stopped by anything. The guarantee is unachievable by construction for the one operation
it is meant to guard. (SUSPECTED — NVM timing is from the ATtiny datasheet, outside the
files in scope.)

The larger, CONFIRMED problem: **the spec specifies no response latency or timeout for any
subcommand.** §3.2 tells the host *"The host sees a timeout and knows the bus is live"* —
a timeout with no specified duration. `COMMIT_CAL` (~10 ms of NVM), `RESET` (reboot +
another 100 ms gate close), `GET_*` (one SSC transaction) and `PING` differ by three orders
of magnitude and the host tool has nothing to size its timeouts against. This is a frozen
wire interface with a Python implementation as a separate deliverable.

### M7 — `LATCH_SYNC` can be silently partially executed, and there is no way to tell. (CONFIRMED)

§3.8: broadcast latch, *"**No module replies** — the only deliberately unanswered frame in
the protocol, which is what makes it safe to broadcast."*

§3.2: a gated request is dropped *"in complete silence. No reply, no NAK"*.

For `LATCH_SYNC` these two produce identical observable behaviour: **silence means both
"latched" and "dropped"**. If any subset of modules has its gate closed (one was reset,
one was hot-plugged, one's RX resynced late), those modules do not latch, and
`GET_LATCHED` then returns **whatever they latched previously** — §3.6 defines no
freshness indicator, no latch sequence counter, and no "never latched" sentinel.

The host assembles a "synchronous" 16-joint snapshot in which some samples are from a
different latch event entirely, with nothing in the protocol to detect it. For a
calibration station this is the worst possible failure: silently wrong data that looks
right. §3.8's claim that all samples *"share one timestamp to within the frame's
propagation delay"* is unconditional and false under the gate.

`GET_LATCHED` before any `LATCH_SYNC` is likewise undefined.

### M8 — Staging-buffer lifetime is completely unspecified; `SET_ID` silently destroys staged data. (CONFIRMED from §3.9)

§3.9 gives the flow `UNLOCK_1 → UNLOCK_2 → STAGE_ADDR(0) → STAGE_DATA ×16 → COMMIT_CAL →
(reload) → LOCK` and says nothing about the buffer outside it. Undefined:

1. **Is the buffer cleared on entry to factory mode?** If not, a host can stage words 0–7
   fresh, leave 8–14 from a previous module's session, restage word 15 with a matching
   CRC, and `COMMIT_CAL` accepts it — because §3.9's only pre-burn check is the CRC. A
   Frankenstein calibration page passes every gate in the protocol.
2. **Is the staging index valid before the first `STAGE_ADDR`?** §3.9's flow implies
   `STAGE_ADDR` is mandatory but nothing makes it so.
3. **What does `STAGE_DATA` do at index 16?** §3.6 says it returns "next staging index";
   after word 15 that is 16. `BAD_INDEX` is presumably intended but never stated.
4. **`SET_ID` "reads the current USERROW into the staging buffer"** — so
   `STAGE_DATA ×16 → SET_ID → COMMIT_CAL` silently discards the staged calibration and
   re-commits the old one, returning `0 = ok` twice. No warning, no error code.
5. **What happens to the buffer on the 5 s factory timeout mid-staging?** §3.9's timer is
   reset only by *"accepted factory subcommand"* — and `GET_*` subcommands are gated
   `idle`, not `factory`, so a station that verifies with `GET_CAL_WORD` between batches
   does not reset the timer and can be dropped out of factory mode mid-upload.

### M9 — `COMMIT_CAL` that changes the device's own ID leaves the session in an undefined address space. (CONFIRMED)

§3.9's flow is `COMMIT_CAL → (reload) → LOCK`. After the reload the module's `device_id`
is the newly committed one.

- Factory mode was entered against the **old** ID (`UNLOCK_2 ARG = 0xA5E8 ^ (device_id ×
  0x0101)`). Is it still valid after the ID changes? Unstated.
- `LOCK` is an *addressed* subcommand. Addressed to the old ID or the new one? §3.9's
  flow diagram gives no address. Unstated.
- The reply to `COMMIT_CAL` is ID=0 (§3.3), so the host gets no signal of the new ID from
  the frame — it must re-run `GET_DEVICE_ID`, which the spec does not say to do.

Two competent implementers will disagree on all three, and the station will hang on `LOCK`
against one of them.

### M10 — §3.3's rationale for discarding the reply ID is unsupported, and its cost is not acknowledged. (CONFIRMED)

§3.3: *"duplicate IDs show up as two modules replying at once — a bus collision and a
framing error, which is detectable, and arguably more reliable than reading a header."*

Two RS-485 drivers contending do not reliably produce a framing error; the resulting bit
pattern depends on drive strength, cable position and bit alignment, and can be a
perfectly well-formed frame. "Arguably more reliable" is asserted with no evidence, and
the spec nowhere requires the host to check for framing errors at all.

The unacknowledged cost: with ID=0 on every reply, **a late reply is attributed to the
wrong module**. §3.1's *"Exactly one request produces at most one reply"* is a statement
about the device, not a normative prohibition on the host pipelining, and if a host times
out module A and moves to module B, A's late answer is indistinguishable from B's. Replies
can be matched by echoed SUB, never by source. Given B6 (duplicate IDs are the *default*
state at the station), this is the normal case, not the exception.

### M11 — §1.4 overstates the M5's reaction to a stray frame; §3.4 contradicts it; and the real exposure is elsewhere. (CONFIRMED)

§1.4, called *"The single most important finding in this document"*: a CMD=3 frame *"would
trip the jump detector after `JUMP_CONFIRM_FRAMES` (20 frames) and fault the arm."*

`M5/src/main.cpp:216-218` resets `jump_count[i] = 0` on every frame with
`diff < JUMP_THRESHOLD_DEG`, and line 213 substitutes `last_good_angle[i]` for the
outlier. So **one stray frame is fully suppressed by the M5 and cannot trip anything** —
20 *consecutive* deviations are required, as §3.4 correctly says. §1.4 and §3.4 state
different things about the same mechanism, and §1.4 is the one the design is justified by.

The genuine exposure, which the spec misses entirely, is in the paths that bypass jump
detection:

- **Grippers.** `M5/include/Common.h:97` and `:106` set `skip_jump_detect = true` for ch8
  and ch16. `M5/src/main.cpp:200` excludes them from the check, so a stray frame on either
  gripper channel reaches the PC stream unsubstituted and undetected.
- **Jump detect off.** `M5/src/main.cpp:328-330` exposes a GUI toggle; with
  `jump_detect_enabled` false, line 197 disables the check on all 16 channels.
- **STANDBY mode.** Line 198 requires `mode == AppMode::STREAM`; in STANDBY the else
  branch at 219-223 accepts the stray value as the new `last_good_angle`, so it also
  poisons the first STREAM frame after start.
- **The zeroing workflow — worst of the four.** `M5/src/main.cpp:155` stores
  `snapshot.sensors[i].raw_deg` *before* jump detection, and line 238 reads
  `save_val = snapshot.sensors[i].raw_deg` when saving jig offsets, then line 246 commits
  it to NVS. Jump detection never touches `raw_deg`. A stray CMD=3 frame landing in the
  same 1 ms window as a `ZERO_ALL` writes a garbage jig offset to persistent storage,
  permanently, silently.

§3.4's risk assessment (*"a single stray frame is one bad sample, overwritten 1 ms later"*)
is correct for the streaming path and wrong for the persistence path.

### M12 — The firmware upgrade invalidates every stored jig zero offset, and the spec claims the M5's zeroing workflow is untouched. (CONFIRMED)

§6.3: *"the M5 already owns the zero point through `ENCODER_CONFIG[].mech_joint_offset`
plus jig zeroing. Adding one here would fight that."* §8's scope is `encoder/` only and
task constraint 5 is that nothing M5-side needs touching.

`g_state.jig_angle_offsets` is persisted in NVS (`M5/src/main.cpp:245-247`) and reloaded
at boot (`:367-369`). Those values were captured from *uncompensated* angles. Harmonic
compensation shifts each module's reported angle by up to several degrees (§6.1 cites raw
errors of 0.48°–3.42°). After flashing calibrated firmware, **every stored jig offset is
wrong by that module's compensation delta**, and the arm reads wrong until re-zeroed.

The M5's *code* is untouched; its *persisted data* is invalidated. The spec has no
migration or re-zero requirement anywhere. A secondary effect: `M5/src/main.cpp:162-168`
applies a ±360° wrap correction against `mech_min/mech_max ± MARGIN_DEG`; a channel sitting
within the shifted amount of a limit can flip a full turn after the upgrade.

### M13 — Mixed calibrated/uncalibrated chains are undetectable from the M5 or the PC. (CONFIRMED by composition)

§4.1: an invalid USERROW yields *"compensation DISABLED (raw angle passed through)"* — a
per-module fallback the spec calls degrading *"exactly to upstream behaviour"*.

At system level this means a 16-joint arm can run with an arbitrary mix of compensated and
uncompensated channels. CMD=1/2 carry no health field (unchanged by design), the M5's
`error_mask` (`M5/src/main.cpp:479-483`) only reports `_valid`, and `_valid` is never
cleared (`M5/src/RSNexus.cpp:87` sets it; nothing resets it). The only way to read
`CAL_INVALID` is `GET_HEALTH`, which D1 makes unreachable while the M5 is powered.

So the one failure mode §4.1 introduces is, by D1's construction, invisible from every
operational interface. Neither §4.1 nor §3.2 owns this consequence.

### M14 — All of §3.7's diagnostics are RAM-resident and unreachable, possibly permanently. (CONFIRMED / SUSPECTED)

§3.7's latched health bits (3, 4, 5, 7, 9) and all eight `GET_ERRCNT` counters are
*"since boot"* state. Reading any of them requires 100 ms of bus silence (§3.2), and
`M5/src/main.cpp:144-147` transmits unconditionally — **outside** any `AppMode` check, so
STANDBY does not silence the bus either. The only way to create the silence is to stop the
M5.

If the M5 and the encoder modules share a supply rail (SUSPECTED — not determinable from
the files in scope), powering down the M5 power-cycles the modules and erases exactly the
state one was trying to read. `GET_HEALTH` and `GET_ERRCNT` would then be permanently
unreadable for any real operating session. The spec must state the requirement that the
RS-485 line can be isolated without cutting module power, or the feature is decorative.

### M15 — §8's minimal-diff claim contradicts §2.2, §2.4 and D5. (CONFIRMED)

§8: *"`encoder/src/main.cpp` gains only: three `#include`s, a `ker_init()` call in
`setup()`, a `ker_on_angle()` call in the SSC-read block, and one `else if` branch for
CMD=3 in `loop()`"* — *"modified, ~15 lines"*.

Four things in that list are wrong or missing:

1. **The safety word (§2.2 / requirement 5) cannot be read from another file.** The 16
   extra clocks must occur before CS rises, and CS rises inside
   `tleReadAvalRawFast()` at `encoder/src/main.cpp:277`, a `static inline` function in
   `main.cpp`. `ker_sensor.c` cannot reach it.
2. **The D5 sensor config writes cannot either.** `sscWrite16`, `sscRead16`, `csLow`,
   `csHigh`, `dataOut`, `dataIn`, `dataWrite`, `dataRead` are all `static inline` in
   `encoder/src/main.cpp:225-265`. `ker_sensor.c` must either duplicate all eight bit-bang
   primitives or `main.cpp` must be restructured to export them. Neither is "~15 lines".
3. **The bus-idle gate needs a hook in the chain branch, not the addressed branch.**
   §3.2 keys on *any* CMD=2 frame; those frames land in the `else` at
   `encoder/src/main.cpp:334-352`, not in the `r_id == device_id` branch where the CMD=3
   `else if` goes. That is a second insertion point the file plan does not mention.
4. **`device_id` must be sourced from USERROW.** It is a file-scope `static` at
   `encoder/src/main.cpp:80`; `ker_init()` cannot write it from another translation unit,
   so `setup()` needs an assignment, not just a call.

Also: the four `ker_*.c` files are C, `main.cpp` is C++ — the "three `#include`s" need
`extern "C"` guards.

### M16 — §6.4's requirement-3 compliance evidence is measured at 3 harmonics and claimed for 5. (CONFIRMED from the spec's own tables)

§6.4 headline: *"Worst case **0.00146°** against a 0.005° budget. Requirement 3 is met with
3.4× margin."*

Its own table column is *"Coefficients (**H1/H2/H3**)"*, all four cases are 3-harmonic, and
the section closes: *"The sweep is to be re-run at `N_HARM = 5` once the layout is
implemented."*

D4 freezes the layout at **five** slots and §5.1 budgets 15 µs for *"5-harmonic fixed-point
compensation"*. The fixed-point error accumulates per harmonic — §6.4's own kernel is
`Δ += (A_k · sin_q15(a16)) >> 15`, i.e. one truncation per harmonic, each up to 1 LSB
(0.000172°). Five harmonics is 5 truncations, not 3; at 5/3 scaling the worst case is
~0.0024°, and the asymmetric rounding below makes it worse.

Separately: `>> 15` on a negative `int32` rounds toward −∞ while a positive value truncates
toward 0. The correction is signed (`A_k` is `i16`, §4), so positive and negative
corrections carry **opposite-direction** 1-LSB biases — a systematic discontinuity at every
sign change of Δ, which is exactly where the compensated curve should be smoothest. The
spec's error model treats truncation as symmetric noise.

Requirement 3 is presented as met with 3.4× margin; the evidence supports a smaller,
unquantified margin at the frozen configuration.

### M17 — §6.3's prose contradicts its own table for the case that matters. (CONFIRMED)

§6.3: *"Five harmonics puts typical and large parts at or below the 0.0055° quantisation
floor."*

Its table, row 4 (raw error 3.42° — the "large part"), H1–5 column: **0.01424°**. That is
**2.6× above** the 0.0055° floor, and it is the only row in the table that could be called
a large part.

This matters because D4 freezes the layout at five slots and a sixth would require a new
`LAYOUT_VER` (§4 word 1). The spec's own data says a 3.42° part cannot be brought to the
quantisation floor with the frozen layout, while the prose says it can.

### M18 — §3.7's classification of health bits contradicts their definitions. (CONFIRMED)

§3.7: *"Bits 0, 1, 2, 6 are steady state; **the rest are latched until `CLR_ERRCNT`**."*

- Bit 7 `ANGLE_STALE` is defined as *"**most recent** read failed; serving the previous
  valid value"* — an instantaneous status, not a latch.
- Bit 8 `FACTORY_MODE` is defined as *"factory mode **currently** active"* — live state by
  definition.

Under the classification sentence, `CLR_ERRCNT` clears `FACTORY_MODE` **while factory mode
is still active**, so `GET_HEALTH` then reports the device as locked when it is not, and
`ANGLE_STALE` stops tracking the most recent read. `CLR_ERRCNT`'s gate is `idle`, not
`factory`, so any host can do this without unlocking.

### M19 — `GET_TRIM` returns "5 registers" that are not 5 registers. (CONFIRMED)

§3.6: `0x13 GET_TRIM | 0..4 | "read-only laser-trimmed regs (ANG_BASE, OFFX, OFFY, SYNCH,
ORTHO)"`.

§2.4 names the same set as *"`MOD_3.ANG_BASE`, `OFFX`, `OFFY`, `SYNCH`, `IFAB.ORTHO`"* —
**ANG_BASE is a field of MOD_3 and ORTHO is a field of IFAB**, not registers. So index 0
and index 4 are ambiguous: whole register, or masked/shifted field? The station's
record-keeping (§2.4: *"They are read back and recorded"*) and the firmware must agree, and
nothing says which. Index 0 and 4 are the two most likely to diverge because they are the
two that require a decision.

### M20 — The frame has no error detection, and the per-subcommand magics that substitute for it are inconsistent. (CONFIRMED)

The 4-byte frame carries no checksum (§1.6 notes upstream's `crc8_0x07` at
`encoder/src/main.cpp:92` is dead code). The only integrity check anywhere in CMD=3 is the
USERROW CRC-16 checked at `COMMIT_CAL`.

The SUB field is 5 bits with no Hamming distance requirement, and several dangerous
transitions are one bit apart:
- `0x1B STAGE_DATA` (`11011`) → `0x1F RESET` (`11111`): 1 bit
- `0x1D SET_ID` (`11101`) → `0x1F RESET` (`11111`): 1 bit
- `0x1A STAGE_ADDR` (`11010`) → `0x1B STAGE_DATA` (`11011`): 1 bit

The magic ARGs happen to catch the first two. The third is not caught: `STAGE_ADDR(5)`
corrupted to `STAGE_DATA(5)` writes the literal value 5 into the buffer and advances the
index, and is only caught downstream by the commit CRC — which means a corrupted upload
must be fully retransmitted with no indication of where it went wrong. And `STAGE_ADDR`
has **no magic at all**, unlike every other factory subcommand.

The spec never states that magic values exist for bit-error rejection (§3.4 mentions it
only for `LATCH_SYNC`'s broadcast-vs-reply aliasing), never states a Hamming-distance
requirement on SUB codes, and gives no guidance on which subcommands need magics and why.
For a frozen interface on a 2 Mbps differential bus with no CRC, that is a design property
that must be stated or the next subcommand added will not have one.

### M21 — Broadcast NAK behaviour is undefined, and the wrong choice is a 16-way bus collision. (CONFIRMED)

§3.4's table says an ID=0 CMD=3 frame is acted on *"only for `SUB = LATCH_SYNC` with the
correct magic"*. Undefined:

- **Broadcast `LATCH_SYNC` with the wrong magic.** NAK, or ignore? §3.5 says a rejected
  request produces a NAK *"when the bus is idle, so replying is safe"* — and the bus *is*
  idle (the gate passed). Under §3.5's plain reading, **all 16 modules NAK simultaneously**.
  That is 16 RS-485 drivers contending, which §3.3's ID=0 protection does nothing about.
- **Broadcast of any other SUB.** Same question, same answer, same collision.
- **Addressed `LATCH_SYNC` (ID 1–31, SUB=0x14).** §3.6's gate column says only `idle` —
  unlike `UNLOCK_1`, it carries no "broadcast only" or "addressed only" note. Does it
  latch? Does it reply? §3.8 describes only the broadcast form.

The spec needs one normative sentence — "broadcast requests never generate a reply of any
kind, including NAK" — and does not have it.

### M22 — §3.4's "true by construction" claim is half right; the part it credits is the part that does nothing. (CONFIRMED)

§3.4: *"`LATCH_SYNC` is the only subcommand that never replies, so **no reply frame can
ever carry `SUB = 0x14`**. This is true by construction, not by convention, and the 16-bit
magic in `ARG` makes accidental match impossible regardless."*

The first half holds *given* §3.5 (replies echo the request SUB; NAKs use SUB=0x00). Fine.

The second half is false as stated. The magic does **not** make accidental match impossible
"regardless" — it is a check on `ARG`, and `ARG`/`DATA` occupy the same 16 bits in a reply.
`GET_ANGLE_RAW`, `GET_CAL_WORD`, `GET_STAT` and others can trivially return DATA = 0x1A7C.
The **only** thing preventing a reply from being read as a broadcast latch is the SUB
field. "Regardless" invites an implementer to treat the two checks as independent
defence-in-depth when there is exactly one line of defence.

The residual case the magic genuinely does cover — a garbled frame from a two-driver
collision decoding to ID=0/CMD=3/SUB=0x14 — is the one §3.4 does not mention.

### M23 — §3.4's residual exposure is closed by a Python convention, contradicting §3.3's own boast. (CONFIRMED)

§3.3: *"Safety stops depending on timing and starts depending on addressing, **which cannot
drift**."*

§3.4: *"**Residual exposure.** Addressed requests with ID 1–16 remain visible to the M5
... the host library closes it anyway: **the PC tool must listen and confirm 100 ms of bus
silence before transmitting any CMD=3 frame**."*

Half the protection is in firmware (replies at ID=0) and half is a behavioural requirement
on a separate deliverable written in a different language by a different process. That
half drifts by definition — a host that skips the listen step, or a second host on the bus
(§none: two-host operation is never discussed, and there is no arbitration, no collision
detection and no requirement that the host check for framing errors), reintroduces the
exposure with nothing in the firmware to stop it.

This is the asymmetry that should be stated plainly: replies are safe by construction,
requests are safe by convention.

---

## MINOR

1. **§1.3 "the only transmit in the entire M5 firmware"** — CONFIRMED for the two files in
   scope, but `rs485nexus` is a non-`static` global (`M5/src/main.cpp:35`), so any other
   translation unit can `extern` it and transmit. The two cited files do not establish the
   claim, and the entire safety argument rests on it.

2. **§1.3 "the M5 emits exactly one frame per millisecond"** — `M5/src/main.cpp:145` is
   `last_request_time += 1`, not `= now`. After any stall (the NVS commit at `:245-247`
   runs *inside* `acquisitionTask`) the task accumulates debt and catches up at one frame
   per loop iteration. It never bursts (the `vTaskDelay(pdMS_TO_TICKS(1))` at `:255` rate-
   limits it), but the bus goes silent for the duration of the stall. The spec performs no
   worst-case analysis of M5 bus silence anywhere, and that bound is what `T_IDLE_GATE`
   should have been derived from (see B1).

3. **§4 vs §3.6 field-order inversion.** USERROW word 1 puts DEVICE_ID in `[15:8]` and
   LAYOUT_VER in `[7:0]`. `GET_DEVICE_ID` (0x04) puts the effective ID in `[7:0]`;
   `GET_CAL_STATUS` (0x10) puts the layout version in `[15:8]`. Both fields are in the
   opposite half in the protocol from where they sit in the storage layout. Two
   independent implementations will get one of them backwards.

4. **§4.1 never says when `CAL_VER_UNSUPPORTED` (health bit 1) is set.** The else branch
   lists `CAL_INVALID` and `ID_FROM_BUILD` only.

5. **§4.1 "`ID_FROM_BUILD` set if applicable"** — in the else branch the ID *always* comes
   from the build default, so it is always applicable, and there is no path where bit 6 is
   set without bit 0. The bit is either redundant or the "if applicable" hides an
   unstated case.

6. **§3.6 `UNLOCK_2 ARG = 0xA5E8 ^ (id * 0x0101)`** — `id` is undefined in the table row;
   only §3.9 says `device_id`. Also: nothing bounds how long the post-`UNLOCK_1` armed
   state lasts (the 5 s timer is for factory mode, which has not been entered yet), and
   there is no retry lockout.

7. **No reason code fits a sequence violation.** `UNLOCK_2` without `UNLOCK_1`:
   `NOT_UNLOCKED` (0x02, defined as "factory mode required and not active") or `BAD_ARG`
   (0x03)? Both are wrong; neither is specified.

8. **`SUB = 0x00` as a request** is undefined (0x00 is marked "reply-only"). Presumably
   `UNSUPPORTED`, producing a NAK whose SUB is also 0x00.

9. **Non-zero ARG on zero-ARG subcommands** (PING, GET_PROTO_VER, GET_HEALTH, …) — ignored
   or `BAD_ARG`? Matters for forward compatibility.

10. **§3.6 `GET_FW_VER` index 2 = "build id"** in 16 bits. A git hash does not fit;
    the encoding is undefined.

11. **`RESET` has no post-conditions.** After reboot `t_last_chain` re-initialises to the
    boot instant (§3.2), so the gate is closed for another 100 ms. The station must wait
    boot-time + 100 ms before the next frame, and the spec says neither number.

12. **`STAT_ERR` names two different things.** §2.2 defines it as safety-word bit 14;
    §3.7 defines it as health bit 4. Same name, different width, different register.

13. **§5.1's read-step table omits the STAT read.** §3.6 (`GET_STAT`) and §3.7
    (`STAT_ERR`, `SENSOR_CFG_FAIL`) require STAT (0x00) to be read, which is a *separate*
    SSC transaction (command word + data word + safety word ≈ 48 clocks), not covered by
    the table's "16 extra SSC clocks for the safety word". Whether `GET_STAT`/`GET_DMAG`/
    `GET_TEMP` read on demand or from a cache is also inconsistent — §3.6 says "**last**
    TLE5012B STAT" for 0x06 but plain "D_MAG, raw" / "FSYNC, raw" for 0x07/0x08.

14. **§5.1's 15 µs estimate for 5-harmonic compensation** is ~60 cycles per harmonic at
    20 MHz, which must cover a 24-bit mask+multiply, a table index, a linear interpolation
    multiply and a 32-bit multiply-shift. Optimistic by roughly 2–3×. It sits off the
    critical path so the chain budget survives, but §7's flash/RAM estimate derives from
    the same optimism. (SUSPECTED — no measurement in scope.)

15. **§6.4's 130-byte sine table** must be `PROGMEM`/`__flash` on AVR or it is copied to
    RAM at startup. §7 counts it as flash only; the spec never mentions the qualifier.
    RAM headroom is 1869 bytes so the consequence is benign, but the accounting is wrong.

16. **§4's "USERROW is not erased by a UPDI chip erase"** is stated unconditionally. On
    tinyAVR 1-series this holds for an *unlocked* device; a chip erase of a **locked**
    device erases everything including USERROW. The whole choice of USERROW over EEPROM
    rests on this, and the caveat is not stated. (SUSPECTED — datasheet claim, outside
    scope.) The `SYSCFG0 = 0xC4` / `EESAVE = 0` claim is also not verifiable from the
    files in scope (it lives in `platformio.ini`) — the bit arithmetic is right (0xC4 bit
    0 = 0) but the value is unverified.

17. **§3.9's "without ever leaving a half-written page in flash"** is true of host-side
    truncation only. A power loss during the USERROW burn does leave a half-written page;
    it fails the CRC at next boot and the module falls back to build ID 31 — i.e. a
    previously provisioned joint silently becomes a missing joint on the arm. Acceptable
    failure mode, but unstated.

18. **§3.2 does not say that CMD=3 frames must not update `t_last_chain`.** The wording
    excludes them, but an implementer who timestamps every received frame produces a
    protocol that deadlocks itself (the first request closes the gate for 100 ms). Worth
    an explicit negative.

19. **§9.1 has no decision row** for `T_IDLE_GATE = 100 ms` as a standalone value, the
    CMD=3 payload split (SUB 5 / ARG 16), the 5 s factory timeout, or the USERROW layout
    freeze — all of which are frozen by this document.

20. **§1.1 "MSB of byte 0 is the only framing marker"** — the receiver also requires
    MSB=0 on bytes 1–3 (`encoder/src/main.cpp:182, 190, 198`), and rejects the frame
    otherwise. Pedantic, but the framing rule as written is weaker than the code.

---

## Framing and encoding (§3.1) — verified clean

Checked as requested; no defect found, stated here only so the gap is not read as an
omission.

With `P[20:16] = SUB`, `P[15:0] = ARG`:
- `d0 = P & 0x7F` = ARG[6:0], max 0x7F
- `d1 = (P >> 7) & 0x7F` = ARG[13:7], max 0x7F
- `d2 = ((SUB & 0x1F) << 2) | ((ARG >> 14) & 0x03)` = (0x1F << 2) | 3 = **0x7F** max

`d2` is identical to `(P >> 14) & 0x7F`, so it round-trips through
`encoder/src/main.cpp:203` `data = d0 | (d1 << 7) | (d2 << 14)` exactly. No legal
SUB/ARG combination sets the MSB of any payload byte. The header is
`0x80 | (ID << 2) | 3`, always MSB-set, never colliding with a payload byte.

The only nit: `P` is described positionally but never given as an expression, and `d0`/`d1`
are written in terms of `P` while `d2` is written in terms of `SUB`/`ARG`. Cosmetic.

---

## Compatibility gaps (task item 5) — summary

Things the spec claims need no M5-side action that in practice do:

- **M12** — persisted jig zero offsets are invalidated by the compensation change; the arm
  must be re-zeroed after the encoder firmware upgrade. Not mentioned anywhere.
- **M13** — a mixed calibrated/uncalibrated chain is undetectable from the M5 or the PC,
  because `CAL_INVALID` is only reachable via CMD=3 and CMD=3 is only reachable with the
  M5 off.
- **M14** — reading any of §3.7's diagnostics requires silencing the bus, and
  `M5/src/main.cpp:144-147` transmits unconditionally (outside the `AppMode` check), so
  STANDBY does not suffice. Requires the ability to isolate RS-485 without cutting module
  power — an unstated hardware requirement.
- **M11** — the zeroing workflow reads `raw_deg` (`M5/src/main.cpp:238`), which bypasses
  jump detection entirely, so a stray CMD=3 frame during a `ZERO_ALL` is written to NVS
  permanently.

`ENCODER_CONFIG` itself needs no edit — confirmed, `invert`/`mech_joint_offset` compose
correctly with a transfer-function change applied encoder-side.

---

## What would have to change for a REVISE

1. B1–B6 resolved: gate derivation against measured M5 startup silence; `SET_ID`
   precondition on invalid USERROW; DEVICE_ID range validation in both `COMMIT_CAL` and
   §4.1; the three missing payload tables; the `any` gate value defined; the one-virgin-
   module-at-a-time constraint stated or the unlock scheme fixed.
2. M1, M7, M8, M9, M21 — the state machine gaps. These are the ones that will surface as
   "the station hangs and we don't know why" during bring-up.
3. M4 and M3 — two defects that will produce confidently wrong numbers rather than errors.
4. M15 — the file plan must be reconciled with §2.2/§2.4, or the minimal-diff constraint
   must be relaxed explicitly.
5. M16/M17 — re-run the sweep at N_HARM=5 before claiming requirement 3 is met, and fix
   §6.3's prose to match its table.
