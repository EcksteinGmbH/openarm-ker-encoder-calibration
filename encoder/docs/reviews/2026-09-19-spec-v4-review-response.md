# Response to the spec v4 verification

Verification: `2026-09-19-spec-v4-verification.md` — REVISE (narrow): 0 blocker, 1 major, 14 minor.
Resolved in `../protocol-spec.md` **v5**; § references are to v5.

Status: **fixed**, **accepted** (documented, not changed), **decided** (resolved by the user's decision).

## Major

| # | Finding | Status | Resolution |
|---|---|---|---|
| MAJOR-1 | §7.2 step-6 gate: in-sample, single noisy samples; mis-grades parts at its own defaults; not in the reference | fixed | Out-of-sample validation positions; on-module averaging (K = 1024, `SAMPLE_START`/`GET_SAMPLE`, D17); validation on the **committed module's own output**; empirical noise check with an *insufficient data* verdict; 5 % guard band (§7.2, §4.10). `station_fit.py` now implements every step. Operating characteristic measured over 4000 simulated parts under the datasheet's 0.05° noise: **no accepted part above `R_MAX`**, 100 % pass below 0.010° (`station_sim.py`). |

The verification's finding rested on a fact neither review had: the TLE5012B's **0.05° (1σ) per-reading
noise** at the default filter setting (data sheet Table 10). It is now in §2.7, §7.5, and drives D16–D17.

## Minor

| # | Status | Resolution |
|---|---|---|
| m-N1 SET_ID write failure / retry undefined | fixed | SET_ID builds from the **running** state in a private buffer, so a failed SET_ID is simply retried; `GET_RUN_WORD` (0x15) makes the running page readable (§4.9, §4.6). |
| m-N2 CAL_INVALID stored vs running | fixed | Live bit tracks the running state; GET_CAL_STATUS reports the stored page; §7.1 wording (§4.7, §7.1). |
| m-N3 config-lock safety check at power-on; lock duration | fixed | `S_RST` ignored inside the lock; GET_CFG_VERIFY bit 4 redefined; ≈ 0.3 ms budget (§6.2). |
| m-N4 start-up claims false | fixed | ≈ 9 ms start-up with downstream starvation stated; the M5 does not fault on a 0 at power-up (STANDBY) — corrected (§6.2). |
| m-N5 stale 0.002341° line; ceiling source | fixed | `acc.c` relabelled, results regenerated; `accuracy_analytic_ceiling.txt` from `worstterm.c` (§7.5, App. A). |
| m-N6 650 B unreproducible | fixed | `flash_cost.c` and README command; reproduces 650 B (the verifier's own harness gave 680 B). |
| m-N7 C4 fires on the module's own CMD=1 reply | fixed | C4 bullet 2 reworded (§3.2). |
| m-N8 housekeeping +35 µs underived | fixed | 48 clocks at the first row's rate, plus CRC: ≈ 33 µs (§8.3). |
| m-N9 timeouts vs adapter latency; late replies; retry ID | fixed | Latency at the module pins; host adds its measured round-trip; quiet period stated as the protection; both IDs probed (§4.3 r9, r10). |
| m-N10 unlock residue | fixed | UNLOCK_1 while armed re-arms; any CMD=1/2 frame disarms (§4.9). |
| m-N11 "far below 30°" | fixed | Qualified: true for datasheet parts; format permits 33.75° (§6.2). |
| m-N12 sample freshness vs stage motion | fixed | Sampling is started only after the stage has settled (§7.2 step 1). |
| m-N13 N_HARM choice; "every code" claim | fixed | N_HARM = 6 always; table caption corrected (§7.2). |
| m-N14 cosmetics | fixed | C6 LOCK wording, `ref_comp.c` comment, `wrap` interval [−180, 180). |

## Open questions raised by the verification

| Question | Resolution |
|---|---|
| TLE5012B noise at the locked FIR_MD | 0.05° at FIR_MD 2 (datasheet); FIR_MD kept at 2 (D16). |
| Latch counts differ across modules reset at different times | Host compares **deltas** before/after each latch (§4.8). |
| Do housekeeping / config-lock transactions advance the sequence number and totals? | No — only angle transactions (§4.7). |

## Decisions taken with the user, 2026-09-19

| | Decision |
|---|---|
| P1 → D16 | FIR_MD stays at 2. |
| P2 → D17 | Add on-module averaging; used SUBs 0x16–0x17; the SUB space is now full (D21). |
| O5 → D18 | Persistent faults: hold 20 consecutive failures, then pass CRC-valid readings through, flagged `ANGLE_DEGRADED`. |
| O6 → D19 | The user did not know the supply voltage. Inferred 5 V from the 20 MHz clock, which the ATtiny1616 only permits at 4.5–5.5 V; `VDD_MIN_PROG` = 4.5 V. To be revisited if the boards are not 5 V. |

## Found during the revision

1. Two bugs in my own first version of `station_sim.py` — a missing re-wrap after mean removal, and an
   unwrap centred on the grid angle instead of the output — produced impossible "true errors" of 55° and
   325°. Both were in the simulation's reference metric, not in the gate or the firmware routine; both were
   fixed before any number was recorded.
2. Noise dithers the 15-bit steps, so the **averaged** output has no quantisation sawtooth; the systematic
   error seen by an averaging user is the model residual alone (§7.5).
