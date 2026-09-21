# Independent verification: `encoder/docs/protocol-spec.md` v5

Verifier: critic (independent). I did not rely on the response document. Every closure below was checked against
the v5 text, the evidence code, the upstream source, or the TLE5012B datasheet extract.
Scratch directory (all scripts and outputs): `/tmp/claude-1000/-home-dev-workspace/38490050-73d7-4d9c-8938-ba86d5c14f65/scratchpad/v5ver/`
(`v5lib.py`, `check_ref.py`, `attack.py`, `attack_n.py`, `k256.py`, `repro.sh`/`repro.log`, `attack_*.txt`).

**VERDICT: ACCEPT WITH MINOR CHANGES.**
- There are no blockers and no majors.
- v4 MAJOR-1 (station gate) is **CLOSED**. I attacked the §7.2 gate as written, at its defaults, with my own
  part populations: concentrated around `R_MAX`, residual carried by H7/H8, H12 or H16, and deliberately
  asymmetric residuals. I also tried AR(1)-correlated noise with ρ up to 0.95 and lower sensor noise. In none
  of these did the gate accept a part above `R_MAX`.
- `true_systematic()` is correct: its exact expectation agrees with a 400 000-reading Monte Carlo to within
  MC noise, including at offsets near 0° and ±180°. I found no third bug. Its docstring's "best constant" is
  imprecise: it removes the circular (L2) mean, not the minimax constant (m-V2).
- Of the 14 v4 minors, 12 are CLOSED and 2 are PARTIAL (m-N5 and m-N6, evidence-file residue). All three open
  questions are closed.
- New v5 content has 10 MINOR defects. Most are undefined corners of the new §6.2 persistent-fault rule and the
  new SUBs, plus two datasheet-claim inaccuracies in §2.7.

Mode: THOROUGH. I found no CRITICAL, no MAJOR and no systemic pattern, so I did not escalate.

---

## 0. Reproduction (README end to end, `harmonics_v3.py` skipped)

| Item | Result |
|---|---|
| `gen_sinq.py` | all four `.inc` byte-identical; the 6-bit table reports `DOES NOT fit uint16`, as claimed |
| `acc.c` | byte-identical to `results/accuracy_host.txt`; relabelled line present ("a search result, NOT the worst case") |
| AVR differential | `AVR == host`, 21/21 sets; host hashes identical to `results/host.txt` |
| Mutants | int16: invisible on host, **20/21** differ on AVR; uncal: invisible on host, **1/21** differ on AVR. Both identical to the committed `avr_mutant_*.txt` |
| uncalibrated = upstream | `0 mismatches` |
| `construct.c` | N=1…6 lines identical (0.002587° at N=6) |
| cycles (`cyc_main.c`, `cyc_worst.c`) | identical to the committed files apart from simavr's ANSI colour codes; 156…1058 |
| CRC-8 | `b592 t123 e1` |
| `worstterm.c` | prints **one** line. The committed `accuracy_analytic_ceiling.txt` has a second "ceiling N=6 … 0.002605 deg" line that the program does not print (m-N5 residue). The arithmetic is right: 6 × 2.4458 + 0.5 = 15.17 LSB = 0.002605° |
| `flash_cost.c` | 888 − 238 = **650 B**, reproduced. `.rodata` sits at 0x8274, not the 0x82FE in §7.4 item 3 (m-N6 residue) |
| `base_mapping.py` | identical |
| `station_fit.py` | byte-identical to `results/station_fit.txt` |
| `station_sim.py … 0.05 1024 4000` | **byte-identical** to `results/station_oc_K1024.txt` (2 min 22 s) |
| `station_oc_K256_R_ACCEPT_1.00.txt` | no README command, and `station_sim.py` has no R_ACCEPT argument. Byte-identical when rerun with `R_ACCEPT = 1.00·R_MAX` patched in (`k256.py`). The "a third insufficient" claim in §7.2 does not depend on R_ACCEPT and holds: 1346/4000 |

---

## 1. The acceptance gate (§7.2, `station_fit.py`, `station_sim.py`)

### 1.1 Is `true_systematic()` a correct reference?

