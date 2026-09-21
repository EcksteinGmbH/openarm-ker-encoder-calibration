# Response to the spec v5 verification

Verification: `2026-09-19-spec-v5-verification.md` — **ACCEPT WITH MINOR CHANGES**: 0 blocker, 0 major.
The minor changes are made in `../protocol-spec.md` (still v5; § references are to it).

| # | Finding | Status | Resolution |
|---|---|---|---|
| m-V1 | Gate's guarantee not established below the default counts; no allowed range | fixed | `N_FIT`, `N_VAL` ≥ 128 and `K` ≥ 1024 are **minimums** (§7.2). Measured: at 64 + 64 positions two parts up to 0.0204° are accepted (`station_oc_K1024_N64.txt`). |
| m-V2 | "True systematic error" constant unspecified; gate sensitive to offset shift between passes | fixed | Both the definition and the gate use the **half-range** (max deviation about the minimax constant), which is invariant to any constant: no offset estimate is carried from the fit pass. Measured: a 0.01° shift between passes gives verdicts identical to no shift (`station_oc_K1024_drift0.01.txt`). The note that a single-point jig zero can see up to 2 × `R_MAX` is stated (§7.2). |
| m-V3 | `station_fit.py` does not implement every step it claims | fixed | Adds GET_SAMPLE→angle (`sample_angle`, `sample_output`), the step-2 `noise_check`, `half_range`, and v5 step numbering; the simulation now calls these rather than its own copies. The docstring and §7.2 state which parts are the station's (motion, settling, I/O, discard rules). |
| m-V4 | Step 2 standard deviation undefined across the seam | fixed | Circular standard deviation (§7.2 step 2; `noise_check`). |
| m-V5 | D18 conflicts with start-up text and status bits; what counts toward 20; S_RST; sample and latch validity | fixed | §6.2 rewritten: every failure counts; only status-row failures with valid CRC pass through; S_RST, CRC and no-response never do; flag semantics for ANGLE_STALE / ANGLE_DEGRADED / NO_VALID_ANGLE; GET_SAMPLE and latch-valid behaviour (§4.7, §6.2). |
| m-V6 | GET_RUN_WORD on the build default | fixed | Every word reads `0xFFFF`. |
| m-V7 | GET_ENV index 1 before the first commit | fixed | VDD measured at start-up and on every housekeeping transaction. |
| m-V8 | Stale text | fixed | GET_PROTO_VER `5`; "no v5 subcommand"; "five records"; D13 marked superseded by D20. |
| m-V9 | VDD threshold has no measurement tolerance | accepted | Stated: reference accuracy not subtracted, spurious `WRITE_FAIL` possible near 4.5 V, fails safe; stations supply ≥ 4.75 V (§5.5). Reference accuracy is an O2 bench item. |
| m-V10 | §2.7 table citation; 1.6° includes drift and hysteresis; approach direction and temperature unstated | fixed | Table 9 cited; §2.7 states what a static fit cannot remove; §7.2 step 1 fixes the approach direction and records temperatures. |
| m-V11 | Evidence hygiene: hand-added ceiling line; K = 256 file unreproducible | fixed | `ceiling.py` generates the ceiling lines; every OC file has a README command. |
| m-N5 (partial in v5) | as m-V11 | fixed | as above. |
| m-N6 (partial in v5) | `0x82FE` address image-dependent | fixed | §7.4 states the section and range, not an address. |
| — | Seam-crossing sets not required in §11.2 | fixed | Required in both directions; measured coverage of the reference sets: 10 below 0, 9 above 2²¹ − 1 (`seam_check.c`). |

## Re-measured after the statistic change

The switch to the half-range changed both the gate and the reference metric, so the operating
characteristic was re-run rather than carried over. At the minimums, 4000 parts: no accepted part above
`R_MAX`, **no rejected part below 0.75 × `R_MAX`** (the v5 draft had one), 100 % pass below 0.015°.
