# Response to the spec v3 reviews

Reviews: `2026-09-19-spec-v3-protocol-review.md` (0 B / 7 M / 16 m) and
`2026-09-19-spec-v3-numerics-review.md` (1 B / 2 M / 11 m). Both: REVISE.
Resolved in `../protocol-spec.md` **v4**; § references are to v4.

Status: **fixed**, **accepted** (documented, not changed), **disputed** (checked, not upheld, with evidence).

## Numerics review

| # | Finding | Status | Resolution |
|---|---|---|---|
| B-1 | §7.2 "no constant term" fails with a mounting offset | fixed | Reproduced (`station_fit.py`: 0.046° at 1°, rejection at 180°). New procedure: circular-mean removal, constant column fitted and discarded; ≈ 0.006° at every offset, verified through `ker_compensate()` (§7.2, D13). |
| M-1 | 0.002341° is not the worst case | fixed | Reproduced the constructed case: 0.002587°, ceiling 0.002605°, margin 1.93×. Per-N table in §7.5. |
| M-2 | Differential test skips N = 0, 1, 2, 4, 5 | fixed | 21 sets covering N = 0–6. Reviewer's mutant B (`(uint32_t)(raw15 << 6)`) added as a second negative control; now caught by the N = 0 set (§11.2). |
| m1 | SSC ≈ 48 µs not 35; read step ≈ 112 µs | fixed | §8.3. |
| m2 | Worst case 1056 cycles | fixed | Reproduced; 1058 after adding the `n` guard (§8.3). |
| m3 | AVRxt reasoning wrong (no `lds` in the loop; flash table reads) | fixed | §8.3. |
| m4 | `0x1AD` unsigned → 209 °C | fixed | §2.6. |
| m5 | 732 B code size does not reproduce | fixed | Replaced by a linked measurement: 650 B total including libgcc and table (§10). |
| m6 | No script for uncalibrated = upstream, or CRC-8 cycles | fixed | `uncalibrated_equals_upstream.c`, `crc8_cycles.c` added to the evidence. |
| m7 | `raw15 << 1` signed overflow with 16-bit `int` | **disputed** | With 16-bit `int`, `uint16_t` cannot be represented by `int` and so promotes to `unsigned int` (C11 6.3.1.1p2); the shift is unsigned and well defined. Checked with `_Static_assert(_Generic((uint16_t)0 << 1, unsigned int: 1, …))`, which compiles for `-mmcu=attiny1616`. On a 32-bit host it promotes to `int` and `0x7FFF << 1` cannot overflow. |
| m8 | `gen_sinq.py` assumes non-negative steps | fixed | Asserted in the generator. |
| m9 | "typical parts reach the floor" overstated; §7.5 vs O1 disagree | fixed | §7.6 wording; O1 and §7.5 both say ≈ 0.04°. |
| m10 | Bin centre vs bin floor | accepted | Stated in §7.6 (constant, removed with the mean, ≤ 3 %). |
| m11 | `ker_compensate()` does not bound `n` | fixed | `n > 6` treated as uncalibrated (§7.4 item 5). |

## Protocol review

### Major

| # | Finding | Status | Resolution |
|---|---|---|---|
| MJ1 | Snapshot rule ambiguous; breaks latch check or tears raw15/sequence | fixed | Per-subcommand records captured at index 0; index > 0 first → NAK SEQUENCE; GET_ANGLE_RAW record includes validity (index 4); GET_ERRCNT captures all counters together; GET_CAL_WORD explicitly has no record (§4.3 r6, §4.7). |
| MJ2 | Unlock "next frame" vs "any other frame"; unlock while unlocked; retry after lost reply | fixed | "Next CMD=3 request whose header ID equals `device_id`"; replies are ID 0 and never count, so self-echo and twins' replies are harmless. UNLOCK_1 in factory mode → SEQUENCE; UNLOCK_2 in factory mode is idempotent (§4.9). |
| MJ3 | Duplicate detection unsound; one-module rule unstated | fixed | Stated as a residual risk (§3.3); normative single-module station rule (§3.4, D14). |
| MJ4 | Write-failure path undefined | fixed | Keep running previous identity and coefficients, stay in factory mode with buffer intact, retryable; GET_CAL_STATUS bit 7 shows the divergence (§4.9). |
| MJ5 | Failed config lock not retried and does not affect reads; start-up value; SRST clear-on-read | fixed | Start-up sequence completes before the first frame is answered; lock retried every 16th read; compensation suspended while unlocked; reset detection uses `S_RST` only; STAT bits' clear-on-read is a pre-condition for the mask (§2.3, §6.2, O2). |
| MJ6 | SET_ID overwrites any invalid page | fixed | Identity page only over a virgin page; otherwise NAK BAD_PAGE (§4.9, D15). |
| MJ7 | No latency, timeouts, one-outstanding rule | fixed | §4.3 r8–r10; bench item §8.4.8. |

### Minor

| # | Status | Resolution |
|---|---|---|
| m1 `prev_id` "unmasked" | fixed | §5.2 now states the masked computation that produces the hazard. |
| m2 209 °C | fixed | §2.6. |
| m3 "fully suppressed" only for ≥ 30° | fixed | §1.6. |
| m4 C3 overstated; wrong interval measured | fixed | "since its last reset"; residual in §3.3; §8.4.6 measures module reset → first CMD=2. |
| m5 bit error to CMD=2 latches until power cycle | fixed | Stated in C3. |
| m6 C3 vs C4 on CMD=1 | fixed | C3 and C4 reworded consistently. |
| m7 LOCK has no magic; STAGE_DATA aliasing | fixed | LOCK `0x10CC`; aliasing documented as fail-safe in C6. |
| m8 NAK precedence | fixed | §4.3 r11; §5.2 check order. |
| m9 rule 4 vs RESET | fixed | §4.3 r4; RESET wrong magic → BAD_ARG. |
| m10 "accepted" undefined | fixed | §4.3 r7. |
| m11 hook misses own-ID CMD=2/3 frames | fixed | Single `ker_on_frame()` after the dispatch, for every frame (§11.1). |
| m12 16-bit digest collisions | fixed | Stated (§3.3); moot under §3.4. |
| m13 GET_ANGLE_RAW under-defined | fixed | Record fields defined; GET_STAT/GET_SAFETY return the most recent transaction whether or not it passed (§4.7, §4.6). |
| m14 build-id encoding | fixed | First 4 hex digits of the commit hash; index 3 dirty flag. |
| m15 build default not in the file plan | fixed | `platformio.ini` and the `main.cpp` fallback listed (§5.4, §11.1). |
| m16 USERROW writes with BOD off | fixed | VDD check before programming; threshold is O6 (§5.5). |

### "What's missing" section

| Item | Resolution |
|---|---|
| one-unprovisioned-module rule | §3.4 |
| host retry / idempotency | §4.3 r10 |
| fit acceptance criterion | §7.2 step 6–7; defaults pending O1/O3 |
| value before first valid read | §6.2 start-up |
| what GET_ERRCNT "dropped" counts | §4.7, index 5 |
| `arm_seen` has no software clear | C3 |

### Out-of-scope items the reviewer could not verify

- `USBStream` in `USE_USB` builds: checked; it writes only to the USB vendor interface (§1.3).
- RS-485 receiver enabled during transmit: no longer matters — the v4 unlock rule counts only requests
  addressed to the module, and a module's own replies are ID 0.
- TLE5012B start-up time, SRST semantics, USERROW programming time: O2.