I checked `station_sim.py:40-55` line by line:
- `P(code j)` = Φ(((j+1)Q − m)/σ) − Φ((jQ − m)/σ) is correct for noise added before `floor` quantisation, which
  is the same model `sensor_readings()` uses.
- `js` and `m % 360` are in the same frame. The span of ±29 codes is ±6.4σ, and renormalisation removes the
  ≈ 2·10⁻¹⁰ truncated tail.
- The unwrap is around the central code's output, which is correct at any offset.
- The `% 32768` index is right.

Independent check (`check_ref.py`): exact expectation vs Monte Carlo with 400 000 readings (MC 1σ = 0.00008°)
at 15 grid points per part, for three parts with offsets 0°, 179.99° and 359.97°. The maximum deviations were
0.00022°, 0.00014° and 0.00017°, which is consistent with MC noise. **No third bug.**

The choice of constant is the one issue:
- The docstring and §7.2 say "with its best constant removed". The code removes the **circular mean**, which
  is the L2-best constant, not the minimax one, which is the midrange.
- For the no-false-accept claim this is conservative: the midrange metric is never larger.
- It is the reason drift between passes looks like false accepts in §1.4.
- It also leaves the meaning of `R_MAX` unstated (m-V2).

The grid is 2048 points. I reran on 8192 points: the conclusions are unchanged.

### 1.2 Does the simulation implement §7.2 as written?

| Step | Simulation | Match |
|---|---|---|
| 1 settle, discard status 1/2 or < 90 % passing | no failures are modelled | n/a (not exercised) |
| 2 σ from 8 repeats at one position, `σ_MAX = R_MAX/6`, *insufficient data* | `station_sim.py:82-84` and `sf.accept` | yes. It uses the raw mean angle at θ_true = 0, which the spec does not name (m-V4) |
| 3 fit positions only, `r₀ + Σ/n`, reference = first reading, wrapped differences | `wrapped_mean(...,32768)` | yes |
| 4–5 circular mean, constant column, `offset = c + a₀` | `sf.fit` | yes |
| 6 conversion, `A_k > 32767` rejected | `sf.to_cal` | yes |
| 7 validation positions only, on the committed output, `c₀ + Σ/n`, wrapped, against `offset`, `≤ 0.95·R_MAX` | `station_sim.py:77-84`, `sf.accept` | yes |

The response claims that "`station_fit.py` now implements every step". That is only partly true (m-V3):
- Step 1's discard rules are absent.
- Step 2's σ computation and step 3's GET_SAMPLE-to-angle conversion (`wrapped_mean`) live only in `station_sim.py`.
- The step numbers in `station_fit.py` comments are v4's: "step 3: remove the mounting offset" at `:62`,
  "Step 5" at `:72` and "Step 6" at `:101`, against v5's steps 4, 6 and 7.

### 1.3 Own populations (defaults, σ = 0.05°, K = 1024, 400–1200 parts each)

| Population | Parts with true error ≥ R_MAX | False accepts | Worst accepted true error | Good parts (< 0.015°) rejected |
|---|---|---|---|---|
| author's generator (my seeds), 1200 | 812 | **0** | 0.01901 | 0 |
| low orders realistic + H7/H8 tuned to 0.014–0.026, 600 | 318 | **0** | 0.01872 | 0 |
| same, residual carried by one H12, 600 | 400 | **0** | 0.01832 | 0 |
| same, residual carried by one H16, 600 | 407 | **0** | 0.01874 | 0 |
| asymmetric residual (H7 + phase-locked H14), 600 | 454 | **0** | 0.01915 | 0 |
| H16 population, σ = 0.02° / 0.01° | — | 1 / 2 | 0.02008 / 0.02004 | — |

The effective threshold sits at about 0.018–0.019°:
- The per-position noise (σ_mean ≈ 0.0015°) biases the maximum over 128 positions upward.
- That bias, together with the 5 % band, covers the validation grid's sampling loss. The loss is
  1 − cos(m · 1.406°): 1.9 % at H8 and 7.6 % at H16.
