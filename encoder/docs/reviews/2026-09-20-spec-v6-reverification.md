# Spec v6 re-verification — the fixes to findings V1–V7

| | |
|---|---|
| Subject | the changes made in answer to `2026-09-20-spec-v6-verification.md`: `protocol-spec.md` (§7.1, §7.2, §7.4, §7.7, §9.7, §11.2, App. A), `evidence/v3-reference/{ref_selfcal.py, station_fit.py, ref_comp_mutant_noround.c.txt, README.md, regen_results.sh, results/}`, `evidence/v5-accuracy-review-scripts/author_s3_check.py`, `station-reference-encoder.md` §4–§6, `reviews/2026-09-20-{accuracy-review-response, spec-v6-verification-response}.md` |
| Verifier | the same independent agent, 2026-09-20 |
| Rules kept | no existing file edited, nothing committed, builds in `mktemp -d`, Python run with `PYTHONDONTWRITEBYTECODE=1`. New: this file, and `evidence/v6-verification-scripts/{selfcal_recheck.py, selfcal_drift_mechanism.py}` + `results/` |

## 1. Verdict

**ACCEPT WITH MINOR CHANGES: 0 blocker, 0 major, 3 minor (all wording; one comes with an optional one-line improvement).**
V1–V7 are resolved. The new commissioning order is executable and `ref_selfcal.py` follows it step for step; the
sub-divisional error is now really sampled and the result does not depend on the stage-scatter value chosen; both §7.7
tables, the 23.9″ / 14.9″ statement, the ± 14–18″ / ± 5–10″ summary and the condition number are identical to
`results/ref_selfcal.txt`, which reproduces bit for bit from the documented command. The 23.9″ / 14.9″ statement held up
under a different seed and under combined faults (worst 23.5″ / 15.0″), and "about 70 % absorbed" re-derives as 72–74 % on
the new model. §3 and §5 are still byte-identical to v5 and §4 still differs in one line. What remains: one sentence of §7.7
is stronger than the author's own table (W1), the headline bound should carry its two conditions and one significant
digit less (W2), and three rows of the accuracy-review response quote superseded limits (W3). None of them touches the
firmware, the protocol or a number in the spec's tables.

## 2. Status of V1–V7

