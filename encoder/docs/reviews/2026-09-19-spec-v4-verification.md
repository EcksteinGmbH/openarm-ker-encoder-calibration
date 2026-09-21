# Independent verification: `encoder/docs/protocol-spec.md` v4

Verifier: critic. This is an independent check. I did not rely on the response document: every closure below
was checked against the v4 text, the evidence files or the upstream source.
Scratch directory (all builds, scripts and outputs): `/tmp/claude-1000/-home-dev-workspace/38490050-73d7-4d9c-8938-ba86d5c14f65/scratchpad/v4ver/`
(`attack.py`, `scen1.py`, `scen2.py`, `scen3.py`, `m7.c`, `ub.c`, `f_with.c`/`f_without.c`).

**VERDICT: REVISE (narrow).**
- There are no blockers.
- The v3 blocker (B-1) is genuinely fixed. It reproduces, and it holds at every offset I tried, including ±180°.
- 8 of the 10 v3 MAJOR findings are closed. MJ4 is partial. Numerics M-2 is closed in substance: every N_HARM from 0 to 6 is covered, but the seam-negative set was never written down as a requirement.
- One new MAJOR remains. The §7.2 step-6 acceptance criterion, which the response lists as closing the v3 "fit acceptance criterion" gap, does not do its job at its own defaults:
  - With the sparse sampling it allows, it accepts parts whose true error is up to 1.4× `R_MAX`.
  - With the dense sampling the station will more likely use, and ordinary noise, it rejects good parts.
  - The "golden reference" `station_fit.py` does not implement the criterion at all.
- Everything else is MINOR.

Mode: I started in THOROUGH mode and did not escalate to ADVERSARIAL. I found one MAJOR, no critical findings, and no systemic pattern. The v4 edits are careful. Most defects are residual ambiguity in rare paths.

---

## 0. Reproduction (all commands run by me; outputs compared with `evidence/v3-reference/results/`)

| Item | Command (abridged) | Result |
|---|---|---|
| §7.2 station procedure | `gcc -O2 -shared -fPIC -o $S/libref.so ref_comp.c`; `.venv/bin/python station_fit.py $S/libref.so` | **byte-identical** to `results/station_fit.txt` |
| §11.2 AVR differential | `diff_main.c` host vs avr-gcc `-mmcu=atmega328p -Os` in simavr | `AVR == host`, 21/21 sets |
| §11.2 mutants | README loop | int16: invisible on host; differs on AVR sets 0–13, 15–20 (**20/21**). uncal: invisible on host; differs **only on set 14** (N = 0). Matches §11.2. |
| §7.5 constructed worst case | `../v3-review-scripts/construct.c` | identical N = 1…6 lines (0.002587° at N = 6) |
| §8.3 cycles | `cyc_worst.c` in simavr | identical: 156/363/502/641/780/919/1058 |
| §8.3 CRC-8 | `crc8_cycles.c` in simavr | `b592 t123 e1` (123 cycles; table matches bitwise) |
| §7.1 uncalibrated = upstream | `uncalibrated_equals_upstream.c` | `0 mismatches` |
| Sine tables | `gen_sinq.py` | all four `.inc` files byte-identical. The 6-bit table fails the `_Static_assert` under avr-gcc `-mmcu=attiny1616`, as claimed. |
| UBSan | `ub.c` over 65536 codes at ±32767/−32768 amplitudes and n = 7 | clean |
| §10 flash cost | no generator is shipped. My own harness (`f_with.c`/`f_without.c`, `-Os --gc-sections`, attiny1616) | delta = 680 B. That is consistent with the claimed 650 B within harness overhead, but it is **not reproducible from the evidence** (see m-N6). |

---

## 1. Closure audit

### Numerics review (v3)

