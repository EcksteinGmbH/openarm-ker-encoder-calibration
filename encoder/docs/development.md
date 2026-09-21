# Working on this repository

Where the project stands, how to set it up on a machine that has never seen it, and what to do
next. Written to be the **only** thing you need to read first — after it, `protocol-spec.md` is
the reference and `../CHANGELOG.md` is what was built.

If you are an assistant picking this up in a fresh session: **this repository is the state.** There
is no conversation history you are missing. Everything that was decided is in `protocol-spec.md`
§12 (decisions D1–D28, open questions O1–O6), everything that was argued about is in `reviews/`,
and everything that was measured is in `evidence/` and reproducible.

---

## 1. Set up a fresh Linux machine

```bash
git clone https://github.com/EcksteinGmbH/openarm-ker-encoder-calibration.git
cd openarm-ker-encoder-calibration/encoder

# Python: PlatformIO, numpy, the station simulations and the kercal tests
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt    # `uv venv` also works

# Build once. PlatformIO downloads avr-gcc and megaTinyCore itself (~200 MB, first run only).
.venv/bin/pio run
```

Expect `Flash: 10237 B (62.5%)`, `RAM: 459 B (22.4%)`. A different number means the toolchain
version moved; say so rather than editing the figure in the docs.

Two more tools, needed only by the full test suite:

```bash
sudo apt install simavr        # the AVR differential test runs here
gcc --version                  # host compiler, for the unit tests
```

Then:

```bash
cd test && ./run_tests.sh      # 16 checks, about 3 minutes
```

All 16 must pass. Missing tools are reported as SKIP, never as PASS, so a partial environment
gives a partial answer rather than a false one.

**Nothing else needs migrating.** `.venv/` (114 MB) is platform-specific and has absolute paths
baked in; `.pio/` is build output; `.omc/` is assistant scratch state. None of it is in git and
none of it should be.

## 2. Where things are

| | |
|---|---|
| `docs/protocol-spec.md` | the design. §12 is the decision log and the open questions |
| `../CHANGELOG.md` | what was built, what it costs, every place the code departs from the spec |
| `docs/compatibility-checklist.md` | 40 claims about not breaking an M5, each marked *desk* or *measured* |
| `docs/bench-and-station.md` | how to build the bench and the calibration station, with diagrams |
| `docs/timing-measurements.md` | the bench method and the empty results sheet |
| `docs/station-reference-encoder.md` | the calibration station's reference chain and purchasing (Chinese) |
| `docs/evidence/` | the reference implementation and every cited measurement, reproducible |
| `docs/reviews/` | 13 review passes and their 7 responses |
| `src/ker_*` | the firmware |
| `tools/kercal/` | the host library and CLI |
| `test/run_tests.sh` | everything verifiable without hardware |

`src/ker_comp.c` is a byte-for-byte port of `docs/evidence/v3-reference/ref_comp.c`, which is what
every accuracy figure in §7.5 was measured on. `test/run_tests.sh` fails if they drift apart. If you
change one, change both, and re-run `docs/evidence/v3-reference/regen_results.sh`.

## 3. Where the project stands

**The firmware is complete against spec v6 and has never run on hardware.** Everything claimed is
either measured off-target — the arithmetic, the resource usage, the simulations — or reasoned from
datasheets and Infineon's driver. Nothing has seen a TLE5012B, an RS-485 bus or an M5.

What is known to work, because it was measured:

- an uncalibrated module is bit-exact with upstream over all 32768 sensor codes;
- AVR and host builds of the compensation agree bit for bit over 21 coefficient sets, and three
  negative controls generated from the shipping source are caught;
- worst-case fixed-point error 0.003186° against a 0.005° budget;
- the M5's float32 accumulation is exactly zero over a simulated hour;
- the station gate passes no part above 0.02° as grade A and ships none above 0.05°, over 4000
  simulated parts.

What is **not** known: whether any of it behaves that way on a board.

**The station is being built** (2026-09-21). Its topology changed to two through-bore grating
encoders clamped on one precision shaft, which forced a change to the commissioning of §7.7 —
`evidence/v7-throughbore/` has the simulation and `bench-and-station.md` part 2 the build. A stepper
and driver are on order; nothing else is waiting on them.

