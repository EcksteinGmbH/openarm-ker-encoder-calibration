# Response to the spec v6 verification

Verification: `2026-09-20-spec-v6-verification.md` — **REVISE (narrow)**: 0 blocker, 2 major, 6 minor. Both majors
are confined to the §7.7 commissioning simulation and procedure; everything the firmware and the protocol
depend on was verified. Fixed in `../protocol-spec.md` (still v6; § references are to it).

| # | Finding | Status | Resolution |
|---|---|---|---|
| V1 | The check mounting and the production mounting excluded each other as simulated; §7.7 gave no order | fixed | §7.7 states the executable order: set A out → check mounting at 100° → set A back, whose last clamping is the production mounting and is never touched again → set B out and back on it. `ref_selfcal.py` follows that order; the check turn carries the drift of its place in the sequence; production is evaluated on the clamping set B ran on. The check limit was re-derived for the smaller drift it now sees. |
| V2 | The simulated sub-divisional error was inert (8 whole periods per grid step); the reference had no content above the fitted H20 | fixed | Stage positions scatter by 0.03° rms about the nominal grid; the reference error now has content to H40. The good station's `θ_true` error rises accordingly, and §7.7, the reference note §4–§5 and response row F6 quote the new figures. A new column gives the part of that error that lies in H1–H6 — the only part that can enter a module's coefficients. |
| V3 | S3 evidence stale; the script had lost its negative control; §11.2 item 7 worded too strongly | fixed | Mutant C (`ref_comp_mutant_noround.c.txt`, the routine rounding to 1 LSB as in v5) is the negative control. `author_s3_check.py` now runs upstream, v6 and mutant C, adds a cell at 64–128° from the zero, prints PASS/FAIL, and reproduces the earlier "+0.004…+0.013°/h" exactly for the mutant. `regen_results.sh` and the README build the mutant library. §11.2 item 7 reworded as the verifier proposed and cites the verifier's 81-cell script for motion, `_invert` and transitions. |
| V4 | §7.4 item 2 still said "one rounded `>> 7`" | fixed | §7.4 item 2 gives the v6 rounding and names the reliance on an arithmetic right shift. |
| V5 | "Absorbed by S2" is ≈ 72 % true; "limits set between good and faulty" not true of the check limit | fixed | §7.7 says "mostly"; the criteria are now justified by pass rates per fault level and by the worst `θ_true` error of any station that passes both, from `ref_selfcal.py`'s second table, not by medians. "Caught" is replaced by the pass rates. |
| V6 | Suspended compensation leaves the 8-LSB grid | fixed | §7.1: bounded at ≈ 3 × 10⁻⁵° per episode; only continuous flapping while moving accumulates, ≈ 0.01°/h, cleared by re-zeroing. Transition case added to §11.2 item 7. |
| V7.1 | v6 row detached from the revision table | fixed | |
| V7.2 | `station_fit.py` docstrings; "v5 procedure" in the demo; step 2 direction | fixed | Docstrings and the demo header updated (`results/station_fit.txt` regenerated); step 2 re-approaches always clockwise. |
| V7.3 | Centring gate had no constant or function in the reference | fixed | `H2_MAX`, `centring()`. |
| V7.4 | Service list could not link a module to its grade | fixed | §9.7: `GET_SERNUM`, the 16 `GET_RUN_WORD`s compared with the database record, identity page via `GET_CAL_STATUS`. |
| V7.5 | ± 0.5 K is ± 1 count | fixed | ± 2 counts of `TEMPR`. |
| V7.6 | "spread ≤ 3″" inconsistent with 1.5″ rms reference noise | fixed | Stationarity: standard deviation ≤ twice the static noise of the incoming test, and first-half against second-half mean within 3″. |
| V7.7 | Hysteresis bias is +0.002°, partly real | fixed | §7.2 text. |
| V7.8 | §7.1 omitted the 64–128° band | fixed | §7.1 text. |
| V7.9 | Appendix A path; magnet lot and thread-locker | fixed | Appendix A; §7.2, §9.7. |

The sampled response rows the verifier marked *partly* (F2, F4) and *asserted only* (F6, for the SDE part) are
the subject of V1, V2 and V5 and are updated in `2026-09-20-accuracy-review-response.md` accordingly.

**Not addressed, by the verifier's own list:** the authenticity of the v5 text used for the diff (there is no git
history — nothing is committed), and real hardware.

## Re-verification

`2026-09-20-spec-v6-reverification.md` — **ACCEPT WITH MINOR CHANGES**: V1–V7 all resolved; 0 blocker, 0 major,
3 minor, all wording.

| # | Finding | Status | Resolution |
|---|---|---|---|
| W1 | "Out and back cancels linear drift" is stronger than the table: it equalises drift within a set, not between set A and set B | fixed (wording) | §7.7, reference note §5, response row F5. The verifier's optional one-column refinement of the fit is recorded in §7.7 for adoption, with re-verification, when `kercal` is written; it is not adopted now, so no number changes. |
| W2 | The 23.9″ / 14.9″ bound is seed-dependent in the last digit and holds only with an encoder-grade C2 and SDE ≤ 8″ | fixed (wording) | "≈ 24″ / ≈ 15″" with both conditions and the verifier's two counter-examples, in §7.7, the reference note §5 and the response rows F2 and F5. |
| W3 | Accuracy-review response quoted superseded limits; §7.1 "add exactly" | fixed | Rows F3, F5, F7, S3; §7.1 first paragraph. |

The verifier's first-round scripts `selfcal_criteria_oc.py` and `selfcal_sde_alias.py` no longer run against the
rewritten `ref_selfcal.py`; their stored results remain the record of the first v6 draft.
