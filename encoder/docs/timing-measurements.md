# Timing: how to measure it, and what the answers must be

Deliverable 6. Method for the bench measurements of `protocol-spec.md` §8.4, and the sheet
they are recorded on.

**Status on 2026-09-21: not one of these has been measured.** Every number in the "expected"
column comes from a model or a datasheet, named per row in §8. The point of this document is
that the firmware ships with a way to find out, not with a claim that it has been checked.

---

## 1. Equipment and probe points

A logic analyser with ≥ 4 channels, ≥ 24 MS/s (one RS-485 bit at 2 Mbps is 500 ns, so 24 MS/s
gives 12 samples per bit), and a UART decoder. Saleae Logic, sigrok/PulseView or equivalent.

| Ch | Signal | Where | Why |
|---|---|---|---|
| 0 | RS-485 A–B, or the module's RX pin (PA7 / `RX` = 6) | the bus, or the transceiver's RO | frames in and out; one UART decoder serves the whole cascade |
| 1 | module `EN` (pin 5) | module under test | when *this* module drives the bus — separates its reply from everyone else's |
| 2 | `CS` (pin 13) | module under test | the SSC transaction window |
| 3 | `CLK` (pin 16) | module under test | SSC clocks, so transactions can be counted and identified |

For item 5 a spare pin is toggled around the code being timed; see §5 below.

Decoder: UART, 2 000 000 baud, 8N1, no parity, LSB first. A frame is four bytes: one with the
MSB set, then three with it clear (§1.1). Set the decoder to show hex.

**Ground the analyser to the module, not to the M5**, and keep the probe lead short: at 2 Mbps a
long unterminated lead will show edges that are not there.

---

## 2. The measurements

Each row says what to trigger on, what to measure, and what the result must be for the design
to hold. "Expected" is the model; "must" is the criterion that fails the build.

### 1. Reply latency, per hop

*Trigger*: falling edge of `EN` on the previous module in the chain, or the stop bit of the
trigger frame on channel 0.
*Measure*: last bit of the incoming CMD=2 frame → first bit of this module's reply (rising edge
of `EN` is the cleaner mark).
*Compare*: the same module flashed with the upstream build, `-DDEVICE_ID=n`, same wiring.