| # | Status | v4 § | Verification notes |
|---|---|---|---|
| B-1 | **CLOSED** | §7.2 steps 3–4; D13; §11.2 item 4 | Reproduced byte-identically. My own out-of-sample check, a dense 65536-point true grid through all 32768 codes of `ker_compensate()`, gives 0.00632° at 0°, 0.00627° at 179.9°, 0.00632° at 180.0°, 0.00647° at −179.99° and 0.00660° at 180.004° (`scen1.py`). Offset handling is sound. The acceptance step that follows it is not; see MAJOR-1. |
| M-1 | **CLOSED** | §7.5 | 0.002587°, 1.93× margin, per-N table: reproduced. Nit: the ceiling 0.002605° comes from `worstterm.c`, which Appendix A does not list. `results/accuracy_host.txt` still prints the refuted "adversarial worst … margin 2.1x" line (m-N5). |
| M-2 | **CLOSED** (fix partly unstated) | §11.2 items 2–3 | Sets 14–20 cover N = 0…6. Mutant B is caught on set 14 only. The reviewer also asked that "at least one set with negative `u + Δ` at the seam" be *stated* in item 2. It is not stated. It is covered incidentally, by sets 1–3 at r = 0. |
| m1 | CLOSED | §8.3 | 48 + 4 × 224 + 8 = 952 cy ≈ 48 µs at 20 MHz; the total is ≈ 112 µs. Housekeeping moved from +27 µs to "+≈ 35 µs" with no derivation (m-N8). |
| m2 | CLOSED | §8.3 | 1058 cycles reproduced, including the `n` guard. |
| m3 | CLOSED | §8.3 | The reasoning is now correct: push/call are faster, the 24 table reads come from mapped flash, net ≈ −7 cycles. |
| m4 | CLOSED | §2.6 | 209 °C. |
| m5 | **PARTIAL** | §10 | 732 B is gone. The new 650 B cannot be reproduced from the evidence: there is no source and no README command (m-N6). |
| m6 | CLOSED | Appendix A | Both generators exist and reproduce. |
| m7 | **Dispute UPHELD** | — | `m7.c`: `_Static_assert(_Generic((uint16_t)0 << 1, unsigned int: 1, default: 0))` together with `sizeof(int)==2` compiles with avr-gcc for `-mmcu=attiny1616`. On AVR, `uint16_t` is `unsigned int`, so there is no promotion to signed `int` and no UB. On the host, `0x7FFF << 1` fits in `int`. The original finding was wrong. |
| m8 | CLOSED | `gen_sinq.py:15` | Assert present; tables regenerate byte-identically. |
| m9 | CLOSED | §7.5, §7.6, O1 | "≈ 0.04°" is used consistently; the worst-moderate row 0.03872 is now in the table. |
| m10 | CLOSED (accepted) | §7.6 last bullet | |
| m11 | CLOSED | §7.4 item 5; `ref_comp.c:54` | |
| Missing: offset / sparse-station simulation | **PARTIAL** | §7.2 table | The offset sweep is present. The sparse station is still not simulated: §7.6 figures are for 131072 dense positions, while §7.2 allows 64. My runs: typical part, 64 uniform positions, true error up to 0.011° against ≈ 0.007° dense (`scen3.py`). |
| Missing: worst-case statements | CLOSED | §7.5, §8.3 | |
| Missing: AVRxt flash-read timing | CLOSED (deferred to bench) | §8.3, §8.4 item 5 | |

### Protocol review (v3)