- With a quieter sensor the bias shrinks, and H16 content produces marginal false accepts of 0.4 %. This is
  negligible, but it means the guard band relies on noise for content above ≈ H12 (noted, not scored).

**Correlated noise (AR(1) between consecutive readings, boundary H7/H8 population):**

| ρ | median σ_mean | insufficient data | false accepts |
|---|---|---|---|
| 0.5 | 0.00254 | 64/400 | 0 |
| 0.65 | 0.00319 | 176/400 | 0 |
| 0.8 | 0.00439 | 329/400 | 0 |
| 0.95 | 0.00908 | 398/400 | 0 |

The empirical σ check does catch correlation. Below its trip point, the extra noise only makes the gate more
conservative.

### 1.4 Does step 7's use of the fit-pass `offset` hide a dependency?

- **Noise in the fit pass** is modelled, and it is small: the offset noise is ≈ 0.00015°.
- **A constant shift between the fit pass and the validation pass is not modelled.** Examples are module or
  sensor warm-up, stage re-homing and magnet creep. The two passes are about 30 s apart.
- I injected a shift δ into the validation pass only:
  - Author population, δ = ±0.003°: 0 false accepts, 8–12 good parts rejected.
  - Asymmetric population, δ = ±0.002° (1.3 σ_mean): **5–13 false accepts** against the simulation's own
    circular-mean metric, worst 0.0219°.
  - Asymmetric population, δ = ±0.004°: 20–30 false accepts, worst 0.0231°.
  - In every such case the minimax (midrange) error of the accepted part is ≤ 0.018°. Mathematically,
    max|e − offset − δ| ≥ the midrange error for any δ, so the gate can never false-accept under the minimax
    definition.
- Whether this is a defect therefore depends entirely on what "true systematic error" means, which the spec
  does not define (m-V2).
- What a user actually sees after M5 zeroing at one pose is up to the **peak-to-peak** error. For accepted
  parts I measured up to **0.037°**.

### 1.5 Non-default constants

§7.2 labels `N_FIT`, `N_VAL`, `K` and `R_ACCEPT` "Default" but states no permitted range, and the operating
characteristic is only valid at these values (`attack_n.py`):
- `N_FIT = N_VAL = 64`, H16 population: **20 false accepts**, worst 0.0235°.
- 32/32: 142 false accepts (H16) and 14 (H7/H8), worst 0.0268°.
- `N_VAL = 32` with `N_FIT = 128`: 127 false accepts (H16) and 12 (H7/H8).

This is the v4 MAJOR-1 failure class (sparse but legal sampling), now reachable only by editing a "default"
(m-V1).

### 1.6 Verdict on the gate

At the stated defaults the gate does what §7.2 and §11.2 item 4 claim. The simulation is faithful, and its
reference metric is correct. **MAJOR-1 is closed.** Three MINOR residues remain: m-V1, m-V2 and m-V3.

---

## 2. Closure audit

### v4 findings