| | expected | must |
|---|---|---|
| upstream | baseline, whatever it is | — |
| this fork | **≤ 5 µs more** (§8.2) | **≤ 50 µs more** (the brief's ceiling) |

The ≤ 5 µs target matters more than the 50 µs ceiling: per-hop cost multiplies by 16.
Record ≥ 100 replies and report the maximum, not the mean.

### 2. Full cascade

*Trigger*: the M5's CMD=2 ID 0 frame.
*Measure*: to the last bit of ID 16's reply.
*Expected*: ≈ 500 µs. *Must*: < 1000 µs, or the chain cannot hold 1 kHz.

### 3. Refresh rate over ≥ 60 s

*Method*: free-run capture, count M5 trigger frames and count cascades in which all 16 replies
appeared, in order, before the next trigger.
*Must*: ≥ 1000 complete cascades per second, **zero** dropped, and no cascade extending past its
own 1 ms window. Report dropped and late counts separately; a late cascade that still completes
is a different fault from a missing reply.

### 4. CS-low window with traffic present

*Method*: channels 2 and 3 while the cascade runs. The read step overlaps the busiest part of
the cascade for modules 1–15 (§8.1), and UART RX interrupts run inside the CS-low window.
*Measure*: distribution of the CS-low duration over ≥ 10⁴ transactions; the maximum is what
matters, and the interrupt jitter shows as a tail.
*Must*: the 80-clock window never overlaps this module's own `EN` high, and
`GET_ERRCNT` indices 2–4 stay at 0 over a run of ≥ 10 minutes. If the safety-word CRC
counter moves, the SSC is being disturbed by the UART and the clock rate must come down.

### 5. Compensation and read step on the target

The cycle counts of §8.3 were measured in simavr on an ATmega328P, which is an AVRe core; the
ATtiny1616 is AVRxt. The object code is the same, the timing is not quite.

*Method*: build with `-DKER_TIMING_PIN=<pin>` — not present in this release; add a
`digitalWriteFast` pair around the call being timed in `ker_sensor_read_angle()` and rebuild.
Measure with channel 3 free.
*Measure*: (a) `ker_compensate()` alone with `N_HARM = 6`; (b) the whole read step; (c) the
every-16th read with its housekeeping transaction.

| | expected | must |
|---|---|---|
| `ker_compensate()`, N=6 worst case | 1099 cycles ≈ **55 µs** (§8.3) | ≤ 70 µs |
| read step | ≈ **114 µs** | ≤ 200 µs |
| read step + housekeeping | ≈ **147 µs** | ≤ 250 µs |
| read step + configuration-lock retry | ≈ 114 + 250 µs | ≤ 600 µs |

The last row is the worst case that can occur in a fault state (§6.2) and must still fit the
≈ 870 µs per-cycle slack of §8.1.

### 6. Reset → first CMD=2, worst supply sequencing

The write-eligibility latch (`T_ARM_WAIT` = 3 s, C3) only protects an installed module if the
M5 starts polling well before it expires.

*Method*: power the arm through its normal path; trigger on the module's supply rail rising;
measure to the first CMD=2 frame on channel 0. Repeat with the M5 powered last, with the
slowest supply ramp the hardware can produce, and after a brown-out dip.
*Must*: **≤ 1.5 s in every case** — a factor of two against `T_ARM_WAIT`. If it is not, the
latch is the wrong protection and §3.3's residual risk becomes a real one.

### 7. Start-up to first answered frame

*Method*: trigger on the supply rail or on `RESET`; measure to the module's first reply.
*Expected*: ≈ **9 ms** (§6.2: USERROW, `t_pon` 7 ms, configuration lock, first passing read).
*Must*: ≤ 15 ms, and the downstream modules must resume without the M5 faulting. Compare
against upstream, whose gap is shorter but of the same kind.

### 8. CMD=3 latency, and programming time

*Method*: bench bus, one module, `kercal`. Trigger on the end of the request frame.
*Must*: reply starts **≤ 1 ms** after the request for everything except `COMMIT_CAL` and
`SET_ID`, which must be **≤ 50 ms** (`T_PROG_MAX`, §4.3 rule 9). Record the distribution of
`COMMIT_CAL` over ≥ 50 writes; the USERROW programming time is open (O2), and whether it stalls
the CPU shows here as a gap in everything else.

### 9. Are readings 200 µs apart independent?

The station's averaging assumes they are; the datasheet does not say so (§4.10).

*Method*: no analyser. With the unit stationary, take 30 × `SAMPLE_START(e=10)` at one position
and compute the standard deviation of the 30 averages.
*Expected*: ≈ 0.05° / √1024 = **0.0016°**.
*Must*: ≤ 0.0024° (1.5× the independent value). Above that, raise `SAMPLE_SPACING` until it
holds, and re-run — the station's noise check (§7.2 step 2) uses `σ_MAX` = 0.0033°, so
correlated readings would eat the whole budget.

### 10. Data age

*Method*: one capture holding the sensor's update (inferred from the SSC transaction), the reply
on the wire, and a host timestamp taken on the M5's serial output. Repeat over ≥ 1000 cycles for
the jitter.
*Expected*: ≈ **1.8 ms** total (§8.5). *Must*: report it; there is no pass criterion, because
nothing downstream currently compensates for it. If it exceeds 3 ms, §8.5 is wrong and the
figure belongs in the arm's control documentation.

### 11. Float32 accumulation on a real M5

The one measurement that tests the reason for rounding to 8 LSB (D22, §7.1).

*Method*: a calibrated module clamped **≥ 128° from its zero** with the **sensor angle below
64°** — the cell where the arithmetic is most sensitive. Log the host angle for one hour with
the joint stationary, and again with it dithered by hand every few seconds.
*Must*: the 10 s mean must not move by more than **0.001°** over the hour. The simulation says
exactly zero (`test/results/m5_accumulation.txt`); a real M5 adds its own arithmetic, which is
what this checks. A module built with the v5 rounding would drift 0.004–0.013° per hour in the
same cell, which is the scale to look for.

---

## 3. Results

Fill in as measured. Leave a row blank rather than estimating it: an estimate in this table
would be indistinguishable from a measurement the next time someone reads it.

| # | Measurement | Expected | Measured | Date | By | Verdict |
|---|---|---|---|---|---|---|
| 1 | reply latency added per hop | ≤ 5 µs | | | | |
| 2 | full cascade | ≈ 500 µs | | | | |
| 3 | refresh rate, 60 s | ≥ 1 kHz, 0 dropped | | | | |
| 4 | CS-low window with traffic | no overlap, 0 errors | | | | |
| 5a | `ker_compensate()` N=6 | ≈ 55 µs | | | | |
| 5b | read step | ≈ 114 µs | | | | |
| 5c | read step + housekeeping | ≈ 147 µs | | | | |
| 6 | reset → first CMD=2 | ≤ 1.5 s | | | | |
| 7 | start-up to first reply | ≈ 9 ms | | | | |
| 8a | CMD=3 reply latency | ≤ 1 ms | | | | |
| 8b | `COMMIT_CAL` duration | ≤ 50 ms | | | | |
| 9 | scatter of K=1024 averages | ≈ 0.0016° | | | | |
| 10 | data age | ≈ 1.8 ms | | | | |
| 11 | M5 accumulation, 1 h | ≤ 0.001° | | | | |

Save each capture next to this file as `evidence/timing/<item>-<date>.sr` (sigrok) or `.sal`
(Saleae), and name it in the row. A verdict without a capture is an opinion.