| ID | Status | Basis |
|---|---|---|
| V1 | **resolved** | §7.7 "Order" and the reference note §5 state: set A out → check at 100° (not fitted) → set A back, last clamping = production, never touched → set B on it. `ref_selfcal.py:171-176` builds exactly that sequence (37 turns; the fit excludes the check turn, `fit_idx`). The check turn sits at index 10 of 36 and gets `drift × 10/36` (l. 178). Production (l. 190-191) runs on `g_last`/`c_last` — the clamping set B ran on — with `random_module()` and a fresh `s2_now()`. Every set-B turn draws its own `s2_now()` (l. 176); set A keeps the artefact's one fixturing. Nothing in the sequence needs a clamp to be undone and restored. `CHECK_MAX` re-derived to 12″: good stations pass 100 % of 300 (max 8.1″ in my 200 with another random stream) |
| V2 | **resolved** | `turn()` adds `STAGE_SCATTER` = 0.03° rms (61° rms of SDE phase). `selfcal_recheck.py` R1, good station, 200 stations: SDE 0 → 8.4″ / 12.8″; SDE 8″ → **14.4″ / 18.8″**; scatter 0 (the old inert case) → 8.4″ / 12.8″ again; scatter 0.10° (phase fully randomised) → 14.8″ / 19.6″, so the ± 14–18″ figure is **not sensitive to the assumed scatter**. Reference content to H40 is present and lies outside the fit, but it is small: truncating it to H20 changes 14.4″ / 18.8″ to 13.1″ / 18.0″ (≈ 1.3″). The unmodelled-content budget is carried by the SDE; the spec's wording ("content to H40, i.e. beyond the fitted model") is accurate and does not claim more. The H1–H6 column is computed correctly (projection of the production-turn error on H1–H6 of the horn angle) and is the right quantity to quote |
| V3 | **resolved** | Mutant C differs from `ref_comp.c` in the one rounding line (`(acc + 64) >> 7`). `author_s3_check.py libref.so libmut.so` reproduces `results/author_s3_check.txt` exactly, exit code 0, PASS: upstream 0, v6 0, mutant C +0.0130 / +0.0069 / +0.0055°/h in the three sensitive cells incl. the new 64–128° cell, ≈ 0 at sensor 250°. README and `regen_results.sh` build `libmut.so`. §11.2 item 7 now asks for exactly zero (v6), no growth and ≤ 1 × 10⁻⁴° (uncalibrated, a suspension episode), and a drifting negative control |
| V4 | **resolved** | §7.4 item 2 gives `((acc + 512) >> 10) * 8` and names the reliance on the arithmetic right shift |
| V5 | **resolved** | (1) "mostly … about 70 %": `selfcal_recheck.py` R3 on the **new** model — H1–H6 of the remaining error 10.2″ with only the production clamp bad (30″ + 15″), 36.7″ in the control (set B on fresh clamps), 0.8″ with no clamp error: 72–74 % absorbed. (2) The criteria are now justified by pass rates and by the worst error among passing stations, and the text says they "do not separate good from faulty stations cleanly" — which is what the table shows. See W2 for the wording of the bound |
| V6 | **resolved** | New paragraph at the end of the D22 explanation; transition case in §11.2 item 7. (Nit: the paragraph above it still says upstream's images "add exactly"; the new one says "bounded … ≈ 3 × 10⁻⁵°". The second is right) |
| V7.1–7.9 | **resolved** | Table row attached; `station_fit.py` docstrings, `H2_MAX`, `centring()`, demo header "v4-v6 procedure" (`results/station_fit.txt` reproduces); step 2 "always clockwise"; §9.7 service list with `GET_SERNUM` and the 16 `GET_RUN_WORD`s; ± 2 `TEMPR` counts; stationarity = σ ≤ 2 × static noise and half-means within 3″ (with 8 polls at 1.5″ rms that is a 2.8 σ limit, ≈ 0.5 % false repeats, and it still catches the review's 36″ step); hysteresis sentence; 64–128° band in §7.1; Appendix A paths; magnet lot and thread-locker |

Frozen items: `## 3` md5 `9988b8db…` and `## 5` md5 `477f9617…` equal in v5 and v6; `## 4` differs in the single `GET_PROTO_VER` line.
The refreshed diff file is identical to `diff -u protocol-spec-v5-final.md protocol-spec.md`. `ref_comp.c`, `ref_comp.h` and
mutants A/B are untouched since the first verification (timestamps 14:17; `host.txt` still reproduces).

## 3. New findings

### W1 — MINOR — "Running out and back cancels linear drift of the artefact" is stronger than the simulation

**Where.** Spec §7.7, "Order" bullet; reference note §5 step 2 ("用来抵消传递件的线性漂移"); response row F5.

**What.** `ref_selfcal.py` applies *exactly* linear drift (`mscale = 1 + drift·i/(T−1)`), and its own second table shows the
H1–H6 error — the part that enters every module — growing 4.7″ → 7.0″ → 9.5″ → 15.1″ → 29.8″ for 1, 2, 3, 5, 10 %. Linear drift
is attenuated about ten-fold, not cancelled. Out-and-back equalises the artefact's mean scale *within* a set; it does
nothing about the offset *between* the sets (set A is centred on turn 10 of 36, set B on turn 28.5). Inside set A the
columns of `M` (a function of θ + δ₀) and of `S2` (a function of θ) are collinear — only set B separates them — so a scale of
`M` that differs between the sets is partly booked to `Ŝ2`.

**Evidence.** `selfcal_drift_mechanism.py 100` → `results/selfcal_drift_mechanism.txt` (good station; `θ_true` error all | H1–H6, median / max, arcsec):

| drift | as `ref_selfcal.py` | same drift inside each set, both sets centred on one mean (isolates the offset) | as `ref_selfcal.py` + one fitted parameter |
|---|---|---|---|
| 0 % | 13.1 / 16.2 \| 3.3 / 6.1 | 13.1 / 16.2 \| 3.3 / 6.1 | 13.0 / 16.1 \| 3.3 / 5.8 |
| 2 % | 16.5 / 27.9 \| 7.1 / 16.3 | 13.1 / 16.2 \| 3.3 / 6.1 | 13.0 / 16.1 \| 3.3 / 5.8 |
| 5 % | 24.7 / 49.2 \| 15.7 / 38.7 | 13.1 / 16.2 \| 3.3 / 6.1 | 13.0 / 16.1 \| 3.3 / 5.8 |
| 10 % | 39.0 / 86.1 \| 30.7 / 76.1 | 13.1 / 16.2 \| 3.3 / 6.0 | 13.1 / 16.2 \| 3.4 / 5.9 |

The whole drift sensitivity is the A-to-B offset. The third column adds **one** column to the second pass of the joint fit —
`−[turn in set B] · M̂_pass1(θ_s)`, i.e. the scale of the artefact in set B relative to set A — and the error becomes
independent of drift up to 10 %, at no cost at 0 %.

**Fix.** Required: reword — "cancels linear drift within each set; the offset between set A and set B does not cancel and is
what the drift rows of the second table show (H1–H6 ≈ + 2.5–3″ per 1 % of drift)". Optional, the author's call: adopt the
extra column in `ref_selfcal.py` / `kercal`. If adopted, regenerate `ref_selfcal.txt` and the second table; note that the
reproducibility criterion will still flag drift (within-set residuals remain), which then is a false alarm on the safe
side, so its role changes from protection to diagnosis.

### W2 — MINOR — The headline bound should carry its conditions and one digit less

**Where.** Spec §7.7, bold sentence "over all fault levels, no station that passed both had a `θ_true` error above 23.9″
(0.0066°), or above 14.9″ (0.0041°)"; reference note §5 last bullet; response rows F2, F5.

**What.** As a statement about the run it is exact (the file's last line). As the bound a reader will take it for, it is
supported but seed-dependent in the last digit, and it holds only under two conditions that the sentence does not carry —
the spec states both elsewhere, the reference note's bullet states neither.

**Evidence.** `selfcal_recheck.py 200` → `results/selfcal_recheck.txt`, worst error among stations passing both criteria, all / H1–H6:

| Case | pass both | worst passing |
|---|---|---|
| other seed: drift 2 % / drift 5 % / clamp 10″+5″ | 90 % / 23 % / 67.5 % | 23.5 / **15.0** · 22.7 / 14.3 · 21.1 / 10.5 |
| combined: clamp 6″+4″ and drift 2 % | 82.5 % | 22.2 / 11.8 |
| combined: clamp 10″+5″ and drift 3 % | 36.5 % | 20.5 / 11.2 |
| C2 diaphragm varying 60 % per fixturing | 100 % | 23.1 / 12.3 |
| **SDE 20″** (pole-pitch class), else good | 100 % | **31.1** / 13.0 |
| **C2 a bellows** 40″+20″, else good | 90 % | **38.0 / 31.6** |
| C2 a bellows and drift 2 % | 58.5 % | 38.7 / 30.4 |

So: combined faults do not break the bound (they fail the criteria sooner); the H1–H6 bound holds for everything except a
poor C2; the all-harmonics bound additionally needs the SDE to be what was assumed. Neither a poor C2 nor a large SDE is
visible to the criteria — the spec says so for C2 two sentences later ("mostly still under the limit": 90 % pass) and for
the SDE under "What cannot be calibrated".

**Fix.** "…no station that passed both had a `θ_true` error above **≈ 24″ (0.007°)**, or above **≈ 15″ (0.004°)** in the
harmonics that can enter a module — **given an encoder-grade C2 and a sub-divisional error of ≤ 8″, neither of which the
criteria can see**; the incoming test's fine scan supplies the second." Same in the reference note §5 and response row F2.

### W3 — MINOR — Response rows that quote superseded limits

`reviews/2026-09-20-accuracy-review-response.md`: row **F5** "Warm-up, ± 0.5 K" — §7.7 now says ± 2 counts of `TEMPR`
(≈ ± 0.7 K). Row **F7** "spread ≤ 3″" — §7.7 now says σ ≤ 2 × static noise and half-means within 3″. Row **S3** still reads
"calibrated +0.004…+0.013°/h, rounded 0" and "both mutants still caught"; after V3 that figure belongs to mutant C and
there are three mutants. Row F3's "U ≈ 13″" is the review's figure; the spec's own is now ± 14–18″ (the argument it
supports gets stronger, not weaker). Spec, reference note §4–§6, §7.8, D27, O3 and the verification response are
consistent with each other and with the results file; I found no other stale figure (searched for 25″, 10–15″, 7–13″, 4.3″,
50.4″, 15.6″, 23.5″, "caught", "spread", ± 0.5 K).

## 4. What I re-ran

| Item | Result |
|---|---|
| `OPENBLAS_NUM_THREADS=1 python ref_selfcal.py 100 300` (5 min 22 s) | `results/ref_selfcal.txt` reproduced bit for bit |
| §7.7 table 1 (7 rows × 10 numbers) and table 2 (9 rows) against the file, by script | 16 of 16 rows identical; 23.9″ / 14.9″, 0.0066° / 0.0041°, cond 3.0, "3.0″ to 6.7″", ± 14–18″ / ± 5–10″ all match; degree conversions correct |
| Reference note §4, §5 (pass-rate table, 52″ / 1.2″, 23.9″ / 14.9″, C2 table) and response rows F1, F2, F4, F5, F6, F10 against the file | all figures match |
| `author_s3_check.py libref.so libmut.so` | reproduced, exit 0, PASS |
| `station_fit.py` | `results/station_fit.txt` reproduced (new header) |
| `diff_main.c` host build | `results/host.txt` still reproduced; `ref_comp.c` unchanged |
| md5 of `## 3`, `## 5`, line diff of `## 4`; `diff -u` against the refreshed diff file | frozen items intact; diff file faithful |
| new `selfcal_recheck.py 200` (R1 SDE / H40 / scatter; R2 other seed, combined and out-of-table faults; R3 absorption) | V2, V5 confirmed; W2 |
| new `selfcal_drift_mechanism.py 100` | W1 |

Not re-run: everything that depends only on `ref_comp.c` (unchanged since the first verification), `station_sim.py`.
My first-round scripts `selfcal_criteria_oc.py` and `selfcal_sde_alias.py` import the **first** v6 draft of `ref_selfcal.py`
and no longer run against the rewritten one; their `results/*.txt` are the record of that draft and are cited as such.
Still not verifiable here, as before: the authenticity of the v5 text (no git history) and real hardware — in particular
whether 1–2 % artefact drift over a two-hour commissioning at ± 2 `TEMPR` counts is realistic (O1 warm-up data).