| # | Status | v5 § | Evidence / notes |
|---|---|---|---|
| MAJOR-1 | **CLOSED** | §7.2, §4.10, D17, D20, §11.2 item 4 | §1 above. Residues m-V1, m-V2, m-V3 |
| m-N1 SET_ID failure/retry | **CLOSED** | §4.9 SET_ID table and last paragraph; §4.6 0x15 | Built from the running state in a private buffer, so a retry after WRITE_FAIL is well defined. GET_RUN_WORD makes the running page readable. It is undefined for a build-default module (m-V6) |
| m-N2 CAL_INVALID stored vs running | **CLOSED** | §4.7 GET_HEALTH bit 0, GET_CAL_STATUS header, §7.1 | Consistent |
| m-N3 lock at power-on; duration | **CLOSED** | §6.2 "Config lock", §4.7 GET_CFG_VERIFY bit 4 | S_RST is ignored inside the lock; ≈ 0.3 ms budgeted against rule 9 |
| m-N4 start-up claims | **CLOSED** | §6.2 "Start-up" | Verified: `M5/src/main.cpp:425` is `g_state.mode = AppMode::STANDBY`, and `:219-223` is the non-STREAM branch that makes every frame `last_good_angle`. `RSNexus.cpp:23` is the only `_valid[]=false`; `:87` sets it |
| m-N5 stale line; ceiling source | **PARTIAL** | §7.5, App. A | `accuracy_host.txt` is relabelled (reproduced). `accuracy_analytic_ceiling.txt` line 2 is not program output (§0) |
| m-N6 650 B | **PARTIAL** | §10, README | 650 B reproduced. The image-dependent `0x82FE` (§7.4 item 3), flagged in the same v4 finding, is unchanged; my image gives 0x8274 |
| m-N7 C4 own reply | **CLOSED** | §3.2 C4 bullet 2 | "neither the host's own request nor the addressed module's reply to it" |
| m-N8 +35 µs | **CLOSED** | §8.3 last row | 48 clocks × 0.6 µs (= 48 µs / 80 clocks) + CRC ≈ 33 µs. Consistent |
| m-N9 host timing, late replies, retry ID | **CLOSED** | §4.3 r8–r10 | Pin-referenced latency, RTT measured with PING, quiet period named as the protection, both IDs probed |
| m-N10 unlock residue | **CLOSED** | §4.9 | Re-arm and "any CMD=1 or CMD=2 frame on the bus" both stated |
| m-N11 "far below 30°" | **CLOSED** | §6.2 last paragraph | |
| m-N12 freshness | **CLOSED** | §7.2 step 1 | |
| m-N13 N_HARM; "every code" | **CLOSED** | §7.2 table (`N_HARM` 6), "Why steps 4 and 5" caption | |
| m-N14 cosmetics | **CLOSED** | §3.2 C6; `ref_comp.c:41` "Spec §7.1"; §7.2 step 4 `[−180°, 180°)` | Matches `station_fit.py:48` |

### v4 open questions

| Question | Status | Where |
|---|---|---|
| TLE5012B noise at the locked FIR_MD | **CLOSED** | §2.7, D16. Datasheet extract l. 957-961: 0.11/0.08/**0.05**/0.04° at FIR_MD 0/1/2/3 |
| Latch counts across modules | **CLOSED** | §4.8 (deltas before and after) |
| Do housekeeping and lock transactions advance idx 3 and totals? | **CLOSED** | §4.7 GET_ANGLE_RAW idx 3; GET_ERRCNT idx 0 "angle transactions (§6.1)" |

Carry-over note (unscored): v4 closure of numerics M-2 observed that §11.2 item 2 still does not *state* the
seam-negative (`u + Δ < 0` at r = 0) coverage requirement. It is still unstated in v5.

---

## 3. New v5 content: consistency

**§4.10 and the GET_SAMPLE record.**
- Accumulator widths are sound:
  - Σ wrap₁₅ ≤ 2¹⁴ × 2¹⁰ = 2²⁴ fits `int32_t`.
  - Σ wrap₂₁ ≤ 2²⁰ × 2¹⁰ = 2³⁰ fits `int32_t`.
  - Σ d² can reach 2³⁸, hence saturating with status bit 2. That is the only accumulator that can saturate.
- K = 1024 × 200 µs = 204.8 ms. 200 µs ≥ 2 × 85.3 µs.
- Record rule 6 lists GET_SAMPLE. The abort, restart and gate R rules are consistent with C2 and with rule 7:
  SAMPLE_START is "accepted", so it keeps factory mode alive, which is harmless.
- Undefined:
  - whether pass-through (degraded) readings count as passing, and what "output" is summed;
  - what happens if compensation is suspended (SENSOR_CFG_FAIL) mid-sample during the validation pass.

  See m-V5.

**§6.2 persistent-fault rule vs the flags and start-up.** Contradictions and gaps (m-V5):
- "sends 0 until one does" (start-up) contradicts D18. After 20 status-only failures a degraded angle is sent.
- NO_VALID_ANGLE is only cleared "on ok", so a module can send a live degraded angle while claiming no valid angle.
- Bit 7's meaning "previous **valid** angle is being sent" is false when the held value is a degraded one, after
  a CRC or no-response failure that follows a pass-through.