## 4. What to do next, in order

### 4.1 `STAT.SFUSE` — one hour, one board, highest value

Spec §12.2 O2, first item. Does `SFUSE` clear at run time once `CRCPAR` is rewritten, or does it
latch until the sensor is reset?

If it latches, the configuration lock can never pass, `SENSOR_CFG_FAIL` sticks, and **every module
silently ships the uncalibrated mapping** — with `GET_CFG_VERIFY` reading `0x0017` as the only sign.
`SFUSE` is also inside `STAT_FAULT`, so every angle read would fail its status check too and the
persistent-fault rule would pass readings through degraded. Nothing downstream would notice.

Test: flash one module, put it on a bench bus alone, `kercal info --id 31`. `cfg_verify.passed`
must be true and `checks` must list all five. If `SFUSE_clear` is the only one missing, this is the
failure mode. Building that bench takes an afternoon: `bench-and-station.md` part 1.

### 4.2 O6 — field at the die

Spec §12.2 O6. Estimated 28–39 mT against a 30–50 mT requirement; the magnet is N52, so the gap is
the only remaining lever. Needs a Hall probe (€30–60); a phone magnetometer saturates two orders of
magnitude too early and `D_MAG` measures direction, not strength.

**Do this before the assembly is frozen**, because the answer may be "reduce the gap to 2.0–2.2 mm",
which is a mechanical change. There is no probe yet; until there is, the O1 hysteresis curve below is
a weak indirect indicator — see O6 for what it can and cannot tell you.

### 4.3 O1 — the first ten units, which needs the station

Spec §12.2 O1, in its stated order. The first item, the clockwise-against-counter-clockwise curve,
sets `HYST_MAX`, which is still the provisional 0.10°, and doubles as the indirect field check.

This is the first step that needs the calibration station, which has to be commissioned before it
may calibrate anything: `bench-and-station.md` part 2. Note that a first, coarse version of this
measurement needs neither the station nor a reference encoder — hysteresis is the difference between
the two approach directions at the *same* position, so a repeatable hard stop is enough to learn
whether it is near the 0.10° typical figure or much worse.

### 4.4 The bench sheet

`docs/timing-measurements.md` has the method and an empty results table for all eleven timing items.
Fill rows in as measured; leave a row blank rather than estimating it, because an estimate in that
table is indistinguishable from a measurement the next time someone reads it.

## 5. House rules

- **`M5/` is never modified.** The compatibility argument cites it (`M5/include/AngleProcessor.h:68-72`,
  `M5/src/main.cpp:425`), so it must stay, but it stays as upstream's.
- **`main` tracks upstream.** Work happens on `calibration`. Keeping `main` clean is what makes
  "Sync fork" work and lets a small upstream PR be cut without dragging the whole fork with it.
  Never merge `calibration` into `main`: most of this repository is fork identity — the README
  banner, `CLAUDE.md`, the changelog, `docs/`, `tools/` and `test/` — and none of it belongs
  upstream. `../../CLAUDE.md` lists what may never leave the fork, and how to cut an upstream PR
  without dragging it along.
- **Claims are marked.** *measured* means there is a command that reproduces it; anything else says
  so. If you find a figure that is neither, that is a defect.
- **New features go in new files**, and `src/main.cpp` stays as close to upstream as it can.
- **Licence**: files from upstream keep `Copyright 2026 Enactic, Inc.` and carry a modification
  notice; files written here are `Copyright 2026 Eckstein GmbH`. `src/ker_ssc.h` keeps the upstream
  notice because its contents were moved out of `src/main.cpp` unchanged.

## 6. Ignore rules

Repository-wide rules are in the root `.gitignore`. `M5/.gitignore` and `encoder/.gitignore` are
upstream's and are left exactly as upstream wrote them, so that the set of modified upstream files
stays as small as it can be; anything this fork needs to ignore goes in the root file instead.

One thing that must **not** be added there: a blanket build-output rule. `encoder/firmware/*.hex` is
tracked upstream.