| # | Status | v4 § | Verification notes |
|---|---|---|---|
| MJ1 | **CLOSED** | §4.3 r6, §4.7, §4.8, §7.2 step 1 | Records are per-SUB, captured at index 0, and independent. idx > 0 first gives SEQUENCE. The GET_ANGLE_RAW record carries validity (idx 4). §4.8 reads 0 then 3. §7.2 reads 0 then 2/3/4. GET_CAL_WORD has no record. All consistent (§2 below). |
| MJ2 | **CLOSED** (minor residue) | §4.9 | "Next CMD=3 request whose header ID equals `device_id`"; ID-0 replies do not count; factory-mode rows for UNLOCK_1 and UNLOCK_2 exist. Residue: whether a CMD=1 to another ID, or a repeated UNLOCK_1 while armed, disarms or re-arms is unstated (m-N10). |
| MJ3 | **CLOSED** | §3.3, §3.4, D14 | |
| MJ4 | **PARTIAL** | §4.9 | The COMMIT_CAL failure path is fully defined. Still open from MJ4's own bullets: (a) where SET_ID builds its page, and therefore what a SET_ID retry sees; (b) whether CAL_INVALID reflects the stored page or the running state after a failed write. Point (b) now contradicts §7.1 and GET_HEALTH bit 0 (m-N1, m-N2). |
| MJ5 | **CLOSED** (minor residue) | §2.3, §6.2, O2 | Lock retry every 16th read; compensation suspended; start-up specified; reset detection uses `S_RST` only; clear-on-read added to O2. Residue: m-N3 (the config lock's own safety-word "valid" is undefined at power-on), m-N4 (start-up claims). |
| MJ6 | **CLOSED** | §4.9 SET_ID table, D15 | Except the post-write-failure case (m-N1). |
| MJ7 | **CLOSED** (minor residue) | §4.3 r8–r10, §8.4 item 8 | Residue: m-N9 (host timeouts and adapter latency; rule 10's "new ID if the commit may have changed it"). |
| m1 | CLOSED | §5.2 | Verified against `encoder/src/main.cpp:120,336`. |
| m2 | CLOSED | §2.6 | |
| m3 | CLOSED | §1.6 | Verified against `M5/src/main.cpp:201-202,215-218`. |
| m4 | CLOSED | C3, §3.3, §8.4 item 6 | |
| m5 | CLOSED | C3 bullet 2 | |
| m6 | CLOSED | C3, C4 | C4 now introduces a new, different conflict (m-N7). |
| m7 | CLOSED | §4.6 LOCK `0x10CC`; C6 | Cosmetic: C6 says LOCK "needs factory mode, which it already has", but LOCK is gate R; it also names LOCK as a one-bit alias, but STAGE_DATA `11011` → LOCK `11110` is a two-bit flip. Harmless. |
| m8 | CLOSED | §4.3 r11, §5.2 | All five v3 examples now have one answer: BAD_INDEX; BAD_INDEX; NOT_ELIGIBLE; SEQUENCE; CRC_FAIL. |
| m9 | CLOSED | §4.3 r4, §4.6 RESET | |
| m10 | CLOSED | §4.3 r7 | |
| m11 | CLOSED | §11.1 | A single `ker_on_frame()` after the dispatch. Verified that `encoder/src/main.cpp:323-333` ignores CMD=2/3 frames carrying the module's own ID. |
| m12 | CLOSED | §3.3 | |
| m13 | CLOSED | §4.6, §4.7 | |
| m14 | CLOSED | §4.6 GET_FW_VER | |
| m15 | CLOSED | §5.4, §11.1 | `encoder/platformio.ini:46` = `-DDEVICE_ID=3`; `encoder/src/main.cpp:38` = default 1. Both verified. |
| m16 | CLOSED | §5.5, O6 | |
| Missing: one-module rule | CLOSED | §3.4 | |
| Missing: retry / idempotency | CLOSED | §4.3 r10 | Except SET_ID after WRITE_FAIL (m-N1). |
| Missing: fit acceptance criterion | **NOT EFFECTIVE** | §7.2 steps 6–7 | Present, but see MAJOR-1. |
| Missing: value before first valid read | CLOSED | §6.2 | Sends 0 with NO_VALID_ANGLE. The claim about how the M5 reacts is wrong (m-N4). |
| Missing: GET_ERRCNT "dropped" | CLOSED | §4.7 idx 5 | |
| Missing: `arm_seen` has no software clear | CLOSED | C3 | |
| Out of scope: USBStream | CLOSED | §1.3 | `M5/src/USBStream.cpp` contains no `Serial` reference (`grep -c Serial` = 0); `:193` and `:275` are `_vendor.write`. |

---

## 2. Regression hunt (v4 edits)

**§4.3 r6–r11 vs §4.5, §4.6, §4.7, §4.9. Consistent.**
- Indices match between §4.6 and §4.7: ANGLE_RAW 0–4, ANGLE_COMP 0–1, LATCHED 0–3, ERRCNT 0–7.
- SEQUENCE covers three cases in §4.5, and r11 places it after the gates and before magic/index.
- SENSOR_FAIL is reserved, which fits GET_TRIM being served from cache (so the 1 ms latency of r9 is achievable for every GET).
- BAD_ARG is now "wrong magic or tag" only, which removes the old overlap with BAD_INDEX.
- One oddity, which is defined and not a defect: an out-of-range index before any index-0 capture returns SEQUENCE rather than BAD_INDEX.

**Record rule vs §4.8 and §7.2 step 1. Consistent.**
- Both read index 0 first.
- The latch check reads idx 0 (capture) then idx 3, so a new LATCH_SYNC in between cannot tear the pair.

**§4.9 write failure vs §5.3, GET_CAL_STATUS and the staging table.**
- These are consistent for COMMIT_CAL: factory mode is kept, the buffer is intact, and bits 5 and 7 give the running/stored split.
- They are not consistent with §7.1 and GET_HEALTH bit 0 (m-N2), and they are undefined for SET_ID (m-N1).

**§6.2 suspension vs §7.1, GET_HEALTH bit 2, GET_ANGLE_RAW idx 4 bit 1 and GET_CAL_STATUS bit 5. Consistent.** All four use the §7.1 definition. Residue: m-N3, and the "far below 30°" claim (m-N11).

**§6.2 start-up vs the M5 cascade. Not honest enough; see m-N4.**
- Upstream `setup()` (`encoder/src/main.cpp:297-315`) is pin and UART initialisation only: microseconds on top of the 8 ms SUT.
- v4 adds USERROW validation, `t_pon` (❓), the config lock, and up to 10 reads.
- While a module does not answer, every downstream module is starved. For a reset during operation, the M5 then streams frozen angles for all downstream joints as *valid*, because `_valid[]` is never cleared (`M5/src/RSNexus.cpp:87,116-118`; the only clear is at construction, `:23`).
- Upstream has the same failure mode, over a shorter window. "Exactly as during upstream's own start-up" is therefore true in kind but not in duration. The downstream consequence is not stated, and §8.4 item 7 has no pass threshold.

**§3.2 C4 vs §7.2 and §11.2.** Nothing in provisioning or calibration needs CMD=1 or CMD=2: §7.2 uses GET_ANGLE_RAW and GET_ANGLE_COMP only. C4 bullet 2, however, conflicts with its own bullet 3 (m-N7).

**Stale v3 numbers.** Searched for `0.002341`, `1047`, `1056`, `≈ 100 µs`, `35 µs` (SSC), `732`, `2.1×` and `178`: none remain in the spec. Remaining stale items:
- The `ref_comp.c:41` comment "Spec v3 sec 6.2".
- `results/accuracy_host.txt` still printing "0.002341 … margin 2.1x".
- The §7.4 item 3 table address `0x82FE`, which depends on the image: my image puts `ker_sinq` at `0x8274`. The claim that matters is that the table sits in mapped flash above `0x8000`, and that holds.

**Citations re-verified (§1.3, §1.6, §5.2, §5.4, §5.5, §11.1, and §1.4 and §9.1 in passing). All correct:**
- `M5/platformio.ini:26` (`default_envs = usb`)
- `M5/src/main.cpp:25-26,28-29,35,145,146,155,162-168,201-202,215-218,245-247,255,367-369,431,434`
- `M5/src/USBStream.cpp:193,275`
- `M5/include/Common.h:47-48,97,106`
- `encoder/src/main.cpp:38,120,323-333,336,367-368`
- `encoder/platformio.ini:34-35,46`

---

## 3. Station procedure attack (task 3)

Harness: `attack.py` `exec`s `station_fit.py`'s own `fit()`/`wrap()` verbatim, and implements step 6 exactly as written: |A| ≤ 32767, ≥ 64 positions, max gap ≤ 10°, and an in-sample residual ≤ 0.02° computed from the rounded coefficients through `ker_compensate()` with the circular mean removed. It then measures the **true** error over a dense 65536-point grid of true angles, through all codes.

**Text vs `station_fit.py`:**

| Aspect | Match? | Notes |
|---|---|---|
| Circular mean | yes | |
| Constant column and discard | yes | |
| Conversion and rounding | yes | Python `round` is round-half-even, which the spec does not state; the effect is negligible. |
| `wrap` | cosmetic difference | The script's interval is [−180, 180); the spec's is (−180, 180]. This only matters at exactly ±180°, which the mean removal makes unreachable. |
| Step 1 (validity and sequence) | **not implemented** | |
| Step 6 (positions, gap, `R_MAX`) | **not implemented** | The script only rejects `|A| > 32767`. |
| §7.2 table claim "every code through `ker_compensate()`" | **not what the script does** | The script evaluates at the 4096 fit points only (in-sample). The numbers are close to out-of-sample: 0.00619 against my 0.00632. |
| N | always 6 | The spec never says how N_HARM is chosen. |

**Offsets near ±180°:** robust at 179.9°, 180°, −179.99° and 180.004° (§1, B-1).

**Larger harmonics:**
- A typical profile with H1 = 4.0° is accepted, true error 0.0163°.
- H1 = 5.0° and 5.5° are correctly rejected by the residual (0.0237° and 0.0276°).
- Worst-moderate (H1 2.5°, dense) is accepted, true 0.0152°.

**Sparse / non-uniform sampling.** Monte Carlo: 40 random phase and offset draws per row, sampling patterns all legal under step 6 (`scen2.py`):

| Part | Sampling | Accepted | **Accepted with true error > `R_MAX`** | Worst such true error |
|---|---|---|---|---|
| worst-moderate (H1 2.5°) | 4096 uniform | 13/40 | 0 | — |
| worst-moderate | 64 uniform | 20/40 | **13** | **0.02458°** |
| worst-moderate | 64, one 10° gap | 19/40 | **9** | **0.02564°** |
| worst-moderate | 64 clustered (36 at 10° + 28) | 24/40 | **15** | **0.02540°** |
| typical + 1 % H7/H8 | 64 clustered | 6/40 | **6** | **0.02862°** |
| large-moderate (H1 1.5°) | any | 40/40 | 0 | — |

**Measurement noise** (single sample per position, as step 1 prescribes; `scen3.py`, typical part, 10 draws):

| Noise σ | 64 uniform | 360 uniform | 4096 uniform |
|---|---|---|---|
| 0.002° | 10/10 accepted, true ≤ 0.0116 | 10/10, true ≤ 0.0077 | 10/10, true ≤ 0.0071 |
| 0.005° | 10/10, true ≤ 0.0118 | 9/10, true ≤ 0.0092 | **2/10** accepted, true ≤ **0.0075** |
| 0.01° | 1/10, true ≤ 0.021 | 0/10, true ≤ 0.011 | **0/10**, true ≤ **0.0079** |

**Conclusion.** The step-6 test is a maximum residual measured *at the fit points*. Two consequences follow:
- At the 64-position minimum it permits, it is optimistic by up to ≈ 1.8×, so it passes parts that miss `R_MAX`.
- Under noise it is pessimistic, and more so the denser the station, so it rejects good parts from the better station and accepts them from the worse one.

Step 7 checks only ≥ 8 positions, and GET_ANGLE_COMP has no validity or sequence field, so step 7 is not an effective backstop.

---

## 4. Findings

### MAJOR

**MAJOR-1: The §7.2 step-6 acceptance criterion does not separate good fits from bad at its own defaults, and the golden reference does not implement it.**
- Evidence: §7.2 step 6 reads `"the residual at the fit points, recomputed from the rounded A_k, φ_k … ≤ R_MAX. Defaults 64 / 10° / 0.02°"`. §11.1 reads `"encoder/tools/kercal/ … its fit is station_fit.py's"`. `station_fit.py:40` is the only rejection in the script. The measurements are in §3 above.
- Why it matters:
  - This is the only quality gate before a calibration is written to a part.
  - It passes parts with true error up to 0.0286° against a 0.02° limit when sampling is sparse but legal.
  - It rejects most good parts on a dense station with σ = 0.005° noise.
  - `kercal` is to copy a reference that has no gate at all.
- Confidence: HIGH on the measurements; they come from the spec's own reference code. The defaults are marked "pending O1/O3", which mitigates the numbers but not the structure: an in-sample maximum with no hold-out and single noisy samples.
- Fix (text only):
  - State what the residual is evaluated on, so that it bounds the true error: dense or held-out positions, or a stated inflation for the fit's degrees of freedom.
  - State whether samples are averaged per position.
  - Add steps 1 and 6 to `station_fit.py` so that the reference implements the normative procedure.
  - Mark the §7.6 accuracy figures as dense-station figures.

### MINOR

- **m-N1: SET_ID write failure and retry are undefined** (the SET_ID half of v3 MJ4).
  - §4.9 SET_ID says `"commit as above"`. The write-failure paragraph says the host `"can retry COMMIT_CAL"`.
  - It is unstated whether SET_ID builds its page in the staging buffer. If it does, a retry gets STAGING_BUSY; if not, a retry sees a now-invalid, non-virgin page and gets `BAD_PAGE`.
  - After a failed SET_ID over a valid page, the only good copy of the calibration is in RAM. It is not readable over CMD=3, because GET_CAL_WORD returns USERROW `"as stored"`.
  - Rated MINOR, not MAJOR. Mitigated by: the VDD pre-check makes a program or verify failure rare; WRITE_FAIL is reported, not silent; the running module is unaffected; and §5.1 station records keyed by SERNUM allow a full STAGE/COMMIT rebuild.
  - Fix: one row for SET_ID in the staging table, and one sentence of recovery in r10.
- **m-N2: After a write failure, §7.1 and GET_HEALTH bit 0 contradict §4.9.**
  - §7.1 says `"Compensation is active when the page is valid"`; which page is meant, stored or running?
  - GET_HEALTH bit 0 is a *live* `"USERROW page invalid → compensation off, upstream mapping, build-default ID"`.
  - §4.9 says the module `"keeps running its previous identity and coefficients"` while USERROW may be invalid. If CAL_INVALID tracks the stored page, bit 0's meaning column is false; §4.9 implies it should not.
  - v3 MJ4 asked `"CAL_INVALID set at once, or only at boot?"` and this is still unanswered.
- **m-N3: The config lock's own safety-word check is undefined at power-on.**
  - GET_CFG_VERIFY bit 4 requires `"every safety word during the sequence valid"`.
  - At the first transaction after sensor power-on, `S_RST` = 0 by design (§2.2).
  - If "valid" includes S_RST, every boot lock fails: SENSOR_CFG_FAIL is set and compensation stays suspended until the next 16th-read retry.
  - §6.2 row 3 (`S_RST = 0 → re-run the config lock`) is also recursive inside the lock.
  - The config-lock duration is not budgeted in §8.3, and it now runs inside `loop()` (every 16th read while failed, and on `S_RST`), next to r9's 1 ms reply bound.
- **m-N4: §6.2 start-up claims.**
  - (a) `"exactly as during upstream's own start-up"`: upstream `setup()` is microseconds (`encoder/src/main.cpp:297-315`). v4 adds `t_pon`, the lock and up to 10 reads, and says nothing about downstream starvation. On a reset during operation, the M5 streams frozen downstream angles as valid (`RSNexus.cpp:87,116-118`).
  - (b) `"the M5 will see as a jump and eventually fault on, correctly"` is false for the power-up case:
    - jump detection needs `last_good_valid` and STREAM mode (`M5/src/main.cpp:197-200`);
    - the M5 boots in STANDBY (`:425`), where every frame just becomes `last_good_angle` (`:219-223`);
    - so a 0 present from start-up becomes the reference and never trips;
    - it is also never checked on ch8 and ch16, or with jump detection off.
  - The behaviour is no worse than upstream; the claim is wrong.
- **m-N5: A stale refuted claim in the evidence.** `results/accuracy_host.txt` (which §7.5 cites for 0.000274°) still says `"adversarial worst … 0.002341 deg … margin 2.1x"`, with no annotation. The ceiling 0.002605° (`worstterm.c`) is missing from Appendix A.
- **m-N6: §10's 650 B has no generator or README command**, which is the same class as numerics m6. My harness gives 680 B, so the number is plausible but unreproducible as shipped. The §7.4 item 3 `0x82FE` depends on the image.
- **m-N7: C4 bullet 2 fires on the module's own replies.**
  - The rule is `"stop transmitting … if any CMD=1 or CMD=2 frame not sent by the host itself is seen"`.
  - A module answers CMD=1 with a CMD=1 frame (§1.2).
  - So the compatibility test that bullet 3 permits terminates the session at its first reply. It should read "other than a reply to the host's own CMD=1".
- **m-N8: §8.3 housekeeping "+≈ 35 µs"** has no derivation. v3 had +27 µs, and the v2 model gives ≈ 25–28 µs for 48 clocks. Harmless.
- **m-N9: Host timing and late replies.**
  - r9 fixes host timeouts at 2 ms and 100 ms. It does not say where they are measured, and USB–RS-485 adapters commonly add milliseconds of latency.
  - Replies echo SUB but not the index, so a late reply within the same SUB (for example GET_SERNUM idx n vs n+1) is undetectable. That is the case r8 exists to prevent.
  - r10's `"at the new ID if the commit may have changed it, else at the old one"`: after a lost reply the outcome is unknown, so both IDs must be probed.
- **m-N10: Unlock residue.** It is unstated whether UNLOCK_1 while armed re-arms, and whether a CMD=1 addressed to another ID disarms. Factory mode itself ends on any CMD=1, but the armed state is only disarmed by `"any other request to this module"`.
- **m-N11: §6.2 `"at most the compensation amplitude, far below the M5's 30° jump threshold"`.** The format allows Σ|A_k| up to 6 × 5.625° = 33.75°. It is true only for realistic parts; say so.
- **m-N12: §7.2 step 1 freshness.** `"index 3 differs from the previous sample's"` does not guarantee that the transaction happened after the stage settled at θ_true. Bench reads occur every 20 ms (`encoder/src/main.cpp:34`). The normative text allows a sample taken in motion.
- **m-N13: §7.2 does not say how N_HARM is chosen**; the reference always fits 6. §7.2's table text says `"every code"`, but it is evaluated at the fit points.
- **m-N14: Cosmetic.** C6's LOCK wording (see m7 in §1); the `ref_comp.c:41` "Spec v3" comment; `wrap` interval.

---

## 5. Open questions (unscored)

- **TLE5012B angle noise** at the locked FIRMD setting decides how bad the noise half of MAJOR-1 is (O2/O3).
- **§4.8 latch counts** are "since reset". Modules reset at different times never show equal counts. Should hosts compare deltas instead? This is pre-existing, and v3 did not flag it.
- **Whether a housekeeping or config-lock transaction advances** the GET_ANGLE_RAW sequence number (idx 3) and the GET_ERRCNT transaction count (idx 0/1).

---

## 6. Verdict

**REVISE (narrow).**
- Every v3 blocker and major is closed except MJ4, which is partial but now MINOR in residual impact.
- The v4 edits introduced no protocol contradiction of MAJOR weight: the index, reason, gate and record tables are mutually consistent.
- The one MAJOR is that the normative fit-acceptance gate, which v4 introduced to close a v3 gap, measurably mis-grades parts at its own defaults, and the golden reference does not implement it.

**What would change the verdict:** redefine the step-6 residual so that it bounds the true error (for example evaluated off the fit points, with the averaging stated), and implement steps 1 and 6 in `station_fit.py`. With that done, and the minors addressed or accepted, this becomes **ACCEPT WITH MINOR CHANGES**.