- It is not said whether an `S_RST = 0` read is a "status" failure eligible for pass-through.
- It is not said whether setup's 10 attempts and housekeeping transactions count toward the 20.
- It is not said what GET_LATCHED bit 8 and §4.8's "valid bit" mean for a degraded sample.

**GET_ENV** index 1 is "VDD from the most recent measurement (§5.5)". §5.5 measures only before a commit, so
the value before the first commit is undefined (m-V7).

**D16–D21 vs body.** All six map to body text (§2.4/§2.7, §4.10, §6.2, §5.5, §7.2, §4.6). D13 still says
"acceptance criteria", which D20 now supersedes; this is cosmetic.

**SUB table.**
- 0x01–0x1F are all allocated; I checked every value.
- Leftovers (m-V8):
  - GET_PROTO_VER still returns `4` although v5 added 0x15–0x17 (SUSPECTED stale; D21 ties new SUBs to a new protocol version).
  - §4.5 SENSOR_FAIL says "no **v4** subcommand".
  - UNSUPPORTED "unknown or reserved SUB" can now only mean 0x00.
- C6's one-bit analysis is unaffected: STAGE_DATA `11011` has no one-bit neighbour among the new SUBs 10101, 10110 and 10111.

**§5.5 VDD.**
- Verified: `encoder/platformio.ini:30` `board_build.f_cpu = 20000000L`; `:36` `OSCCFG = 0x02` 20 MHz;
  `:34-35` WDT and BOD off.
- The 0–20 MHz @ 4.5–5.5 V speed grade matches the tinyAVR 1-series data sheet. I did not have the extract;
  this is from general knowledge, so SUSPECTED-correct.
- No measurement tolerance is given. A 4.5 V threshold measured against the internal reference, on a supply
  that USB-powered benches can hold at 4.4–4.75 V, will produce spurious WRITE_FAILs. This fails safe (m-V9).

**§2.7 against the datasheet extract** (m-V10):
- Correct: t_upd 42.7, 85.3 and 170.6 µs (l. 943-945); delays 60–70, 80–95 and 120–140 µs (l. 948-950); noise 0.08, 0.05 and 0.04° (l. 958-961); t_pon 5 typ / 7 max ms with SBIST = 1, and no write access within it (l. 785-787); 0.6° typ / 1.6° max without autocal (l. 924-927).
- Wrong or overstated:
  - The overall angle error is **Table 9**, not "Table 10 and Table 4".
  - "This is the systematic error that calibration removes" is overstated. The 1.6° figure explicitly
    includes **temperature drift** and **hysteresis caused by revolution direction change** (footnote 2, l. 919-920).
    A single-temperature, direction-agnostic static fit removes neither.
  - §7.2 does not specify approach direction or station temperature. `R_MAX` is therefore a station-condition
    figure, not an in-service one.

**§10 RAM estimate** says "four records". There are now five, plus the live sampling accumulators and the SET_ID
private buffer (32 B). Headroom is unaffected (m-V8).

---

## 4. Findings

### BLOCKER
None.

### MAJOR
None. (Realist check: m-V1 and m-V2 were considered for MAJOR.
- m-V1 is mitigated because the defaults are safe and D20 names them. The failure needs a deliberate edit.
- m-V2 is mitigated because, under the minimax reading, the gate is provably conservative against any constant
  shift. The risk is a stakeholder reading 0.02° as absolute accuracy, not a mis-graded part.)

### MINOR

- **m-V1: The §7.2 constants have no validity range.** The table is headed "Default". D20 cites "defaults of
  §7.2". The operating characteristic, and the 5 % guard band, hold only at `N_VAL = 128` and `K = 1024`.
  - Evidence: at 64/64, 20 of 400 H16 parts were falsely accepted, worst 0.0235°. At `N_VAL = 32`, H7/H8 parts
    were falsely accepted up to 0.0216° (`attack_n.txt`).
  - Fix: make the four constants normative minimums, or require `station_sim.py` to be rerun and pass for any change.
- **m-V2: "True systematic error" (`R_MAX`) is not defined.**
  - `station_sim.py` removes the circular mean but says "best constant".
  - The gate uses the fit-pass `offset`.
  - The user, after M5 zeroing, sees the peak-to-peak error, up to 0.037° for accepted parts.
  - Under the simulation's own metric, a 0.002° shift between the passes gives false accepts up to 0.0219°
    (asymmetric residuals, §1.4). Under the minimax metric it gives none.
  - Fix: define `R_MAX` against the minimax constant, or state explicitly which constant is removed, and say that
    user-visible error after zeroing is up to 2 × `R_MAX`. Also state that fit/validation drift is assumed
    below a stated bound (ties to O3).
- **m-V3: The golden reference is incomplete, contrary to the response.**
  - `station_fit.py` lacks step 1 (discard / 90 %) and step 2's σ computation.
  - It also lacks the GET_SAMPLE → angle conversion; `wrapped_mean` exists only in `station_sim.py:31-35`.
  - Its comments carry v4 step numbers (`:62`, `:72`, `:101`).
  - §11.1 makes this file kercal's reference.
- **m-V4: Step 2 does not define its statistic across the seam.** "standard deviation of their mean angles": if
  the chosen position's sensor angle is within ≈ 0.2° of 0°, `r₀ + Σ/n` straddles 0/32768 and a naive standard
  deviation explodes. This fails safe (*insufficient data*). The fix is to say "wrapped about their circular mean".
  Step 3's θ_s can also fall outside [0, 360), which is harmless to the fit.
- **m-V5: The persistent-fault rule (D18) is under-specified against the flags, start-up and records** (§3
  above). The "sends 0 until one does" text is contradicted by D18.
- **m-V6: GET_RUN_WORD is undefined when the running state is the build default** (no page).
- **m-V7: GET_ENV index 1 is undefined before the first commit.**
- **m-V8: Stale text.** GET_PROTO_VER `4` (SUSPECTED); "no v4 subcommand"; "unknown or reserved SUB"; §10 "four
  records"; §7.4 item 3 `0x82FE`; D13 vs D20 overlap; the revision history has no "v4 → v5" change list.
- **m-V9: `VDD_MIN_PROG` = 4.5 V has no stated measurement tolerance** against a nominal 5 V supply whose −10 %
  limit is 4.5 V. Expect spurious WRITE_FAILs on USB-fed benches. This fails safe.
- **m-V10: §2.7 datasheet claims.**
  - The table citation is wrong: it is Table 9.
  - The 1.6° figure includes temperature drift and direction hysteresis, which a static fit does not remove.
  - §7.2 states neither the approach direction nor the station temperature.
- **m-V11: Evidence hygiene.**
  - `accuracy_analytic_ceiling.txt` line 2 is not program output.
  - `station_oc_K256_R_ACCEPT_1.00.txt` has no README command and needs a code edit to reproduce.

---

## 5. Open questions (unscored)

- Harmonic content above ≈ H12 at the station: the guard band covers it only through the noise bias (§1.3).
  Bench data (O1) would settle whether that matters.
- Is the config-lock "≈ 400 SSC clocks" realistic? My count for write MOD_1, write MOD_2, a block read of
  0x08–0x0F, write TCO_Y, read-backs, STAT and the 5 trim registers is ≈ 550–650 clocks, about 0.4 ms. That is
  still within rule 9's 1 ms.
- Is `S_RST = 0` seen only after t_pon? If not, the §6.2 re-lock writes inside the sensor's power-on window,
  where writes are not permitted. The lock would fail, set SENSOR_CFG_FAIL, and recover on the 16-read retry.
  This is self-healing.

---

## 6. Verdict

**ACCEPT WITH MINOR CHANGES.**
- The single v4 MAJOR is genuinely closed. The new gate, at its defaults, holds under every adversarial
  population and noise model I tried, and its simulation and reference metric are correct and reproduce
  byte-identically.
- All remaining items are MINOR text, definition or evidence-hygiene fixes. None changes the wire protocol or
  the USERROW layout.

**What would change it:** evidence that real modules drift by more than about 0.002° between the fit pass and
the validation pass, combined with a decision that `R_MAX` means the circular-mean-referenced error, or a
station that runs with non-default `N_VAL`/`K`. Either would turn m-V1/m-V2 into a MAJOR and the verdict into
REVISE.
